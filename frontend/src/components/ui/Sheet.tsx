import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { Icon } from '../Icon'

interface Props {
  open: boolean
  title: string
  /** 一句解釋（例如刪除會失去咩）。 */
  body?: ReactNode
  children?: ReactNode
  confirmLabel: string
  /** `danger` 會用紅色（刪除類）。 */
  tone?: 'normal' | 'danger'
  onConfirm: () => void
  onClose: () => void
}

/**
 * 底部彈出 sheet（Phase 2a）。
 *
 * 為咩要有：以前用 `window.prompt()` / `window.alert()`：
 *  - iOS 連續彈幾個 prompt 會被 **封鎖**（後面嗰啲靜靜唔出）；
 *  - IG／FB 等 in-app browser 直情 disable `prompt()`；
 *  - 樣衰、阻塞、冇得跟主題，亦冇得 undo。
 *
 * 實作重點：`role="dialog" aria-modal`、Escape 關、開嘅時候 focus 落第一個輸入／主要掣、
 * 關嘅時候 focus 返之前嗰個元素（唔做嘅話鍵盤／screen reader 用戶會迷失位置）。
 * 動效 200ms，跟 `prefers-reduced-motion`（tokens.css 有全域 rule）。
 */
export function Sheet({
  open,
  title,
  body,
  children,
  confirmLabel,
  tone = 'normal',
  onConfirm,
  onClose,
}: Props) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const lastFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    lastFocus.current = document.activeElement as HTMLElement | null
    const el = sheetRef.current?.querySelector<HTMLElement>('input, textarea, .btn')
    el?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      /* Focus trap：冇呢段，Tab 會行到 `.scrim` 後面被蓋住嘅頁面控制項 —— 用戶睇住
         sheet 但 focus 已經走咗去後面（讀屏尤其迷失）。`aria-modal="true"` 只係聲明，
         瀏覽器唔會自動幫你 trap。 */
      const nodes = sheetRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]',
      )
      if (!nodes || nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const here = document.activeElement
      if (e.shiftKey && (here === first || !sheetRef.current?.contains(here))) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (here === last || !sheetRef.current?.contains(here))) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      lastFocus.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="scrim">
      {/* 背景撳落去 = 關閉。用**真按鈕**而唔係 `<div onClick>`：後者係 a11y 反模式
          （jsx-a11y/no-noninteractive-element-interactions 就係噉樣捉），
          而真按鈕有 accessible name、鍵盤 focus 得到、screen reader 讀得到。 */}
      <button className="scrim-backdrop" aria-label="取消並關閉" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} ref={sheetRef}>
        <span className="grab" aria-hidden />
        <h3>{title}</h3>
        {body && <div className="sheet-body">{body}</div>}
        {children}
        <button className={`btn wide ${tone === 'danger' ? 'danger solid' : 'primary'}`} onClick={onConfirm}>
          {tone === 'danger' && <Icon name="trash-2" size={17} />}
          {confirmLabel}
        </button>
        <button className="btn wide" onClick={onClose}>
          取消
        </button>
      </div>
    </div>
  )
}
