import { useState } from 'react'
import { Chat } from '../components/Chat'
import { ProgressView } from '../components/ProgressView'
import { RecordsView } from '../components/RecordsView'
import { SettingsView } from '../components/SettingsView'
import type { SceneTab, ShellNav, ShellProps, ShellScene } from './defs'
import { MobileHome } from './MobileHome'
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
  const [scene, setScene] = useState<ShellScene>('home')
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
        onToggleCloud={p.onToggleCloud}
      />

      <div className="shell-scene">
        {scene === 'home' && <MobileHome p={p} nav={nav} />}
        {scene === 'chat' && (
          <Chat
            conversation={active}
            conversations={p.conversations}
            messages={p.messages[active.id] ?? []}
            sending={p.sending}
            onSend={p.onSend}
            online={p.online}
            loading={p.loadingThread}
            onSelectConversation={p.onSelectConversation}
            onToggleCloud={p.onToggleCloud}
            onConfirmEvents={p.onConfirmEvents}
            onQuickRecord={p.onQuickRecord}
          />
        )}
        {scene === 'records' && <RecordsView conversation={active} />}
        {scene === 'progress' && <ProgressView conversation={active} />}
        {scene === 'settings' && (
          <SettingsView
            conversations={p.conversations}
            activeId={active.id}
            online={p.online}
            onSelectConversation={p.onSelectConversation}
            onAddConversation={p.onAddConversation}
            onRenameConversation={p.onRenameConversation}
            onDeleteConversation={p.onDeleteConversation}
          />
        )}
      </div>

      <nav className="mob-tabs" role="tablist" aria-label="手機版導覽">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={scene === t.key}
            className={scene === t.key ? 'active' : ''}
            onClick={() => setScene(t.key)}
          >
            <span className="ti" aria-hidden>
              {t.icon}
            </span>
            <span className="tl">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
