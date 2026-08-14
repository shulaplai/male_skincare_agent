/* 每日 Check-in —— 護膚 + 飲食 + 相片 + 備註/疑惑 → 可問 AI */

import { useEffect, useMemo, useState } from 'react';
import { useDb, useSettings, getDb, mutateDb } from '../lib/store';
import { hasAi } from '../lib/storage';
import { runCheckin, applyInsights, saveEntry } from '../lib/services';
import { AiError } from '../lib/ai';
import { uid, type Entry, type SkincareStep } from '../lib/types';
import { todayLocal, formatYMD, weekday } from '../lib/date';
import { PhotoUpload } from '../components/PhotoUpload';
import { AiResponse } from '../components/AiResponse';
import { Banner, EmptyState, Field } from '../components/ui';

const STEP_OPTIONS = ['潔面', '爽膚水', '精華', '保濕', '防曬', '去角質', '面膜', '眼霜', '其他'];

export function CheckIn() {
  const db = useDb();
  const settings = useSettings();
  const aiOn = hasAi();

  const [date, setDate] = useState(todayLocal());
  const existing = db.entries.find((e) => e.date === date);

  /* 揀咗第二日 → 重新載入嗰日嘅 entry（state 唔可以淨係 mount 時初始化一次） */
  useEffect(() => {
    const target = db.entries.find((e) => e.date === date);
    setSteps(
      target?.skincare.length
        ? target.skincare
        : [{ id: uid(), step: '潔面', product: '' }],
    );
    setDiet(target?.diet ?? '');
    setPhoto(target?.photo);
    setNotes(target?.notes ?? '');
    setQuestion(target?.question ?? '');
    setAiText(target?.ai?.advice ?? '');
    setSaved(!!target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const [steps, setSteps] = useState<SkincareStep[]>(
    existing?.skincare.length
      ? existing.skincare
      : [{ id: uid(), step: '潔面', product: '' }],
  );
  const [diet, setDiet] = useState(existing?.diet ?? '');
  const [photo, setPhoto] = useState<string | undefined>(existing?.photo);
  const [notes, setNotes] = useState(existing?.notes ?? '');
  const [question, setQuestion] = useState(existing?.question ?? '');
  const [aiText, setAiText] = useState(existing?.ai?.advice ?? '');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(!!existing);

  const prevEntry = useMemo(() => {
    const prev = [...db.entries].filter((e) => e.date < date).sort((a, b) => b.date.localeCompare(a.date))[0];
    return prev;
  }, [db.entries, date]);

  if (!db.profile) {
    return <EmptyState title="未有檔案" hint="請先喺「今日」頁建立皮膚檔案。" />;
  }

  const patchStep = (id: string, p: Partial<SkincareStep>) =>
    setSteps((ss) => ss.map((s) => (s.id === id ? { ...s, ...p } : s)));

  const currentEntry = (): Entry => ({
    id: existing?.id ?? uid(),
    date,
    photo,
    skincare: steps,
    diet,
    notes,
    question: question.trim() || undefined,
    ai: existing?.ai,
    createdAt: existing?.createdAt ?? Date.now(),
    updatedAt: Date.now(),
  });

  const save = (): boolean => {
    const entry = currentEntry();
    try {
      mutateDb((d) => saveEntry(d, entry));
      setSaved(true);
      setError(null);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : '儲存失敗。');
      return false;
    }
  };

  const askAi = async () => {
    if (!aiOn) return;
    setError(null);
    // 先儲存紀錄（同「儲存後問 AI」嘅字面意思一致）；AI 失敗都唔會丟失紀錄
    if (!save()) return;
    setStreaming(true);
    let acc = '';
    try {
      const res = await runCheckin({
        settings,
        db: getDb(), // save 之後嘅最新 db，唔好用 render 時閉包嘅舊 db
        entry: currentEntry(),
        prevEntry,
        onChunk: (delta) => {
          acc += delta;
          setAiText(acc);
        },
      });
      // 存 AI 回應落 entry + 擷取到嘅 insights 寫入 memory
      const entry = currentEntry();
      mutateDb((d) => {
        const withAi = saveEntry(d, { ...entry, ai: res.advice });
        return applyInsights(withAi, res.insights, entry.id);
      });
    } catch (e) {
      if (e instanceof AiError && e.code === 'aborted') return;
      setError(e instanceof AiError ? e.message : 'AI 回應失敗，請再試。');
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="rise">
      <div className="page-head">
        <h1 className="page-title">每日 Check-in</h1>
        <div className="page-meta">LOG · 02</div>
      </div>

      {!aiOn ? (
        <Banner>AI 未設定：可以照做手動紀錄；設定 API key 之後每次 check-in 可以問 AI 回應。</Banner>
      ) : null}
      {error ? <Banner kind="err">{error}</Banner> : null}

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="kicker">Daily Log · {formatYMD(date)} {weekday(date)}</div>

          <Field label="日期">
            <input type="date" className="input" value={date} max={todayLocal()} onChange={(e) => setDate(e.target.value || todayLocal())} />
          </Field>

          <Field label="護膚做咗咩" hint="步驟＋用咗咩產品（唔記得可以淨係揀步驟）。">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {steps.map((s) => (
                <div key={s.id} style={{ display: 'flex', gap: 8 }}>
                  <select className="select" style={{ width: 130, flexShrink: 0 }} value={s.step} onChange={(e) => patchStep(s.id, { step: e.target.value })}>
                    {STEP_OPTIONS.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                  <input
                    className="input"
                    placeholder="產品／成分（例如：煙酰胺精華）"
                    value={s.product}
                    onChange={(e) => patchStep(s.id, { product: e.target.value })}
                  />
                  <button
                    type="button"
                    className="btn ghost sm"
                    onClick={() => setSteps((ss) => (ss.length > 1 ? ss.filter((x) => x.id !== s.id) : ss))}
                    aria-label="移除步驟"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button type="button" className="btn ghost sm" onClick={() => setSteps((ss) => [...ss, { id: uid(), step: '其他', product: '' }])}>
                + 加步驟
              </button>
            </div>
          </Field>

          <Field label="食咗咩">
            <textarea className="textarea" value={diet} onChange={(e) => setDiet(e.target.value)} placeholder="例如：雞胸沙律、糙米飯、飲咗 2L 水…" />
          </Field>

          <Field label="今日相片（可選）" hint="建議同一角度、同一光線，先可以同之前對比。">
            <PhotoUpload value={photo} onChange={setPhoto} label="上載今日相" />
          </Field>

          <Field label="備註／自己嘅觀察">
            <textarea className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="例如：今日 T 字位好似冇咁油…" />
          </Field>

          <Field label="新疑惑（可選）">
            <textarea className="textarea" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="例如：煙酰胺同水楊酸可唔可以同晚用？" />
          </Field>

          <div className="btn-row">
            <button className="btn" onClick={save}>{saved ? '更新紀錄' : '儲存紀錄'}</button>
            <button className="btn accent" onClick={() => void askAi()} disabled={streaming || !aiOn}>
              {streaming ? 'AI 回應中…' : '儲存後問 AI'}
            </button>
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            {prevEntry ? (
              <>上次紀錄：{formatYMD(prevEntry.date)}（{prevEntry.skincare.map((s) => s.step).join('、') || '冇護膚'}）</>
            ) : (
              '未有更早嘅紀錄'
            )}
          </div>
        </div>

        <div>
          <AiResponse
            text={aiText}
            streaming={streaming}
            model={aiText ? settings.textModel : undefined}
            error={null}
            onCancel={() => undefined}
          />
          {!aiText && !streaming ? (
            <div className="empty-state" style={{ marginTop: 14 }}>
              儲存紀錄之後撳「問 AI」，AI 會對比昨日、點評今日護膚同飲食、回應你嘅疑惑。
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
