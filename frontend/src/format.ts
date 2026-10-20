import type { AttributeKey, LLMProvenance, ServerMessage, Message } from './types'

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

/**
 * 三態 vision 徽章（issue #14）：`null` / `undefined` 係「未知」，唔係「未睇相」。
 * 舊 payload 冇 `vision_used`，以前會靜靜當 false → UI 對一個真睇過相嘅回覆講
 * 「文字分析（未睇相）」。未知就唔出徽章，比講錯好。
 */
export function visionClaim(
  used: boolean | null | undefined,
  hasClip = false,
): { icon: 'eye' | 'pencil'; text: string; tone: 'seen' | 'text' } | null {
  // 片同相要分開講：一條片冇被睇過時，寫「未睇相」會令用戶以為 app 睇咗條片
  // （2026-10-20：真 DB 有一條回覆 body 寫「睇你條片…泛紅由 0 回升到 1」，
  // 而 `vision_used` 係 false —— 呢個徽章係唯一講真話嘅位）。
  const what = hasClip ? '片' : '相'
  if (used === true) return { icon: 'eye', text: `已睇${what}分析（雲端）`, tone: 'seen' }
  if (used === false) return { icon: 'pencil', text: `文字分析（未睇${what}）`, tone: 'text' }
  return null
}

/**
 * Provenance chip 文案（issue #14）：fake 一定要講明係測試模式，唔可以扮真模型；
 * live 就出 resolver 真正揀咗嘅 provider · model（例如 `openai · gpt-4o-mini`）。
 * 舊訊息冇 provenance → null（唔出 chip）。
 */
export function provenanceLabel(p?: LLMProvenance | null): string | null {
  if (!p) return null
  if (p.mode === 'fake') return 'FakeLLM · 測試模式'
  return p.model ? `${p.provider} · ${p.model}` : p.provider
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
    // 保留三態：冇呢個欄位嘅舊 row = 未知（null），唔可以降級成 false。
    vision_used: p.vision_used ?? null,
    // 舊 row 冇呢個 key → undefined（徽章就會講「相」，同以前一樣，唔會亂講）。
    vision_clip: p.vision_clip === true,
    provenance: m.provenance ?? null,
    // AI 抽出嘅自報事件要跟埋 reload 返嚟（以前只在 live state → reload 就消失，
    // 用戶永遠確認唔到 diet／product，成因時間線亦餵唔到料）。已經確認過嘅唔再出。
    events: !p.events_applied && p.detected_events?.length ? p.detected_events : undefined,
  }
}
