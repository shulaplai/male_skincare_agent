# SKINFILE — 男性護膚 AI 實驗室

> 上載相片 → 設定目標 → 留低疑惑 → AI 睇相畀建議 → 每日／每週紀錄護膚同飲食 → 對比相片 → 睇吓目標達成未。

一個**單頁 AI 助手**：將「護膚追蹤」變成一個有 **Memory（AI 會記住你嘅皮膚狀態，仲會過期同更新）** 嘅縱向紀錄系統。

---

## 30 秒 Elevator Pitch

> 「ChatGPT 淨係識畀你一次性建議，但唔會記得你上個月張相。SKINFILE 係一個**長期縱向追蹤**：你上載 baseline 相、設定目標（去暗瘡／控油／淡印）、每日紀錄護膚同食咗咩、再上載相。AI 每次睇相分析、對比前後、更新佢對你皮膚嘅『推導記憶』（帶 confidence 同 expiry），最後逐個目標打分，話你知有冇達成。單次對話做唔到嘅係：**跨時間嘅閉環追蹤**。」

## 功能

| 功能 | 說明 |
|---|---|
| 📸 睇相分析 | 上載素顏相，AI（支援視覺嘅 model）描述泛紅／暗瘡／油光／乾燥，同 baseline 對比 |
| 🎯 目標＋疑惑 | 設定多個目標，隨時留低想 AI 解答嘅問題 |
| 📓 每日 Check-in | 紀錄護膚步驟（＋產品）、飲食、相片、備註，AI 對比昨日畀回應 |
| 🧠 Memory 系統 | 推導型結論（例：偏油，confidence 82%）30 日到期衰減；新證據與舊結論矛盾時版本覆蓋、留歷史 |
| 📈 進度評估 | AI 逐個目標打分（0–100）＋狀態印章（未開始／進展中／已達成／需調整） |
| ⇄ Before/After | 拖曳滑桿對比 baseline 同最新相 |
| 🧪 Demo Mode | 一鍵載入 30 日合成示範資料（相片係 canvas 生成嘅皮膚色調示意圖） |

## 快速開始

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 產出 dist/
npm run eval       # 評估 harness（parser 測試唔使 key）
```

### 設定 AI（必要先用到 AI 功能）

去「設定」頁：

1. 揀 Provider：**OpenAI**（`gpt-4o-mini` 系，支援睇相）／ **DeepSeek**（`deepseek-chat`，純文字，會自動降級唔送相）／ 自訂 OpenAI-compatible endpoint
2. **香港用戶**：OpenAI 官方唔支援香港 IP，直接用內建嘅香港直連 presets —— **Google Gemini**（免費、支援睇相）／ **OpenRouter**（多 model）／ **阿里雲 Qwen-VL**／ **智譜 GLM-4V**／ **SiliconFlow**（後三者 CORS 要撳「測試連線」確認）
3. 入 API key（只存喺你自己瀏覽器嘅 localStorage，純前端 App 冇後端）
4. 撳「測試連線」

> ⚠️ 瀏覽器直連限制：需要目標 API 支援 CORS（OpenAI / DeepSeek / Gemini 支援；中國 provider 要實測）。呢個係純前端取捨，詳細講解見 [`DECISIONS.md`](DECISIONS.md)。

### 體驗 Demo

`設定 → Demo Mode → 載入示範資料`，即有 30 日紀錄＋目標＋Memory，即刻玩「進度檔案」同「AI 諮詢」（要入咗 key）。

## Eval

```bash
SKINFILE_API_KEY=sk-xxx npm run eval
# 可選：SKINFILE_BASE_URL / SKINFILE_MODEL / SKINFILE_STRONG_MODEL / SKINFILE_JUDGE_MODEL
```

- 3 個 golden scenarios（暗瘡油性肌／敏感乾性肌／間斷紀錄）
- 每場景：諮詢回應 + 進度評估 schema 驗證 + **LLM-as-judge** 三維評分（具體性／相關性／安全性）
- 報告：`eval/out/report.md`；評分準則見 [`eval/judge.rubric.md`](eval/judge.rubric.md)

## 架構

```
src/lib/
  types.ts        核心資料型別（Db / Entry / Memory / Insights）
  storage.ts      localStorage 持久化（versioned schema + module cache + 匯出/匯入）
  memory.ts       Memory 規則：三類記憶、confidence、30 日 expiry、矛盾 versioning
  prompts.ts      三種任務 prompt（諮詢／check-in／進度評估 JSON）＋ parser
  ai.ts           OpenAI-compatible 呼叫：視覺 / SSE 串流 / JSON mode / 錯誤分類 / 降級
  services.ts     操作層：視覺降級、insight 擷取、寫入 memory
  demoData.ts     Demo Mode 合成資料（canvas 生成示意相）
views/            Dashboard / Consult / CheckIn / Progress / Settings
eval/             scenarios.json + judge.rubric.md + run-eval.ts（tsx）
```

## 開發指引

想用 AI agent 喺呢個 repo 開發？睇 [`AGENTS.md`](AGENTS.md)。技術選型嘅「點解」同面試談資？睇 [`DECISIONS.md`](DECISIONS.md)。
