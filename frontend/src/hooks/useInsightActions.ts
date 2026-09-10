import * as api from '../api'
import type { MemoryItem } from '../types'

export interface InsightActions {
  /** 刪一條記憶（correction；會先 confirm） */
  removeInsight: (insight: MemoryItem) => void
}

/** Memory correction（刪 insight）嘅單一 source。 */
export function useInsightActions(cid: string, reload: () => void): InsightActions {
  const removeInsight = (insight: MemoryItem) => {
    if (!insight.id) return
    if (!window.confirm(`刪除呢條記憶：「${insight.text}」？`)) return
    api
      .deleteInsight(cid, insight.id)
      .then(reload)
      .catch((e: Error) => window.alert(`刪除失敗：${e.message}`))
  }

  return { removeInsight }
}
