/* 相片時間線 —— 證據檔案風格 */

import { useState } from 'react';
import type { Entry } from '../lib/types';
import { formatYMD, weekday, shortYMD } from '../lib/date';

export function Timeline({ entries }: { entries: Entry[] }) {
  const sorted = [...entries].sort((a, b) => b.date.localeCompare(a.date));
  const [open, setOpen] = useState<string | null>(null);

  if (!sorted.length) {
    return <div className="empty-state">未有紀錄 —— 由今日開始第一個 check-in。</div>;
  }

  return (
    <div style={{ position: 'relative', paddingLeft: 26 }}>
      {/* 垂直線 */}
      <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 1, background: 'var(--line-strong)' }} />

      {sorted.map((e, idx) => {
        const isOpen = open === e.id;
        return (
          <div key={e.id} style={{ position: 'relative', marginBottom: 14 }}>
            {/* 節點 */}
            <div
              style={{
                position: 'absolute',
                left: -26,
                top: 14,
                width: 9,
                height: 9,
                borderRadius: '50%',
                background: e.photo ? 'var(--accent)' : 'var(--paper-3)',
                border: '2px solid var(--paper)',
                boxShadow: '0 0 0 1px var(--line-strong)',
              }}
            />
            <div
              className="card"
              style={{ padding: 14, cursor: 'pointer', transition: 'box-shadow .2s var(--ease)' }}
              onClick={() => setOpen(isOpen ? null : e.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') {
                  ev.preventDefault();
                  setOpen(isOpen ? null : e.id);
                }
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  <span className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{formatYMD(e.date)}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>{weekday(e.date)} · #{sorted.length - idx}</span>
                </div>
                <span className="mono" style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '.08em' }}>
                  {isOpen ? '▲ 收起' : '▼ 展開'}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 14, marginTop: 10, alignItems: 'flex-start' }}>
                {e.photo ? (
                  <div className="photo-frame" style={{ width: 64, height: 64, flexShrink: 0 }}>
                    <img src={e.photo} alt={`${e.date} 相片`} loading="lazy" />
                  </div>
                ) : (
                  <div className="photo-frame" style={{ width: 64, height: 64, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
                    🧴
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {e.skincare.length ? (
                    <div style={{ marginBottom: 4 }}>
                      {e.skincare.slice(0, 3).map((s) => (
                        <span key={s.id} className="mono" style={{ fontSize: 11, background: 'var(--accent-soft)', color: 'var(--accent-text)', padding: '2px 7px', borderRadius: 10, marginRight: 6, whiteSpace: 'nowrap' }}>
                          {s.step}{s.product ? `·${s.product}` : ''}
                        </span>
                      ))}
                      {e.skincare.length > 3 ? <span className="mono muted" style={{ fontSize: 11 }}>+{e.skincare.length - 3}</span> : null}
                    </div>
                  ) : (
                    <div className="muted" style={{ fontSize: 12.5 }}>冇護膚紀錄</div>
                  )}
                  <div className="muted" style={{ fontSize: 12.5 }}>{e.diet || '飲食：冇紀錄'}</div>
                  {e.notes ? <div style={{ fontSize: 12.5, marginTop: 3 }}>📝 {e.notes}</div> : null}
                  {e.ai ? <div className="mono" style={{ fontSize: 10.5, color: 'var(--accent-text)', marginTop: 3 }}>AI 已回應（{e.ai.model}）</div> : null}
                </div>
              </div>

              {isOpen ? (
                <div style={{ marginTop: 12, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
                  {e.skincare.length ? (
                    <div style={{ marginBottom: 8 }}>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: '.12em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4 }}>護膚步驟</div>
                      {e.skincare.map((s) => (
                        <div key={s.id} style={{ fontSize: 13, marginBottom: 2 }}>
                          <span className="mono" style={{ color: 'var(--accent-text)', marginRight: 8 }}>{s.step}</span>
                          {s.product}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {e.question ? (
                    <div style={{ marginBottom: 8 }}>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: '.12em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4 }}>疑惑</div>
                      <div style={{ fontSize: 13 }}>{e.question}</div>
                    </div>
                  ) : null}
                  {e.ai?.analysis ? (
                    <div>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: '.12em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4 }}>AI 睇相分析</div>
                      <div style={{ fontSize: 13 }}>{e.ai.analysis}</div>
                    </div>
                  ) : null}
                  {e.ai?.advice ? (
                    <div>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: '.12em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4 }}>AI 建議</div>
                      <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{e.ai.advice}</div>
                    </div>
                  ) : null}
                  <div className="mono" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 8 }}>
                    記錄 ID {shortYMD(e.date)}-{e.id.slice(0, 4)}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
