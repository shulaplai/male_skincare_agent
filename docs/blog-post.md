# 點樣控制一個 AI Agent，而唔係俾佢控制你

> SkinCoach —— local-first 男性護膚 AI 教練嘅技術筆記。全文對應 repo 嘅真實實作（`docs/status-vs-claims.md` 係 live 對照）；模型名用 DeepSeek V4、eval 數字用最新 `--fake` report。

「AI Agent」呢個詞，由 2024 開始就係 buzzword。大部分你見到嘅「agent」其實係包咗一層嘅 API chatbot：你 call model → 攞到一段文字 → 顯示出嚟。冇狀態、冇合約、冇質素門檻、冇得 debug。我做 SkinCoach 嘅時候，目標係相反：**LLM 只係成個 product 入面其中一個組件，而唔係個 product 本身。**

一句公式：

> **Product = 確定性骨架 + 型別合約 + Tool whitelist + Guardrail + Eval 門檻；LLM 只做「模糊嗰層」。**

下面逐個控制點拆開講。

## 1. 背景：點解「包層 API」唔夠

SkinCoach 係一個皮膚記錄 + 教練 app：每日影相／打字 check-in，agent 分析皮膚、俾建議，同時**記住你一段時間**。

「包層 API」做唔到核心件事：*ChatGPT 唔記得你上個月張相*。你要嘅唔係一次過嘅建議，而係一個**跨時間閉環**：

> 你三個月前食咗辣嘢嗰排爆瘡，之後停咗就好返。

呢種「因果 trace」要 agent 有能力：跨時間寫 memory、讀 memory、detect 變化、將自報事件（食咗咩／用咗咩）寫入 timeline —— 之後先可以做因果分析。呢啲全部都唔可以靠「再問多次 model」。

## 2. 架構總覽

```
React (frontend) ──/api──> FastAPI ──> LangGraph agent
                                    ├─ SQLite (memory / entries / photos / timeline)
                                    ├─ RAG (SQLite chunks + fastembed)
                                    └─ guardrail (deterministic code)
```

Local-first：所有 data 喺用戶部機（SQLite + file system）。雲端只係 opt-in 嘅「分析」層，唔係儲存層 —— 儲存同分析係兩個獨立決策。

## 3. 控制點一：State Graph —— 每一條 edge 都係你嘅 code

Agent flow 用 LangGraph `StateGraph`，得 5 個 node，線性：

```
analyze → tools → advise → guardrail → persist
```

**LLM 只出現喺 `analyze` 同 `advise`。** 其他三個 node —— 工具分派、guardrail、persist —— 全部係我自己寫嘅 deterministic code。

`analyze`：有相 + 用戶 consent → 送 vision model（DeepSeek V4 `deepseek-v4-flash-vision-exp`）；冇相／consent off → 純文字降級。出嚟係**結構化** `SkinAnalysis`：固定 attribute schema + summary + metrics。

`tools`：執行 analysis 揀嘅 whitelist 工具（見控制點四）。`advise`：text model 出建議正文。`guardrail`：硬規則（見控制點五）。`persist`：寫日記、detect 變化寫 timeline、更新 memory、寫 chat message。

點解 LangGraph 而唔係更輕嘅框架？因為我想擁有每一條 edge。黑盒框架幫你慳嘅嘢，正正係我想練嗰 part ——「點控制 agent」。

## 4. 控制點二：型別合約（Pydantic）

LLM 輸出永遠要 fit 一個 Pydantic schema，冇 free text 漏出嚟：

- `SkinAnalysis`：summary + metrics + **attributes（六個 key × 0–3 severity，固定）** + tool_calls
- `Advice`：reply（正文）+ items（行動點）+ detected_events
- `DetectedEvent`：diet / product_start / product_stop（用戶**確認先落 DB**）

好處好直接：前端 render 到、persist 寫到、eval 測到。attribute schema 係**唯一真源** —— change detect、memory、timeline 全部食佢，所以加 attribute = 改 versioned schema，唔係叫 LLM 自由發揮。

實戰教訓：DeepSeek V4 預設開 thinking mode，而 thinking mode 唔俾強制 `tool_choice` → HTTP 400。解法係對 structured output 加 `extra_body={"thinking": {"type": "disabled"}}`。呢種嘢冇得靠 prompt 祈求，係要喺 adapter 層寫死。

## 5. 控制點三：長期記憶係 deterministic，唔係 prompt 祈求

Memory 分三類：

| 類型 | 例子 | 生命週期 |
|---|---|---|
| fact | 「對花生敏感」 | 永久（用戶確認嘅 ground truth） |
| derived | 「暗瘡：中等」confidence 0.82 | 30 日 expiry；可延長／升 confidence |
| preference | 「近排成日食辣嘢」 | 穩定、低頻更新 |

Reconcile 規則（全部 code）：

