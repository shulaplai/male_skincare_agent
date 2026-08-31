import type { MemoryItem, SkinScore, TimelineEvent } from '../types'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  pref: '偏好',
  fact: '事實',
}

function Sparkline({ series }: { series: number[] }) {
  const w = 260
  const h = 60
  const pts = series.map((v, i) => {
    const x = (i / (series.length - 1)) * w
    const y = 4 + (1 - v) * (h - 12)
    return [x, y] as const
  })
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')
  const area = `${line} L${w} ${h} L0 ${h} Z`
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" preserveAspectRatio="none">
      <line className="gridline" x1="0" y1="15" x2={w} y2="15" />
      <line className="gridline" x1="0" y1="42" x2={w} y2="42" />
      <path className="area" d={area} />
      <path className="line" d={line} />
    </svg>
  )
}

interface Props {
  score: SkinScore
  memories: MemoryItem[]
  timeline: TimelineEvent[]
  bodyPart: string
}

export function RightPanel({ score, memories, timeline, bodyPart }: Props) {
  return (
    <aside className="right">
      <div className="score">
        <div className="sh">
          <h3>{bodyPart}指數</h3>
          <span>SKIN SCORE</span>
        </div>
        <div className="row">
          <span className="big">
            {score.value}
            <small>/100</small>
          </span>
          <span className="delta">{score.delta}</span>
        </div>
        <Sparkline series={score.series} />
        <div className="sc-metrics">
          {score.metrics.map((m) => (
            <div className="m" key={m.key}>
              <div className="k">{m.key}</div>
              <div className={`v ${m.dir}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3>AI 記得你</h3>
        <div className="mem-group">
          {memories.map((m, i) => (
            <div className="mem" key={i}>
              <div className={`t ${m.kind}`}>{kindLabel[m.kind]}</div>
              <div className="txt">{m.text}</div>
              {m.confidence != null && (
                <>
                  <div className="conf">
                    <i style={{ width: `${m.confidence * 100}%` }} />
                  </div>
                  <div className="pct">confidence {m.confidence.toFixed(2)}</div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3>因果時間線</h3>
        <div className="tl">
          {timeline.map((e, i) => (
            <div className="ev" key={i}>
              <div className="d">{e.date}</div>
              <div className="x">{e.text}</div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
