import { useState } from 'react'
import { Lightbox } from './ui/Lightbox'
import { Icon } from './Icon'

interface Props {
  src: string
  alt?: string
  /**
   * `bubble` = 對話入面嘅相；`thumb` = composer 未送出嘅預覽；
   * `grid` = 記錄／日記／今日嗰啲方形縮圖格（尺寸由外層 CSS 決定）。
   */
  variant?: 'bubble' | 'thumb' | 'grid'
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
 * ⚠️ **每一個 render 皮膚相嘅地方都要經呢個 component。** 2026-10-01 加咗 `grid`
 * variant 之前，`RecordsView`／`MobileHome`／`JournalHome` 三個地方係直接寫
 * `<img src="/api/photos/…">`，即係「今日」tab（手機一開就見到）同「記錄」tab 全部
 * 皮膚相都係**全清**出街；`JournalHome` 仲要包住 `<a href="/api/photos/…">`，
 * 撳一下就喺新 tab 開**原圖**，繞過 Lightbox。實測 3 個 scene 共 42 張相、
 * `getComputedStyle(img).filter === 'none'`、0 張有 `.photo` wrapper。
 * 加新 UI 要出相之前，問一句：「呢張相有冇經 BlurPhoto？」
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
