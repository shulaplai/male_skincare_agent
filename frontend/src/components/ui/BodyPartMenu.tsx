import { useEffect, useRef, useState } from 'react'
import type { Conversation } from '../../types'

interface Props {
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  /** 加落 `.dropdown` 容器（`chathead` 入面嘅版本要唔同排版時用） */
  className?: string
}

/**
 * 「切換部位 ▾」下拉。桌面 `Chat` 同 `ShellTop` 之前各寫一份，兩份都係
 * `<span onClick>` + `<div onClick>` —— 即係：
 * - 撳唔到（唔係 button、唔入 tab order、冇鍵盤 handler）→ 純鍵盤／開關控制用戶
 *   **轉唔到部位**，而轉部位係呢個 app 最主要嘅導覽；
 * - 讀屏唔知佢係「展開／收起」狀態（冇 `aria-expanded`）；
 * - 打開之後 Esc 關唔到、撳外面關唔到。
 *
 * 呢度一份實作兩邊共用。改用**真 button**，唔用 `role="listbox"`／`role="option"`：
 * ARIA listbox 要配 roving tabindex + 方向鍵，做半套比唔做更差（`MobileShell` 個
 * `role="tablist"` 就係同一類問題）；一班普通 `<button>` 已經完全可用。
 */
export function BodyPartMenu({ conversations, activeId, onSelect, className }: Props) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onDown = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [open])

  return (
    <div className={`dropdown${className ? ` ${className}` : ''}`} ref={root}>
      <button
        type="button"
        className="switch"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        切換部位 ▾
      </button>
      {open && (
        <div className="dropdown-menu">
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`dropdown-item${c.id === activeId ? ' active' : ''}`}
              aria-current={c.id === activeId ? 'true' : undefined}
              onClick={() => {
                onSelect(c.id)
                setOpen(false)
              }}
            >
              {c.icon} {c.bodyPart}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
