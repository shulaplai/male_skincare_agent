# SkinCoach Backend

Local-first 男性護膚 AI coach 嘅 backend：FastAPI + LangGraph agent + SQLite（RAG + memory + diary）+ eval harness。

## 快速開始

```bash
# backend/ 度行（.env 由 CWD 讀）
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # 填 key（冇 key 都行到：FakeLLM + hash embedder）
./.venv/bin/python -m uvicorn app.main:app --reload --port 8001

# 健康檢查
curl http://localhost:8001/health        # {"status":"ok","llm_provider":"deepseek"}

# 前端一齊跑（可選）
cd ../frontend && npm run dev            # http://localhost:5173（proxy /api -> 8001）

# 想睇有數據嘅 UI（interview demo）——獨立 DEMO DB，唔掂真 data
./.venv/bin/python scripts/seed_demo.py
SKINCOACH_DATABASE_URL=sqlite:///./data/demo.db ./.venv/bin/python -m uvicorn app.main:app --port 8001
```

第一次 startup 會 `init_db()`：建表 + 自動加新 column（`db.py._COLUMN_MIGRATIONS`，唔會鏟 data）。

## Config（`backend/.env`，全部 `SKINCOACH_` 前綴）

| Env | 預設 | 說明 |
|---|---|---|
| `SKINCOACH_LLM_PROVIDER` | `deepseek` | `deepseek \| anthropic \| openai`（HK 直連得 DeepSeek；Anthropic/OpenAI 香港係 403） |
| `SKINCOACH_DEEPSEEK_API_KEY` | — | 真 key 只喺本地 `.env`，唔好 commit |
| `SKINCOACH_DEEPSEEK_TEXT_MODEL` | `deepseek-v4-flash` | advise／text 用 |
| `SKINCOACH_DEEPSEEK_VISION_MODEL` | `deepseek-v4-flash-vision-exp` | analyze 睇相用 |
| `SKINCOACH_ANTHROPIC_MODEL` / `SKINCOACH_OPENAI_MODEL` | `claude-sonnet-5` / `gpt-5` | 其他 provider（要自己 set key） |
| `SKINCOACH_CLOUD_ANALYSIS_DEFAULT` | `false` | 新 conversation 嘅雲分析默認（self-hoster 可 set `true`） |
| `SKINCOACH_DATABASE_URL` | `sqlite:///./data/skincoach.db` | data 全部喺 `data/` |

> ⚠️ Model id 唔好用 legacy 名（`deepseek-chat` 2026-07 已退役）。DeepSeek V4 預設 thinking mode 會令 structured output 400 —— adapter 已自動加 `thinking: {type: disabled}`，唔好移除。

## 架構速覽

```
POST /api/consult  ──►  LangGraph：analyze → tools → advise → guardrail → persist
                            analyze   ：有相＋cloud consent → vision model（deepseek-v4-flash-vision-exp）
                                        否則 text model 純文字（標明「未睇相」）
                            tools     ：whitelist（get_skin_profile / get_recent_entries / search_knowledge）
                                        profile 包括 global-scope insights（Q31）；knowledge 用 hybrid retrieval
                                        + load 最近 10 條 chat messages 做 context
                            advise    ：出 Advice{reply（正文 2–5 句）, items, detected_events}
                            guardrail ：deterministic（紅旗 → 轉介；藥物詞 → 唔俾建議；自動 disclaimer）
                            persist   ：upsert 當日 Entry（attributes/metrics/photos）
                                        + deterministic change detect → timeline event（sparse）
                                        + per-attribute derived memory（tag+direction reconcile）
                                        + 寫 ChatMessage（user + coach，reload 唔會清空）
```

