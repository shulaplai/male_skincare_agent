import { useState } from 'react'
import type { Conversation, Message } from '../types'
import { useTheme } from '../theme'

interface Props {
  conversation: Conversation
  messages: Message[]
  onSend: (text: string) => void
  online: boolean
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

export function Chat({ conversation, messages, onSend, online }: Props) {
  const { toggle } = useTheme()
  const [draft, setDraft] = useState('')

  const submit = () => {
    const t = draft.trim()
    if (!t) return
    onSend(t)
    setDraft('')
  }

  return (
    <main className="chat">
      <header className="chathead">
        <div className="cur">
          <span className="part">{conversation.icon}</span>
          <h1>{conversation.bodyPart}</h1>
          <span className="switch">切換部位 ▾</span>
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
          <span className="iconbtn" title="加相">
            <svg viewBox="0 0 24 24">
              <rect x="3" y="5" width="18" height="14" rx="3" />
              <circle cx="8.5" cy="10" r="1.5" />
              <path d="M21 15l-5-5-9 9" />
            </svg>
          </span>
          <span className="iconbtn" title="影相">
            <svg viewBox="0 0 24 24">
              <path d="M4 7h3l2-3h6l2 3h3v13H4z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </span>
        </div>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder={`問${conversation.bodyPart}教練任何嘢…（食咗咩／用咗咩／反應）`}
        />
        <span className="mode">
          本地 <span className="sw" /> 雲
        </span>
        <button className="send" onClick={submit}>
          發送
        </button>
      </div>
    </main>
  )
}
