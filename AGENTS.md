# AGENTS.md — 畀（人類同 AI）開發者嘅 SkinCoach monorepo 指引

> 呢個係 monorepo（backend + frontend + docs）嘅工作指引。跟住佢改 code，可以減少破壞同走冤枉路。
> 上一代純前端版嘅指引喺 `archive/skinfile/AGENTS.md`（博物館，唔好喺度改）。

## 常用命令

```bash
# Backend（一定要喺 backend/ 度行，.env 由 CWD 讀）
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --port 8001   # dev server
./.venv/bin/python -m pytest -q                                   # 60 個 test，綠先算完成
./.venv/bin/python -m eval.run_eval --fake                        # deterministic eval（CI 用）
HF_HOME=./.hf-cache ./.venv/bin/python -m eval.run_eval           # 真 embedder + 有 key 時連埋 LLM-as-judge
./.venv/bin/python scripts/ingest_corpus.py                       # 重建 RAG corpus（chunks table）
./.venv/bin/python scripts/seed_demo.py                           # 起獨立 DEMO DB（唔掂真 data；見 README）

# Frontend
cd frontend
npm run typecheck    # tsc --noEmit，一定要過
npm run build        # typecheck + vite build
npm run dev          # :5173（proxy /api -> :8001，所以 backend 要同時行）
```

## 目錄結構速覽

| 路徑 | 內容 | 注意 |
|---|---|---|
| `backend/app/main.py` | FastAPI routes | 所有 API 都喺度；DB session 用 `get_session` |
| `backend/app/agent/` | LangGraph agent：`graph.py`（5 nodes）、`llm.py`（adapters + get_llm）、`prompts.py`（純函數）、`schemas.py`（Pydantic 合約）、`attributes.py`（固定 attribute schema + change detect）、`tools.py`（whitelist）、`guardrails.py`（deterministic） | 核心邏輯 |
| `backend/app/memory.py` | Memory 規則（decay / reconcile，tag+direction 語義 Q47） | pure functions；persist 喺 graph.py call |
| `backend/app/preferences.py` | 偏好低頻抽取（Q48）：diet trigger ≥3 日 / 產品 ≥3 日 → preference insight | deterministic；apply_events 後 call |
| `backend/app/correlation.py` | 相關性偵測（Q30）：cause episodes → attribute deltas，repeated = strong | deterministic；`/correlations` endpoint 用 |
| `backend/app/self_report.py` | 確認自報事件 → Entry/timeline/products/facts | diet 寫 **global** timeline（Q31）；product fact hook |
| `backend/app/rag/` | chunking / embeddings / vectorstore / hybrid / ingest | `hybrid.py` 已接線（`tools.search_knowledge` 用 `search_hybrid`） |
| `backend/app/models.py` | SQLAlchemy tables：users / conversations / entries / photos / insights / timeline_events / chat_messages / chunks | 加 column 要同步 `db.py` `_COLUMN_MIGRATIONS`（SQLite 唔會自動 ALTER） |
| `backend/app/db.py` | engine + `init_db()`（create_all + 輕量 ALTER migration） | init_db 唔會毀 data |
| `backend/eval/` | `run_eval.py` + `golden/`（committed 細 corpus）+ scenarios | eval 行 **temp DB**，唔好改返佢用 real DB |
| `backend/tests/` | pytest（而家 60 個） | 每加功能要有 test |
| `backend/corpus/` | 語料種子（zh basics + sources list）；大 corpus 喺 `data/corpus`（gitignored） | |
| `frontend/src/` | React：`App.tsx`（state 主控）、`components/`、`api.ts`（API 層）、`format.ts`（helpers）、`types.ts`（types） | server 係 source of truth，**冇 demo data** |
| `docs/` | architecture / roadmap / demo-script / blog-outline / eval-report-sample / status-vs-claims | 見 `docs/status-vs-claims.md` 對照 |
| `archive/skinfile/` | 上一代純前端 demo | 博物館，唔好改 |

## 設計約定（改 code 前先睇）

1. **Deterministic core 行先，LLM 只做模糊層**：guardrail、change detect、timeline 寫入、memory decay 全部係 code，唔好靠 prompt 求 LLM。LLM 只出現喺 `analyze`（睇相/文字出結構化分析）同 `advise`（出建議正文＋items）。
2. **固定 attribute schema（唔好自創）**：`attributes.py` 六個 key（acne/oiliness/redness/dryness/pores/texture）× 0–3 severity 係唯一真源；change detect、persist、timeline 全部食佢。加 attribute = 改 schema（versioned），唔係叫 LLM 自由發揮。
3. **型別合約**：所有 LLM 輸出強制 Pydantic schema（`schemas.py`）；唔好漏 free text。
4. **Privacy consent 唔可以繞過**：送相上雲前一定要 check conversation `cloud_analysis`；off 時只行純文字並喺 prompt 講明「有相但睇唔到」，唔好同 model 講「無相」。
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
- **Diet 事件係 global**（Q31）：`self_report.apply_events` 嘅 diet 寫 `conversation_id=NULL` timeline（唔係 conv-scoped）；`/summary` timeline = conv events + global events merge。搵 diet 事件記得 query `IS NULL` 都要包埋。
- **Delete/edit 係真 correction**：`DELETE /api/conversations/{cid}/entries/{eid}` 會連同日 conv timeline events 一齊刪（global 唔刪）；`DELETE /api/entries/{eid}/photos/{pid}` 係按 **path**（`photos/<pid>.jpg`）搵 Photo row，唔係 Photo.id；delete insight 前要清 `superseded_by` 指針。
- **eval 唔可以污染 dev DB**：`run_eval` 一定用自己 temp DB；見到佢寫入 `backend/data` 就係 bug。
- **FakeLLM 唔係「真 offline」**：冇 key 時 `service.run_consult` 仍然會 instantiate `FastembedEmbedder`（首次會 download model 或靜靜 fallback hash）。test 用 `DeterministicEmbedder`。
- **相片 id 有 shape check**：`photo.py` 只接受 32-char hex；`persist` 只 attach 真存在嘅相，唔好造 dangling Photo row。
- **Frontend draft 要 reset**：切 conversation 要清 draft/attached（`Chat.tsx` useEffect on conversation.id）。
- **Memory kind**：backend 用 `fact | derived | preference`；frontend `kindLabel` 要用 `preference` 唔係 `pref`。
- **DB 有真 key／真 data**：`backend/.env` 係真 DeepSeek key，`backend/data` 有真 corpus —— 開發時唔好 print key、唔好鏟 data dir。

## 現況（見 `docs/status-vs-claims.md` 最新狀態）

- Layer 1 已完成（Block 1–3 + frontend sync + eval/CI + docs）。
- Layer 2 已完成：rolling 多錨點 UI（`/summary.anchors`）、product 庫（products table）、diet trigger tagging、correlation detector（`app/correlation.py` + `/correlations`）、global scope 寫入（diet → global timeline Q31）、preference 低頻抽取（`app/preferences.py`）、check-in 自動 fact（product fact hook）、hybrid 接線（tools search_knowledge）。
- Layer 3：delete/edit UI（entry note / delete entry / delete photo / delete insight）已做；demo environment＋seed script（`scripts/seed_demo.py`）已做；Settings 測試連線已做；Docker compose 修復（nginx proxy / env 路徑 / corpus bake）見 status #18（狀態以 status-vs-claims 為準）；roadmap v2 同 blog/demo video 係 docs 層交付。
