/* Before / After 對比滑桿 */

import { useState } from 'react';

export function PhotoCompare({
  before,
  after,
  beforeLabel = '之前',
  afterLabel = '之後',
}: {
  before?: string;
  after?: string;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  const [pos, setPos] = useState(50);

  if (!before || !after) {
    return (
      <div className="empty-state">
        需要兩張相（例如 baseline 同最近一張）先可以對比。
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <div
        className="photo-frame"
        style={{ aspectRatio: '1/1', cursor: 'ew-resize', touchAction: 'none' }}
        onPointerDown={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setPos(Math.round(((e.clientX - rect.left) / rect.width) * 100));
          const move = (ev: PointerEvent) => {
            const r = e.currentTarget.getBoundingClientRect();
            setPos(Math.max(0, Math.min(100, Math.round(((ev.clientX - r.left) / r.width) * 100))));
          };
          const up = () => {
            window.removeEventListener('pointermove', move);
            window.removeEventListener('pointerup', up);
          };
          window.addEventListener('pointermove', move);
          window.addEventListener('pointerup', up);
        }}
      >
        {/* 之後（底層） */}
        <img src={after} alt={afterLabel} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
        {/* 之前（上層，裁剪） */}
        <img
          src={before}
          alt={beforeLabel}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            clipPath: `inset(0 ${100 - pos}% 0 0)`,
          }}
        />
        {/* 分隔線 */}
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${pos}%`, width: 2, background: 'var(--paper)', boxShadow: '0 0 8px rgba(0,0,0,.5)', transform: 'translateX(-1px)' }} />
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: `${pos}%`,
            transform: 'translate(-50%, -50%)',
            width: 34,
            height: 34,
            borderRadius: '50%',
            background: 'var(--paper)',
            border: '2px solid var(--ink)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
            color: 'var(--ink)',
            boxShadow: 'var(--shadow-2)',
            pointerEvents: 'none',
          }}
        >
          ⇄
        </div>
        {/* 標籤 */}
        <span style={{ position: 'absolute', top: 10, left: 10, fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.12em', background: 'rgba(20,24,28,.72)', color: 'var(--paper)', padding: '3px 8px', borderRadius: 2 }}>
          {beforeLabel}
        </span>
        <span style={{ position: 'absolute', top: 10, right: 10, fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.12em', background: 'rgba(20,24,28,.72)', color: 'var(--paper)', padding: '3px 8px', borderRadius: 2 }}>
          {afterLabel}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 10, textAlign: 'center', marginTop: 6, color: 'var(--muted)', letterSpacing: '.1em' }}>
        拖曳分隔線對比
      </div>
    </div>
  );
}
