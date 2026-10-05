import type { IconName } from '../components/Icon'
import type { Conversation, DetectedEvent, LayoutId, Message, View } from '../types'

/** 所有 shell 共用嘅 props（由 App 一次過供俾四套結構）。 */
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
  onSend: (text: string, photos: { id: string; path: string }[]) => void
  onConfirmEvents: (conversationId: string, msgId: string, events: DetectedEvent[]) => void
  /** 「重試」一則送出失敗嘅訊息（audit §7）：重用原句再送，唔會多出一條。 */
  onRetryMessage: (conversationId: string, msgId: string) => void
}

/** 新結構 shell 內部嘅 scene（home 係各 shell 自己嘅主畫面）。 */
export type ShellScene = 'home' | View

/**
 * 底部 tab bar 嘅 scene。`guide` 故意唔包括：指南係由 Settings 入嘅 sub-page，
 * 唔會佔一個 tab（所以 `NAV_ICONS` 可以係 exhaustive Record，漏咗就編譯唔過）。
 */
export type TabScene = Exclude<ShellScene, 'guide'>

/** `icon` 係 `components/Icon.tsx` 嘅 icon 名（以前係 emoji；見嗰個檔嘅註解）。 */
export interface SceneTab {
  key: TabScene
  label: string
  icon: IconName
}

/**
 * URL 認得嘅**所有** scene，唔止 tab。
 * `guide` 冇 tab（由 Settings 入），但佢一樣係一個 page：如果只認 tab 名，
 * `?scene=guide` reload 就會靜靜跌返第一頁（真實撞過）。
 */
export const SHELL_SCENES: ShellScene[] = ['home', 'chat', 'records', 'progress', 'settings', 'guide']

/**
 * Layout registry：四套「結構」嘅 **metadata／導覽 config**（純 data，唔含 JSX）。
 * - Settings 揀選 UI（`LayoutPicker`）同 App dispatch（`Shells.tsx`）都係食呢個 list
 * - `tabs`：非 chat 結構嘅 scene tabs（chat 結構用 `Sidebar` 嘅 site nav，所以冇 tabs）
 * - 邊個 component 渲染由 `Shells.tsx` 決定（metadata 同 rendering 分家：呢度唔 import React）
 */
export interface LayoutDef {
  id: LayoutId
  name: string
  icon: IconName
  tagline: string
  blurb: string
  tabs?: SceneTab[]
}

/**
 * `mobile` 結構嘅斷點。**呢個係唯一真源** —— `LayoutContext` 用佢砌 `matchMedia`。
 * CSS 冇得 import，所以 `index.css` 尾段嗰個 `@media (max-width: 760px)` 同
 * `.app.layout-mobile` 係人手同步；改呢個數一定要同時改 CSS（見 AGENTS.md 陷阱）。
 * 760 = 原本 `index.css` `@media (max-width: 760px)` 收埋 sidebar 嗰個值，唔另立新標準。
 */
export const MOBILE_MAX_WIDTH = 760

