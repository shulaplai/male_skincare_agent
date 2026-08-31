/* ============================================================
   SKINFILE — 持久化層（localStorage，versioned schema）
   module-level 快取：避免每次 render 都讀 localStorage
   ============================================================ */

import type { AiSettings, Db, Profile, Entry, Memory } from './types';

const DB_KEY = 'skinfiledb:v1';
const SETTINGS_KEY = 'skinfiledb:settings:v1';

export class StorageError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StorageError';
  }
}

const emptyDb = (): Db => ({
  version: 1,
  profile: null,
  entries: [],
  memory: { facts: [], derived: [], preferences: [] },
});

let cache: Db | null = null;

function normalize(raw: unknown): Db {
  const r = (raw ?? {}) as Partial<Db>;
  const mem = (r.memory ?? {}) as Partial<Memory>;
  return {
    version: 1,
    demo: !!r.demo,
    profile: r.profile ?? null,
    entries: Array.isArray(r.entries) ? r.entries : [],
    assessment: r.assessment,
    memory: {
      facts: Array.isArray(mem.facts) ? mem.facts : [],
      derived: Array.isArray(mem.derived) ? mem.derived : [],
      preferences: Array.isArray(mem.preferences) ? mem.preferences : [],
    },
  };
}

export function loadDb(): Db {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(DB_KEY);
    if (!raw) {
      cache = emptyDb();
      return cache;
    }
    const parsed = JSON.parse(raw) as Db;
    if (parsed.version !== 1) throw new Error(`unsupported version ${parsed.version}`);
    cache = normalize(parsed);
  } catch {
    cache = emptyDb();
  }
  return cache;
}

export function saveDb(db: Db): void {
  // 先寫 localStorage 成功先更新 cache，避免 quota 爆時 cache 同實際儲存唔一致
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  } catch (e) {
    if (e instanceof DOMException && (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED')) {
      throw new StorageError('儲存空間已滿：相片可能太多。請喺「設定」匯出資料後清除，或減少相片上載。');
    }
    throw e;
  }
  cache = db;
}

export function resetCache(): void {
  cache = null;
}

export function clearDb(): void {
  localStorage.removeItem(DB_KEY);
  cache = emptyDb();
}

export function setProfile(db: Db, profile: Profile): Db {
  return { ...db, profile };
}

/* ---------- 匯出 / 匯入 ---------- */

export function exportData(db: Db, settings: AiSettings): string {
  return JSON.stringify({ exportedAt: new Date().toISOString(), db, settings }, null, 2);
}

export function importData(json: string): { db: Db; settings: AiSettings } {
  let parsed: { db?: unknown; settings?: unknown };
  try {
    parsed = JSON.parse(json);
  } catch {
    throw new StorageError('匯入失敗：唔係有效 JSON。');
  }
  if (!parsed || typeof parsed !== 'object') throw new StorageError('匯入失敗：格式唔啱。');
  const db = normalize(parsed.db);
  if (!db.profile && db.entries.length === 0) {
    throw new StorageError('匯入失敗：檔案入面搵唔到資料。');
  }
  return { db, settings: mergeSettings(parsed.settings) };
}

/* ---------- 設定 ---------- */

export const DEFAULT_SETTINGS: AiSettings = {
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  visionModel: 'gpt-4o-mini',
  textModel: 'gpt-4o-mini',
  strongModel: 'gpt-4o',
  visionEnabled: true,
};

let settingsCache: AiSettings | null = null;

export function mergeSettings(raw: unknown): AiSettings {
  const r = (raw ?? {}) as Partial<AiSettings>;
  return {
    baseUrl: typeof r.baseUrl === 'string' && r.baseUrl ? r.baseUrl : DEFAULT_SETTINGS.baseUrl,
    apiKey: typeof r.apiKey === 'string' ? r.apiKey : '',
    visionModel: typeof r.visionModel === 'string' && r.visionModel ? r.visionModel : DEFAULT_SETTINGS.visionModel,
    textModel: typeof r.textModel === 'string' && r.textModel ? r.textModel : DEFAULT_SETTINGS.textModel,
    strongModel: typeof r.strongModel === 'string' && r.strongModel ? r.strongModel : DEFAULT_SETTINGS.strongModel,
    visionEnabled: typeof r.visionEnabled === 'boolean' ? r.visionEnabled : true,
  };
}

export function loadSettings(): AiSettings {
  if (settingsCache) return settingsCache;
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    settingsCache = raw ? mergeSettings(JSON.parse(raw)) : { ...DEFAULT_SETTINGS };
  } catch {
    settingsCache = { ...DEFAULT_SETTINGS };
  }
  return settingsCache;
}

export function saveSettings(s: AiSettings): void {
  settingsCache = s;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

export function hasAi(): boolean {
  const s = loadSettings();
  return !!(s.apiKey && s.baseUrl);
}

/* ---------- 統計 ---------- */

export function dbStats(db: Db): { bytes: number; entries: number; photos: number; derived: number } {
  const bytes = JSON.stringify(db).length;
  const photos = db.entries.filter((e) => e.photo).length + (db.profile?.baselinePhoto ? 1 : 0);
  return {
    bytes,
    entries: db.entries.length,
    photos,
    derived: db.memory.derived.length,
  };
}

export { emptyDb };
export type { Entry };
