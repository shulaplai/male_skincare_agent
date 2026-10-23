# SkinCoach：present 用嘅詳細 flow（結構、選型、實作細節、Q&A）

> 呢份係**講稿＋cheat sheet**，比 4 頁 PDF 詳細。每個數字都係由 code／DB／eval 實測得出，
> 冇一個係「大約」。present 之前掃一次 §10 嘅講稿，答問題用 §11。
>
> 更新日期：2026-10-23。驗證：`pytest` **373 passed**、`eval.run_eval --fake` **EXIT 0**、
> `npm run ui:check` **64 passed**（含 axe 淺/暗 12 scene）。

---

## 0. 一句話版本

> 一個**本機優先**嘅男士護膚顧問：每日對話 → 固定六項膚況指標 → 時間線／記憶 → 有出處嘅建議。
> 設計原則一句：**能用確定性程式解決的，不交給模型；能用本機解決的，不上雲。**

三個數字先聲奪人：

| 數字 | 意思 |
|---|---|
| **2** | 一次諮詢只打 **2 次** LLM（analyze 一次、advise 一次）；其餘 3 個 node 係純 code |
| **6** | 膚況 schema 永遠係 6 個 key × 0–3，唔會自由發揮 |
| **373 / 64** | 後端 373 個 test、前端 64 個 UI test（snapshot ＋ axe 淺/暗） |

---

## 1. 專案結構

```
male_skincare_agent/
├─ backend/                    FastAPI + LangGraph；單一 process
│  ├─ app/main.py              32 個 route（consult／summary／entries／photos／products／
│  │                           videos／guide／persona／correlations／settings／delete…）
│  ├─ app/models.py            SQLAlchemy：users / conversations / entries / photos /
│  │                           insights / timeline_events / chat_messages / products /
│  │                           videos / chunks
│  ├─ app/db.py                engine + init_db()：create_all ＋ 手寫 ALTER migration
│  ├─ app/agent/
│  │  ├─ graph.py              5 個 node：analyze → tools → advise → guardrail → persist
│  │  ├─ schemas.py            Pydantic 合約（LLM 唯一出口）
│  │  ├─ prompts.py            純函數：state → messages（唔掂 DB、唔掂網絡）
│  │  ├─ attributes.py         6-key schema ＋ change detect
│  │  ├─ tools.py              whitelist 3 個 tool（search_knowledge／get_skin_profile／…）
│  │  ├─ guardrails.py         確定性醫療安全閘（scan title＋reply＋items）
│  │  ├─ llm.py                adapter ＋ get_llm() ＋ FakeLLM ＋ 格式重試
│  │  ├─ service.py            route 同 graph 之間：consent 閘、clip 解析、503 轉換
│  │  ├─ recommend.py          7 條規則 → 主選／次選成分（指南同 agent 共用）
│  │  ├─ ingredients.py        成份正規化 ＋ 31 條有引文嘅 seed 字典
│  │  └─ product_eval.py       貼上產品 → coverage／verdict／conflict
│  ├─ app/rag/                 chunking / embeddings / vectorstore / hybrid / ingest
│  ├─ app/video.py             影片：probe／抽格／壓縮（≤20s、≤6 格）
│  ├─ app/persona.py           顧問人設（DB 存、有 safety line 唔可以蓋過）
│  ├─ app/greeting.py          主動問候文案（09:00／21:00、每日上限 2、23:00–08:00 靜音）
│  ├─ app/scheduler.py         每 60 秒 tick 一次；只有真 LLM 才寫
│  ├─ app/guide.py             「男士護膚基本資料」（Pydantic 樹 ＋ 每句 citations）
│  ├─ eval/                    run_eval ＋ golden corpus ＋ scenarios ＋ judge
│  ├─ tests/                   41 個 test 檔、373 個 test
│  └─ scripts/                 ingest_corpus / seed_demo / trace_consult / repair_clip_entry
├─ frontend/                   React 18 + Vite 5 + TS
│  ├─ src/App.tsx              state 主控（conversation／messages／summary）
│  ├─ src/api.ts               API 層（唯一 fetch 出口）
│  ├─ src/hooks/               useSummary / useCorrelations / useEntryActions …
│  ├─ src/components/          Chat / RecordsView / ProgressView / SettingsView / GuideView
│  ├─ src/layouts/             4 套 layout：chat / journal / dash / mobile
│  ├─ src/styles/tokens.css    設計 token（type scale／spacing／radius／elevation／line）
│  └─ tests/ui/                7 個 Playwright spec、64 個 test、41 張 snapshot
├─ docs/                       架構／backend-flow／roadmap／eval／open-findings／PDF
└─ design/                     靜態設計樣板（唔喺 build 範圍）
```

