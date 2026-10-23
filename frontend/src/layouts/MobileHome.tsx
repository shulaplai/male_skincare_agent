import { useMemo } from 'react'
import { MemoryList } from '../components/blocks'
import { useInsightActions } from '../hooks/useInsightActions'
import { useSummary } from '../hooks/useSummary'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META } from '../format'
import type { Message, RecordEntry } from '../types'
import type { HomeProps } from './defs'
import { Icon } from '../components/Icon'

/** `今天` / `昨天` / `YYYY-MM-DD · 星期X`；`short` 就出 `MM-DD 週X`（手機空間有限） */
function dayLabel(date: string, short = false): string {
  const d = new Date(`${date}T00:00:00`)
  if (Number.isNaN(d.getTime())) return date
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((today.getTime() - d.getTime()) / 86400000)
  const wd = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  if (short) {
    if (diff <= 0) return '今天'
    if (diff === 1) return '昨天'
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} 週${wd}`
  }
  // 同一個畫面唔應該同時出現 `2026-10-01 · 星期四` 同 `10-01 週四`（兩種格式、兩種星期寫法）。
  // 一律用短格式：10-01 週四。年份只喺跨年時才需要，而家未有跨年紀錄。
  if (diff <= 0) return `今天 · 週${wd}`
  if (diff === 1) return `昨天 · 週${wd}`
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} 週${wd}`
}

