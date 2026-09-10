import { useMemo, useState } from 'react'
import { Chat } from '../components/Chat'
import { MemoryList, TimelineList } from '../components/blocks'
import { useEntryActions } from '../hooks/useEntryActions'
import { useInsightActions } from '../hooks/useInsightActions'
import { useSummary } from '../hooks/useSummary'
import { ATTRIBUTE_META, severityText } from '../format'
import type { Message, RecordEntry } from '../types'
import type { HomeProps } from './defs'

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

/** 每條 entry 當日最後一條教練回覆（用 App 已載入嘅 messages，唔另 fetch） */
function lastCoachByDate(messages: Message[]): Map<string, Message> {
  const map = new Map<string, Message>()
  for (const m of messages) {
    if (m.role !== 'coach' || m.error) continue
    map.set(m.date, m)
  }
  return map
}

/** 結構 2 home：皮膚日記 —— 逐日卡片 feed＋右欄記憶/時間線＋FAB 開對話 drawer */
export function JournalHome({ p, nav }: HomeProps) {
  const active = p.active!
  const cid = active.id
  const { summary, loading, error, reload } = useSummary(cid, p.refreshKey)
  const entryActions = useEntryActions(cid, reload)
  const { removeInsight } = useInsightActions(cid, reload)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [drawer, setDrawer] = useState(false)

  const messages = p.messages[cid] ?? []
  const coachByDate = useMemo(() => lastCoachByDate(messages), [messages])
  const entries = summary?.entries ?? []

  const startEdit = (entry: RecordEntry) => {
    setEditingId(entry.id)
    setDraft(entry.note || '')
  }
  const saveNote = (entry: RecordEntry) => {
    entryActions.saveNote(entry, draft)
    setEditingId(null)
  }

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
          <button className="btn" onClick={() => nav.go('chat')}>
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
            <button className="btn" onClick={() => nav.go('chat')}>
              ✍️ 今日打卡／問教練
            </button>
          </div>
        ) : (
          entries.map((entry) => {
            const reply = coachByDate.get(entry.date)
            return (
              <article className="day-card" key={entry.id}>
                <div className="day-card-head">
                  <div className="day-date">{dayLabel(entry.date)}</div>
                  <div className="entry-actions">
                    <button className="link-btn" onClick={() => startEdit(entry)}>
                      ✎ 改筆記
                    </button>
                    <button className="link-btn danger" onClick={() => entryActions.removeEntry(entry)}>
                      🗑 刪除
                    </button>
                  </div>
                </div>

                {(entry.photos?.length ?? 0) > 0 && (
                  <div className="jm-photos">
                    {entry.photos!.map((photoPath) => {
                      const pid = photoPath.split('/').pop()?.replace('.jpg', '')
                      return (
                        <span className="photo-cell" key={photoPath}>
                          <a href={`/api/photos/${pid}`} target="_blank" rel="noreferrer">
                            <img src={`/api/photos/${pid}`} alt={`${entry.date} 皮膚相`} />
                          </a>
                          <i
                            className="photo-x"
                            title="刪除呢張相"
                            onClick={() => entryActions.removePhoto(entry, photoPath)}
                          >
                            ×
                          </i>
                        </span>
                      )
                    })}
                  </div>
                )}

                <div className="entry-metrics">
                  {(entry.attributes ?? []).map((a) => (
                    <span key={a.key} className="chip attr">
                      {ATTRIBUTE_META[a.key]?.zh ?? a.key} {severityText(a.severity)} · {a.severity}/3
                    </span>
                  ))}
                  {(entry.products ?? []).map((product) => (
                    <span key={product} className="chip">
                      🧴 {product}
                    </span>
                  ))}
                  {(entry.metrics ?? []).map((m) => (
                    <span key={`${m.key}-${m.value}`} className={`chip ${m.dir}`}>
                      {m.key} {m.value}
                    </span>
                  ))}
                  {(entry.attributes?.length ?? 0) === 0 &&
                    (entry.products?.length ?? 0) === 0 &&
                    (entry.metrics?.length ?? 0) === 0 && <span className="chip neutral">冇指標（純文字筆記）</span>}
                </div>

                {editingId === entry.id ? (
                  <div className="note-edit">
                    <textarea
                      value={draft}
                      onChange={(ev) => setDraft(ev.target.value)}
                      rows={2}
                      placeholder="當日筆記（文字）"
                    />
                    <div className="note-actions">
                      <button className="btn ghost small" onClick={() => setEditingId(null)}>
                        取消
                      </button>
                      <button className="btn small" onClick={() => saveNote(entry)}>
                        儲存
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="day-note">{entry.note || '—'}</p>
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
          {summary && <MemoryList items={summary.insights} onDelete={removeInsight} />}
        </section>
        <section>
          <h3>因果時間線</h3>
          {summary && <TimelineList events={summary.timeline} />}
        </section>
        <p className="hint">時間線／記憶會同「教練對話」右欄同步 —— 真數據，冇 demo。</p>
      </aside>

      <button className="jm-fab" title="今日打卡／問教練" onClick={() => setDrawer(true)}>
        ✍️ 今日打卡
      </button>

      {drawer && (
        <div className="jm-drawer-veil" onClick={() => setDrawer(false)}>
          <div className="jm-drawer" onClick={(ev) => ev.stopPropagation()}>
            <div className="jm-drawer-head">
              <b>
                {active.icon} {active.bodyPart} · 教練對話
              </b>
              <i className="jm-drawer-x" onClick={() => setDrawer(false)}>
                ✕
              </i>
            </div>
            <div className="jm-drawer-body">
              <Chat
                conversation={active}
                conversations={p.conversations}
                messages={messages}
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
