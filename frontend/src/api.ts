import type {
  CorrelationResult,
  DetectedEvent,
  Guide,
  ServerMessage,
  Summary,
  VideoUpload,
} from './types'

export interface ApiConversation {
  id: string
  body_part: string
  icon: string
  cloud_analysis: boolean
}

export interface ConsultResult {
  analysis: {
    summary: string
    metrics: { key: string; value: string; dir: 'good' | 'bad' | 'neutral' }[]
    attributes: { key: string; severity: number; note?: string }[]
    tool_calls: string[]
  }
  tool_results: { tool: string; result: unknown }[]
  advice: { reply?: string; items: string[]; disclaimer: string; escalate: boolean; detected_events?: DetectedEvent[] }
  escalate: boolean
  vision_used: boolean
}

export interface Settings {
  llm_provider: string
  model: string
  vision_model?: string
  has_api_key: boolean
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* non-json body */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

/**
 * Turn any thrown value into a line that belongs in a Cantonese UI.
 *
 * `fetch` rejects with a bare `TypeError: Failed to fetch` when the backend is down, and
 * that raw English was leaking into the message thread (`出錯：Failed to fetch`). Any
 * error we did not write ourselves is a bug report waiting to happen, not a sentence to
 * show; callers get a generic Chinese line and the raw text stays in the console.
 */
export function readableError(e: unknown): string {
  const isOffline = e instanceof TypeError || (e instanceof Error && /fetch|network/i.test(e.message))
  if (isOffline) return '連唔到後端，檢查 network／backend 起咗未？'
  const msg = e instanceof Error ? e.message : String(e)
  // Our own `parse`/XHR errors are already written for the user (`HTTP 503`, 「上傳失敗」…).
  return /^[A-Za-z]/.test(msg) ? `系統出錯（${msg}）` : msg
}

export async function listConversations(): Promise<ApiConversation[]> {
  return parse(await fetch('/api/conversations'))
}

export async function createConversation(bodyPart: string, icon = '🧴'): Promise<ApiConversation> {
  return parse(
    await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body_part: bodyPart, icon }),
    }),
  )
}

