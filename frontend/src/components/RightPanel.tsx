import { useEffect, useState } from 'react'
import * as api from '../api'
import { useConfirm } from './ui/Confirm'
import { useToast } from './ui/Toast'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META, severityText } from '../format'
import type { Conversation, MemoryItem, RecordEntry, Summary } from '../types'
import { Icon } from '../components/Icon'
import { Skeleton } from './ui/Skeleton'
import { EmptyState } from './ui/EmptyState'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  preference: '偏好',
  fact: '事實',
}

interface Props {
  conversation: Conversation
  refreshKey: number
}

function Spark({ series }: { series: number[] }) {
  const w = 240
  const h = 44
  if (series.length < 2) return null
  const max = Math.max(...series, 1)
  const pts = series.map((v, i) => {
    const x = (i / (series.length - 1)) * w
    const y = 2 + (1 - v / max) * (h - 8)
    return [x, y] as const
  })
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" preserveAspectRatio="none">
      <path className="line" d={line} />
    </svg>
  )
}

function attrSeries(entries: RecordEntry[], key: string): { dates: string[]; sev: number[] } {
  const dates: string[] = []
  const sev: number[] = []
  for (const e of [...entries].reverse()) {
    const a = (e.attributes ?? []).find((x) => x.key === key)
    if (a && a.severity != null) {
      dates.push(e.date)
      sev.push(a.severity)
    }
  }
  return { dates, sev }
}

export function RightPanel({ conversation, refreshKey }: Props) {
  const { toast } = useToast()
  const confirm = useConfirm()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'err'>('loading')

  const load = () => {
    setState('loading')
    api
      .getSummary(conversation.id)
      .then((s) => {
        setSummary(s)
        setState('ok')
      })
      .catch(() => setState('err'))
  }

  useEffect(() => {
    let alive = true
    setState('loading')
    api
      .getSummary(conversation.id)
      .then((s) => {
        if (!alive) return
        setSummary(s)
        setState('ok')
      })
      .catch(() => alive && setState('err'))
    return () => {
      alive = false
    }
  }, [conversation.id, refreshKey])

  const latest = summary?.entries?.[0] // entries are date-desc
  const prev = summary?.entries?.[1]
  const severityOf = (e: RecordEntry | undefined, key: string): number | null =>
    e ? (e.attributes ?? []).find((a) => a.key === key)?.severity ?? null : null

  const onDeleteInsight = async (m: MemoryItem) => {
    if (!m.id) return
    const ok = await confirm({
      title: '刪除呢條記憶？',
      body: `「${m.text}」`,
      confirmLabel: '刪除記憶',
      tone: 'danger',
    })
    if (!ok) return
    api
      .deleteInsight(conversation.id, m.id)
      .then(() => {
        load()
        toast('已刪除呢條記憶')
      })
      .catch((e: Error) => toast(`刪除失敗：${api.readableError(e)}`, { tone: 'err' }))
  }

  return (
    <aside className="right">
      <div className="panel-head">
        <h3>{conversation.bodyPart}</h3>
      </div>

      {state === 'err' && <p className="empty small">連唔到 backend。</p>}
      {state === 'loading' && <Skeleton lines={2} />}
      {state === 'ok' && summary && (
        <>
          <div>
            <h3>皮膚指標</h3>
            {latest && (latest.attributes ?? []).length > 0 ? (
              <div className="attr-list">
                {ATTRIBUTE_KEYS.map((key) => {
                  const cur = severityOf(latest, key)
                  const prevSev = severityOf(prev, key)
                  if (cur == null) return null
                  const delta = prevSev == null || prevSev === cur ? '' : cur > prevSev ? '↑ 惡化' : '↓ 改善'
                  return (
                    <div className="attr" key={key}>
                      <span className="k">{ATTRIBUTE_META[key].zh}</span>
                      <span className="dots">
                        {[0, 1, 2, 3].map((d) => (
                          <i key={d} className={d <= cur ? `on lv${cur}` : ''} />
                        ))}
                      </span>
                      <span className="sev">{severityText(cur)}</span>
                      <span className={`delta ${delta.includes('惡化') ? 'bad' : 'good'}`}>{delta}</span>
                    </div>
                  )
                })}
                <div className="trends">
                  {ATTRIBUTE_KEYS.map((key) => {
                    const s = attrSeries(summary.entries, key)
                    if (s.sev.length < 2) return null
                    return (
                      <div className="trend" key={key}>
                        <span className="k">{ATTRIBUTE_META[key].zh}</span>
                        <Spark series={s.sev} />
                        <span className="latest">{s.sev[s.sev.length - 1]}/3</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : (
              <EmptyState small icon="camera">未有指標。影張相／打個卡，agent 會寫低今日嘅皮膚狀態。</EmptyState>
            )}
          </div>

          <div>
            <h3>AI 記得你</h3>
            {summary.insights.length === 0 ? (
              <EmptyState small icon="sparkles">未有記憶。</EmptyState>
            ) : (
              <div className="mem-group">
                {summary.insights.map((m, i) => (
                  <div className="mem" key={m.id ?? i}>
                    <div className={`t ${m.kind}`}>
                      {kindLabel[m.kind] ?? m.kind}
                      {m.scope === 'global' && <span className="scope-badge"><Icon name="globe" size={12} /> 全局</span>}
                      {m.id && (
                        <button
                          type="button"
                          className="mem-x"
                          title="刪除呢條記憶（修正）"
                          aria-label={`刪除記憶：${m.text}`}
                          onClick={() => onDeleteInsight(m)}
                        >
                          ×
                        </button>
                      )}
                    </div>
                    <div className="txt">{m.text}</div>
                    {m.confidence != null && (
                      <>
                        <div className="conf">
                          <i style={{ width: `${Math.round(m.confidence * 100)}%` }} />
                        </div>
                        <div className="pct">confidence {m.confidence.toFixed(2)}</div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3>因果時間線</h3>
            {summary.timeline.length === 0 ? (
              <EmptyState small icon="clipboard-list">未有事件。自報嘅飲食／產品同明顯皮膚變化會喺度累積。</EmptyState>
            ) : (
              <div className="tl">
                {summary.timeline.map((e, i) => (
                  <div className="ev" key={i}>
                    <div className="d">
                      {e.date}
                      <span className={`src ${e.source ?? 'user'}`}>
                        {e.source === 'agent' ? (<><Icon name="sparkles" size={12} /> AI 偵測</>) : e.scope === 'global' ? (<><Icon name="globe" size={12} /> 飲食（全局）</>) : '你'}
                      </span>
                    </div>
                    <div className="x">{e.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  )
}
