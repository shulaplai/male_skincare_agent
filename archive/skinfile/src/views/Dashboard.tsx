/* Dashboard —— 今日狀態 */

import { Link } from 'react-router-dom';
import { useDb } from '../lib/store';
import { hasAi } from '../lib/storage';
import { activeInsights } from '../lib/memory';
import { streakDays, todayLocal, formatYMD, weekday, daysBetween } from '../lib/date';
import { Onboarding } from '../components/Onboarding';
import { GoalCard } from '../components/GoalCard';
import { Sparkline, lastNDays } from '../components/Sparkline';
import { Banner } from '../components/ui';
import { INSIGHT_KIND_LABEL } from '../lib/types';

export function Dashboard() {
  const db = useDb();
  const today = todayLocal();
  const aiOn = hasAi();

  if (!db.profile) {
    return (
      <div className="rise">
        <div className="page-head">
          <h1 className="page-title">今日</h1>
          <div className="page-meta">DASHBOARD · 00</div>
        </div>
        {!aiOn ? (
          <Banner>
            AI 未設定：AI 建議需要 API key。你可以先去「設定」入 key；未設定都可以照用手動紀錄。
          </Banner>
        ) : null}
        <Onboarding />
      </div>
    );
  }

  const todayEntry = db.entries.find((e) => e.date === today);
  const lastEntry = [...db.entries].sort((a, b) => b.date.localeCompare(a.date))[0];
  const streak = streakDays(db.entries.map((e) => e.date));
  const insights = activeInsights(db);
  const days = lastNDays(30);
  const daySet = new Set(db.entries.map((e) => e.date));

  const goalScores: Record<string, number> = {};
  if (db.assessment) {
    for (const g of db.assessment.goals) goalScores[g.goalId] = g.score;
  }

  return (
    <div className="rise">
      <div className="page-head">
        <div>
          <div className="kicker">Daily Briefing · {formatYMD(today)} {weekday(today)}</div>
          <h1 className="page-title" style={{ fontSize: 28 }}>
            {db.profile.name}，今日好。
          </h1>
        </div>
        <div className="page-meta">
          {db.demo ? <span style={{ color: 'var(--amber)' }}>DEMO</span> : null}
          <br />
          streak：{streak} 日
          {lastEntry && lastEntry.date !== today ? ` · 上次紀錄 ${daysBetween(lastEntry.date, today)} 日前` : ''}
        </div>
      </div>

      {!aiOn ? (
        <Banner>
          AI 未設定：去「設定」輸入 API key 之後，AI 先可以睇相同畀建議。未設定都可以照做手動紀錄。
        </Banner>
      ) : null}

      <div className="grid-2">
        <div>
          <h2 className="sec"><span className="sec-num">01</span> 目標</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {db.profile.goals.map((g) => (
              <GoalCard key={g.id} goal={g} score={goalScores[g.id]} />
            ))}
          </div>
          <div style={{ marginTop: 12 }}>
            <Link to="/progress" className="mono" style={{ fontSize: 12, letterSpacing: '.1em' }}>
              進度檔案 →
            </Link>
          </div>
        </div>

        <div>
          <h2 className="sec"><span className="sec-num">02</span> 最新紀錄</h2>
          {lastEntry ? (
            <div className="card" style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              {lastEntry.photo ? (
                <div className="photo-frame" style={{ width: 88, height: 88, flexShrink: 0 }}>
                  <img src={lastEntry.photo} alt="最新相片" />
                </div>
              ) : (
                <div className="photo-frame" style={{ width: 88, height: 88, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>
                  🧴
                </div>
              )}
              <div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{formatYMD(lastEntry.date)} · {lastEntry.skincare.length} 步護膚</div>
                <div style={{ fontSize: 13.5, marginTop: 4 }}>{lastEntry.diet || '飲食：冇紀錄'}</div>
                {lastEntry.ai ? <div className="mono" style={{ fontSize: 11, color: 'var(--accent-text)', marginTop: 3 }}>AI 已回應</div> : null}
              </div>
            </div>
          ) : (
            <div className="empty-state">未有紀錄</div>
          )}

          <h2 className="sec"><span className="sec-num">03</span> 最近 30 日活動</h2>
          <div className="card">
            <Sparkline days={days} active={(d) => daySet.has(d)} width={420} height={44} />
            <div className="mono" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>有紀錄 = 綠點</div>
          </div>
        </div>
      </div>

      <h2 className="sec"><span className="sec-num">04</span> AI 推導結論（Memory）</h2>
      {insights.length ? (
        <div className="grid-3">
          {insights.map((i) => (
            <div key={i.id} className="card" style={{ padding: 14 }}>
              <div className="mono" style={{ fontSize: 10, letterSpacing: '.12em', color: 'var(--accent-text)', textTransform: 'uppercase' }}>
                {INSIGHT_KIND_LABEL[i.kind]} · v{i.version}
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, marginTop: 4 }}>{i.label}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{Math.round(i.confidence * 100)}% confidence · {new Date(i.expiresAt).getMonth() + 1}/{new Date(i.expiresAt).getDate()} 到期</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ padding: 22 }}>
          AI 未產生過推導結論 —— 做一次「每日紀錄 → 問 AI」或「進度評估」就會出現。
        </div>
      )}

      <div className="btn-row" style={{ marginTop: 26 }}>
        <Link to="/checkin" className="btn">{todayEntry ? '更新今日紀錄' : '今日 Check-in →'}</Link>
        <Link to="/consult" className="btn accent">問 AI 諮詢 →</Link>
      </div>
    </div>
  );
}
