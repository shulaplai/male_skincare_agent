/* 活動 sparkline —— 最近 N 日有冇紀錄 */

export function Sparkline({
  days,
  active,
  width = 260,
  height = 40,
}: {
  days: string[]; // 由舊到新（YYY-MM-DD）
  active: (date: string) => boolean;
  width?: number;
  height?: number;
}) {
  const n = days.length;
  const step = n > 1 ? width / (n - 1) : width;
  const points = days
    .map((d, i) => {
      const y = active(d) ? height * 0.3 : height * 0.82;
      return `${(i * step).toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <line x1={0} y1={height * 0.82} x2={width} y2={height * 0.82} stroke="rgba(20,24,28,.12)" strokeDasharray="2 3" />
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
      {days.map((d, i) =>
        active(d) ? <circle key={d} cx={i * step} cy={height * 0.3} r={2.2} fill="var(--accent)" /> : null,
      )}
    </svg>
  );
}

export function lastNDays(n: number): string[] {
  const out: string[] = [];
  const d = new Date();
  d.setDate(d.getDate() - (n - 1));
  for (let i = 0; i < n; i++) {
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
    d.setDate(d.getDate() + 1);
  }
  return out;
}
