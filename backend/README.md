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
```

第一次 startup 會 `init_db()`：建表 + 自動加新 column（`db.py._COLUMN_MIGRATIONS`，唔會鏟 data）。

## Config（`backend/.env`，全部 `SKINCOACH_` 前綴）

| Env | 預設 | 說明 |
|---|---|---|
| `SKINCOACH_LLM_PROVIDER` | `deepseek` | `deepseek \| anthropic \| openai`（HK 直連得 DeepSeek；Anthropic/OpenAI 香港係 403） |
| `SKINCOACH_DEEPSEEK_API_KEY` | — | 真 key 只喺本地 `.env`，唔好 commit |
| `SKINCOACH_DEEPSEEK_TEXT_MODEL` | `deepseek-v4-flash` | advise／memory 用 |
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
                                        + load 最近 10 條 chat messages 做 context
                            advise    ：出 Advice{reply（正文 2–5 句）, items（行動點）}
                            guardrail ：deterministic（紅旗 → 轉介；藥物詞 → 唔俾建議；自動 disclaimer）
                            persist   ：upsert 當日 Entry（attributes/metrics/photos）
                                        + deterministic change detect → timeline event（sparse）
                                        + 寫 ChatMessage（user + coach，reload 唔會清空）
```

- **固定 attribute schema**：`agent/attributes.py` —— 六個 key × 0–3 severity，change detect／timeline／memory 全部食同一個 schema。
- **Memory**：`insights` table（fact / derived / preference），derived 30 日 expiry + supersede versioning（`memory.py`）。⚠️ per-attribute tag+direction rewrite 未做（而家只寫 `recent_status`，confidence 唔會累積）。
- **RAG**：`chunks` table（JSON embedding）+ Python cosine。Corpus：`corpus/`（committed 種子）＋ `data/corpus/`（gitignored 大 corpus）。`app/rag/hybrid.py` 暫時係 orphan（未接線）。
- **Messages vs Entries**：`chat_messages` = 對話 turns（display）；`entries` = 每日結構化摘要（data truth）。

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
./.venv/bin/python -m pytest -q     # 40 個：memory / rag / hybrid / agent / guardrails / eval / export / attributes / vision-consent / messages
```

## 常用 scripts

| Script | 用途 |
|---|---|
| `scripts/ingest_corpus.py` | 掃 `corpus/` + `data/corpus/` 入 chunks（pdf/xml/txt/md） |
| `scripts/crawl_*.py` / `expand_*.py` | corpus 擴充（要 `trafilatura`/`playwright`，pyproject 未列入 —— 見 root `AGENTS.md`） |
