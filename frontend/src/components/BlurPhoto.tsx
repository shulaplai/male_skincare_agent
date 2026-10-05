import { useState } from 'react'
import { Lightbox } from './ui/Lightbox'
import { Icon } from './Icon'

interface Props {
  src: string
  /**
   * 出縮圖嘅闊度（後端 `GET /api/photos/{id}?w=`，只認 `photo.THUMB_WIDTHS`）。
   *
   * ⚠️ 一定要係**兩倍** CSS 大細：格仔 96px → 192、日記 148px → 296、氣泡 168px
   * → 336（手機版再各自細一級）。2× 縮圖同原檔喺螢幕上係一樣清，但差幾倍 bytes：
   * 實測真 data 20 張相，原檔合共 **899.7 KB**，`w=192` 全部加埋 **170.3 KB**（18.9%），
   * 而一張 768×1024 / 65 KB 嘅相出 192 只係 **7–9 KB**。以前手機首頁為咗 96×96 嘅格
   * 下載 605.9 KB 就係因為呢度冇縮圖。
   *
   * 只有 Lightbox 全螢幕先要原檔，所以 `src`（原檔）唔會喺 grid 之下被下載。
   */
  thumbWidth?: number
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
export function BlurPhoto({
  src,
  thumbWidth,
  alt = '皮膚相',
  variant = 'bubble',
  onLoad,
}: Props) {
  const [shown, setShown] = useState(false)
  const [zoom, setZoom] = useState(false)
  // 螢幕上睇到嘅永遠係縮圖（2× 已經同原檔一樣清）；原檔留返畀 Lightbox。
  const preview = thumbWidth ? `${src}?w=${thumbWidth}` : src
  // 格仔／日記清單可以長，捲到先載入。對話氣泡唔用 lazy：佢係用戶啱啱send嘅，
  // 遲半秒先出會有「係唔係冇上載到」嘅錯覺。
  const loading = variant === 'grid' ? 'lazy' : undefined
  return (
    <span className={`photo ${variant} ${shown ? 'shown' : 'blurred'}`}>
      {shown ? (
        <button className="photo-open" onClick={() => setZoom(true)} aria-label="全螢幕睇相">
          <img src={preview} alt={alt} onLoad={onLoad} loading={loading} decoding="async" />
        </button>
      ) : (
        <img
          src={preview}
          alt="已模糊嘅皮膚相（撳「顯示」睇）"
          onLoad={onLoad}
          loading={loading}
          decoding="async"
        />
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
