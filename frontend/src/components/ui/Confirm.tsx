import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Sheet } from './Sheet'

export interface Ask {
  title: string
  body?: ReactNode
  confirmLabel: string
  tone?: 'normal' | 'danger'
}

type Confirm = (ask: Ask) => Promise<boolean>

const Ctx = createContext<Confirm>(async () => false)

/** `const ok = await confirm({...})` —— 喺 hook／component 都用得。 */
export const useConfirm = () => useContext(Ctx)

/**
 * 全 app 一個 confirm（Phase 2a）。
 *
 * 為咩唔各自用 `useState`：刪除類確認有 5 個地方（部位／紀錄／相／記憶／事件），
 * 每個都自己寫一次 state + Sheet 就會走樣。呢個 provider 出一個 promise，
 * 令呼叫端寫法同以前 `window.confirm` 一樣直觀：
 *
 *   if (!(await confirm({ title: '刪除？', confirmLabel: '刪除', tone: 'danger' }))) return
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [ask, setAsk] = useState<Ask | null>(null)
  const resolver = useRef<((v: boolean) => void) | null>(null)

  const confirm = useCallback<Confirm>(
    (next) =>
      new Promise<boolean>((resolve) => {
        resolver.current = resolve
        setAsk(next)
      }),
    [],
  )

  const settle = (value: boolean) => {
    resolver.current?.(value)
    resolver.current = null
    setAsk(null)
  }

  return (
    <Ctx.Provider value={confirm}>
      {children}
      <Sheet
        open={ask !== null}
        title={ask?.title ?? ''}
        body={ask?.body}
        confirmLabel={ask?.confirmLabel ?? '確定'}
        tone={ask?.tone}
        onConfirm={() => settle(true)}
        onClose={() => settle(false)}
      />
    </Ctx.Provider>
  )
}
