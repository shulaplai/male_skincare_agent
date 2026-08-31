/* 進度檔案 —— 對比 + 評估 + 時間線 + Memory */

import { useState } from 'react';
import { useDb, useSettings, mutateDb } from '../lib/store';
import { hasAi } from '../lib/storage';
import { runProgress, applyInsights } from '../lib/services';
import { activeInsights, insightHistory } from '../lib/memory';
import { AiError } from '../lib/ai';
import { PhotoCompare } from '../components/PhotoCompare';
import { Timeline } from '../components/Timeline';
import { InsightCard } from '../components/InsightCard';
import { GoalCard } from '../components/GoalCard';
import { Banner, EmptyState, SectionTitle } from '../components/ui';
import { formatTs } from '../lib/date';

export function Progress() {
  const db = useDb();
  const settings = useSettings();
  const aiOn = hasAi();

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!db.profile) {
    return <EmptyState title="未有檔案" hint="請先喺「今日」頁建立皮膚檔案。" />;
  }

  const latest = [...db.entries].sort((a, b) => b.date.localeCompare(a.date))[0];
  const baseline = db.profile.baselinePhoto;
  const latestPhoto = latest?.photo;
  const insights = activeInsights(db);

  const assess = async () => {
    setError(null);
    setRunning(true);
    try {
      const res = await runProgress({ settings, db });
      mutateDb((d) => {
        const withAssessment = { ...d, assessment: res.assessment };
        return applyInsights(withAssessment, res.insights, undefined);
      });
    } catch (e) {
      setError(e instanceof AiError ? e.message : '進度評估失敗，請再試。');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rise">
      <div className="page-head">
        <h1 className="page-title">進度檔案</h1>
        <div className="page-meta">PROGRESS · 03</div>
      </div>

      {!aiOn ? (
        <Banner>AI 未設定：可以睇時間線同相片對比；設定 API key 之後可以跑「AI 進度評估」。</Banner>
      ) : null}
      {error ? <Banner kind="err">{error}</Banner> : null}

      <SectionTitle num="01">Before / After 對比</SectionTitle>
      <PhotoCompare before={baseline} after={latestPhoto} beforeLabel="BASELINE" afterLabel={latest ? latest.date.slice(5).replace('-', '/') : '最新'} />

      <SectionTitle num="02">目標評估</SectionTitle>
      <div className="btn-row" style={{ marginBottom: 14 }}>
        <button className="btn accent" onClick={() => void assess()} disabled={running || !aiOn}>
          {running ? 'AI 評估中…' : db.assessment ? '重新評估' : 'AI 進度評估 →'}
        </button>
        {db.assessment ? (
          <span className="mono muted" style={{ fontSize: 11 }}>
            上次評估：{formatTs(db.assessment.ts)} · {db.assessment.model}
          </span>
        ) : null}
      </div>

      {db.assessment ? (
        <div style={{ marginBottom: 10 }}>
          <div className="card dark" style={{ marginBottom: 12 }}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 6 }}>
              Overall Assessment
            </div>
            <div style={{ fontSize: 15, lineHeight: 1.7 }}>{db.assessment.overall}</div>
          </div>
          <div className="grid-2">
            {db.assessment.goals.map((g) => {
              const goal = db.profile?.goals.find((x) => x.id === g.goalId);
              return (
                <div key={g.goalId} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16 }}>{g.title || goal?.title || '目標'}</div>
                    <span className={`stamp ${g.status}`}>{g.status === 'not-started' ? '未開始' : g.status === 'in-progress' ? '進展中' : g.status === 'achieved' ? '已達成' : '需調整'}</span>
                  </div>
                  {g.score !== undefined ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <div style={{ flex: 1, height: 6, background: 'var(--paper-3)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${g.score}%`, background: g.score >= 70 ? 'var(--accent)' : g.score >= 40 ? 'var(--amber)' : 'var(--danger)', transition: 'width .6s var(--ease)' }} />
                      </div>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{g.score}/100</span>
                    </div>
                  ) : null}
                  <div className="muted" style={{ fontSize: 13 }}>{g.reason}</div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="empty-state" style={{ padding: 22 }}>
          未跑過評估 —— 撳「AI 進度評估」，AI 會對比成段時間嘅紀錄，逐個目標打分＋更新 Memory 推導結論。
        </div>
      )}

      <SectionTitle num="03">記憶（Memory）</SectionTitle>
      {insights.length ? (
        <div className="grid-3">
          {insights.map((i) => (
            <InsightCard key={i.id} insight={i} history={insightHistory(db, i.kind)} />
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ padding: 22 }}>
          AI 未產生推導結論 —— 跑一次「AI 進度評估」就會有（含 confidence／到期／版本歷史）。
        </div>
      )}

      <SectionTitle num="04">紀錄時間線</SectionTitle>
      <Timeline entries={db.entries} />

      {db.profile.goals.length ? (
        <>
          <SectionTitle num="05">目標一覽</SectionTitle>
          <div className="grid-2">
            {db.profile.goals.map((g) => (
              <GoalCard key={g.id} goal={g} />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
