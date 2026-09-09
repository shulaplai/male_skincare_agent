import { useEffect, useState } from 'react'
import * as api from '../api'
import { LayoutPicker } from '../layouts/LayoutPicker'
import { useTheme } from '../theme'
import type { Conversation } from '../types'

type Conn = 'checking' | 'ok' | 'fail'

interface Props {
  /** conversation 管理（rename/delete）——三套結構都傳，等任何一套都改到部位。 */
  conversations?: Conversation[]
  activeId?: string
  online?: boolean
  onSelectConversation?: (id: string) => void
  onAddConversation?: () => void
  onRenameConversation?: (c: Conversation) => void
  onDeleteConversation?: (c: Conversation) => void
}

export function SettingsView(props: Props) {
  const { conversations, activeId, online, onSelectConversation, onAddConversation, onRenameConversation, onDeleteConversation } = props
  const { theme, toggle } = useTheme()
  const [settings, setSettings] = useState<api.Settings | null>(null)
  const [settingsErr, setSettingsErr] = useState<string | null>(null)
  const [conn, setConn] = useState<Conn>('checking')

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch((e: Error) => setSettingsErr(e.message))
    api
      .health()
      .then(() => setConn('ok'))
      .catch(() => setConn('fail'))
  }, [])

  const testConn = () => {
    setConn('checking')
    api
      .health()
      .then(() => setConn('ok'))
      .catch(() => setConn('fail'))
  }

  const convs = conversations ?? []

  return (
    <main className="view full">
      <div className="view-head">
        <h2>設定</h2>
      </div>

      <h3 className="block-title">介面結構（即時切換 · 記得你揀邊套）</h3>
      <div style={{ maxWidth: 860 }}>
        <LayoutPicker />
      </div>
      <p className="hint">
        三套都係同一批真數據嘅唔同排法：對話主導（原本）、日記主導（逐日回顧）、數據主導（快睇進度）。
        切咗即刻生效，之後每次開都係呢套。
      </p>

      <h3 className="block-title">Agent 連線</h3>
      <div className="settings-grid">
        <div className="setting">
          <div className="k">LLM Provider</div>
          <div className="v">{settings?.llm_provider ?? settingsErr ?? '…'}</div>
        </div>
        <div className="setting">
          <div className="k">文字 Model</div>
          <div className="v">{settings?.model ?? '…'}</div>
        </div>
        <div className="setting">
          <div className="k">Vision Model（睇相）</div>
          <div className="v">{settings?.vision_model ?? '（冇設定）'}</div>
        </div>
        <div className="setting">
          <div className="k">API Key</div>
          <div className={`v ${settings?.has_api_key ? 'good' : 'bad'}`}>
            {settings?.has_api_key ? '✓ 已設定' : '未設定（會用 FakeLLM）'}
          </div>
        </div>
        <div className="setting">
          <div className="k">Backend</div>
          <div className="v">
            {conn === 'checking' && '測試緊…'}
            {conn === 'ok' && <span className="good">✓ 連線正常</span>}
            {conn === 'fail' && <span className="bad">✗ 連唔到</span>}
            <button className="btn ghost small" onClick={testConn}>
              測試連線
            </button>
          </div>
        </div>
        <div className="setting">
          <div className="k">Theme</div>
          <div className="v">
            <button className="btn ghost" onClick={toggle}>
              {theme === 'light' ? '☀️ 日間模式' : '🌙 夜間模式'}（撳一下切換）
            </button>
          </div>
        </div>
      </div>
      <p className="hint">
        Provider／Model／API key 都係由 <code>backend/.env</code> 管理（env-only，改完 restart backend）。對話入面個
        「本地／雲」掣係 per-conversation 嘅雲分析同意開關。
      </p>

      {convs.length > 0 && onRenameConversation && onDeleteConversation && (
        <>
          <h3 className="block-title">部位對話（管理）</h3>
          <div className="conv-mgr" style={{ maxWidth: 560 }}>
            {convs.map((c) => (
              <div key={c.id} className={`conv-mgr-row${c.id === activeId ? ' active' : ''}`}>
                <span className="part">{c.icon}</span>
                <span className="nm">{c.bodyPart}</span>
                <span className="meta">{c.cloudAnalysis ? '☁️ 雲分析' : '🔒 本地'}</span>
                {c.id !== activeId && onSelectConversation && (
                  <button className="link-btn" onClick={() => onSelectConversation(c.id)}>
                    切換
                  </button>
                )}
                <button className="link-btn" onClick={() => onRenameConversation(c)}>
                  ✎ 改名
                </button>
                <button className="link-btn danger" onClick={() => onDeleteConversation(c)}>
                  🗑 刪除
                </button>
              </div>
            ))}
            {onAddConversation && online !== false && (
              <button className="btn ghost small" onClick={onAddConversation}>
                ＋ 新增部位對話
              </button>
            )}
          </div>
          <p className="hint">喺度改名／刪除任何部位；刪除會連相、日記、記憶、時間線一齊冇（冇得復原）。</p>
        </>
      )}

      <h3 className="block-title">數據</h3>
      <div className="row-gap">
        <a className="btn ghost" href="/api/export">
          ⬇ 匯出全部數據 (zip)
        </a>
        <p className="hint">
          相片同日記永遠儲喺你部機（SQLite + file）。匯出係一個 zip，你可以自己 keep 返一份。
        </p>
      </div>
    </main>
  )
}
