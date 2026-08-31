import { useEffect, useState } from 'react'
import * as api from '../api'
import { useTheme } from '../theme'

export function SettingsView() {
  const { theme, toggle } = useTheme()
  const [settings, setSettings] = useState<api.Settings | null>(null)

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => {})
  }, [])

  return (
    <main className="view full">
      <div className="view-head">
        <h2>設定</h2>
      </div>

      <div className="settings-grid">
        <div className="setting">
          <div className="k">LLM Provider</div>
          <div className="v">{settings?.llm_provider ?? '…'}</div>
        </div>
        <div className="setting">
          <div className="k">Model</div>
          <div className="v">{settings?.model ?? '…'}</div>
        </div>
        <div className="setting">
          <div className="k">API Key</div>
          <div className={`v ${settings?.has_api_key ? 'good' : 'bad'}`}>
            {settings?.has_api_key ? '✓ 已設定' : '未設定（會用 FakeLLM）'}
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
