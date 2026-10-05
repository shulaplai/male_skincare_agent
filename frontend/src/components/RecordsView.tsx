import { useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_META, severityText } from '../format'
import type { Conversation, RecordEntry } from '../types'
import { BlurPhoto } from './BlurPhoto'
import { Icon } from './Icon'
import { useConfirm } from './ui/Confirm'
import { useToast } from './ui/Toast'
import { Skeleton } from './ui/Skeleton'
import { EmptyState } from './ui/EmptyState'

export function RecordsView({ conversation }: { conversation: Conversation }) {
  const { toast } = useToast()
  const confirm = useConfirm()
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
        setError(api.readableError(e))
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
        toast('筆記已更新')
      })
      .catch((err: Error) => toast(`儲存失敗：${api.readableError(err)}`, { tone: 'err' }))
  }

  const onDeleteEntry = async (e: RecordEntry) => {
    const ok = await confirm({
      title: `刪除 ${e.date} 嘅紀錄？`,
      body: '會移除當日嘅相、指標、筆記，同埋嗰日嘅時間線事件。冇得復原。',
      confirmLabel: '刪除紀錄',
      tone: 'danger',
    })
    if (!ok) return
    api
      .deleteEntry(conversation.id, e.id)
      .then(() => {
        reload()
        toast(`已刪除 ${e.date} 嘅紀錄`)
      })
      .catch((err: Error) => toast(`刪除失敗：${api.readableError(err)}`, { tone: 'err' }))
  }

  /* Photo row id == 檔名 id（route 按 path 搵 row）。 */
  const onDeletePhoto = async (e: RecordEntry, photoPath: string) => {
    const ok = await confirm({
      title: `刪除 ${e.date} 呢張相？`,
      body: '檔案會由你部機永久刪除，冇得復原。',
      confirmLabel: '刪除相片',
      tone: 'danger',
    })
    if (!ok) return
    const id = photoPath.split('/').pop()?.replace('.jpg', '')
    api
      .deleteEntryPhoto(e.id, id ?? '')
      .then(() => {
        reload()
        toast('已刪除呢張相')
      })
      .catch((err: Error) => toast(`刪相失敗：${api.readableError(err)}`, { tone: 'err' }))
  }

  return (
    <main tabIndex={0} role="region" aria-label="記錄內容" className="view full">
      <div className="view-head">
        <h2>皮膚記錄 · {conversation.bodyPart}</h2>
        <a className="btn ghost" href="/api/export">
          <Icon name="download" size={16} /> 匯出數據 (zip)
        </a>
      </div>
      <p className="hint">記錄係你嘅真數據：可以改筆記、刪走影錯嘅相、或者刪成日紀錄。</p>
      {loading ? (
        <Skeleton lines={3} />
      ) : error ? (
        <p className="empty">
            <Icon name="circle-alert" size={16} /> {error}（請確認 backend 已起）
          </p>
      ) : entries.length === 0 ? (
        <EmptyState icon="clipboard-list">未有記錄。去「教練對話」影相／打卡，agent 會自動寫入日記。</EmptyState>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="entry-card">
            <div className="entry-date">
              {e.date}
              <span className="entry-actions">
                <button className="link-btn" onClick={() => startEdit(e)}>
                  <Icon name="pencil" size={15} /> 改筆記
                </button>
                <button className="link-btn danger" onClick={() => onDeleteEntry(e)}>
                  <Icon name="trash-2" size={15} /> 刪除
                </button>
              </span>
            </div>
            {editingId === e.id ? (
              <div className="note-edit">
                <textarea
                  value={draft}
                  onChange={(ev) => setDraft(ev.target.value)}
                  rows={2}
                  placeholder="當日筆記（文字）"
                  aria-label={`${e.date} 當日筆記`}
                />
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
                      {/* 皮膚相一律經 `BlurPhoto` —— 呢度以前係裸 `<img>`，即係「記錄」
                          tab 全部自拍都係全清（見 `BlurPhoto` docstring）。 */}
                      <BlurPhoto
                        src={`/api/photos/${id}`}
                        alt={`${e.date} 皮膚相`}
                        variant="grid"
                        thumbWidth={192}
                      />
                      <button
                        type="button"
                        className="photo-x"
                        aria-label={`刪除 ${e.date} 呢張相`}
                        title="刪除呢張相"
                        onClick={() => onDeletePhoto(e, p)}
                      />
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
