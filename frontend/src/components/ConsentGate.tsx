import { useState } from 'react'

interface Props {
  busy: boolean
  error: string | null
  onAgree: () => void
}

/**
 * 一次性相片同意（2026-10-01 決定：全雲端，唔再分「本地／雲」）。
 *
 * 因為 app 冇本地模式，consent 就更加要**明示**：唔撳「我同意」就唔會入到 app，
 * 而後端亦一樣擋（`service.run_consult` 見唔到 `photo_cloud_consent` 就唔會送相上雲）。
 * 畫面要老實講清楚三件事：邊個睇得到、檔案放邊、可唔可以撤回。
 */
export function ConsentGate({ busy, error, onAgree }: Props) {
  const [checked, setChecked] = useState(false)
  return (
    <div className="app layout-chat">
      <main tabIndex={0} role="region" aria-label="同意聲明" className="view full consent-gate">
        <div className="consent-card">
          <h1>開始之前，需要你同意一件事</h1>
          <ul>
            <li>
              你上載嘅 <b>皮膚相會送去雲端 vision 模型</b>（DeepSeek）分析，先睇得出暗瘡、油光、泛紅、
              乾燥、毛孔同膚質。
            </li>
            <li>
              相片 <b>檔案本身只會存喺你自己部機</b>（<code>backend/data/photos/</code>），唔會上載去任何雲端儲存。
            </li>
            <li>
              每日嘅皮膚讀數、記憶同時間線都存喺本機 SQLite；每次只會送<b>你今次上載嗰張相</b>。
            </li>
            <li>
              你嘅文字訊息本身已經會送去同一個模型做分析同建議（呢個 app 冇 on-device 模型）。
            </li>
            <li>冇本地模式：唔同意就唔可以用相片分析（純文字都仍然需要傳文字去模型）。</li>
          </ul>
          <label className="consent-check">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            我明白並同意：我上載嘅皮膚相會送去雲端 AI 分析。
          </label>
          {error && <p className="consent-err">記錄唔到同意：{error}</p>}
          <button className="btn" disabled={!checked || busy} onClick={onAgree}>
            {busy ? '儲存緊…' : '同意，開始用'}
          </button>
        </div>
      </main>
    </div>
  )
}
