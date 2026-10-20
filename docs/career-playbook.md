# 用 SkinCoach 準備 AI programmer 面試（個人筆記，唔係 product doc）

> 呢份係寫俾你自己嘅：點樣用呢個 repo 練功、點樣講、邊啲位唔好講。
> Product 嘅 claim 狀態一律以 [`status-vs-claims.md`](status-vs-claims.md) 為準，唔好喺面試講得比嗰張表更叻。

## 0. 一句話定位（電梯簡報）

> 「我一個人由零建咗一個 AI 護膚教練：5-node agent、hybrid retrieval、348 個 backend test、CI gate。
> 但真正學到嘢嘅係——我發現自己個 gate **唔會 fail**，然後用成個 audit 去修正『我以為我做咗』同『我真係做咗』之間嘅距離。」

呢句嘅威力在最後半句。大部分 junior 講「我用咗 X、Y、Z；你講嘅係「我發現自己講大話，然後修好」。後者係 senior 思維。

## 1. 呢個 repo 已經證明你識咩（可以照講嘅證據）

| 能力 | 證據（面試可以指名道姓） | 一句話點講 |
|---|---|---|
| 讀 code 對文件 | `docs/status-vs-claims.md` 27 行逐行 verdict；#16 sweep | 「我寫咗張表，每一行 claim 都要講清楚係 offline 定真環境驗證過」 |
| 設計驗證機器 | 348 test ＋ `eval.run_eval --fake` 入 CI ＋ 非像素 Playwright 入 CI | 「綠代表 source-level 行為同 wiring 過，唔代表 ranking 質素」 |
| 捉「假綠」 | #17：eval 量 function、產品行 wiring；我加咗 reciprocal wiring test 同 mutation 驗證 | 「我試過故意 revert 個 tool，睇下 gate 會唔會紅——會」 |
| Debug 環境 | CI 紅：`npx vite` 喺 runner 綁 `::1`，Playwright poll `127.0.0.1` → 加 `--host 127.0.0.1` | 「呢個 bug 本機永遠重現唔到」 |
| 資源生命週期 | #23 orphan 相（24h sweep ＋ 409 規則）、#27 未送出嘅片 | 「刪嘢要分兩條路：用戶撳掣即時刪，同離開頁面嘅 TTL 掃描」 |
| Domain 建模 | #21 同一日再打卡唔再覆蓋（`mentioned` 旗標 ＋ merge policy） | 「一句含糊嘅訊息唔應該抹走今朝嘅讀數」 |
| 誠實決策 | #10 親手拆自己 RAG 嘅賣點、#9 承認 pipeline 唔係 agent | 「我寧願講細啲但講得真」 |
| 性能 | 縮圖 82%（660 KB → 119 KB）、SSE 串流五個 node | 「等 5.4 秒好過乜都唔見」 |

## 2. 佢仲未證明嘅嘢（誠實清單 — interviewer 一定會問到）

- **未部署過**：image 從未 build（Docker daemon 唔成日開）。→ 呢個係最大嘅 credibility gap。
- **冇第二個用戶**：single-user、local-first，冇 auth、冇 multi-tenant。
- **Eval 數字弱**：golden index 得 4 chunks，recall 數字證明唔到檢索質素。
- **冇 production 可觀察性**：只有 `runs.jsonl`，冇 metrics／trace／alert。
- **冇 load/perf 數據**：唔知 10 個人同時用會點。

**點講先唔扣分**：唔好假裝，直接講「我知道呢個 gap 喺邊，我嘅下一步係 X」。一個講得出自己邊度未做嘅人，比一個乜都話做咗嘅人可信十倍。

## 3. 「IT programmer」同「新 AI programmer」真正嘅分別

用呢個 repo 嘅經驗翻譯：

| 層 | 傳統 IT programmer | AI programmer（多出嚟嘅） |
|---|---|---|
| 交付 | 跟 spec 交功能、識 framework、寫 unit test | 一樣，但 spec 本身係「輸出唔確定」——要設計 eval 同 guardrail |
| 驗證 | test 綠 = 做完 | test 綠只證明 wiring；要另外證明「答案好唔好」，而且要講清楚綠代表咩 |
| Debug | 重現、縮細、修 | 一樣，再加「model 版本／prompt 一改就靜靜 regression」 |
| 成本 | 唔太理 | token、延遲、judge 成本都要有預算意識（5.4 s 中位、14 張相 660 KB 呢類數字） |
| 溝通 | 報進度 | 報**能力邊界**：邊啲 claim 驗證過、邊啲未有、憑咩 |

一句總結：**AI 令「寫 code」變便宜，令「證明你寫嘅嘢係真」變貴。** 你喺呢個 repo 練嘅正正係後者——呢個就係市場上稀缺嘅部分。

## 4. 四星期 drill（每星期 3 個動作，做完打勾）

**Week 1 — 補最大嘅洞**
- [ ] 開 Docker Desktop，`docker compose up --build`，行得郁就 `curl /health`。
- [ ] 用 DB 已有嘅真相行一次真 `/api/consult`，確認 `vision_used: true`（issue #8 嘅 HITL 半場）。
- [ ] 錄 90 秒 demo（手機 screen record 都得）：由打卡 → 分析 → 記錄 → 摘要。

