# 現況 vs Docs Claim 對照（live）

> 用途：單一 source of truth —— 邊啲 docs claim 係真、邊啲係 drift、邊啲未做。改 code ／改 docs 之後要更新呢張表。
> 缺口類型：(a) 純文字 drift → 改 docs；(b) 真數據路徑缺口 → 做真 code；(c) 面試 stretch → 降級／標明 demo。
> 最後更新：Layer 2/3 全部落地之後（correlation / preference / global scope / anchors UI / delete-edit UI / demo seed / hybrid 接線）。

## 總覽

- **定位**：見工 portfolio + showcase；自己係 daily user（single-user）。
- **真數據路徑 100% 真；面試敘事可以 stretch 但唔可以喺真路徑扮真。**
- Backend tests **60/60 綠**；frontend typecheck + build 綠；eval（--fake）100% recall / MRR 0.90 / 3 agent scenarios PASS；CI 有 pytest + eval + frontend jobs。

## 對照表

| # | Docs claim（位置） | Code reality | 類型 | 狀態／行動 |
|---|---|---|---|---|
| 1 | 「AI 視覺分析」每日影相 → AI 睇相（README / architecture §2） | ✅ 真：analyze 有相＋`cloud_analysis` consent → 送 `deepseek-v4-flash-vision-exp`；off 時純文字並標「未睇相」；UI badge 顯示 | (b) | ✅ **真**。需真實相 smoke test 過 |
| 2 | LangGraph 6-node flow（architecture §2 / README） | 實際 5 nodes：analyze→tools→advise→guardrail→persist | (a) | ✅ docs 已改（5-node） |
| 3 | Model tiering：strong vision / strong text（architecture §7） | ✅ 分層：analyze=vision-exp、advise/text=deepseek-v4-flash；dead config 已刪 | (b) | ✅ **真**（Q20） |
| 4 | Local mode（Ollama） | 冇 Ollama；冇 key = FakeLLM 示範模式 | (c) | ✅ docs 已改：FakeLLM、冇 Ollama |
| 5 | LangGraph checkpointer 做長期記憶 | 冇用 checkpointer；stateless consult + SQLite + 最近 10 條 messages | (a) | ✅ docs 已改 |
| 6 | 三類 memory（fact/derived/preference）+ 30 日衰減 + 矛盾 versioning | ✅ **per-attribute reconcile 真**（tag+direction，Q47）：strengthen / supersede + version；fact endpoint（可 global）；preference 低頻抽（Q48）；product fact hook | (b) | ✅ Block 3 + Layer 2 **完成** |
| 7 | 因果時間線 / 一年 trace | ✅ deterministic change detect + timeline（threshold 先寫）；rolling multi-anchor 對比（vs 上次／1M／3M）已上 UI（`/summary.anchors`，Q12） | (b)(c) | ✅ 事件寫手 + anchors UI **真**；「一年視圖」stretch 唔再做 |
| 8 | RAG：PDF→OCR→chunk→embed→sqlite-vec | RAG 真（chunks + cosine）；冇 OCR（pypdf 抽 text）；embedding 存 JSON | (a) | ✅ docs 已改 |
| 9 | Hybrid retrieval | ✅ **已接線**：`tools.search_knowledge` 行 `rag/hybrid.py`（semantic recall + keyword re-rank）；eval recall 行純 `retrieve()` 做基準 | (a) | ✅ 唔再係 orphan |
| 10 | Embedding model env / bge-m3 | ✅ dead config 已刪；code 用 MiniLM-L12-v2（fastembed 預設） | (a) | ✅ |
| 11 | LLM-as-judge 三維評分 | ✅ `eval/judge.py` 接線：有 key 時逐 scenario 評分；--fake skip | (c) | ✅（Q17） |
| 12 | Eval 入 CI、「綠先 merge」 | ✅ CI `eval` job（`--fake`，FAIL → exit 1）；temp DB + golden corpus | (b) | ✅（Q16） |
| 13 | 「20 / 40 / 42 tests」 | 實際 **60** 個（backend） | (a) | ✅ 文件已改 60 |
| 14 | Chat-first UI + 右 panel 指數/記憶/時間線 | ✅ chat-first 真；右 panel live（真 attributes/insights/timeline，global 🌐 標記）；假 78 分刪走 | (b) | ✅ |
| 15 | Chat 歷史 persist | ✅ `chat_messages` + messages endpoint；reload 唔清空 | (b) | ✅（Q7/Q35） |
| 16 | 每個部位獨立日記/記憶/時間線 + global scope | ✅ body-part scoped 真；**global 寫手已做**：diet → global timeline（Q31）、global fact/preference 可見於 summary + coach tools | (b) | ✅ Layer 2 **完成** |
| 17 | 產品庫 products table（roadmap P1） | ✅ products table 真（self-report 確認創建 + Entry.products + per-product fact） | (b) | ✅（Q28 + check-in 自動 fact） |
| 18 | Docker `compose up --build` 撳得郁 | 🟡 已修：frontend nginx `/api`+`/health` proxy → backend、optional `env_file: ./backend/.env`（`required: false`）+ `${VAR:-default}` environment、`./data` bind volume、corpus bake／empty-chunks ingest entrypoint、兩邊 .dockerignore、healthcheck。`docker compose config` ✅ PASS。**實際 build 未跑**（本機 Docker daemon 未開） | (c) | 🟡 最後一關：起 Docker Desktop 再 `docker compose up --build` |
| 19 | 單用戶 local-first；key 喺 env | ✅ `.env` gitignored、data gitignored、export/import zip | (b) | ✅ |
| 20 | 舊 SKINFILE 概念升級重用 | 🟡 archive 博物館（Q4）；tiering/consent 已兌現；prefix caching 唔強求 | (a) | ✅ 冇再做 |
| 21 | Correlation detector（Q30） | ✅ `app/correlation.py` + `GET /correlations` + ProgressView「相關性觀察」；deterministic candidate、標明唔等於因果 | (b) | ✅ Layer 2 **完成** |
| 22 | Preferences 低頻抽取（Q48） | ✅ `app/preferences.py`：diet tag ≥3 日／產品 ≥3 日 → preference；text 冇變唔 rewrite | (b) | ✅ Layer 2 **完成** |
| 23 | Memory-correction UI（delete/edit） | ✅ 改 entry note、刪 entry（連相 + 同日 conv events）、刪單相、刪 insight（清 superseded_by 指針） | (b) | ✅ Layer 3 **完成** |
| 24 | Demo environment + seed（Q10/Q19） | ✅ `scripts/seed_demo.py` → 獨立 `data/demo.db`（90 日 synthetic + global diet events 令 correlation 有得睇）；唔掂真 data | (b) | ✅ Layer 3 **完成** |

