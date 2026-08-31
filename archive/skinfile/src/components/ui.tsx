/* 共用 UI 小元件 */

import type { ReactNode } from 'react';
import type { GoalStatus } from '../lib/types';
import { GOAL_STATUS_LABEL } from '../lib/types';

export function Card({ children, className = '', dark }: { children: ReactNode; className?: string; dark?: boolean }) {
  return <div className={`card ${dark ? 'dark' : ''} ${className}`}>{children}</div>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint ? <div className="muted" style={{ fontSize: 12, marginTop: 5 }}>{hint}</div> : null}
    </div>
  );
}

export function Banner({ kind = 'warn', children }: { kind?: 'warn' | 'err' | 'ok'; children: ReactNode }) {
  const cls = kind === 'err' ? 'banner err' : kind === 'ok' ? 'banner ok' : 'banner';
  return <div className={cls}>{children}</div>;
}

export function EmptyState({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 17, marginBottom: 6 }}>{title}</div>
      {hint ? <div style={{ fontSize: 13 }}>{hint}</div> : null}
      {children ? <div style={{ marginTop: 14 }}>{children}</div> : null}
    </div>
  );
}

export function StatusStamp({ status }: { status: GoalStatus }) {
  return <span className={`stamp ${status}`}>{GOAL_STATUS_LABEL[status]}</span>;
}

export function SectionTitle({ num, children }: { num?: string; children: ReactNode }) {
  return (
    <h2 className="sec">
      {num ? <span className="sec-num">{num}</span> : null}
      {children}
    </h2>
  );
}
