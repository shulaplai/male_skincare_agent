import { useEffect, useState } from 'react'
import * as api from '../api'
import type { CorrelationResult } from '../types'

export interface CorrelationsState {
  corr: CorrelationResult | null
  loading: boolean
}

/** 相關性偵測結果（`/correlations`）嘅單一 fetch pattern。 */
export function useCorrelations(cid: string, refreshKey = 0): CorrelationsState {
  const [corr, setCorr] = useState<CorrelationResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    api
      .getCorrelations(cid)
      .then((c) => alive && setCorr(c))
      .catch(() => alive && setCorr(null))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [cid, refreshKey])

  return { corr, loading }
}
