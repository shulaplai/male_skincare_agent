import * as api from '../api'
import { useConfirm } from '../components/ui/Confirm'
import { useToast } from '../components/ui/Toast'
import type { MemoryItem } from '../types'

export interface InsightActions {
  /** 刪一條記憶（correction；會先出 confirm sheet） */
  removeInsight: (insight: MemoryItem) => Promise<void>
}

/** Memory correction（刪 insight）嘅單一 source。失敗一律 toast。 */
export function useInsightActions(cid: string, reload: () => void): InsightActions {
  const confirm = useConfirm()
  const toast = useToast().toast

  const removeInsight = async (insight: MemoryItem) => {
    if (!insight.id) return
    const ok = await confirm({
      title: '刪除呢條記憶？',
      body: `「${insight.text}」`,
      confirmLabel: '刪除記憶',
      tone: 'danger',
    })
    if (!ok) return
    api
      .deleteInsight(cid, insight.id)
      .then(reload)
      .catch((e: Error) => toast(`刪除失敗：${api.readableError(e)}`, { tone: 'err' }))
  }

  return { removeInsight }
}
