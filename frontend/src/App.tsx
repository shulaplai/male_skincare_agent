import { useCallback, useEffect, useRef, useState } from 'react'
import { ConsentGate } from './components/ConsentGate'
import { useViewportHeight } from './hooks/useViewportHeight'
import { ConfirmProvider, useConfirm } from './components/ui/Confirm'
import { Sheet } from './components/ui/Sheet'
import { ToastProvider, useToast } from './components/ui/Toast'
import { LayoutProvider, useLayout } from './layouts/LayoutContext'
import { Shell } from './layouts/Shells'
import { ThemeProvider } from './theme'
import * as api from './api'
import { fromServerMessage } from './format'
import type { Conversation, DetectedEvent, Message } from './types'
import type { ShellProps } from './layouts/defs'

let localId = 1
const local = (): string => `m${localId++}`

function toConversation(c: api.ApiConversation, isDefault = false): Conversation {
  return { id: c.id, bodyPart: c.body_part, icon: c.icon, cloudAnalysis: c.cloud_analysis, isDefault }
}

/**
 * 要喺 `LayoutProvider` **入面**先讀到 layout context（App 本身 render provider，
 * 喺 App body 讀只會永遠拿到 default）→ 所以呢個 host 一定要係 provider 嘅 child。
 */
function LayoutHost({ p }: { p: ShellProps }) {
  const { layout } = useLayout()
  return (
    <div className={`app layout-${layout}`}>
      <Shell layout={layout} p={p} />
    </div>
  )
}

/**
 * ⚠️ `useToast()` / `useLayout()` 只可以喺 provider **之內** 用，所以真正嘅 app 係
 * `AppInner`，而 `App` 淨係負責掛 providers（次序：theme → toast → layout）。
 * 以前所有嘢都喺 `App` 度，想用 `useToast()` 就會拿到 context 嘅 default（靜靜冇反應）。
 */