**三層，方向單一**：`React（顯示）→ /api → FastAPI route → service → LangGraph → SQLite`。
冇 ORM 魔法、冇第二個 backend service、冇 message queue。

---

## 2. 一個 turn 由頭到尾（10 步）

1. **前端送請求** — `POST /api/consult`（`{conversation_id, text, photo_paths?, video_id?}`）。
2. **route 檢 consent** — `service.open_consult()`（`service.py:91`）：
   `cloud_analysis = conversation.cloud_analysis AND user.photo_cloud_consent`（`:108`）。
   相如果唔准出機，就**唔會**放入 `photo_paths`，同時喺 prompt 講「有相但睇唔到」（唔可以講「無相」）。
3. **組 state** — `_consult_state()` 讀 conversation、最後 N 條 message、summary、memory lines、persona；
   如果有 `video_id`，`resolve_clip_frames()` 由 `Video.frames` 砌返 `photo_paths`（抽格已經喺上傳時做）。
4. **`analyze` node（LLM #1）** — 文字＋（准許時）圖片 → `SkinAnalysis`：
   `summary`、6 個 attribute（0–3）、`observes_skin`、`tool_calls[]`（**字串**，唔係 function call）。
5. **`tools` node（純 code）** — 執行 whitelist 三個 tool：
   - `search_knowledge` → `search_hybrid()`（RAG）
   - `get_skin_profile` → 過去 N 日 Entry
   - `get_recent_entries` → 最近幾日 Entry（tool 只讀，唔寫）
   貼上一大段 INCI 成份表 → `ingredients.looks_like_ingredient_list()` 偵測 → 直接計 coverage。
6. **`advise` node（LLM #2）** — 輸入：analysis ＋ tool 結果 ＋ memory ＋ persona ＋（如果係產品問題）已計好嘅事實。
   輸出 `Advice{title, reply, items[]}`：一句標題、2–5 句正文、2–5 個項目。
7. **`guardrail` node（純 code）** — `DOSE_RE`／`MEDICAL_TERMS` 掃 **title＋reply＋items**；
   中咗就整段換成轉介訊息（唔係刪一句），`escalate=True`。
8. **`persist` node（純 code）** — **只有 `observes_skin or vision_used` 才寫 Entry**；
   寫 Entry＋attributes＋timeline event＋insight；否則只寫 `ChatMessage`（`entry_written: false`）。
9. **回 response** — `{reply, analysis, advice, trace}`；前端逐段顯示（標題 → 正文打字 → 分析卡）。
10. **run log** — `data/runs.jsonl` 逐行記 node／ms／摘要／tool_calls／vision 狀態（debug 同成本審計）。

`state["trace"]` 係 `Annotated[list, operator.add]`，每個 node append 一筆 → `graph.stream()` 可以逐步出 delta。

---

## 3. 為什麼係呢套 stack（每項：目標 → 揀咗 → 唔揀咩 → 代價）

### 3.1 LangGraph（5-node 線性 graph）

- **目標**：LLM 只出現喺模糊層，同時要「睇得到每一步」。
- **揀咗**：LangGraph 嘅 graph ＋ typed state。
  - 每個 node 只經 state 通訊 → **可以逐個 node 單獨測**（pytest 直接 import，唔使起 server）。
  - `graph.stream()` 每步出 delta → 前端／trace 睇到行到邊，出事唔會靜靜死。
  - 「邊步用 LLM」變成結構（analyze／advise），唔係散喺 `if` 裡面。
- **唔揀**：
  - 一條手寫 function chain → 冇 trace／冇 stream／冇 per-node 計時，debug 靠 print。
  - autonomous agent（多 agent 自由決定用咩 tool、幾時停）→ 5 步固定反而**可審計**；
    自由決策就答唔到「呢個數點解寫咗入去」。
- **代價**：多一個框架依賴；linear graph 用框架有點重 —— 但換來 trace／stream／state 合約。

### 3.2 SQLite（＋ SQLAlchemy）

