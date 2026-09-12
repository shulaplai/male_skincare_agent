import { CorrelationList, LevelDots, MemoryList, Spark, TimelineList, attrSeries, severityOf } from '../components/blocks'
import { useCorrelations } from '../hooks/useCorrelations'
import { useInsightActions } from '../hooks/useInsightActions'
import { useSummary } from '../hooks/useSummary'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META, severityText } from '../format'
import type { AttributeAnchor, AnchorInfo } from '../types'
import type { HomeProps } from './defs'

function AnchorCell({ v, now }: { v: AnchorInfo | null; now: number }) {
  if (!v) return <span className="anchor-cell none">—</span>
  const cls = v.delta === 0 ? 'same' : v.delta > 0 ? 'bad' : 'good'
  const arrow = v.delta === 0 ? '→' : v.delta > 0 ? '↑' : '↓'
  return (
    <span className={`anchor-cell ${cls}`} title={`${v.date}：${v.old}/3 → ${now}/3`}>
      {arrow} {Math.abs(v.delta)}
    </span>
  )
}

/** 結構 3 home：進度儀表板 —— widgets 大廳，動作收喺頂部 CTA */
export function DashHome({ p, nav }: HomeProps) {
  const active = p.active!
  const cid = active.id
  const { summary, loading, reload } = useSummary(cid, p.refreshKey)
  const { corr, loading: corrLoading } = useCorrelations(cid, p.refreshKey)
  const { removeInsight } = useInsightActions(cid, reload)

  const entries = summary?.entries ?? []
  const latest = entries[0]
  const prev = entries[1]
  const anchors = summary?.anchors ?? []

  return (
    <div className="dash">
      <div className="dash-actions">
        <div className="dash-title">
          {active.icon} {active.bodyPart} · 今日狀態一覽
        </div>
        <div className="dash-btns">
          <button className="btn" onClick={() => nav.go('chat')}>
            ✍️ 今日打卡／問教練
          </button>
          <button className="btn ghost" onClick={() => nav.go('records')}>
            🗂 完整記錄
          </button>
          <button className="btn ghost" onClick={() => nav.go('progress')}>
            📈 進度詳細
          </button>
        </div>
      </div>

      <div className="dash-grid">
        <section className="dash-card today">
          <h3>今日皮膚狀態{latest ? ` · ${latest.date}` : ''}</h3>
          {loading ? (
            <p className="empty small">載入中…</p>
          ) : !latest || (latest.attributes ?? []).length === 0 ? (
            <p className="empty small">未有指標。撳「今日打卡」影張相／打個卡，agent 會寫低今日狀態。</p>
          ) : (
            <div className="attr-list">
              {ATTRIBUTE_KEYS.map((key) => {
                const cur = severityOf(latest, key)
                if (cur == null) return null
                const prevSev = severityOf(prev, key)
                const delta = prevSev == null || prevSev === cur ? '' : cur > prevSev ? '↑ 惡化' : '↓ 改善'
                return (
                  <div className="attr" key={key}>
                    <span className="k">{ATTRIBUTE_META[key].zh}</span>
                    <LevelDots severity={cur} />
                    <span className="sev">{severityText(cur)}</span>
                    <span className={`delta ${delta.includes('惡化') ? 'bad' : 'good'}`}>{delta}</span>
                  </div>
                )
              })}
              {latest.note && <p className="hint">{latest.note}</p>}
            </div>
          )}
        </section>

        <section className="dash-card trends">
          <h3>指標趨勢（0–3 級）</h3>
          {loading ? (
            <p className="empty small">載入中…</p>
          ) : entries.length === 0 ? (
            <p className="empty small">未有數據。打卡幾次之後趨勢會由真數據畫出嚟。</p>
          ) : (
            <div className="trends">
              {ATTRIBUTE_KEYS.map((key) => {
                const s = attrSeries(entries, key)
                if (s.sev.length < 2) return null
                return (
                  <div className="trend" key={key}>
                    <span className="k">{ATTRIBUTE_META[key].zh}</span>
                    <Spark series={s.sev} />
                    <span className="latest">{s.sev[s.sev.length - 1]}/3</span>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        <section className="dash-card anchors">
          <h3>同基準比較</h3>
          {loading ? (
            <p className="empty small">載入中…</p>
          ) : anchors.length === 0 ? (
            <p className="empty small">
              未有得比較。記錄夠 3 日以上，最新一日就會同上次／約 1 個月前／約 3 個月前比較（±7 日內最接近嗰日）。
            </p>
          ) : (
            <div className="anchor-table">
              <div className="anchor-row head">
                <span className="k">指標</span>
                <span className="now">最新</span>
                <span className="anchor-cell">vs 上次</span>
                <span className="anchor-cell">vs 1M</span>
                <span className="anchor-cell">vs 3M</span>
              </div>
              {anchors.map((a: AttributeAnchor) => (
                <div className="anchor-row" key={a.key}>
                  <span className="k">{a.label}</span>
                  <span className="now">{a.severity}/3</span>
                  <AnchorCell v={a.prev} now={a.severity} />
                  <AnchorCell v={a.month} now={a.severity} />
                  <AnchorCell v={a.quarter} now={a.severity} />
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="dash-card corr">
          <h3>相關性觀察（自動偵測 · 唔等於因果）</h3>
          <CorrelationList corr={corr} loading={corrLoading} />
        </section>

        <section className="dash-card mem">
          <h3>AI 記得你</h3>
          {summary ? (
            <MemoryList items={summary.insights} onDelete={removeInsight} />
          ) : (
            <p className="empty small">載入中…</p>
          )}
        </section>

        <section className="dash-card timeline">
          <h3>因果時間線</h3>
          {summary ? <TimelineList events={summary.timeline} /> : <p className="empty small">載入中…</p>}
        </section>
      </div>
    </div>
  )
}
