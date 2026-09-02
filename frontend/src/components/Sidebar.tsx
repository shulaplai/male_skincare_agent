import type { Conversation, View } from '../types'

interface Props {
  conversations: Conversation[]
  activeId: string
  view: View
  online: boolean
  onSelect: (id: string) => void
  onAdd: () => void
  onNavigate: (view: View) => void
}

const NAV: { key: View; label: string; icon: JSX.Element }[] = [
  {
    key: 'chat',
    label: '教練對話',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.5 8.5 0 0 1-8.5-8.5A8.5 8.5 0 0 1 12.5 3c.7 0 1.4.08 2 .24L17 5l-1.5 3 3.5 1-1 2.5z" />
      </svg>
    ),
  },
  {
    key: 'records',
    label: '皮膚記錄',
    icon: (
      <svg viewBox="0 0 24 24">
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="M3 9h18M8 4v16" />
      </svg>
    ),
  },
  {
    key: 'progress',
    label: '進度追蹤',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M3 17l6-6 4 4 7-7" />
        <path d="M14 7h7v7" />
      </svg>
    ),
  },
  {
    key: 'settings',
    label: '設定',
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7 7 0 0 0-.14-1.4l2-1.5-2-3.5-2.4 1A7 7 0 0 0 14 5.4L13.5 3h-3L10 5.4A7 7 0 0 0 7.6 6.6l-2.4-1-2 3.5 2 1.5A7 7 0 0 0 5 12a7 7 0 0 0 .14 1.4l-2 1.5 2 3.5 2.4-1A7 7 0 0 0 10 18.6l.5 2.4h3l.5-2.4a7 7 0 0 0 2.4-1.2l2.4 1 2-3.5-2-1.5A7 7 0 0 0 19 12z" />
      </svg>
    ),
  },
]

export function Sidebar({ conversations, activeId, view, online, onSelect, onAdd, onNavigate }: Props) {
  return (
    <aside className="side">
      <div className="brand">
        <span className="dot" />
        <div>
          <b>SkinCoach</b>
          <br />
          <span>MALE SKIN OS</span>
        </div>
      </div>

      <div>
        <div className="convo-head">
          <label>部位對話</label>
          <span className="add" title="新增對話" onClick={onAdd}>
            ＋
          </span>
        </div>
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`convo${c.id === activeId ? ' active' : ''}`}
            onClick={() => {
              onSelect(c.id)
              onNavigate('chat')
            }}
          >
            <span className="part">{c.icon}</span>
            <span className="t">
              <span className="name">{c.bodyPart}</span>
              <span className="meta">
                {c.isDefault ? '主對話' : '部位對話'}
                {c.cloudAnalysis ? ' · ☁️' : ' · 🔒'}
              </span>
            </span>
          </div>
        ))}
        <button className="new-convo" onClick={onAdd}>
          ＋ 新增部位對話
        </button>
        <div className="hint">
          例如：頭皮、背部、手腳…
          <br />
          每個部位有獨立日記、記憶、時間線。
        </div>
      </div>

      <nav className="nav">
        {NAV.map((n) => (
          <a key={n.key} className={view === n.key ? 'active' : ''} onClick={() => onNavigate(n.key)}>
            {n.icon}
            {n.label}
          </a>
        ))}
      </nav>

      <div className="profile">
        <div className="who">
          <div className="avatar" />
          <div>
            <div className="name">SkinCoach · 單機用戶</div>
            <div className="sub">{online ? 'Agent 在線' : '離線（只記 session）'}</div>
          </div>
        </div>
        <div className="skin-tag">
          <i className={online ? 'ok' : ''} /> 數據只存呢部機（local-first）
        </div>
      </div>
    </aside>
  )
}