## Open work（由呢張表反推）

- **#18 Docker 真機驗證**：code 已改，要喺有 Docker 嘅機 `docker compose up --build` 行一次，確認 UI／photo upload／API proxy 全部通先可以畫 ✅。
- **Docs 層交付**：roadmap v2 ✅、blog 草稿 ✅（`docs/blog-post.md`）、demo video 要真人 screen record（劇本 `docs/demo-script.md`）—— 呢個係唯一要人手嘅交付物。
- **數據累積**：correlation / preference 嘅「重複模式」要靠真數據 collect 幾星期先有意義 —— code 已 ready，等 data。

## 面試前 checklist

- [ ] 真 vision smoke test（開 ☁️、影相 → `vision_used: true`、badge 出現）
- [ ] 新 conversation 第一次 upload → 詳盡 onboarding 回覆（baseline 解釋）
- [ ] Reload 頁面 → thread 仲喺度（#15）
- [ ] `python -m pytest -q` 60 綠 + `npm run typecheck` + `npm run build`
- [ ] `python -m eval.run_eval --fake` PASS（#12）
- [ ] `scripts/seed_demo.py` 起 DEMO DB → 開 UI 展示 90 日數據（#24）
- [ ] Docker `compose up --build` 撳得郁（#18）／或敘事用「local dev + seed demo」
- [ ] 揀好面試敘事用邊幾條真 claim（#1/3/6/7/11/12/14/21/22）——每條都要答到「點 control LLM」
- [ ] 錄 demo video（跟 `docs/demo-script.md`）