- **目標**：單用戶、本機、隱私（唔上雲）。
- **揀咗**：單檔 DB，`cp data/skincoach.db` 就係備份；`create_all` ＋ 手寫 `_COLUMN_MIGRATIONS`（`db.py:33`）令舊 DB 唔需要鏟。
- **唔揀**：Postgres／Supabase → 要 server、要網絡、同「資料只存呢部機」矛盾。
- **代價**：**冇開 WAL**（用預設 rollback journal），並發寫入係已知限制；換多人部署要換 DB。

### 3.3 Pydantic 合約

- **目標**：LLM 輸出唔可以係 free text。
- **揀咗**：`SkinAnalysis`／`Advice`／`ProductNarrative`… 全部 schema；persist／前端／eval 三邊都唔會見到「半結構」字串。
- **代價**：schema 一改要三處同步；Pydantic 有 JSON-schema cache（改 `FieldInfo.description` 唔會影響已建 schema —— 撞過）。

### 3.4 fastembed（MiniLM 384d）＋ hybrid 檢索

- **目標**：RAG 要跑得喺本機、冇 API 成本，而且中文 query 要搵到英文文獻。
- **揀咗**：`fastembed` MiniLM（384 維、CPU 夠快）＋ 語意召回後**關鍵字 re-rank**。
- **唔揀**：OpenAI embeddings（要 key、要上雲、每次查詢都付費）；純 BM25（中文 query vs 英文文獻完全對唔上）。
- **代價**：384 維表達力有限；hash fallback（128 維）同真維度**唔可以混**（`vectorstore` 會 raise／跳過並 log）。

### 3.5 React 18 ＋ Vite ＋ TypeScript

- **目標**：四套 layout（chat／journal／dash／mobile）但**功能完全一致**。
- **揀咗**：共用 hooks＋共用 blocks；layout 只係「排位」，資料層一份。
- **唔揀**：四套獨立 app → 四份 bug。
- **代價**：CSS 有 4 套 shell 嘅 override，`@media` 同步要人手（撞過 specificity bug）。

### 3.6 DeepSeek V4.1-flash

- **目標**：香港可直接連、又要睇相。
- **揀咗**：同一個 model 接受文字＋圖片（1M context），所以 analyze 唔需要兩個 adapter。
- **唔揀**：Anthropic／OpenAI —— **實測香港直連係 403**。
- **代價**：`thinking` 預設開會令 structured output 400，所以 `_client()` 要關 thinking（`{"type":"disabled"}`，寫 `"off"` 都 400）；model id 會變（`deepseek-v4-flash` 已變成 alias，現時 list 只有 `deepseek-flash`）。

---

## 4. RAG：切幾多、重疊幾多、點 rerank

### 4.1 切塊（`backend/app/rag/chunking.py`）

- `chunk_text(text, chunk_size=500, overlap=80)` —— **500 字、重疊 80 字**。
- **句子感知**：`_SENT_BOUNDARY = (?<=[。！？；;])\s* | (?<=[.!?])\s+`
  → ASCII 句號只喺**後接空白**時才切，所以 `0.5%`、`e.g.` 唔會被切開。
- 逐句打包到 500 字，滿了就開新 chunk，並將上一 chunk 最後 80 字接去新 chunk 開頭（boundary 唔會斷上下文）。
- `overlap >= chunk_size` 時 fallback 去 `chunk_size // 4`（防止無限重複）。
- **為什麼係 500／80**：embedder 嘅有效 context 係 512 token；500 字（中文為主）大約安全；
  80 字 ≈ 一至兩句，夠保住跨 chunk 嘅指代。
- **一個真 bug（講得出口）**：原本 regex 漏咗 ASCII `.`，88% 英文 corpus（PMC XML）**完全唔切**，
  chunk 平均 ~2,500 字、最長 ~53k，遠超 embedder 512-token 截斷 → 大部分英文內容**永遠檢索唔到**。
  修好之後才有句子邊界。
- **⚠️ 已知未做（照實講）**：`data/` 嘅 corpus **未重新 ingest**，所以現時 `chunks` 表仲有舊長 chunk：
  **3,220 條、218 個 source**，長度 p50 = **800**、p90 = **6,472**、max = **53,172**，**1,864 條 > 512 字**。
  切法已修，但要跑 `scripts/ingest_corpus.py` 才套用到。eval 用 `eval/golden/` 細 corpus（已用新切法），所以 eval 數字係乾淨嘅。

