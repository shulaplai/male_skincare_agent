# 現況 vs Docs Claim 對照（live）

> 用途：單一 source of truth —— 邊啲 docs claim 係真、邊啲係 drift、邊啲未做。改 code ／改 docs 之後要更新呢張表。
> 缺口類型：(a) 純文字 drift → 改 docs；(b) 真數據路徑缺口 → 做真 code；(c) 面試 stretch → 降級／標明 demo。
> 最後更新：**2026-10-05 docs sweep（#16）** —— 加入「驗證等級」詞彙、更正測試數、更正 #25／#27／#18 敘述，逐行對 code 重新驗過；同日**重讀 live DB 嘅 `sqlite_master`**，更正「live DB 仲係壞」嗰條（schema 早已修好，見 row 16）。

## 驗證等級（點讀呢張表）

呢個 repo 反覆撞到同一種錯：**pytest 全綠 + eval PASS，但真環境行唔到**。所以每個 ✅ 都要講明喺邊個環境證實：

| 標記 | 意思 | 例子 |
|---|---|---|
| ✅ **offline** | code 真、有 test／量度證明，喺呢個 working tree 行得通（FakeLLM／temp DB／本機） | 5 nodes、attribute schema、reconcile 規則 |
| ✅ **real** | 喺**真環境**真係行過：真 provider／真瀏覽器／真 GitHub Actions／真 user data | CI（`gh run list` 睇到 push run 綠）、`data/runs.jsonl` 嗰 5 次真 run |
| 🟡 **未喺真環境驗證** | offline 綠，但從來冇喺真環境行過（冇證據，唔可以當 ✅） | #18 Docker build、#1 UI vision badge |
| ❌ **真環境壞** | offline 綠但真環境實測失敗（**最危險嗰類**，因為 gate 照綠） | global write（diet timeline）喺 live DB 500 |

⚠️ **唔可以一個 overclaim 換另一個**：settle 唔到就標 🟡 並寫明「咩證據可以 settle 佢」。

## 總覽

- **定位**：見工 portfolio + showcase；自己係 daily user（single-user）。
- **真數據路徑 100% 真；面試敘事可以 stretch 但唔可以喺真路徑扮真。**
- Backend tests **312/312 綠**（`cd backend && ./.venv/bin/python -m pytest -q`，2026-10-05 實測）；frontend `npm run typecheck` + `npm run build` 綠，本機 UI gate `npm run ui:check` **60 個 Playwright test**（40 snapshot ＋ axe 淺／暗 12 ＋ 互動 5 ＋ 相片模糊 5 ＋ consult 串流 2）綠 —— ⚠️ **CI 只行 `typecheck` + `build`，未行 `ui:check`**（見下面「仍然開住」）。eval（--fake）semantic recall 100% / MRR 0.90（baseline）＋ hybrid recall 100% / MRR 1.00（runtime path）＋ **4** agent scenarios PASS（**4 個之中 3 個**有 `expect_tool` gate —— `red_flag` 只有 `expect_escalate`；`returning_user` 用 `seed_days` 主動 seed 過去紀錄去覆蓋「已有記憶」嗰條路）。每個 scenario 行自己一個新 conversation，所以加／刪／重排 scenario 唔會改動其他 scenario 嘅結果（見 `eval/agent_eval.py` docstring）；CI（`.github/workflows/ci.yml`）有 pytest + eval + frontend jobs，`gh run list` 睇到 2026-10-05 嘅 push run 綠（**real**）。
- **真環境實測記錄**（`research/`，2026-09-14 audit）：`backend/data/runs.jsonl` 有 **5 次真 run**（最後 2026-09-30，其中一次真 vision：`vision_used: true`、`images_loaded: 6`）；真 LLM `analyze` 喺 audit 期間 **7 次有 5 次**拋 `OutputParserException`（provider 返一個 RAG tool call）—— 呢個就係 `/api/consult` 503 同 SSE in-band error 存在嘅原因。

## 對照表

