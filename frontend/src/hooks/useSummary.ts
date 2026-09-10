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

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getSummary(cid)
      .then(setSummary)
      .catch((e: Error) => {
        setSummary(null)
        setError(e.message || '載入失敗')
      })
      .finally(() => setLoading(false))
  }, [cid])

  useEffect(reload, [reload, refreshKey])

  return { summary, loading, error, reload }
}
