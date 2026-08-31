/* AI 諮詢 —— 睇相 + 目標 + 疑惑 → 串流建議 */

import { useEffect, useRef, useState } from 'react';
import { useDb, useSettings, mutateDb } from '../lib/store';
import { hasAi } from '../lib/storage';
import { runConsult, extractInsights, applyInsights } from '../lib/services';
import { AiError } from '../lib/ai';
import { AiResponse } from '../components/AiResponse';
import { Banner, EmptyState, Field } from '../components/ui';

export function Consult() {
  const db = useDb();
  const settings = useSettings();
  const aiOn = hasAi();

  const latestPhoto =
    db.profile?.baselinePhoto ??
    [...db.entries].sort((a, b) => b.date.localeCompare(a.date))[0]?.photo;

  const [photo, setPhoto] = useState<string | undefined>(latestPhoto);
  const [concerns, setConcerns] = useState(db.profile?.concerns ?? '');
  const [text, setText] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const aborter = useRef<{ abort: () => void } | null>(null);

  useEffect(() => {
    return () => aborter.current?.abort();
  }, []);

  const start = async () => {
    if (!db.profile) return;
    setError(null);
    setText('');
    setDone(false);
    setStreaming(true);
    const ctrl = new AbortController();
    aborter.current = ctrl;
    let acc = '';
    try {
      await runConsult({
        settings,
        db,
        photo,
        concerns: concerns.trim() || undefined,
        signal: ctrl.signal,
        onChunk: (delta) => {
          acc += delta;
          setText(acc);
        },
      });
      setDone(true);
      // 之後台擷取 insight 寫入 memory（失敗唔影響主流程）
      try {
        const drafts = await extractInsights({ settings, db, aiText: acc });
        if (drafts.length) {
          mutateDb((d) => applyInsights(d, drafts, undefined));
        }
      } catch {
        /* ignore */
      }
    } catch (e) {
      if (e instanceof AiError && e.code === 'aborted') return;
      setError(e instanceof AiError ? e.message : '發生未知錯誤，請再試。');
    } finally {
      setStreaming(false);
      aborter.current = null;
    }
  };

  if (!db.profile) {
    return <EmptyState title="未有檔案" hint="請先喺「今日」頁建立皮膚檔案。" />;
  }

  return (
    <div className="rise">
      <div className="page-head">
        <h1 className="page-title">AI 諮詢</h1>
        <div className="page-meta">CONSULT · 01</div>
      </div>

      {!aiOn ? (
        <Banner kind="err">
          AI 未設定：去「設定」輸入 API key 先可以用 AI 諮詢。
        </Banner>
      ) : null}

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div>
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="kicker">Inputs · 輸入</div>

            <Field label="相片（AI 會睇相分析）" hint="預設用 baseline／最新相；換一張都得。">
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {[
                  { label: 'Baseline', url: db.profile.baselinePhoto },
                  { label: '最新紀錄', url: [...db.entries].sort((a, b) => b.date.localeCompare(a.date))[0]?.photo },
                ]
                  .filter((x): x is { label: string; url: string } => !!x.url)
                  .map((x) => (
                    <button
                      key={x.label}
                      type="button"
                      onClick={() => setPhoto(x.url)}
                      style={{
                        width: 96,
                        height: 96,
                        border: photo === x.url ? '2px solid var(--accent)' : '1px solid var(--line-strong)',
                        borderRadius: 6,
                        overflow: 'hidden',
                        padding: 0,
                        position: 'relative',
                      }}
                    >
                      <img src={x.url} alt={x.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      <span style={{ position: 'absolute', bottom: 0, left: 0, right: 0, fontFamily: 'var(--font-mono)', fontSize: 9, background: 'rgba(20,24,28,.7)', color: '#fff', padding: '2px 0', textAlign: 'center' }}>
                        {x.label}
                      </span>
                    </button>
                  ))}
              </div>
            </Field>

            <Field label="目標（跟住評估）">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {db.profile.goals.map((g) => (
                  <span key={g.id} className="stamp in-progress">{g.title}</span>
                ))}
              </div>
            </Field>

            <Field label="疑惑／想問">
              <textarea
                className="textarea"
                value={concerns}
                onChange={(e) => setConcerns(e.target.value)}
                placeholder="寫低想 AI 解答嘅問題…"
              />
            </Field>

            <button className="btn accent" onClick={() => void start()} disabled={streaming || !aiOn}>
              {streaming ? '諮詢中…' : '開始 AI 諮詢 →'}
            </button>
          </div>
        </div>

        <div>
          <AiResponse
            text={text}
            streaming={streaming}
            model={done ? settings.strongModel : undefined}
            error={error}
            onRetry={() => void start()}
            onCancel={() => aborter.current?.abort()}
          />
          {!text && !streaming && !error ? (
            <div className="empty-state" style={{ marginTop: 14 }}>
              諮詢結果會喺度出現 —— AI 會分析皮膚狀態、畀早晚流程建議、逐條回答你嘅疑惑。
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
