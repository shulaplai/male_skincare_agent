import { useEffect } from 'react'
import { Icon } from '../Icon'

interface Props {
  src: string
  alt?: string
  open: boolean
  onClose: () => void
}

/**
 * 全螢幕睇相（Phase 3）。
 *
 * 以前撳「顯示」只係原地解除模糊：132px 闊嘅相永遠睇唔清細節（例如「下巴嗰粒」係咩樣）。
 * 呢度係標準做法：黑色底、contain、撳背景／Escape／關閉掣都可以走。
 * 唔做 pinch-zoom（瀏覽器本身有 page zoom，自己做手勢會搶咗佢）。
 */
export function Lightbox({ src, alt = '皮膚相', open, onClose }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="皮膚相（全螢幕）">
      <button className="lightbox-backdrop" aria-label="關閉" onClick={onClose} />
      <img src={src} alt={alt} />
      <button className="lightbox-close" onClick={onClose}>
        <Icon name="x" size={18} /> 關閉
      </button>
    </div>
  )
}