function AppInner() {
  const { toast } = useToast()
  const confirm = useConfirm()
  useViewportHeight()  // iOS 鍵盤：寫 --vvh 落 :root（見 hooks/useViewportHeight.ts）
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Record<string, Message[]>>({})
  const [online, setOnline] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [sending, setSending] = useState(false)
  const [loadingThread, setLoadingThread] = useState(false)
  /* 一次性相片同意：`null` = 未知（載入緊）。未同意之前唔會 render app —— 因為
     「全雲端」之下冇本地模式，用戶冇得「唔同意但照用」。後端一樣擋。 */
  /* Sheet 取代 window.prompt／confirm（Phase 2a）。一次只會開一個。 */
  const [sheet, setSheet] = useState<{ kind: 'new' | 'rename'; conv?: Conversation } | null>(null)
  const [sheetText, setSheetText] = useState('')
  const [consent, setConsent] = useState<boolean | null>(null)
  const [consentBusy, setConsentBusy] = useState(false)
  const [consentErr, setConsentErr] = useState<string | null>(null)
  const booted = useRef(false)

  const agree = useCallback(() => {
    setConsentBusy(true)
    setConsentErr(null)
    api
      .grantConsent(true)
      .then((r) => setConsent(r.granted))
      .catch((e: Error) => setConsentErr(e.message || '未知錯誤'))
      .finally(() => setConsentBusy(false))
  }, [])

  // Consent 狀態：app 開之前問後端（唔靠 localStorage，因為呢個係 data truth）
  useEffect(() => {
    api
      .getConsent()
      .then((r) => setConsent(r.granted))
      .catch(() => setConsent(null)) // 後端未起：下面會顯示「連接緊 backend…」
  }, [])

  // Boot: list/create conversations from the backend (source of truth).
  useEffect(() => {
    if (booted.current) return
    booted.current = true
    api
      .listConversations()
      .then(async (list) => {
        setOnline(true)
        let convs: Conversation[]
        if (list.length) {
          convs = list.map((c) => toConversation(c, c.body_part === '面部皮膚'))
        } else {
          const c = await api.createConversation('面部皮膚', '🧔')
          convs = [toConversation(c, true)]
        }
        setConversations(convs)
        setActiveId(convs[0].id)
        // Real threads load per-conversation below; no demo content (Q10).
      })
      .catch(() => {
        setOnline(false)
        // Offline: allow a local scratch conversation so the UI is usable.
        const scratch: Conversation = { id: 'local', bodyPart: '面部皮膚', icon: '🧔', cloudAnalysis: false }
        setConversations([scratch])
        setActiveId('local')
      })
  }, [])

  // Load a conversation's persisted thread when it becomes active (Q7).
  useEffect(() => {
    if (!activeId || !online) return
    let alive = true
    setLoadingThread(true)
    api
      .getMessages(activeId)
      .then((msgs) => {
        if (!alive) return
        setMessages((prev) => ({ ...prev, [activeId]: msgs.map(fromServerMessage) }))
      })
      .catch(() => {
        if (alive) setMessages((prev) => ({ ...prev, [activeId]: [] }))
      })
      .finally(() => alive && setLoadingThread(false))
    return () => {
      alive = false
    }
  }, [activeId, online])

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  const addConversation = () => {
    setSheetText('')
    setSheet({ kind: 'new' })
  }

  const submitNewConversation = () => {
    const name = sheetText.trim()
    if (!name) return
    setSheet(null)
    if (online) {
      api.createConversation(name.trim()).then((c) => {
        const conv = toConversation(c)
        setConversations((prev) => [...prev, conv])
        setActiveId(conv.id)
      })
      return
    }
    const conv: Conversation = { id: `local-${localId++}`, bodyPart: name.trim(), icon: '🧴', cloudAnalysis: false }
    setConversations((prev) => [...prev, conv])
    setActiveId(conv.id)
  }

  const sendMessage = (
    text: string,
    photos: { id: string; path: string }[],
    video?: { duration: number; frames: number },
  ) => {
    if (!active) return
    if (sending) return // guard against double-submit while a consult is running
    const cid = active.id
    const pid = photos[0]?.id
    const userMsg: Message = {
      id: local(),
      role: 'user',
      text,
      time: '現在',
      date: new Date().toISOString().slice(0, 10),
      // 片：只出「🎬 皮膚影片」chip；抽格出嚟嘅相唔會顯示（內部實作）
      clip: video ? { duration: video.duration } : undefined,
      photo: !video && pid ? `/api/photos/${pid}` : undefined,
      pending: true,
    }
    setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []), userMsg] }))

    if (!online) {
      // Offline fallback: echo locally, clearly marked (no fake demo content).
      window.setTimeout(() => {
        const reply: Message = {
          id: local(),
          role: 'coach',
          text: '後端未連線：訊息只記錄喺呢個 session，未存入日記。請起返 backend 再試。',
          time: '現在',
          date: new Date().toISOString().slice(0, 10),
          error: true,
        }
        setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []).filter((x) => x.id !== userMsg.id), { ...userMsg, pending: false }, reply] }))
      }, 400)
      return
    }

    setSending(true)
    api
      .consult(cid, text, photos.map((p) => p.id), video)
      .then((res) => {
        const reply: Message = {
          id: local(),
          role: 'coach',
          text: res.advice.reply || res.analysis.summary,
          time: '現在',
          date: new Date().toISOString().slice(0, 10),
          analysis: { title: 'Agent 分析', metrics: res.analysis.metrics, advice: res.advice.items },
          disclaimer: res.advice.disclaimer,
          escalate: res.escalate,
          vision_used: res.vision_used,
          events: res.advice.detected_events?.length ? res.advice.detected_events : undefined,
        }
        setMessages((prev) => ({
          ...prev,
          [cid]: [...(prev[cid] ?? []).filter((x) => x.id !== userMsg.id), { ...userMsg, pending: false }, reply],
        }))
        setRefreshKey((k) => k + 1)
      })
      .catch((e: Error) => {
        const reply: Message = {
          id: local(),
          role: 'coach',
          text: `出錯：${e.message || '未知錯誤'}`,
          time: '現在',
          date: new Date().toISOString().slice(0, 10),
          error: true,
        }
        setMessages((prev) => ({
          ...prev,
          [cid]: [...(prev[cid] ?? []).filter((x) => x.id !== userMsg.id), { ...userMsg, pending: false }, reply],
        }))
      })
      .finally(() => setSending(false))
  }

  const confirmEvents = (cid: string, msgId: string, events: DetectedEvent[]) => {
    if (!online) return
    // `s<id>` = 由 server 載入嘅訊息（有真 DB id，可以精準標記）；session 內新訊息
    // 只有本地 id，交返 server 用事件內容配對。
    const dbId = /^s\d+$/.test(msgId) ? Number(msgId.slice(1)) : undefined
    api
      .applyEvents(cid, events, dbId)
      .then(() => {
        // Hide the chips on that message once confirmed.
        setMessages((prev) => ({
          ...prev,
          [cid]: (prev[cid] ?? []).map((m) => (m.id === msgId ? { ...m, events: undefined } : m)),
        }))
        setRefreshKey((k) => k + 1)
      })
      .catch((e: Error) => toast(`記低失敗：${e.message}`, { tone: 'err' }))
  }

  const renameConversation = (c: Conversation) => {
    setSheetText(c.bodyPart)
    setSheet({ kind: 'rename', conv: c })
  }

  const submitRename = () => {
    const c = sheet?.conv
    const name = sheetText.trim()
    if (!c || !name) return
    setSheet(null)
    api
      .renameConversation(c.id, name)
      .then((r) => {
        setConversations((prev) => prev.map((x) => (x.id === c.id ? { ...x, bodyPart: r.body_part } : x)))
        toast(`已改名做「${r.body_part}」`)
      })
      .catch((e: Error) => toast(`改名失敗：${e.message}`, { tone: 'err' }))
  }

  const deleteConv = async (c: Conversation) => {
    const ok = await confirm({
      title: `刪除「${c.bodyPart}」？`,
      body: '會連同呢個部位嘅相、日記、記憶同時間線一齊永久刪除，冇得復原。',
      confirmLabel: '確定刪除',
      tone: 'danger',
    })
    if (!ok) return
    api.deleteConversation(c.id)
      .then(async () => {
        const rest = conversations.filter((x) => x.id !== c.id)
        if (rest.length) {
          setConversations(rest)
          if (activeId === c.id) setActiveId(rest[0].id)
        } else {
          const nc = await api.createConversation('面部皮膚', '🧔')
          setConversations([toConversation(nc, true)])
          setActiveId(nc.id)
        }
        setRefreshKey((k) => k + 1)
        toast(`已刪除「${c.bodyPart}」`)
      })
      .catch((e: Error) => toast(`刪除失敗：${e.message}`, { tone: 'err' }))
  }

  if (consent === false) {
    return <ConsentGate busy={consentBusy} error={consentErr} onAgree={agree} />
  }

  if (!active) {
    return (
      <div className="app layout-chat">
        <main tabIndex={0} role="region" aria-label="連線狀態" className="view full">
          <p className="empty">連接緊 backend…（如冇反應，請確認 uvicorn 已喺 :8001 起咗）</p>
        </main>
      </div>
    )
  }

  const shellProps: ShellProps = {
    conversations,
    active,
    messages,
    online,
    sending,
    loadingThread,
    refreshKey,
    onSelectConversation: setActiveId,
    onAddConversation: addConversation,
    onRenameConversation: renameConversation,
    onDeleteConversation: deleteConv,
    onSend: sendMessage,
    onConfirmEvents: confirmEvents,
  }

  return (
    <>
      <LayoutHost p={shellProps} />

      <Sheet
        open={sheet?.kind === 'new'}
        title="新增部位"
        body="例如：背部、手腳、頭皮。每個部位有自己嘅紀錄、記憶同時間線。"
        confirmLabel="新增"
        onConfirm={submitNewConversation}
        onClose={() => setSheet(null)}
      >
        <input
          type="text"
          value={sheetText}
          onChange={(e) => setSheetText(e.target.value)}
          placeholder="部位名稱"
          aria-label="部位名稱"
          onKeyDown={(e) => e.key === 'Enter' && submitNewConversation()}
        />
      </Sheet>

      <Sheet
        open={sheet?.kind === 'rename'}
        title="改名"
        confirmLabel="儲存"
        onConfirm={submitRename}
        onClose={() => setSheet(null)}
      >
        <input
          type="text"
          value={sheetText}
          onChange={(e) => setSheetText(e.target.value)}
          placeholder="部位名稱"
          aria-label="部位名稱"
          onKeyDown={(e) => e.key === 'Enter' && submitRename()}
        />
      </Sheet>

    </>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ConfirmProvider>
          <LayoutProvider>
            <AppInner />
          </LayoutProvider>
        </ConfirmProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
