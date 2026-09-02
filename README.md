# SkinCoach — Local-first 男性護膚 AI 教練

> 每日／每週影相記錄皮膚 → AI 視覺分析（opt-in 雲端）→ 對話 check-in 追問（食咗咩、用咗咩產品）→ 長期記憶 + 美容知識庫 → 一段時間後可以 trace 返「邊個原因令皮膚變咗」。

一個**真係落地嘅 AI Agent product**（唔係薄薄哋包層 API 嘅 chatbot）：
- **多步 stateful agent**（LangGraph，5 nodes）：分析相/文字 → 揀工具 → 生成建議 → guardrail → 寫入日記
- **視覺分析**：有相＋conversation 開咗「雲分析」→ 送 `deepseek-v4-flash-vision-exp`（HK 直連）；冇相／off → 純文字降級，UI 標明
- **長期記憶**：facts / derived / preferences 三類；derived per-attribute reconcile（tag+direction：strengthen / supersede versioning + 30 日 expiry）；preference 低頻抽取（Q48）；自報事件自動寫 global fact / timeline（Q25/Q31）
- **Local-first**：相永遠留喺用戶機；每 conversation 一個雲分析開關（default off，self-hoster 可 env 改 default）；冇 key 行 FakeLLM 示範
- **RAG 美容知識庫**：文字/PDF 語料 → chunk → embed → SQLite（Python cosine，升級路徑留咗）
- **Eval harness 入 CI**：RAG recall + agent golden scenarios + 安全 check（+ 有 key 時 LLM-as-judge），FAIL 唔准 merge

> 開發指引：`AGENTS.md`（monorepo）／`backend/README.md`（backend runbook）。Docs claim vs code 現況：`docs/status-vs-claims.md`。

---

## 30 秒 Elevator Pitch

> 「ChatGPT 淨係識俾你一次性建議，但唔記得你上個月張相。SkinCoach 係一個**跨時間閉環**：你影相 → agent 分析（或純文字 check-in）→ 更新佢對你皮膚嘅長期記憶（帶 confidence 同 expiry）→ 推薦 routine。單次對話做唔到嘅係：『你三個月前食咗辣嘢嗰排爆瘡，之後停咗就好返』——呢種跨時間因果 trace。」

## Tech Stack

| 層 | 技術 |
|---|---|
| Agent orchestration | **LangGraph**（5-node state graph，每一條 edge 係你嘅 code） |
| 後端 | **FastAPI**（Python 3.11+） |
| 儲存 | **SQLite**（SQLAlchemy）＋ 相落 file system |
| 向量庫 | **SQLite `chunks` 表（JSON embedding + Python cosine）**；抽象層留 sqlite-vec/pgvector 升級路 |
| Embedding | fastembed（ONNX、無 torch、多語言 MiniLM） |
| LLM | **DeepSeek V4**（`deepseek-v4-flash` text／`deepseek-v4-flash-vision-exp` vision，HK 直連）；冇 key → FakeLLM |
| 前端 | React + Vite + TypeScript |
| 部署 | Docker Compose（frontend nginx proxy `/api`→backend、bind volume、corpus bake） |
| Eval | 自建 harness（recall@3 + MRR + agent golden + 安全 + judge）入 CI |

## 目錄結構

```
backend/          FastAPI + LangGraph agent + RAG + storage + eval（睇 backend/README.md）
frontend/         React + Vite + TS
docs/             architecture / roadmap / demo-script / blog-outline / status-vs-claims
archive/skinfile/ 舊 SKINFILE（純前端 demo，博物館）
AGENTS.md         開發指引（人類 + AI agent）
```

## 快速開始

```bash
# 後端（local dev）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # 填 SKINCOACH_DEEPSEEK_API_KEY（冇 key 都行 FakeLLM）
./.venv/bin/python -m uvicorn app.main:app --reload --port 8001   # http://localhost:8001

# 建知識庫（RAG，第一次要先跑）
./.venv/bin/python scripts/ingest_corpus.py

# 跑 eval（deterministic，唔使 key）
./.venv/bin/python -m eval.run_eval --fake    # 報告 -> eval/out/report.md

# 前端
cd ../frontend
npm install && npm run dev    # http://localhost:5173（proxy /api → 8001）

# 自己 host 想新 conversation 自動開雲分析（可選）
echo "SKINCOACH_CLOUD_ANALYSIS_DEFAULT=true" >> backend/.env   # 再 restart backend

# Interview demo：想個 UI 即刻有 90 日數據睇（獨立 DEMO DB，唔掂你真 data）
cd backend && ./.venv/bin/python scripts/seed_demo.py
SKINCOACH_DATABASE_URL=sqlite:///./data/demo.db ./.venv/bin/python -m uvicorn app.main:app --port 8001
# 前端照常：cd ../frontend && npm run dev（:5173 proxy /api -> :8001）
```

## 部署

> ⚠️ **日常用 = local dev**（backend + frontend 本地跑，最可靠）。`docker compose up --build` 提供 production 形態：frontend nginx 有 `/api` proxy → backend、data 用 bind volume、corpus 喺 image build 時 bake（詳情 `docs/status-vs-claims.md` #18）。Interview 想零 setup 展示，用 `seed_demo.py`（上面）仲快。

## 面試交付物清單

| 交付物 | 位置 |
|---|---|
| 技術決策 + 面試談資（已對齊 reality） | `docs/architecture.md` |
| **Docs claim vs code 現況對照（live）** | `docs/status-vs-claims.md` |
| Roadmap v2（Phase 0–5 對照 reality） | `docs/roadmap.md` |
| Demo video 劇本（2.5 分鐘） | `docs/demo-script.md` |
| 技術 blog 大綱 | `docs/blog-outline.md` |
| Eval report（sample） | `docs/eval-report-sample.md` |
| 開發指引（人類 + AI） | `AGENTS.md` |
| 舊 SKINFILE 嘅選型討論（博物館，重讀有用） | `archive/skinfile/DECISIONS.md` |
| CI（pytest + eval + typecheck + build） | `.github/workflows/ci.yml` |

## 決策同路線

- 點解咁揀 + 面試談資：`docs/architecture.md`
- 邊啲 claim 做咗、邊啲未做：`docs/status-vs-claims.md`
