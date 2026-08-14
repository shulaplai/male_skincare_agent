/* Markdown 檢視 */

import { renderMarkdown } from '../lib/markdown';

export function MarkdownView({ text }: { text: string }) {
  return <div>{renderMarkdown(text)}</div>;
}
