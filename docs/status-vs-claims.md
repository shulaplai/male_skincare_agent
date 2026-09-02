# 現況 vs Docs Claim 對照（live）

> 用途：單一 source of truth —— 邊啲 docs claim 係真、邊啲係 drift、邊啲未做。改 code ／改 docs 之後要更新呢張表。
> 缺口類型：(a) 純文字 drift → 改 docs；(b) 真數據路徑缺口 → 做真 code；(c) 面試 stretch → 降級／標明 demo。
> 最後更新：Block 1 + Block 2（backend core + frontend sync）+ eval/CI + docs 三件套之後。

## 總覽

- **定位**：見工 portfolio + showcase；自己係 daily user（single-user）。
- **真數據路徑 100% 真；面試敘事可以 stretch 但唔可以喺真路徑扮真。**
- Backend tests **40/40 綠**；frontend typecheck + build 綠；eval（--fake）100% recall / 3 scenarios PASS。

## 對照表

| # | Docs claim（位置） | Code reality | 類型 | 狀態／行動 |
|---|---|---|---|---|
| 1 | 「AI 視覺分析」每日影相 → AI 睇相（README elevator / architecture §2） | ✅ 真：analyze 有相＋`cloud_analysis` consent → 送 `deepseek-v4-flash-vision-exp`；off 時純文字並標「未睇相」；UI badge 顯示 | (b) | ✅ **真**。需真實相 smoke test 過 |
| 2 | LangGraph 6-node flow（architecture §2 / README） | 實際 5 nodes：analyze→tools→advise→guardrail→persist；memory read/檢索係 tools | (a) | ✅ docs 已改（architecture/README §2 5-node） |
| 3 | Model tiering：strong vision / strong text / fast（architecture §7、舊 DECISIONS） | ✅ 分層：analyze=vision-exp、advise/text=deepseek-v4-flash；`fast_model`/`strong_model` 死 config 已刪 | (a)(b) | ✅ **真**（Q20） |
| 4 | Local mode（Ollama）（README/architecture §4） | 冇 Ollama adapter；冇 key = FakeLLM（唔係真 offline，embedder 照 load） | (c) | ✅ docs 已改：FakeLLM 示範模式、冇 Ollama；Ollama 唔做 |
| 5 | LangGraph checkpointer 做長期記憶（architecture §3） | 冇用 checkpointer。實際：stateless consult + SQLite + 最近 10 條 messages context | (a) | ✅ docs 已改（§3 明確唔用 checkpointer） |
| 6 | 三類 memory（fact/derived/preference）+ 30 日衰減 + 矛盾 versioning（README/architecture §5） | ✅ schema + decay + supersede 真（`memory.py`）；但 persist **只寫 derived/recent_status**；fact/preference 冇寫手；**strengthen branch 要 byte-identical text → 真 LLM 永遠 supersede、confidence 卡 0.6** | (b) | 🟡 **Block 3 未做**：per-attribute tag+direction reconcile（Q14）、fact=自報+手動（Q25）、preference 低頻抽（Q13） |
| 7 | 因果時間線 / 一年 trace（README / demo-script） | ✅ deterministic change detect + timeline events（`attributes.py`，threshold 先寫、每日最多一條）**真**；但係「一年 trace」UI 深層未做 | (b)(c) | 🟡 事件寫手真；一年視圖屬 stretch（Layer 2） |
| 8 | RAG：PDF→OCR→chunk→embed→sqlite-vec（README） | RAG 真（chunks + cosine）；冇 OCR（pypdf 抽 text）；embedding 存 JSON | (a) | ✅ docs 已改（README/architecture §6：冇 OCR、JSON embed） |
| 9 | Hybrid retrieval（git log 最新） | ❌ `hybrid.py` orphan：runtime + eval 都行純 semantic `retrieve()` | (a) | 🟡 接線（tools.py search_knowledge 用 search_hybrid）或者刪；兩邊唔好留 |
| 10 | Embedding model env（`SKINCOACH_EMBEDDING_MODEL` / bge-m3） | ✅ 死 config 已刪；code 用 MiniLM-L12-v2（fastembed 預設） | (a) | ✅ |
| 11 | LLM-as-judge 三維評分（README:10 / roadmap P5 / architecture §8.4） | ✅ `eval/judge.py` 已接線：`run_eval` 有 key 時逐 scenario judge 入報告；--fake skip | (c) | ✅ **接線真**（Q17） |
| 12 | Eval 入 CI、「綠先 merge」（roadmap P5 / demo-script） | CI 有 `eval` job（`--fake`，FAIL → exit 1）；temp DB + committed golden corpus | (b) | ✅ **真**（Q16）+ eval-report-sample/demo-script 已更新 |
| 13 | 「20 tests 全綠」 | 實際 **40** 個（backend） | (a) | ✅ eval-report-sample / demo-script 已改做 40 |
| 14 | Chat-first UI + 右 panel 指數/記憶/時間線（architecture §10） | ✅ chat-first 真；右 panel **live**（真 attributes 趨勢/insights/timeline），假 78 分刪走 | (b) | ✅（Q9B + Frontend sync） |
| 15 | Chat 歷史 persist（demo 聲稱 reload 唔清空） | ✅ `chat_messages` + `GET /api/conversations/{id}/messages`；App boot load thread | (b) | ✅（Q7/Q35） |
| 16 | 每個部位獨立日記/記憶/時間線 + global scope（architecture §10 / Q27） | 🟡 body-part scoped 真（conversation 隔離）；`global` scope 只加咗 nullable FK/column，**未有任何 global 寫手** | (b)(c) | 🟡 Layer 2：diet/product/medication 寫 global 因（Q29/Q31） |
| 17 | 產品庫 products table（roadmap P1） | ❌ 冇 products table（roadmap 有但冇做）；products 只係 entry JSON column | (c) | 🟡 Layer 2（Q28） |
| 18 | Docker `compose up --build` 撳得郁（README 部署） | ❌ frontend nginx 冇 `/api` proxy → API 404 → 靜靜 offline；`env_file: .env`（root）唔存在；image 冇 corpus/ingest；冇 .dockerignore | (c) | 🟡 Layer 3（Q5）：補 proxy + env + ingest 步驟先算「撳得郁」 |
| 19 | 單用戶 local-first；key 喺 env（README） | ✅ `.env` gitignored、data gitignored、export/import zip | (b) | ✅。註：你 `.env` 有真 DeepSeek key |
| 20 | 舊 SKINFILE 概念升級重用（DECISIONS.md） | 🟡 archive 保留做博物館（Q4）；部分談資（tiering 已兌現；視覺降級已兌現；prefix caching 未兌現——prompt 有 static-first 傾向但未刻意做） | (a) | 🟡 揀「真做咗」嘅升呢入 architecture；prefix caching 唔強求 |

