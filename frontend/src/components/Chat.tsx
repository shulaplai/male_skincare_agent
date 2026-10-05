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
  onSend: (text: string, photos: { id: string; path: string }[], video?: { duration: number; frames: number }) => void
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

function Bubble({
  m,
  onConfirm,
  onMediaLoad,
  onRetry,
}: {
  m: Message
  onConfirm?: (msgId: string, evs: DetectedEvent[]) => void
  onMediaLoad?: () => void
  onRetry?: (msgId: string) => void
}) {
  const label = m.role === 'user' ? '你' : '教練 · Agent'
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
        {m.text}
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
        {m.role === 'coach' && m.analysis && (
          <>
            <div className={`vision-badge ${m.vision_used ? 'seen' : 'text'}`}>
              <Icon name={m.vision_used ? 'eye' : 'pencil'} size={13} />
              {m.vision_used ? '已睇相分析（雲端）' : '文字分析（未睇相）'}
            </div>
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
    onSend(t || fallback, attached, clip ? { duration: clip.duration, frames: clip.frames.length } : undefined)
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

  return (
    <main className="chat">
      <header className="chathead">
        <div className="cur">
          <span className="part">{conversation.icon}</span>
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
                onRetry={(mid) => onRetryMessage(conversation.id, mid)}
              />
            </div>
          )
        })}
        {sending && (
          <div className="msg coach">
            <div className="a coach" />
            {/* `role="status"` + `aria-live="polite"`：screen reader 會讀出「教練諗緊…」，
                但唔會搶焦點（以前係完全冇提示，用戶以為壞咗）。 */}
            <div className="bubble typing" role="status" aria-live="polite">
              <span className="pulse" aria-hidden />
              {/* 後端逐個 node 報返嚟（SSE）之前，照舊老實講要等幾久；報咗之後就
                  改成講「而家做緊咩」，令 5.5 秒唔再係一片空白（audit §7）。 */}
              {stage ?? '教練諗緊…（睇相＋分析＋建議，約 5–10 秒）'}
            </div>
          </div>
        )}
      </div>

      <div className="compose">
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
                <em>已加入，撳「發送」交俾教練分析</em>
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
          placeholder={`問${conversation.bodyPart}教練任何嘢…`}
          aria-label={`同${conversation.bodyPart}教練對話`}
        />
        <button className="send" onClick={submit} disabled={busy} aria-label="發送" title="發送（Enter）">
          {sending ? (
            <svg className="spin" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" />
            </svg>
          ) : (
            <Icon name="arrow-up" size={20} />
          )}
        </button>
      </div>
    </main>
  )
}