**Week 2 — 練講**
- [ ] 合上 `docs/` 三份 audit，口述 5 個 finding（錄音，自己聽返）。要求：每個 finding 有「我以為 → 實際 → 我點修」。
- [ ] 寫 blog 大綱：*「I found 12 false claims in my own repo — and built the machine that catches them」*。
- [ ] 準備 5 個 STAR 故事（下面第 5 節有開頭，補結尾）。

**Week 3 — 練答**
- [ ] Mock interview：我叫你扮演 interviewer 問 10 條（第 6 節），你限時答，我評分。
- [ ] Code review drill：隨機開一個舊 commit，用 10 分鐘講「呢個 diff 有咩風險」。
- [ ] 白板題：畫一次 consult 嘅 5-node 流程 ＋ 邊度可以 fail、邊度要 stream。

**Week 4 — 出手**
- [ ] 改 CV／LinkedIn（第 7 節），每投一份先改一次 bullet。
- [ ] 投 10 份（HK：銀行 finTech、保險、AI startup、agency 各 2–3 份）。
- [ ] 覆盤：每個拒絕／無回覆，記低「係 CV、係技術、係 domain、定係 timing」。

## 5. 五個 STAR 故事（開頭已寫好，補你自己嘅細節）

1. **「我個 gate 唔會 fail」**（#17）— Situation：四份 audit 獨立講同一件事。Task：證明定否證。Action：revert tool → 全套綠；寫 reciprocal wiring test；mutation 驗證。Result：門檻由「print 靚數字」變成「紅就 merge 唔到」。
2. **「一句含糊嘅訊息抹走咗今朝嘅讀數」**（#21）— S：同日再打卡，entry 整條被覆寫。T：保留舊讀數但唔凍結。A：`mentioned` 旗標 ＋ per-attribute merge ＋ 記憶只為真係提及嘅 attribute 更新。R：10 個 test、memory 唔再被假 0 污染。
3. **「本機永遠重現唔到嘅 CI 紅」**（IPv4）— S：新加嘅 UI gate 喺 GitHub 紅，log 冇 vite 輸出。T：喺 Linux runner 行得郁。A：`npx vite --host 127.0.0.1`、timeout 120 s、`stdout: 'pipe'` 令下次有 log。R：61 passed。
4. **「我拆咗自己嘅差異化」**（#10）— S：RAG 係 sell point。T：驗證佢值唔值。A：發現 golden index 得 4 chunks、production index 92% 英文、chunker 漏 ASCII 句號。R：改講 grounding／citation／control，寫低可證偽 revisit bar。
5. **「刪錯記憶會令舊記憶復活」**（#19）— S：delete insight 會清 `superseded_by`。T：定義「刪」嘅語義。A：改成 retire（`expires_at = now`）而唔係 revive；補 6 條 guard test。R：memory 層嘅保證終於同文件一致。

## 6. 會被問到嘅技術題（同呢個 repo 嘅答案）

- **你點 test 一個 LLM 功能？** → 三層：deterministic fake mode 嘅 eval harness（wiring、schema、safety）、source-level wiring 斷言、錄真 provider response 喺 CI replay。加一句「綠代表 wiring，唔代表質素」。
- **你點知 RAG 有冇用？** → 老實答：我呢個 4-chunk index 證明唔到；我會要 ≥3000 條真 chunks、≥100 條標註 query、random ＋ BM25 baseline。
- **設計一個教練嘅記憶系統** → write／read path 對稱（過期嘢唔可以喺 prompt 出現）、supersede、delete 語義（retire 唔係 revive）、global vs per-body-part scope。
- **你點 deploy？** → compose（backend＋frontend）、boot 時行 migration（`_COLUMN_MIGRATIONS` ＋ NOT NULL rebuild）、`/health` 報 resolved adapter、data dir 掛 volume；未做：auth、multi-user、備份策略。
- **最難嘅 bug？** → 三個都講得：同一日覆寫、orphan 資源、CI IPv4。
- **你個 pipeline 算唔算 agent？** → 唔算 autonomous agent；分支喺 model 嘅 `tool_calls` 同 deterministic guardrail，唔喺圖嘅邊。呢個係故意嘅控制決定。
- **點解唔用 vector DB／LangChain？** → 規模唔需要；SQLite JSON ＋ cosine 夠，少一個 infra 依賴；要換嘅話 interface 已經隔開（`rag/`）。

## 7. CV／LinkedIn 用字（有數字，唔 overclaim）

- Built a single-user AI skincare coach (FastAPI · React · SQLite): 5-node agent, hybrid retrieval, **348 backend tests**, CI gate (pytest + eval + Playwright) on every push.
- Ran a **27-claim self-audit** into a verified/corrected/out-of-scope ledger; fixed **four classes of gates that could not fail** (eval measured a function the product never called).
- Cut image payload **82%** (660 KB → 119 KB per screen) with DPR-aware thumbnails; streamed the agent's nodes to remove a 5.4 s silent wait.
- Designed a same-day **per-attribute merge policy** so a vague follow-up no longer erases earlier readings; memory only strengthens on attributes the user actually mentioned.

## 8. 唔好做嘅事

- 唔好講「我用 AI 寫得好快」——interviewer 聽唔到能力，只聽到風險。
- 唔好把 RAG recall 100% 當賣點（4-chunk index）。
- 唔好講「差啲 deploy 咗」；要麼 deploy，要麼講清楚點解未。
- 唔好背答案；每條都要有你親手做過嘅細節（commit、issue、test 名）。
- 唔好把 audit 講成「之前嘅人寫得差」——全部係你自己嘅 code，講「我發現」。
