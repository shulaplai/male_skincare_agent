import { useState } from 'react'
import { Chat } from '../components/Chat'
import { ProgressView } from '../components/ProgressView'
import { RecordsView } from '../components/RecordsView'
import { RightPanel } from '../components/RightPanel'
import { SettingsView } from '../components/SettingsView'
import { Sidebar } from '../components/Sidebar'
import type { View } from '../types'
import type { SceneTab, ShellScene, ShellProps } from './defs'
import { JournalHome } from './JournalHome'
import { ShellTop } from './ShellTop'

const TABS: SceneTab[] = [
  { key: 'home', label: '皮膚日記', icon: '📔' },
  { key: 'chat', label: '教練對話', icon: '💬' },
  { key: 'records', label: '完整記錄', icon: '🗂️' },
  { key: 'progress', label: '進度', icon: '📈' },
  { key: 'settings', label: '設定', icon: '⚙️' },
]

/**
 * 結構 2：皮膚日記（日記主導）—— 左欄部位、中間逐日 feed、右欄記憶/時間線。
 * 其他功能（對話／完整記錄／進度／設定）由頂部 tabs 進入，唔會冇咗功能。
 */
export function JournalShell(p: ShellProps) {
  const [scene, setScene] = useState<ShellScene>('home')
  const active = p.active
  if (!active) return null
  return (
    <>
      <Sidebar
        compact
        conversations={p.conversations}
        activeId={active.id}
        view={(scene === 'home' ? 'records' : scene) as View}
        online={p.online}
        onSelect={p.onSelectConversation}
        onAdd={p.onAddConversation}
        onNavigate={() => {}}
        onRename={p.onRenameConversation}
        onDelete={p.onDeleteConversation}
      />
      <div className="shell-main">
        <ShellTop
          bodyLabel={`${active.bodyPart} · 日記`}
          icon={active.icon}
          conversations={p.conversations}
          active={active}
          online={p.online}
          tabs={TABS}
          scene={scene}
          onScene={setScene}
          onSelectConversation={p.onSelectConversation}
          onToggleCloud={p.onToggleCloud}
        />
        <div className="shell-scene">
          {scene === 'home' && <JournalHome p={p} onGoChat={() => setScene('chat')} />}
          {scene === 'chat' && (
            <div className="shell-chat">
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
              <RightPanel conversation={active} refreshKey={p.refreshKey} onToggleCloud={p.onToggleCloud} />
            </div>
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
      </div>
    </>
  )
}
