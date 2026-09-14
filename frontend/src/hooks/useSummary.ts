import { useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import type { Summary } from '../types'

export interface SummaryState {
  summary: Summary | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Conversation summary 嘅單一 fetch pattern（新結構 home 共用）。
 * 切 conversation（cid）或者 App bump refreshKey（send／delete 之後）都會 re-fetch。
 */
export function useSummary(cid: string, refreshKey = 0): SummaryState {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    // Cancellation guard: switching body part (or bumping refreshKey) can leave an
    // older request in flight, and its late response would otherwise overwrite the
    // newer one — rendering body part A's metrics under B's heading. Same pattern
    // as useCorrelations.ts and the inline effect in RightPanel.tsx.
    let alive = true
    setLoading(true)
    setError(null)
    api
      .getSummary(cid)
      .then((s) => {
        if (alive) setSummary(s)
      })
      .catch((e: Error) => {
        if (!alive) return
        setSummary(null)
        setError(e.message || '載入失敗')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [cid, refreshKey, nonce])

  return { summary, loading, error, reload }
}
