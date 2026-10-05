import { useTheme } from '../theme'
import type { Conversation } from '../types'
import type { SceneTab, ShellScene } from './defs'
import { BodyPartMenu } from '../components/ui/BodyPartMenu'
import { linkClick, sceneHref } from '../hooks/useSceneRoute'
import { Icon } from '../components/Icon'

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
}

/** 結構 2/3/4 共用嘅頂部：部位切換 + 狀態/主題 + scene tabs。
 *  ☁️／🔒 開關已經冇咗（2026-10-01：全雲端，consent 只問一次）。 */
export function ShellTop({ bodyLabel, icon, conversations, active, online, tabs, scene, onScene, onSelectConversation }: Props) {
  const { toggle } = useTheme()
  /** tab bar 嘅 default scene（`useSceneRoute` 嘅 fallback）= 第一個 tab。 */
  const fallback = tabs[0].key
  return (
    <header className="shell-top">
      <div className="top-row">
        <div className="cur">
          <span className="part">{icon}</span>
          <h1>{bodyLabel}</h1>
          <BodyPartMenu conversations={conversations} activeId={active.id} onSelect={onSelectConversation} />
        </div>
        <div className="head-actions">
          {/* title 一定要有：手機版（`.app.layout-mobile`）會用 CSS 將文字收成一個 pulse 點，
              冇 title 就會完全失去「在線／離線」呢個資訊 */}
          <div className={`status${online ? '' : ' offline'}`} title={online ? 'Agent 在線' : '離線模式'}>
            <span className="pulse" />
            <span className="sb">{online ? 'Agent 在線' : '離線模式'}</span>
          </div>
          <button className="theme" onClick={toggle} title="切換日/夜模式" aria-label="切換日/夜模式">
            <span className="sun"><Icon name="sun" size={17} /></span>
            <span className="moon"><Icon name="moon" size={17} /></span>
          </button>
        </div>
      </div>
      {/* 真 `<a href>`：冇 href 嘅 `<a>` 入唔到 tab order（見 `sceneHref` 註解），
          而呢個就係 journal／dash 結構嘅主要導覽。 */}
      <nav className="scene-tabs" aria-label="頁面導覽">
        {tabs.map((t) => (
          <a
            key={t.key}
            href={sceneHref(t.key, fallback)}
            className={scene === t.key ? 'active' : ''}
            aria-current={scene === t.key ? 'page' : undefined}
            onClick={linkClick(t.key, onScene)}
          >
            <span className="ti" aria-hidden><Icon name={t.icon} size={16} /></span>
            {t.label}
          </a>
        ))}
      </nav>
    </header>
  )
}