export const LAYOUTS: LayoutDef[] = [
  {
    id: 'chat',
    name: '教練對話',
    icon: 'message-square',
    tagline: '對話主導',
    blurb: '左欄部位＋中間對話＋右欄實時數據。每日問教練、睇相分析、覆事件最順。',
  },
  {
    id: 'journal',
    name: '皮膚日記',
    icon: 'notebook-text',
    tagline: '日記主導',
    blurb: '中間係逐日紀錄 feed（相＋指標＋當日回覆），右欄記憶／時間線。記錄為本、回顧友好。',
    tabs: [
      { key: 'home', label: '皮膚日記', icon: 'notebook-text' },
      { key: 'chat', label: '教練對話', icon: 'message-square' },
      { key: 'records', label: '完整記錄', icon: 'clipboard-list' },
      { key: 'progress', label: '進度', icon: 'chart-column' },
      { key: 'settings', label: '設定', icon: 'settings' },
    ],
  },
  {
    id: 'dash',
    name: '進度儀表板',
    icon: 'chart-column',
    tagline: '數據主導',
    blurb: '一眼睇晒今日狀態、趨勢、相關性同記憶。快睇「有冇變好」，操作收喺頂部。',
    tabs: [
      { key: 'home', label: '進度儀表板', icon: 'chart-column' },
      { key: 'chat', label: '教練對話', icon: 'message-square' },
      { key: 'records', label: '完整記錄', icon: 'clipboard-list' },
      { key: 'progress', label: '進度', icon: 'chart-column' },
      { key: 'settings', label: '設定', icon: 'settings' },
    ],
  },
  {
    /** ⚠️ 一定排最後：`layoutById` fallback 係 `LAYOUTS[0]`，唔可以搶咗 `chat` 嘅 fallback。 */
    id: 'mobile',
    name: '手機版',
    icon: 'smartphone',
    tagline: '手機主導 · 窄屏自動',
    blurb:
      '窄屏專用：頂部部位／狀態，底部 5 個 tab，單欄全屏。窄屏會自動用呢套，闊屏揀咗就當手機框 preview。',
    tabs: [
      { key: 'home', label: '今日', icon: 'house' },
      { key: 'chat', label: '對話', icon: 'message-square' },
      { key: 'records', label: '記錄', icon: 'clipboard-list' },
      { key: 'progress', label: '進度', icon: 'chart-column' },
      { key: 'settings', label: '設定', icon: 'settings' },
    ],
  },
]

export const layoutById = (id: LayoutId): LayoutDef => LAYOUTS.find((l) => l.id === id) ?? LAYOUTS[0]

/** `resolveLayout` 嘅輸入（全部由 `LayoutContext` 供，呢度唔碰 DOM）。 */
export interface LayoutInputs {
  /** `?layout=` 嘅 preview override（唔會寫入偏好） */
  preview: LayoutId | null
  /** 今次 page load 喺 Settings 手動揀過（覆蓋窄屏自動，但唔會持久化窄屏嗰層） */
  pick: LayoutId | null
  /** viewport 係唔係窄屏（`MOBILE_MAX_WIDTH`） */
  narrow: boolean
  /** `localStorage['skc-layout']` 記住嘅偏好 */
  preferred: LayoutId
}

/**
 * 決定實際 render 邊套結構。**純函數**（無 React／DOM 依賴）—— 呢個係窄屏自動切換嘅唯一真源，
 * 亦係將來自動化測試可以直接 import 嘅位置（repo 而家冇 DOM harness，見 status #25）。
 *
 * 優先次序：`?layout=` > 今次手動揀 > 窄屏自動 `mobile` > 儲存嘅偏好。
 *
 * 注意（**CDP 實測過**）：窄屏自動**唔會將 `mobile` 寫入 `localStorage`** —— persist 寫嘅永遠係
 * `preferred`（你喺 Settings 真揀嗰個）。所以：
 * - 手機 reload 一定返 `mobile`，但你嘅偏好唔會被打亂；
 * - 窄屏睇完之後返去闊屏，仍然係你原本揀嗰套（唔會殘留 `mobile`）；
 * - 想喺窄屏固定睇某一套，用 `?layout=`（preview，同樣唔寫入）。
 *   （第一次到訪仍然會寫入 default `'chat'`，同未加手機版之前完全一樣。）
 */
export function resolveLayout({ preview, pick, narrow, preferred }: LayoutInputs): LayoutId {
  return preview ?? pick ?? (narrow ? 'mobile' : preferred)
}

/** 新結構 home／scene 之間嘅唯一導覽介面（唔好再逐個 callback 傳） */
export interface ShellNav {
  go: (scene: ShellScene) => void
}

/** 新結構 home component 嘅統一 props 形狀（p = shell props、nav = scene 導覽） */
export interface HomeProps {
  p: ShellProps
  nav: ShellNav
}
