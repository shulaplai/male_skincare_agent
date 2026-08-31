/* 設定：AI 連線 + 資料管理 + Demo Mode */

import { useRef, useState } from 'react';
import { useDb, useSettings, setSettings, setDb } from '../lib/store';
import { PROVIDER_PRESETS, testConnection, AiError } from '../lib/ai';
import { exportData, importData, clearDb, dbStats } from '../lib/storage';
import { buildDemoDb } from '../lib/demoData';
import { Card, Field, Banner, SectionTitle } from '../components/ui';
import type { AiSettings } from '../lib/types';

export function Settings() {
  const db = useDb();
  const settings = useSettings();
  const fileRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [form, setForm] = useState<AiSettings>({ ...settings });

  const patch = (p: Partial<AiSettings>) => setForm((f) => ({ ...f, ...p }));

  const applyProvider = (id: string) => {
    const p = PROVIDER_PRESETS.find((x) => x.id === id);
    if (!p) return;
    patch({
      baseUrl: p.baseUrl,
      visionModel: p.visionModel,
      textModel: p.textModel,
      strongModel: p.strongModel,
      visionEnabled: !p.textOnly,
    });
  };

  const save = () => {
    setSettings({ ...form, baseUrl: form.baseUrl.trim().replace(/\/+$/, '') });
    setMsg({ kind: 'ok', text: '設定已儲存（只存喺呢個瀏覽器）。' });
  };

  const test = async () => {
    setTesting(true);
    setMsg(null);
    try {
      await testConnection({ ...form });
      setMsg({ kind: 'ok', text: '連線成功！API 回覆正常。' });
    } catch (e) {
      setMsg({ kind: 'err', text: e instanceof AiError ? e.message : '連線失敗。' });
    } finally {
      setTesting(false);
    }
  };

  const doExport = () => {
    const blob = new Blob([exportData(db, settings)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `skinfiles-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setMsg({ kind: 'ok', text: '已匯出 JSON 檔案。' });
  };

  const doImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      const json = await file.text();
      const { db: nextDb, settings: nextSettings } = importData(json);
      setDb(nextDb);
      setSettings(nextSettings);
      setForm({ ...nextSettings });
      setMsg({ kind: 'ok', text: '匯入成功！資料已載入。' });
    } catch (e) {
      setMsg({ kind: 'err', text: e instanceof Error ? e.message : '匯入失敗。' });
    }
  };

  const loadDemo = () => {
    try {
      setDb(buildDemoDb());
      setMsg({ kind: 'ok', text: '已載入示範資料（30 日紀錄 + 目標 + Memory）。去「進度檔案」睇效果！' });
    } catch (e) {
      setMsg({ kind: 'err', text: e instanceof Error ? e.message : '載入示範資料失敗。' });
    }
  };

  const removeDemo = () => {
    if (db.demo) {
      clearDb();
      setDb({ version: 1, profile: null, entries: [], memory: { facts: [], derived: [], preferences: [] } });
      setMsg({ kind: 'ok', text: '示範資料已移除。' });
    }
  };

  const doClear = () => {
    clearDb();
    setDb({ version: 1, profile: null, entries: [], memory: { facts: [], derived: [], preferences: [] } });
    setConfirmClear(false);
    setMsg({ kind: 'ok', text: '所有資料已清除。' });
  };

  const stats = dbStats(db);
  const preset = PROVIDER_PRESETS.find((p) => {
    if (p.id === 'custom') return form.baseUrl.trim() === '';
    const host = p.baseUrl.split('//')[1]?.split('/')[0] ?? '';
    return host && form.baseUrl.includes(host);
  });

  return (
    <div className="rise">
      <div className="page-head">
        <h1 className="page-title">設定</h1>
        <div className="page-meta">SETTINGS · 04</div>
      </div>

      {msg ? <Banner kind={msg.kind}>{msg.text}</Banner> : null}

      <SectionTitle num="A">AI 連線</SectionTitle>
      <Card>
        <div className="grid-2">
          <Field label="Provider 預設">
            <select
              className="select"
              value={preset?.id ?? 'custom'}
              onChange={(e) => applyProvider(e.target.value)}
            >
              {PROVIDER_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.hk ? '（香港直連）' : ''}
                </option>
              ))}
            </select>
            {preset?.note ? (
              <div style={{ fontSize: 12, marginTop: 6, color: preset.hk ? 'var(--accent-text)' : 'var(--amber-text)', background: preset.hk ? 'var(--accent-soft)' : 'var(--amber-soft)', padding: '6px 10px', borderRadius: 4 }}>
                {preset.note}
              </div>
            ) : null}
          </Field>
          <Field label="Base URL（OpenAI-compatible）">
            <input className="input" value={form.baseUrl} onChange={(e) => patch({ baseUrl: e.target.value })} placeholder="https://api.openai.com/v1" />
          </Field>
        </div>

        <Field label="API Key" hint="只存喺呢個瀏覽器嘅 localStorage，唔會上傳去任何 server。">
          <input
            className="input"
            type="password"
            value={form.apiKey}
            onChange={(e) => patch({ apiKey: e.target.value })}
            placeholder="sk-…"
            autoComplete="off"
          />
        </Field>

        <div className="grid-3">
          <Field label="諮詢用（強 model）" hint="分析相片＋詳細建議">
            <input className="input" value={form.strongModel} onChange={(e) => patch({ strongModel: e.target.value })} />
          </Field>
          <Field label="Check-in／進度（平快 model）">
            <input className="input" value={form.textModel} onChange={(e) => patch({ textModel: e.target.value })} />
          </Field>
          <Field label="視覺分析 model" hint="唔支援相就自動降級純文字">
            <input className="input" value={form.visionModel} onChange={(e) => patch({ visionModel: e.target.value })} />
          </Field>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
          <input type="checkbox" checked={form.visionEnabled} onChange={(e) => patch({ visionEnabled: e.target.checked })} />
          <span style={{ fontSize: 14 }}>AI 睇相分析（模型唔支援時會自動改用純文字）</span>
        </label>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <button className="btn" onClick={save}>儲存設定</button>
          <button className="btn ghost" onClick={() => void test()} disabled={testing || !form.apiKey}>
            {testing ? '測試中…' : '測試連線'}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
          模型分級：諮詢用強 model 詳細分析；Check-in 回應、進度評估、Memory 擷取用平快 model 慳成本。
        </div>
      </Card>

      <SectionTitle num="B">Demo Mode</SectionTitle>
      <Card>
        <p className="muted" style={{ marginTop: 0, fontSize: 13.5 }}>
          一鍵載入 30 日合成示範資料（目標＋紀錄＋Memory＋模擬相片），即刻體驗完整流程，唔使慢慢 onboarding。
        </p>
        <div className="btn-row">
          <button className="btn accent" onClick={loadDemo} disabled={db.demo}>載入示範資料</button>
          {db.demo ? <button className="btn ghost" onClick={removeDemo}>移除示範資料</button> : null}
        </div>
      </Card>

      <SectionTitle num="C">資料管理</SectionTitle>
      <Card>
        <div className="mono" style={{ fontSize: 12, marginBottom: 14, color: 'var(--muted)' }}>
          紀錄 {stats.entries} 條 · 相片 {stats.photos} 張 · Memory 推導 {stats.derived} 條 · 約 {(stats.bytes / 1024).toFixed(0)} KB
        </div>
        <div className="btn-row">
          <button className="btn ghost" onClick={doExport}>匯出 JSON</button>
          <button className="btn ghost" onClick={() => fileRef.current?.click()}>匯入 JSON</button>
          {confirmClear ? (
            <>
              <span className="mono" style={{ fontSize: 12, color: 'var(--danger)' }}>確定清除所有資料？</span>
              <button className="btn danger sm" onClick={doClear}>確認清除</button>
              <button className="btn ghost sm" onClick={() => setConfirmClear(false)}>取消</button>
            </>
          ) : (
            <button className="btn danger" onClick={() => setConfirmClear(true)}>清除所有資料</button>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/json"
          hidden
          onChange={(e) => {
            void doImport(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
      </Card>
    </div>
  );
}
