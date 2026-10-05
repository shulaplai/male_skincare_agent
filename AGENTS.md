# AGENTS.md — 畀（人類同 AI）開發者嘅 SkinCoach monorepo 指引

> 呢個係 monorepo（backend + frontend + docs）嘅工作指引。跟住佢改 code，可以減少破壞同走冤枉路。
> 上一代純前端版嘅指引喺 `archive/skinfile/AGENTS.md`（博物館，唔好喺度改）。

## 常用命令

```bash
# Backend（一定要喺 backend/ 度行，.env 由 CWD 讀）
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --port 8001   # dev server
./.venv/bin/python -m pytest -q                                   # 285 個 test，綠先算完成
./.venv/bin/python -m eval.run_eval --fake                        # deterministic eval（CI 用）
FASTEMBED_CACHE_PATH=./.hf-cache ./.venv/bin/python -m eval.run_eval  # 真 embedder + 有 key 時連埋 LLM-as-judge
./.venv/bin/python scripts/ingest_corpus.py                       # 重建 RAG corpus（chunks table）
./.venv/bin/python scripts/seed_demo.py                           # 起獨立 DEMO DB（唔掂真 data；見 README）
./.venv/bin/python scripts/trace_consult.py --text "下巴爆瘡點算？"   # trace 一次 consult（temp DB + FakeLLM，安全）
./.venv/bin/python scripts/trace_consult.py --real --text "..."     # 用真 LLM 睇 tool_calls / vision 行為

# Frontend
cd frontend
npm run typecheck    # tsc --noEmit，一定要過
npm run build        # typecheck + vite build
npm run dev          # :5173（proxy /api -> :8001，所以 backend 要同時行）
npm run ui:check     # ⭐ typecheck + eslint + stylelint + Playwright（40 snapshot + axe 12（淺／暗）＋ 5 互動 ＋ 4 相片模糊）
npm run ui:update    # UI 改動**預期之內**時更新 baseline snapshot（要逐個解釋）
npm run ui:test      # 只跑 Playwright（會自己起 Vite :5180，唔撞 :5173/:5174）
```

## 目錄結構速覽

| 路徑 | 內容 | 注意 |
|---|---|---|
| `backend/app/main.py` | FastAPI routes | 所有 API 都喺度；DB session 用 `get_session` |
| `backend/app/agent/` | LangGraph agent：`graph.py`（5 nodes）、`llm.py`（adapters + get_llm）、`prompts.py`（純函數）、`schemas.py`（Pydantic 合約）、`attributes.py`（固定 attribute schema + change detect）、`tools.py`（whitelist）、`guardrails.py`（deterministic）、**`ingredients.py`**（成份正規化 + 有引文嘅 seed 字典）、**`recommend.py`**（規則表：主選／次選，商品評估同指南共用）、**`product_eval.py`**（coverage matching + verdict）；全部純函數 | 核心邏輯 |
| `backend/app/agent/product_context.py` | 商品評估嘅 **DB 膠水**：`profile_inputs()` / `evaluate_for_conversation()` / `summarise_evaluation()`。`product_eval.py` 係純函數所以唔可以自己讀 profile | **兩個 caller 共用**（`/products/evaluate` route ＋ `graph.tools`）；分開寫就一定會分岔（見下面陷阱） |
| `backend/app/memory.py` | Memory 規則（decay / reconcile，tag+direction 語義 Q47） | pure functions；persist 喺 graph.py call |
| `backend/app/preferences.py` | 偏好低頻抽取（Q48）：diet trigger ≥3 日 / 產品 ≥3 日 → preference insight | deterministic；apply_events 後 call |
| `backend/app/correlation.py` | 相關性偵測（Q30）：cause episodes → attribute deltas，repeated = strong | deterministic；`/correlations` endpoint 用 |
| `backend/app/self_report.py` | 確認自報事件 → Entry/timeline/products/facts | diet 寫 **global** timeline（Q31）；product fact hook |
| `backend/app/rag/` | chunking / embeddings / vectorstore / hybrid / ingest | `hybrid.py` 已接線（`tools.search_knowledge` 用 `search_hybrid`） |
| `backend/app/models.py` | SQLAlchemy tables：users / conversations / entries / photos / insights / timeline_events / chat_messages / **products** / **videos** / chunks | 加 column 要同步 `db.py` `_COLUMN_MIGRATIONS`（SQLite 唔會自動 ALTER）；**新表**唔使，`create_all` 會建 |
| `backend/app/guide.py` | In-app「男士護膚基本資料」內容（Pydantic 樹 + 每句 `citations`）；「應該用咩產品」由 `recommend.RULES` **生成**，所以指南同 agent 唔可能唔一致 | 純函數；`tests/test_guide.py` 對真 DB 逐條驗引文（CI skip） |
| `backend/app/video.py` | 影片 → 抽格：`video_path` / `probe` / `extract_frames` / `compress_video` / `save_video` / `video_file` / `delete_video`。**≤20 秒**、上限 **100MB**（`MAX_BYTES`，串流途中驗）、最多 **6 格**、去重（32×32 灰階平均差 <6.0）。>40MB（`COMPRESS_OVER_BYTES`）自動重編碼（縮到 1280px、CRF 26、**丟音軌**）。原始片**本機儲**（`data/videos/<32hex>`）＋ `Video` row | ⚠️ **imageio 個 ffmpeg plugin 唔收 `BytesIO`**，所以一定要先寫落 disk 再解碼。⚠️ **`compress_video` 會將條片改名做 `<id>.c.mp4`** —— 搵／刪片一定要經 `video_file()`／`delete_video()`（兩個 spelling 都認），自己砌 `data_dir / v.path` 就會漏（見 `backend-flow.md` §7） |
| `backend/app/db.py` | engine + `init_db()`（create_all + 輕量 ALTER migration） | init_db 唔會毀 data |
| `backend/eval/` | `run_eval.py` + `golden/`（committed 細 corpus）+ scenarios | eval 行 **temp DB**，唔好改返佢用 real DB；agent scenario 有 `expect_tool` gate |
| `backend/scripts/trace_consult.py` | 單次 consult 嘅逐步 trace（debug 入口） | 預設 temp DB + FakeLLM，零風險；`--db dev` 會寫真 data |
| `backend/tests/` | pytest（而家 285 個） | 每加功能要有 test |
| `backend/corpus/` | 語料種子（zh basics + sources list）；大 corpus 喺 `data/corpus`（gitignored） | |
| `frontend/src/` | React：`App.tsx`（state 主控）、`components/`、`api.ts`（API 層）、`format.ts`（helpers）、`types.ts`（types） | server 係 source of truth，**冇 demo data** |
| `frontend/tests/ui/` | **UI gate**：`fixtures.ts`（deterministic API fixture；假相係 8px 棋盤格、`SUMMARY.entries[].photos` 有相 —— 兩樣都係刻意，見下面盲點）、`snapshots.spec.ts`（4 layout × 6 scene × 手機/桌面 ＋ 暗色 5 ＋ 橫向 ＋ 平板 ＋ 760/761，`settle()` 會 `clock.setFixedTime` 凍結「今日」）、`a11y.spec.ts`（axe **淺色＋暗色**各 6 個 scene，`KNOWN` 空）、`interactions.spec.ts`（Sheet／Toast／Lightbox／暗色）、**`photos.spec.ts`**（每個 scene 每張相都要 `.photo.blurred` ＋ 唔可以包 `<a>`） | 所有 snapshot 都攔截 API，唔會讀真 DB；改 UI 之後要 `npm run ui:update` 並解釋 diff |
| `frontend/src/styles/tokens.css` | **唯一值來源**：顏色（全部量過 WCAG）、字級 scale（下限 12px）、spacing／radius／tap／動效時長 ＋ `prefers-reduced-motion` 全域 rule | 唔好喺 `index.css` 加新 raw hex／新尺寸 |
| `frontend/src/components/ui/` | 基礎元件：`Icon`（Lucide registry，35 個）、`Sheet`、`Confirm`（promise 式 `useConfirm()`）、`Toast`、`Skeleton`、`Lightbox` | 新 UI 一律用呢批，唔好返去 `window.prompt/alert` |
| `frontend/public/` | **PWA 靜態資產**（Vite 會原封複製到網站根目錄，唔入 bundle）：`manifest.json` ＋ `icon-192`／`icon-512`／`apple-touch-icon.png`／`favicon.png` | 由 `frontend/scripts/generate_icons.py` 產生（Pillow），唔好手改 PNG |
| `frontend/scripts/generate_icons.py` | 產生上面嗰批 icon（跑法：由 repo root `./backend/.venv/bin/python frontend/scripts/generate_icons.py`） | 改 `--accent-deep`／`--bg` token 之後要重跑 |
| `learn/` | **AI agent 入門課程（教材，唔屬於 app）**：9 章 markdown（§06 係「點樣寫自己嘅 eval」）＋ 10 個可執行實驗（`learn/labs/`，FakeLLM ＋ 臨時 DB）＋ `walkthrough-lab03.md`（逐格 trace 導讀）＋ `exercises.md`（習題）。給「識 Python 但未接觸過 AI」嘅人。跑法 `./backend/.venv/bin/python learn/labs/lab03_agent_loop.py` | 改 app 之後如果教材講錯咗（行號／行為），要同步；課程唔可以引入 app 冇嘅嘢。§06 引 `eval/*.py` 行號，改 eval 要一齊改 |
| `docs/ux-audit-round2.md` | **第二輪 UX／UI 審計（2026-10-05）**：兩個 P0（相冇模糊、匯出壞）＋ 三個 P1（桌面導覽唔入 URL、鍵盤用唔到、冇 PWA）＋ **gate 盲點清單**（點解全部 gate 綠燈但問題出街）。全部有實測數字 | 改 UI／gate 之前先睇 §6 |
| `docs/ui-plan.md` | **手機版 UI／UX 審計 ＋ 四階段計劃**：Phase 0（工具／gate）已完成；5 個決定已經用戶逐項批（Lucide 統一、保守動效、自寫 Sheet/Toast、完整字級 scale）。量到嘅 tap target／字級／對比度問題列咗喺度，Phase 1–3 逐項修 | 開工前先睇 |
| `docs/` | architecture / **backend-flow**（由請求到 DB 嘅完整流程 + 真/Fake LLM 分別）/ roadmap / demo-script / blog-outline / eval-report-sample / status-vs-claims / product-eval-plan / open-findings | 見 `docs/status-vs-claims.md` 對照；**改 pipeline 要同步 `backend-flow.md`**（佢引 `file:line`） |
| `design/mobile-v2-round1.html` | **手機版 v2 樣板（2026-10-01，等緊用戶批）**：11 個手機框（5 scene ＋ 指南 ＋ 狀態 ＋ Sheet／Toast ＋ 影片上載 ＋ 暗色）＋ token 對照表。單一檔案、假數據、唔喺 Vite build 範圍 | 批之前唔好照住改 app；批准後 Phase 1–3 就照佢做 |
| `design/` | 靜態 HTML 設計樣板：`index.html`（桌面方向 chooser，方向 01 已選）／`mobile.html`（手機樣式 chooser）＋ `mockup-*.html` / `mobile-*.html`（每個係 self-contained phone/laptop frame） | **唔喺 Vite build 範圍**（Vite root 係 `frontend/`）；**同出貨 app 係兩套視覺語言**（`mockup-*.html` 用 Newsreader + cream/forest，app 用 Fraunces + 玫瑰粉）—— 唔好當佢係 app 嘅前例；樣板內容係假數據；serve 嘅時候只 serve `design/`（唔好喺 repo root serve，會漏 `backend/.env`） |
| `archive/skinfile/` | 上一代純前端 demo | 博物館，唔好改 |

