# Roadmap — SkinCoach（v2，對照 reality）

> 目標：三個月後拎住一個 **真係用得、部署到、有 eval 數據** 嘅 AI Agent product 去見工（AI Agent Developer）。
> 呢份係 v2：每個 phase 對照 `docs/status-vs-claims.md`（live）寫**完成度**，唔再寫「打算做」當做咗。
> 而家位置：**Phase 0–5 嘅核心全部完成**（backend 60 tests 綠、5-node agent 真、RAG 有 corpus、chat-first UI 真、eval 入 CI、Layer 2 全部落地）。剩低嘅係收尾 + 打磨 + 記錄。

---

## Phase 0 — 地基 ✅
- monorepo（backend + frontend + docs）、FastAPI + React+Vite+TS 骨架 ✅
- Docker Compose + Dockerfile ✅（v2 修咗：frontend nginx `/api` proxy、bind volume、corpus bake；狀態見 status #18）
- README + architecture + roadmap + AGENTS.md ✅
- 舊 SKINFILE → `archive/skinfile/` 博物館 ✅

## Phase 1 — 數據層（local-first 核心）✅
- SQLite schema：users / conversations / entries / photos / insights / timeline_events / chat_messages / products ✅（加 column 用 `_COLUMN_MIGRATIONS` auto-ALTER）
- 相片壓縮落 file system、metadata 落 DB ✅
- 長期記憶規則落 SQL：fact / derived / preference + tag+direction reconcile（Q47）✅
- Export/Import zip ✅
- **demo environment**：`scripts/seed_demo.py` 起獨立 DEMO DB（Q10/Q19）✅

## Phase 2 — RAG 美容知識庫 ✅
- 中英 corpus（zh basics + DermNet + incidecoder + Europe PMC 擴充爬蟲）✅
- chunk + embed（fastembed MiniLM，無 OCR —— 語料多數係 text）→ SQLite JSON embedding + Python cosine ✅
- 檢索接口 + **recall eval**（golden queries）✅
- Runtime 用 hybrid（semantic recall + keyword re-rank）✅

## Phase 3 — Agent（LangGraph）✅
- 5-node state graph：analyze → tools → advise → guardrail → persist ✅
- Tool whitelist（profile / recent entries / search_knowledge）✅
- Pydantic 型別合約（`SkinAnalysis` / `Advice` / `DetectedEvent`）✅
- Medical guardrail + disclaimer ✅
- Model tiering + vision consent 降級（DeepSeek V4，無 Ollama）✅
- **Layer 2 功能**（喺 Phase 3 之後做埋）：
  - 自報事件確認（chat detect → chips confirm → 落 DB）✅
  - diet → **global** timeline（Q31）＋ products table（Q28）＋ per-product fact hook ✅
  - preference 低頻抽取（Q48，deterministic throttle）✅
  - correlation detector（Q30，deterministic candidates）✅
  - rolling multi-anchor 對比（/summary.anchors + UI，Q12）✅

## Phase 4 — 前端 ✅
- chat-first 真 UI：Chat / RightPanel（live 指標/記憶/時間線）/ Records / Progress（趨勢 + anchors + correlations）/ Settings ✅
- 多部位對話（每部位獨立日記/記憶/時間線）✅
- 記憶修正 UI：改筆記、刪日記、刪相、刪 insight（Q52 delete/edit）✅
- 接後端 API（server source of truth，無 demo data）✅

## Phase 5 — Eval + Production 🟡（大部分完成）
- Eval harness：RAG recall + agent golden scenarios + safety + LLM-as-judge（有 key 時）✅
- CI（GitHub Actions）：typecheck / pytest / eval `--fake` 綠先 merge ✅
- Docker 部署（compose up 撳得郁）✅（以 status #18 為準）
- README + demo video + 技術 blog：
  - 技術 blog 大綱 ✅（`docs/blog-outline.md`）；完整 blog post 草稿 🟡 `docs/blog-post.md`（本文檔配套）
  - demo video 🟡 —— 要真人 screen record，劇本喺 `docs/demo-script.md`；未錄影

---

## 面試前 checklist（跟 `docs/status-vs-claims.md` 末段一齊用）

- [ ] 真 vision smoke test（☁️ 開、影相 → `vision_used: true`、badge 出現）
- [ ] 新 conversation 第一次 upload → 詳盡 onboarding reply
- [ ] Reload 頁面 → thread 仲喺度
- [ ] `pytest -q`（60 綠）+ `npm run typecheck` + `npm run build`
- [ ] `eval.run_eval --fake` PASS（recall 100%、MRR 0.90、3 agent scenarios）
- [ ] `scripts/seed_demo.py` → demo DB 行得起（interview 零準備 demo 用）
- [ ] Docker `compose up --build` 撳得郁（#18）／或敘事用「local dev + seed demo」
- [ ] 錄 demo video（2–3 分鐘，跟 `docs/demo-script.md`）
- [ ] Blog post 上稿前對照 `docs/blog-post.md` 草稿 + status doc 最新數字
