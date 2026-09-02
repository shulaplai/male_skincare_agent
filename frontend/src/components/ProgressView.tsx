import { useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META } from '../format'
import type { Conversation, CorrelationResult, MemoryItem, RecordEntry, Summary } from '../types'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  preference: '偏好',
  fact: '事實',
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

function AnchorRow({ a }: { a: { key: string; label: string; severity: number; prev: { date: string; old: number; delta: number } | null; month: { date: string; old: number; delta: number } | null; quarter: { date: string; old: number; delta: number } | null } }) {
  const cell = (v: { date: string; old: number; delta: number } | null) => {
    if (!v) return <span className="anchor-cell none">—</span>
    const cls = v.delta === 0 ? 'same' : v.delta > 0 ? 'bad' : 'good'
    const arrow = v.delta === 0 ? '→' : v.delta > 0 ? '↑' : '↓'
    return (
      <span className={`anchor-cell ${cls}`} title={`${v.date}：${v.old}/3 → ${a.severity}/3`}>
        {arrow} {Math.abs(v.delta)}
      </span>
    )
  }
  return (
    <div className="anchor-row">
      <span className="k">{a.label}</span>
      <span className="now">{a.severity}/3</span>
      {cell(a.prev)}
      {cell(a.month)}
      {cell(a.quarter)}
    </div>
  )
}

function Correlations({ corr, loading }: { corr: CorrelationResult | null; loading: boolean }) {
  return (
    <div className="corr-block">
      {loading ? (
        <p className="empty small">偵測緊…</p>
      ) : !corr || corr.candidates.length === 0 ? (
        <p className="empty small">
          {corr?.note ||
            '未有足夠數據去偵測「原因 → 變化」關聯。每日記低飲食／產品，我會自動比較事件前後。'}
        </p>
      ) : (
        <>
          <p className="corr-note">{corr.note}</p>
          <div className="corr-list">
            {corr.candidates.map((c, i) => (
              <div className={`corr-item ${c.strong ? 'strong' : 'weak'}`} key={i}>
                <div className="t">
                  {c.cause_label} → {c.attribute_label} {c.direction === 'up' ? '↑ 惡化' : '↓ 改善'}
                </div>
                <div className="x">{c.note}</div>
                <div className="meta">
                  {c.occurrences} 次觀察 · {c.first_date} → {c.last_date}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function ProgressView({ conversation }: { conversation: Conversation }) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [corr, setCorr] = useState<CorrelationResult | null>(null)
  const [corrLoading, setCorrLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    api
      .getSummary(conversation.id)
      .then((s) => alive && setSummary(s))
      .catch(() => alive && setSummary(null))
      .finally(() => alive && setLoading(false))
    api
      .getCorrelations(conversation.id)
      .then((c) => alive && setCorr(c))
      .catch(() => alive && setCorr(null))
      .finally(() => alive && setCorrLoading(false))
    return () => {
      alive = false
    }
  }, [conversation.id])

  const entries = summary?.entries ?? []

  return (
    <main className="view full">
      <div className="view-head">
        <h2>進度追蹤 · {conversation.bodyPart}</h2>
      </div>

      <h3 className="block-title">皮膚指標趨勢（真實數據 · 0–3 級）</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : entries.length === 0 ? (
        <p className="empty">未有數據。去「教練對話」影相／打卡，趨勢會由你嘅真實紀錄畫出嚟。</p>
      ) : (
        <div className="attr-list" style={{ maxWidth: 640 }}>
          {ATTRIBUTE_KEYS.map((key) => {
            const s = attrSeries(entries, key)
            if (s.sev.length === 0) return null
            const first = s.sev[0]
            const last = s.sev[s.sev.length - 1]
            const delta = last - first
            const trend = delta === 0 ? '持平' : delta < 0 ? `↓ 改善 ${-delta} 級` : `↑ 惡化 ${delta} 級`
            return (
              <div className="trend" key={key}>
                <span className="k">{ATTRIBUTE_META[key].zh}</span>
                <span className="date-range">{s.dates[0]} → {s.dates[s.dates.length - 1]}</span>
                <span className={`delta ${delta > 0 ? 'bad' : delta < 0 ? 'good' : ''}`}>{trend}</span>
              </div>
            )
          })}
        </div>
      )}

      <h3 className="block-title">同基準比較（上次 / 約 1 個月 / 約 3 個月）</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : !summary || summary.anchors.length === 0 ? (
        <p className="empty">
          未有得比較。記錄夠 3 日以上，最新一日就會同上次／約 1 個月前／約 3 個月前比較（±7 日內最接近嗰日）。
        </p>
      ) : (
        <div className="anchor-table" style={{ maxWidth: 640 }}>
          <div className="anchor-row head">
            <span className="k">指標</span>
            <span className="now">最新</span>
            <span className="anchor-cell">vs 上次</span>
            <span className="anchor-cell">vs 1 個月</span>
            <span className="anchor-cell">vs 3 個月</span>
          </div>
          {summary.anchors.map((a) => (
            <AnchorRow key={a.key} a={a} />
          ))}
        </div>
      )}

      <h3 className="block-title">相關性觀察（自動偵測 · 唔等於因果）</h3>
      <div style={{ maxWidth: 640 }}>
        <Correlations corr={corr} loading={corrLoading} />
      </div>

      <h3 className="block-title">AI 記得你</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : !summary || summary.insights.length === 0 ? (
        <p className="empty">未有記憶。多打卡幾次，agent 會建立推導記憶。</p>
      ) : (
        <div className="mem-group" style={{ maxWidth: 560 }}>
          {summary.insights.map((m, i) => (
            <div className="mem" key={i}>
              <div className={`t ${m.kind}`}>
                {kindLabel[m.kind] ?? m.kind}
                {m.scope === 'global' && <span className="scope-badge">🌐 全局</span>}
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

      <h3 className="block-title">因果時間線</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : !summary || summary.timeline.length === 0 ? (
        <p className="empty">未有時間線。</p>
      ) : (
        <div className="tl" style={{ maxWidth: 560 }}>
          {summary.timeline.map((e, i) => (
            <div className="ev" key={i}>
              <div className="d">
                {e.date}
                <span className={`src ${e.source ?? 'user'}`}>
                  {e.source === 'agent' ? 'AI 偵測' : e.scope === 'global' ? '🌐 飲食（全局）' : '你'}
                </span>
              </div>
              <div className="x">{e.text}</div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