| # | Docs claim（位置） | Code reality | 類型 | 狀態／驗證等級 |
|---|---|---|---|---|
| 1 | 「AI 視覺分析」每日影相 → AI 睇相（README / architecture §2） | ✅ 真：analyze 有相＋`cloud_analysis` consent → 送 `deepseek-v4-flash-vision-exp`；off 時純文字並標「未睇相」；UI badge 顯示 | (b) | ✅ **offline** ＋後端路徑 **real**（`runs.jsonl` 有一次真 vision run：`images_loaded: 6`、`vision_used: true`）。🟡 **UI 端真相 smoke test 未做**（要真人影相撳 UI 睇 badge）；real-LLM `analyze` 唔穩定（audit 5/7 失敗） |
| 2 | LangGraph 6-node flow（architecture §2 / README） | 實際 5 nodes：analyze→tools→advise→guardrail→persist | (a) | ✅ **offline**，docs 已改（5-node；`tests/test_consult_stream.py` 斷言次序） |
| 3 | Model tiering：strong vision / strong text（architecture §7） | ✅ 分層：analyze=vision-exp、advise/text=deepseek-v4-flash；dead config 已刪 | (b) | ✅ **offline**（Q20）＋真 LLM 行過 |
| 4 | Local mode（Ollama） | 冇 Ollama；冇 key = FakeLLM 示範模式 | (c) | ✅ docs 已改：FakeLLM、冇 Ollama |
| 5 | LangGraph checkpointer 做長期記憶 | 冇用 checkpointer；stateless consult + SQLite + 最近 10 條 messages | (a) | ✅ docs 已改 |
| 6 | 三類 memory（fact/derived/preference）+ 30 日衰減 + 矛盾 versioning | ✅ **per-attribute reconcile 真**（tag+direction，Q47）：strengthen / supersede + version；fact endpoint（可 global）；preference 低頻抽（Q48）；product fact hook | (b) | ✅ **offline**（Block 3 + Layer 2 完成）。global 寫入嘅 schema blocker 已修（見 row 16／21），但 live DB 冇成功寫入記錄 |
| 7 | 因果時間線 / 一年 trace | ✅ deterministic change detect + timeline（threshold 先寫）；rolling multi-anchor 對比（vs 上次／1M／3M）已上 UI（`/summary.anchors`，Q12） | (b)(c) | ✅ **offline**；「一年視圖」stretch 唔再做 |
| 8 | RAG：PDF→OCR→chunk→embed→sqlite-vec | RAG 真（chunks + cosine）；冇 OCR（pypdf 抽 text）；embedding 存 JSON | (a) | ✅ docs 已改 |
| 9 | Hybrid retrieval | ✅ **已接線**：`tools.search_knowledge` 行 `rag/hybrid.py`（semantic recall + keyword re-rank）；eval recall 行純 `retrieve()` 做基準 | (a) | ✅ **offline**（eval 兩行數字都由 `--fake` 重現過） |
| 10 | Embedding model env / bge-m3 | ✅ dead config 已刪；code 用 MiniLM-L12-v2（fastembed 預設） | (a) | ✅ **offline** |
| 11 | LLM-as-judge 三維評分 | ✅ `eval/judge.py` 接線：有 key 時逐 scenario 評分；--fake skip | (c) | 🟡 **一半**：`judge.py` 真 key 行過（返真 1–5 分）＋ `--fake` skip 證實；但**harness 從未產出逐 scenario judge 分**（真 `run_eval` 喺 step 2 就因 analyze 掛而 abort）。`docs/eval-report-sample.md` 嗰批分數已標明係格式示例 |
| 12 | Eval 入 CI、「綠先 merge」 | ✅ CI `eval` job（`--fake`，FAIL → exit 1）；temp DB + golden corpus | (b) | ✅ **real**（GitHub Actions push run 綠；`ci.yml` pytest + eval + frontend jobs） |
| 13 | 「20 / 40 / 42 / 226 tests」 | 實際 **312** 個（backend，2026-10-05） | (a) | ✅ 文件已改（本表同 AGENTS.md／roadmap 已同步；#26 嗰句「pytest 60 綠」係歷史數字，保留做教訓） |
| 14 | Chat-first UI + 右 panel 指數/記憶/時間線 | ✅ chat-first 真；右 panel live（真 attributes/insights/timeline，global 🌐 標記）；假 78 分刪走 | (b) | ✅ **offline**（有 snapshot gate） |
| 15 | Chat 歷史 persist | ✅ `chat_messages` + messages endpoint；reload 唔清空 | (b) | ✅ **offline**（Q7/Q35） |
| 16 | 每個部位獨立日記/記憶/時間線 + global scope | ✅ body-part scoped 真；**global 寫手已做**：diet → global timeline（Q31）、global fact/preference 可見於 summary + coach tools | (b) | ✅ **offline**（code + test）· ✅ **schema blocker 已修並喺真 DB 生效**：`backend/app/db.py:111` `_rebuild_stale_nullables()`（2026-10-01 `3b008b1`）見到 DB `NOT NULL` 但 model nullable 就 create→copy→drop→rename（連 index）；`docs/open-findings.md:16` 喺**真 DB 嘅 copy** 上驗過（`POST /facts`＋`/events` 由 500 變 200、`global_events` 0→1、行數／index 不變）。2026-10-05 **讀 live `skincoach.db` 嘅 `sqlite_master` 確認已 relax**（`timeline_events.conversation_id VARCHAR(32)`、`insights` 同樣）。⚠️ 但 live DB **0 條 global timeline row／0 條 global insight** —— 真寫入喺 live data 上**未成功過**（要一次真 diet 確認才 settle）。⚠️ 呢個 rebuild **冇 test**（`backend/tests/` grep 唔到） |
| 17 | 產品庫 products table（roadmap P1） | ✅ products table 真（self-report 確認創建 + Entry.products + per-product fact） | (b) | ✅ **offline**（Q28 + check-in 自動 fact）。⚠️ 舊 schema 下同 global 寫入同一批次時，diet 失敗會 rollback 埋 product 寫入（`research/residual-rows.md` 表 C）—— schema 已修（row 16），但呢個批次組合未喺真環境重試 |
| 18 | Docker `compose up --build` 撳得郁 | 🟡 已修：frontend nginx `/api`+`/health` proxy → backend、optional `env_file: ./backend/.env`（`required: false`）+ `${VAR:-default}` environment、`./data` bind volume、corpus bake／empty-chunks ingest entrypoint、兩邊 .dockerignore、healthcheck。`docker compose config` ✅ PASS。**實際 build 未嘗試**（image 從來冇 build／up 過） | (c) | 🟡 **最後一關**：`docker compose up --build` 再行一次。⚠️ 以前寫「本機 Docker daemon 未開」係錯（`docker info` → 27.4.0，daemon 一直行緊），已更正 |
| 19 | 單用戶 local-first；key 喺 env | ✅ `.env` gitignored、data gitignored、export/import zip | (b) | ✅ **offline**；export 66.1 MB／5.6 s（排除 model cache 之後，2026-10-05 實測） |
| 20 | 舊 SKINFILE 概念升級重用 | 🟡 archive 博物館（Q4）；tiering/consent 已兌現；prefix caching 唔強求 | (a) | ✅ 冇再做 |
| 21 | Correlation detector（Q30） | ✅ `app/correlation.py` + `GET /correlations` + ProgressView「相關性觀察」；deterministic candidate、標明唔等於因果 | (b) | ✅ **offline**（product→attribute 半真）· 🟡 diet 半：schema blocker 已修（row 16），但 live DB 冇 global row，所以嗰半仍然冇真 data |
| 22 | Preferences 低頻抽取（Q48） | ✅ `app/preferences.py`：diet tag ≥3 日／產品 ≥3 日 → preference；text 冇變唔 rewrite | (b) | ✅ **offline**（rule 有 test、apply_events 後真 call）· 🟡 diet 分支同 row 16 同一個 blocker（已修、live DB 未有記錄）；product 分支真 |
| 23 | Memory-correction UI（delete/edit） | ✅ 改 entry note、刪 entry（連相 + 同日 conv events）、刪單相、刪 insight（清 superseded_by 指針） | (b) | ✅ **offline**（Layer 3） |
| 24 | Demo environment + seed（Q10/Q19） | ✅ `scripts/seed_demo.py` → 獨立 `data/demo.db`（90 日 synthetic + global diet events 令 correlation 有得睇）；唔掂真 data | (b) | ✅ **offline** |
| 25 | 四套 UI 結構俾 User 揀（介面結構） | ✅ `layouts/` registry（`defs.ts` 定義 chat/journal/dash/**mobile**）＋ Settings「介面結構」揀選（CSS wireframe 縮圖、即時切換、`localStorage skc-layout` persist）；`?layout=` preview override；四套共用同一批 view 元件（Chat / RecordsView / ProgressView / SettingsView / **GuideView** + `blocks.tsx`）—— ⚠️ 「feature parity」只係 **action／API layer**（同一批 endpoint、同一批畫面元件），唔係 pixel／行為 parity：各自有自己嘅 home 同空間分配。窄屏（≤760px）自動用 `mobile`，判斷邏輯係純函數 `defs.resolveLayout`（**唔會將 `mobile` 寫入 localStorage**）。另外 `View` 另有 `guide`（`GET /api/guide`，Settings「指南」入口）—— 一個 scene 唔係第 5 套 layout。**證據（2026-10-05 更新）**：`npm run typecheck` + `npm run build` 綠；**`npm run ui:check` 60 個 Playwright test 綠** —— 40 個 snapshot（4 layout × 6 scene 手機／桌面 ＋ 暗色 ＋ 橫向 ＋ 平板 ＋ 760/761 斷點）＋ axe WCAG 2.1 AA（淺／暗各 6 scene）＋ 互動 ＋ 相片模糊 ＋ heading 層級。⚠️ **CI 冇行 `ui:check`**（`.github/workflows/ci.yml` frontend job 只有 typecheck + build），所以呢個防線而家係**本地 gate**，靠人記得行 | (b) | ✅ **offline（真）**：純 presentation layer，食同一批 `/summary` 等 API；⚠️ 自動化回歸網存在但未入 CI |
| 26 | 「AI 會用工具／RAG 檢索」（architecture §2、README feature list） | ⚠️ **曾經係真 bug**：prompt 從來冇提過任何 tool 名，schema `tool_calls` 又冇 description → 實測真 DeepSeek 回 `tool_calls: []`，RAG 同長期記憶**完全冇跑**；因為 FakeLLM 硬編碼 tool 名，當時 pytest 全綠 + eval --fake PASS 都 detect 唔到。修法：`prompts.TOOL_GUIDE` + schema description + `expect_tool` eval gate；修完實測真 LLM 回齊三個 tool | (b) | ✅ 已修 ＋ test／eval gate（**offline**）· 🟡 真環境只係**部份**：3/3 tool 喺 audit 一次成功，但同一支真 LLM 喺 7 次裡面 5 次拋 `OutputParserException`（provider 回一個 tool call）→ 所以 `/api/consult` 先有 503／SSE in-band error 嗰條路 |
| 27 | 「AI agent 可以 debug」（我自己嘅開發流程） | ✅ node trace（`state["trace"]`：node／ms／摘要）、`graph.stream()` live delta（`POST /api/consult/stream` 逐 node SSE frame）、`/api/consult` 回最終 trace、run log writer（`service.write_run_log` → `settings.run_log_path` = `./data/runs.jsonl`，CWD-relative，`run_log_enabled` 預設 True）—— **三個入口都寫**：`POST /api/consult`、`POST /api/consult/stream`（兩者共用 `_finish_consult`）、`scripts/trace_consult.py:138`。`runs.jsonl` 而家**真係有** 5 條真 run（最後 2026-09-30，含真 vision）；`scripts/trace_consult.py` CLI（temp DB + FakeLLM 預設）；vision／tool 失敗同 embedder fallback 由「靜靜吞」改為 log + trace；embedding 維度 384/128 混用會 raise 而唔係靜靜比前綴 | (b) | ✅ **real**（呢套工具就係查出 #26 嗰個 bug 嘅方法；`runs.jsonl` 有真記錄） |

## 未喺真環境驗證／已知缺口（誠實列出）

- **global 寫入未有 live-DB 成功記錄**：schema blocker 本身**已經修好**（`db.py:111` `_rebuild_stale_nullables()`，喺真 DB copy 上驗過 500→200；2026-10-05 讀 live DB `sqlite_master` 亦見已 relax），但 live DB 係 **0 global timeline row／0 global insight**。#16／#17／#21／#22 嘅 global 路徑喺作者自己 data 上**從來冇成功過**。**要 settle**：喺真 app 做一次 diet 確認（或 `POST /api/conversations/{cid}/events`）睇 global row 出唔出。⚠️ 另外 `_rebuild_stale_nullables()` **完全冇 test** —— 呢類「offline 綠、真環境靜靜壞」嘅唯一防線就係 test（要驗：舊 schema 開 DB → rebuild → 行數／index 保留）。
- **#18 Docker**：image 從來冇 build／up 過（daemon 係開嘅）。要 settle：`docker compose up --build`。
- **#1 UI vision badge**：要真人影相行一次 UI；後端路徑已經有真 run 做證。
- **CI 未行 `ui:check`**：60 個 Playwright test 係本地 gate。要 settle：喺 `ci.yml` frontend job 加 `npx playwright install --with-deps chromium` ＋ `npm run ui:check`（成本：CI 時間同 browser download）。
- **真 LLM 穩定性**：analyze 對某啲輸入會拋 `OutputParserException`（audit 5/7）。UI 而家老實講「分析唔到，再試一次」＋有重試掣，但模型層面未修。

## Open work（由呢張表反推）

- **#18 Docker 真機驗證**：code 已改，要 `docker compose up --build` 行一次，確認 UI／photo upload／API proxy 全部通先可以畫 ✅。
- **Live DB global 寫入驗證**：schema 已修；要喺真 app 做一次 diet 確認（#8 嘅一部份），並且補 `_rebuild_stale_nullables()` 嘅 regression test（舊 DB → rebuild → 行數／index 保留）。
- **UI gate 入 CI**：而家 60 個 Playwright test 只喺本機行。
- **Docs 層交付**：roadmap v2 ✅、blog 草稿 ✅（`docs/blog-post.md`）、demo video 要真人 screen record（劇本 `docs/demo-script.md`）—— 呢個係唯一要人手嘅交付物。
- **數據累積**：correlation / preference 嘅「重複模式」要靠真數據 collect 幾星期先有意義 —— code 已 ready，等 data（而且要等上面嘅 live DB 修好先寫得入）。

## 面試前 checklist

- [ ] 真 vision smoke test（開 ☁️、影相 → `vision_used: true`、badge 出現）—— 後端已有真 run 做證，剩 UI 端
- [ ] 新 conversation 第一次 upload → 詳盡 onboarding 回覆（baseline 解釋）
- [ ] Reload 頁面 → thread 仲喺度（#15）
- [ ] `cd backend && ./.venv/bin/python -m pytest -q` **312 綠** + `npm run typecheck` + `npm run build`
- [ ] `cd frontend && npm run ui:check` **60 passed**（snapshot／axe／互動／相片模糊／串流）
- [ ] `python -m eval.run_eval --fake` PASS（#12）
- [ ] `scripts/seed_demo.py` 起 DEMO DB → 開 UI 展示 90 日數據（#24）
- [ ] Debug 路線試一次（#27）：`scripts/trace_consult.py --text "…"`（fake，安全）＋ `--real` 對照；行一次 UI consult 後 `backend/data/runs.jsonl` 多一條（已經有 5 條真記錄）
- [ ] 四套結構試一次（#25）：`/?layout=chat|journal|dash|mobile` 或 Settings「介面結構」切換；**窄屏（≤760px）應該自動入 `mobile`**（頂部 bar + 底部 5 tab，冇 sidebar）
- [ ] Docker `compose up --build` 撳得郁（#18）／或敘事用「local dev + seed demo」
- [ ] 揀好面試敘事用邊幾條真 claim（#1/3/6/7/11/12/14/21/22）——每條都要答到「點 control LLM」；⚠️ 講 #16／#17／#21／#22 之前先講清楚「offline 綠；舊 live DB 會 500，schema blocker 已修（真 DB copy 驗過）但 live DB 未有成功寫入記錄」
- [ ] 錄 demo video（跟 `docs/demo-script.md`）
