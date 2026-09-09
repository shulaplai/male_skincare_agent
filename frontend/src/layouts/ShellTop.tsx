import { useState } from 'react'
import { useTheme } from '../theme'
import type { Conversation } from '../types'
import type { SceneTab, ShellScene } from './defs'

interface Props {
  bodyLabel: string
  icon: string
  conversations: Conversation[]
  active: Conversation
  online: boolean
  tabs: SceneTab[]
  scene: ShellScene
  onScene: (s: ShellScene) => void
  onSelectConversation: (id: string) => void
  onToggleCloud: (id: string, enabled: boolean) => void
}

/** 結構 2/3 共用嘅頂部：部位切換 + 狀態/雲/主題 + scene tabs。 */
export function ShellTop({ bodyLabel, icon, conversations, active, online, tabs, scene, onScene, onSelectConversation, onToggleCloud }: Props) {
  const { toggle } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const cloud = active.cloudAnalysis
  return (
    <header className="shell-top">
      <div className="top-row">
        <div className="cur">
          <span className="part">{icon}</span>
          <h1>{bodyLabel}</h1>
          <div className="dropdown">
            <span className="switch" onClick={() => setMenuOpen((v) => !v)}>
              切換部位 ▾
            </span>
            {menuOpen && (
              <div className="dropdown-menu">
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    className={`dropdown-item${c.id === active.id ? ' active' : ''}`}
                    onClick={() => {
                      onSelectConversation(c.id)
                      setMenuOpen(false)
                    }}
                  >
                    {c.icon} {c.bodyPart}
                    {c.cloudAnalysis ? ' · ☁️' : ' · 🔒'}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="head-actions">
          <div className={`status${online ? '' : ' offline'}`}>
            <span className="pulse" /> {online ? 'Agent 在線' : '離線模式'}
          </div>
          <span
            className={`cloud-toggle ${cloud ? 'on' : ''}`}
            title={cloud ? '雲分析已開（影相會送雲端 vision）' : '本地模式（相唔會上雲分析）'}
            onClick={() => onToggleCloud(active.id, !cloud)}
          >
            {cloud ? '☁️ 雲分析' : '🔒 本地'}
          </span>
          <button className="theme" onClick={toggle} title="切換日/夜模式">
            <span className="sun">☀️</span>
            <span className="moon">🌙</span>
          </button>
        </div>
      </div>
      <nav className="scene-tabs">
        {tabs.map((t) => (
          <a key={t.key} className={scene === t.key ? 'active' : ''} onClick={() => onScene(t.key)}>
            <span className="ti">{t.icon}</span>
            {t.label}
          </a>
        ))}
      </nav>
    </header>
  )
}
