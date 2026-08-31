import { useRef, useState } from 'react'
import * as api from '../api'
import type { Conversation, Message } from '../types'
import { useTheme } from '../theme'

interface Props {
  conversation: Conversation
  conversations: Conversation[]
  messages: Message[]
  onSend: (text: string, photos: { id: string; path: string }[]) => void
  online: boolean
  onSelectConversation: (id: string) => void
}

function splitAdvice(a: string): { lead: string; rest: string } {
  const idx = a.indexOf(' —— ')
  if (idx === -1) return { lead: a, rest: '' }
  return { lead: a.slice(0, idx), rest: a.slice(idx) }
}

function Bubble({ m }: { m: Message }) {
  const label = m.role === 'user' ? '你' : '教練 · Agent'
  return (
    <div className={`msg ${m.role}`}>
      <div className={`a ${m.role}`} />
      <div className="bubble">
        <div className="meta">
          {label} · {m.time}
        </div>
        {m.escalate && <div className="escalate-banner">⚠️ 呢個情況建議轉介皮膚科醫生</div>}
        {m.text}
        {m.photo && (
          <span className="photo">
            <img src={m.photo} alt="皮膚相" />
          </span>
        )}
        {m.analysis && (
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
        )}
        {m.disclaimer && <div className="disclaimer">{m.disclaimer}</div>}
      </div>
    </div>
  )
}

export function Chat({ conversation, conversations, messages, onSend, online, onSelectConversation }: Props) {
  const { toggle } = useTheme()
  const [draft, setDraft] = useState('')
  const [attached, setAttached] = useState<{ id: string; path: string }[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [localMode, setLocalMode] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const submit = () => {
    const t = draft.trim()
    if (!t && attached.length === 0) return
    onSend(t || '（已上傳皮膚相）', attached)
    setDraft('')
    setAttached([])
  }

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    api
      .uploadPhoto(f)
      .then((p) => setAttached((prev) => [...prev, p]))
      .catch(() => window.alert('相片上傳失敗，請確認後端已起。'))
    e.target.value = ''
  }

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
        <div className="day">今天</div>
        <div className="hello">
          早晨呀 ☀️ 今日{conversation.bodyPart}感覺點？可以影張相，或者直接話我知食咗咩、用咗咩，我會
          <b>一路記住</b>幫你追蹤。
        </div>
        {messages.map((m) => (
          <Bubble key={m.id} m={m} />
        ))}
      </div>

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
        </div>
        {attached.map((a) => (
          <span key={a.id} className="attach">
            <img src={`/api/photos/${a.id}`} alt="預覽" />
            <i onClick={() => setAttached((prev) => prev.filter((x) => x.id !== a.id))}>×</i>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder={`問${conversation.bodyPart}教練任何嘢…（食咗咩／用咗咩／反應）`}
        />
        <span className="mode" title={localMode ? '本地模式：相唔會上雲分析' : '雲分析（opt-in）'}>
          本地 <span className={`sw${localMode ? ' on' : ''}`} onClick={() => setLocalMode((v) => !v)} /> 雲
        </span>
        <button className="send" onClick={submit}>
          發送
        </button>
      </div>
    </main>
  )
}
