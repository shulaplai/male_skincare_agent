# §05 Python 環境同請求生命週期

> 你第五個問題：「呢啲 code 喺 Python 環境度係點走？」

## 1. 三個「層」：venv、套件、程式

```
backend/.venv/            ← 呢個 project 專用嘅 Python 環境（唔會污染你系統）
  lib/python3.13/site-packages/   ← 安裝落嚟嘅套件（fastapi, langgraph, sqlalchemy, fastembed…）
backend/app/              ← 我哋自己嘅 code
```

為咩要 venv？同一個專案可能要 `langgraph 0.x`，另一個要 `1.x`。venv 令兩者唔打架。

```bash
cd backend
./.venv/bin/python -m pytest -q      # 用 venv 嗰個 python（唔係系統 python3）
./.venv/bin/python -c "import langgraph; print(langgraph.__file__)"
```

## 2. `.env` 係由「當前目錄」讀嘅（新手最常撞）

`backend/app/config.py:10` 用 `pydantic-settings`，設定 `env_file=".env"` ——
**相對當前工作目錄**。所以：

```bash
cd backend && ./.venv/bin/python -m uvicorn app.main:app --port 8001   # ✅ 讀到 backend/.env
cd .. && backend/.venv/bin/python -m uvicorn app.main:app              # ❌ 讀唔到 key
```

`AGENTS.md` 寫明「一定要喺 backend/ 度行」就係呢個原因。
`learn/labs/` 嘅 script 幫你處理好（自己 `sys.path.insert`），所以你由 repo root 跑都得。

## 3. Import 路徑：`app.*` 係點嚟

```
backend/app/__init__.py           ← 有咗呢個檔，`app` 先係一個 package
backend/app/agent/graph.py        ← 所以叫 app.agent.graph
```

`learn/labs/_common.py` 做咗：

```python
sys.path.insert(0, str(REPO_ROOT / "backend"))
from app.agent.graph import build_graph
```

同樣道理，`tests/conftest.py` 開頭都會加 `backend` 落 `sys.path`。

## 4. 一次 consult 由 HTTP 到 DB：完整路徑

```
POST /api/consult                       main.py:365
  └─ run_consult(conversation_id, text, photo_paths, clip)     service.py:71
       ├─ 開 DB session（SessionLocal，db.py:29）→ 讀 conversation + user consent
       ├─ 決定 cloud_analysis = conversation 允許 AND 用戶同意（privacy gate）
       ├─ build_graph(llm=get_llm("text"), vision_llm=get_llm("vision"), embedder=…)
       ├─ graph.invoke({...state})      ← 跑 5 個 node（§04）
       ├─ write_run_log(...)            → data/runs.jsonl（service.py:41）
       └─ 回 result（連 trace）

每個 node 內部要 DB 就自己開 session：
  persist  → SessionLocal() → 寫 entries / insights / timeline_events / chat_messages
  tools    → 讀 insights / entries / chunks
```

## 5. Async 喺邊？

- FastAPI 嘅 endpoint 可以係 `def`（普通）或者 `async def`。呢個 repo 大部分 route 係普通 `def`
  （因為主要做 SQL 同步查詢），但**影片上載係 async**，而且要
  `while chunk := await file.read(1MB)` 串流寫落 disk ——
  因為 20 秒 4K 片可以 200MB+，一次過 `await file.read()` 就 OOM。
- LLM call 係同步（SDK 內部處理），所以一次 consult 幾秒之內會 block 住個 thread。

## 6. 三個 server 嘅關係（開發時）

```
瀏覽器 ──► Vite dev server (:5173) ──proxy /api──► FastAPI (:8001) ──► SQLite (backend/data/)
                  │                                       │
             React 前端                              LangGraph agent + RAG
```

- Vite 喺 `frontend/`，proxy 設定喺 `frontend/vite.config.ts`
- 前端 build 產物係 static files；production 用 nginx 反代（見 `frontend/nginx.conf`）
- 所以「前端 500」好多時係後端冇起

## 7. 常用命令（照抄）

```bash
# ── 後端
cd backend
./.venv/bin/python -m pytest -q                                   # 273 個 test
./.venv/bin/python -m eval.run_eval --fake                        # 確定性 eval（免 key）
./.venv/bin/python scripts/trace_consult.py --text "下巴爆瘡點算？"   # 睇一次真流程
./.venv/bin/python scripts/trace_consult.py --real --text "..."     # 用真 LLM
./.venv/bin/python -m uvicorn app.main:app --reload --port 8001     # dev server
./.venv/bin/python scripts/ingest_corpus.py                       # 重建 RAG 語料庫

# ── 前端
cd frontend
npm run dev          # :5173
npm run ui:check     # typecheck + eslint + stylelint + 51 個 UI test

# ── 學習實驗
./backend/.venv/bin/python learn/labs/lab03_agent_loop.py
```

## 8. 點樣「睇住佢行」

| 手段 | 睇咩 |
|---|---|
| `graph.stream()` | 逐 node 吐 delta（lab03） |
| `data/runs.jsonl` | 每次 consult 一行 JSON（事後追） |
| `LOG_LEVEL` / 睇 log | app 內部 warning（vision 失敗、embedder fallback） |
| `scripts/trace_consult.py` | 一 command 睇晒 5 站 |
| pytest 單一 test | `./.venv/bin/python -m pytest tests/test_persist_evidence.py -q -s` |

## 9. 本章練習

1. 由 repo root 同由 `backend/` 各跑一次 `trace_consult.py`，睇下有咩唔同（提示：`.env`）。
2. `./backend/.venv/bin/python -c "from app.config import settings; print(settings.database_url)"`，
   再試喺 `frontend/` 目錄跑同一句（會 ImportError —— 想想為咩）。
3. 跑一次 `trace_consult.py`，然後 `tail -1 backend/data/runs.jsonl`，對照兩者。

## 本章重點

1. `.env` 跟當前目錄 → 後端命令一律喺 `backend/` 行。
2. 生命週期：`main.py` route → `service.run_consult` → graph 5 node → SQLite；每個 node 自己開 session。
3. 想知佢做咩，唔好猜：`stream()`、trace、`runs.jsonl`、`trace_consult.py`。
