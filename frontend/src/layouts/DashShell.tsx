import { useState } from 'react'
import { Chat } from '../components/Chat'
import { ProgressView } from '../components/ProgressView'
import { RecordsView } from '../components/RecordsView'
import { RightPanel } from '../components/RightPanel'
import { SettingsView } from '../components/SettingsView'
import { Sidebar } from '../components/Sidebar'
import type { View } from '../types'
import type { SceneTab, ShellScene, ShellProps } from './defs'
import { DashHome } from './DashHome'
import { ShellTop } from './ShellTop'

const TABS: SceneTab[] = [
  { key: 'home', label: '進度儀表板', icon: '📊' },
  { key: 'chat', label: '教練對話', icon: '💬' },
  { key: 'records', label: '完整記錄', icon: '🗂️' },
  { key: 'progress', label: '進度', icon: '📈' },
  { key: 'settings', label: '設定', icon: '⚙️' },
]

/**
 * 結構 3：進度儀表板（數據主導）—— 左欄部位、主區係 widgets 大廳。
 * 打卡／詳細頁全部由頂部 tabs 同大廳按鈕進入。
 */
export function DashShell(p: ShellProps) {
  const [scene, setScene] = useState<ShellScene>('home')
  const active = p.active
  if (!active) return null
  return (
    <>
      <Sidebar
        compact
        conversations={p.conversations}
        activeId={active.id}
        view={(scene === 'home' ? 'progress' : scene) as View}
        online={p.online}
        onSelect={p.onSelectConversation}
        onAdd={p.onAddConversation}
        onNavigate={() => {}}
        onRename={p.onRenameConversation}
        onDelete={p.onDeleteConversation}
      />
      <div className="shell-main">
        <ShellTop
          bodyLabel={`${active.bodyPart} · 儀表板`}
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
          {scene === 'home' && (
            <DashHome
              p={p}
              onGoChat={() => setScene('chat')}
              onGoRecords={() => setScene('records')}
              onGoProgress={() => setScene('progress')}
            />
          )}
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
