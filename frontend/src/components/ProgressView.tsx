import { useEffect, useState } from 'react'
import * as api from '../api'
import { score } from '../data'
import type { Conversation, MemoryItem, TimelineEvent } from '../types'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  pref: '偏好',
  fact: '事實',
}

export function ProgressView({ conversation }: { conversation: Conversation }) {
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [memories, setMemories] = useState<MemoryItem[]>([])

  useEffect(() => {
    api
      .getSummary(conversation.id)
      .then((s) => {
        setTimeline(s.timeline)
        setMemories(s.insights)
      })
      .catch(() => {})
  }, [conversation.id])

  return (
    <main className="view full">
      <div className="view-head">
        <h2>進度追蹤 · {conversation.bodyPart}</h2>
      </div>

      <div className="score" style={{ maxWidth: 420 }}>
        <div className="sh">
          <h3>{conversation.bodyPart}指數</h3>
          <span>SKIN SCORE</span>
        </div>
        <div className="row">
          <span className="big">
            {score.value}
            <small>/100</small>
          </span>
          <span className="delta">{score.delta}</span>
        </div>
        <div className="sc-metrics">
          {score.metrics.map((m) => (
            <div className="m" key={m.key}>
              <div className="k">{m.key}</div>
              <div className={`v ${m.dir}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      <h3 className="block-title">AI 記得你</h3>
      {memories.length === 0 ? (
        <p className="empty">未有記憶。多打卡幾次，agent 會建立推導記憶。</p>
      ) : (
        <div className="mem-group" style={{ maxWidth: 560 }}>
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
      )}

      <h3 className="block-title">因果時間線</h3>
      {timeline.length === 0 ? (
        <p className="empty">未有時間線。</p>
      ) : (
        <div className="tl" style={{ maxWidth: 560 }}>
          {timeline.map((e, i) => (
            <div className="ev" key={i}>
              <div className="d">{e.date}</div>
              <div className="x">{e.text}</div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