- **固定 attribute schema**：`agent/attributes.py` —— 六個 key（acne/oiliness/redness/dryness/pores/texture）× 0–3 severity，change detect／timeline／memory 全部食同一個 schema。
- **Memory**：`insights` table（fact / derived / preference）+ `memory.py` reconcile。derived **per-attribute**：tag = attribute，direction = problem（≥2）／normal（≤1）；同 tag 同 direction → strengthen（confidence 升、expiry 延長、text 更新）；flip → supersede（version+1）。30 日 expiry。
- **Self-report 事件**（`self_report.py`，Q49/Q51）：用戶 confirm 先落 DB。diet → 當日 `Entry.diet` + **global** timeline event（`conversation_id=NULL`，Q31 —— 飲食影響所有部位）；product_start/stop → `products` table + `Entry.products` + per-product fact insight（check-in 自動 fact）。
- **Preference 低頻抽取**（`preferences.py`，Q48）：diet trigger tag ≥3 個唔同日（21 日內）→ global preference「近排成日食…」；同一產品 ≥3 日 → conversation preference「常用產品：…」。text 冇變就唔 rewrite（throttle）。
- **Correlation detector**（`correlation.py`，Q30）：cause episodes（product 首次使用日 / diet 事件日）→ 前後 window 嘅 attribute delta；≥2 次重複先算 strong candidate；UI「相關性觀察」標明唔等於因果。
- **RAG**：`chunks` table（JSON embedding）+ Python cosine。Corpus：`corpus/`（committed 種子）＋ `data/corpus/`（gitignored 大 corpus）。Runtime 檢索行 **hybrid**（`rag/hybrid.py`：semantic recall + keyword re-rank）；eval recall 用純 `retrieve()` 做基準。
- **Messages vs Entries**：`chat_messages` = 對話 turns（display）；`entries` = 每日結構化摘要（data truth）。

## API 一覽（`app/main.py`）

| Route | 用途 |
|---|---|
| `POST /api/consult` | 行 agent graph |
| `GET/POST /api/conversations`、`PUT/DELETE /api/conversations/{cid}` | 部位 conversation CRUD（rename/delete Q52） |
| `PUT /api/conversations/{cid}/cloud-analysis` | 雲分析開關（Q18） |
| `POST /api/conversations/{cid}/facts` | 手動 ground-truth fact（可 global） |
| `POST /api/conversations/{cid}/events` | confirm detected_events → 寫 Entry/timeline/products/preferences |
| `GET /api/conversations/{cid}/summary` | entries + insights（含 global）+ timeline（含 global）+ anchors（vs 上次/1M/3M） |
| `GET /api/conversations/{cid}/correlations` | deterministic correlation candidates（Q30） |
| `GET /api/conversations/{cid}/messages` | 對話歷史（reload 唔清空） |
| `PUT/DELETE /api/conversations/{cid}/entries/{eid}`、`DELETE /api/entries/{eid}/photos/{pid}` | memory-correction：改筆記／刪日記／刪相 |
| `DELETE /api/conversations/{cid}/insights/{iid}` | 刪錯嘅 memory |
| `POST /api/photos`、`GET /api/photos/{id}` | 相 upload/serve |
| `GET /api/export`、`POST /api/import` | zip 備份/還原 |
| `GET /api/settings`、`GET /health` | settings／health |

## Eval

```bash
./.venv/bin/python -m eval.run_eval --fake        # deterministic：FakeLLM + hash embedder（CI 用）
HF_HOME=./.hf-cache ./.venv/bin/python -m eval.run_eval   # 真 embedder；有 key 時連埋 LLM-as-judge
```

- 行 **temp DB** + committed `eval/golden/` corpus —— 唔會掂 dev DB，clean clone 都 reproducible。
- 報告：`eval/out/report.md`（gitignored）。任何 FAIL → exit 1（CI gate）。
- CI（`.github/workflows/ci.yml`）：pytest + eval(--fake) + frontend typecheck/build。

## Tests

```bash
./.venv/bin/python -m pytest -q     # 60 個：memory / rag / hybrid / agent / guardrails / eval / export / attributes /
                                    #        vision-consent / messages / self-report / correlation / preferences / API layers
```

## 常用 scripts

| Script | 用途 |
|---|---|
| `scripts/ingest_corpus.py` | 掃 `corpus/` + `data/corpus/` 入 chunks（pdf/xml/txt/md） |
| `scripts/seed_demo.py` | 起一個**獨立** DEMO DB（`data/demo.db`，~90 日 synthetic entries + events + memory + chat），interview demo 用；唔掂真 data |
| `scripts/crawl_*.py` / `expand_*.py` | corpus 擴充（要 `trafilatura`/`playwright`，pyproject 未列入 —— 見 root `AGENTS.md`） |
