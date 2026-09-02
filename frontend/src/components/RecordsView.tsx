import { useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_META, severityText } from '../format'
import type { Conversation, RecordEntry } from '../types'

export function RecordsView({ conversation }: { conversation: Conversation }) {
  const [entries, setEntries] = useState<RecordEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    api
      .getSummary(conversation.id)
      .then((s) => alive && setEntries(s.entries))
      .catch((e: Error) => {
        if (alive) {
          setEntries([])
          setError(e.message || '載入失敗')
        }
      })
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [conversation.id])

  return (
    <main className="view full">
      <div className="view-head">
        <h2>皮膚記錄 · {conversation.bodyPart}</h2>
        <a className="btn ghost" href="/api/export">
          ⬇ 匯出數據 (zip)
        </a>
      </div>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : error ? (
        <p className="empty">⚠️ {error}（請確認 backend 已起）</p>
      ) : entries.length === 0 ? (
        <p className="empty">未有記錄。去「教練對話」影相／打卡，agent 會自動寫入日記。</p>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="entry-card">
            <div className="entry-date">{e.date}</div>
            <div className="entry-note">{e.note || '—'}</div>
            {(e.metrics?.length > 0 || (e.attributes ?? []).length > 0) && (
              <div className="entry-metrics">
                {(e.attributes ?? []).map((a) => (
                  <span key={a.key} className="chip attr">
                    {ATTRIBUTE_META[a.key]?.zh ?? a.key} {severityText(a.severity)} · {a.severity}/3
                  </span>
                ))}
                {e.metrics.map((m) => (
                  <span key={`${m.key}-${m.value}`} className={`chip ${m.dir}`}>
                    {m.key} {m.value}
                  </span>
                ))}
              </div>
            )}
            {e.photos?.length > 0 && (
              <div className="entry-photos">
                {e.photos.map((p) => {
                  const id = p.split('/').pop()?.replace('.jpg', '')
                  return <img key={p} src={`/api/photos/${id}`} alt="" />
                })}
              </div>
            )}
          </div>
        ))
      )}
    </main>
  )
}
