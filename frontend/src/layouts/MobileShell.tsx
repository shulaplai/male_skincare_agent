import { Chat } from '../components/Chat'
import { ProgressView } from '../components/ProgressView'
import { RecordsView } from '../components/RecordsView'
import { SettingsView } from '../components/SettingsView'
import { GuideView } from '../components/GuideView'
import { useSceneRoute } from '../hooks/useSceneRoute'
import type { SceneTab, ShellNav, ShellProps } from './defs'
import { MobileHome } from './MobileHome'
import { NavIcon } from './navIcons'
import { ShellTop } from './ShellTop'

interface Props {
  p: ShellProps
  tabs: SceneTab[]
}

/**
 * 結構 4：手機版（窄屏自動，見 `defs.resolveLayout`）—— 風格 01「柔卡」。
 * 排法：頂部 bar（重用 `ShellTop`）→ 單欄 scene → 底部 5 個 tab bar。
 *
 * 刻意同 `StandardShell` 唔同嘅地方：
 * - scene 區用 `.shell-scene`，**唔可以用 `.shell-chat`** —— 嗰個係 2 欄 grid，
 *   而且 `AGENTS.md` 有明文警告同名／混用會撞壞成個 app grid。
 * - 頂部 `ShellTop` 嘅 `.scene-tabs` 由 CSS 收埋，改用底部 `.mob-tabs`。
 * - `Chat` 自己嘅 `.chathead` 由 CSS 收埋（`ShellTop` 已經提供同一組資訊：部位／狀態／雲／主題），
 *   避免手機上雙重 header 食掉一半高度。
 *
 * scene 對應同 `StandardShell` 一模一樣（同一批元件、同一組 props）→ feature parity 自動成立。
 */
export function MobileShell({ p, tabs }: Props) {
  // Page 系統：scene 寫入 URL（`?scene=chat`），所以 reload／上一頁會停喺同一頁
  const [scene, setScene] = useSceneRoute(tabs)
  const active = p.active
  if (!active) return null
  const nav: ShellNav = { go: setScene }

  return (
    <div className="shell-main mob-shell">
      <ShellTop
        bodyLabel={active.bodyPart}
        icon={active.icon}
        conversations={p.conversations}
        active={active}
        online={p.online}
        tabs={tabs}
        scene={scene}
        onScene={setScene}
        onSelectConversation={p.onSelectConversation}
      />

      <div className="shell-scene">
        {scene === 'home' && <MobileHome p={p} nav={nav} />}
        {scene === 'chat' && (
          <Chat
            conversation={active}
            conversations={p.conversations}
            messages={p.messages[active.id] ?? []}
            sending={p.sending}
            stage={p.stage}
            onSend={p.onSend}
            online={p.online}
            loading={p.loadingThread}
            onSelectConversation={p.onSelectConversation}
            onConfirmEvents={p.onConfirmEvents}
            onRetryMessage={p.onRetryMessage}
          />
        )}
        {scene === 'records' && <RecordsView conversation={active} />}
        {scene === 'progress' && <ProgressView conversation={active} />}
        {scene === 'guide' && <GuideView onBack={() => setScene('settings')} />}
        {scene === 'settings' && (
          <SettingsView
            conversations={p.conversations}
            activeId={active.id}
            online={p.online}
            onSelectConversation={p.onSelectConversation}
            onAddConversation={p.onAddConversation}
            onRenameConversation={p.onRenameConversation}
            onDeleteConversation={p.onDeleteConversation}
            onNavigate={setScene}
          />
        )}
      </div>

      {/* 唔用 `role="tablist"`／`role="tab"`：ARIA tabs 要配 `aria-controls` +
          roving tabindex + 左右方向鍵，做半套比唔做更差（讀屏會宣布「tab」但方向鍵
          冇反應）。普通 `<button>` + `aria-current` 已經完全可用。 */}
      <nav className="mob-tabs" aria-label="手機版導覽">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-current={scene === t.key ? 'page' : undefined}
            className={scene === t.key ? 'active' : ''}
            onClick={() => setScene(t.key)}
          >
            <span className="ti" aria-hidden>
              <NavIcon scene={t.key} />
            </span>
            <span className="tl">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
