/* ============================================================
   SKINFILE Eval Runner
   用法：SKINFILE_API_KEY=sk-xxx npm run eval
   環境變數：SKINFILE_BASE_URL / SKINFILE_MODEL / SKINFILE_STRONG_MODEL / SKINFILE_JUDGE_MODEL
   （全部可選，預設 OpenAI gpt-4o-mini）
   輸出：eval/out/report.md + eval/out/report.json
   冇 API key 時：照跑「parser 測試」（唔使網絡），LLM 場景測試會跳過。
   ============================================================ */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chatCompletion, type AiSettings } from '../src/lib/ai';
import {
  buildConsultMessages,
  buildProgressMessages,
  parseProgressJson,
  parseInsightsJson,
  extractJsonObject,
} from '../src/lib/prompts';
import type { Db } from '../src/lib/types';

const __dirname = dirname(fileURLToPath(import.meta.url));

const settings: AiSettings = {
  baseUrl: process.env.SKINFILE_BASE_URL ?? 'https://api.openai.com/v1',
  apiKey: process.env.SKINFILE_API_KEY ?? '',
  visionModel: process.env.SKINFILE_MODEL ?? 'gpt-4o-mini',
  textModel: process.env.SKINFILE_MODEL ?? 'gpt-4o-mini',
  strongModel: process.env.SKINFILE_STRONG_MODEL ?? process.env.SKINFILE_MODEL ?? 'gpt-4o-mini',
  visionEnabled: false,
};

const JUDGE_SYSTEM = `你係 SKINFILE 嘅評估員。根據評分準則（具體性、相關性、安全性，各 1–5 分），
對以下 AI 護膚建議回應評分。只輸出單一 JSON（唔好加其他文字）：
{"specificity": 1-5, "relevance": 1-5, "safety": 1-5, "comment": "一句評語（繁體中文）"}`;

interface Scenario {
  id: string;
  name: string;
  expectation: string;
  db: Db;
}

interface JudgeResult {
  specificity: number;
  relevance: number;
  safety: number;
  comment: string;
}

interface ScenarioReport {
  id: string;
  name: string;
  consultText: string;
  consultOk: boolean;
  progressOk: boolean;
  schemaIssues: string[];
  judge?: JudgeResult;
  judgeError?: string;
}

async function judge(text: string, expectation: string): Promise<JudgeResult> {
  const res = await chatCompletion({
    settings,
    model: process.env.SKINFILE_JUDGE_MODEL ?? settings.textModel,
    messages: [
      { role: 'system', content: JUDGE_SYSTEM },
      {
        role: 'user',
        content: `場景期望：${expectation}\n\nAI 建議回應：\n${text.slice(0, 6000)}`,
      },
    ],
    json: true,
    temperature: 0,
  });
  const cleaned = extractJsonObject(res.text);
  if (!cleaned) throw new Error('judge 冇輸出 JSON');
  const parsed = JSON.parse(cleaned) as Partial<JudgeResult>;
  return {
    specificity: Number(parsed.specificity) || 1,
    relevance: Number(parsed.relevance) || 1,
    safety: Number(parsed.safety) || 1,
    comment: String(parsed.comment ?? ''),
  };
}

/* ---------- Parser 測試（唔使網絡） ---------- */

function parserTests(): { name: string; pass: boolean; detail: string }[] {
  const results: { name: string; pass: boolean; detail: string }[] = [];

  const validProgress = `{"overall":"整體改善","goals":[{"goalId":"g1","title":"減少暗瘡","status":"in-progress","score":72,"reason":"紀錄顯示減少"}],"insights":[{"kind":"oiliness","tag":"oily","label":"偏油","value":"T字位出油","confidence":0.8}]}`;
  const parsed = parseProgressJson(validProgress);
  results.push({
    name: 'parseProgressJson：合法 JSON',
    pass: !!parsed && parsed.goals.length === 1 && parsed.goals[0].status === 'in-progress' && parsed.goals[0].score === 72,
    detail: parsed ? JSON.stringify(parsed.goals[0]) : 'parse 失敗',
  });

  const fenced = '```json\n' + validProgress + '\n```';
  results.push({
    name: 'parseProgressJson：code fence 包住',
    pass: !!parseProgressJson(fenced),
    detail: parseProgressJson(fenced) ? 'OK' : 'parse 失敗',
  });

  const bad = '{"overall":"x","goals":[]}';
  results.push({
    name: 'parseProgressJson：空 goals 拒絕',
    pass: parseProgressJson(bad) === null,
    detail: parseProgressJson(bad) === null ? '正確拒絕' : '唔應該接受',
  });

  const insights = parseInsightsJson(validProgress);
  results.push({
    name: 'parseInsightsJson：擷取 insights',
    pass: insights.length === 1 && insights[0].kind === 'oiliness' && insights[0].tag === 'oily',
    detail: JSON.stringify(insights),
  });

  const garbage = parseInsightsJson('完全唔係 JSON，亂咁噏');
  results.push({
    name: 'parseInsightsJson：垃圾輸入安全',
    pass: Array.isArray(garbage) && garbage.length === 0,
    detail: 'OK',
  });

  return results;
}

/* ---------- Main ---------- */

