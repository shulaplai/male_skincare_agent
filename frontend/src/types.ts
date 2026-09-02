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
  id?: string
  kind: 'derived' | 'preference' | 'fact'
  text: string
  confidence?: number
  direction?: string
  tag?: string
  scope?: 'global' | 'body_part'
}

export interface TimelineEvent {
  date: string
  text: string
  source?: 'user' | 'agent'
  scope?: 'global' | 'body_part'
}

export interface RecordEntry {
  id: string
  date: string
  note: string
  metrics: Metric[]
  attributes: SkinAttribute[]
  photos: string[]
  products?: string[]
}

export interface AnchorInfo {
  date: string
  old: number
  delta: number
}

export interface AttributeAnchor {
  key: AttributeKey
  label: string
  severity: number
  prev: AnchorInfo | null
  month: AnchorInfo | null
  quarter: AnchorInfo | null
}

export interface CorrelationCandidate {
  cause_type: 'diet' | 'product'
  cause_key: string
  cause_label: string
  attribute: string
  attribute_label: string
  direction: 'up' | 'down'
  occurrences: number
  avg_delta: number
  first_date: string
  last_date: string
  strong: boolean
  note: string
}

export interface CorrelationResult {
  candidates: CorrelationCandidate[]
  lines: string[]
  entry_days: number
  cause_episodes: number
  note: string
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
  anchors: AttributeAnchor[]
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
