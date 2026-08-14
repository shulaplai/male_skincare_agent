/* ============================================================
   Prompts —— 全部純函數（eval runner 可直接 import）
   設計原則（prefix caching 友善）：
   - system prompt + 穩定嘅目標/偏好 前置（stable prefix）
   - 每次變動嘅紀錄數據 後置
   ============================================================ */

import type { Assessment, Db, Entry, GoalAssessment, GoalStatus, InsightDraft, InsightKind } from './types';
import { GOAL_STATUS_LABEL, INSIGHT_KIND_LABEL } from './types';
import type { ChatMessage } from './ai';
import { buildMemoryContext } from './memory';
import { formatYMD } from './date';

export const SYSTEM_PROMPT = `你係「SKINFILE」嘅專業男性皮膚科顧問（AI 助手）。
身份：擅長男士護膚嘅實務顧問，語氣專業、直接、具體，用繁體中文（可以帶少量廣東話口吻，唔好用火星文）。
原則：
1. 建議一定要具體可執行：步驟、時機（早/晚）、產品類別或成分（例如煙酰胺、水楊酸、維A醇、神經醯胺），唔好淨係講「做好保濕」。
2. 有科學依據優先；唔確定就明講，唔好亂吹。
3. 考慮男士特點：簡單步驟優先（唔好要人用十樣嘢）、清爽質地、鬚後護理。
4. 每次回應最後畀「下一步 / 呢個星期點做」。
5. 安全邊界：你唔係醫生，唔可以診斷或處方；嚴重情況（持續惡化、感染、疼痛）建議睇皮膚科醫生。
6. 唔好承諾「一定好返」；強調進度靠持續紀錄先睇到。`;

/* ---------- 目標 / 疑惑 文案 ---------- */

function goalsText(db: Db): string {
  const goals = db.profile?.goals ?? [];
  if (!goals.length) return '（未設定目標）';
  return goals
    .map((g) => {
      const s = GOAL_STATUS_LABEL[g.status];
      return `- 「${g.title}」${g.detail ? `（${g.detail}）` : ''}［狀態：${s}］`;
    })
    .join('\n');
}

function concernsText(db: Db): string {
  return db.profile?.concerns?.trim() || '（無特別疑惑）';
}

function skinTypeText(db: Db): string {
  return db.profile?.skinType ? `（用戶聲稱膚質：${db.profile.skinType}）` : '';
}

/* ---------- 初始諮詢 ---------- */

export function buildConsultMessages(input: {
  db: Db;
  photo?: string; // dataURL（可選）
  concerns?: string; // 覆寫 concerns
}): ChatMessage[] {
  const { db, photo, concerns } = input;
  const memory = buildMemoryContext(db, 7);
  const userParts: ChatMessage['content'] = [];

  const text = [
    `用戶：${db.profile?.name ?? '新用戶'}${skinTypeText(db)}`,
    `目標：\n${goalsText(db)}`,
    `疑惑／想問：\n${concerns ?? concernsText(db)}`,
    `背景記憶：\n${memory}`,
    '',
    '請做以下嘢：',
    '1. 【皮膚狀態分析】如果收到相片，描述你睇到嘅皮膚狀態（泛紅、暗瘡、油光、乾燥、毛孔、印等），並指出趨勢；冇相就講明「基於文字紀錄分析」。',
    '2. 【核心建議】針對目標同疑惑，畀一套具體嘅早晚護膚流程（步驟＋成分／產品類別），再補充飲食同作息建議。',
    '3. 【回答疑惑】逐條回答用戶嘅疑惑，直接、具體。',
    '4. 【呢個星期點做】用「呢星期清單」結尾：3–5 個可執行項目。',
  ].join('\n');

  if (photo) {
    userParts.push({ type: 'image_url', image_url: { url: photo } });
  }
  userParts.push({ type: 'text', text });
  return [
    { role: 'system', content: SYSTEM_PROMPT },
    { role: 'user', content: userParts },
  ];
}

/* ---------- Check-in 回應 ---------- */

export function buildCheckinMessages(input: { db: Db; entry: Entry; prevEntry?: Entry }): ChatMessage[] {
  const { db, entry, prevEntry } = input;
  const memory = buildMemoryContext(db, 7);
  const steps = entry.skincare.length
    ? entry.skincare.map((s) => `${s.step}${s.product ? `（${s.product}）` : ''}`).join('、')
    : '冇做護膚';
  const prevLine = prevEntry
    ? `昨日（${formatYMD(prevEntry.date)}）：護膚[${prevEntry.skincare.map((s) => s.step).join('、') || '冇'}]\n`
    : '（冇昨日紀錄）';

  const text = [
    `用戶：${db.profile?.name ?? '新用戶'}${skinTypeText(db)}`,
    `目標：\n${goalsText(db)}`,
    `背景記憶：\n${memory}`,
    '',
    `今日（${formatYMD(entry.date)}）紀錄：`,
    `護膚做咗：${steps}`,
    `食咗咩：${entry.diet || '冇紀錄'}`,
    entry.notes ? `備註：${entry.notes}` : '',
    entry.question ? `新疑惑：${entry.question}` : '',
    prevLine,
    '',
    '請做以下嘢：',
    '1. 對比昨日同今日，簡短點評進度（有相就睇相描述變化；冇相就靠文字）。',
    '2. 指出今日做得好／要改善嘅位（具體）。',
    '3. 回應新疑惑（如有）。',
    '4. 用一句話講明日最應該專注做嘅一件事。',
  ]
    .filter(Boolean)
    .join('\n');

  return [
    { role: 'system', content: SYSTEM_PROMPT },
    { role: 'user', content: text },
  ];
}

