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
| 向量庫 | **sqlite-vec**（嵌入式、單檔；抽象層留 Qdrant/pgvector 升級路） |
| Embedding | sentence-transformers（中英多語言 model） |
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
cp .env.example .env        # 填 API key
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000

# 前端
cd frontend
npm install
npm run dev                 # http://localhost:5173（proxy /api → 8000）

# 一炮起晒（production 形態）
docker compose up --build
```

## 決策同路線

- 點解咁揀 + 面試談資：`docs/architecture.md`
- 三個月 roadmap：`docs/roadmap.md`
