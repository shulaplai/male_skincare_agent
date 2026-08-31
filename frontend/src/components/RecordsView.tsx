import { useEffect, useState } from 'react'
import * as api from '../api'
import type { Conversation, RecordEntry } from '../types'

export function RecordsView({ conversation }: { conversation: Conversation }) {
  const [entries, setEntries] = useState<RecordEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .getSummary(conversation.id)
      .then((s) => setEntries(s.entries))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
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
      ) : entries.length === 0 ? (
        <p className="empty">未有記錄。去「教練對話」影相／打卡，agent 會自動寫入日記。</p>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="entry-card">
            <div className="entry-date">{e.date}</div>
            <div className="entry-note">{e.note || '—'}</div>
            {e.metrics?.length > 0 && (
              <div className="entry-metrics">
                {e.metrics.map((m) => (
                  <span key={m.key} className={`chip ${m.dir}`}>
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