### 4.2 檢索（`backend/app/rag/hybrid.py`）—— rerank 就係呢 10 行

```python
RECALL_K = 80      # 先用語意取 80 條
BOOST    = 0.18    # 每條最多加 0.18

sem = semantic_search(session, embedder.embed(query), top_k=RECALL_K)
for c, cos in sem:
    overlap = |q_tokens ∩ c_tokens| / |q_tokens|
    score   = cos + BOOST * min(overlap, 1.0)
sort by score desc → top_k（預設 5）
```

- `_tokenize`：拉丁字母數字 token ＋**中文 bigram**（`zh[i:i+2]`）—— 中文冇空格，bigram 係最便宜嘅近似。
- **為什麼唔用 RRF（rank fusion）**：RRF 會令「純關鍵字命中但語意唔關事」嘅 chunk 冲入結果；
  BM25 喺中文＋英文混合嘅 corpus 會 flood。所以**只喺語意 top-80 之內**加分，唔會無中生有。
- **為什麼 boost 係 0.18**：cosine 一般 0.3–0.8；0.18 足夠令「同語言、字面命中」嘅 chunk 跳一兩位，
  但唔會蓋過語意差好遠嘅錯配（0.18 < 半個 cosine 差距）。
- **兩條路徑、兩組數字**（同一 golden set）：
  - 純語意 baseline：recall@3 **100%**、MRR **0.90**
  - runtime hybrid：recall@3 **100%**、MRR **1.00**
  → hybrid 冇令 recall 變差，但令正確 chunk 排得更前（MRR 0.90 → 1.00）。
- **為什麼要量兩邊**：eval 用純語意，runtime 用 hybrid。如果只量 runtime，就分唔清「檢索好」定「re-rank 掩蓋咗檢索差」。

### 4.3 入 DB

`ingest_file` → `chunk_text` → `embedder.embed` → `vectorstore.add_chunks`（SQLite 一張 `chunks` 表，embedding 存 JSON）。
檢索時 `search()` 讀全部再 cosine —— 3,220 條唔需要 ANN；再大就要換（照實講）。

---

## 5. Eval 係點整（`backend/eval/`）

**三個獨立部分，最後用 exit code 做 gate：**

1. **RAG recall**（`rag_recall.py`）：5 條 query（oily／dry／salicylic／rosacea／sunscreen），
   每條有 `expected_source`；計 recall@3 同 MRR。**跑兩次**：純語意（baseline）＋ hybrid（runtime）。
2. **Agent scenarios**（`agent_eval.py` ＋ `scenarios.json`）：4 個 scenario
   （`acne_normal`／`dry_normal`／`red_flag`／`returning_user`）。
   每個 assert：`expect_tool`（有冇真係叫 tool）、`expect_escalate`（紅旗要轉介）、
   `violations`（有冇藥名／劑量）、`first_checkin`。
   **每個 scenario 開一個新 conversation** —— 共用會令次序依賴（撞過：第 2／3 個 scenario 永遠 `first_checkin=False`）。
   要「已有記憶」嘅路徑就用 `seed_days`，唔好靠上一個 scenario 漏出嚟。
3. **Safety**（`safety.py`）：掃 title＋reply＋items；同 runtime **共用同一個 helper**（唔可以兩邊各寫一次）。

**設計上嘅三個堅持：**

- **隔離**：eval 永遠用 temp DB ＋ `eval/golden/`（committed），**唔會掂** `data/skincoach.db`；所以由 clean clone 都重現到。
- **Gate 唔可以空轉**：`rag_scenarios.json` 或 `scenarios.json` 係空 → **exit 1**，因為「a gate over zero cases proves nothing」。
  刪 golden 檔 = FAIL，唔係「零個 case 全綠」。
- **--fake 模式**：`FakeLLM` ＋ `DeterministicEmbedder`，冇網絡、冇 key、數字穩定 → CI 用；
  `judge_advice`（LLM-as-judge）只在有真 key 時跑。

**Mutation 測試（我點證明 gate 真係會紅）**：故意改壞 `chunking` 嘅句子邊界、或者令 hybrid 回空
→ recall gate 即刻 FAIL；修返才綠。呢個習慣用喺所有新 guard（例如「空分析卡」test：拆一個 guard 唔紅、
拆兩個才紅 → 證明兩層都真係擋住）。

