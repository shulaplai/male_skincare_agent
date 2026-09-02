import { useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_META, severityText } from '../format'
import type { Conversation, RecordEntry } from '../types'

export function RecordsView({ conversation }: { conversation: Conversation }) {
  const [entries, setEntries] = useState<RecordEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getSummary(conversation.id)
      .then((s) => setEntries(s.entries))
      .catch((e: Error) => {
        setEntries([])
        setError(e.message || '載入失敗')
      })
      .finally(() => setLoading(false))
  }, [conversation.id])

  useEffect(reload, [reload])

  const startEdit = (e: RecordEntry) => {
    setEditingId(e.id)
    setDraft(e.note || '')
  }

  const saveNote = (e: RecordEntry) => {
    api
      .editEntryNote(conversation.id, e.id, draft)
      .then(() => {
        setEditingId(null)
        reload()
      })
      .catch((err: Error) => window.alert(`儲存失敗：${err.message}`))
  }

  const onDeleteEntry = (e: RecordEntry) => {
    if (!window.confirm(`刪除 ${e.date} 嘅紀錄（相／指標／筆記）？時間線同日事件都會移除。冇得復原。`)) return
    api
      .deleteEntry(conversation.id, e.id)
      .then(reload)
      .catch((err: Error) => window.alert(`刪除失敗：${err.message}`))
  }

  const onDeletePhoto = (e: RecordEntry, photoPath: string) => {
    if (!window.confirm(`刪除 ${e.date} 呢張相？冇得復原。`)) return
    const id = photoPath.split('/').pop()?.replace('.jpg', '')
    // Photo row id == stored file name id.
    api
      .deleteEntryPhoto(e.id, id ?? '')
      .then(reload)
      .catch((err: Error) => window.alert(`刪相失敗：${err.message}`))
  }

  return (
    <main className="view full">
      <div className="view-head">
        <h2>皮膚記錄 · {conversation.bodyPart}</h2>
        <a className="btn ghost" href="/api/export">
          ⬇ 匯出數據 (zip)
        </a>
      </div>
      <p className="hint">記錄係你嘅真數據：可以改筆記、刪走影錯嘅相、或者刪成日紀錄。</p>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : error ? (
        <p className="empty">⚠️ {error}（請確認 backend 已起）</p>
      ) : entries.length === 0 ? (
        <p className="empty">未有記錄。去「教練對話」影相／打卡，agent 會自動寫入日記。</p>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="entry-card">
            <div className="entry-date">
              {e.date}
              <span className="entry-actions">
                <button className="link-btn" onClick={() => startEdit(e)}>
                  ✎ 改筆記
                </button>
                <button className="link-btn danger" onClick={() => onDeleteEntry(e)}>
                  🗑 刪除
                </button>
              </span>
            </div>
            {editingId === e.id ? (
              <div className="note-edit">
                <textarea value={draft} onChange={(ev) => setDraft(ev.target.value)} rows={2} placeholder="當日筆記（文字）" />
                <div className="note-actions">
                  <button className="btn ghost small" onClick={() => setEditingId(null)}>
                    取消
                  </button>
                  <button className="btn small" onClick={() => saveNote(e)}>
                    儲存
                  </button>
                </div>
              </div>
            ) : (
              <div className="entry-note">{e.note || '—'}</div>
            )}
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
                  return (
                    <span className="photo-cell" key={p}>
                      <img src={`/api/photos/${id}`} alt="" />
                      <i className="photo-x" title="刪除呢張相" onClick={() => onDeletePhoto(e, p)}>
                        ×
                      </i>
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        ))
      )}
    </main>
  )
}
