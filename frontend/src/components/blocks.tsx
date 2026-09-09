import type { CorrelationResult, MemoryItem, RecordEntry, TimelineEvent } from '../types'

/** 純 display blocks：食 props，唔自己 fetch（新結構嘅 home 共用）。 */

export const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  preference: '偏好',
  fact: '事實',
}

export function Spark({ series, w = 240, h = 44 }: { series: number[]; w?: number; h?: number }) {
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

export function attrSeries(entries: RecordEntry[], key: string): { dates: string[]; sev: number[] } {
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

export function MemoryList({ items, onDelete }: { items: MemoryItem[]; onDelete?: (m: MemoryItem) => void }) {
  if (items.length === 0) return <p className="empty small">未有記憶。多打卡幾次，agent 會建立推導記憶。</p>
  return (
    <div className="mem-group">
      {items.map((m, i) => (
        <div className="mem" key={m.id ?? i}>
          <div className={`t ${m.kind}`}>
            {kindLabel[m.kind] ?? m.kind}
            {m.scope === 'global' && <span className="scope-badge">🌐 全局</span>}
            {onDelete && m.id && (
              <i className="mem-x" title="刪除呢條記憶（修正）" onClick={() => onDelete(m)}>
                ×
              </i>
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
  )
}

export function TimelineList({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return <p className="empty small">未有事件。自報嘅飲食／產品同明顯皮膚變化會喺度累積。</p>
  return (
    <div className="tl">
      {events.map((e, i) => (
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
  )
}

export function CorrelationList({ corr, loading }: { corr: CorrelationResult | null; loading: boolean }) {
  if (loading) return <p className="empty small">偵測緊…</p>
  if (!corr || corr.candidates.length === 0)
    return (
      <p className="empty small">
        {corr?.note ||
          '未有足夠數據去偵測「原因 → 變化」關聯。每日記低飲食／產品，我會自動比較事件前後。'}
      </p>
    )
  return (
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
  )
}
