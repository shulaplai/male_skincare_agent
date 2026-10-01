export type Theme = 'light' | 'dark'

export type View = 'chat' | 'records' | 'progress' | 'settings' | 'guide'

/** 四套可揀嘅 UI「結構」（Q: 介面結構）—— 唔同場景主導嘅排法，食同一批 API。 */
export type LayoutId = 'chat' | 'journal' | 'dash' | 'mobile'

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
  /** 用戶今次上傳嘅係一段片（UI 出「🎬 皮膚影片」，唔會顯示抽格出嚟嘅相） */
  clip?: { duration: number }
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
    /** AI 抽取出嚟、等用戶確認嘅自報事件（Q51）——persist 之後 reload 都仲喺度 */
    detected_events?: DetectedEvent[]
    /** 用戶已經撳過「✅ 記低」→ reload 唔應該再出同一個 chip */
    events_applied?: boolean
    /** user message：今次係片（`{duration, frames}`），唔係相 */
    clip?: { duration: number; frames: number } | null
    vision_used?: boolean
  }
  created_at: string
}

/* ---------- 男士護膚基本資料（app/guide.py 出嘅內容）---------- */

export type GuideBlockType = 'para' | 'list' | 'steps' | 'callout' | 'image' | 'sources' | 'actives'

export interface GuideBlock {
  type: GuideBlockType
  text: string
  items: string[]
  tone: 'info' | 'warn' | 'tip' | string
  image_id: string
  citations: string[]
}

export interface GuideSection {
  id: string
  title: string
  icon: string
  summary: string
  blocks: GuideBlock[]
}

export interface Guide {
  title: string
  subtitle: string
  sections: GuideSection[]
  /* 所有引用資料嘅匯總（source :: title），對應 backend corpus chunks */
  sources: string[]
}

/** A frame sampled out of an uploaded clip. It **is** a photo (`/api/photos/<id>`). */
export interface VideoFrame {
  id: string
  path: string
}

/**
 * Response of `POST /api/videos`.
 *
 * `sampled` / `dropped` are candidate counts (the sampler proposes up to 24 points and
 * de-duplicates them down to at most 6), not the frame count — that is `frames.length`.
 */
export interface VideoUpload {
  video_id: string
  path: string
  duration: number
  fps: number
  width: number
  height: number
  sampled: number
  dropped: number
  timestamps: number[]
  frames: VideoFrame[]
  original_bytes: number
  stored_bytes: number
  compressed: boolean
  /* Non-null when re-encoding was attempted and failed. The clip is still usable and
     still stored — compression is never allowed to fail the upload. */
  compress_error: string | null
}
