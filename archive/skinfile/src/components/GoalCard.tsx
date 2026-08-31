/* 目標卡：狀態印章 + 評分條 */

import type { Goal } from '../lib/types';
import { StatusStamp } from './ui';

export function GoalCard({ goal, score }: { goal: Goal; score?: number }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16.5, lineHeight: 1.25 }}>{goal.title}</div>
          {goal.detail ? <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>{goal.detail}</div> : null}
        </div>
        <StatusStamp status={goal.status} />
      </div>
      {score !== undefined ? (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.08em', color: 'var(--muted)', marginBottom: 4 }}>
            <span>AI 評分</span>
            <span>{score}/100</span>
          </div>
          <div style={{ height: 6, background: 'var(--paper-3)', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${score}%`,
                background: score >= 70 ? 'var(--accent)' : score >= 40 ? 'var(--amber)' : 'var(--danger)',
                transition: 'width .6s var(--ease)',
              }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
