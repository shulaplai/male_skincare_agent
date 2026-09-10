import { useState } from 'react'
import type { ComponentType } from 'react'
import { Chat } from '../components/Chat'
import { ProgressView } from '../components/ProgressView'
import { RecordsView } from '../components/RecordsView'
import { RightPanel } from '../components/RightPanel'
import { SettingsView } from '../components/SettingsView'
import { Sidebar } from '../components/Sidebar'
import type { View } from '../types'
import type { HomeProps, SceneTab, ShellNav, ShellProps, ShellScene } from './defs'
import { ShellTop } from './ShellTop'

interface Props {
  p: ShellProps
  tabs: SceneTab[]
  /** home scene 嘅 component（journal/dash 各自一個；一定要用 element 渲染，唔可以直接 call） */
  home: ComponentType<HomeProps>
}

/**
 * 非 chat 結構共用嘅 shell（journal／dash 只差 tabs + home）。
 * 排法：左欄部位（compact sidebar）→ 頂部 bar（部位／狀態／雲／主題 + scene tabs）→ scene 區。
 * scene 區一律重用返現成 view（Chat+RightPanel／RecordsView／ProgressView／SettingsView）→ feature parity。
 */
export function StandardShell({ p, tabs, home: Home }: Props) {
  const [scene, setScene] = useState<ShellScene>('home')
  const active = p.active
  if (!active) return null
  const nav: ShellNav = { go: setScene }

  return (
    <>
      <Sidebar
        compact
        conversations={p.conversations}
        activeId={active.id}
        view={(scene === 'home' ? tabs[0].key : scene) as View}
        online={p.online}
        onSelect={p.onSelectConversation}
        onAdd={p.onAddConversation}
        onNavigate={() => {}}
        onRename={p.onRenameConversation}
        onDelete={p.onDeleteConversation}
      />
      <div className="shell-main">
        <ShellTop
          bodyLabel={`${active.bodyPart} · ${tabs[0].label}`}
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
          {scene === 'home' && <Home p={p} nav={nav} />}
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
