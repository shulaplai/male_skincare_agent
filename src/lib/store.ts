/* React store —— useSyncExternalStore 訂閱 db / settings */

import { useSyncExternalStore } from 'react';
import type { AiSettings, Db } from './types';
import { loadDb, saveDb, loadSettings, saveSettings } from './storage';
import { expireDerived } from './memory';

let db: Db = expireDerived(loadDb());
let settings: AiSettings = loadSettings();

const dbListeners = new Set<() => void>();
const settingsListeners = new Set<() => void>();

export function getDb(): Db {
  return db;
}

export function setDb(next: Db): void {
  db = expireDerived(next); // 每次寫入順便標記過期 insight（衰減）
  saveDb(db);
  dbListeners.forEach((l) => l());
}

/** 以函數更新 db（例如 mutateDb(d => ({...d, profile}))）；儲存失敗會 throw */
export function mutateDb(fn: (d: Db) => Db): void {
  setDb(fn(db));
}

export function subscribeDb(cb: () => void): () => void {
  dbListeners.add(cb);
  return () => dbListeners.delete(cb);
}

export function useDb(): Db {
  return useSyncExternalStore(subscribeDb, getDb, getDb);
}

export function getSettings(): AiSettings {
  return settings;
}

export function setSettings(next: AiSettings): void {
  settings = next;
  saveSettings(next);
  settingsListeners.forEach((l) => l());
}

export function subscribeSettings(cb: () => void): () => void {
  settingsListeners.add(cb);
  return () => settingsListeners.delete(cb);
}

export function useSettings(): AiSettings {
  return useSyncExternalStore(subscribeSettings, getSettings, getSettings);
}
