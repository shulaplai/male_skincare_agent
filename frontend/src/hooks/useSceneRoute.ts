import { useCallback, useEffect, useMemo, useState } from 'react'
import { SHELL_SCENES } from '../layouts/defs'
import type { SceneTab, ShellScene, TabScene } from '../layouts/defs'

const PARAM = 'scene'

/** URL 入面嘅 scene（`?scene=chat`）。唔合法／冇 → `null`（caller 決定 default）。 */
export function readSceneFromUrl(valid: readonly string[]): ShellScene | null {
  if (typeof window === 'undefined') return null
  const raw = new URLSearchParams(window.location.search).get(PARAM)
  return raw && valid.includes(raw) ? (raw as ShellScene) : null
}

/**
 * Page 系統：mobile／journal／dash 嘅 tab 係**真 page**，唔止係 component state。
 *
 * 之前 scene 只係 `useState`，所以撳完 tab 一 reload（或者由其他 app 返嚟）就跌返
 * 第一頁 —— 用戶要再撳一次。而家：
 * - 撳 tab → `pushState`（URL 變成 `?scene=chat`，`?layout=` 等其他參數照留）；
 * - 上一頁／下一頁真係行得（`popstate`）；
 * - reload／bookmark／由 Safari 分頁返嚟都停喺同一頁。
 *
 * `home` 唔寫參數（URL 保持乾淨），係唯一 default。
 */
export function useSceneRoute(tabs: readonly SceneTab[]): [ShellScene, (s: ShellScene) => void] {
  const fallback: TabScene = useMemo(() => tabs[0].key, [tabs])
  const [scene, setScene] = useState<ShellScene>(() => readSceneFromUrl(SHELL_SCENES) ?? fallback)

  useEffect(() => {
    const onPop = () => setScene(readSceneFromUrl(SHELL_SCENES) ?? fallback)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [fallback])

  const go = useCallback(
    (next: ShellScene) => {
      setScene(next)
      const url = new URL(window.location.href)
      if (next === fallback) url.searchParams.delete(PARAM)
      else url.searchParams.set(PARAM, next)
      window.history.pushState({ scene: next }, '', url)
    },
    [fallback],
  )

  return [scene, go]
}
