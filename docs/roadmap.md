# Roadmap — SkinCoach（v2，對照 reality）

> 目標：三個月後拎住一個 **真係用得、部署到、有 eval 數據** 嘅 AI Agent product 去見工（AI Agent Developer）。
> 呢份係 v2：每個 phase 對照 `docs/status-vs-claims.md`（live）寫**完成度**，唔再寫「打算做」當做咗。
> ⚠️ **2026-10-05 定位更正（issue #11 判決）**：呢份文件係 **changelog**，唔係 forward plan —— 每個 phase 嘅 ✅ 都係事後補寫，唔應該當成計劃去 re-plan。前望嘅工作在 wayfinder map（[#1](https://github.com/shulaplai/male_skincare_agent/issues/1)）同 issue 度。
> **真正嘅 binding constraint 唔係時間**，係兩樣：(1) 從來未喺真環境行過一次完整部署（image 未 build 過）；(2) 冇任何唔係我自己嘅使用者。三個月時間線係已經發生嘅事。
> 呢一輪 frontier 嘅決定推翻咗下面三處敘述（Phase 2 RAG／Phase 5 gate／Docker 狀態），已逐處更正。
> 而家位置：**Phase 0–5 嘅核心全部完成**（backend 317 tests 綠、5-node agent 真、RAG 有 corpus、chat-first UI 真、eval 入 CI、Layer 2 全部落地）。剩低嘅係收尾 + 打磨 + 記錄。

---

## Phase 0 — 地基 ✅
- monorepo（backend + frontend + docs）、FastAPI + React+Vite+TS 骨架 ✅
- Docker Compose + Dockerfile 🟡（v2 修咗：frontend nginx `/api` + `/health` proxy、bind volume、corpus bake、`FASTEMBED_CACHE_PATH`；`docker compose config` 通過，但 image 從來冇 build／未 up 過 —— daemon 係開嘅（`docker info` → 27.4.0），未 build 係未試，唔係做唔到，狀態以 status #18 為準）
- README + architecture + roadmap + AGENTS.md ✅
- 舊 SKINFILE → `archive/skinfile/` 博物館 ✅

## Phase 1 — 數據層（local-first 核心）✅
- SQLite schema：users / conversations / entries / photos / insights / timeline_events / chat_messages / products / chunks ✅（加 column 用 `_COLUMN_MIGRATIONS` auto-ALTER）
- 相片壓縮落 file system、metadata 落 DB ✅（serve 端有 `?w=` 縮圖 whitelist `THUMB_WIDTHS`，UI 一律用縮圖 ＋ grid `loading="lazy"`）
- 長期記憶規則落 SQL：fact / derived / preference + tag+direction reconcile（Q47）✅
- Export/Import zip ✅
- **demo environment**：`scripts/seed_demo.py` 起獨立 DEMO DB（Q10/Q19）✅

## Phase 2 — RAG 美容知識庫 ✅（敘事 2026-10-05 更正，issue #10）
- 中英 corpus（zh basics + DermNet + incidecoder + Europe PMC 擴充爬蟲）✅ —— ⚠️ production index 冇得由 repo 重建，而且 92.2% 係英文、250 個 CJK chunk 之中 248 個來自同一篇唇膏新聞稿。
- chunk + embed（fastembed MiniLM，無 OCR —— 語料多數係 text）→ SQLite JSON embedding + Python cosine ✅
  ⚠️ chunker 以前漏 ASCII `.`（漏 88% 語料：英文 chunk 平均 2520 chars vs `chunk_size=500`，MiniLM 512 token 會截斷）—— regex 已修，剩低嘅係語料本身。
