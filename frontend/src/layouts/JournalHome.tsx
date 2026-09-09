import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api'
import { Chat } from '../components/Chat'
import { MemoryList, TimelineList } from '../components/blocks'
import { ATTRIBUTE_META, severityText } from '../format'
import type { Message, RecordEntry, Summary } from '../types'
import type { ShellProps } from './defs'

function dayLabel(date: string): string {
  const d = new Date(`${date}T00:00:00`)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((today.getTime() - d.getTime()) / 86400000)
  const wd = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  if (diff <= 0) return `今天 · 星期${wd}`
  if (diff === 1) return `昨天 · 星期${wd}`
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} · 星期${wd}`
}

/** 每條 entry 當日最後一條教練回覆（用 App 已載入嘅 messages，唔另 fetch）。 */
function lastCoachByDate(messages: Message[]): Map<string, Message> {
  const map = new Map<string, Message>()
  for (const m of messages) {
    if (m.role !== 'coach' || m.error) continue
    map.set(m.date, m)
  }
  return map
}

export function JournalHome({ p, onGoChat }: { p: ShellProps; onGoChat: () => void }) {
  const active = p.active!
  const cid = active.id
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [drawer, setDrawer] = useState(false)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getSummary(cid)
      .then(setSummary)
      .catch((e: Error) => {
        setSummary(null)
        setError(e.message || '載入失敗')
      })
      .finally(() => setLoading(false))
  }, [cid])

  useEffect(reload, [reload, p.refreshKey])

  const coachByDate = useMemo(() => lastCoachByDate(p.messages[cid] ?? []), [p.messages, cid])

  const startEdit = (e: RecordEntry) => {
    setEditingId(e.id)
    setDraft(e.note || '')
  }
  const saveNote = (e: RecordEntry) => {
    api
      .editEntryNote(cid, e.id, draft)
      .then(() => {
        setEditingId(null)
        reload()
      })
      .catch((err: Error) => window.alert(`儲存失敗：${err.message}`))
  }
  const onDeleteEntry = (e: RecordEntry) => {
    if (!window.confirm(`刪除 ${e.date} 嘅紀錄（相／指標／筆記）？時間線同日事件都會移除。冇得復原。`)) return
    api.deleteEntry(cid, e.id).then(reload).catch((err: Error) => window.alert(`刪除失敗：${err.message}`))
  }
  const onDeletePhoto = (e: RecordEntry, photoPath: string) => {
    if (!window.confirm(`刪除 ${e.date} 呢張相？冇得復原。`)) return
    const id = photoPath.split('/').pop()?.replace('.jpg', '')
    api.deleteEntryPhoto(e.id, id ?? '').then(reload).catch((err: Error) => window.alert(`刪相失敗：${err.message}`))
  }
  const onDeleteInsight = (m: { id?: string; text: string }) => {
    if (!m.id) return
    if (!window.confirm(`刪除呢條記憶：「${m.text}」？`)) return
    api.deleteInsight(cid, m.id).then(reload).catch((e: Error) => window.alert(`刪除失敗：${e.message}`))
  }

  const entries = summary?.entries ?? []
  const coachMsgs = p.messages[cid] ?? []

  return (
    <div className="jm">
      <div className="jm-feed">
        <div className="jm-hero">
          <div>
            <div className="k">皮膚日記 · {active.bodyPart}</div>
            <div className="t">
              {entries.length === 0
                ? '未有記錄。撳右下角同教練打卡／影相，agent 會自動寫低每日皮膚狀態。'
                : `共 ${entries.length} 日記錄。逐日卡：相、指標、筆記、同當日教練回覆。`}
            </div>
          </div>
          <button className="btn" onClick={onGoChat}>
            💬 開啟對話
          </button>
        </div>

        {loading ? (
          <p className="empty">載入中…</p>
        ) : error ? (
          <p className="empty">⚠️ {error}（請確認 backend 已起）</p>
        ) : entries.length === 0 ? (
          <div className="jm-empty">
            <p className="empty">未有記錄。呢度會由你嘅真數據逐日砌出嚟。</p>
            <button className="btn" onClick={onGoChat}>
              ✍️ 今日打卡／問教練
            </button>
          </div>
        ) : (
          entries.map((e) => {
            const reply = coachByDate.get(e.date)
            return (
              <article className="day-card" key={e.id}>
                <div className="day-card-head">
                  <div className="day-date">{dayLabel(e.date)}</div>
                  <div className="entry-actions">
                    <button className="link-btn" onClick={() => startEdit(e)}>
                      ✎ 改筆記
                    </button>
                    <button className="link-btn danger" onClick={() => onDeleteEntry(e)}>
                      🗑 刪除
                    </button>
                  </div>
                </div>

                {(e.photos?.length ?? 0) > 0 && (
                  <div className="jm-photos">
                    {e.photos!.map((pth) => {
                      const pid = pth.split('/').pop()?.replace('.jpg', '')
                      return (
                        <span className="photo-cell" key={pth}>
                          <a href={`/api/photos/${pid}`} target="_blank" rel="noreferrer">
                            <img src={`/api/photos/${pid}`} alt={`${e.date} 皮膚相`} />
                          </a>
                          <i className="photo-x" title="刪除呢張相" onClick={() => onDeletePhoto(e, pth)}>
                            ×
                          </i>
                        </span>
                      )
                    })}
                  </div>
                )}

                <div className="entry-metrics">
                  {(e.attributes ?? []).map((a) => (
                    <span key={a.key} className="chip attr">
                      {ATTRIBUTE_META[a.key]?.zh ?? a.key} {severityText(a.severity)} · {a.severity}/3
                    </span>
                  ))}
                  {(e.products ?? []).map((pr) => (
                    <span key={pr} className="chip">
                      🧴 {pr}
                    </span>
                  ))}
                  {(e.metrics ?? []).map((m) => (
                    <span key={`${m.key}-${m.value}`} className={`chip ${m.dir}`}>
                      {m.key} {m.value}
                    </span>
                  ))}
                  {((e.attributes?.length ?? 0) === 0) && ((e.products?.length ?? 0) === 0) && (e.metrics?.length ?? 0) === 0 && (
                    <span className="chip neutral">冇指標（純文字筆記）</span>
                  )}
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
                  <p className="day-note">{e.note || '—'}</p>
                )}

                {reply && (
                  <div className="jm-reply">
                    <div className="k">當日教練回覆{reply.vision_used ? ' · 👁 已睇相' : ''}</div>
                    <div className="t">{reply.text}</div>
                  </div>
                )}
              </article>
            )
          })
        )}
      </div>

      <aside className="jm-side">
        <section>
          <h3>AI 記得你</h3>
          {summary && (
            <MemoryList items={summary.insights} onDelete={(m) => onDeleteInsight({ id: m.id, text: m.text })} />
          )}
        </section>
        <section>
          <h3>因果時間線</h3>
          {summary && <TimelineList events={summary.timeline} />}
        </section>
        <p className="hint">時間線／記憶會同「教練對話」右欄同步 —— 真數據，冇 demo。</p>
      </aside>

      <button className="fab" title="今日打卡／問教練" onClick={() => setDrawer(true)}>
        ✍️ 今日打卡
      </button>

      {drawer && (
        <div className="drawer-veil" onClick={() => setDrawer(false)}>
          <div className="drawer" onClick={(ev) => ev.stopPropagation()}>
            <div className="drawer-head">
              <b>
                {active.icon} {active.bodyPart} · 教練對話
              </b>
              <i className="drawer-x" onClick={() => setDrawer(false)}>
                ✕
              </i>
            </div>
            <div className="drawer-body">
              <Chat
                conversation={active}
                conversations={p.conversations}
                messages={coachMsgs}
                sending={p.sending}
                onSend={p.onSend}
                online={p.online}
                loading={p.loadingThread}
                onSelectConversation={p.onSelectConversation}
                onToggleCloud={p.onToggleCloud}
                onConfirmEvents={p.onConfirmEvents}
                onQuickRecord={p.onQuickRecord}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
