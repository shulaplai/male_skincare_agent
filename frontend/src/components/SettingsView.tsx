import { useEffect, useState } from 'react'
import * as api from '../api'
import { LayoutPicker } from '../layouts/LayoutPicker'
import { useTheme } from '../theme'
import type { Conversation, View } from '../types'
import { Icon } from '../components/Icon'
import { useToast } from './ui/Toast'

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
  /** 去其他 scene（而家只有「指南」用）。四套 shell 都會傳。 */
  onNavigate?: (v: View) => void
}

export function SettingsView(props: Props) {
  const { conversations, activeId, online, onSelectConversation, onAddConversation, onRenameConversation, onDeleteConversation, onNavigate } = props
  const { theme, toggle } = useTheme()
  const { toast } = useToast()
  const [persona, setPersona] = useState<api.Persona | null>(null)
  const [draft, setDraft] = useState<Pick<api.Persona, 'gender' | 'ethnicity' | 'prompt'> | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api
      .getPersona()
      .then((p) => {
        setPersona(p)
        setDraft({ gender: p.gender, ethnicity: p.ethnicity, prompt: p.prompt })
      })
      .catch(() => setPersona(null))
  }, [])

  const dirty =
    !!persona &&
    !!draft &&
    (draft.gender !== persona.gender ||
      draft.ethnicity !== persona.ethnicity ||
      draft.prompt !== persona.prompt)

  const savePersona = () => {
    if (!draft) return
    setSaving(true)
    api
      .patchPersona(draft)
      .then((p) => {
        setPersona(p)
        setDraft({ gender: p.gender, ethnicity: p.ethnicity, prompt: p.prompt })
        toast('顧問設定已儲存')
      })
      .catch((e: Error) => toast(api.readableError(e), { tone: 'err' }))
      .finally(() => setSaving(false))
  }

  const toggleGreet = () => {
    if (!persona) return
    const next = !persona.greet_enabled
    setPersona({ ...persona, greet_enabled: next })
    api
      .patchPersona({ greet_enabled: next })
      .then((p) => setPersona(p))
      .catch((e: Error) => {
        setPersona({ ...persona, greet_enabled: !next })
        toast(api.readableError(e), { tone: 'err' })
      })
  }
  const [settings, setSettings] = useState<api.Settings | null>(null)
  const [settingsErr, setSettingsErr] = useState<string | null>(null)
  const [conn, setConn] = useState<Conn>('checking')

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch((e: Error) => setSettingsErr(api.readableError(e)))
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
    <main tabIndex={0} role="region" aria-label="設定內容" className="view full">
      <div className="view-head">
        <h2>設定</h2>
      </div>

      <h3 className="block-title">介面結構（即時切換 · 記得你揀邊套）</h3>
      <div style={{ maxWidth: 860 }}>
        <LayoutPicker />
      </div>
      <p className="hint">
        四套都係同一批真數據嘅唔同排法：對話主導（原本）、日記主導（逐日回顧）、數據主導（快睇進度）、
        手機版（窄屏專用）。切咗即刻生效，之後每次開都係呢套。
        <br />
        窄屏（≤ 760px）會<b>自動</b>用手機版；喺呢度揀邊套即時蓋過（今次開頁有效）—— 闊屏就會用你揀嗰套。
        想喺窄屏固定睇某一套，用 URL 加 <code>?layout=chat|journal|dash|mobile</code>（preview，唔會寫入偏好）。
      </p>

      <h3 className="block-title">顧問</h3>
      <div className="persona-card">
        <p className="hint" style={{ marginTop: 0 }}>
          你嘅專屬顧問。呢啲設定會直接影響佢嘅語氣同稱呼 —— 但唔會影響安全規則（唔診斷、唔開藥、紅旗轉介）。
        </p>
        <div className="persona-field">
          <span className="k" id="persona-gender">性別</span>
          <div className="seg" role="group" aria-labelledby="persona-gender">
            {([
              ['', '不指定'],
              ['male', '男性'],
              ['female', '女性'],
            ] as const).map(([value, label]) => (
              <button
                key={value || 'none'}
                type="button"
                aria-pressed={draft?.gender === value}
                className={draft?.gender === value ? 'on' : ''}
                onClick={() => setDraft((d) => (d ? { ...d, gender: value } : d))}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="persona-field">
          <label className="k" htmlFor="persona-ethnicity">背景（種族／地區）</label>
          <input
            id="persona-ethnicity"
            value={draft?.ethnicity ?? ''}
            maxLength={40}
            placeholder="例如：香港人、東南亞"
            onChange={(e) => setDraft((d) => (d ? { ...d, ethnicity: e.target.value } : d))}
          />
        </div>
        <div className="persona-field block">
          <label className="k" htmlFor="persona-prompt">人設描述</label>
          <textarea
            id="persona-prompt"
            rows={3}
            value={draft?.prompt ?? ''}
            maxLength={persona?.max_prompt_length ?? 400}
            placeholder={persona?.default_prompt ?? '例如：一位有多年經驗、講嘢直接但溫和嘅皮膚科顧問'}
            onChange={(e) => setDraft((d) => (d ? { ...d, prompt: e.target.value } : d))}
          />
          <span className="hint">留空就用預設：{persona?.default_prompt ?? '—'}</span>
        </div>
        <div className="persona-field">
          <span className="k" id="persona-greet">主動問候</span>
          <div className="persona-greet">
            <button
              type="button"
              role="switch"
              aria-checked={!!persona?.greet_enabled}
              aria-labelledby="persona-greet"
              className={`switch${persona?.greet_enabled ? ' on' : ''}`}
              onClick={toggleGreet}
            >
              <span />
            </button>
            <span className="hint">朝 09:00 · 晚 21:00（每日最多 2 次；23:00–08:00 唔會發）</span>
          </div>
        </div>
        <div className="persona-actions">
          <button className="btn" onClick={savePersona} disabled={!dirty || saving}>
            {saving ? '儲存緊…' : '儲存顧問設定'}
          </button>
          {!dirty && <span className="hint">冇改動</span>}
        </div>
      </div>

      <h3 className="block-title">指南</h3>
      <div className="guide-entry" style={{ maxWidth: 560 }}>
        <button className="guide-entry-btn" onClick={() => onNavigate?.('guide')}>
          <span className="ic" aria-hidden>
            <Icon name="book-open" size={22} />
          </span>
          <span className="t">
            <b>男士護膚基本資料</b>
            <em>一日點護膚 · 先後次序 · 咩皮膚用咩成份 · 有咩要注意</em>
          </span>
          <span className="go" aria-hidden>
            →
          </span>
        </button>
      </div>
      <p className="hint">
        「應該用咩產品」嗰節同 app 推薦你嘅成份用同一份資料（backend <code>recommend.RULES</code>），
        所以指南同顧問唔會講兩套。
      </p>

      <h3 className="block-title">Agent 連線</h3>
      <div className="settings-grid">
        <div className="setting">
          <div className="k">LLM Provider</div>
          <div className="v">{settings?.llm_provider ?? settingsErr ?? '…'}</div>
        </div>
        <div className="setting">
          <div className="k">文字 Model</div>
          <div className="v">
            {settings
              ? settings.llm_mode === 'fake'
                ? 'FakeLLM · 測試模式'
                : settings.model
              : '…'}
          </div>
        </div>
        <div className="setting">
          <div className="k">Vision Model（睇相）</div>
          <div className="v">
            {settings
              ? settings.vision_mode === 'fake'
                ? 'FakeLLM · 測試模式'
                : settings.vision_model || '（冇設定）'
              : '…'}
          </div>
        </div>
        <div className="setting">
          <div className="k">API Key</div>
          <div className={`v ${settings?.has_api_key ? 'good' : 'bad'}`}>
            {settings?.has_api_key ? <><Icon name="check" size={13} /> 已設定</> : '未設定（會用 FakeLLM）'}
          </div>
        </div>
        <div className="setting">
          <div className="k">Backend</div>
          <div className="v">
            {conn === 'checking' && '測試緊…'}
            {conn === 'ok' && <span className="good"><Icon name="check" size={13} /> 連線正常</span>}
            {conn === 'fail' && <span className="bad"><Icon name="x" size={13} /> 連唔到</span>}
            <button className="btn ghost small" onClick={testConn}>
              測試連線
            </button>
          </div>
        </div>
        <div className="setting">
          <div className="k">Theme</div>
          <div className="v">
            <button className="btn ghost" onClick={toggle}>
              {theme === 'light' ? <><Icon name="sun" size={14} /> 日間模式</> : <><Icon name="moon" size={14} /> 夜間模式</>}（撳一下切換）
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
                {c.id !== activeId && onSelectConversation && (
                  <button className="link-btn" onClick={() => onSelectConversation(c.id)}>
                    切換
                  </button>
                )}
                <button className="link-btn" onClick={() => onRenameConversation(c)}>
                  <Icon name="pencil" size={15} /> 改名
                </button>
                <button className="link-btn danger" onClick={() => onDeleteConversation(c)}>
                  <Icon name="trash-2" size={15} /> 刪除
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
          <Icon name="download" size={16} /> 匯出全部數據 (zip)
        </a>
        <p className="hint">
          相片同日記永遠儲喺你部機（SQLite + file）。匯出係一個 zip，你可以自己 keep 返一份。
        </p>
      </div>
    </main>
  )
}
