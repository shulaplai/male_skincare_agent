import type { AttributeKey, ServerMessage, Message } from './types'

export const ATTRIBUTE_META: Record<AttributeKey, { label: string; zh: string }> = {
  acne: { label: 'acne', zh: '暗瘡' },
  oiliness: { label: 'oiliness', zh: '油光' },
  redness: { label: 'redness', zh: '泛紅' },
  dryness: { label: 'dryness', zh: '乾燥' },
  pores: { label: 'pores', zh: '毛孔' },
  texture: { label: 'texture', zh: '質感' },
}

export const ATTRIBUTE_KEYS: AttributeKey[] = ['acne', 'oiliness', 'redness', 'dryness', 'pores', 'texture']

export function severityText(sev: number): string {
  return { 0: '正常', 1: '輕微', 2: '中等', 3: '嚴重' }[sev] ?? '—'
}

/**
 * 問候語跟住用戶自己部機嘅時間行（audit §7）：以前 19:5x、夜晚 11 點都係「早晨呀」，
 * 用戶會覺得個 app 唔知時間。連 icon 一齊回，免得 JSX 再判斷一次。
 */
export function greeting(now: Date = new Date()): { text: string; icon: 'sun' | 'moon' } {
  const h = now.getHours()
  if (h >= 5 && h < 12) return { text: '早晨呀', icon: 'sun' }
  if (h >= 12 && h < 18) return { text: '午安', icon: 'sun' }
  if (h >= 18 && h < 23) return { text: '晚上好', icon: 'moon' }
  return { text: '夜深喇', icon: 'moon' }
}

/** 時間一律交俾 `Intl`（audit §7）：手寫 `padStart` 只係喺單一語言下啱。 */
const TIME_FMT = new Intl.DateTimeFormat('zh-HK', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function hhmm(iso: string): string {
  const d = new Date(`${iso}Z`)
  if (Number.isNaN(d.getTime())) return iso
  return TIME_FMT.format(d)
}

export function ymd(iso: string): string {
  const d = new Date(`${iso}Z`)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Map a persisted server message back to a display Message (Q7 reload). */
export function fromServerMessage(m: ServerMessage): Message {
  if (m.role === 'user') {
    const clip = m.payload.clip
    const pid = m.payload.photos?.[0]
    return {
      id: `s${m.id}`,
      role: 'user',
      text: m.text || (clip ? '（已上傳皮膚影片）' : '（已上傳皮膚相）'),
      time: hhmm(m.created_at),
      date: ymd(m.created_at),
      // 片：出影片 chip，唔可以顯示抽格出嚟嘅相（內部實作唔應該 leak 俾用戶）
      clip: clip ? { duration: clip.duration ?? 0 } : undefined,
      photo: !clip && pid ? `/api/photos/${pid}` : undefined,
    }
  }
  const p = m.payload
  return {
    id: `s${m.id}`,
    role: 'coach',
    text: p.reply || p.summary || m.text,
    time: hhmm(m.created_at),
    date: ymd(m.created_at),
    analysis: {
      title: 'Agent 分析',
      metrics: p.metrics ?? [],
      advice: p.advice ?? [],
    },
    disclaimer: p.disclaimer,
    escalate: p.escalate,
    vision_used: p.vision_used,
    // AI 抽出嘅自報事件要跟埋 reload 返嚟（以前只在 live state → reload 就消失，
    // 用戶永遠確認唔到 diet／product，成因時間線亦餵唔到料）。已經確認過嘅唔再出。
    events: !p.events_applied && p.detected_events?.length ? p.detected_events : undefined,
  }
}