**CI 命令**：`python -m eval.run_eval --fake`（exit code gate）＋ `pytest -q` ＋ `npm run ui:check`。

---

## 6. Backend 有咩特別處理

1. **Privacy consent 係 code gate，唔係 prompt 請求**：`cloud_analysis = conv.cloud_analysis AND user.photo_cloud_consent`；
   off 時**相唔會離機**，而且 prompt 講「有相但睇唔到」（唔講「無相」，否則模型會亂講）。
2. **相片預設模糊**：前端所有出相都要經 `BlurPhoto`（click 才清楚）；`AGENTS.md` 寫明「加新 UI 出相前問一句：呢張相有冇經 BlurPhoto？」。
3. **影片上傳串流寫 disk**：`while chunk := await file.read(1024*1024)`，每 1MB 驗大細（≤100MB）——
   唔可以 `await file.read()` 一次過讀入 RAM（20 秒 4K 可以 200MB+）。>40MB 自動重編碼（1280px／CRF 26／丟音軌），壓縮失敗唔令功能失敗。
4. **Migration 手寫但安全**：`create_all` 唔會 ALTER 舊表 → `_COLUMN_MIGRATIONS` 逐欄 `ALTER TABLE ADD COLUMN`；
   另有 column shape 改變嘅 `_rebuild_stale_nullables()`。**唔會叫人鏟 DB**。
5. **Delete 係真 delete**：刪 conversation 要先收集 photo／video 路徑，**再** cascade（否則檔案永遠留喺 disk）；刪 entry 會連嗰日 conv-scoped timeline event 一齊刪（global 唔刪）。
6. **Guardrail 掃 title＋reply＋items**：最初只掃 items，實測同一句「每日口服抗生素 50mg」放 reply 就原封不動送到用戶。
   `"mg"` 唔可以放喺 `MEDICAL_TERMS`（substring 會誤中）；劑量用 `DOSE_RE`。
7. **LLM 格式失敗有重試**：`_invoke` 最多 3 次，每次 append `FORMAT_CORRECTION`（只重試同一組 messages 冇用，實測連兩次都失敗）；
   最終失敗 → route 回 **HTTP 503 可讀訊息**（唔好裸 500、唔好造假分析）。
8. **每個 node 都留 trace**：`state["trace"]`、`graph.stream()`、`data/runs.jsonl`；tool 例外／vision fallback／embedder fallback 全部 log＋入 trace（唔可以靜靜吞）。
9. **`observes_skin` 閘**：唔係每個 turn 都寫 Entry。判據交俾 LLM（關鍵詞列表分唔開「呢支會唔會令我爆瘡？」同「下巴爆咗兩粒」），但**寫唔寫落 DB 係 code 決定**。
10. **Global vs conv-scoped timeline**：飲食事件寫 global（`conversation_id=NULL`），`/summary` 合併兩者。

---

## 7. Frontend 有咩特別處理

1. **四套 layout，一份資料層**：`layouts/defs.ts`（純 data ＋ `resolveLayout` 純函數）／`Shells.tsx`（registry）／`ChatShell`／`StandardShell`／`MobileShell`。
   窄屏自動切 `mobile`（`MOBILE_MAX_WIDTH = 760`），但**唔會**將 `mobile` 寫入 localStorage。
2. **設計 token 強制**：type scale 12/14/16/18/20/24/30/36、spacing 4 基數、radius 5 級、elevation 4 級；
   控件邊界用 `--line-strong`（3.67:1），裝飾線才用 `--line`。
3. **三段式回覆**：標題即出 → 正文逐字（~1.3 秒）→ 分析卡最後才 render；`prefers-reduced-motion` 即出全句。
4. **零內部資訊外洩**：`vision_used`／`provenance`／model 名只入 payload／run log，**唔出 badge**（用戶要求；有 test 封住）。
5. **空狀態唔造假**：冇數據就「未有記錄」，冇「今日膚況 2/3」呢種 demo 數；首頁日期用 `isToday()` 判斷，唔係假設第一條就係今日。
6. **手機細節**：`100dvh`（唔用 `100vh`，否則底部 tab bar 縮落 browser chrome）、`env(safe-area-inset-bottom)`、input 16px（否則 iOS 自動 zoom）。
7. **Accessibility 係 gate**：axe 掃 12 個 scene × 淺/暗；選中狀態唔可以只靠顏色（`aria-pressed` ＋「使用中」label）。
8. **UI gate**：`npm run ui:check` = typecheck ＋ eslint ＋ stylelint ＋ Playwright（41 張 snapshot ＋ axe ＋ 互動 ＋ 照片模糊 ＋ consult streaming）。

