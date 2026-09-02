import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Conversation, DetectedEvent, Message } from '../types'
import { useTheme } from '../theme'

interface Props {
  conversation: Conversation
  conversations: Conversation[]
  messages: Message[]
  loading: boolean
  sending: boolean
  onSend: (text: string, photos: { id: string; path: string }[]) => void
  online: boolean
  onSelectConversation: (id: string) => void
  onToggleCloud: (id: string, enabled: boolean) => void
  onConfirmEvents: (conversationId: string, msgId: string, events: DetectedEvent[]) => void
  onQuickRecord: (conversationId: string, diet: string, product: string) => void
}

function splitAdvice(a: string): { lead: string; rest: string } {
  const idx = a.indexOf(' —— ')
  if (idx === -1) return { lead: a, rest: '' }
  return { lead: a.slice(0, idx), rest: a.slice(idx) }
}

function dayChip(date: string): string {
  const d = new Date(`${date}T00:00:00`)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((today.getTime() - d.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function EventChips({ m, onConfirm }: { m: Message; onConfirm?: (msgId: string, evs: DetectedEvent[]) => void }) {
  if (!m.events?.length) return null
  return (
    <div className="events-row">
      <span className="ev-label">我留意到：</span>
      {m.events.map((e, i) => (
        <span key={i} className={`event-chip t-${e.type}`}>
          {e.type === 'diet' ? '🍜' : e.type === 'product_start' ? '🧴' : '✋'}{' '}
          {e.text || e.product_name}
        </span>
      ))}
      {onConfirm && (
        <span className="ev-actions">
          <button className="ev-yes" onClick={() => onConfirm(m.id, m.events!)}>
            ✅ 記低
          </button>
        </span>
      )}
    </div>
  )
}

function Bubble({ m, onConfirm }: { m: Message; onConfirm?: (msgId: string, evs: DetectedEvent[]) => void }) {
  const label = m.role === 'user' ? '你' : '教練 · Agent'
  return (
    <div className={`msg ${m.role}${m.error ? ' err' : ''}`}>
      <div className={`a ${m.role}`} />
      <div className="bubble">
        <div className="meta">
          {label} · {m.time}
          {m.pending && <span className="pending-dot">傳送緊…</span>}
        </div>
        {m.escalate && <div className="escalate-banner">⚠️ 呢個情況建議轉介皮膚科醫生</div>}
        {m.text}
        {m.photo && (
          <span className="photo">
            <img src={m.photo} alt="皮膚相" />
          </span>
        )}
        {m.role === 'coach' && m.analysis && (
          <>
            <div className={`vision-badge ${m.vision_used ? 'seen' : 'text'}`}>
              {m.vision_used ? '👁 已睇相分析（雲端）' : '✍️ 文字分析（未睇相）'}
            </div>
            <div className="card">
              <h4>{m.analysis.title}</h4>
              <div className="metrics">
                {m.analysis.metrics.map((mm) => (
                  <div className="metric" key={mm.key}>
                    <div className="k">{mm.key}</div>
                    <div className={`v ${mm.dir}`}>{mm.value}</div>
                    {mm.note && <div className="d">{mm.note}</div>}
                  </div>
                ))}
              </div>
              <ul className="advice">
                {m.analysis.advice.map((a, i) => {
                  const { lead, rest } = splitAdvice(a)
                  return (
                    <li key={i}>
                      <span className="n">{String(i + 1).padStart(2, '0')}</span>
                      <span>
                        <b>{lead}</b>
                        {rest}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          </>
        )}
        {m.disclaimer && <div className="disclaimer">{m.disclaimer}</div>}
        {m.role === 'coach' && <EventChips m={m} onConfirm={onConfirm} />}
      </div>
    </div>
  )
}

export function Chat({
  conversation,
  conversations,
  messages,
  loading,
  sending,
  onSend,
  online,
  onSelectConversation,
  onToggleCloud,
  onConfirmEvents,
  onQuickRecord,
}: Props) {
  const { toggle } = useTheme()
  const [draft, setDraft] = useState('')
  const [attached, setAttached] = useState<{ id: string; path: string }[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  const [quickDiet, setQuickDiet] = useState('')
  const [quickProduct, setQuickProduct] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // Reset per-conversation composer state when switching body part (fix D1:
  // a half-typed message must not leak into another conversation).
  useEffect(() => {
    setDraft('')
    setAttached([])
    setUploading(false)
    setUploadErr(null)
    setMenuOpen(false)
    setQuickOpen(false)
    setQuickDiet('')
    setQuickProduct('')
  }, [conversation.id])

  const submit = () => {
    const t = draft.trim()
    if (!t && attached.length === 0) return
    if (sending || uploading) return
    onSend(t || '（已上傳皮膚相）', attached)
    setDraft('')
    setAttached([])
  }

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setUploading(true)
    setUploadErr(null)
    api
      .uploadPhoto(f)
      .then((p) => setAttached((prev) => [...prev, p]))
      .catch((err: Error) => setUploadErr(err.message || '上傳失敗'))
      .finally(() => setUploading(false))
    e.target.value = ''
  }

  const cloudOn = conversation.cloudAnalysis
  const cloudLabel = cloudOn
    ? '雲分析已開：影相會送雲端 vision 分析'
    : '本地模式：相唔會上雲分析（純文字）'
  const busy = sending || uploading

  return (
    <main className="chat">
      <header className="chathead">
        <div className="cur">
          <span className="part">{conversation.icon}</span>
          <h1>{conversation.bodyPart}</h1>
          <div className="dropdown">
            <span className="switch" onClick={() => setMenuOpen((v) => !v)}>
              切換部位 ▾
            </span>
            {menuOpen && (
              <div className="dropdown-menu">
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    className={`dropdown-item${c.id === conversation.id ? ' active' : ''}`}
                    onClick={() => {
                      onSelectConversation(c.id)
                      setMenuOpen(false)
                    }}
                  >
                    {c.icon} {c.bodyPart}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="head-actions">
          <div className={`status${online ? '' : ' offline'}`}>
            <span className="pulse" /> {online ? 'Agent 在線' : '離線模式'}
          </div>
          <button className="theme" onClick={toggle} title="切換日/夜模式">
            <span className="sun">☀️</span>
            <span className="moon">🌙</span>
          </button>
        </div>
      </header>

      <div className="thread">
        <div className="hello">
          早晨呀 ☀️ 今日{conversation.bodyPart}感覺點？可以影張相，或者直接話我知食咗咩、用咗咩，我會
          <b>一路記住</b>幫你追蹤。
        </div>
        {loading && messages.length === 0 && <p className="empty small">載入緊對話歷史…</p>}
        {messages.map((m, i) => {
          const prevDate = i > 0 ? messages[i - 1].date : null
          return (
            <div key={m.id}>
              {m.date !== prevDate && <div className="day">{dayChip(m.date)}</div>}
              <Bubble m={m} onConfirm={(mid, evs) => onConfirmEvents(conversation.id, mid, evs)} />
            </div>
          )
        })}
        {sending && (
          <div className="msg coach">
            <div className="a coach" />
            <div className="bubble typing">
              <span className="pulse" /> 教練諗緊…（睇相＋分析＋建議，約 5–10 秒）
            </div>
          </div>
        )}
      </div>

      {quickOpen && (
        <div className="quickbar">
          <input
            value={quickDiet}
            onChange={(e) => setQuickDiet(e.target.value)}
            placeholder="飲食特別嘢（例：打邊爐·辣底）— 可空"
          />
          <input
            value={quickProduct}
            onChange={(e) => setQuickProduct(e.target.value)}
            placeholder="開始用產品（例：水楊酸 toner）— 可空"
          />
          <button
            className="btn ghost small"
            onClick={() => {
              onQuickRecord(conversation.id, quickDiet, quickProduct)
              setQuickDiet('')
              setQuickProduct('')
              setQuickOpen(false)
            }}
          >
            記低
          </button>
        </div>
      )}

      <div className="compose">
        <div className="tools">
          <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onPick} />
          <span className="iconbtn" title="加相" onClick={() => fileRef.current?.click()}>
            <svg viewBox="0 0 24 24">
              <rect x="3" y="5" width="18" height="14" rx="3" />
              <circle cx="8.5" cy="10" r="1.5" />
              <path d="M21 15l-5-5-9 9" />
            </svg>
          </span>
          <span className="iconbtn" title="影相" onClick={() => fileRef.current?.click()}>
            <svg viewBox="0 0 24 24">
              <path d="M4 7h3l2-3h6l2 3h3v13H4z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </span>
          <span className={`iconbtn ${quickOpen ? 'on' : ''}`} title="今日記錄（飲食／產品）" onClick={() => setQuickOpen((v) => !v)}>
            <svg viewBox="0 0 24 24">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <path d="M12 8v8M8 12h8" />
            </svg>
          </span>
        </div>
        {uploading && <span className="chip uploading">⏳ 上傳緊張相…</span>}
        {attached.map((a) => (
          <span key={a.id} className="attach ok">
            <img src={`/api/photos/${a.id}`} alt="預覽" />
            <i className="ok-mark">✓</i>
            <i className="x" onClick={() => setAttached((prev) => prev.filter((x) => x.id !== a.id))}>
              ×
            </i>
          </span>
        ))}
        {uploadErr && <span className="chip upload-err">✗ 上傳失敗：{uploadErr}</span>}
        {attached.length > 0 && !cloudOn && (
          <span className="warn-chip">⚠️ 本地模式：張相唔會俾 AI 睇（撳 ☁️ 開雲分析先會睇相）</span>
        )}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder={`問${conversation.bodyPart}教練任何嘢…（食咗咩／用咗咩／反應）`}
        />
        <span
          className={`mode ${cloudOn ? 'cloud' : 'local'}`}
          title={cloudLabel}
          onClick={() => online && onToggleCloud(conversation.id, !cloudOn)}
        >
          {cloudOn ? '☁️ 雲' : '🔒 本地'}
        </span>
        <button className="send" onClick={submit} disabled={busy}>
          {sending ? '處理中…' : '發送'}
        </button>
      </div>
    </main>
  )
}
