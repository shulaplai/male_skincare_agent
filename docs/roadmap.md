# Roadmap — SkinCoach（3 個月）

目標：三個月後拎住一個 **真係用得、部署到、有 eval 數據** 嘅 AI Agent product 去見工（AI Agent Developer）。

---

## Phase 0 — 地基（✅ 進行中）
- monorepo：`backend/` + `frontend/` + `docs/`
- 後端骨架（FastAPI + config）、前端骨架（React+Vite+TS）
- Docker Compose + Dockerfile
- README + architecture + roadmap
- 舊 SKINFILE 移去 `archive/skinfile/`

## Phase 1 — 數據層（local-first 核心）
- SQLite schema：users / entries / photos / insights（memory）/ products
- 相片壓縮（max 1024px、JPEG）+ 落 file system，metadata 落 DB
- 長期記憶規則（三類 / 30 日衰減 / 矛盾 versioning）落 SQL
- Export / Import（zip = SQLite + 相），滿足「一定可以儲喺用戶自己電腦」

## Phase 2 — RAG 美容知識庫
- 上網搵中英美容 PDF（皮膚學、成分、暗瘡、屏障、routine 等）
- 掃描版 → OCR（pdf skill + Tesseract/PaddleOCR）
- chunk + embed（sentence-transformers 多語言 model）→ sqlite-vec
- 檢索接口 + **recall eval**（golden questions）

## Phase 3 — Agent（LangGraph）
- 多步 state graph：分析相 → 讀記憶 → 檢索 → 揀工具 → 生成建議 → 寫入
- Tool whitelist（查產品 / 查日記 / 查知識庫）
- Pydantic 型別合約（JSON mode 輸出）
- Medical guardrail + disclaimer
- Model tiering + vision 降級 + 本地模式（Ollama）

## Phase 4 — 前端（3 個方向揀一）
- 先出 **3 個 HTML 方向 prototype** 俾你揀（chat-first / dashboard-first / 問卷-first）
- 揀完起真 React UI：Dashboard / Check-in / Consult（chat）/ Timeline（一年因果 trace）/ Settings
- 接後端 API

## Phase 5 — Eval + Production
- Eval harness：retrieval recall + LLM-as-judge（具體性/相關性/安全）+ golden set
- CI（GitHub Actions）：typecheck / pytest / eval 綠先 merge
- logging / 錯誤分類 / rate limit / 基本 auth
- Docker 部署（VPS / Railway / Fly）
- README + demo video + 技術 blog（解釋 RAG + agent 架構 + 點控制 LLM）

---

## 面試交付物清單（最終要齊）

- [ ] GitHub repo + 有質素 README + architecture/roadmap docs
- [ ] 部署咗、撳得郁嘅網
- [ ] eval report（recall + judge 分數 + 安全維度）
- [ ] demo video（2-3 分鐘：由影相到一年後 trace）
- [ ] 技術 blog（點解 LangGraph / 點控制 LLM / memory 點設計）
