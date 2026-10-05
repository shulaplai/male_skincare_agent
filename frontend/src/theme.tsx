import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Theme } from './types'

interface ThemeValue {
  theme: Theme
  toggle: () => void
}

const ThemeContext = createContext<ThemeValue>({ theme: 'light', toggle: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('skc-theme')
      if (saved === 'dark' || saved === 'light') return saved
    }
    return 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    /* `theme-color` 要跟手改：iOS standalone（加到主畫面）同 Android Chrome 都用佢做
       狀態欄／工具列底色，唔改就會「日間模式但狀態欄係深色」。`index.html` 有兩個帶
       `media` 嘅 tag + 一段 inline script 處理首次載入，呢度處理之後每次切換。 */
    for (const m of document.querySelectorAll('meta[name="theme-color"]')) {
      m.setAttribute('content', theme === 'dark' ? '#1c1419' : '#faf3f0')
    }
    try {
      localStorage.setItem('skc-theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, toggle: () => setTheme((t) => (t === 'light' ? 'dark' : 'light')) }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