- 檢索接口 + recall eval（golden queries）✅ —— ⚠️ **recall 數字唔再係賣點**：golden index 得 4 chunks（random baseline recall@3 0.849／MRR 0.563 vs semantic 1.000／0.900），證明唔到檢索質素。數字留喺 eval report 做 wiring baseline。
- Runtime 用 hybrid（semantic recall + keyword re-rank）✅
- **定位（issue #10 決定）**：retrieval 係 grounding／citation／control，唔係差異化。要再投資就先要撞到一條可證偽 bar：≥3000 條真·護膚 chunks、≥100 條 chunk-level 標註 query、公開 random ＋ BM25 baseline、runtime path 入 CI、至少一次真 embedder run。

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
- CI（GitHub Actions）：typecheck / lint / stylelint / pytest / eval `--fake` / UI gate 非像素子集 ✅（2026-10-05 run `37310220211` 三個 job 全綠；pixel snapshot 因為 baseline 係 macOS-only 所以唔入 CI）
  ⚠️ **「綠先 merge」到今日仍然係紀律，唔係機制**：`main` 冇 branch protection（`gh api .../branches/main/protection` → **404 Branch not protected**），`recall_hybrid` 同 judge 亦未入 exit code。決定（issue #17）＝(a) 令 gate 咬得住（加 reciprocal wiring 斷言、metric 入 exit code、開 branch protection），跟住 (b) 錄真 provider response 喺 CI replay。綠之後代表咩：「source-level 行為同 wiring 過」，唔代表 ranking 質素或真 provider 行為。
- Docker 部署（compose up 撳得郁）🟡 —— ⚠️ 2026-10-05 更正：Docker Desktop 唔係成日開（稍早 `docker info` → 27.4.0，同日再試係 `Cannot connect to the Docker daemon … Is the docker daemon running?`），所以係 **image 從來冇 build／up 過**，唔係「daemon 開住只係未試」。
- README + demo video + 技術 blog：
  - 技術 blog 大綱 ✅（`docs/blog-outline.md`）；完整 blog post 草稿 🟡 `docs/blog-post.md`（本文檔配套）
  - demo video 🟡 —— 要真人 screen record，劇本喺 `docs/demo-script.md`；未錄影

---

## Deliberately not built（issue #11 要求嘅一句）

已經寫死喺 wayfinder map 嘅 out of scope：multi-user／auth／hosted deployment、自己以外嘅用戶研究、demo video 以外嘅 marketing 素材、`archive/skinfile/`、同面試可信度無關嘅一般工程衛生（coverage target、module layout、1882 行 `index.css`）。

⚠️ 以下係我建議、但**用戶今次冇確認**（#11 嘅多選留空，所以先當提案）：唔再為「agent」呢個字加 loop／conditional edge（#9 已定）、未撞到上面條 bar 之前唔再投資 RAG 語料／embedder、唔再加第 5 套 UI layout、未部署過之前唔寫 scaling／性能故事。

## Binding constraint（真正嘅下一步）

1. **一次真環境完整 run**：`docker compose up --build` ＋ 一個真·皮膚相嘅 `POST /api/consult`（#8 嘅 HITL 半場；用戶 2026-10-05 決定會自己開 Docker Desktop、用 DB 已有嘅真相）。
2. **一個唔係我自己嘅使用者**：map out of scope 講明今次唔做 external user research，所以呢樣係下一份 effort 嘅事，唔好偷偷寫入呢三個月嘅成果。

---

## 面試前 checklist（跟 `docs/status-vs-claims.md` 末段一齊用）

- [ ] 真 vision smoke test（☁️ 開、影相 → `vision_used: true`、badge 出現）
- [ ] 新 conversation 第一次 upload → 詳盡 onboarding reply
- [ ] Reload 頁面 → thread 仲喺度
- [ ] `cd backend && ./.venv/bin/python -m pytest -q`（**317 綠**）+ `npm run typecheck` + `npm run build`
- [ ] `cd frontend && npm run ui:check`（**60 passed**）
- [ ] `eval.run_eval --fake` PASS（semantic baseline recall 100% / MRR 0.90；hybrid（runtime path）100% / 1.00；**4** agent scenarios，其中 **3/4** 有 `expect_tool` gate）
- [ ] `scripts/seed_demo.py` → demo DB 行得起（interview 零準備 demo 用）
- [ ] Docker `compose up --build` 撳得郁（#18）／或敘事用「local dev + seed demo」
- [ ] 錄 demo video（2–3 分鐘，跟 `docs/demo-script.md`）
- [ ] Blog post 上稿前對照 `docs/blog-post.md` 草稿 + status doc 最新數字
