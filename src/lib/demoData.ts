/* ============================================================
   Demo Mode —— 一鍵載入合成示範資料
   相片係 canvas 生成嘅皮膚色調漸變圖（唔係真人相），
   隨日數模擬「泛紅減少、膚色均勻」嘅改善趨勢。
   ============================================================ */

import type { Db, Entry, Goal } from './types';
import { uid } from './types';
import { toYMD } from './date';

const DEMO_DAYS = 30;

/** 生成一張「皮膚示意圖」：膚色漸變 + 雜訊 + 數粒模擬瑕疵（隨進度減少） */
export function makeSyntheticSkinPhoto(dayIndex: number, total: number): string {
  const size = 480;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  const progress = dayIndex / Math.max(1, total - 1); // 0..1
  // 由偏紅偏油 → 趨向乾淨均勻
  const r = Math.round(188 + 26 * progress);
  const g = Math.round(150 + 30 * progress);
  const b = Math.round(126 + 26 * progress);

  const grad = ctx.createLinearGradient(0, 0, size, size);
  grad.addColorStop(0, `rgb(${r + 14}, ${g + 8}, ${b + 4})`);
  grad.addColorStop(1, `rgb(${r - 10}, ${g - 6}, ${b - 8})`);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // 雜訊
  for (let i = 0; i < 2600; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const v = Math.random() * 26 - 13;
    ctx.fillStyle = `rgba(${r + v}, ${g + v}, ${b + v}, 0.06)`;
    ctx.fillRect(x, y, 1.4, 1.4);
  }

  // 模擬瑕疵（T 字位集中），數量隨進度減少
  const blemishes = Math.max(1, Math.round(14 * (1 - progress) + 2));
  for (let i = 0; i < blemishes; i++) {
    const x = size * (0.35 + Math.random() * 0.3);
    const y = size * (0.15 + Math.random() * 0.35);
    const rad = 2 + Math.random() * 5;
    ctx.beginPath();
    ctx.arc(x, y, rad, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${Math.round(150 + progress * 40)}, ${Math.round(80 + progress * 30)}, ${Math.round(70 + progress * 20)}, ${0.25 + progress * 0.2})`;
    ctx.fill();
  }

  // 高光（模擬油光，隨進度減少）
  const sheen = Math.round(10 * (1 - progress));
  for (let i = 0; i < sheen; i++) {
    const x = size * (0.3 + Math.random() * 0.4);
    const y = size * (0.2 + Math.random() * 0.3);
    ctx.beginPath();
    ctx.ellipse(x, y, 10 + Math.random() * 18, 6 + Math.random() * 10, Math.random() * Math.PI, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.10)';
    ctx.fill();
  }

  return canvas.toDataURL('image/jpeg', 0.72);
}

const DEMO_SKINCARE_ROUTINES: { step: string; product: string }[][] = [
  [
    { step: '潔面', product: '胺基酸洗面奶' },
    { step: '爽膚水', product: '無酒精控油爽膚水' },
    { step: '保濕', product: '清爽凝露' },
  ],
  [
    { step: '潔面', product: '胺基酸洗面奶' },
    { step: '去角質', product: '水楊酸精華（每週 2 次）' },
    { step: '保濕', product: '神經醯胺乳液' },
  ],
  [
    { step: '潔面', product: '胺基酸洗面奶' },
    { step: '精華', product: '煙酰胺精華 5%' },
    { step: '防曬', product: '清爽防曬 SPF50' },
  ],
];

const DEMO_DIETS = [
  '公司飯堂，偏油，加咗杯凍檸茶',
  '雞胸沙律 + 糙米飯，少油少糖',
  '夜晚約咗人食火鍋，食多咗',
  '早餐麥皮，午餐自備，戒咗奶茶',
  '加班叫外賣，炸雞……',
  '清淡一日：魚、菜、白飯，飲咗 2L 水',
];

const DEMO_NOTES = [
  '',
  '今日 T 字位好似冇咁油',
  '',
  '下巴生咗粒瘡，冇乜理佢',
  '開始早瞓，11 點前',
  '',
];

function dayOffset(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() - offsetDays);
  return toYMD(d);
}

export function buildDemoDb(): Db {
  const now = Date.now();
  const goals: Goal[] = [
    { id: uid(), title: '減少暗瘡', detail: '下巴同額頭嘅暗瘡明顯減少', status: 'in-progress', createdAt: now },
    { id: uid(), title: '控油', detail: 'T 字位出油減少，冇咁快泛油光', status: 'in-progress', createdAt: now },
    { id: uid(), title: '淡暗瘡印', detail: '痘印顏色變淡', status: 'not-started', createdAt: now },
  ];

  const entries: Entry[] = [];
  // 頭 5 日每日有相，之後每 3 日一張相（模擬「每星期 update 相」嘅節奏）
  for (let i = DEMO_DAYS - 1; i >= 0; i--) {
    const photo =
      i < 5 || i % 3 === 0
        ? makeSyntheticSkinPhoto(DEMO_DAYS - 1 - i, DEMO_DAYS)
        : undefined;
    const routine = DEMO_SKINCARE_ROUTINES[i % DEMO_SKINCARE_ROUTINES.length];
    const ts = now - i * 86_400_000;
    entries.push({
      id: uid(),
      date: dayOffset(i),
      photo,
      skincare: routine.map((s) => ({ ...s, id: uid() })),
      diet: DEMO_DIETS[i % DEMO_DIETS.length],
      notes: DEMO_NOTES[i % DEMO_NOTES.length],
      createdAt: ts,
      updatedAt: ts,
    });
  }
  entries.sort((a, b) => a.date.localeCompare(b.date));

  const daysAgo = (n: number) => now - n * 86_400_000;
  const d30 = 30 * 86_400_000;

  return {
    version: 1,
    demo: true,
    profile: {
      id: uid(),
      name: '阿俊',
      skinType: '混合偏油',
      baselinePhoto: makeSyntheticSkinPhoto(0, DEMO_DAYS),
      concerns: 'T 字位成日出油，下巴成日生暗瘡，想知點先可以減少出油同淡走啲痘印。',
      goals,
      createdAt: daysAgo(DEMO_DAYS),
    },
    entries,
    memory: {
      facts: entries.map((e) => e.id),
      derived: [
        {
          id: uid(),
          kind: 'oiliness',
          tag: 'oily',
          label: 'T 字位偏油',
          value: '綜合紀錄，T 字位出油明顯，但近兩星期有改善趨勢。',
          confidence: 0.82,
          createdAt: daysAgo(6),
          expiresAt: now + d30,
          version: 2,
        },
        {
          id: uid(),
          kind: 'acne',
          tag: 'improving',
          label: '暗瘡趨勢：改善中',
          value: '暗瘡數量由高峰期回落，下巴間中仍有一兩粒。',
          confidence: 0.7,
          createdAt: daysAgo(3),
          expiresAt: now + d30,
          version: 1,
        },
        {
          id: uid(),
          kind: 'hydration',
          tag: 'normal',
          label: '保濕狀態正常',
          value: '使用神經醯胺乳液後無乾燥繃緊情況。',
          confidence: 0.66,
          createdAt: daysAgo(9),
          expiresAt: now + d30,
          version: 1,
        },
      ],
      preferences: [
        { id: uid(), kind: 'preference', text: '鍾意清爽質地，唔鍾意油笠笠', createdAt: daysAgo(20) },
        { id: uid(), kind: 'aversion', text: '想避免刺激性強嘅成分', createdAt: daysAgo(20) },
      ],
    },
  };
}
