import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import * as api from '../api'
import { BlurPhoto } from './BlurPhoto'
import type { Conversation, DetectedEvent, Message } from '../types'
import { useTheme } from '../theme'
import { Icon } from './Icon'
import { Skeleton } from './ui/Skeleton'
import { BodyPartMenu } from './ui/BodyPartMenu'
import { greeting } from '../format'

interface Props {
  conversation: Conversation
  conversations: Conversation[]
  messages: Message[]
  loading: boolean
  sending: boolean
  /** 串流期間要顯示嘅步驟（audit §7）；null 就用原本嗰句「約 5–10 秒」。 */
  stage?: string | null
  onSend: (
    text: string,
    photos: { id: string; path: string }[],
    video?: { duration: number; frames: number; video_id?: string },
  ) => void
  online: boolean
  onSelectConversation: (id: string) => void
  onConfirmEvents: (conversationId: string, msgId: string, events: DetectedEvent[]) => void
  /** 送失敗／離線嗰句可以原句重試（audit §7）——以前用戶打嘅字冇咗下文。 */
  onRetryMessage: (conversationId: string, msgId: string) => void
}

function splitAdvice(a: string): { lead: string; rest: string } {
  const idx = a.indexOf(' —— ')
  if (idx === -1) return { lead: a, rest: '' }
  return { lead: a.slice(0, idx), rest: a.slice(idx) }
}

