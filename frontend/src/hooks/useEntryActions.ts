import * as api from '../api'
import { useConfirm } from '../components/ui/Confirm'
import { useToast } from '../components/ui/Toast'
import type { RecordEntry } from '../types'

export interface EntryActions {
  /** 改當日筆記（confirm 由 UI 決定，儲存後 reload） */
  saveNote: (entry: RecordEntry, note: string) => void
  /** 刪成日紀錄（連相＋同日 conv timeline events；會先 confirm） */
  removeEntry: (entry: RecordEntry) => Promise<void>
  /** 刪單張相（path 帶 id；會先 confirm） */
  removePhoto: (entry: RecordEntry, photoPath: string) => Promise<void>
}

/**
 * Entry 修正動作嘅單一 source（journal／records 兩個 view 共用）。
 * 失敗一律 toast（唔再 window.alert），成功交返 reload 俾 caller。
 */
export function useEntryActions(cid: string, reload: () => void): EntryActions {
  const confirm = useConfirm()
  const toast = useToast().toast
  const saveNote = (entry: RecordEntry, note: string) => {
    api
      .editEntryNote(cid, entry.id, note)
      .then(reload)
      .catch((e: Error) => toast(`儲存失敗：${api.readableError(e)}`, { tone: 'err' }))
  }

  const removeEntry = async (entry: RecordEntry) => {
    const ok = await confirm({
      title: `刪除 ${entry.date} 嘅紀錄？`,
      body: '會移除當日嘅相、指標、筆記，同埋嗰日嘅時間線事件。冇得復原。',
      confirmLabel: '刪除紀錄',
      tone: 'danger',
    })
    if (!ok) return
    api
      .deleteEntry(cid, entry.id)
      .then(reload)
      .catch((e: Error) => toast(`刪除失敗：${api.readableError(e)}`, { tone: 'err' }))
  }

  const removePhoto = async (entry: RecordEntry, photoPath: string) => {
    const ok = await confirm({
      title: `刪除 ${entry.date} 呢張相？`,
      body: '檔案會由你部機永久刪除，冇得復原。',
      confirmLabel: '刪除相片',
      tone: 'danger',
    })
    if (!ok) return
    const photoId = photoPath.split('/').pop()?.replace('.jpg', '') ?? ''
    // Photo row 係按 path（photos/<id>.jpg）搵，唔係 Photo.id。
    api
      .deleteEntryPhoto(entry.id, photoId)
      .then(reload)
      .catch((e: Error) => toast(`刪相失敗：${api.readableError(e)}`, { tone: 'err' }))
  }

  return { saveNote, removeEntry, removePhoto }
}
