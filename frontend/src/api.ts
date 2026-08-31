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

export async function consult(conversationId: string, text: string): Promise<ConsultResult> {
  return parse(
    await fetch('/api/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, text }),
    }),
  )
}
