# SkinCoach — Local-first 男性護膚 AI 教練

> 每日／每週影相記錄皮膚 → AI 視覺分析 → 對話 check-in 追問（食咗咩、用咗咩產品）→ 長期記憶 + 美容知識庫 → 一年後可以 trace 返「邊個原因令皮膚變咗」。

一個**真係落地嘅 AI Agent product**（唔係薄薄哋包層 API 嘅 chatbot）：
- **多步 stateful agent**（LangGraph）：分析相 → 讀記憶 → 檢索知識 → 揀工具 → 生成建議 → 寫入日記
- **長期記憶**：facts / derived / preferences 三類，30 日衰減 + 矛盾 versioning
- **Local-first**：相永遠留喺用戶機；opt-in 先上雲分析、用完即棄；有純本地模式（Ollama）
- **RAG 美容知識庫**：中英 PDF → OCR → chunk → embed → sqlite-vec
- **Eval harness**：retrieval recall + LLM-as-judge + 安全 guardrail，CI 跑綠先 merge

---

## 30 秒 Elevator Pitch

> 「ChatGPT 淨係識俾你一次性建議，但唔記得你上個月張相。SkinCoach 係一個**跨時間閉環**：你影相 → agent 分析、對比、追問 → 更新佢對你皮膚嘅長期記憶（帶 confidence 同 expiry）→ 推薦 routine。單次對話做唔到嘅係：『你三個月前食咗辣嘢嗰排爆瘡，之後停咗就好返』——呢種跨時間因果 trace。」

## Tech Stack

| 層 | 技術 |
|---|---|
| Agent orchestration | **LangGraph**（state graph，你擁有每一條 edge） |
| 後端 | **FastAPI**（Python 3.11+） |
| 儲存 | **SQLite**（SQLAlchemy）＋ 相落 file system |
| 向量庫 | **SQLite（chunks 表 + cosine）**；抽象層留 sqlite-vec/pgvector 升級路 |
| Embedding | fastembed（ONNX、無 torch、多語言 MiniLM） |
| LLM | 雲 API（Anthropic/DeepSeek，opt-in）＋ Ollama 本地模式 |
| 前端 | React + Vite + TypeScript |
| 部署 | Docker Compose |
| Eval | 自建 harness（recall + LLM-as-judge + 安全） |

## 目錄結構

```
backend/          FastAPI + LangGraph agent + RAG + storage + eval
frontend/         React + Vite + TS
docs/             architecture.md / roadmap.md
archive/skinfile/ 舊 SKINFILE（純前端 demo，概念參考用）
docker-compose.yml
```

## 快速開始

```bash
# 後端（local dev）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # 填 API key（冇 key 都會用 FakeLLM 跑）
HF_HOME=./.hf-cache uvicorn app.main:app --reload --port 8001   # http://localhost:8001

# 建知識庫（RAG，第一次要先跑）
python scripts/ingest_corpus.py

# 跑 eval harness
python -m eval.run_eval    # 報告 -> eval/out/report.md

# 前端
cd ../frontend
npm install
npm run dev                 # http://localhost:5173（proxy /api → 8001）

# 一炮起晒（production 形態）
cd .. && docker compose up --build
```

## 部署（production 形態）

```bash
docker compose up --build
# frontend -> http://localhost:5173 ，backend -> http://localhost:8001
```

要 deploy 去 VPS / Railway / Fly：`docker-compose.yml` 已齊 backend（FastAPI）＋ frontend（nginx 託 static build）；改 `ports` 同加 `SKINCOACH_ANTHROPIC_API_KEY`（或 DeepSeek）入 `.env` 就得。相／SQLite 用 volume 綁喺 `./data`，滿足 local-first。

## 面試交付物清單

| 交付物 | 位置 |
|---|---|
| 技術決策 + 面試談資 | `docs/architecture.md` |
| 三個月 roadmap | `docs/roadmap.md` |
| Demo video 劇本（2.5 分鐘） | `docs/demo-script.md` |
| 技術 blog 大綱 | `docs/blog-outline.md` |
| Eval report（sample） | `docs/eval-report-sample.md` |
| 舊 SKINFILE 嘅選型討論（重讀有用） | `archive/skinfile/DECISIONS.md` |
| CI（pytest + typecheck + build） | `.github/workflows/ci.yml` |

## 決策同路線

- 點解咁揀 + 面試談資：`docs/architecture.md`
- 三個月 roadmap：`docs/roadmap.md`
