/* Error Boundary —— view 出錯時唔好成個 App 白畫面 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('SKINFILE UI crash:', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        style={{
          maxWidth: 460,
          margin: '80px auto',
          padding: 26,
          border: '1px solid var(--line-strong)',
          borderRadius: 'var(--radius-lg)',
          background: '#fffdf8',
          boxShadow: 'var(--shadow-2)',
          fontFamily: 'var(--font-body)',
        }}
      >
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 900, fontSize: 22 }}>
          出現咗意外錯誤
        </div>
        <div className="muted" style={{ fontSize: 13, margin: '10px 0 18px', lineHeight: 1.6 }}>
          {String(this.state.error.message || this.state.error)}
        </div>
        <button className="btn" onClick={() => window.location.reload()}>
          重新載入
        </button>
      </div>
    );
  }
}
