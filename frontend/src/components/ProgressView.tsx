import { useEffect, useState } from 'react'
import * as api from '../api'
import { ATTRIBUTE_KEYS, ATTRIBUTE_META } from '../format'
import type { Conversation, MemoryItem, RecordEntry, Summary } from '../types'

const kindLabel: Record<MemoryItem['kind'], string> = {
  derived: '推導記憶',
  preference: '偏好',
  fact: '事實',
}

function attrSeries(entries: RecordEntry[], key: string): { dates: string[]; sev: number[] } {
  const dates: string[] = []
  const sev: number[] = []
  for (const e of [...entries].reverse()) {
    const a = (e.attributes ?? []).find((x) => x.key === key)
    if (a && a.severity != null) {
      dates.push(e.date)
      sev.push(a.severity)
    }
  }
  return { dates, sev }
}

export function ProgressView({ conversation }: { conversation: Conversation }) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    api
      .getSummary(conversation.id)
      .then((s) => alive && setSummary(s))
      .catch(() => alive && setSummary(null))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [conversation.id])

  const entries = summary?.entries ?? []

  return (
    <main className="view full">
      <div className="view-head">
        <h2>進度追蹤 · {conversation.bodyPart}</h2>
      </div>

      <h3 className="block-title">皮膚指標趨勢（真實數據 · 0–3 級）</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : entries.length === 0 ? (
        <p className="empty">未有數據。去「教練對話」影相／打卡，趨勢會由你嘅真實紀錄畫出嚟。</p>
      ) : (
        <div className="attr-list" style={{ maxWidth: 640 }}>
          {ATTRIBUTE_KEYS.map((key) => {
            const s = attrSeries(entries, key)
            if (s.sev.length === 0) return null
            const first = s.sev[0]
            const last = s.sev[s.sev.length - 1]
            const delta = last - first
            const trend = delta === 0 ? '持平' : delta < 0 ? `↓ 改善 ${-delta} 級` : `↑ 惡化 ${delta} 級`
            return (
              <div className="trend" key={key}>
                <span className="k">{ATTRIBUTE_META[key].zh}</span>
                <span className="date-range">{s.dates[0]} → {s.dates[s.dates.length - 1]}</span>
                <span className={`delta ${delta > 0 ? 'bad' : delta < 0 ? 'good' : ''}`}>{trend}</span>
              </div>
            )
          })}
        </div>
      )}

      <h3 className="block-title">AI 記得你</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : !summary || summary.insights.length === 0 ? (
        <p className="empty">未有記憶。多打卡幾次，agent 會建立推導記憶。</p>
      ) : (
        <div className="mem-group" style={{ maxWidth: 560 }}>
          {summary.insights.map((m, i) => (
            <div className="mem" key={i}>
              <div className={`t ${m.kind}`}>{kindLabel[m.kind] ?? m.kind}</div>
              <div className="txt">{m.text}</div>
              {m.confidence != null && (
                <>
                  <div className="conf">
                    <i style={{ width: `${Math.round(m.confidence * 100)}%` }} />
                  </div>
                  <div className="pct">confidence {m.confidence.toFixed(2)}</div>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <h3 className="block-title">因果時間線</h3>
      {loading ? (
        <p className="empty">載入中…</p>
      ) : !summary || summary.timeline.length === 0 ? (
        <p className="empty">未有時間線。</p>
      ) : (
        <div className="tl" style={{ maxWidth: 560 }}>
          {summary.timeline.map((e, i) => (
            <div className="ev" key={i}>
              <div className="d">
                {e.date}
                <span className={`src ${e.source ?? 'user'}`}>{e.source === 'agent' ? 'AI 偵測' : '你'}</span>
              </div>
              <div className="x">{e.text}</div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
