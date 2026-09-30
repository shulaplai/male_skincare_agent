import { useMemo } from 'react'
import { LevelDots, MemoryList } from '../components/blocks'
import { useInsightActions } from '../hooks/useInsightActions'
import { useSummary } from '../hooks/useSummary'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META, severityText } from '../format'
import type { Message, RecordEntry } from '../types'
import type { HomeProps } from './defs'

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
  if (diff <= 0) return `今天 · 星期${wd}`
  if (diff === 1) return `昨天 · 星期${wd}`
  return `${date} · 星期${wd}`
}

const severityOf = (e: RecordEntry | undefined, key: string): number | null =>
  e ? (e.attributes ?? []).find((a) => a.key === key)?.severity ?? null : null

/** 每條 entry 當日最後一條教練回覆（用 App 已載入嘅 messages，唔另 fetch） */
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
    if (!latest || today.recorded === 0) return '今日未有指標。撳下面打卡／影相，agent 會寫低今日狀態。'
    if (!today.compared) return '第一次記錄，暫時未有得同上次比較。'
    return `${today.improved} 項改善 · ${today.worse} 項惡化 · ${today.same} 項持平`
  }

  return (
    <div className="mob-home">
      <section className="mob-hero">
        <div className="mob-hero-txt">
          <div className="k">{latest ? dayLabel(latest.date) : '今日'}</div>
          <div className="h1">今日膚況</div>
          <p className="sub">{heroSub()}</p>
        </div>
        <div
          className="mob-ring"
          style={{ ['--v' as string]: (today.recorded / ATTRIBUTE_KEYS.length) * 100 }}
          title={`今日記低咗 ${today.recorded}/${ATTRIBUTE_KEYS.length} 個指標`}
        >
          <span>
            {today.recorded}
            <small>/{ATTRIBUTE_KEYS.length}</small>
          </span>
        </div>
      </section>

      <button className="mob-cta" onClick={() => nav.go('chat')}>
        ✍️ 今日打卡／問教練
      </button>

      {error && <p className="empty">⚠️ {error}（請確認 backend 已起）</p>}

      <section className="mob-card">
        <h3>今日指標</h3>
        {loading ? (
          <p className="empty small">載入中…</p>
        ) : today.recorded === 0 ? (
          <p className="empty small">未有指標。打卡／影張相，agent 會寫低今日嘅皮膚狀態。</p>
        ) : (
          <div className="attr-list">
            {ATTRIBUTE_KEYS.map((key) => {
              const cur = severityOf(latest, key)
              if (cur == null) return null
              const was = severityOf(prev, key)
              const delta = was == null || was === cur ? '' : cur > was ? '↑ 惡化' : '↓ 改善'
              return (
                <div className="attr" key={key}>
                  <span className="k">{ATTRIBUTE_META[key].zh}</span>
                  <LevelDots severity={cur} />
                  <span className="sev">{severityText(cur)}</span>
                  {delta && <span className={`delta ${delta.includes('惡化') ? 'bad' : 'good'}`}>{delta}</span>}
                </div>
              )
            })}
          </div>
        )}
      </section>

      <section className="mob-card">
        <h3>最近幾日</h3>
        {loading ? (
          <p className="empty small">載入中…</p>
        ) : entries.length === 0 ? (
          <p className="empty small">未有記錄。呢度會由你嘅真數據逐日砌出嚟。</p>
        ) : (
          entries.slice(0, 3).map((e) => {
            const reply = coachByDate.get(e.date)
            const attrs = (e.attributes ?? []).filter((a) => a.severity != null)
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
                {e.photos?.length > 0 && (
                  <div className="jm-photos">
                    {e.photos.map((ph) => {
                      const id = ph.split('/').pop()?.replace('.jpg', '')
                      return (
                        <span className="photo-cell" key={ph}>
                          <a href={`/api/photos/${id}`} target="_blank" rel="noreferrer">
                            <img src={`/api/photos/${id}`} alt="" />
                          </a>
                        </span>
                      )
                    })}
                  </div>
                )}
                {reply && (
                  <div className="jm-reply">
                    <div className="k">教練回覆 · Agent</div>
                    {reply.text}
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
        <h3>AI 記得你</h3>
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
