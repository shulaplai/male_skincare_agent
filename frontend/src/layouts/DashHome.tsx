import { CorrelationList, LevelDots, MemoryList, Spark, TimelineList, attrSeries, severityOf } from '../components/blocks'
import { useCorrelations } from '../hooks/useCorrelations'
import { useInsightActions } from '../hooks/useInsightActions'
import { useSummary } from '../hooks/useSummary'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META, severityText } from '../format'
import type { AttributeAnchor, AnchorInfo } from '../types'
import type { HomeProps } from './defs'
import { Icon } from '../components/Icon'
import { Skeleton } from '../components/ui/Skeleton'
import { EmptyState } from '../components/ui/EmptyState'

/* 一格 = 一個真正嘅 `<td>`：呢個比較表以前用 span 砌，報讀器見唔到行列關係。 */
function AnchorCell({ v, now }: { v: AnchorInfo | null; now: number }) {
  if (!v) return <td className="anchor-cell none">—</td>
  const cls = v.delta === 0 ? 'same' : v.delta > 0 ? 'bad' : 'good'
  const arrow = v.delta === 0 ? '→' : v.delta > 0 ? '↑' : '↓'
  return (
    <td className={`anchor-cell ${cls}`} title={`${v.date}：${v.old}/3 → ${now}/3`}>
      {arrow} {Math.abs(v.delta)}
    </td>
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
            <Icon name="camera" size={16} /> 今日打卡／問教練
          </button>
          <button className="btn ghost" onClick={() => nav.go('records')}>
            <Icon name="clipboard-list" size={16} /> 完整記錄
          </button>
          <button className="btn ghost" onClick={() => nav.go('progress')}>
            <Icon name="chart-column" size={16} /> 進度詳細
          </button>
        </div>
      </div>

      <div className="dash-grid">
        <section className="dash-card today">
          <h2>今日皮膚狀態{latest ? ` · ${latest.date}` : ''}</h2>
          {loading ? (
            <Skeleton lines={2} />
          ) : !latest || (latest.attributes ?? []).length === 0 ? (
            <EmptyState small icon="camera">未有指標。撳「今日打卡」影張相／打個卡，agent 會寫低今日狀態。</EmptyState>
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
          <h2>指標趨勢（0–3 級）</h2>
          {loading ? (
            <Skeleton lines={2} />
          ) : entries.length === 0 ? (
            <EmptyState small icon="chart-column">未有數據。打卡幾次之後趨勢會由真數據畫出嚟。</EmptyState>
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
          <h2>同基準比較</h2>
          {loading ? (
            <Skeleton lines={2} />
          ) : anchors.length === 0 ? (
            <p className="empty small">
              未有得比較。記錄夠 3 日以上，最新一日就會同上次／約 1 個月前／約 3 個月前比較（±7 日內最接近嗰日）。
            </p>
          ) : (
            <table className="anchor-table">
              <thead>
                <tr className="anchor-row head">
                  <th scope="col" className="k">指標</th>
                  <th scope="col" className="now">最新</th>
                  <th scope="col" className="anchor-cell">vs 上次</th>
                  <th scope="col" className="anchor-cell">vs 1M</th>
                  <th scope="col" className="anchor-cell">vs 3M</th>
                </tr>
              </thead>
              <tbody>
                {anchors.map((a: AttributeAnchor) => (
                  <tr className="anchor-row" key={a.key}>
                    <th scope="row" className="k">{a.label}</th>
                    <td className="now">{a.severity}/3</td>
                    <AnchorCell v={a.prev} now={a.severity} />
                    <AnchorCell v={a.month} now={a.severity} />
                    <AnchorCell v={a.quarter} now={a.severity} />
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="dash-card corr">
          <h2>相關性觀察（自動偵測 · 唔等於因果）</h2>
          <CorrelationList corr={corr} loading={corrLoading} />
        </section>

        <section className="dash-card mem">
          <h2>AI 記得你</h2>
          {summary ? (
            <MemoryList items={summary.insights} onDelete={removeInsight} />
          ) : (
            <Skeleton lines={2} />
          )}
        </section>

        <section className="dash-card timeline">
          <h2>因果時間線</h2>
          {summary ? <TimelineList events={summary.timeline} /> : <Skeleton lines={2} />}
        </section>
      </div>
    </div>
  )
}
