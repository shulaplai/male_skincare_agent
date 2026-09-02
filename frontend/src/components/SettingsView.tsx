import { useEffect, useState } from 'react'
import * as api from '../api'
import { useTheme } from '../theme'

type Conn = 'checking' | 'ok' | 'fail'

export function SettingsView() {
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

  return (
    <main className="view full">
      <div className="view-head">
        <h2>設定</h2>
      </div>

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
