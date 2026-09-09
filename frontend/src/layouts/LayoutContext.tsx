import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { LayoutId } from '../types'

interface LayoutValue {
  layout: LayoutId
  setLayout: (l: LayoutId) => void
}

const LayoutContext = createContext<LayoutValue>({ layout: 'chat', setLayout: () => {} })

const isLayoutId = (v: string | null): v is LayoutId => v === 'chat' || v === 'journal' || v === 'dash'

/** URL ?layout=chat|journal|dash = 今次 load 嘅 preview override（唔會覆寫你揀咗嗰套）。 */
function urlPreview(): LayoutId | null {
  if (typeof window === 'undefined') return null
  const v = new URLSearchParams(window.location.search).get('layout')
  return isLayoutId(v) ? v : null
}

/** 三套結構揀邊套：localStorage（skc-layout），同 theme 同一個 pattern，唔使 DB。 */
export function LayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<LayoutId>(() => {
    const preview = urlPreview()
    if (preview) return preview
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('skc-layout')
      if (isLayoutId(saved)) return saved
    }
    return 'chat'
  })

  useEffect(() => {
    if (urlPreview()) return // preview link：唔寫入偏好
    try {
      localStorage.setItem('skc-layout', layout)
    } catch {
      /* ignore */
    }
  }, [layout])

  return <LayoutContext.Provider value={{ layout, setLayout }}>{children}</LayoutContext.Provider>
}

export const useLayout = () => useContext(LayoutContext)
