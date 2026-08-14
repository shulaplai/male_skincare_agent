/* ============================================================
   Memory 系統
   - 事實型（facts）：check-in / 相片，永久
   - 推導型（derived）：AI 分析結論，帶 confidence + expiresAt
     · 結論一致 → 更新 confidence、延長 expiry、保留 version
     · 結論不一致 → 新 version 覆蓋（舊 insight 標 supersededBy，留歷史）→ 矛盾處理
     · 過期 → 標 expired → 衰減
   - 偏好型（preferences）：目標 / 喜好，穩定
   ============================================================ */

import type { Db, DerivedInsight, InsightDraft, InsightKind } from './types';
import { uid } from './types';

export const INSIGHT_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 日

export function isExpired(i: DerivedInsight, now = Date.now()): boolean {
  return i.expiresAt < now || i.expired === true;
}

/** 將過期 insight 標記 expired（衰減） */
export function expireDerived(db: Db, now = Date.now()): Db {
  let changed = false;
  const derived = db.memory.derived.map((i) => {
    if (!i.expired && i.expiresAt < now) {
      changed = true;
      return { ...i, expired: true };
    }
    return i;
  });
  return changed
    ? { ...db, memory: { ...db.memory, derived } }
    : db;
}

export function activeInsights(db: Db, now = Date.now()): DerivedInsight[] {
  return db.memory.derived.filter((i) => !isExpired(i, now) && !i.supersededBy);
}

/** 同一 kind 嘅歷史（含被覆蓋 / 過期），新→舊 */
export function insightHistory(db: Db, kind: InsightKind): DerivedInsight[] {
  return db.memory.derived
    .filter((i) => i.kind === kind)
    .sort((a, b) => b.createdAt - a.createdAt);
}

/**
 * 記錄一個推導型 insight。
 * - 冇 active 同 kind → 新增（version 1）
 * - 有 active 且 tag 相同（結論一致）→ 更新：confidence 提升、expiry 延長、保留 version、更新 value
 * - 有 active 且 tag 唔同（矛盾）→ 舊 insight 標 supersededBy，新增 version+1
 */
export function recordInsight(db: Db, draft: InsightDraft, sourceEntryId?: string, now = Date.now()): Db {
  const active = activeInsights(db, now).find((i) => i.kind === draft.kind);

  if (!active) {
    const insight: DerivedInsight = {
      id: uid(),
      kind: draft.kind,
      tag: draft.tag,
      label: draft.label,
      value: draft.value,
      confidence: clamp(draft.confidence),
      sourceEntryId,
      createdAt: now,
      expiresAt: now + INSIGHT_TTL_MS,
      version: 1,
    };
    return { ...db, memory: { ...db.memory, derived: [...db.memory.derived, insight] } };
  }

  if (active.tag === draft.tag) {
    // 結論一致 → 合併更新（confidence 向新高靠攏，但唔會超過 0.97）
    const merged: DerivedInsight = {
      ...active,
      label: draft.label || active.label,
      value: draft.value || active.value,
      confidence: clamp(Math.max(active.confidence, draft.confidence, active.confidence + 0.05)),
      sourceEntryId: sourceEntryId ?? active.sourceEntryId,
      createdAt: now,
      expiresAt: now + INSIGHT_TTL_MS,
    };
    const derived = db.memory.derived.map((i) => (i.id === active.id ? merged : i));
    return { ...db, memory: { ...db.memory, derived } };
  }

  // 結論不一致 → 矛盾處理：舊 insight 被覆蓋，留歷史
  const next: DerivedInsight = {
    id: uid(),
    kind: draft.kind,
    tag: draft.tag,
    label: draft.label,
    value: draft.value,
    confidence: clamp(draft.confidence),
    sourceEntryId,
    createdAt: now,
    expiresAt: now + INSIGHT_TTL_MS,
    version: active.version + 1,
  };
  const derived = db.memory.derived.map((i) => (i.id === active.id ? { ...i, supersededBy: next.id } : i));
  return { ...db, memory: { ...db.memory, derived: [...derived, next] } };
}

function clamp(n: number): number {
  if (!Number.isFinite(n)) return 0.5;
  return Math.min(0.97, Math.max(0.1, n));
}

/** 記錄多個 insight（每個獨立做 merge/supersede） */
export function recordInsights(db: Db, drafts: InsightDraft[], sourceEntryId?: string): Db {
  let next = db;
  for (const d of drafts) next = recordInsight(next, d, sourceEntryId);
  return next;
}

/* ---------- 偏好型 ---------- */

export function upsertPreference(db: Db, kind: 'goal' | 'preference' | 'aversion', text: string): Db {
  if (kind === 'goal') {
    // goal 由 profile.goals 管理，唔好重複寫入 memory
    return db;
  }
  const prefs = db.memory.preferences.filter((p) => !(p.kind === kind && p.text === text));
  return {
    ...db,
    memory: {
      ...db.memory,
      preferences: [...prefs, { id: uid(), kind, text, createdAt: Date.now() }],
    },
  };
}

/* ---------- context 構建（prefix caching 友善） ---------- */

/**
 * 將 memory 轉成畀 AI 嘅文字 context。
 * 順序固定：偏好（穩定）→ 推導（穩定，唔會逐次變）→ 事實摘要（最後，最易變）
 * —— stable prefix 前置，變動數據後置，方便 API 嘅 prefix caching。
 */
export function buildMemoryContext(db: Db, days = 14): string {
  const prefs = db.memory.preferences
    .map((p) => `- [${p.kind === 'preference' ? '偏好' : '迴避'}] ${p.text}`)
    .join('\n');

  const active = activeInsights(db);
  const derived = active
    .map((i) => `- ${i.label}（confidence ${Math.round(i.confidence * 100)}%，版本 v${i.version}，${formatExpiry(i.expiresAt)}到期）`)
    .join('\n');

  const recent = [...db.entries]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, days)
    .map((e) => {
      const steps = e.skincare.length
        ? e.skincare.map((s) => `${s.step}${s.product ? `（${s.product}）` : ''}`).join('、')
        : '冇紀錄';
      const diet = e.diet || '冇紀錄';
      const photo = e.photo ? '有相' : '冇相';
      return `- ${e.date}：護膚[${steps}]；飲食[${diet}]；${photo}${e.question ? `；疑惑「${e.question}」` : ''}`;
    })
    .join('\n');

  const lines: string[] = [];
  if (prefs) lines.push(`用戶偏好：\n${prefs}`);
  if (derived) lines.push(`目前推導結論（AI 分析，會過期）：\n${derived}`);
  lines.push(`最近 ${days} 日紀錄：\n${recent || '（未有紀錄）'}`);
  return lines.join('\n\n');
}

function formatExpiry(ts: number): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