- Derived insight 每條 = 一個 attribute tag + 一個 **direction**（`problem` = severity ≥2／`normal` ≤1）。
- 同一 tag 同 direction → **strengthen**：confidence 升（cap 0.97）、expiry 延長、text 更新做最新觀察。
- Direction flip（problem ↔ normal）→ **supersede**：舊 insight 標 `superseded_by`、新 insight `version+1`，歷史保留。

早期版本試過靠「文字一樣」判斷一致 —— 錯嘅：byte-identical text 先會撞上，實際永遠唔會 strengthen。改做 **tag + direction** 之後，先真正有用。

Preferences 都係 code 抽：同一 diet trigger（例如「辣」）喺 21 日內出現 ≥3 個唔同日 → global preference「近排成日食辣嘢」。**Text 冇變就唔 rewrite** —— 呢個 throttle 令 memory 唔會每條 message 都 churn。

## 6. 控制點四：Tool whitelist

Agent 只可以 call 三個工具：`get_skin_profile`（讀 memory，連 global facts）、`get_recent_entries`（讀日記，連產品名）、`search_knowledge`（RAG 檢索）。未知工具名直接 ignore。

冇任意外部 URL、冇代碼執行。呢個係「agent 唔會越權」嘅結構性保證 —— 唔係靠 system prompt 講「你唔好亂咁嚟」。

RAG 檢索行 hybrid：semantic recall（embedding cosine）top-80，再對 query 字面 token overlap 做 keyword re-rank。中英混雜 query 會優先浮返中文 chunks，又唔會俾純 keyword（BM25-style）flood 個結果。

## 7. 控制點五：Guardrail（health-adjacent）

護膚係 health-adjacent，所以安全唔可以靠 model 聽話，要 model **冇得揀**：

- 硬規則唔經 LLM：唔診斷疾病、唔開藥、唔俾劑量。
- 紅旗詞（大面積／潰瘍／流膿／持續出血／高燒…）→ 強制收起建議 + 轉介皮膚科。
- 建議含藥物／劑量詞 → 換成轉介訊息。
- 每答自動帶 disclaimer。

## 8. 控制點六：Eval 門檻

冇 eval 嘅 agent = 冇方法知道佢幾時靜靜變差。SkinCoach 有兩層：

1. **Deterministic eval**（`python -m eval.run_eval --fake`，CI 跑）：RAG recall@3（golden queries，100%、MRR 0.90）+ agent golden scenarios（3 個 PASS，包括紅旗 escalation）+ safety checks。FakeLLM + hashing embedder → 冇 key 都 reproducible。
2. **LLM-as-judge**（有 key 時）：逐個 scenario 用 judge model 三維評分（具體性／相關性／安全）。

Eval 永遠行 temp DB + committed golden corpus —— 唔會污染 dev data。

改 prompt 要過 eval、CI 綠先 merge。呢個先令「agent 質素」變成工程問題而唔係信仰。

## 9. Local-first + opt-in 雲分析

- 相 + 日記永遠留喺用戶部機。
- 雲分析係 opt-in：每個 conversation 一個開關，off 時相唔會離開部機，agent 行純文字並誠實講「有相但睇唔到」（唔會同 model 講「無相」嚟呃佢）。
- 冇 API key 都行到：FakeLLM + hash embedder，成個 flow 跑得通 —— demo 冇得賴「冇 key」。

## 10. 教訓 + 下一步

**教訓**
- Vector DB 唔使急住上：幾千 chunks 用 SQLite + Python cosine 係 instant。抽象層隔開之後，要換 sqlite-vec／pgvector 唔使改上層。
- Memory 要 semantic reconcile（tag+direction），唔係文字相等。
- 「Local-first」要拆兩個決策：儲存（一定本地）同分析（opt-in 雲端）—— 呢個先係可以做 product 嘅 privacy 設計。
- Docs 要 live：`status-vs-claims.md` 逐條 claim 對照 code，`(a) docs drift → 改 docs`，`(b) 真數據路徑缺口 → 做真 code`。

**下一步**
- Correlation detector 已上（deterministic candidate，標明唔等於因果）——等真數據 collect 幾星期先有意義。
- 部署：Docker Compose（nginx proxy / bind volume / corpus bake）；interview demo 可以用 `scripts/seed_demo.py` 起獨立 demo DB，零準備展示 90 日數據 UI。
- 再遠：多用戶 auth、Postgres + pgvector、真一年因果 trace。

一句總結：**AI Agent product 唔係「call 個 model」，而係用確定性嘅骨架去 control 一個 fuzzy 嘅 model。** LLM 做佢叻嘅嘢（睇相、組織語言），其餘每一層都由你寫嘅 code 話事 —— 咁你先可以 debug 佢、eval 佢、同埋放心俾佢記住你三個月前食咗咩。
