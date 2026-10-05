import { useCallback, useEffect, useMemo, useState } from 'react'
import type { MouseEvent } from 'react'
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

/**
 * 畀 `<a href>` 用嘅 scene URL —— 同 `go()` 寫入嗰個**完全一樣**（保留 `?layout=` 等
 * 其他參數，default scene 唔寫參數）。
 *
 * 點解要真 `href`：桌面 Sidebar 同 `ShellTop` 嘅 scene 導覽以前係 `<a>` **冇 href**
 * 加 `onClick`。冇 href 嘅 `<a>` 唔入 tab order、唔會被讀成 link —— 實測 Tab 40 次
 * 完全去唔到「教練對話／皮膚記錄／進度追蹤／護膚指南／設定」，即係純鍵盤用戶
 * **入唔到設定同記錄**（axe 都唔會報，因為冇規則要求 `<a onClick>` 要 focusable）。
 * 有咗 href 仲順便拎到 Cmd／中鍵開新 tab 同「複製連結」。
 */
export function sceneHref(scene: ShellScene, fallback: ShellScene): string {
  if (typeof window === 'undefined') return `?${PARAM}=${scene}`
  const url = new URL(window.location.href)
  if (scene === fallback) url.searchParams.delete(PARAM)
  else url.searchParams.set(PARAM, scene)
  return `${url.pathname}${url.search}`
}

/**
 * `<a href>` + `onClick` 共用嘅 handler：普通左鍵交返俾 SPA（`preventDefault` + `go()`），
 * 帶修飾鍵／中鍵就唔插手，等瀏覽器自己開新 tab／新窗。
 */
export function linkClick(
  scene: ShellScene,
  go: (s: ShellScene) => void,
): (e: MouseEvent<HTMLAnchorElement>) => void {
  return (e) => {
    if (e.defaultPrevented) return
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
    e.preventDefault()
    go(scene)
  }
}
