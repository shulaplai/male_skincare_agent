import { useState } from 'react'
import { Lightbox } from './ui/Lightbox'
import { Icon } from './Icon'

interface Props {
  src: string
  alt?: string
  /** `bubble` = 對話入面嘅相；`thumb` = composer 未送出嘅預覽 */
  variant?: 'bubble' | 'thumb'
  /** 相載入完 thread 會變高 → `Chat` 要重新 pin 到底（見 `pinToBottom`） */
  onLoad?: () => void
}

/**
 * 相片一律**先模糊**，要撳「顯示」才睇得到。
 *
 * 理由係肩窺（shoulder surfing）：皮膚相係自拍，一上載就自動全清喺 chat 入面顯示
 * 等於行過嘅人一眼睇晒。所以每次 render 都由模糊狀態開始，唔會記住「呢張睇過」
 * （reload 之後亦一樣）。呢個係 UI 層嘅保護，唔關 privacy consent 事 —— consent 係
 * 「相可唔可以送去雲端分析」，呢個係「相喺螢幕度畀邊個睇到」。
 *
 * 唔用 `<img>` 嘅 `filter` 做「遮住」就算：`alt` 文字都要跟住狀態改，否則 screen
 * reader 會讀出未顯示嘅相。
 */
export function BlurPhoto({ src, alt = '皮膚相', variant = 'bubble', onLoad }: Props) {
  const [shown, setShown] = useState(false)
  const [zoom, setZoom] = useState(false)
  return (
    <span className={`photo ${variant} ${shown ? 'shown' : 'blurred'}`}>
      {shown ? (
        <button className="photo-open" onClick={() => setZoom(true)} aria-label="全螢幕睇相">
          <img src={src} alt={alt} onLoad={onLoad} />
        </button>
      ) : (
        <img src={src} alt="已模糊嘅皮膚相（撳「顯示」睇）" onLoad={onLoad} />
      )}
      <Lightbox src={src} alt={alt} open={zoom} onClose={() => setZoom(false)} />
      {!shown && (
        <button
          type="button"
          className="reveal"
          aria-label="顯示相片"
          onClick={(e) => {
            e.stopPropagation()
            setShown(true)
          }}
        >
          <Icon name="eye" size={15} /> 顯示
        </button>
      )}
    </span>
  )
}
