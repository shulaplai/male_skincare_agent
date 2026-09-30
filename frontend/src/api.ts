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

export async function setCloudAnalysis(cid: string, enabled: boolean): Promise<{ cloud_analysis: boolean }> {
  return parse(
    await fetch(`/api/conversations/${cid}/cloud-analysis`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }),
  )
}

export async function consult(
  conversationId: string,
  text: string,
  photoPaths: string[] = [],
): Promise<ConsultResult> {
  return parse(
    await fetch('/api/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, text, photo_paths: photoPaths }),
    }),
  )
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
export async function uploadVideo(conversationId: string, file: File): Promise<VideoUpload> {
  const fd = new FormData()
  fd.append('file', file)
  return parse(
    await fetch(`/api/videos?cid=${encodeURIComponent(conversationId)}`, {
      method: 'POST',
      body: fd,
    }),
  )
}

export async function getSummary(conversationId: string): Promise<Summary> {
  return parse(await fetch(`/api/conversations/${conversationId}/summary`))
}

export async function getMessages(conversationId: string): Promise<ServerMessage[]> {
  return parse(await fetch(`/api/conversations/${conversationId}/messages`))
}

export async function applyEvents(conversationId: string, events: DetectedEvent[]): Promise<{ written: number }> {
  return parse(
    await fetch(`/api/conversations/${conversationId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
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

export async function deleteInsight(cid: string, insightId: string): Promise<{ status: string }> {
  return parse(await fetch(`/api/conversations/${cid}/insights/${insightId}`, { method: 'DELETE' }))
}

export async function getGuide(): Promise<Guide> {
  return parse(await fetch('/api/guide'))
}

export async function health(): Promise<{ status: string; llm_provider: string }> {
  return parse(await fetch('/health'))
}
