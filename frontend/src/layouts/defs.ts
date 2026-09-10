import type { Conversation, DetectedEvent, LayoutId, Message, View } from '../types'

/** 所有 shell 共用嘅 props（由 App 一次過供俾三套結構）。 */
export interface ShellProps {
  conversations: Conversation[]
  active: Conversation | undefined
  messages: Record<string, Message[]>
  online: boolean
  sending: boolean
  loadingThread: boolean
  refreshKey: number
  onSelectConversation: (id: string) => void
  onAddConversation: () => void
  onRenameConversation: (c: Conversation) => void
  onDeleteConversation: (c: Conversation) => void
  onToggleCloud: (id: string, enabled: boolean) => void
  onSend: (text: string, photos: { id: string; path: string }[]) => void
  onConfirmEvents: (conversationId: string, msgId: string, events: DetectedEvent[]) => void
  onQuickRecord: (conversationId: string, diet: string, product: string) => void
}

/** 新結構 shell 內部嘅 scene（home 係各 shell 自己嘅主畫面）。 */
export type ShellScene = 'home' | View

export interface SceneTab {
  key: ShellScene
  label: string
  icon: string
}

/**
 * Layout registry：三套「結構」嘅 **metadata／導覽 config**（純 data，唔含 JSX）。
 * - Settings 揀選 UI（`LayoutPicker`）同 App dispatch（`Shells.tsx`）都係食呢個 list
 * - `tabs`：非 chat 結構嘅 scene tabs（chat 結構用 `Sidebar` 嘅 site nav，所以冇 tabs）
 * - 邊個 component 渲染由 `Shells.tsx` 決定（metadata 同 rendering 分家：呢度唔 import React）
 */
export interface LayoutDef {
  id: LayoutId
  name: string
  icon: string
  tagline: string
  blurb: string
  tabs?: SceneTab[]
}

export const LAYOUTS: LayoutDef[] = [
  {
    id: 'chat',
    name: '教練對話',
    icon: '💬',
    tagline: '對話主導',
    blurb: '左欄部位＋中間對話＋右欄實時數據。每日問教練、睇相分析、覆事件最順。',
  },
  {
    id: 'journal',
    name: '皮膚日記',
    icon: '📔',
    tagline: '日記主導',
    blurb: '中間係逐日紀錄 feed（相＋指標＋當日回覆），右欄記憶／時間線。記錄為本、回顧友好。',
    tabs: [
      { key: 'home', label: '皮膚日記', icon: '📔' },
      { key: 'chat', label: '教練對話', icon: '💬' },
      { key: 'records', label: '完整記錄', icon: '🗂️' },
      { key: 'progress', label: '進度', icon: '📈' },
      { key: 'settings', label: '設定', icon: '⚙️' },
    ],
  },
  {
    id: 'dash',
    name: '進度儀表板',
    icon: '📊',
    tagline: '數據主導',
    blurb: '一眼睇晒今日狀態、趨勢、相關性同記憶。快睇「有冇變好」，操作收喺頂部。',
    tabs: [
      { key: 'home', label: '進度儀表板', icon: '📊' },
      { key: 'chat', label: '教練對話', icon: '💬' },
      { key: 'records', label: '完整記錄', icon: '🗂️' },
      { key: 'progress', label: '進度', icon: '📈' },
      { key: 'settings', label: '設定', icon: '⚙️' },
    ],
  },
]

export const layoutById = (id: LayoutId): LayoutDef => LAYOUTS.find((l) => l.id === id) ?? LAYOUTS[0]

/** 新結構 home／scene 之間嘅唯一導覽介面（唔好再逐個 callback 傳） */
export interface ShellNav {
  go: (scene: ShellScene) => void
}

/** 新結構 home component 嘅統一 props 形狀（p = shell props、nav = scene 導覽） */
export interface HomeProps {
  p: ShellProps
  nav: ShellNav
}
