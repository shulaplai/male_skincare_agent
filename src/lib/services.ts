/* ============================================================
   服務層 —— 將 prompts + ai + memory 串起嚟
   每個操作都處理：視覺降級、JSON parse fallback、insight 擷取
   ============================================================ */

import type { AiAdvice, AiSettings, Assessment, Db, Entry, InsightDraft } from './types';
import { chatCompletion, modelLooksTextOnly, AiError, type ChatMessage } from './ai';
import {
  buildConsultMessages,
  buildCheckinMessages,
  buildProgressMessages,
  buildInsightExtractMessages,
  parseProgressJson,
  parseInsightsJson,
} from './prompts';
import { buildMemoryContext, recordInsights } from './memory';

/* ---------- 諮詢（支援視覺 + 降級） ---------- */

const CONSULT_TIMEOUT_MS = 90_000;

export async function runConsult(input: {
  settings: AiSettings;
  db: Db;
  photo?: string;
  concerns?: string;
  signal?: AbortSignal;
  onChunk?: (delta: string) => void;
}): Promise<AiAdvice> {
  const { settings, db, photo, concerns, signal, onChunk } = input;
  const wantVision = settings.visionEnabled && !!photo && !modelLooksTextOnly(settings.strongModel);

  let messages = buildConsultMessages({ db, photo: wantVision ? photo : undefined, concerns });
  let vision = wantVision;

  try {
    const result = await chatCompletion({
      settings,
      model: settings.strongModel,
      messages,
      stream: !!onChunk,
      signal,
      onChunk,
      timeoutMs: CONSULT_TIMEOUT_MS,
    });
    return { advice: result.text, analysis: undefined, model: result.model, vision, ts: Date.now() };
  } catch (e) {
    // 圖唔受支援 → 自動降級純文字重試
    if (e instanceof AiError && e.code === 'image-not-supported') {
      vision = false;
      messages = buildConsultMessages({ db, photo: undefined, concerns });
      const result = await chatCompletion({
        settings,
        model: settings.strongModel,
        messages,
        stream: !!onChunk,
        signal,
        onChunk,
        timeoutMs: CONSULT_TIMEOUT_MS,
      });
      return { advice: result.text, analysis: undefined, model: result.model, vision: false, ts: Date.now() };
    }
    throw e;
  }
}

/* ---------- Check-in 回應 ---------- */

const CHECKIN_TIMEOUT_MS = 45_000;
const PROGRESS_TIMEOUT_MS = 45_000;
const INSIGHT_TIMEOUT_MS = 30_000;

export async function runCheckin(input: {
  settings: AiSettings;
  db: Db;
  entry: Entry;
  prevEntry?: Entry;
  signal?: AbortSignal;
  onChunk?: (delta: string) => void;
}): Promise<{ advice: AiAdvice; insights: InsightDraft[] }> {
  const { settings, db, entry, prevEntry, signal, onChunk } = input;

  const wantVision = settings.visionEnabled && !!entry.photo && !modelLooksTextOnly(settings.textModel);
  let vision = wantVision;
  let messages: ChatMessage[] = [];
  if (wantVision) {
    // check-in 有相：把相加落 user 訊息開頭
    messages = [
      ...buildCheckinMessages({ db, entry, prevEntry }).slice(0, 1),
      {
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: entry.photo! } },
          { type: 'text', text: (buildCheckinMessages({ db, entry, prevEntry })[1].content as string) },
        ],
      },
    ];
  } else {
    messages = buildCheckinMessages({ db, entry, prevEntry });
  }

  let result;
  try {
    result = await chatCompletion({
      settings,
      model: settings.textModel,
      messages,
      stream: !!onChunk,
      signal,
      onChunk,
      timeoutMs: CHECKIN_TIMEOUT_MS,
    });
  } catch (e) {
    if (e instanceof AiError && e.code === 'image-not-supported') {
      vision = false; // 降級純文字之後，badge 唔可以再話「已睇相」
      result = await chatCompletion({
        settings,
        model: settings.textModel,
        messages: buildCheckinMessages({ db, entry, prevEntry }),
        stream: !!onChunk,
        signal,
        onChunk,
        timeoutMs: CHECKIN_TIMEOUT_MS,
      });
    } else {
      throw e;
    }
  }

  const advice: AiAdvice = {
    advice: result.text,
    model: result.model,
    vision: vision && result.text.length > 0,
    ts: Date.now(),
  };

  // 獨立細 call 擷取可累積結論（平快 model，失敗唔影響主流程）
  let insights: InsightDraft[] = [];
  try {
    insights = await extractInsights({ settings, db, aiText: result.text });
  } catch {
    insights = [];
  }
  return { advice, insights };
}

/* ---------- 進度評估（JSON mode） ---------- */

export async function runProgress(input: {
  settings: AiSettings;
  db: Db;
  signal?: AbortSignal;
}): Promise<{ assessment: Assessment; insights: InsightDraft[]; raw: string; model: string }> {
  const { settings, db, signal } = input;
  const messages = buildProgressMessages(db);

  let result;
  try {
    result = await chatCompletion({
      settings,
      model: settings.textModel,
      messages,
      json: true,
      signal,
      temperature: 0.3,
      timeoutMs: PROGRESS_TIMEOUT_MS,
    });
  } catch (e) {
    // JSON mode 唔受支援 → 純文字重試再解析
    if (e instanceof AiError && e.code === 'bad-request') {
      result = await chatCompletion({ settings, model: settings.textModel, messages, signal, temperature: 0.3, timeoutMs: PROGRESS_TIMEOUT_MS });
    } else {
      throw e;
    }
  }

  let assessment = parseProgressJson(result.text);
  if (!assessment) {
    throw new AiError('bad-request', 'AI 回應格式無法解析，請再試一次。');
  }
  assessment = { ...assessment, model: result.model };

  let insights: InsightDraft[] = [];
  try {
    insights = parseInsightsJson(result.text);
  } catch {
    insights = [];
  }
  return { assessment, insights, raw: result.text, model: result.model };
}

/* ---------- Insight 擷取（獨立細 call） ---------- */

export async function extractInsights(input: {
  settings: AiSettings;
  db: Db;
  aiText: string;
  signal?: AbortSignal;
}): Promise<InsightDraft[]> {
  const { settings, db, aiText, signal } = input;
  const context = buildMemoryContext(db, 7);
  const result = await chatCompletion({
    settings,
    model: settings.textModel,
    messages: buildInsightExtractMessages(context, aiText),
    json: true,
    signal,
    temperature: 0.1,
    timeoutMs: INSIGHT_TIMEOUT_MS,
  });
  return parseInsightsJson(result.text);
}

/* ---------- 儲存輔助（views 用） ---------- */

/** 把擷取到嘅 insights 寫入 memory（已處理衰減 / 矛盾） */
export function applyInsights(db: Db, insights: InsightDraft[], sourceEntryId?: string): Db {
  if (!insights.length) return db;
  return recordInsights(db, insights, sourceEntryId);
}

/**
 * 以「日期」upsert 一個 entry，並同步 memory.facts（事實型索引）。
 * CheckIn 一日一條 entry（按 date upsert），呢度係唯一寫 entry 嘅入口。
 */
export function saveEntry(db: Db, entry: Entry): Db {
  const entries = [...db.entries.filter((e) => e.date !== entry.date), entry];
  const facts = db.memory.facts.includes(entry.id)
    ? db.memory.facts
    : [...db.memory.facts, entry.id];
  return { ...db, entries, memory: { ...db.memory, facts } };
}
