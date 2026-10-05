import type { Conversation, View } from '../types'
import type { ShellScene } from '../layouts/defs'
import { linkClick, sceneHref } from '../hooks/useSceneRoute'
import { Icon } from './Icon'
import type { IconName } from './Icon'

interface Props {
  conversations: Conversation[]
  activeId: string
  view: View
  online: boolean
  onSelect: (id: string) => void
  onAdd: () => void
  onNavigate: (view: ShellScene) => void
  onRename: (c: Conversation) => void
  onDelete: (c: Conversation) => void
  /** compact = 淨係部位對話（journal/dash 結構用，冇 site 導覽同 profile） */
  compact?: boolean
}

/**
 * Site 導覽（桌面 chat 結構嘅左欄）。
 * ⚠️ 呢五個 icon 以前係**手畫 SVG** —— 同底部 nav 一樣，唔同來源嘅線重／視覺大小會唔一致，
 * 所以同 emoji 一樣要換成 registry（Lucide）。
 *
 * ⚠️ 導覽項一定要係**有 `href` 嘅 `<a>`**，唔可以 `onClick` 就算（見 `sceneHref` 註解）：
 * 冇 href 嘅 `<a>` 唔入 tab order，純鍵盤用戶入唔到記錄／進度／設定。
 */
const NAV: { key: View; label: string; icon: IconName }[] = [
  { key: 'chat', label: '教練對話', icon: 'message-square' },
  { key: 'records', label: '皮膚記錄', icon: 'clipboard-list' },
  { key: 'progress', label: '進度追蹤', icon: 'chart-column' },
  { key: 'guide', label: '護膚指南', icon: 'book-open' },
  { key: 'settings', label: '設定', icon: 'settings' },
]

/** ChatShell 嘅 default scene（`useSceneRoute` 嘅 fallback）—— 決定邊啲 nav 唔寫 URL 參數。 */
const FALLBACK = 'chat'

export function Sidebar({ conversations, activeId, view, online, onSelect, onAdd, onNavigate, onRename, onDelete, compact }: Props) {
  return (
    <aside className={`side${compact ? ' compact' : ''}`}>
      {/* 每個 scene 都要有一個 `<h1>`：chat 結構冇 `ShellTop`（body part 嗰個 h1 喺嗰度），
          而 axe 嘅 `heading-order` 係 **best-practice** rule、唔在 wcag tag 入面，所以
          12 條 axe test 捉唔到（2026-10-05 實測：記錄／進度／設定／指南頁嘅第一個
          heading 係 h2）。`tests/ui/a11y.spec.ts`「heading 層級」就係補呢個盲點。 */}
      <h1 className="sr-only">{NAV.find((n) => n.key === view)?.label ?? '教練對話'}</h1>
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
          <button type="button" className="add" aria-label="新增對話" title="新增對話" onClick={onAdd}>
            ＋
          </button>
        </div>
        {conversations.map((c) => (
          <div key={c.id} className={`convo${c.id === activeId ? ' active' : ''}`}>
            {/* 以前成行 `.convo` 係 `<div onClick>`：入唔到 tab order、讀屏唔知佢撳得。
                而家由一個真 `<button>` 包住 icon＋名（rename／delete 係佢兄弟，
                button 唔可以嵌套 button）。 */}
            <button
              type="button"
              className="convo-open"
              aria-current={c.id === activeId ? 'true' : undefined}
              onClick={() => {
                onSelect(c.id)
                if (!compact) onNavigate('chat')
              }}
            >
              <span className="part" aria-hidden>{c.icon}</span>
              <span className="t">
                <span className="name">{c.bodyPart}</span>
                <span className="meta">{c.isDefault ? '主對話' : '部位對話'}</span>
              </span>
            </button>
            <span className="convo-actions">
              <button type="button" title="改名" aria-label={`改名：${c.bodyPart}`} onClick={() => onRename(c)}>
                <Icon name="pencil" size={14} />
              </button>
              <button type="button" title="刪除" aria-label={`刪除：${c.bodyPart}`} onClick={() => onDelete(c)}>
                <Icon name="trash-2" size={14} />
              </button>
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
          <nav className="nav" aria-label="主要導覽">
            {NAV.map((n) => (
              <a
                key={n.key}
                href={sceneHref(n.key, FALLBACK)}
                className={view === n.key ? 'active' : ''}
                aria-current={view === n.key ? 'page' : undefined}
                onClick={linkClick(n.key, onNavigate)}
              >
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
