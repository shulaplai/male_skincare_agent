import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Icon } from '../Icon'

interface Item {
  id: number
  text: string
  tone: 'ok' | 'err'
  action?: { label: string; run: () => void }
}

interface Api {
  /** 成功／失敗都係一句，取代 `window.alert`（唔會阻塞、可以帶「復原」）。 */
  toast: (text: string, opts?: { tone?: 'ok' | 'err'; action?: { label: string; run: () => void } }) => void
}

const Ctx = createContext<Api>({ toast: () => {} })
export const useToast = () => useContext(Ctx)

let seq = 1

/**
 * Toast（Phase 2a）：取代 `window.alert`。
 *
 * `role="status" aria-live="polite"` → screen reader 會讀出嚟，但唔會搶焦點。
 * 4 秒自動消失；有 action（例如「復原」）就唔會自動消失。
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([])

  const toast = useCallback<Api['toast']>((text, opts) => {
    const id = seq++
    setItems((prev) => [...prev, { id, text, tone: opts?.tone ?? 'ok', action: opts?.action }])
    if (!opts?.action) {
      window.setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 4000)
    }
  }, [])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`toast ${i.tone}`}>
            <Icon name={i.tone === 'ok' ? 'check' : 'circle-alert'} size={17} />
            <span>{i.text}</span>
            {i.action && (
              <button
                className="toast-action"
                onClick={() => {
                  i.action?.run()
                  setItems((prev) => prev.filter((x) => x.id !== i.id))
                }}
              >
                {i.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}
