/* AI 回應區塊：串流打字效果 + model 標籤 + 錯誤 + 重試 */

import { MarkdownView } from './MarkdownView';

export function AiResponse({
  text,
  streaming,
  model,
  vision,
  error,
  onRetry,
  onCancel,
}: {
  text: string;
  streaming: boolean;
  model?: string;
  vision?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onCancel?: () => void;
}) {
  return (
    <div className="card dark" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--accent)' }}>
          SKINFILE AI 分析
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--muted-on-ink)', display: 'flex', gap: 8, alignItems: 'center' }}>
          {model ? <span>{model}</span> : null}
          {vision ? <span style={{ color: 'var(--amber)' }}>◉ 已睇相</span> : null}
          {streaming ? <span style={{ color: 'var(--amber)' }}>生成中…</span> : null}
        </span>
      </div>

      {error ? (
        <div style={{ color: '#e8a08f', fontSize: 13.5, border: '1px solid rgba(179,69,47,.5)', borderRadius: 4, padding: '10px 12px', marginBottom: 10 }}>
          {error}
        </div>
      ) : null}

      {text ? (
        <div className={streaming ? 'typing-cursor' : ''} style={{ lineHeight: 1.75, fontSize: 14.5 }}>
          <MarkdownView text={text} />
        </div>
      ) : streaming ? (
        <div className="mono" style={{ color: 'var(--muted-on-ink)', fontSize: 13 }}>
          正在諮詢皮膚科顧問…
        </div>
      ) : null}

      {streaming && onCancel ? (
        <button type="button" className="btn sm paper" onClick={onCancel} style={{ marginTop: 12 }}>
          停止生成
        </button>
      ) : null}
      {!streaming && error && onRetry ? (
        <button type="button" className="btn sm accent" onClick={onRetry} style={{ marginTop: 12 }}>
          重試
        </button>
      ) : null}
    </div>
  );
}
