import type { Summary } from './types'

export interface ApiConversation {
  id: string
  body_part: string
  icon: string
}

export interface ConsultResult {
  analysis: {
    summary: string
    metrics: { key: string; value: string; dir: 'good' | 'bad' }[]
    tool_calls: string[]
  }
  tool_results: { tool: string; result: unknown }[]
  advice: { items: string[]; disclaimer: string; escalate: boolean }
  escalate: boolean
}

export interface Settings {
  llm_provider: string
  model: string
  has_api_key: boolean
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
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

export async function getSummary(conversationId: string): Promise<Summary> {
  return parse(await fetch(`/api/conversations/${conversationId}/summary`))
}

export async function getSettings(): Promise<Settings> {
  return parse(await fetch('/api/settings'))
}
