import { useCallback, useEffect, useRef, useState } from 'react'
import { ThemeProvider } from './theme'
import { Sidebar } from './components/Sidebar'
import { Chat } from './components/Chat'
import { RightPanel } from './components/RightPanel'
import { RecordsView } from './components/RecordsView'
import { ProgressView } from './components/ProgressView'
import { SettingsView } from './components/SettingsView'
import * as api from './api'
import { fromServerMessage } from './format'
import type { Conversation, DetectedEvent, Message, View } from './types'

let localId = 1
const local = (): string => `m${localId++}`

function toConversation(c: api.ApiConversation, isDefault = false): Conversation {
  return { id: c.id, bodyPart: c.body_part, icon: c.icon, cloudAnalysis: c.cloud_analysis, isDefault }
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Record<string, Message[]>>({})
  const [online, setOnline] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [refreshKey, setRefreshKey] = useState(0)
  const [sending, setSending] = useState(false)
  const [loadingThread, setLoadingThread] = useState(false)
  const booted = useRef(false)

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
    const name = window.prompt('新部位名稱？（例如：背部、手腳、頭皮…）')
    if (!name?.trim()) return
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

  const setCloud = useCallback(
    (cid: string, enabled: boolean) => {
      if (!online) return
      api
        .setCloudAnalysis(cid, enabled)
        .then(() => {
          setConversations((prev) => prev.map((c) => (c.id === cid ? { ...c, cloudAnalysis: enabled } : c)))
        })
        .catch((e: Error) => window.alert(`更新失敗：${e.message}`))
    },
    [online],
  )

  const sendMessage = (text: string, photos: { id: string; path: string }[]) => {
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
      photo: pid ? `/api/photos/${pid}` : undefined,
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
      .consult(cid, text, photos.map((p) => p.id))
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
    api
      .applyEvents(cid, events)
      .then(() => {
        // Hide the chips on that message once confirmed.
        setMessages((prev) => ({
          ...prev,
          [cid]: (prev[cid] ?? []).map((m) => (m.id === msgId ? { ...m, events: undefined } : m)),
        }))
        setRefreshKey((k) => k + 1)
      })
      .catch((e: Error) => window.alert(`記低失敗：${e.message}`))
  }

  const quickRecord = (cid: string, diet: string, product: string) => {
    const events: DetectedEvent[] = []
    if (diet.trim()) events.push({ type: 'diet', text: diet.trim(), tags: [] })
    if (product.trim()) events.push({ type: 'product_start', text: `開始用：${product.trim()}`, product_name: product.trim() })
    if (!events.length) return
    if (!online) {
      window.alert('後端未連線，記唔到。')
      return
    }
    api
      .applyEvents(cid, events)
      .then(() => setRefreshKey((k) => k + 1))
      .catch((e: Error) => window.alert(`記低失敗：${e.message}`))
  }


  const renameConversation = (c: Conversation) => {
    const name = window.prompt('改名做？', c.bodyPart)
    if (!name?.trim()) return
    api.renameConversation(c.id, name.trim()).then((r) => {
      setConversations((prev) => prev.map((x) => (x.id === c.id ? { ...x, bodyPart: r.body_part } : x)))
    }).catch((e: Error) => window.alert(`改名失敗：${e.message}`))
  }

  const deleteConv = (c: Conversation) => {
    if (!window.confirm(`永久刪除「${c.bodyPart}」同佢所有紀錄（相／日記／記憶／時間線）？呢個動作冇得復原。`)) return
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
      })
      .catch((e: Error) => window.alert(`刪除失敗：${e.message}`))
  }

  if (!active) {
    return (
      <ThemeProvider>
        <div className="app">
          <main className="view full">
            <p className="empty">連接緊 backend…（如冇反應，請確認 uvicorn 已喺 :8001 起咗）</p>
          </main>
        </div>
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
      <div className="app">
        <Sidebar
          conversations={conversations}
          activeId={active.id}
          view={view}
          online={online}
          onSelect={setActiveId}
          onAdd={addConversation}
          onNavigate={setView}
          onRename={renameConversation}
          onDelete={deleteConv}
        />
        {view === 'chat' && (
          <>
            <Chat
              conversation={active}
              conversations={conversations}
              messages={messages[active.id] ?? []}
              sending={sending}
              onSend={sendMessage}
              online={online}
              loading={loadingThread}
              onSelectConversation={setActiveId}
              onToggleCloud={setCloud}
              onConfirmEvents={confirmEvents}
              onQuickRecord={quickRecord}
            />
            <RightPanel conversation={active} refreshKey={refreshKey} onToggleCloud={setCloud} />
          </>
        )}
        {view === 'records' && <RecordsView conversation={active} />}
        {view === 'progress' && <ProgressView conversation={active} />}
        {view === 'settings' && <SettingsView />}
      </div>
    </ThemeProvider>
  )
}
