import { Icon } from '../components/Icon'
import type { TabScene } from './defs'

/**
 * 底部 navigation 用嘅 icon。**唯一來源係 `components/Icon.tsx`** ——
 * 呢度只負責 scene → icon 名嘅 mapping。
 *
 * 歷史（值得記住）：emoji 唔得（字形來源唔同）；自己手畫 SVG 都唔得（實測 ink 高度
 * 17／17／16.5／14／12 CSS px、視覺中心差 1.25px）。最後改用 Lucide 官方 path 先齊。
 * 加新 scene 一定要喺 `ICONS` 加 mapping（`Record<TabScene, …>` 漏咗就編譯唔過）。
 */
const ICONS: Record<TabScene, 'house' | 'message-square' | 'clipboard-list' | 'chart-column' | 'settings'> = {
  home: 'house',
  chat: 'message-square',
  records: 'clipboard-list',
  progress: 'chart-column',
  settings: 'settings',
}

export function NavIcon({ scene }: { scene: TabScene }) {
  return <Icon name={ICONS[scene]} size={22} />
}
