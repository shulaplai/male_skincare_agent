import { Sidebar } from '../components/Sidebar'
import { Chat } from '../components/Chat'
import { RightPanel } from '../components/RightPanel'
import { RecordsView } from '../components/RecordsView'
import { ProgressView } from '../components/ProgressView'
import { SettingsView } from '../components/SettingsView'
import { GuideView } from '../components/GuideView'
import { useSceneRoute } from '../hooks/useSceneRoute'
import type { SceneTab } from './defs'
import type { View } from '../types'
import type { ShellProps } from './defs'

/**
 * 結構 1：教練對話（對話主導）—— 即係原本成個 app 嘅排法。
 * Sidebar 全導覽 + chat 場景（中間對話＋右欄實時數據）+ records/progress/settings 頁。
 *
 * ⚠️ **場景一定要經 `useSceneRoute`（URL），唔可以係 `useState`。**
 * 呢個 shell 一度係唯一冇 migrate 嗰個，結果闊屏（即係 default 結構）：
 * - 撳完「皮膚記錄」reload 就跌返對話 —— mobile／journal／dash 早就修好嘅同一類 bug；
 * - 瀏覽器「上一頁」永遠唔會幫你返上一頁（實測撳完設定，URL 一路都係 `/`）；
 * - `?scene=guide` 深層連結完全冇反應（實測 DOM 同對話頁一模一樣）。
 * 新 shell 一律用 `useSceneRoute`；`fallback` 係第一個 tab。
 */
const CHAT_TABS: SceneTab[] = [
  { key: 'chat', label: '教練對話', icon: 'message-square' },
  { key: 'records', label: '皮膚記錄', icon: 'clipboard-list' },
  { key: 'progress', label: '進度追蹤', icon: 'chart-column' },
  { key: 'settings', label: '設定', icon: 'settings' },
]

/**
 * 呢個 shell 真正 render 到嘅 scene。`useSceneRoute` 用 `SHELL_SCENES` 驗 URL，而佢
 * 包含 `home`（其他 shell 嘅主畫面）—— 如果唔過濾，`?scene=home` 會令呢個 shell
 * 四個 branch 都唔中，變成一片空白。`guide` 冇 tab（由 Settings 入）但一樣係 page。
 */
const CHAT_VIEWS: readonly View[] = ['chat', 'records', 'progress', 'settings', 'guide']

export function ChatShell(p: ShellProps) {
  const [rawScene, goScene] = useSceneRoute(CHAT_TABS)
  const view: View = CHAT_VIEWS.includes(rawScene as View) ? (rawScene as View) : 'chat'
  const active = p.active
  if (!active) return null
  return (
    <>
      <Sidebar
        conversations={p.conversations}
        activeId={active.id}
        view={view}
        online={p.online}
        onSelect={p.onSelectConversation}
        onAdd={p.onAddConversation}
        onNavigate={goScene}
        onRename={p.onRenameConversation}
        onDelete={p.onDeleteConversation}
      />
      {view === 'chat' && (
        <>
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
          <RightPanel conversation={active} refreshKey={p.refreshKey} />
        </>
      )}
      {view === 'records' && <RecordsView conversation={active} />}
      {view === 'progress' && <ProgressView conversation={active} />}
      {view === 'guide' && <GuideView onBack={() => goScene('settings')} />}
      {view === 'settings' && (
        <SettingsView
          conversations={p.conversations}
          activeId={active.id}
          online={p.online}
          onSelectConversation={p.onSelectConversation}
          onAddConversation={p.onAddConversation}
          onRenameConversation={p.onRenameConversation}
          onDeleteConversation={p.onDeleteConversation}
          onNavigate={goScene}
        />
      )}
    </>
  )
}
