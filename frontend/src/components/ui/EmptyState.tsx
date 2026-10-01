import type { ReactNode } from 'react'
import { Icon } from '../Icon'
import type { IconName } from '../Icon'

interface Props {
  icon: IconName
  children: ReactNode
  /** 可選行動掣（例如「去打卡」）——空態唔應該只係一句死路。 */
  action?: ReactNode
  small?: boolean
}

/**
 * 統一空態（Phase 2b）：icon ＋ 一句 ＋ 可選行動掣。
 * 以前淨係一句灰字（`<p className="empty">未有…</p>`），用戶唔知下一步做咩。
 * 純展示元件，唔會放 demo 數（AGENTS.md 約定 #10）。
 */
export function EmptyState({ icon, children, action, small }: Props) {
  return (
    <div className={`empty-state${small ? ' small' : ''}`}>
      <Icon name={icon} size={small ? 20 : 26} />
      <span>{children}</span>
      {action}
    </div>
  )
}
