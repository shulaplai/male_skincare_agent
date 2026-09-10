import * as api from '../api'
import type { RecordEntry } from '../types'

export interface EntryActions {
  /** 改當日筆記（confirm 由 UI 決定，儲存後 reload） */
  saveNote: (entry: RecordEntry, note: string) => void
  /** 刪成日紀錄（連相＋同日 conv timeline events；會先 confirm） */
  removeEntry: (entry: RecordEntry) => void
  /** 刪單張相（path 帶 id；會先 confirm） */
  removePhoto: (entry: RecordEntry, photoPath: string) => void
}

/**
 * Entry 修正動作嘅單一 source（journal／records 兩個 view 共用）。
 * 失敗一律 window.alert（同現有 UI 一致），成功交返 reload 俾 caller。
 */
export function useEntryActions(cid: string, reload: () => void): EntryActions {
  const saveNote = (entry: RecordEntry, note: string) => {
    api
      .editEntryNote(cid, entry.id, note)
      .then(reload)
      .catch((e: Error) => window.alert(`儲存失敗：${e.message}`))
  }

  const removeEntry = (entry: RecordEntry) => {
    if (!window.confirm(`刪除 ${entry.date} 嘅紀錄（相／指標／筆記）？時間線同日事件都會移除。冇得復原。`)) return
    api
      .deleteEntry(cid, entry.id)
      .then(reload)
      .catch((e: Error) => window.alert(`刪除失敗：${e.message}`))
  }

  const removePhoto = (entry: RecordEntry, photoPath: string) => {
    if (!window.confirm(`刪除 ${entry.date} 呢張相？冇得復原。`)) return
    const photoId = photoPath.split('/').pop()?.replace('.jpg', '') ?? ''
    // Photo row 係按 path（photos/<id>.jpg）搵，唔係 Photo.id。
    api
      .deleteEntryPhoto(entry.id, photoId)
      .then(reload)
      .catch((e: Error) => window.alert(`刪相失敗：${e.message}`))
  }

  return { saveNote, removeEntry, removePhoto }
}