export async function renameConversation(cid: string, bodyPart: string): Promise<ApiConversation> {
  return parse(
    await fetch(`/api/conversations/${cid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body_part: bodyPart }),
    }),
  )
}

export async function deleteConversation(cid: string): Promise<{ status: string }> {
  return parse(
    await fetch(`/api/conversations/${cid}`, { method: 'DELETE' }),
  )
}

export interface ConsentState {
  granted: boolean
  at: string | null
}

/** 一次性相片同意（2026-10-01：全雲端，consent 由 conversation 級升去 user 級）。 */
export async function getConsent(): Promise<ConsentState> {
  return parse(await fetch('/api/consent'))
}

export async function grantConsent(granted = true): Promise<ConsentState> {
  return parse(
    await fetch('/api/consent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ granted }),
    }),
  )
}

export async function consult(
  conversationId: string,
  text: string,
  photoPaths: string[] = [],
  /** 今次係一條片（唔係相）→ 後端叫 model 講「條片」，唔會數字數 */
  video?: { duration: number; frames: number },
): Promise<ConsultResult> {
  return parse(
    await fetch('/api/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        text,
        photo_paths: photoPaths,
        video: video ?? null,
      }),
    }),
  )
}

/** 串流期間後端報嘅每個 node 行完咗（`node` 係 graph 嘅 node 名，`ms` 係佢用咗幾久）。 */
export interface ConsultNodeEvent {
  node: string
  ms?: number
}

/**
 * Same consult as `consult()`, but the reply no longer arrives as one 5.5-second lump
 * (audit §7): the server walks analyze → tools → advise → guardrail → persist and sends
 * one `data:` frame per finished node, then a final `result` frame with exactly the same
 * payload `consult()` returns.
 *
 * `onNode` is called for each node so the UI can name what is happening. If the browser
 * or a proxy gives us no stream body, this falls back to the plain POST rather than
 * failing — a missing nicety must not cost the user their message.
 */
export async function consultStream(
  conversationId: string,
  text: string,
  photoPaths: string[],
  video: { duration: number; frames: number } | undefined,
  onNode: (e: ConsultNodeEvent) => void,
): Promise<ConsultResult> {
  const body = JSON.stringify({
    conversation_id: conversationId,
    text,
    photo_paths: photoPaths,
    video: video ?? null,
  })
  const res = await fetch('/api/consult/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
  if (!res.ok) {
    // Same sentence the non-streaming path would throw (HTTP 404 ／ 422 …).
    let detail = `HTTP ${res.status}`
    try {
      const parsed = await res.json()
      if (typeof parsed?.detail === 'string') detail = parsed.detail
    } catch {
      /* non-json body */
    }
    throw new Error(detail)
  }
  if (!res.body) return consult(conversationId, text, photoPaths, video)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ConsultResult | null = null
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE frames are separated by a blank line; a partial tail stays in `buffer`.
    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = block.split('\n').find((l) => l.startsWith('data:'))
      if (line) {
        const event = JSON.parse(line.slice('data:'.length).trim())
        if (event.type === 'node') onNode({ node: event.node, ms: event.ms })
        else if (event.type === 'result') result = event as ConsultResult & { type: string }
        else if (event.type === 'error') throw new Error(String(event.detail))
      }
      sep = buffer.indexOf('\n\n')
    }
  }
  if (!result) throw new Error('串流中途斷咗（後端冇回最終結果）')
  return result
}

export async function uploadPhoto(file: File): Promise<{ id: string; path: string }> {
  const fd = new FormData()
  fd.append('file', file)
  return parse(
    await fetch('/api/photos', {
      method: 'POST',
      body: fd,
    }),
  )
}

/**
 * Upload a clip and get back the frames sampled from it.
 *
 * The frames are **ordinary photos**: the caller attaches their ids and sends them as
 * `photo_paths` to `/api/consult`, so nothing downstream needs to know it was a video.
 * `compressed` / `original_bytes` / `stored_bytes` are reported so the UI can tell the
 * user what happened to their file rather than silently shrinking it.
 */
/**
 * 上載一條片。用 XHR 而唔用 fetch：`fetch` 冇 upload progress event，而一條 20 秒
 * 手機片可以幾十 MB —— 用戶要見到「上載緊，幾多 %」，唔係呆呆等。
 */
export function uploadVideo(
  conversationId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<VideoUpload> {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/videos?cid=${encodeURIComponent(conversationId)}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100)
        resolve(body as VideoUpload)
      } else {
        const detail = (body as { detail?: string } | null)?.detail
        reject(new Error(detail || `HTTP ${xhr.status}`))
      }
    }
    xhr.onerror = () => reject(new Error('網絡中斷，上傳失敗'))
    xhr.onabort = () => reject(new Error('上傳已取消'))
    xhr.send(fd)
  })
}

export async function getSummary(conversationId: string): Promise<Summary> {
  return parse(await fetch(`/api/conversations/${conversationId}/summary`))
}

export async function getMessages(conversationId: string): Promise<ServerMessage[]> {
  return parse(await fetch(`/api/conversations/${conversationId}/messages`))
}

export async function applyEvents(
  conversationId: string,
  events: DetectedEvent[],
  /** 邊條 chat message 出嘅 chip（`s123` → 123）；session 內新訊息可以唔傳 */
  messageId?: number,
): Promise<{ written: number; events_applied_on: number | null }> {
  return parse(
    await fetch(`/api/conversations/${conversationId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events, message_id: messageId ?? null }),
    }),
  )
}

export async function getSettings(): Promise<Settings> {
  return parse(await fetch('/api/settings'))
}

export async function getCorrelations(conversationId: string): Promise<CorrelationResult> {
  return parse(await fetch(`/api/conversations/${conversationId}/correlations`))
}

export async function editEntryNote(
  cid: string,
  entryId: string,
  note: string,
): Promise<{ id: string; note: string }> {
  return parse(
    await fetch(`/api/conversations/${cid}/entries/${entryId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    }),
  )
}

export async function deleteEntry(cid: string, entryId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/conversations/${cid}/entries/${entryId}`, { method: 'DELETE' }))
}

export async function deleteEntryPhoto(entryId: string, photoId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/entries/${entryId}/photos/${photoId}`, { method: 'DELETE' }))
}

/**
 * Delete a photo the user picked but never sent (issue #23).
 *
 * Picking a photo uploads it to disk immediately, so without this 「撳 ×」 left the file
 * behind forever — no `Photo` row, no UI that could see it. The server refuses (409)
 * for a photo an entry owns: a record's photo is removed from the journal, never here.
 */
export async function deleteUnattachedPhoto(photoId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/photos/${photoId}`, { method: 'DELETE' }))
}

/**
 * Delete a clip the user picked but never sent (issue #27).
 *
 * Uploading a clip immediately writes the file, its `Video` row and every sampled frame,
 * and `sweep_orphan_photos` keeps `Video.frames` on purpose (a clip waiting to be sent
 * must keep them) — so nothing cleaned up after 「撳 ×」 except deleting the conversation.
 */
export async function deleteUnattachedVideo(videoId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/videos/${videoId}`, { method: 'DELETE' }))
}

export async function deleteInsight(cid: string, insightId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/conversations/${cid}/insights/${insightId}`, { method: 'DELETE' }))
}

export async function getGuide(): Promise<Guide> {
  return parse(await fetch('/api/guide'))
}

export async function health(): Promise<{ status: string; llm_provider: string }> {
  return parse(await fetch('/health'))
}