## 設計約定（改 code 前先睇）

1. **Deterministic core 行先，LLM 只做模糊層**：guardrail、change detect、timeline 寫入、memory decay 全部係 code，唔好靠 prompt 求 LLM。LLM 只出現喺 `analyze`（睇相/文字出結構化分析）同 `advise`（出建議正文＋items）。
2. **固定 attribute schema（唔好自創）**：`attributes.py` 六個 key（acne/oiliness/redness/dryness/pores/texture）× 0–3 severity 係唯一真源；change detect、persist、timeline 全部食佢。加 attribute = 改 schema（versioned），唔係叫 LLM 自由發揮。
3. **型別合約**：所有 LLM 輸出強制 Pydantic schema（`schemas.py`）；唔好漏 free text。
4. **Privacy consent 唔可以繞過（2026-10-01 改咗模型：全雲端 + 默認同意）**：已經冇「本地模式」。
   送相上雲要**同時**滿足 `Conversation.cloud_analysis`（legacy 欄，永遠 True）**同**
   `User.photo_cloud_consent`，兩個都喺 **`service.run_consult`（server-side）** check，唔可以只靠前端
   唔顯示個掣。唔夠條件時只行純文字（prompt 講明「有相但睇唔到」，唔好同 model 講「無相」）。
   **默認**：呢個 deployment 係單一用戶自用，所以 `settings.require_photo_consent = False` →
   同意當作已給（`_normalise_consent_policy()` 會補舊 row），`ConsentGate` 唔會出。
   多人／hosted 部署要設 `SKINCOACH_REQUIRE_PHOTO_CONSENT=true` 才會問。
   **撤回要保留 `consent_at`** —— 佢係「有同意歷史」嘅標記，補 backfill 靠佢分辨「從來冇同意」同「撤回咗」，
   否則重啟就會靜靜幫人開返。（決定記錄：[issue #25](https://github.com/shulaplai/male_skincare_agent/issues/25)。）
5. **`Entry` 同 `ChatMessage` 分家**：Entry = 每日結構化摘要（data truth，畀 code 食）；ChatMessage = 對話 turns（display truth，畀 reload 用）。唔好混埋。
6. **Pure functions**：`prompts.py` / `attributes.py` / `memory.py` 唔可以有 DB/DOM 依賴；eval 會直接 import。
7. **SQLite migration**：改 model 加 column 時，喺 `db.py._COLUMN_MIGRATIONS` 加 ALTER；`create_all` 唔會改舊 table。唔好叫人鏟 DB。
8. **Secrets**：key 只放 `backend/.env`（gitignored）；`.env.example` 保持 template。唔好 commit `.env`／`data/`。
9. **Eval 門檻**：改 prompt／guardrail／retrieval 要過 `python -m eval.run_eval --fake`（CI 都會跑）。eval 永遠行 temp DB + `eval/golden/`，唔好掂 dev data。
10. **真數據路徑唔可以有假嘢**：online UI 唔准顯示 hardcode demo 數（分數/timeline/記憶）。冇數據 = empty state。

## 點樣加一個新功能（範例順序）

1. `schemas.py` 加型別（如果 LLM 要出）→ 2. `models.py` + `db.py` migration（如果持久化）→ 3. pure 邏輯放 `agent/` 或對應 module + unit test → 4. `graph.py` node 接線 → 5. `main.py` route → 6. `frontend/src/api.ts` + types → 7. UI component → 8. `pytest -q` + `npm run typecheck` + `eval.run_eval --fake` 全綠。

## 陷阱（真實撞過）

- **DeepSeek V4 thinking mode**：V4 預設開 thinking，thinking 唔俾強制 `tool_choice`（`with_structured_output` 會咁做）→ HTTP 400。解法：`OpenAICompatLLM._client()` 對 deepseek base_url 加 `extra_body={"thinking": {"type": "disabled"}}`（`"off"` string 唔得，會 400）。**唔好移除**。
- **Vision 要用 vision model**：analyze 送相要用 `vision_llm`（`deepseek-v4-flash-vision-exp`），唔好用 text model call `structured_vision`（會靜靜 fallback）。`service.run_consult` 要同時傳 `llm=get_llm("text")` 同 `vision_llm=get_llm("vision")`。
- **`deepseek-chat` 已退役**（2026-07）：model id 要用 `deepseek-v4-flash`／`deepseek-v4-flash-vision-exp`。Anthropic 3.5 alias 都冇咗，HK 直連 Anthropic/OpenAI 係 403。
- **reconcile 用 tag + direction，唔係 text（Q47）**：同一 tag 同 direction → strengthen（confidence 升、text 更新做最新）；direction flip（problem↔normal）→ supersede。改返舊「比 text」邏輯 = 回歸 bug。
- **`hybrid.py` 唔好拆走**：runtime `tools.search_knowledge` 用 `search_hybrid`（semantic recall + keyword re-rank）；eval recall 用純 `retrieve()` 做基準。兩邊都留，唔好改返純 semantic 落 tools。
- **eval gate 一定要望住 production 真正 call 嗰個路徑**：`run_eval.py` 一度只 gate 語意檢索，但 runtime 用 `search_hybrid` —— 有人改返純 `retrieve()` 落 `tools`，報告照印 hybrid 靚數、**exit code 照樣 0**，產品實際嗰條路壞咗都冇人知。反方向同樣致命：`eval/safety.py` 一度同 `apply_guardrails` **同一個盲點**（只掃 `items` 唔掃 `reply`），所以 eval 報 `violations: []` 而危險句照送到用戶。加檢查之前先問：「我量嘅係唔係 production 行嗰條路？」（教材：`learn/06-writing-eval.md` §4。）
- **Diet 事件係 global**（Q31）：`self_report.apply_events` 嘅 diet 寫 `conversation_id=NULL` timeline（唔係 conv-scoped）；`/summary` timeline = conv events + global events merge。搵 diet 事件記得 query `IS NULL` 都要包埋。
- **Delete/edit 係真 correction**：`DELETE /api/conversations/{cid}/entries/{eid}` 會連同日 conv timeline events 一齊刪（global 唔刪）；`DELETE /api/entries/{eid}/photos/{pid}` 係按 **path**（`photos/<pid>.jpg`）搵 Photo row，唔係 Photo.id；delete insight 前要清 `superseded_by` 指針。
- **eval 唔可以污染 dev DB**：`run_eval` 一定用自己 temp DB；見到佢寫入 `backend/data` 就係 bug。
- **FakeLLM 唔係「真 offline」**：冇 key 時 `service.run_consult` 仍然會 instantiate `FastembedEmbedder`（首次會 download model 或靜靜 fallback hash）。test 用 `DeterministicEmbedder`。
- **Tool 名一定要喺 prompt 講清楚**：`prompts.TOOL_GUIDE` 列出 `tools.WHITELIST` 三個 tool，`SkinAnalysis.tool_calls` 亦有 description。曾經冇寫 → 真 DeepSeek 回 `tool_calls: []`（實測）→ RAG／記憶完全冇跑，但 FakeLLM 硬編碼 tool 名令 pytest + eval --fake 全綠。加減 tool 要同步三處（whitelist／TOOL_GUIDE／schema description），`tests/test_observability.py` 會檢查。
- **Pydantic schema 有 cache**：`SkinAnalysis.model_fields["x"].description = None` **唔會**改變送去 LLM 嘅 JSON schema（核心 schema 已建好）。想驗「舊 schema 嘅行為」一定要另開一個 model class 再 monkeypatch 模組變數，唔係改 FieldInfo。
- **每個 node 都要留 trace**：`state["trace"]`（`Annotated[list, operator.add]`）逐 node 記錄 node/ms/摘要；`graph.stream()` 睇 live delta，`/api/consult` 回最終 trace。run log（`data/runs.jsonl`）由 `service.write_run_log` 寫，**兩個入口都會寫**：`POST /api/consult` 同 `scripts/trace_consult.py`（後者以前唔會寫，所以 checklist 嗰句曾經係假）。**唔好再靜靜吞錯誤**（vision 失敗、tool 例外、未知 tool 名、embedder fallback 全部要 log + 入 trace）。
- **embedding 維度唔可以混**：384（真 MiniLM）vs 128（hash fallback）唔可比，而 `_cosine` 用 `zip()` 會靜靜比前綴。`vectorstore.add_chunks` 會 raise，`search` 會跳過維度唔一致嘅 chunk 並 log warning。fastembed cache 預設喺 temp dir（會被清）→ 用 `SKINCOACH_EMBEDDER_CACHE_DIR` 指去 data dir。
- **相片 id 有 shape check**：`photo.py` 只接受 32-char hex；`persist` 只 attach 真存在嘅相，唔好造 dangling Photo row。
- **Frontend draft 要 reset**：切 conversation 要清 draft/attached（`Chat.tsx` useEffect on conversation.id）。
- **Memory kind**：backend 用 `fact | derived | preference`；frontend `kindLabel` 要用 `preference` 唔係 `pref`。
- **DB 有真 key／真 data**：`backend/.env` 係真 DeepSeek key，`backend/data` 有真 corpus —— 開發時唔好 print key、唔好鏟 data dir。
- **四套結構 UI（layout shells）**：分三層 ——
  1. `src/layouts/defs.ts`：純 data（名／描述／`tabs`／props 型別）＋ 純函數 `resolveLayout` ＋ `MOBILE_MAX_WIDTH`，**唔可以 import React**
  2. `src/layouts/Shells.tsx`：renderer registry（`LayoutId` → `ChatShell` / `StandardShell`+home / `MobileShell`）
  3. `ChatShell`（原本三欄）／`StandardShell`（journal+dash 共用，只差 tabs + home；home component 一定要用 `<Home/>` element 渲染，**唔可以直接 call function**）／`MobileShell`（底部 tab bar，scene 一樣係 `home|chat|records|progress|settings`）
  揀咗邊套存 `localStorage['skc-layout']`，`?layout=` preview 覆蓋一次；`LAYOUTS` 一定要將 `mobile` **排最後**（`layoutById` fallback 係 `LAYOUTS[0]`）。
- **窄屏自動切換嘅唯一真源係 `defs.resolveLayout`（純函數）**：優先 `?layout=` > 今次手動揀 > 窄屏 `mobile` > `localStorage`。**唔好喺 component 直接讀 `window.innerWidth`**，亦唔好喺其他地方再寫一次呢個判斷。
- **窄屏自動唔會將 `mobile` 寫入 `localStorage`**：persist 寫嘅永遠係用戶真揀嗰個。所以闊屏唔會殘留 `mobile`，但窄屏 reload 一定返 `mobile`。（CDP 實測。）
- **`MOBILE_MAX_WIDTH = 760` 嘅 CSS 冇得 import**：`index.css` 尾段 `@media (max-width: 760px)` 同 `.app.layout-mobile` 係人手同步 —— **改一邊要改兩邊**。實測過 760 = mobile、761 = 桌面，兩邊一致。
- **`.app.layout-journal` / `.app.layout-dash` 嘅 `grid-template-columns` 係 (0,2,0)，會蓋過 `@media (max-width:760px) .app` 嘅 (0,1,0)**（真實 bug：窄屏會令 `.shell-main` 跌落 220px 第一欄，內容被壓扁）。窄屏覆蓋一定要用**同等 specificity 而且放喺檔尾**。
- **`mobile` shell 嘅 scene 區要用 `.shell-scene`，唔可以用 `.shell-chat`**：`.shell-chat` 係 2 欄 grid；另外 `mobile` 區會用 CSS 收埋 `.chathead`（`ShellTop` 已提供同一組資訊，唔好雙重 header）。
- **`.chat` 一定要有 `min-height: 0`，`.shell-scene` 嘅 child 一定要 `flex: 1 1 auto; min-height: 0`**（真實 bug，用戶喺 iPhone 上撞到）：`.chat` 同時係 `.shell-chat`（grid）同 `.shell-scene`（flex column）嘅 item，兩個容器都會將 `min-height: auto` 解析成「內容高度」→ 長 thread 唔會喺 `.thread` 內部 scroll，而係撐爆容器（390×844 實測 `.chat` 4237px／grid row 4523px、`.thread` scrollable 0、`.compose` top 4221），再加 `.app.layout-mobile { overflow: hidden }` = **冇任何方法 scroll、輸入框永遠摸唔到**。同 `.app > * { min-height: 0 }` 係同一個 family，只係喺再落一層 —— 加新 shell／改 scene 容器時要一齊 check。⚠️ 「`scrollWidth == innerWidth`、冇溢出」**唔等於**「撳得到」：驗窄屏一定要**長內容 ＋ 量 `.compose` 喺唔喺 viewport 內 ＋ 真 wheel gesture**。
- **Scene（tab）= page，唔係 `useState`**：`hooks/useSceneRoute.ts` 將 scene 寫入 URL（`?scene=chat`、home 唔寫），`pushState` + `popstate`。有 tab 嘅 shell（`MobileShell`／`StandardShell`）都一定要用佢 —— 以前係 local state，撳完 tab 一 reload 就跌返第一頁（真實用戶回報）。
  ⚠️ URL 驗證要用 `defs.SHELL_SCENES`（**所有** scene）而唔係 `tabs.map(t => t.key)`：`guide` 冇 tab 但一樣係一個 page，只認 tab 名就會令 `?scene=guide` reload 靜靜跌返第一頁（真實撞過）。
  ⚠️ **四個 shell 都要用，包 `ChatShell`。** 2026-10-05 實測：`ChatShell` 一直係 `useState`，所以闊屏（default 結構）撳「皮膚記錄」URL 唔變、**reload 跌返對話**、瀏覽器上一頁去咗舊 URL、`?scene=guide` 完全冇反應。`ChatShell` 唔 render `home`，所以要 `CHAT_VIEWS` 過濾（唔係嘅話 `?scene=home` 四個 branch 都唔中 = 一片空白）。
  `sceneHref()`／`linkClick()` 係畀 `<a href>` 用嘅（見下面「導覽一定要有 href」）。
- **片＝一條片，唔係「6 張相」**（2026-10-01 用戶指示）：抽格／壓縮係 backstage 實作，**唔可以 leak 俾用戶**。
  UI 端：上載期間喺 composer 出「🎬 皮膚影片 + 真進度條」（`api.uploadVideo` 用 **XHR** 因為 `fetch` 冇 upload progress），
  **唔會**逐格出縮圖、冇「抽咗 6 張相／已壓縮 MB／格太似」文案；送出後對話只出中性 chip（`Message.clip`）。
  資料端：`POST /api/consult` 帶 `video:{duration,frames}` → `state["clip"]` → `persist` 寫入 user payload
  `payload["clip"]`（所以 reload 都係出 chip 唔係相）→ `format.ts` 見到 `clip` 就**唔會**出 `photo`。
  Prompt 端：`build_analyze_prompt(..., clip=...)` 同 `build_advise_prompt` 都明文禁止講「幾張相／格數／抽格」；
  `frames < 2` 時改用一句廣東話提醒「鏡頭慢慢掃過成塊面」（唔講數字）。
- **本地影片預覽嘅 blob 生命週期**：`URL.createObjectURL` 一定要經 `useEffect` cleanup 回收（即場 revoke 會令
  `<video>` 報 `ERR_REQUEST_RANGE_NOT_SATISFIABLE`）。另加一層防守：`onError` → SVG 佔位（唔會黑格）。
  ⚠️ **更正記錄**：我一度以為 Chromium 播唔到 H.264，其實係我自己嘅測試檔被 `open(..., 'wb')` 清空成 0 byte
  —— 用真片（4.3KB、160×120、2 秒）重測係 `readyState 4 / duration 2 / error None`。寫測試資料前先 `ls -la`。
- **底部 nav icon 用 vendored Lucide path，改完一定要重量**：`layouts/navIcons.tsx` 係 `lucide-static@0.469.0`（ISC）嘅官方 path。
  之前兩版都唔齊：emoji（字形來源唔同）同**自己手畫嘅 path**（實測 ink 高 17／17／16.5／**14**／**12** CSS px、
  視覺中心差 1.25px）。而家五個 icon ink 中心一致（`home` 加咗 `translate(0 0.4)` 校正）。
  ⚠️ 改完要行 `/tmp/skc-trial/w1_tabbar_ink.py`（dsf=4 量 ink bounding box）確認 `cy`／`h` 對齊。
- **唔好寫未定義嘅 CSS 變數**（真實 bug）：`var(--bg2, #eee)` / `var(--ink, #333)` —— `--bg2`／`--ink` **從來冇定義過**，所以永遠用 fallback（淺灰底）。淺色模式睇唔出，**暗色模式就係淺底淺字**（實測 `.chip.neutral` 1.03:1、`.src.agent` 2.57:1、`AI 偵測` 2.57:1）。要寫 fallback 之前，先 grep 個變數有冇定義。
- **無障礙檢查一定要跑淺色**同**暗色**：第一版 axe spec 只跑淺色，上面嗰批問題完全冇人知。而家用 `for (const theme of ['light','dark'])` 跑 12 個 case。
- **量度半透明背景唔可以當實色**：`.msg.me .bubble` 用 `var(--glow)`（alpha 0.16）；手寫 script 當佢實色會報 1.31:1 假警報。要由 element 一路合成 alpha 到 html（或者直接用 axe，佢處理得正確）。
- **UI 改動一定要過 `npm run ui:check`**（Phase 0，2026-10-01）：55 個 Playwright test（40 snapshot、4 layout × 6 scene、暗色、橫向、平板、760/761 斷點、影片上載、P1-4 長 thread 回歸、相片模糊）＋ axe WCAG 2.1 AA（淺／暗）。
  ⚠️ **snapshot 一定要 commit**，而且 `toHaveScreenshot` 係**反過來**保護你：唔關你事嘅走位會即刻紅燈。
  ⚠️ Playwright route 係**反轉** match（後註冊先贏）→ catch-all 一定要**最先**註冊（`fixtures.ts` 有註解）。
  ⚠️ snapshot flaky 嘅源頭通常係 **webfont swap**：`settle()` 一定要 `await document.fonts.ready`，
    而 `Chat.tsx` 亦已經加咗 `document.fonts.ready.then(pinToBottom)`（真用戶 reload 之後條 thread 亦要貼底）。
- **`useToast()` / `useLayout()` 只可以喺 provider 之內用**：`App` 自己 render providers，所以真正嘅 app 係 `AppInner`（provider 入面），`App` 淨係掛 `ThemeProvider → ToastProvider → ConfirmProvider → LayoutProvider`。喺 provider 外面叫會拿到 context default（**靜靜冇反應**）。
- **block comment 入面唔可以出現「星號＋斜線」**：我自己中過兩次 —— 寫 `` `**/api/**` `` 呢個 glob 嘅時候，
  中間嘅星號＋斜線會提早閂咗 JSDoc，後面嘅文字變成 code → eslint `no-unused-expressions`
  （而且報錯行數係**註解入面**，好難睇得出）。要寫 glob 就用文字描述（`fixtures.ts` 開頭有寫法示範）。
- **撳得到嘅嘢一定要係真 `<button>` 或 `<a href>`**：2026-10-05 掃 `src/**/*.tsx` 揾到 **17 處** `<span onClick>`／`<i onClick>`／`<div onClick>`（`Chat.tsx` 影相掣同切換部位、`RecordsView`／`JournalHome`／`blocks.tsx`／`RightPanel.tsx` 嘅刪除、`Sidebar` 嘅改名／刪除同成行對話…）。全部**入唔到 tab order、冇 Enter／Space、讀屏唔知撳得**。實測 Tab 40 次：一次都去唔到 sidebar nav（因為 `<a>` 冇 `href`），即係**純鍵盤用戶入唔到設定／記錄**。
  ⚠️ **axe 唔會報**：冇任何 axe 規則要求 `<a onClick>`／`<span onClick>` focusable。所以「0 violations」唔等於「用得到」。
  規則：動作 → `<button>`（＋`aria-label`，尤其 icon-only）；導覽 → `<a href>`（`sceneHref()` 產生，`linkClick()` 處理修飾鍵）；modal／drawer 背景 → 真 `<button>` backdrop（同 `ui/Sheet.tsx` 一樣）；`<i>`／`<span>` 唔可以有 onClick。
  ⚠️ 用 `opacity` 而唔係 `display: none` 去收起一個按鈕（`display:none` 會令佢跌出 tab order，永遠 focus 唔到）。
  ⚠️ 下拉請用 `components/ui/BodyPartMenu.tsx`（一份共用；**唔好**用 `role="listbox"`／`role="tablist"` 就算，ARIA 要配 roving tabindex + 方向鍵，做半套比唔做更差）。
  ⚠️ 自己寫量度 script 時，selector 一定要包 `<i>`／`<span>`／`[onclick]`：第一輪「0 個 < 44px tap target」就係因為只查 `button, a[href], input…`，所以 `.photo-x`（18px）同嗰批 `<i onClick>` **完全冇量到**。
- **相片一律先模糊（`components/BlurPhoto.tsx`）**：皮膚相係自拍，`<img>` 直接出清等於行過嘅人一眼睇晒。`BlurPhoto` 每次 render 都由模糊開始（唔記「睇過」），要撳「顯示」先清；`alt` 亦要跟狀態改。呢個係 UI 遮蓋，同 consent（相可唔可以上雲）係兩件事，兩樣都要。
  ⚠️ **2026-10-05 實測：呢條規則一度只有 `Chat.tsx` 遵守。** `RecordsView`／`MobileHome`／`JournalHome`
  三個地方係裸 `<img>`，`JournalHome` 仲包住 `<a href="/api/photos/…" target="_blank">` —— 撳一下
  就喺新 tab 開**原圖**。量到 3 個 scene 共 **42 張相、0 張有 blur**（`getComputedStyle(img).filter
  === 'none'`）、28 張喺 anchor 入面；而 **51 個 snapshot 全綠**（原因見下一個陷阱）。
  公告板格仔用 `variant="grid"`；加新 UI 出相之前，問一句「呢張相有冇經 `BlurPhoto`？」，
  而 `frontend/tests/ui/photos.spec.ts` 就係答嗰句嘅網。
- **UI gate 有盲點，而且盲點係靜嘅**：2026-10-05 嗰批 P0／P1 全部係「過齊所有 gate 之後出街」。
  逐個原因（全部實測）：
  1. **snapshot 睇唔到 blur**：`fixtures.ts` 嘅假相本來係低對比漸變（67 色、channel std ≈ 10），
     `blur(15px)` 只改到平均 **3.2/255**，低過 Playwright 門檻 → 已換成 8px 棋盤格（**79/255**）。
  2. **fixture 根本冇相**：`SUMMARY.entries[].photos` 係 `[]`，所以「記錄」／日記／今日三個 scene
     喺 gate 眼入面從來冇相（`/api/photos/*` 只出現喺 chat message 度）→ 已加相。
  3. **snapshot 會隨真實日期腐爛**：baseline 2026-10-01 影，當時 fixture 嗰日就係「今日」→ chip 出「今天」；
     2026-10-05 再跑變「2026-10-01」→ 3 個 snapshot 無故紅燈（實測 `390-mobile-home` 日期字 ink 91px → 150px）
     → `settle()` 加咗 `page.clock.setFixedTime(new Date('2026-10-01T09:00:00+08:00'))`。
     ⚠️ 用 `setFixedTime`，唔係 `clock.install()`：後者會令 timer 停，webfont／動效嗰啲 timeout 會卡死。
  4. **axe 捉唔到「撳唔到」**、**`test_export` 嘅 `tmp_path` 太乾淨**、**自己寫嘅量度 selector 漏 `<i>`**：
     見上面各自嗰條。
  ➡️ 通則：**「有 test」唔等於「量到你改嘅嘢」**。加檢查之後，一定要**反轉條件證明佢會紅**
     （今輪就係暫時將 `RecordsView` 還原做裸 `<img>`，睇到 `Error: 有相冇經 BlurPhoto` 才收貨）。
- **加到主畫面（PWA）metadata 一定要成套做**：2026-10-05 之前 `index.html` 完全冇 manifest／
  favicon／apple-touch-icon／theme-color／description —— 對手機為主嘅 app 具體後果係
  「加入主畫面」用網站截圖做 icon，而且一開係 Safari（有網址欄）。
  ⚠️ **iOS Safari 唔用 manifest 決定 icon／standalone**：佢只認 `apple-touch-icon` 同
  `apple-mobile-web-app-capable`。兩套都要寫（`manifest.json` 係畀 Android／桌面 Chrome／install prompt）。
  ⚠️ `theme-color` 要跟 `data-theme`（唔係 `prefers-color-scheme`）：`index.html` 放兩個帶 `media` 嘅 tag
  處理首屏，再喺 inline script 同 `theme.tsx` 跟 localStorage／切換更新 —— 唔做就係「日間模式但狀態欄深色」。
  ⚠️ `color-scheme`（`tokens.css`）同 `touch-action: manipulation` ＋ `-webkit-tap-highlight-color`
  （`index.css` `html`）都係呢一組。之前 `colorScheme === 'normal'`（暗色模式捲軸仍然係白）、
  `touchAction === 'auto'`、tap highlight 係 WebKit 預設藍 `rgba(51,181,229,0.4)`。
  ⚠️ Icon 係 `frontend/scripts/generate_icons.py`（Pillow）產生，**唔好手畫 binary**；顏色跟
  `--accent-deep` / `--bg` token，改 token 要重跑。Maskable 安全圈（中央 80%）要量過（現時 203.3 < 204.8）。
- **AI 抽出嘅自報事件一定要 persist 落 coach payload**（issue #22）：`Advice.detected_events`（diet／product_start／product_stop）係飲食／產品嘅**唯一入口**，用戶只會順口講。`persist` 要寫入 `ChatMessage.payload["detected_events"]`，`format.ts` 要 restore 返 —— 以前只存在 browser live state，reload 就冇，用戶永遠確認唔到，因果時間線亦冇料。另外確認之後要標 `payload["events_applied"]`（`main._mark_events_applied`：有 `message_id` 用 id，session 內新訊息用事件內容配對），否則 reload 會再出同一個 chip，撳兩次就寫兩次。
- **`RECORDING_GUIDE` 嘅文字有兩份**：`app/agent/prompts.py`（AI 喺對話講）同 `app/guide.py`「點樣記錄最準確」一節（app 內指南）。兩邊講同一件事 —— **改一邊要改另一邊**。當中「拍片／講出嚟嘅聲唔會記錄」係產品事實（抽格會丟音軌），唔可以為咗好聽而刪。
  ⚠️ **`build_advise_prompt` 讀 `state["vision_reason"]`，所以 `analyze` 一定要將佢寫入 state**（唔可以只放入 trace detail）。2026-10-05 實測：佢本來只存在於 trace，`AgentState` 完全冇聲明過，所以 `state.get("vision_reason")` 喺真路徑永遠係 `None` ——「非首次純文字打卡就提佢下次影相／拍片」呢個 nudges **從來冇去到 model**，而 `AGENTS.md` 一路當佢有效。同時 `saw_photo` 嗰句靜靜降級成 `bool(vision_used)`。
  點解 test 捉唔到：`test_prompt_recording_guide.py` 同 `test_prompt_photo_claims.py` 係用**手砌嘅 state dict**（裏面已經有 `vision_reason`）去 call prompt 函數 —— 佢哋證明「格式正確」，但從來冇檢查有冇人寫入過嗰個 key。**呢個係同上面兩條 eval 陷阱一模一樣嘅形狀：test 自己造出 production 永遠造唔出嘅嘢。**
  網：`tests/test_vision_reason_state.py` —— 行真 `graph.invoke`，用一個會記錄 prompt 嘅 stub 去斷言 nudges 真係出現（同埋首次打卡**唔**應該出現）。已驗證會紅：拎走 `analyze` 嗰行 `"vision_reason": ...` → 2 個 test 即刻紅，訊息直接講「analyze 冇將 vision_reason 寫入 state」。
  ⚠️ 寫 assert 之前先問：「我係唔係自己造咗個 production 造唔出嘅輸入？」同類真例子：`tests/test_upload_errors.py` 嗰句 `assert not list(...) if dir.exists() else True` 因為條件表達式優先次序而**永遠唔會紅**（已改成先斷言目錄狀態、再斷言內容）。
- **Chat bubble 嘅 class 名唔可以照抄 `role`**：`role` 係 `user|coach`，但 CSS 嘅左右分邊係 `.msg.me`（`row-reverse` + `margin-left: auto`）／`.a.me`。直接寫 `msg ${m.role}` 會出 `msg user`，**永遠 match 唔到** —— 實測 390px 全部 bubble 都由 x=57 開始，用戶自己講嘅嘢同 AI 一樣靠左。`Chat.tsx` 一定要做 `role → me/coach` mapping。
- **`.thread` 係內部 scroll 容器，唔係 window scroll**：所以 `Chat.tsx` 要自己「跟住最新一句」（`useLayoutEffect` ＋ `onScroll` pinned ＋ `<img onLoad>`——相係 async 載入，載入完 scrollHeight 又變，唔重新 pin 就會停喺中間）。用戶自己向上睇歷史時**唔可以**搶佢位置。
- **高度鏈用 `html, body, #root, .app { height: 100% }`，唔用 `100dvh`**（2026-10-01 改）：dvh 係動態值，Chrome Android 喺 nested scroller（我哋 `.thread`）捲動時會收起 URL bar、dvh 跟住變，而 app 本身唔 scroll（`overflow: hidden`）→ re-layout 落後，底部 tab bar 下面就出現一條空位（用戶回報）。`%` 鏈跟 layout viewport 就唔會變。`viewport-fit=cover` 照留（`env(safe-area-inset-*)` 要用）。
- **Composer 係 auto-grow `<textarea>`，唔係 `<input>`**：`.compose textarea` 窄屏一樣要 16px（< 16px 會令 iOS Safari focus 時自動 zoom 成個 page）。高度由 `Chat.tsx` 量 `scrollHeight` 寫 inline style（上限 132px，之後自己 scroll），`.compose` 要 `align-items: flex-end`（唔係 center）。**Enter 送、Shift+Enter 換行，而且一定要擋 `e.nativeEvent.isComposing`** —— 中文輸入法確認候選字都會 fire Enter，唔擋就會誤送。placeholder 要短：長 placeholder 喺手機 16px 字會自己 wrap 成兩行，令輸入框一開就 72px 高。發送掣係圓形箭嘴 SVG（`.send`，送緊時換轉圈），冇文字。
- **`useLayout()` 只可以喺 `LayoutProvider` 嘅 child 讀**：App 本身 render provider，所以 layout 要喺 `LayoutHost`（provider 內）讀；喺 App body 讀 = 永遠 default `chat`（真實撞過，layout 切換會靜靜失效）。
- **App wrapper class 係 `app layout-<id>`**，唔好改做 `shell-<id>` —— `.shell-chat` 係 shell 內部 chat 場景 grid container，同名會撞壞成個 app grid（chat 佈局變兩欄）。
- **新結構嘅 data／動作一律用 hooks**：`hooks/useSummary`、`useCorrelations`、`useEntryActions`、`useInsightActions`（`refreshKey` 一 bump 就 re-fetch）；顯示 block 一律 `components/blocks.tsx`。改 API 只應該改一處。
- **`View` 有 `guide`**：`GuideView`（男士護膚基本資料）係一個 scene，唔係第 5 套 layout —— 由 Settings「指南」入口入，四個 shell 都要 render 佢（`ChatShell`/`StandardShell`/`MobileShell` 已經有）。所以加 scene 唔會改任何 tab 數。內容來自 `GET /api/guide`；`**粗體**` 係 `RichText` 手寫嘅極簡渲染（內容係我哋自己寫，唔係用戶輸入）；圖片係 CSS 佔位方塊，`figcaption` 有「未加圖片」標示，唔可以扮真圖。
- **`?layout=chat|journal|dash|mobile`**：URL preview override（唔會寫入偏好），demo／smoke 用。preview 生效期間喺 Settings 揀結構會**解除 preview**（`clearPreview()` 用 `replaceState` 清走參數）—— 唔做嘅話個 picker 會似壞咗。
- **新 home 畫面食真數據**：`JournalHome`／`DashHome`／`MobileHome` 用 `getSummary`／`getCorrelations`／`p.messages`（App 已載）；空態全部係「未有…」，唔可以放 demo 數。
- **guardrail 一定要掃 `Advice.reply`，唔止 `items`**：`reply` 係用戶真係睇到嘅 bubble（`frontend/src/App.tsx`：`res.advice.reply || res.analysis.summary`）。以前 `apply_guardrails` 同 `eval/safety.py` 都只掃 `items` —— 兩邊**同一個盲點**，所以互相照唔到。實測：同一句「每日口服抗生素 50mg」放 `items` 會被換成轉介訊息，放 `reply` 就原封不動送到用戶。改動集中在 `guardrails.advice_text()`／`contains_medical_advice()`，兩個 caller 共用，唔好再各自寫一次。
- **`MEDICAL_TERMS` 唔可以有 bare `"mg"`**：`contains_any` 係 substring，`"mg"` 會喺任何 ASCII 字中間命中；而修好 `reply` 之後掃描範圍由兩條 bullet 變成 2–5 句，false positive 面積大增。劑量改用 `DOSE_RE`（`\d+\s*(mg|mcg|µg|ug|iu)`，要有數字前綴）。**`g`／`ml` 故意唔收** —— 佢哋係包裝容量（「呢支 30g」），唔係劑量，商品評估會成日講。
- **eval scenario 一定要各自一個新 conversation**：`graph` 最後一定 `persist`，共用 conversation 會令 scenario 次序依賴（實測：第 2／3 個 scenario 永遠 `first_checkin=False`、memory confidence 0.60→0.65→0.70、`get_skin_profile` 回嘅 rows 係上一個 scenario 寫落嘅）。加／刪／重排一個 scenario 會改動其他。要覆蓋「已有記憶」嗰條路就用 `seed_days`，唔好靠洩漏。
- **`ingredients.py` 個字典係 SEED，唔係完成品**：目標係 ≥200 個、來源 IECIC（`docs/product-eval-plan.md` D4），而 corpus 只有 8 個成份撐得起。**唔好手寫成份名**（連中文名）—— 咁就係憑空造事實。每個有功效主張嘅 entry 都要有 `corpus="source :: title"` 引文，`tests/test_ingredients.py` 會對真 DB 逐條驗（CI 冇 `data/` 就 skip）。**引文一定要抄到完全一樣**（連尾句號）。
- **`MobileHome` 個環形進度係「今日記低咗幾個指標」（0–6），唔係膚況分數**：app **冇**「整體膚況分數」呢個概念（`index.css` 有 `.score` 嘅死 CSS，但 `RightPanel` 從來冇 render 過）。設計樣板 `design/mobile-1-soft-cards.html` 嗰個「膚況 2/3」係樣板自己發明 —— **唔可以照搬**（約定 #2／#10）。
- **`LayoutPicker` 用 `Record<LayoutId, JSX.Element>` 而唔係 `if`／`switch` chain**：以前用 chain，加第 4 個 id 會**靜靜** render dash 嗰個縮圖。用 Record 漏咗就編譯唔過。
- **test 唔可以打真 LLM**：`backend/.env` 有真 key，所以 `get_llm()` 會回真 adapter。`tests/conftest.py` 有個 autouse fixture patch **`OpenAICompatLLM._client` / `AnthropicLLM._client`** —— 唔 patch `get_llm`，因為幾個 module 用 `from … import get_llm` 各自持有 reference。呢個 guard 係撞過嘅：一個新 API test 令 suite 花咗 6 次真 API call（10.36s → 修好 0.30s）。要真 provider 一定要加 `@pytest.mark.no_real_llm_opt_out`。
- **引文比對要 normalize 空白**：corpus 嘅 `title` 含 non-breaking space（U+00A0，例如一條 PMC title 係 `Application\xa0of`）。`test_guide.py` / `test_ingredients.py` 用 `replace(title, char(160), ' ')` 再比對 —— 唔做就會為咗一個隱形字元而查唔到。
- **`app/guide.py` 嘅「應該用咩產品」係生成嘅，唔係手寫**：佢讀 `recommend.RULES`，所以指南同 agent 推薦唔可能唔一致。加／改規則要記住兩邊都會變。冇 corpus 來源嘅建議（例如「一次只加一樣新產品」）要**明確標明係 app 建議**，唔可以當文獻結論。
- **`TOOL_GUIDE` 嘅措辭係 load-bearing，唔可以寫成「你可以 call 呢啲工具」**：model 會當 `search_knowledge` 係可 call 嘅 function，DeepSeek 就真嘅 emit 一個咁名嘅 tool call → `OutputParserException: Unknown tool type` → consult 掛。**特別打中產品／成份問題**（model 最想用 `search_knowledge`）。現行寫法係「你唔可以 call 任何 function，只可以喺 `tool_calls` 欄位填字串」，`tests/test_observability.py` 有斷言封住。改措辭要保留「唔可以 call」同三個名。
- **`llm._invoke` 個 retry 一定要帶糾正訊息**：只重試同一組 messages 唔夠（實測連續兩次都失敗）。retry 時 append `FORMAT_CORRECTION`；最多 3 次；仍然失敗就拋俾 `service.run_consult` 轉成 **HTTP 503 可讀訊息**（唔好裸 500、唔好造假分析）。
- **macOS 冇 `timeout`**：要 `gtimeout`（coreutils）。我試過用 `timeout 120 python …` 做真-LLM 測試，三次都「失敗」—— 其實 exit 127 command not found，測試根本冇跑過。做 shell 測試要檢查 exit code，唔好只信「失敗/成功」字眼。
- **`Entry` 只喺個 turn 有皮膚證據時才寫**：閘係 `SkinAnalysis.observes_skin`（LLM 判）`or vision_used`。以前每條訊息都當打卡，而 `ANALYZE_SYSTEM` 話「未提及就畀 0」→ 問一句產品問題就會用**全 0** 覆蓋當日讀數，而且因為「一日只准一個 agent event」而將假「改善」**永久凍結**（真打卡之後都改唔返）。`persist` 唔過閘就只寫 `ChatMessage`，`entry_written: false` 會入 trace。
- **`observes_skin` 唔可以漏入 `advise` 嘅 prompt**：真 LLM 會將欄位名照讀返俾用戶（「分析顯示 observes_skin=false」），而且將「唔係打卡」誤讀成「睇唔到皮膚」→ 叫用戶補相、**完全冇答佢問嘅問題**。`build_advise_prompt` 一定要 `pop` 走佢，並用廣東話描述情況。同埋 onboarding 引導塊**只喺 `observed` 時**才出。
- **`imageio` 個 ffmpeg reader 只收真檔案路徑，唔收 `BytesIO`**（拆唔到，佢係 spawn 一個 ffmpeg subprocess 去讀檔）。而且 **writer 都唔收 BytesIO** —— 寫測試片一定要用 temp file。所以 `video.extract_frames()` 個簽名係 `(path)`，caller 要先 `save_video()` 落 disk。「本機儲片」呢個產品要求啱好同解碼器要求一致。
- **抽格一定要平均分佈，唔可以 `[:max_frames]`**：實測過 3 秒片出 0.0–1.3s（全部偏喺片頭）。用戶橫掃塊面，後面嘅格先係唔同部位。而家係喺 survivors 之中等距揀。
- **影片 endpoint 一定要串流寫落 disk**：唔可以用 `await file.read()` —— 20 秒 4K 可以 200MB+，一次過讀入 RAM 就 OOM。（上限係 100MB 而唔係無限，但仍然遠遠大過一個安全嘅 `read()`。）用 `while chunk := await file.read(1MB): out.write(chunk)`。超過 `COMPRESS_OVER_BYTES` 就 `compress_video()`（縮 1280px、CRF 26、`-an` 丟音軌）；**壓縮失敗唔可以令功能失敗**（保留原檔 + log + response 報 `compress_error`）。
- **`video.MAX_SECONDS = 20`、`MAX_FRAMES = 6`**：實測 30 秒 → 5.2 秒一格、20 秒 → 約 3.3 秒一格。⚠️ 覆蓋範圍取決於**鏡頭有冇移動**：一條 20 秒定鏡片只出 **1 張相**（全被當重複），一條 10 秒橫掃片出足 6 張。UI 一定要提示「鏡頭慢慢掃過成塊肌」。
- **商品評估有兩條入口，但只可以有一個定義**：`POST /api/conversations/{cid}/products/evaluate`（程式化）同 chat 入面貼成份表（`graph.tools` 偵測到就自動跑）。兩邊都要經 `app/agent/product_context.py`——分開砌 inputs 就會對「用邊個 profile 比對」有分歧，同 `guardrails` 以前掃 `items`／`reply` 兩個位係同一類 bug。`tests/test_product_eval_api.py::test_the_route_and_the_chat_path_agree` 封住。
- **貼成份表係「一條 chat turn」，唔係第二個 UI**：用戶決定唔要獨立商品評估畫面。所以 `graph.tools` node 會用 `ingredients.looks_like_ingredient_list()` 判斷，命中就跑 `evaluate_product`，`advise` 只負責覆述。`persist` 唔會寫 `Entry`（成份表唔算皮膚觀察），所以問產品永遠唔會變成「一日皮膚數據」。
- **`looks_like_ingredient_list()` 唔可以靠字典**：真 INCI 表有 20–40 項而 seed 字典得 31 個，靠「認得幾多個」判斷就會**漏掉所有真產品**。判斷要用結構（≥5 個逗號分隔嘅拉丁字 token、總字數 ≥40），`成份`／`INCI` marker 會降低門檻。**寧願漏（照平常答），唔好誤中（會用用戶冇貼過嘅成份嚟比對）**。實測 12 句廣東話口語 0 false positive。
- **`成份：Aqua, …` 個標籤會黐落第一個成份**：`parse_ingredients` 之前唔剝標籤，所以 `成份：Aqua` 變成唔認得 → 真 LLM 回覆「我認唔到第一個字『Aqua』…其實係水嚟嘅」。`ingredients.strip_list_marker()` 喺 `parse_ingredients` 入面做（所以兩條入口一齊修好），`Water (Aqua)` / `Aqua (Water)` 亦加咗做 `aqua` 嘅 alias。
- **`evaluate_product` 撞到處方成份時，`recognised` 都要清**：本來只清 `matched`／`missing`，但 `recognised` 會 render 成「產品嘅其他認得嘅功效成份」，喺 `avoid` 隔籬列一排保濕劑一樣係「大致冇事，得一粒唔得」嘅讀法（實測 `tretinoin` 嗰條 case 出 `('甘油','泛醇','尿囊素')`）。`unknown` **故意保留**——佢係老實嘅「我認唔到」，而硬停成份名本身就喺度報。
- **`graph.guardrail` 會用 `product_eval.escalate` 覆寫 `reply`**：模型可以照寫一句「呢支好溫和，早晚用得」。處方成份係 deterministic 硬停，所以 reply 會被換成程式算出嘅嗰句（會指名成份——安全，而且係用戶自己貼嘅，講出嚟更有用）。`trace.guardrail.forced_by_product_eval` 會記錄。
- **`MEDICAL_TERMS` 要同時有 `tretinoin` 同 `isotretinoin`**：`isotretinoin` 唔包含 `tretinoin`（反過來才對），只寫後者就會漏咗 topical tretinoin 產品。
- **`compress_video` 會改條片個名**：寫 `<id>.c.mp4` 而唔係 `<id>.mp4`。`video_file()` / `delete_video()` 兩個 spelling 都認；**唔好自己砌 `data_dir / v.path`**，否則壓縮過嘅片既搵唔到亦刪唔到（`DELETE` 會靜靜報「冇嘢刪」）。
- **大細上限係 100MB（`video.MAX_BYTES`），唔係「無限」**：文檔寫過「冇上限」係錯嘅。<40MB 原檔留、40–100MB 自動重編碼、>100MB 回 **413** 加可讀訊息。`check_size()` 係喺串流途中逐 1MB 驗，唔會先寫滿成個檔。
- **`export_zip()` 會 `rglob` 成個 data dir —— 所以一定要排除 cache**：片一直在 zip 入面（文檔寫過「唔包含片」係錯，`tests/test_export.py::test_export_includes_stored_clips` 封住）。但 **2026-10-05 實測**：fastembed 嘅 ONNX model cache 就住喺 `data/`（`SKINCOACH_EMBEDDER_CACHE_DIR=./data/.fastembed-cache`，另加一份 `.hf-cache`），所以「匯出數據」實際會行 **71 個檔案、1070.5 MB，其中 962 MB（90%）係同一個 235 MB model blob ×2**；ONNX 壓唔縮（deflate ratio 0.92），所以 `GET /api/export` **45 秒 0 bytes**（放到 50.5 秒才返），而 953 MB zip 建喺 heap 再被 `getvalue()` 複製一次 ≈ 1 GB。真 user data 只有 ~72 MB。
  而家：`EXPORT_SKIP_DIRS`（`.fastembed-cache`／`.hf-cache`／`__pycache__`／`.cache`）＋ `iter_export_zip()` 串流（temp file，1 MB 一 chunk）＋ route 用 `StreamingResponse` → 實測 **66.1 MB、5.6 秒**。
  ⚠️ 舊 test 捉唔到，因為三個 test 都係 `data_dir = tmp_path`（空目錄，`rglob` 瞬間完）。加 cache 相關嘢一定要喺 fixture **plant** 一個假 cache 落去。
  ⚠️ `skincoach.db.bak`（35.7 MB 舊快照）**故意留喺** archive（係真 user data），所以 66 MB 有一半係佢。
- **`delete_conversation` 一定要喺 cascade 之前收集檔案路徑**：`db.delete(c)` cascade 一行之後就冇嘢可以查。實測過冇呢步：上載一張相 → 刪 conversation → `.jpg` 仍然喺 disk（route docstring 寫住 "permanently delete … all its records"）。另外 `Video.frames` 入面嘅格係**未 attach 都可能存在**（用戶淨係上載冇問），所以 frame id 都要當檔案路徑刪。
- **Data fetch 唔重複**：只有 active shell 嘅 home 會 mount，每個 block 自己 fetch 一次就夠；`refreshKey` bump（send/delete 後）要令 home re-fetch（`JournalHome`/`DashHome` 已掛）。

## 現況（見 `docs/status-vs-claims.md` 最新狀態）

- Layer 1 已完成（Block 1–3 + frontend sync + eval/CI + docs）。
- Layer 2 已完成：rolling 多錨點 UI（`/summary.anchors`）、product 庫（products table）、diet trigger tagging、correlation detector（`app/correlation.py` + `/correlations`）、global scope 寫入（diet → global timeline Q31）、preference 低頻抽取（`app/preferences.py`）、check-in 自動 fact（product fact hook）、hybrid 接線（tools search_knowledge）。
- Layer 3：delete/edit UI（entry note / delete entry / delete photo / delete insight）已做；demo environment＋seed script（`scripts/seed_demo.py`）已做；Settings 測試連線已做；Docker compose 修復（nginx proxy / env 路徑 / corpus bake）見 status #18（狀態以 status-vs-claims 為準）；roadmap v2 同 blog/demo video 係 docs 層交付。
- Debug／observability：`state["trace"]` + `graph.stream()` + `/api/consult` 回 trace + `data/runs.jsonl`（`POST /api/consult` 同 `trace_consult.py` 都寫；`run_log_enabled` 預設 True，路徑 `./data/runs.jsonl` 跟 CWD）；`scripts/trace_consult.py` 一 command 睇 5 個 node；靜默失敗（vision／tool／embedder fallback）已改為 log + trace；`prompts.TOOL_GUIDE` 修好「真 LLM 唔識叫 tool」嘅結構性 bug（見 status #26）。
- UI 結構四選一（層面：介面結構）：`chat`（原本）／`journal`（皮膚日記 feed）／`dash`（進度儀表板）／`mobile`（手機版，**窄屏 ≤760px 自動**）—— Settings「介面結構」揀，`localStorage skc-layout` persist，`?layout=chat|journal|dash|mobile` 可 preview；四套共用同一批 view 元件（Chat / RecordsView / ProgressView / SettingsView + blocks），feature parity（詳 status-vs-claims #25）。手機版樣式揀咗 `design/mobile-1-soft-cards.html`（「柔卡」）；窄屏自動切換同桌面無回歸都用 CDP 實測過。

## Agent skills

### Issue tracker

Issues 同 spec 住喺 GitHub Issues（`shulaplai/male_skincare_agent`），一律用 `gh` CLI。See `docs/agents/issue-tracker.md`（連 `/wayfinder` 嘅 map／ticket／blocking／frontier 操作）。

**Wayfinder map**：`gh issue list --label wayfinder:map` 搵得到。而家有一個 in-flight 嘅 effort 喺度逐行審計 `docs/status-vs-claims.md` 嘅 claim —— **改 claims 表之前，先睇該 map 嘅 Decisions-so-far**，唔好當表上嘅 ✅ 已經獨立驗證過。

### Triage labels

五個 canonical triage role 用**預設名**（`needs-triage`／`needs-info`／`ready-for-agent`／`ready-for-human`／`wontfix`）。See `docs/agents/triage-labels.md`。⚠️ 呢批同 GitHub 預設嘅 `bug`／`enhancement` 係兩套嘢，唔好混。

### Domain docs

**Single-context**：`CONTEXT.md`（39 個詞、44 個 `_Avoid_` 清單）＋ `docs/adr/0001-0010` 喺 repo root，2026-10-05 用 `/domain-modeling` 建好。See `docs/agents/domain.md`。
⚠️ **寫新 code 之前先讀 `CONTEXT.md` 嘅 `_Avoid_` 清單**：每一個都係呢個 repo 真嘅撞過嘅混淆（`Metric` 唔係 `Attribute`；`scene` 唔係 `tab`；`severity` 唔係分數；一條片唔係六張相；consent 唔等於模糊）。`docs/adr/` 係**唔應該再被重新討論**嘅決定 —— 同 ADR 衝突就要明講，唔可以靜靜做返相反嘅事。
⚠️ `AGENTS.md` 呢個「陷阱」列表係**歷史**（真撞過嘅 bug），唔係規則；兩者以前混埋一齊，所以 `CONTEXT.md` 最後嗰節特別列出「呢個 domain 唔存在嘅嘢」。
