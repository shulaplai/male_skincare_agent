/* ============================================================
   SKINFILE — 核心資料型別
   ============================================================ */

export type GoalStatus = 'not-started' | 'in-progress' | 'achieved' | 'adjusted';

export interface Goal {
  id: string;
  title: string;
  detail?: string;
  status: GoalStatus;
  createdAt: number;
}

export interface SkincareStep {
  id: string;
  step: string;   // 例如「潔面」「保濕」「防曬」
  product: string; // 例如「胺基酸洗面奶」
}

export interface AiAdvice {
  analysis?: string; // 睇相分析（純文字模式時無）
  advice: string;    // 主建議（markdown）
  model: string;
  vision: boolean;
  ts: number;
}

export interface Entry {
  id: string;
  date: string; // YYYY-MM-DD（本地）
  photo?: string; // 壓縮後 dataURL
  skincare: SkincareStep[];
  diet: string;   // 食咗咩
  notes: string;  // 備註 / 自己嘅建議
  question?: string; // 新疑惑
  ai?: AiAdvice;
  createdAt: number;
  updatedAt: number;
}

/* ---------- Memory ---------- */

export type InsightKind =
  | 'skin-type'
  | 'oiliness'
  | 'acne'
  | 'sensitivity'
  | 'hydration'
  | 'texture'
  | 'pores'
  | 'pigmentation'
  | 'general';

export interface DerivedInsight {
  id: string;
  kind: InsightKind;
  tag: string;        // 粗分類值，例如 'oily' | 'normal' | 'dry'；用於「結論一致/不一致」比較
  label: string;      // 短標題：例如「皮膚偏油」
  value: string;      // 詳細文字
  confidence: number; // 0..1
  sourceEntryId?: string;
  createdAt: number;
  expiresAt: number;
  version: number;
  supersededBy?: string; // 被邊個新結論取代（矛盾處理，留歷史）
  expired?: boolean;
}

export interface Preference {
  id: string;
  kind: 'goal' | 'preference' | 'aversion';
  text: string;
  createdAt: number;
}

export interface Memory {
  facts: string[]; // entry ids（事實型索引）
  derived: DerivedInsight[];
  preferences: Preference[];
}

/* ---------- 進度評估 ---------- */

export interface GoalAssessment {
  goalId: string;
  title: string;
  status: GoalStatus;
  score: number; // 0..100
  reason: string;
}

export interface Assessment {
  ts: number;
  model: string;
  overall: string;
  goals: GoalAssessment[];
}

/* ---------- 設定 ---------- */

export interface AiSettings {
  baseUrl: string;
  apiKey: string;
  visionModel: string;  // 平快 model：check-in / 進度 / 擷取
  textModel: string;
  strongModel: string;  // 強 model：諮詢
  visionEnabled: boolean;
}

export interface Db {
  version: 1;
  demo?: boolean;
  profile: Profile | null;
  entries: Entry[];
  memory: Memory;
  assessment?: Assessment;
}

export interface Profile {
  id: string;
  name: string;
  skinType?: string;
  baselinePhoto?: string;
  concerns: string;   // 疑惑 / 想改善嘅問題
  goals: Goal[];
  createdAt: number;
}

/* ---------- AI 擷取（draft） ---------- */

export interface InsightDraft {
  kind: InsightKind;
  tag: string;
  label: string;
  value: string;
  confidence: number;
}

export function uid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export const GOAL_STATUS_LABEL: Record<GoalStatus, string> = {
  'not-started': '未開始',
  'in-progress': '進展中',
  achieved: '已達成',
  adjusted: '需調整',
};

export const INSIGHT_KIND_LABEL: Record<InsightKind, string> = {
  'skin-type': '膚質',
  oiliness: '油脂',
  acne: '暗瘡',
  sensitivity: '敏感',
  hydration: '保濕',
  texture: '質感',
  pores: '毛孔',
  pigmentation: '色素／印',
  general: '綜合',
};
