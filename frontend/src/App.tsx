import { useEffect, useState } from 'react'
import { ThemeProvider } from './theme'
import { Sidebar } from './components/Sidebar'
import { Chat } from './components/Chat'
import { RightPanel } from './components/RightPanel'
import * as api from './api'
import { initialConversations, initialMessages, memoryItems, score, timeline } from './data'
import type { Conversation, Message } from './types'

let counter = 1000

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations)
  const [activeId, setActiveId] = useState(initialConversations[0].id)
  const [messages, setMessages] = useState<Record<string, Message[]>>(initialMessages)
  const [online, setOnline] = useState(false)

  useEffect(() => {
    api
      .listConversations()
      .then(async (list) => {
        setOnline(true)
        if (list.length) {
          const convs: Conversation[] = list.map((c) => ({
            id: c.id,
            bodyPart: c.body_part,
            icon: c.icon,
            days: 0,
            isDefault: c.body_part === '面部皮膚',
          }))
          setConversations(convs)
          setActiveId(convs[0].id)
          setMessages({ [convs[0].id]: [] })
        } else {
          const c = await api.createConversation('面部皮膚', '🧔')
          setConversations([{ id: c.id, bodyPart: c.body_part, icon: c.icon, days: 0, isDefault: true }])
          setActiveId(c.id)
          setMessages({ [c.id]: [] })
        }
      })
      .catch(() => setOnline(false))
  }, [])

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  const addConversation = () => {
    const name = window.prompt('新部位名稱？（例如：背部、手腳、頭皮…）')
    if (!name?.trim()) return
    if (online) {
      api.createConversation(name.trim()).then((c) => {
        const conv: Conversation = { id: c.id, bodyPart: c.body_part, icon: c.icon, days: 0 }
        setConversations((prev) => [...prev, conv])
        setMessages((prev) => ({ ...prev, [c.id]: [] }))
        setActiveId(c.id)
      })
      return
    }
    const id = 'c' + counter++
    const conv: Conversation = { id, bodyPart: name.trim(), icon: '🧴', days: 0 }
    setConversations((prev) => [...prev, conv])
    setMessages((prev) => ({ ...prev, [id]: [] }))
    setActiveId(id)
  }

  const sendMessage = (text: string) => {
    const cid = active.id
    const userMsg: Message = { id: 'm' + counter++, role: 'user', text, time: '現在' }
    setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []), userMsg] }))

    if (online) {
      api
        .consult(cid, text)
        .then((res) => {
          const reply: Message = {
            id: 'm' + counter++,
            role: 'coach',
            text: res.analysis.summary,
            time: '現在',
            analysis: { title: 'Agent 分析', metrics: res.analysis.metrics, advice: res.advice.items },
            disclaimer: res.advice.disclaimer,
            escalate: res.escalate,
          }
          setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []), reply] }))
        })
        .catch(() => {
          const reply: Message = { id: 'm' + counter++, role: 'coach', text: '後端連唔到，請確認 backend 已起。', time: '現在' }
          setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []), reply] }))
        })
      return
    }

    setTimeout(() => {
      const reply: Message = {
        id: 'm' + counter++,
        role: 'coach',
        text: '收到，我記低咗喇 💛（後端未連接，呢個係離線示範回覆）',
        time: '現在',
      }
      setMessages((prev) => ({ ...prev, [cid]: [...(prev[cid] ?? []), reply] }))
    }, 600)
  }

  return (
    <ThemeProvider>
      <div className="app">
        <Sidebar
          conversations={conversations}
          activeId={active.id}
          onSelect={setActiveId}
          onAdd={addConversation}
        />
        <Chat conversation={active} messages={messages[active.id] ?? []} onSend={sendMessage} online={online} />
        <RightPanel score={score} memories={memoryItems} timeline={timeline} bodyPart={active.bodyPart} />
      </div>
    </ThemeProvider>
  )
}
