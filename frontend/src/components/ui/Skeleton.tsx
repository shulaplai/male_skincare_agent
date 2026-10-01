/**
 * 載入骨架（Phase 2b）。以前係一句「載入中…」文字 —— 用戶唔知會出咩、要等幾久，
 * 而且內容一到位版面會跳。骨架「預告」版面形狀，等到嘅時候唔會嚇一跳。
 * 純裝飾（`aria-hidden`）；真正嘅狀態由 `aria-busy` 或者 `aria-live` 講。
 */
export function Skeleton({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`skeleton ${className}`} aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skel" style={{ width: `${[92, 100, 68, 84][i % 4]}%` }} />
      ))}
    </div>
  )
}
