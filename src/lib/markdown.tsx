/* 迷你 markdown renderer —— 唔加 dependency，唔 render 原始 HTML（安全） */

import { Fragment, type ReactNode } from 'react';

function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  // **bold** / *italic* / `code`
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(<Fragment key={`${keyBase}-t${i++}`}>{text.slice(last, m.index)}</Fragment>);
    const token = m[0];
    if (token.startsWith('**')) {
      out.push(<strong key={`${keyBase}-b${i++}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('`')) {
      out.push(
        <code key={`${keyBase}-c${i++}`} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em', background: 'rgba(47,125,107,0.1)', padding: '1px 4px', borderRadius: 3 }}>
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      out.push(<em key={`${keyBase}-i${i++}`}>{token.slice(1, -1)}</em>);
    }
    last = m.index + token.length;
  }
  if (last < text.length) out.push(<Fragment key={`${keyBase}-e${i++}`}>{text.slice(last)}</Fragment>);
  return out;
}

export function renderMarkdown(text: string): ReactNode[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const nodes: ReactNode[] = [];
  let i = 0;
  let key = 0;
  let listBuf: string[] = [];

  const flushList = () => {
    if (!listBuf.length) return;
    nodes.push(
      <ul key={`ul${key++}`} style={{ margin: '6px 0', paddingLeft: 22 }}>
        {listBuf.map((l, idx) => (
          <li key={idx}>{inline(l, `li${key}-${idx}`)}</li>
        ))}
      </ul>,
    );
    listBuf = [];
  };

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      flushList();
      i++;
      continue;
    }

    if (/^#{1,4}\s/.test(line)) {
      flushList();
      const level = line.match(/^#+/)![0].length;
      const content = line.replace(/^#+\s*/, '');
      const Tag = level === 1 ? 'h3' : level === 2 ? 'h4' : 'h5';
      nodes.push(
        <Tag key={`h${key++}`} style={{ fontFamily: 'var(--font-display)', fontWeight: 700, margin: '18px 0 6px' }}>
          {inline(content, `h${key}`)}
        </Tag>,
      );
      i++;
      continue;
    }

    if (/^[-*]\s/.test(line)) {
      listBuf.push(line.replace(/^[-*]\s*/, ''));
      i++;
      continue;
    }

    if (/^\d+\.\s/.test(line)) {
      flushList();
      nodes.push(
        <ol key={`ol${key++}`} style={{ margin: '6px 0', paddingLeft: 22 }}>
          {lines
            .slice(i)
            .filter((l) => /^\d+\.\s/.test(l))
            .map((l, idx) => (
              <li key={idx}>{inline(l.replace(/^\d+\.\s*/, ''), `ol${key}-${idx}`)}</li>
            ))}
        </ol>,
      );
      // 跳過成組數字項
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) i++;
      continue;
    }

    if (/^>\s/.test(line)) {
      flushList();
      nodes.push(
        <blockquote key={`q${key++}`} style={{ margin: '10px 0', padding: '8px 14px', borderLeft: '3px solid var(--accent)', background: 'var(--accent-soft)', color: 'var(--accent-text)', borderRadius: 2 }}>
          {inline(line.replace(/^>\s*/, ''), `q${key}`)}
        </blockquote>,
      );
      i++;
      continue;
    }

    flushList();
    nodes.push(
      <p key={`p${key++}`} style={{ margin: '8px 0' }}>
        {inline(line, `p${key}`)}
      </p>,
    );
    i++;
  }
  flushList();
  return nodes;
}