---

## 8. Test 有咩特別

- **373 個 backend test、41 個檔**；唔係「有 coverage」而係**每個真 bug 都有 regression test**。
- **唔准打真 API**：`tests/conftest.py` autouse fixture patch `OpenAICompatLLM._client`／`AnthropicLLM._client`
  —— 因為 `backend/.env` 有真 key，`get_llm()` 會回真 adapter（撞過：一個新 test 令 suite 花咗 6 次真 call、10.36s → 修好 0.30s）。
- **FakeLLM 唔等於「offline 安全」**：冇 key 時 `run_consult` 仍然會 instantiate `FastembedEmbedder`（首次 download）；
  test 用 `DeterministicEmbedder`。`FakeLLM` 亦係「false green」來源之一（硬編碼 tool_calls、永遠唔會 format error）。
- **真 LLM 測試要另外做**：改 prompt／tool 措辭之後，我用 `scripts/trace_consult.py --real` 同真 DeepSeek 跑過
  （實測：舊 `TOOL_GUIDE` 措辭令 model emit 真 function call → `OutputParserException: Unknown tool type`，產品問題 5/7 掛）。
- **Migration 有 test**：`tests/test_memory_guards.py::EXPECTED_LATE_COLUMNS` 斷言舊 DB 會被補欄。

---

## 9. 難題：真正撞過嘅 5 個（如果有 Q&A 時間，講呢幾個最有力）

1. **「每個 turn 都當打卡」** → 問一句產品問題就用全 0 覆蓋當日讀數，而且一日一個 agent event 令假「改善」**永久凍結**。
   修法：`observes_skin` 閘（LLM 判）＋ vision_used。
2. **`TOOL_GUIDE` 措辭令真 model 呼叫唔存在嘅 function** → 產品／成份問題最容易中；修法：明寫「你唔可以 call 任何 function，只可以喺 tool_calls 填字串」＋ 格式重試 ＋ 503。
3. **影片「已睇」係假嘅**：前端只送 clip metadata，冇 photo_paths → vision 從來冇跑，模型靠 `note` 作數。
   修法：`resolve_clip_frames()` 由 Video.frames 砌相 ＋ prompt 講清「你冇睇過」；再用 `repair_clip_entry.py` 真格重跑覆寫當日（dry-run 預設）。
4. **長 chunk 令 RAG 半盲**：regex 漏 ASCII 句號 → 英文文獻冇切 → 超出 512 token 截斷。
5. **eval 自己會洩漏**：scenario 共用 conversation → 第 2 個 scenario 永遠 `first_checkin=False`、memory confidence 逐個升。
   修法：每個 scenario 新 conversation ＋ `seed_days`。

---

## 10. 5 分鐘講稿（照讀都可以）

> 「呢個係一個男士護膚顧問。它解決嘅問題係：用戶每日講一句『今日塊面點』，我要將它變成可以比較嘅數據，而唔係每次都由零開始。」
>
> 「Flow 係 5 步：analyze 睇文字同相，出六項指標；tools 去 RAG 同記憶攞事實；advise 寫建議；guardrail 用 code 擋醫療風險；persist 決定寫唔寫入 DB。整個 flow 只有 2 次 LLM call，其餘 3 步係純程式 —— 因為『呢句算唔算打卡』、『有冇講藥名』呢啲問題，用 code 判比用 prompt 求可靠。」
>
> 「RAG 切 500 字、重疊 80 字，句子邊界切；檢索先語意取 80 條，再用中文 bigram 同英文字重疊加分 0.18 做 re-rank —— 因為純語意會漏『煙酰胺』呢類專有名詞，但 RRF 又會令關鍵字 flood 蓋過語意。實測 MRR 由 0.90 升到 1.00，recall 唔變。」
>
> 「Eval 用 temp DB ＋ committed golden corpus，量兩組 recall、4 個 agent scenario、同 safety；exit code 就係 gate。我特意加咗『golden 空 = FAIL』，因為零個 case 嘅全綠證明唔到任何事。」
>
> 「隱私係 code gate：consent off，相唔會離開部機，而且 prompt 會講『有相但睇唔到』；UI 預設模糊。」
>
> 「373 個 backend test、64 個 UI test，每個真 bug 都有一條 regression。多謝。」

