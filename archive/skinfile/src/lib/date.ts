/* 日期工具 —— 全部用本地時區 */

const pad = (n: number) => String(n).padStart(2, '0');

/** 今日本地日期 YYYY-MM-DD */
export function todayLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function toYMD(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "2025-08-14" → "8月14日" */
export function formatYMD(ymd: string): string {
  const [, m, d] = ymd.split('-').map(Number);
  if (!m || !d) return ymd;
  return `${m}月${d}日`;
}

/** "2025-08-14" → "週四" */
export function weekday(ymd: string): string {
  const [y, m, d] = ymd.split('-').map(Number);
  const names = ['日', '一', '二', '三', '四', '五', '六'];
  return `週${names[new Date(y, m - 1, d).getDay()]}`;
}

export function shortYMD(ymd: string): string {
  return ymd.slice(5).replace('-', '/');
}

/** 兩個 YYYY-MM-DD 相隔日數（b - a） */
export function daysBetween(a: string, b: string): number {
  const [ay, am, ad] = a.split('-').map(Number);
  const [by, bm, bd] = b.split('-').map(Number);
  const da = new Date(ay, am - 1, ad).getTime();
  const db = new Date(by, bm - 1, bd).getTime();
  return Math.round((db - da) / 86_400_000);
}

/** 連續紀錄日數：由今日（或昨日）倒數 */
export function streakDays(dates: string[]): number {
  const set = new Set(dates);
  let cursor = new Date();
  if (!set.has(toYMD(cursor))) {
    cursor = new Date(cursor.getTime() - 86_400_000); // 今日冇紀錄，由昨日開始數
    if (!set.has(toYMD(cursor))) return 0;
  }
  let n = 0;
  while (set.has(toYMD(cursor))) {
    n += 1;
    cursor = new Date(cursor.getTime() - 86_400_000);
  }
  return n;
}

/** ISO timestamp → "8月14日 21:30" */
export function formatTs(ts: number): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