/* ---------- 進度評估（JSON mode） ---------- */

export const PROGRESS_JSON_SCHEMA_HINT = `輸出必須係單一 JSON 物件，結構如下（唔好加 markdown code fence）：
{
  "overall": "一句總結成個進度",
  "goals": [
    {
      "goalId": "目標 id（必須對應返畀你嘅目標）",
      "status": "not-started | in-progress | achieved | adjusted",
      "score": 0 到 100 嘅整數,
      "reason": "評估理由（具體，引用紀錄）"
    }
  ],
  "insights": [
    {
      "kind": "skin-type | oiliness | acne | sensitivity | hydration | texture | pores | pigmentation | general",
      "tag": "粗分類值（例如 oily / normal / dry，或者 improving / stable / worsening）",
      "label": "短標題，例如「皮膚偏油」",
      "value": "詳細描述",
      "confidence": 0 到 1 嘅數字
    }
  ]
}`;

export function buildProgressMessages(db: Db): ChatMessage[] {
  const memory = buildMemoryContext(db, 30);
  const text = [
    `用戶：${db.profile?.name ?? '新用戶'}${skinTypeText(db)}`,
    `目標（要逐一評估）：\n${goalsText(db)}`,
    `背景記憶：\n${memory}`,
    '',
    '請基於全部紀錄評估每個目標嘅達成情況，並更新你對用戶皮膚狀態嘅推導結論（insights）。',
    '',
    PROGRESS_JSON_SCHEMA_HINT,
  ].join('\n');

  return [
    { role: 'system', content: SYSTEM_PROMPT },
    { role: 'user', content: text },
  ];
}

export function parseProgressJson(text: string): Assessment | null {
  const cleaned = extractJsonObject(text);
  if (!cleaned) return null;
  try {
    const parsed = JSON.parse(cleaned) as {
      overall?: string;
      goals?: Partial<GoalAssessment>[];
      insights?: unknown[];
    };
    const goals: GoalAssessment[] = (parsed.goals ?? [])
      .map((g) => {
        const status = normalizeStatus(g.status);
        return {
          goalId: String(g.goalId ?? ''),
          title: String(g.title ?? ''),
          status,
          score: clampScore(g.score),
          reason: String(g.reason ?? ''),
        };
      })
      .filter((g) => g.goalId && g.title);
    if (!goals.length) return null;
    return {
      ts: Date.now(),
      model: '',
      overall: String(parsed.overall ?? ''),
      goals,
    };
  } catch {
    return null;
  }
}

/** 從回應度擷取 insight drafts（供 recordInsights 用） */
export function parseInsightsJson(text: string): InsightDraft[] {
  const cleaned = extractJsonObject(text);
  if (!cleaned) return [];
  try {
    const parsed = JSON.parse(cleaned) as { insights?: unknown[] };
    const list = Array.isArray(parsed.insights) ? parsed.insights : [];
    return list
      .map((i) => {
        const r = (i ?? {}) as Record<string, unknown>;
        const kind = String(r.kind ?? 'general');
        return {
          kind: kind in INSIGHT_KIND_LABEL ? (kind as InsightKind) : 'general',
          tag: String(r.tag ?? 'x'),
          label: String(r.label ?? ''),
          value: String(r.value ?? ''),
          confidence: Number(r.confidence) || 0.5,
        };
      })
      .filter((i) => i.label);
  } catch {
    return [];
  }
}

export function extractJsonObject(text: string): string | null {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced) return fenced[1].trim();
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) return null;
  return text.slice(start, end + 1);
}

function normalizeStatus(s: unknown): GoalStatus {
  if (s === 'achieved' || s === 'in-progress' || s === 'adjusted' || s === 'not-started') return s;
  return 'in-progress';
}

function clampScore(n: unknown): number {
  const v = Number(n);
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

/* ---------- Insight 擷取（獨立細 call，用平快 model） ---------- */

export function buildInsightExtractMessages(context: string, aiText: string): ChatMessage[] {
  const text = [
    `背景：\n${context}`,
    '',
    `AI 剛才嘅回應：\n${aiText.slice(0, 6000)}`,
    '',
    '從以上內容，擷取對用戶皮膚狀態嘅「可累積結論」（例如膚質、油脂趨勢、暗瘡趨勢、敏感度、保濕狀態）。',
    '只輸出 JSON（唔好加任何其他文字）：',
    '{"insights":[{"kind":"skin-type|oiliness|acne|sensitivity|hydration|texture|pores|pigmentation|general","tag":"粗分類值，例如 oily/normal/dry 或 improving/stable/worsening","label":"短標題","value":"詳細描述","confidence":0到1}]}',
    '如果無可累積結論，輸出 {"insights": []}。',
  ].join('\n');

  return [
    {
      role: 'system',
      content: '你係資料整理員：只輸出合法 JSON，唔好加解釋。',
    },
    { role: 'user', content: text },
  ];
}