/** 本地今日 `YYYY-MM-DD`（entry.date 已經係呢個 shape）。 */
function todayYmd(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const severityOf = (e: RecordEntry | undefined, key: string): number | null =>
  e ? (e.attributes ?? []).find((a) => a.key === key)?.severity ?? null : null

/** 每條 entry 當日最後一條顧問回覆（用 App 已載入嘅 messages，唔另 fetch） */
function lastCoachByDate(messages: Message[]): Map<string, Message> {
  const map = new Map<string, Message>()
  for (const m of messages) {
    if (m.role !== 'coach' || m.error) continue
    map.set(m.date, m)
  }
  return map
}

/**
 * 結構 4 home：手機版「今日」—— hero 卡（今日膚況＋環形進度）＋ 滿寬打卡 CTA
 * ＋ 今日指標 ＋ 最近幾日 ＋ AI 記得你。風格 01「柔卡」（見 `design/mobile-1-soft-cards.html`）。
 *
 * **唯讀**：改筆記／刪相／刪 entry 去「記錄」tab（`RecordsView` 已有齊）。記憶就喺度刪得。
 * 全部數字都係真數據；冇數據就出 empty state，**冇 hardcode demo 數**（AGENTS.md 約定 #10）。
 *
 * ⚠️ 環形進度顯示嘅係「今日記低咗幾個指標」（0–6），**唔係一個膚況分數** ——
 * app 冇「整體膚況分數」呢個概念（`index.css` 有 `.score` 嘅死 CSS，但 `RightPanel` 從來冇
 * render 過）。設計樣板嗰個「膚況 2/3」係樣板自己發明，實作時唔可以照搬（約定 #2／#10）。
 */
export function MobileHome({ p, nav }: HomeProps) {
  const active = p.active!
  const cid = active.id
  const { summary, loading, error, reload } = useSummary(cid, p.refreshKey)
  const { removeInsight } = useInsightActions(cid, reload)

  const messages = p.messages[cid] ?? []
  const coachByDate = useMemo(() => lastCoachByDate(messages), [messages])
  const entries = summary?.entries ?? []
  const latest = entries[0]
  const prev = entries[1]
  /* 「最近一次記錄」唔一定係今日 —— `/summary` 係按日期 desc 排，用戶可能幾日冇打卡。
     以前呢頁唔理，照寫「今日膚況／今日指標／今日記低咗 N 個」，變成一句假話
     （2026-10-20）。而家：有今日 entry 就講今日，冇就照實講係邊一日。 */
  const isToday = latest != null && latest.date === todayYmd()
  const latestLabel = latest ? dayLabel(latest.date, true) : ''

  const today = useMemo(() => {
    const recorded = ATTRIBUTE_KEYS.filter((k) => severityOf(latest, k) != null)
    let improved = 0
    let worse = 0
    let same = 0
    for (const k of recorded) {
      const cur = severityOf(latest, k) as number
      const was = severityOf(prev, k)
      if (was == null || was === cur) same += 1
      else if (cur > was) worse += 1
      else improved += 1
    }
    return {
      recorded: recorded.length,
      improved,
      worse,
      same,
      compared: prev != null && recorded.length > 0,
    }
  }, [latest, prev])

  const heroSub = () => {
    if (loading) return '載入緊…'
    if (!latest || today.recorded === 0) return '未有指標。撳下面打卡／影相，agent 會寫低今日狀態。'
    // 日期已經喺 kicker 同 hero 標題出咗，呢句唔再重複（實測一屏三次）
    if (!isToday) return '撳下面打卡，記低今日嘅狀態。'
    if (!today.compared) return '第一次記錄，暫時未有得同上次比較。'
    return `${today.improved} 項改善 · ${today.worse} 項惡化 · ${today.same} 項持平`
  }

  return (
    <div className="mob-home">
      <section className="mob-hero">
        <div className="mob-hero-txt">
          <div className="k">{latest ? dayLabel(latest.date) : '今日'}</div>
          <div className="h1">{isToday ? '今日膚況' : latest ? '最近一次記錄' : '今日膚況'}</div>
          <p className="sub">{heroSub()}</p>
        </div>
        <div
          className="mob-ring"
          style={{ ['--v' as string]: (today.recorded / ATTRIBUTE_KEYS.length) * 100 }}
          title={`${isToday ? '今日' : latestLabel}記低咗 ${today.recorded}/${ATTRIBUTE_KEYS.length} 個指標`}
        >
          <span aria-label={`已記低 ${today.recorded} / ${ATTRIBUTE_KEYS.length} 項指標`}>
            {today.recorded}
            <small>/{ATTRIBUTE_KEYS.length}</small>
          </span>
          <span className="mob-ring-cap">項指標</span>
        </div>
      </section>

      <button className="mob-cta" onClick={() => nav.go('chat')}>
        <Icon name="camera" size={16} /> 今日打卡／問顧問
      </button>

      {error && (
          <p className="empty">
            <Icon name="circle-alert" size={16} /> {error}（請確認 backend 已起）
          </p>
        )}

      <section className="mob-card">
        <h2>{isToday ? '今日指標' : '最近一次指標'}</h2>
        {loading ? (
          <p className="empty small">載入中…</p>
        ) : today.recorded === 0 ? (
          <p className="empty small">未有指標。打卡／影張相，agent 會寫低皮膚狀態。</p>
        ) : (
          <>
            {/* 以前係 6 行 stack（每行 dots + 文字 + delta），喺手機首頁佔成半版。
                而家一條 chip row：一樣嘅數字，大概三分一高度。詳細版去「記錄」。 */}
            <div className="entry-metrics">
              {ATTRIBUTE_KEYS.map((key) => {
                const cur = severityOf(latest, key)
                if (cur == null) return null
                const was = severityOf(prev, key)
                const delta = was == null || was === cur ? '' : cur > was ? '↑' : '↓'
                return (
                  <span key={key} className={`chip attr${delta === '↑' ? ' bad' : delta === '↓' ? ' good' : ''}`}>
                    {ATTRIBUTE_META[key].zh} {cur}/3{delta && ` ${delta}`}
                  </span>
                )
              })}
            </div>
            {/* 日期只在 hero 出一次（以前同一日喺一屏出現 5 次） */}
          </>
        )}
      </section>

      <section className="mob-card">
        <h2>最近幾日</h2>
        {loading ? (
          <p className="empty small">載入中…</p>
        ) : entries.length === 0 ? (
          <p className="empty small">未有記錄。呢度會由你嘅真數據逐日砌出嚟。</p>
        ) : (
          entries.slice(0, 3).map((e) => {
            const reply = coachByDate.get(e.date)
            // 排序跟 ATTRIBUTE_KEYS：上面「最近一次指標」用同一個次序，兩個卡唔應該唔同
            const attrs = (e.attributes ?? [])
              .filter((a) => a.severity != null)
              .slice()
              .sort((a, b) => ATTRIBUTE_KEYS.indexOf(a.key) - ATTRIBUTE_KEYS.indexOf(b.key))
            return (
              <article className="entry-card" key={e.id}>
                <div className="entry-date">{dayLabel(e.date, true)}</div>
                <div className="entry-note">{e.note || '—'}</div>
                {attrs.length > 0 && (
                  <div className="entry-metrics">
                    {attrs.map((a) => (
                      <span key={a.key} className="chip attr">
                        {ATTRIBUTE_META[a.key]?.zh ?? a.key} {a.severity}/3
                      </span>
                    ))}
                  </div>
                )}
                {/* 手機首頁唔顯示相（2026-10-20 決定）：首頁要短，而且首頁一開就見，
                    自拍 grid 擺喺呢度太搶眼／太多。相繼續喺「記錄」scene 睇。 */}
                {reply && (
                  <div className="jm-reply">
                    <div className="k">顧問回覆</div>
                    {/* 只 clamp 文字段落（見 index.css 註解）：clamp 成個盒會同標籤重疊 */}
                    <p className="jm-reply-text">{reply.text}</p>
                  </div>
                )}
              </article>
            )
          })
        )}
        {!loading && entries.length > 3 && (
          <button className="btn ghost small" onClick={() => nav.go('records')}>
            睇晒全部 {entries.length} 日記錄 →
          </button>
        )}
      </section>

      <section className="mob-card">
        <h2>AI 記得你</h2>
        {loading ? (
          <p className="empty small">載入中…</p>
        ) : summary ? (
          <MemoryList items={summary.insights} onDelete={removeInsight} />
        ) : (
          <p className="empty small">連唔到 backend。</p>
        )}
      </section>

      <p className="hint">
        改筆記／刪相去「記錄」tab。呢度全部係真數據 —— 冇記錄就係空，唔會顯示假數。
      </p>
    </div>
  )
}
