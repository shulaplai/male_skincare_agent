import type { JSX } from 'react'

/**
 * 全 app 嘅 icon registry（Phase 1c，2026-10-01）。
 *
 * 為咩要一個檔：以前 UI chrome 用 emoji（☀️💬🗂️📈⚙️👁✍️🍜🧴✋✅⚠️✎🗑⬇🌐📚📖🌙📱📔📊）。
 * emoji 係**五個唔同字型來源**嘅彩色字形：同一個 font-size 之下大細／基線／光學重量都唔一樣
 * （實測底部 nav：ink 高度 17／17／16.5／14／12 CSS px、視覺中心差 1.25px → 睇落「對唔齊」）。
 * SVG 同一個 24×24 grid、同一組 stroke，就一定齊，而且跟 `currentColor` 行主題色。
 *
 * 來源：**Lucide**（ISC，`lucide-static@0.469.0`）官方 path data —— vendor 落嚟，唔加依賴。
 * ⚠️ 加 icon：由 `https://unpkg.com/lucide-static@0.469.0/icons/<name>.svg` 抄 `<svg>` 入面嘅
 *    內容（可以刪 `class`、`width/height`），呢度只存 path 本身。
 * ⚠️ 唔好自己手畫 path：我試過，五個 icon ink 高度差 5px（見上）。
 */
const PATHS: Record<string, JSX.Element> = {
  'arrow-up': <> <path d="m5 12 7-7 7 7"/> <path d="M12 19V5"/> </>,
  'arrow-left': <> <path d="m12 19-7-7 7-7"/> <path d="M19 12H5"/> </>,
  'book-open': <> <path d="M12 7v14"/> <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/> </>,
  'calendar-check': <> <path d="M8 2v4"/> <path d="M16 2v4"/> <rect width="18" height="18" x="3" y="4" rx="2"/> <path d="M3 10h18"/> <path d="m9 16 2 2 4-4"/> </>,
  'camera': <> <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/> <circle cx="12" cy="13" r="3"/> </>,
  'chart-column': <> <path d="M3 3v16a2 2 0 0 0 2 2h16"/> <path d="M18 17V9"/> <path d="M13 17V5"/> <path d="M8 17v-3"/> </>,
  'check': <> <path d="M20 6 9 17l-5-5"/> </>,
  'chevron-down': <> <path d="m6 9 6 6 6-6"/> </>,
  'chevron-right': <> <path d="m9 18 6-6-6-6"/> </>,
  'circle-alert': <> <circle cx="12" cy="12" r="10"/> <line x1="12" x2="12" y1="8" y2="12"/> <line x1="12" x2="12.01" y1="16" y2="16"/> </>,
  'clipboard-list': <> <rect width="8" height="4" x="8" y="2" rx="1" ry="1"/> <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/> <path d="M12 11h4"/> <path d="M12 16h4"/> <path d="M8 11h.01"/> <path d="M8 16h.01"/> </>,
  'download': <> <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/> <polyline points="7 10 12 15 17 10"/> <line x1="12" x2="12" y1="15" y2="3"/> </>,
  'droplet': <> <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/> </>,
  'eye': <> <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/> <circle cx="12" cy="12" r="3"/> </>,
  'globe': <> <circle cx="12" cy="12" r="10"/> <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/> <path d="M2 12h20"/> </>,
  'hand': <> <path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/> <path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/> <path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/> <path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/> </>,
  'house': <> <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/> <path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/> </>,
  'list-ordered': <> <path d="M10 12h11"/> <path d="M10 18h11"/> <path d="M10 6h11"/> <path d="M4 10h2"/> <path d="M4 6h1v4"/> <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/> </>,
  'loader-circle': <> <path d="M21 12a9 9 0 1 1-6.219-8.56"/> </>,
  'message-square': <> <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/> </>,
  'moon': <> <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/> </>,
  'notebook-text': <> <path d="M2 6h4"/> <path d="M2 10h4"/> <path d="M2 14h4"/> <path d="M2 18h4"/> <rect width="16" height="20" x="4" y="2" rx="2"/> <path d="M9.5 8h5"/> <path d="M9.5 12H16"/> <path d="M9.5 16H14"/> </>,
  'pencil': <> <path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/> <path d="m15 5 4 4"/> </>,
  'play': <> <polygon points="6 3 20 12 6 21 6 3"/> </>,
  'plus': <> <path d="M5 12h14"/> <path d="M12 5v14"/> </>,
  'settings': <> <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/> <circle cx="12" cy="12" r="3"/> </>,
  'smartphone': <> <rect width="14" height="20" x="5" y="2" rx="2" ry="2"/> <path d="M12 18h.01"/> </>,
  'sparkles': <> <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/> <path d="M20 3v4"/> <path d="M22 5h-4"/> <path d="M4 17v2"/> <path d="M5 18H3"/> </>,
  'sun': <> <circle cx="12" cy="12" r="4"/> <path d="M12 2v2"/> <path d="M12 20v2"/> <path d="m4.93 4.93 1.41 1.41"/> <path d="m17.66 17.66 1.41 1.41"/> <path d="M2 12h2"/> <path d="M20 12h2"/> <path d="m6.34 17.66-1.41 1.41"/> <path d="m19.07 4.93-1.41 1.41"/> </>,
  'trash-2': <> <path d="M3 6h18"/> <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/> <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/> <line x1="10" x2="10" y1="11" y2="17"/> <line x1="14" x2="14" y1="11" y2="17"/> </>,
  'triangle-alert': <> <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/> <path d="M12 9v4"/> <path d="M12 17h.01"/> </>,
  'user': <> <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/> <circle cx="12" cy="7" r="4"/> </>,
  'utensils': <> <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/> <path d="M7 2v20"/> <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/> </>,
  'x': <> <path d="M18 6 6 18"/> <path d="m6 6 12 12"/> </>,
  'flask-conical': <> <path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/> <path d="M6.453 15h11.094"/> <path d="M8.5 2h7"/> </>,
  'refresh-cw': <> <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/> <path d="M21 3v5h-5"/> <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/> <path d="M8 16H3v5"/> </>,
  'filter': <> <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/> </>,
}

export type IconName = keyof typeof PATHS

/** 執行期檢查用（例如後端傳落嚟嘅 icon 名要驗一驗先 render）。 */
export const ICON_NAMES = Object.keys(PATHS) as IconName[]

interface Props {
  name: IconName
  /** 預設 16px（inline 文字用）；nav 用 22、大掣用 18–20 */
  size?: number
  className?: string
}

/** 所有 UI icon 都經呢度，唔好喺 component 直接寫 `<svg>`。 */
export function Icon({ name, size = 16, className }: Props) {
  return (
    <svg
      className={className ? `ic ${className}` : 'ic'}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