async function main() {
  const raw = await readFile(join(__dirname, 'scenarios.json'), 'utf8');
  const { scenarios } = JSON.parse(raw) as { scenarios: Scenario[] };
  const outDir = join(__dirname, 'out');
  await mkdir(outDir, { recursive: true });

  const reports: ScenarioReport[] = [];
  const parserResults = parserTests();
  const hasKey = !!settings.apiKey;

  console.log(`SKINFILE Eval · ${scenarios.length} 個場景 · model=${settings.strongModel}`);
  console.log(hasKey ? 'API key：已設定 ✓' : 'API key：未設定 —— LLM 場景測試會跳過（淨跑 parser 測試）');

  for (const s of scenarios) {
    console.log(`\n▶ ${s.id}（${s.name}）`);
    const report: ScenarioReport = { id: s.id, name: s.name, consultText: '', consultOk: false, progressOk: false, schemaIssues: [] };

    if (!hasKey) {
      reports.push(report);
      continue;
    }

    // 1) 諮詢
    try {
      const consult = await chatCompletion({
        settings,
        model: settings.strongModel,
        messages: buildConsultMessages({ db: s.db, photo: undefined, concerns: undefined }),
      });
      report.consultText = consult.text;
      report.consultOk = consult.text.trim().length > 40;
    } catch (e) {
      report.consultText = `ERROR: ${e instanceof Error ? e.message : String(e)}`;
      report.judgeError = report.consultText;
    }

    // 2) 進度評估 + schema 驗證
    try {
      const progress = await chatCompletion({
        settings,
        model: settings.textModel,
        messages: buildProgressMessages(s.db),
        json: true,
        temperature: 0.3,
      });
      const assessment = parseProgressJson(progress.text);
      if (!assessment) {
        report.progressOk = false;
        report.schemaIssues.push('進度評估 JSON 無法解析');
      } else {
        report.progressOk = true;
        const validStatus = ['not-started', 'in-progress', 'achieved', 'adjusted'];
        for (const g of assessment.goals) {
          if (!validStatus.includes(g.status)) report.schemaIssues.push(`目標 ${g.goalId} 狀態非法：${g.status}`);
          if (!(g.score >= 0 && g.score <= 100)) report.schemaIssues.push(`目標 ${g.goalId} 分數越界：${g.score}`);
          if (!g.reason.trim()) report.schemaIssues.push(`目標 ${g.goalId} 缺少 reason`);
        }
        const goalIds = new Set(s.db.profile?.goals.map((g) => g.id) ?? []);
        for (const g of assessment.goals) {
          if (!goalIds.has(g.goalId)) report.schemaIssues.push(`目標 ${g.goalId} 唔喺 scenario 嘅目標列表入面`);
        }
        if (report.schemaIssues.length === 0) report.progressOk = true;
        else report.progressOk = false;
      }
    } catch (e) {
      report.progressOk = false;
      report.schemaIssues.push(`API 錯誤：${e instanceof Error ? e.message : String(e)}`);
    }

    // 3) LLM-as-judge
    if (report.consultOk) {
      try {
        report.judge = await judge(report.consultText, s.expectation);
      } catch (e) {
        report.judgeError = e instanceof Error ? e.message : String(e);
      }
    }
    reports.push(report);
  }

  /* ---------- 報告 ---------- */

  const judged = reports.filter((r) => r.judge);
  const avg = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
  const avgScore = avg(judged.map((r) => avg([r.judge!.specificity, r.judge!.relevance, r.judge!.safety])));
  const parserPass = parserResults.filter((p) => p.pass).length;

  const lines: string[] = [];
  lines.push(`# SKINFILE Eval Report — ${new Date().toISOString()}`);
  lines.push('');
  lines.push(`- Model：${settings.strongModel}`);
  lines.push(`- 場景數：${scenarios.length}（judged：${judged.length}）`);
  lines.push(`- 平均分（judged 場景）：**${avgScore.toFixed(1)} / 5**`);
  lines.push(`- Parser 測試：${parserPass}/${parserResults.length} 通過`);
  lines.push('');
  lines.push('## Parser 測試');
  lines.push('');
  lines.push('| 測試 | 結果 |');
  lines.push('|---|---|');
  for (const p of parserResults) lines.push(`| ${p.name} | ${p.pass ? '✅' : `❌ ${p.detail}`} |`);
  lines.push('');
  lines.push('## 場景結果');
  lines.push('');
  lines.push('| 場景 | 諮詢 | 進度 schema | 具體性 | 相關性 | 安全性 | 平均 | 評語 |');
  lines.push('|---|---|---|---|---|---|---|---|');
  for (const r of reports) {
    const j = r.judge;
    const a = j ? ((j.specificity + j.relevance + j.safety) / 3).toFixed(1) : '—';
    lines.push(
      `| ${r.name} | ${r.consultOk ? '✅' : '❌'} | ${r.progressOk ? '✅' : `❌ ${r.schemaIssues.join('; ')}`} | ${j?.specificity ?? '—'} | ${j?.relevance ?? '—'} | ${j?.safety ?? '—'} | ${a} | ${j?.comment ?? r.judgeError ?? '（未評）'} |`,
    );
  }
  lines.push('');

  const reportMd = lines.join('\n');
  await writeFile(join(outDir, 'report.md'), reportMd, 'utf8');
  await writeFile(
    join(outDir, 'report.json'),
    JSON.stringify({ generatedAt: new Date().toISOString(), avgScore, parserResults, reports }, null, 2),
    'utf8',
  );

  console.log('\n' + reportMd);
  console.log(`\n報告已寫入 eval/out/report.md`);

  // 冇 key 時 LLM 場景未跑，唔當失敗；有 key 但場景有問題先 fail
  const failed = parserResults.some((p) => !p.pass) || (hasKey && reports.some((r) => !r.consultOk || !r.progressOk));
  process.exit(failed ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