## Open work（由呢張表反推）

- **Block 3（Layer 1 餘下）**：memory rewrite —— per-attribute tag + direction reconcile、fact 寫手（check-in 自報 + 手動「記低」API/UI）、preference 低頻抽取。做完 #6 先算 Layer 1 完成。
- **Layer 2**：#9（hybrid 接線或刪）、#16（global 寫手：diet trigger tagging Q29 / product 庫 Q28 / correlation detector Q30 / 目標+趨勢 Q26）、rolling 1M/3M 對比 UI 呈現（Q12 code 已寫，UI 未用）、demo environment + seed script（Q10/Q19）。
- **Layer 3**：delete/edit UI（Q32）、Docker 修復（#18）、roadmap v2（用呢張表做底）、blog/demo video、Settings 已經有測試連線。
- **Docs sweep（(a) 類）**：architecture node 數/checkpointer/Ollama/RAG 字眼、eval-report-sample 同 demo-script 數字、README 部署段、roadmap 標題註 —— ✅ 已完成（今輪）；剩 #18 Docker 屬 code 唔係 docs。

## 面試前 checklist

- [ ] 真 vision smoke test（開 ☁️、影相 → `vision_used: true`、badge 出現）
- [ ] 新 conversation 第一次 upload → 詳盡 onboarding 回覆（baseline 解釋）
- [ ] Reload 頁面 → thread 仲喺度（#15）
- [ ] `python -m pytest -q` 40 綠 + `npm run typecheck` + `npm run build`
- [ ] `python -m eval.run_eval --fake` 100% + 3 scenarios PASS（#12）
- [ ] 揀好面試敘事用邊幾條真 claim（#1/3/6-partial/7/11/12/14）——每條都要答到「點 control LLM」
- [ ] Docker `compose up` 撳得郁（#18）／或改敘事為「local dev 即 demo」
