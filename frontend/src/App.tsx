import { useState } from 'react'
import { ThemeProvider } from './theme'
import { Sidebar } from './components/Sidebar'
import { Chat } from './components/Chat'
import { RightPanel } from './components/RightPanel'
import { initialConversations, initialMessages, memoryItems, score, timeline } from './data'
import type { Conversation, Message } from './types'

let counter = 1000

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations)
  const [activeId, setActiveId] = useState(initialConversations[0].id)
  const [messages, setMessages] = useState<Record<string, Message[]>>(initialMessages)

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  const addConversation = () => {
    const name = window.prompt('新部位名稱？（例如：背部、手腳、頭皮…）')
    if (!name?.trim()) return
    const id = 'c' + counter++
    const conv: Conversation = { id, bodyPart: name.trim(), icon: '🧴', days: 0 }
    setConversations((prev) => [...prev, conv])
    setMessages((prev) => ({ ...prev, [id]: [] }))
    setActiveId(id)
  }

  const sendMessage = (text: string) => {
    const userMsg: Message = { id: 'm' + counter++, role: 'user', text, time: '現在' }
    setMessages((prev) => ({ ...prev, [active.id]: [...(prev[active.id] ?? []), userMsg] }))
    // Canned ack — the real multi-step agent reply lands in Phase 3 (LangGraph backend).
    setTimeout(() => {
      const reply: Message = {
        id: 'm' + counter++,
        role: 'coach',
        text: '收到，我記低咗喇 💛（正式 agent 回應會喺 Phase 3 接上 LangGraph 後端）',
        time: '現在',
      }
      setMessages((prev) => ({ ...prev, [active.id]: [...(prev[active.id] ?? []), reply] }))
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
        <Chat conversation={active} messages={messages[active.id] ?? []} onSend={sendMessage} />
        <RightPanel score={score} memories={memoryItems} timeline={timeline} bodyPart={active.bodyPart} />
      </div>
    </ThemeProvider>
  )
}
