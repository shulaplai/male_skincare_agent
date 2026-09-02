import { useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META, severityText } from '../format'
import type { Conversation, MemoryItem, RecordEntry, Summary } from '../types'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  preference: '偏好',
  fact: '事實',
}

interface Props {
  conversation: Conversation
  refreshKey: number
  onToggleCloud: (id: string, enabled: boolean) => void
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

export function RightPanel({ conversation, refreshKey, onToggleCloud }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'err'>('loading')

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

  const cloud = conversation.cloudAnalysis
  const latest = summary?.entries?.[0] // entries are date-desc
  const prev = summary?.entries?.[1]
  const severityOf = (e: RecordEntry | undefined, key: string): number | null =>
    e ? (e.attributes ?? []).find((a) => a.key === key)?.severity ?? null : null

  return (
    <aside className="right">
      <div className="panel-head">
        <h3>{conversation.bodyPart}</h3>
        <span
          className={`cloud-toggle ${cloud ? 'on' : ''}`}
          title={cloud ? '雲分析已開（影相會送雲端 vision）' : '本地模式（相唔會上雲分析）'}
          onClick={() => onToggleCloud(conversation.id, !cloud)}
        >
          {cloud ? '☁️ 雲分析' : '🔒 本地'}
        </span>
      </div>

      {state === 'err' && <p className="empty small">連唔到 backend。</p>}
      {state === 'loading' && <p className="empty small">載入中…</p>}
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
              <p className="empty small">未有指標。影張相／打個卡，agent 會寫低今日嘅皮膚狀態。</p>
            )}
          </div>

          <div>
            <h3>AI 記得你</h3>
            {summary.insights.length === 0 ? (
              <p className="empty small">未有記憶。</p>
            ) : (
              <div className="mem-group">
                {summary.insights.map((m, i) => (
                  <div className="mem" key={i}>
                    <div className={`t ${m.kind}`}>{kindLabel[m.kind] ?? m.kind}</div>
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
              <p className="empty small">未有事件。自報嘅飲食／產品同明顯皮膚變化會喺度累積。</p>
            ) : (
              <div className="tl">
                {summary.timeline.map((e, i) => (
                  <div className="ev" key={i}>
                    <div className="d">
                      {e.date}
                      <span className={`src ${e.source ?? 'user'}`}>{e.source === 'agent' ? 'AI 偵測' : '你'}</span>
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
