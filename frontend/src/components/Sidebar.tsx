import type { Conversation, View } from '../types'
import { Icon } from './Icon'
import type { IconName } from './Icon'

interface Props {
  conversations: Conversation[]
  activeId: string
  view: View
  online: boolean
  onSelect: (id: string) => void
  onAdd: () => void
  onNavigate: (view: View) => void
  onRename: (c: Conversation) => void
  onDelete: (c: Conversation) => void
  /** compact = 淨係部位對話（journal/dash 結構用，冇 site 導覽同 profile） */
  compact?: boolean
}

/**
 * Site 導覽（桌面 chat 結構嘅左欄）。
 * ⚠️ 呢五個 icon 以前係**手畫 SVG** —— 同底部 nav 一樣，唔同來源嘅線重／視覺大小會唔一致，
 * 所以同 emoji 一樣要換成 registry（Lucide）。
 */
const NAV: { key: View; label: string; icon: IconName }[] = [
  { key: 'chat', label: '教練對話', icon: 'message-square' },
  { key: 'records', label: '皮膚記錄', icon: 'clipboard-list' },
  { key: 'progress', label: '進度追蹤', icon: 'chart-column' },
  { key: 'guide', label: '護膚指南', icon: 'book-open' },
  { key: 'settings', label: '設定', icon: 'settings' },
]

export function Sidebar({ conversations, activeId, view, online, onSelect, onAdd, onNavigate, onRename, onDelete, compact }: Props) {
  return (
    <aside className={`side${compact ? ' compact' : ''}`}>
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
          <span className="convo-head-title">部位對話</span>
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
              if (!compact) onNavigate('chat')
            }}
          >
            <span className="part">{c.icon}</span>
            <span className="t">
              <span className="name">{c.bodyPart}</span>
              <span className="meta">
                {c.isDefault ? '主對話' : '部位對話'}
              </span>
            </span>
            <span className="convo-actions" onClick={(e) => e.stopPropagation()}>
              <i title="改名" aria-label="改名" onClick={() => onRename(c)}><Icon name="pencil" size={14} /></i>
              <i title="刪除" aria-label="刪除" onClick={() => onDelete(c)}><Icon name="trash-2" size={14} /></i>
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

      {!compact && (
        <>
          <nav className="nav">
            {NAV.map((n) => (
              <a key={n.key} className={view === n.key ? 'active' : ''} onClick={() => onNavigate(n.key)}>
                <Icon name={n.icon} size={17} />
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
        </>
      )}
    </aside>
  )
}
