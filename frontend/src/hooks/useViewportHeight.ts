import { useEffect } from 'react'

/**
 * iOS 鍵盤感知（Phase 3）。
 *
 * 問題：`.app` 用 `height: 100%`（我哋刻意唔用 `100dvh`，因為 dvh 會令底部出現空位）。
 * 但 iOS Safari 彈鍵盤嗰陣，**layout viewport 唔會縮**，只有 `visualViewport` 縮 ——
 * 所以 composer 會被鍵盤遮住（要用手推上去先睇得到）。
 *
 * 做法：監聽 `visualViewport`，將「實際可見高度」寫入 `--vvh`，CSS 用
 * `height: var(--vvh, 100%)`。有 JS 就用真實高度，冇（舊 browser／SSR）就 fallback 100%。
 */
export function useViewportHeight() {
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const apply = () => {
      document.documentElement.style.setProperty('--vvh', `${Math.round(vv.height)}px`)
    }
    apply()
    vv.addEventListener('resize', apply)
    vv.addEventListener('scroll', apply)
    return () => {
      vv.removeEventListener('resize', apply)
      vv.removeEventListener('scroll', apply)
      document.documentElement.style.removeProperty('--vvh')
    }
  }, [])
}
