import type { ComponentType } from 'react'
import { ChatShell } from './ChatShell'
import { DashHome } from './DashHome'
import { JournalHome } from './JournalHome'
import { StandardShell } from './StandardShell'
import { layoutById, type HomeProps, type LayoutId, type ShellProps } from './defs'

/**
 * Renderer registry：`LayoutId` → 邊個 shell component 渲染。
 * metadata（名／描述／tabs）喺 `defs.ts`；呢度淨係 mapping，兩邊唔好混。
 * 加第 4 套結構 = defs.ts 加一個 LayoutDef + 呢度加一行（+ 自己嘅 home component）。
 */
const HOMES: Record<'journal' | 'dash', ComponentType<HomeProps>> = {
  journal: JournalHome,
  dash: DashHome,
}

export function Shell({ layout, p }: { layout: LayoutId; p: ShellProps }) {
  if (layout === 'chat') return <ChatShell {...p} />
  const def = layoutById(layout)
  if (!def.tabs) return null // registry 漏咗 tabs = config error（非 chat 結構一定要有）
  return <StandardShell p={p} tabs={def.tabs} home={HOMES[layout as 'journal' | 'dash']} />
}
