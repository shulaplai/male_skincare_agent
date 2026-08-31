export type Theme = 'light' | 'dark'

export type View = 'chat' | 'records' | 'progress' | 'settings'

export interface Conversation {
  id: string
  bodyPart: string
  icon: string
  days: number
  isDefault?: boolean
}

export interface Metric {
  key: string
  value: string
  dir: 'good' | 'bad'
  note?: string
}

export interface Message {
  id: string
  role: 'user' | 'coach'
  text: string
  time: string
  photo?: string
  analysis?: {
    title: string
    metrics: Metric[]
    advice: string[]
  }
  disclaimer?: string
  escalate?: boolean
}

export interface MemoryItem {
  kind: 'derived' | 'pref' | 'fact'
  text: string
  confidence?: number
}

export interface TimelineEvent {
  date: string
  text: string
}

export interface SkinScore {
  value: number
  delta: string
  series: number[]
  metrics: { key: string; value: string; dir: 'good' | 'bad' }[]
}

export interface RecordEntry {
  id: string
  date: string
  note: string
  metrics: Metric[]
  photos: string[]
}

export interface Summary {
  entries: RecordEntry[]
  insights: MemoryItem[]
  timeline: TimelineEvent[]
}
