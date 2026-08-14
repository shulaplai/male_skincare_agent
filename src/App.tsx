import { HashRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useDb } from './lib/store';
import { hasAi } from './lib/storage';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './views/Dashboard';
import { Consult } from './views/Consult';
import { CheckIn } from './views/CheckIn';
import { Progress } from './views/Progress';
import { Settings } from './views/Settings';

const NAV = [
  { to: '/', num: '00', label: '今日' },
  { to: '/consult', num: '01', label: 'AI 諮詢' },
  { to: '/checkin', num: '02', label: '每日紀錄' },
  { to: '/progress', num: '03', label: '進度檔案' },
  { to: '/settings', num: '04', label: '設定' },
];

function Layout() {
  const db = useDb();
  const aiOn = hasAi();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-name">SKINFILE</span>
          <span className="brand-stamp">Lab</span>
        </div>
        <div className="brand-sub">男性護膚 AI 實驗室</div>

        <nav className="nav">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <span className="nav-num">{n.num}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="api-status">
            <span className={`api-dot ${aiOn ? 'on' : ''}`} />
            {aiOn ? 'AI 已連線' : 'AI 未設定'}
          </div>
          <div>REC #{db.entries.length.toString().padStart(3, '0')} · {db.profile?.name ?? '未建立檔案'}</div>
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/consult" element={<Consult />} />
          <Route path="/checkin" element={<CheckIn />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <ErrorBoundary>
        <Layout />
      </ErrorBoundary>
    </HashRouter>
  );
}
