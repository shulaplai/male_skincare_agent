import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { LayoutId } from '../types'
import { MOBILE_MAX_WIDTH, resolveLayout } from './defs'

interface LayoutValue {
  layout: LayoutId
  setLayout: (l: LayoutId) => void
}

const LayoutContext = createContext<LayoutValue>({ layout: 'chat', setLayout: () => {} })

const isLayoutId = (v: string | null): v is LayoutId =>
  v === 'chat' || v === 'journal' || v === 'dash' || v === 'mobile'

/** URL ?layout=chat|journal|dash|mobile = 今次 load 嘅 preview override（唔會覆寫你揀咗嗰套）。 */
function urlPreview(): LayoutId | null {
  if (typeof window === 'undefined') return null
  const v = new URLSearchParams(window.location.search).get('layout')
  return isLayoutId(v) ? v : null
}

/**
 * 撳 Settings 揀結構時解除 `?layout=` preview。
 * 唔做呢步嘅話，preview 生效期間個 picker 會**似壞咗**（撳完冇反應，因為 preview 永遠優先）。
 * 用 `replaceState` 而唔係 push：唔想喺瀏覽器歷史加多一格。
 */
function clearPreview(): void {
  if (typeof window === 'undefined') return
  const url = new URL(window.location.href)
  if (!url.searchParams.has('layout')) return
  url.searchParams.delete('layout')
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}

const NARROW_QUERY = `(max-width: ${MOBILE_MAX_WIDTH}px)`

const matchesNarrow = (): boolean =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(NARROW_QUERY).matches
    : false

/** 窄屏偵測（≤ `MOBILE_MAX_WIDTH`）。`matchMedia` 有 listener，rotate／resize 即刻跟。 */
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(matchesNarrow)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia(NARROW_QUERY)
    const sync = () => setNarrow(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])
  return narrow
}

/**
 * 結構揀邊套：localStorage（`skc-layout`）記住偏好，同 theme 同一個 pattern，唔使 DB。
 *
 * 實際 render 邊套由 `defs.resolveLayout`（純函數）決定，優先次序：
 * `?layout=` > 今次手動揀 > 窄屏自動 `mobile` > 儲存嘅偏好。
 *
 * **窄屏自動唔會將 `mobile` 寫入 `localStorage`** —— persist 寫嘅永遠係 `preferred`（用戶真揀嗰個）。
 * 即係手機 reload 一定返 `mobile`，但用戶嘅偏好唔會被打亂（CDP 實測過，見 `defs.resolveLayout` 註釋）。
 */
export function LayoutProvider({ children }: { children: ReactNode }) {
  const [preferred, setPreferred] = useState<LayoutId>(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('skc-layout')
      if (isLayoutId(saved)) return saved
    }
    return 'chat'
  })
  /** 今次 page load 手動揀過嘅（覆蓋窄屏自動；`preferred` 本身已經持久化咗） */
  const [pick, setPick] = useState<LayoutId | null>(null)
  const narrow = useNarrow()

  // 每次 render 重讀：`setLayout` 可能啱啱用 replaceState 清走咗個參數。
  const preview = urlPreview()
  const layout = resolveLayout({ preview, pick, narrow, preferred })

  useEffect(() => {
    if (preview) return // preview link：唔寫入偏好
    try {
      localStorage.setItem('skc-layout', preferred)
    } catch {
      /* ignore */
    }
  }, [preferred, preview])

  const setLayout = useCallback((l: LayoutId) => {
    clearPreview() // 否則 preview 生效期間撳完唔會有反應
    setPreferred(l)
    setPick(l)
  }, [])

  return <LayoutContext.Provider value={{ layout, setLayout }}>{children}</LayoutContext.Provider>
}

export const useLayout = () => useContext(LayoutContext)
