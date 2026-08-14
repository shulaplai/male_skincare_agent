/* 推導型記憶卡：confidence + expiry + 版本歷史（矛盾處理） */

import { useState } from 'react';
import type { DerivedInsight } from '../lib/types';
import { INSIGHT_KIND_LABEL } from '../lib/types';
import { formatTs } from '../lib/date';

export function InsightCard({
  insight,
  history,
}: {
  insight: DerivedInsight;
  history: DerivedInsight[];
}) {
  const [showHistory, setShowHistory] = useState(false);
  const superseded = history.filter((h) => h.id !== insight.id && (h.supersededBy || h.expired));

  return (
    <div className="card" style={{ padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--accent-text)' }}>
          {INSIGHT_KIND_LABEL[insight.kind]} · v{insight.version}
        </span>
        {insight.supersededBy ? <span className="stamp adjusted">已被覆蓋</span> : insight.expired ? <span className="stamp not-started">已過期</span> : null}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15 }}>{insight.label}</div>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>{insight.value}</div>

      <div style={{ marginTop: 9 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--muted)', marginBottom: 3 }}>
          <span>confidence {Math.round(insight.confidence * 100)}%</span>
          <span>{formatTs(insight.expiresAt)} 到期</span>
        </div>
        <div style={{ height: 4, background: 'var(--paper-3)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${Math.round(insight.confidence * 100)}%`, background: 'var(--accent)' }} />
        </div>
      </div>

      {superseded.length > 0 ? (
        <button type="button" className="btn ghost sm" style={{ marginTop: 9 }} onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? '收起歷史' : `睇歷史（${superseded.length}）`}
        </button>
      ) : null}
      {showHistory && superseded.length > 0 ? (
        <div style={{ marginTop: 8, borderTop: '1px dashed var(--line)', paddingTop: 8 }}>
          {superseded.map((h) => (
            <div key={h.id} className="mono" style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 4 }}>
              <span style={{ color: h.supersededBy ? 'var(--danger)' : 'var(--muted)' }}>v{h.version}</span>
              {' · '}
              {h.label}
              {' · '}
              {formatTs(h.createdAt)}
              {h.supersededBy ? ' → 被新結論覆蓋' : '（過期衰減）'}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
