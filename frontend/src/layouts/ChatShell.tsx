import { useState } from 'react'
import { Sidebar } from '../components/Sidebar'
import { Chat } from '../components/Chat'
import { RightPanel } from '../components/RightPanel'
import { RecordsView } from '../components/RecordsView'
import { ProgressView } from '../components/ProgressView'
import { SettingsView } from '../components/SettingsView'
import type { View } from '../types'
import type { ShellProps } from './defs'

/**
 * 結構 1：教練對話（對話主導）—— 即係原本成個 app 嘅排法。
 * Sidebar 全導覽 + chat 場景（中間對話＋右欄實時數據）+ records/progress/settings 頁。
 */
export function ChatShell(p: ShellProps) {
  const [view, setView] = useState<View>('chat')
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
        onNavigate={setView}
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
            onSend={p.onSend}
            online={p.online}
            loading={p.loadingThread}
            onSelectConversation={p.onSelectConversation}
            onToggleCloud={p.onToggleCloud}
            onConfirmEvents={p.onConfirmEvents}
            onQuickRecord={p.onQuickRecord}
          />
          <RightPanel conversation={active} refreshKey={p.refreshKey} onToggleCloud={p.onToggleCloud} />
        </>
      )}
      {view === 'records' && <RecordsView conversation={active} />}
      {view === 'progress' && <ProgressView conversation={active} />}
      {view === 'settings' && (
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
    </>
  )
}