---

## 11. Q&A 準備（15 條）

| 問題 | 答 |
|---|---|
| 為什麼唔用 OpenAI／Claude？ | 香港直連 403（實測）；DeepSeek 可直連、同一個 model 收文字＋圖。 |
| 為什麼唔用 vector DB（Pinecone／Chroma）？ | 3,220 條 chunk、單機、要離線；SQLite 一張表 ＋ cosine 夠。再大才換 ANN。 |
| 為什麼 chunk 500／overlap 80？ | embedder 有效 512 token；80 字≈1–2 句，夠保住跨 chunk 指代。 |
| 為什麼 hybrid 唔用 RRF／BM25？ | RRF 會令關鍵字命中但語意唔關事嘅 chunk 冲入；BM25 中文 query 打英文 corpus 會 flood。只喺語意 top-80 內加分。 |
| rerank 用咩 model？ | 冇用 cross-encoder；用 token overlap 加權（0.18）。省成本、可解釋；代價係語意近但字面唔同嘅唔會加分。 |
| recall 100% 係唔係太理想？ | golden set 只有 5 條 query、每條 1 個 expected source —— 係 smoke gate，唔係 benchmark。要更大就要擴 scenario。 |
| eval 同 unit test 有咩分別？ | unit test 測「一個 function 啱唔啱」；eval 測「整條 pipeline 出嚟嘅建議安唔安全、有冇叫 tool、RAG 有冇中」。 |
| 為什麼唔係每個 turn 都寫 Entry？ | 產品問題唔係打卡；以前會用全 0 覆蓋當日讀數、仲會永久凍結假 timeline。 |
| LLM 輸出格式錯點算？ | 重試 3 次（帶糾正訊息），仍然錯 → 503 可讀訊息，唔造假分析。 |
| 記憶（Insight）點運作？ | deterministic：tag＋direction 相同 → strengthen（confidence 升）；direction 反轉 → supersede；有 decay。LLM 唔參與。 |
| 六項指標為什麼係 0–3？ | 夠粗到唔會假精確；夠細分到分「冇／輕／中／明顯」。 |
| 隱私點保證？ | consent 係 code gate；相唔離機 ＋ prompt 講明；UI 模糊；`data/` 唔入 git。 |
| 多用戶／部署？ | 未做；SQLite 單檔、`user_id` 已在 schema。要換 DB＋auth＋per-user consent。 |
| 為什麼 test 數咁多？ | 373 個裡面大部分係 regression：每個真 bug 一條，防止「修好又壞返」。 |
| 最大技術債？ | corpus 未重新 ingest（舊長 chunk）；`chunks.section` 係 plumbing-only；SQLite 冇 WAL／單機限制。 |

---

## 12. Cheat sheet（present 前 30 秒掃一次）

| 項目 | 值 |
|---|---|
| Nodes | analyze → tools → advise → guardrail → persist |
| LLM calls / consult | 2（analyze、advise） |
| Attributes | acne／oiliness／redness／dryness／pores／texture × 0–3 |
| Chunk | 500 字、overlap 80、句子邊界 |
| Hybrid | RECALL_K 80、BOOST 0.18、中文 bigram |
| Recall | semantic 100% / MRR 0.90；hybrid 100% / MRR 1.00 |
| Corpus（dev DB） | 3,220 chunks、218 sources、p50 800、1,864 條 >512 字（舊 ingest） |
| Eval | temp DB ＋ golden；空 golden = exit 1；scenario 各自新 conversation |
| Tests | 373 backend（41 檔）、64 UI（41 snapshot ＋ axe 12×2） |
| Routes | 32 個 FastAPI route |
| Video | ≤20s、≤6 格、≤100MB、>40MB 壓 1280px/CRF 26 |
| Guardrail | 掃 title＋reply＋items；`DOSE_RE` 要數字前綴 |
| Greeting | 09:00／21:00、每日上限 2、23:00–08:00 靜音、fake 唔寫 |