function dayChip(date: string): string {
  const d = new Date(`${date}T00:00:00`)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((today.getTime() - d.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function EventChips({ m, onConfirm }: { m: Message; onConfirm?: (msgId: string, evs: DetectedEvent[]) => void }) {
  if (!m.events?.length) return null
  return (
    <div className="events-row">
      <span className="ev-label">我留意到：</span>
      {m.events.map((e, i) => (
        <span key={i} className={`event-chip t-${e.type}`}>
          <Icon name={e.type === 'diet' ? 'utensils' : e.type === 'product_start' ? 'droplet' : 'hand'} size={13} />{' '}
          {e.text || e.product_name}
        </span>
      ))}
      {onConfirm && (
        <span className="ev-actions">
          <button className="ev-yes" onClick={() => onConfirm(m.id, m.events!)}>
            <Icon name="check" size={13} /> 記低
          </button>
        </span>
      )}
    </div>
  )
}

/**
 * 已經打完嘅回覆 id（module 級）。
 *
 * 逐字打出嚟係「一次性」效果：切 scene／切 conversation 會 unmount 再 mount，冇呢個
 * Set 就會由頭再打一次（用戶會以為 app 重新分析）。放 module 級而唔係 state，係因為
 * 一個 id 打完就永遠打完，唔需要令 App re-render。
 */
const TYPED = new Set<string>()

function Bubble({
  m,
  onConfirm,
  onMediaLoad,
  onRetry,
  onGrow,
}: {
  m: Message
  onConfirm?: (msgId: string, evs: DetectedEvent[]) => void
  onMediaLoad?: () => void
  onRetry?: (msgId: string) => void
  /** 逐字期間文字會不停長高 → 要叫 Chat 重新 pin 到底部（同 `onMediaLoad` 一樣理由）。 */
  onGrow?: () => void
}) {
  const label = m.role === 'user' ? '你' : '顧問 · Agent'

  /* 三段式揭示（2026-10-20 用戶要求）：① 標題 → ② 正文 → ③ AI 分析卡，
     一段一段出，唔會三樣嘢同時彈出嚟。五個約束：
     1. 只有「今次新收到」嘅回覆（`m.fresh`）才分段；reload 嘅歷史即刻出齊全套；
     2. 尊重 `prefers-reduced-motion: reduce` → 即刻出齊（唔係裝飾，係易讀性）；
     3. 每一段長高之後都要 pin 到底部，否則用戶追唔到最新一行；
     4. 標題係空（舊 row／模型冇填）就即刻跳去正文 —— 唔會有一個空白段；
     5. `TYPED.add()` 一定要喺**全部出完**之後（`React.StrictMode` 之下 effect
        會 setup → cleanup → setup，喺開頭 add 會令回覆永遠空白，實測中過）。 */
  const fullTitle = m.role === 'coach' ? (m.title ?? '') : ''
  const fullBody = m.text
  const animate =
    m.role === 'coach' &&
    Boolean(m.fresh) &&
    !TYPED.has(m.id) &&
    !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [shown, setShown] = useState(() =>
    animate
      ? { title: '', body: '', card: false }
      : { title: fullTitle, body: fullBody, card: true },
  )
  const growRef = useRef(onGrow)
  growRef.current = onGrow
  useEffect(() => {
    if (!animate) return
    let timer = 0
    let cancelled = false
    // 不論幾長，標題約 0.2 秒、正文約 1.3 秒打完（18ms 一步，步長按字數攤分），
    // 唔會令長篇回覆要等 10 秒。
    const typeText = (text: string, budget: number, apply: (s: string) => void, done: () => void) => {
      if (!text) {
        apply('')
        done()
        return
      }
      const step = Math.max(1, Math.ceil(text.length / budget))
      let i = 0
      const tick = () => {
        if (cancelled) return
        i = Math.min(text.length, i + step)
        apply(text.slice(0, i))
        growRef.current?.()
        timer = window.setTimeout(i < text.length ? tick : done, i < text.length ? 18 : 240)
      }
      timer = window.setTimeout(tick, 40)
    }
    typeText(
      fullTitle,
      12,
      (v) => setShown((x) => ({ ...x, title: v })),
      () =>
        typeText(
          fullBody,
          72,
          (v) => setShown((x) => ({ ...x, body: v })),
          () => {
            if (cancelled) return
            setShown((x) => ({ ...x, card: true }))
            growRef.current?.()
            TYPED.add(m.id)
          },
        ),
    )
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [animate, fullTitle, fullBody, m.id])
  /* ⚠️ class 名唔可以照抄 role：CSS 嘅左右分邊係寫 `.msg.me`（`row-reverse` +
     `margin-left: auto`）＋ `.a.me`，而 role 係 `user` —— 直接寫 `msg user` 就
     永遠 match 唔到，用戶自己嗰句會同 AI 一樣靠左（實測 390px：兩邊 bubble 都由
     x=57 開始）。呢度做一次 mapping，兩邊（class 同 CSS）先真正見面。 */
  const who = m.role === 'user' ? 'me' : 'coach'
  return (
    <div className={`msg ${who}${m.error ? ' err' : ''}`}>
      <div className={`a ${who}`} />
      <div className="bubble">
        <div className="meta">
          {label} · {m.time}
          {m.pending && <span className="pending-dot">傳送緊…</span>}
        </div>
        {m.escalate && <div className="escalate-banner">
          <Icon name="triangle-alert" size={15} /> 呢個情況建議轉介皮膚科醫生
        </div>}
        {/* ① 標題：一句總結，最先出（2026-10-20）。空就唔 render，唔會留白位。
            刻意**唔係** heading（`h3`）：一段對話可能有幾十條回覆，每條都出一個
            heading 會令報讀器嘅標題導覽變成雜訊；而且條 bubble 之前嘅 heading 係
            `h1`（`ShellTop`）→ `h1` 跳 `h3` 會撞 `tests/ui/a11y.spec.ts` 嘅層級規則。
            視覺上靠字重／字級，語意上佢只係訊息嘅第一句。 */}
        {shown.title && <p className="coach-title">{shown.title}</p>}
        {/* ② 正文。包一層 span 純粹係俾 test 量「打咗幾多字」（`.reply-text`），
            冇任何樣式；唔包嘅話 innerText 會連 meta／分析卡一齊數。 */}
        <span className="reply-text">{shown.body}</span>
        {m.error && m.retry && onRetry && (
          <button type="button" className="retry" onClick={() => onRetry(m.id)}>
            <Icon name="refresh-cw" size={13} /> 重試
          </button>
        )}
        {m.clip && (
          <span className="clip-bubble" title="已上傳嘅皮膚影片">
            <Icon name="play" size={13} /> 皮膚影片{m.clip.duration ? ` · ${m.clip.duration.toFixed(0)} 秒` : ''}
          </span>
        )}
        {!m.clip && m.photo && (
          <BlurPhoto src={m.photo} thumbWidth={336} onLoad={onMediaLoad} />
        )}
        {/* ③ AI 分析卡：等正文打完才出（`shown.card`）。以前佢同正文一齊彈，
            用戶會先讀卡再讀解釋。徽章（睇相／雲端／model 名）已按 2026-10-20 要求收埋。 */}
        {shown.card &&
          m.role === 'coach' &&
          m.analysis &&
          (m.analysis.metrics.length > 0 || m.analysis.advice.length > 0) && (
          <>
            <div className="card">
              <h2>{m.analysis.title}</h2>
              <div className="metrics">
                {m.analysis.metrics.map((mm) => (
                  <div className="metric" key={mm.key}>
                    <div className="k">{mm.key}</div>
                    <div className={`v ${mm.dir}`}>{mm.value}</div>
                    {mm.note && <div className="d">{mm.note}</div>}
                  </div>
                ))}
              </div>
              <ul className="advice">
                {m.analysis.advice.map((a, i) => {
                  const { lead, rest } = splitAdvice(a)
                  return (
                    <li key={i}>
                      <span className="n">{String(i + 1).padStart(2, '0')}</span>
                      <span>
                        <b>{lead}</b>
                        {rest}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          </>
        )}
        {m.disclaimer && <div className="disclaimer">{m.disclaimer}</div>}
        {m.role === 'coach' && <EventChips m={m} onConfirm={onConfirm} />}
      </div>
    </div>
  )
}

export function Chat({
  conversation,
  conversations,
  messages,
  loading,
  sending,
  stage,
  onSend,
  online,
  onSelectConversation,
  onConfirmEvents,
  onRetryMessage,
}: Props) {
  const { toggle } = useTheme()
  /* 問候語每次 render 重算：用戶可能開住個 app 由朝早坐到夜晚。 */
  const hello = greeting()
  const [draft, setDraft] = useState('')
  const [attached, setAttached] = useState<{ id: string; path: string }[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState<string | null>(null)
  /* 用戶上傳嘅片：UI 上係「一條片 + 上載進度」。⛔️ 唔會顯示「抽咗 6 張相」、
     壓縮、格數呢啲內部實作（2026-10-01 決定）。`frames` 只用嚟內部送出。 */
  const [clip, setClip] = useState<{
    /** server 嘅片 id：放棄條片時要佢先刪得到 disk 上面嘅檔案（issue #27） */
    videoId: string | null
    url: string
    name: string
    duration: number
    frames: { id: string; path: string }[]
    /** `uploading` 期間可能未有進度數字（瀏覽器未報之前）→ 顯示不確定動畫 */
    state: 'uploading' | 'ready'
    pct: number | null
    /** 瀏覽器播唔到（例如冇 H.264 授權嘅 Chromium build）→ 出 SVG 佔位而唔係黑格。
     *  防守性：本機 Chromium 實測**播得到**（`readyState 4`、`duration 2`），
     *  之前見到 media error 其實係我自己嘅測試檔係 0 byte（見 AGENTS.md）。 */
    previewFailed: boolean
  } | null>(null)
  /* 換 conversation 嘅 effect 只可以依賴 `conversation.id`（加 `clip` 會令佢每次狀態變就
     行），所以用 ref 拎最新嘅片 id 去刪上一個部位放棄咗嘅片。 */
  const clipIdRef = useRef<string | null>(null)
  clipIdRef.current = clip?.videoId ?? null
  const fileRef = useRef<HTMLInputElement>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  /* 用戶係唔係「跟住最新一句」？一向上拉睇歷史就 false，唔好再搶佢個位置。 */
  const pinnedRef = useRef(true)

  const pinToBottom = () => {
    const el = threadRef.current
    if (!el || !pinnedRef.current) return
    el.scrollTop = el.scrollHeight
  }

  /* 輸入框自適應：`scrollHeight` 量完要即刻覆寫返 height（`auto` 先量得到真實內容
     高度）。上限 132px 之後自己 scroll，唔會食晒成個對話區。 */
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`
  }, [draft])

  /* 本地預覽嘅 blob URL：由 effect 回收 —— React 已經換走 `<video>` 之後才 revoke，
     即場 revoke 會令媒體元素報 ERR_REQUEST_RANGE_NOT_SATISFIABLE（實測）。 */
  useEffect(() => {
    const url = clip?.url
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [clip?.url])

  const onThreadScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    pinnedRef.current = el.scrollHeight - el.clientHeight - el.scrollTop <= 24
  }

  // Reset per-conversation composer state when switching body part (fix D1:
  // a half-typed message must not leak into another conversation).
  useEffect(() => {
    setDraft('')
    setAttached([])
    setUploading(false)
    setUploadErr(null)
    // 轉部位＝放棄未送出嘅片，同「撳 ×」一樣要真刪：相有 24 小時 sweep 包底，片冇
    // （issue #27）。
    const stranded = clipIdRef.current
    if (stranded) api.deleteUnattachedVideo(stranded).catch(() => {})
    setClip(null)
  }, [conversation.id])

  /* 對話一入嚟就要見到最新嗰句：`.thread` 係內部 scroll 容器（唔係 window scroll），
     reload／轉部位／手機版由其他 tab 返嚟之後永遠停喺最舊一條，用戶要自己拉幾千 px。
     用 layout effect 喺 paint 前定位，避免「先閃一下頂部再跳到底」。
     只喺換對話、有新訊息、開始送嗰陣強制跳；用戶自己向上睇歷史時唔會被打斷
     （`onScroll` 會更新 pinned）。 */
  useLayoutEffect(() => {
    pinnedRef.current = true
    pinToBottom()
  }, [conversation.id, messages.length, sending])

  /* 相係 async 載入：`<img>` 一 load 完 thread 就高咗，scrollTop 就唔再係底部
     （實測 1280×900：load 前 max 2429、load 後 3147）。所以要喺「仍然 pinned」
     嘅情況下重覆 pin。 */
  useEffect(() => {
    window.addEventListener('resize', pinToBottom)
    return () => window.removeEventListener('resize', pinToBottom)
  }, [])

  /* Webfont 載入完（`font-display: swap` → 先用 fallback 畫，之後換字型）文字高度會變，
     條 thread 就唔再係「貼住最新一句」。相有 `onLoad`，字型都要有。
     唔做呢步：真用戶見到 reload 之後條 thread 唔貼底（而且 snapshot 會 flaky）。 */
  useEffect(() => {
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts
    fonts?.ready.then(() => pinToBottom()).catch(() => {})
  }, [])

  /** 放棄未送出嘅片一定要真刪：`sweep_orphan_photos` 刻意保住 `Video.frames`，所以
   *  呢個係唯一嘅網（issue #27 —— 以前淨係 `setClip(null)`，條片、`Video` row 同啲格
   *  就留到成個對話被刪為止）。失敗唔擋用戶：唔通就係個檔留多陣。 */
  const dropClip = () => {
    const id = clip?.videoId
    if (id) api.deleteUnattachedVideo(id).catch(() => {})
    setClip(null)
  }

  const submit = () => {
    const t = draft.trim()
    // 一條片自己都算內容：以前淨係掛咗片、冇打字就撳發送會靜靜地冇反應。
    if (!t && attached.length === 0 && !clip) return
    if (sending || uploading) return
    // 片：用戶睇到嘅係一條片，所以文字同 UI 都唔會提「抽咗幾多張相」
    const fallback = clip ? '（已上傳皮膚影片）' : '（已上傳皮膚相）'
    onSend(
      t || fallback,
      attached,
      clip
        ? {
            duration: clip.duration,
            frames: clip.frames.length,
            // 後端用佢由 DB 攞返抽好嘅格 → 真正送去做 vision。冇咗呢個 id，條片就等於
            // 冇相（2026-10-20 出過真事故：model 憑 placeholder 作咗成日皮膚數據）。
            video_id: clip.videoId ?? undefined,
          }
        : undefined,
    )
    setDraft('')
    setAttached([])
    setClip(null)
  }

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setUploading(true)
    setUploadErr(null)
    // A clip is not an attachment by itself — the backend samples it into ≤ 6 photos and
    // those photos are what the agent sees. `video/quicktime` (iPhone) has no extension
    // match for `accept`, so the MIME type is the check, not the filename.
    if (f.type.startsWith('video/')) {
      // 換另一條片＝原本嗰條已經放棄，同「撳 ×」一樣要真刪（issue #27）。
      if (clip?.videoId) api.deleteUnattachedVideo(clip.videoId).catch(() => {})
      // 本地預覽：上載期間用戶見到自己嗰條片同進度，唔會只係呆等（用戶回報）。
      const url = URL.createObjectURL(f)
      setClip({
        videoId: null,
        url,
        name: f.name,
        duration: 0,
        frames: [],
        state: 'uploading',
        pct: null,
        previewFailed: false,
      })
      api
        .uploadVideo(conversation.id, f, (pct) => setClip((c) => (c ? { ...c, pct } : c)))
        .then((v) =>
          setClip((c) =>
            c ? { ...c, videoId: v.video_id, duration: v.duration, frames: v.frames, state: 'ready', pct: null } : c,
          ),
        )
        .catch((err: Error) => {
          setUploadErr(api.readableError(err))
          setClip(null)
        })
        .finally(() => setUploading(false))
    } else {
      api
        .uploadPhoto(f)
        .then((p) => setAttached((prev) => [...prev, p]))
        .catch((err: Error) => setUploadErr(api.readableError(err)))
        .finally(() => setUploading(false))
    }
    e.target.value = ''
  }

  const busy = sending || uploading
  /* 冇內容就冇嘢好送：以前個發送掣永遠喺度（撳落去 `submit()` 靜靜早退），
     手機輸入框隔籬長期掛住一個冇用嘅圓掣。`sending` 期間一定要留住（轉圈）。 */
  const canSend = draft.trim() !== '' || attached.length > 0 || clip !== null

  return (
    <main className="chat">
      <header className="chathead">
        <div className="cur">
          {/* 以前 render `conversation.icon`（DB 存住 🧔／🧴 emoji）→ 彩色字形
              同旁邊嘅 Lucide 線稿唔同來源、大細同基線都唔同。而家固定用 icon，
              DB 欄位留住唔動（舊 row 嘅 emoji 只係唔再顯示，唔使 migration）。 */}
          <span className="part" aria-hidden>
            <Icon name="user-round" size={16} />
          </span>
          <h1>{conversation.bodyPart}</h1>
          {/* 一份共用實作（以前 ShellTop 同呢度各寫一份 `<span onClick>`，兩邊都鍵盤撳唔到）。 */}
          <BodyPartMenu
            key={conversation.id}
            conversations={conversations}
            activeId={conversation.id}
            onSelect={onSelectConversation}
            className="chathead-menu"
          />
        </div>
        <div className="head-actions">
          <div className={`status${online ? '' : ' offline'}`} title={online ? 'Agent 在線' : '離線模式'}>
            <span className="pulse" />
            <span className="sb">{online ? 'Agent 在線' : '離線模式'}</span>
          </div>
          <button className="theme" onClick={toggle} title="切換日/夜模式" aria-label="切換日/夜模式">
            <span className="sun"><Icon name="sun" size={17} /></span>
            <span className="moon"><Icon name="moon" size={17} /></span>
          </button>
        </div>
      </header>

      <div className="thread" ref={threadRef} onScroll={onThreadScroll}>
        <div className="hello">
          <Icon name={hello.icon} size={16} /> {hello.text}，今日{conversation.bodyPart}感覺點？可以影張相，或者直接話我知食咗咩、用咗咩，我會
          <b>一路記住</b>幫你追蹤。
        </div>
        {loading && messages.length === 0 && <Skeleton lines={3} />}
        {messages.map((m, i) => {
          const prevDate = i > 0 ? messages[i - 1].date : null
          return (
            <div key={m.id}>
              {m.date !== prevDate && <div className="day">{dayChip(m.date)}</div>}
              <Bubble
                m={m}
                onConfirm={(mid, evs) => onConfirmEvents(conversation.id, mid, evs)}
                onMediaLoad={pinToBottom}
                onGrow={pinToBottom}
                onRetry={(mid) => onRetryMessage(conversation.id, mid)}
              />
            </div>
          )
        })}
        {sending && (
          <div className="msg coach">
            <div className="a coach" />
            {/* `role="status"` + `aria-live="polite"`：screen reader 會讀出「顧問諗緊…」，
                但唔會搶焦點（以前係完全冇提示，用戶以為壞咗）。 */}
            <div className="bubble typing" role="status" aria-live="polite">
              <span className="pulse" aria-hidden />
              {/* 後端逐個 node 報返嚟（SSE）之前，照舊老實講要等幾久；報咗之後就
                  改成講「而家做緊咩」，令 5.5 秒唔再係一片空白（audit §7）。 */}
              {stage ?? '顧問諗緊…（睇相＋分析＋建議，約 5–10 秒）'}
            </div>
          </div>
        )}
      </div>

      <div className="compose">
        {/* 附件擺上面一行（可以換行）：一條片 chip 有 54px thumb 同兩行字，同 textarea 爭同一個 row 就會將輸入框壓扁。`:empty` 令冇附件時唔佔高度。 */}
        <div className="compose-attach">
        {clip && (
          <span className={`clip-chip${clip.state === 'uploading' ? ' uploading' : ''}`}>
            {clip.previewFailed ? (
              <span className="clip-thumb placeholder" aria-hidden>
                <svg viewBox="0 0 24 24">
                  <rect x="3" y="5" width="18" height="14" rx="3" />
                  <path d="M10 9.5l5 2.5-5 2.5z" />
                </svg>
              </span>
            ) : (
              <video
                src={clip.url}
                className="clip-thumb"
                muted
                playsInline
                preload="metadata"
                onError={() => setClip((c) => (c ? { ...c, previewFailed: true } : c))}
              />
            )}
            <span className="clip-meta">
              <b><Icon name="play" size={13} /> 皮膚影片{clip.duration ? ` · ${clip.duration.toFixed(0)} 秒` : ''}</b>
              {clip.state === 'uploading' ? (
                <>
                  <span
                    className={`clip-bar${clip.pct === null ? ' unknown' : ''}`}
                    role="progressbar"
                    aria-valuenow={clip.pct ?? undefined}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <i style={{ transform: clip.pct === null ? undefined : `scaleX(${clip.pct / 100})` }} />
                  </span>
                  <em>上載緊…{clip.pct !== null ? ` ${clip.pct}%` : ''}（唔使等，可以繼續打字）</em>
                </>
              ) : (
                <em>已加入，撳「發送」交俾顧問分析</em>
              )}
            </span>
            <button
              type="button"
              className="x"
              title="移除"
              aria-label="移除皮膚影片"
              onClick={dropClip}
            >
              ×
            </button>
          </span>
        )}
        {attached.map((a) => (
          <span key={a.id} className="attach ok">
            <BlurPhoto src={`/api/photos/${a.id}`} alt="預覽" variant="thumb" thumbWidth={96} />
            <i className="ok-mark"><Icon name="check" size={12} /></i>
            <button
              type="button"
              className="x"
              aria-label="移除呢張相"
              onClick={() => {
                setAttached((prev) => prev.filter((x) => x.id !== a.id))
                // 揀相嗰刻已經寫咗落 disk —— 淨係移除 chip 會令個檔案永遠冇人認領
                // （issue #23）。失敗唔擋用戶：server 24 小時後嘅 sweep 會執手尾。
                api.deleteUnattachedPhoto(a.id).catch(() => {})
              }}
            >
              ×
            </button>
          </span>
        ))}
        {uploadErr && <span className="chip upload-err">
            <Icon name="circle-alert" size={13} /> 上傳失敗：{uploadErr}
          </span>}
        </div>
        <div className="compose-row">
        <div className="tools">
          <input
            ref={fileRef}
            type="file"
            accept="image/*,video/*"
            style={{ display: 'none' }}
            onChange={onPick}
          />
          {/* 2026-10-01：composer 只留一個掣。相簿／相機本來係同一個 file input
              （iOS 個 picker 自己會問「相片圖庫／拍照」），所以收起相簿掣冇功能損失。
              Measured: coverage comes from camera *movement*, not clip length — a 20 s
              static clip de-duplicates down to a single frame, a 10 s pan yields all 6.
              The hint has to reach the user before they film, so it rides the button. */}
          <button
            type="button"
            className="iconbtn"
            title="影相／錄片（片最多 20 秒；錄嗰陣鏡頭慢慢掃過成塊肌）"
            aria-label="影相／錄片"
            onClick={() => fileRef.current?.click()}
          >
            <Icon name="camera" size={20} />
          </button>
        </div>
        <textarea
          ref={inputRef}
          rows={1}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            // 中文輸入法：確認候選字都會 fire Enter，`isComposing` 唔擋就會誤送
            if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return
            e.preventDefault()
            submit()
          }}
          /* 短 placeholder：長版喺手機（16px 字）會自己 wrap 成兩行，令輸入框一開
             就 72px 高、白白食咗 11% 螢幕。提示已經喺上面個 welcome bubble 講咗。 */
          placeholder={`問${conversation.bodyPart}顧問任何嘢…`}
          aria-label={`同${conversation.bodyPart}顧問對話`}
        />
        {(canSend || sending) && (
          <button className="send" onClick={submit} disabled={busy} aria-label="發送" title="發送（Enter）">
            {sending ? (
              <svg className="spin" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="8" />
              </svg>
            ) : (
              /* → 唔係 ↑：呢粒掣係「送出去」，向上箭嘴令人以為係「捲上去」 */
              <Icon name="arrow-right" size={20} />
            )}
          </button>
        )}
        </div>
      </div>
    </main>
  )
}
