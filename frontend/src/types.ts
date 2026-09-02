export type Theme = 'light' | 'dark'

export type View = 'chat' | 'records' | 'progress' | 'settings'

export type AttributeKey = 'acne' | 'oiliness' | 'redness' | 'dryness' | 'pores' | 'texture'

export interface Conversation {
  id: string
  bodyPart: string
  icon: string
  cloudAnalysis: boolean
  isDefault?: boolean
}

export interface Metric {
  key: string
  value: string
  dir: 'good' | 'bad' | 'neutral'
  note?: string
}

export interface SkinAttribute {
  key: AttributeKey
  severity: number // 0..3
  note?: string
}

export interface Analysis {
  title: string
  metrics: Metric[]
  advice: string[]
}

export interface DetectedEvent {
  type: 'diet' | 'product_start' | 'product_stop'
  text: string
  tags?: string[]
  product_name?: string
}

export interface Message {
  id: string
  role: 'user' | 'coach'
  text: string
  time: string // HH:MM display
  date: string // YYYY-MM-DD (for day separators)
  photo?: string
  analysis?: Analysis
  disclaimer?: string
  escalate?: boolean
  vision_used?: boolean
  events?: DetectedEvent[]
  pending?: boolean
  error?: boolean
}

export interface MemoryItem {
  kind: 'derived' | 'preference' | 'fact'
  text: string
  confidence?: number
  direction?: string
  tag?: string
}

export interface TimelineEvent {
  date: string
  text: string
  source?: 'user' | 'agent'
}

export interface RecordEntry {
  id: string
  date: string
  note: string
  metrics: Metric[]
  attributes: SkinAttribute[]
  photos: string[]
}

export interface Summary {
  conversation: {
    id: string
    body_part: string
    icon: string
    cloud_analysis: boolean
  }
  entries: RecordEntry[]
  insights: MemoryItem[]
  timeline: TimelineEvent[]
}

export interface ServerMessage {
  id: number
  role: 'user' | 'coach'
  text: string
  payload: {
    photos?: string[]
    summary?: string
    reply?: string
    metrics?: Metric[]
    attributes?: SkinAttribute[]
    advice?: string[]
    disclaimer?: string
    escalate?: boolean
    vision_used?: boolean
  }
  created_at: string
}
