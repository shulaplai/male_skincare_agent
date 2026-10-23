# 未完成嘅 findings（handover）

> 用途：一次審計（`docs/status-vs-claims.md` 全部 27 行逐行驗證）之後嘅**交收清單**。
> 分三類：**已經修好**、**要你決定先可以改**、**環境／人手先做得到**。
> 決策嗰啲唔喺呢份文件重複 —— 佢哋住喺 GitHub issues（見 `docs/agents/issue-tracker.md`，搵 `wayfinder:map` label）。
> 最後更新：第三輪（六項 UI／數據要求，見 §10）。

---

## 一、已經修好（有驗證）

全部改動都跑過 `pytest -q`（當時 77 綠；呢個 repo 而家係 373）+ `npm run typecheck` + `npm run build` + `eval.run_eval --fake`（exit 0）。

| 原本問題 | 改動 | 點證明 |
|---|---|---|
| **`#18` 真 DB 拒絕所有 global 寫入**（diet timeline / 全局 fact / 全局 preference 全部 500） | `app/db.py` 加 table-rebuild migration：`init_db()` 見到 DB 係 `NOT NULL` 但 model 已經係 nullable，就會 create → copy → drop → rename，連 index 一齊重建 | 喺**真 DB 嘅 copy** 度行：行數一個冇少（6 insights、3220 chunks）、9 個 index 齊、`POST /facts` + `POST /events` 由 500 變 200、`global_events` 由 0 變 1。真 DB md5 全程不變 |
| **`#17` gate 講大話**：runtime 改返純 `retrieve()` → 三個 CI job 全綠，eval 仍然印 hybrid 100% | `eval/run_eval.py` 嘅 `failed` 收埋 `recall_hybrid`；`tests/test_hybrid.py` 加 wiring 斷言 | 兩個 sabotage 都重演過：① 改返 `retrieve()` → 新測試 **FAIL**（以前 73 綠）② hybrid ranking 爛 → eval 印 `80%`、**exit 1**（以前 exit 0） |
| **`#19` 30 日衰減只喺寫入時生效**：過期 insight 照樣出現在 `/summary`，仲會以**更高** confidence 餵入 coach prompt | `/summary`（`app/main.py`）同 `get_skin_profile`（`app/agent/tools.py`）加 expiry filter | 新檔 `tests/test_memory_read_paths.py` 兩個測試；抽走 filter → 兩個都 FAIL（呢條規則之前完全冇 guard） |
| **`#13` 真 LLM `analyze` 5/7 次失敗**（production `/api/consult` 路徑） | `app/agent/llm.py` `_invoke()`：parse 失敗重試一次。**故意唔做 fallback** —— 冇誠實嘅 fallback analysis，作出嚟就係將假數據寫入用戶紀錄 | 新測試：第一次失敗會重試並成功；連續失敗仍然 propagate（唔會被吞） |
| **`#15` 讀唔到相時講假嘢**：明明 consent 開咗，卻同 model 講「本地模式，相唔會離開用戶部機」，model 仲要轉述俾用戶 | `app/agent/graph.py` + `app/agent/prompts.py`：`vision_attempted` 喺 fallback **之前**計算；新增 `vision_reason`（`photo_unreadable` / `vision_error` / `consent_off` / `fake_llm` / `no_photo`）；讀唔到相改用獨立措辭，唔再假稱本地模式 | suite 綠；trace 多咗一個可查嘅欄位 |
| **chunker 忽略 88% 語料**：句子邊界 regex 冇 ASCII `.`，英文 PMC 文本平均 2520 字/chunk（最大 53k），遠超 embedder 512-token 窗 | `app/rag/chunking.py` regex 加 `.`/`!`/`?`（**只喺後面有空白時**才切，所以「0.5%」唔會被切散） | 驗過 5 個 case（英文正常斷句、「0.5%」完整、CJK 不變）；golden corpus 仍然 4 chunks、eval 數字不變 |
| **`#12` 前端 race**：`useSummary` 冇 cancellation guard（兄弟 hook 有），切部位時舊 response 會蓋新嘅 | `frontend/src/hooks/useSummary.ts` 加 `alive` guard，同 `useCorrelations` 一致 | typecheck + build 綠 |
| **D3 Settings「測試連線」永遠失敗**：Vite 只 proxy `/api`，但 health check 打 `/health` | `frontend/vite.config.ts` 加 `/health` proxy | typecheck + build 綠（之前只有 nginx 路徑行得通） |
| **`#24` `seed_demo.py --out` 可以刪咗真 DB** | `backend/scripts/seed_demo.py` 加防護：指向真 DB 就拒絕 | 實測 `--out ./data/skincoach.db` 被拒、真 DB md5 不變；正常路徑照行 |
| **C2 `trace_consult.py` 永遠唔會寫 run log**（所以 checklist「`data/runs.jsonl` 有紀錄」係假） | `scripts/trace_consult.py` 呼叫 `service.write_run_log()`（順便將 `_write_run_log` 變公開名），連 trace 一齊寫 | 實測寫出一行，5 個 node 齊 |
| 3 個誤導性註釋／docstring | `chunking.py`（section 冇 producer）、`prompts.py:7`（指向唔存在嘅 `test_prompts.py`）、`models.py:108`（`direction` 寫住 `better\|worse\|same`，但 code 只寫 `problem\|normal`） | — |
| **D10 `HF_HOME` 係假指示**：fastembed 只認 `FASTEMBED_CACHE_PATH`，所以 model cache 落 container temp、每次 recreate 重新 download | `backend/Dockerfile` 改用 `FASTEMBED_CACHE_PATH=/app/data/.fastembed-cache`（即 bind volume）；`docker-compose.yml` 加同一個 var；`AGENTS.md` 同 `.env.example` 嘅 `HF_HOME` 指令改返正確 | `docker compose config` exit 0 而且 render 出 `FASTEMBED_CACHE_PATH: /app/data/.fastembed-cache`；fastembed 只讀呢個 var（實測 `define_cache_dir`）。⚠️ **container 內部路徑未經 runtime 驗證**（呢部機冇 build 過 image） |
| **`AGENTS.md` 自身嘅 stale 內容** | 表清單補返 `products`（9 張表只列咗 8）；run-log 措辭改成「`POST /api/consult` 同 `trace_consult.py` 都寫」；cache env var 改返正確 | 對 `models.py` / `service.py` 核實 |
| **23 個文件 vs 現實嘅事實修正**（D1–D19 之中非決策相關嗰批）+ test 數 73 → 77 | `docs/*.md`、`README.md`、`backend/README.md`、`AGENTS.md` | 逐條對 code／指令核實；`eval-report-sample.md` 改成 generator 真實輸出 |

---

## 二、要你決定先可以改（唔應該由 agent 自己揀）

呢啲唔係「難改」，而係**改邊個方向取決於產品決定**。全部喺 GitHub：

| Issue | 要決定咩 |
|---|---|
| [#9](https://github.com/shulaplai/male_skincare_agent/issues/9) | 線性 5-node pipeline 算唔算 agent？要唔要真分支？ |
| [#10](https://github.com/shulaplai/male_skincare_agent/issues/10) | RAG 係差異點定負累？invest（真 corpus + ≥100 條 chunk-level query + 公佈 random/BM25 baseline）／reframe／cut |
| [#11](https://github.com/shulaplai/male_skincare_agent/issues/11) | Roadmap Phase 0–5 分解同「三個月」本身對唔對 |
| [#12](https://github.com/shulaplai/male_skincare_agent/issues/12) | 前端要唔要真 harness（已修嘅 race 只係其中一個症狀；冇 runner 就同類 bug 照樣上得） |
| [#14](https://github.com/shulaplai/male_skincare_agent/issues/14) | Provenance 政策：FakeLLM 回合唔應該同真分析一模一樣（要改 schema + UI，所以要你揀政策） |
| [#17](https://github.com/shulaplai/male_skincare_agent/issues/17) | 仲未做嗰半：**branch protection**（repo 設定，只有你可以開）同埋要唔要真-LLM fixture replay |
| [#19](https://github.com/shulaplai/male_skincare_agent/issues/19) | 10 條冇 guard 嘅規則，我補咗 3 條（wiring、expiry ×2）；剩低嗰啲要唔要一齊補 |
| [#16](https://github.com/shulaplai/male_skincare_agent/issues/16) | 決策相關嘅 claims 表措辭（`#8/#9/#10/#18/#21/#22`）—— 等上面決定完才寫得準 |
| [#8](https://github.com/shulaplai/male_skincare_agent/issues/8) | 真 vision smoke test（真相 + UI badge） |

---

## 三、環境／人手先做得到

- **Docker `compose up --build`**：`docs` 之前寫「daemon 未開」係**錯**嘅 —— `docker info` 顯示 server 27.4.0 而且有 container 跑緊。所以呢步隨時做得，只係要你開。
- **真相 vision smoke test**：開 ☁️、用手機／真相 upload、確認 `vision_used: true` 同 badge 出。
- **Branch protection**：`main` 而家冇 protection、冇 ruleset，而 CI 曾經紅住照上 main。呢個係 GitHub repo 設定，唔關 code 事。
- **真-embedder eval**：要 download 0.22 GB model，而且 fastembed 版本之間 pooling 未 pin。
- **手機版 UI 冇自動化回歸防線**：手機版（第 4 套 layout shell）**已經實作並實測過** —— 用 Chrome DevTools Protocol 對真瀏覽器（真 backend + `scripts/seed_demo.py` demo DB）量過 390／760／761／900／1140／1280px：窄屏自動入 `layout-mobile` 單欄、底部 tab bar 5×78px、`scrollWidth == innerWidth`、zero console error；闊屏三套同加手機版之前**逐 px 一樣**。**但**個 harness 係 ad-hoc 寫喺 `/tmp`、冇入 repo、CI 唔會重跑，`frontend/package.json` 仍然冇 `test` script。所以「手機版每次改動都唔會爆」**冇任何自動化保證** —— 呢個正係 [#12](https://github.com/shulaplai/male_skincare_agent/issues/12) 未決嘅問題。要補就係開 #12 個決定，唔應該由實作手機版嘅人順手塞個 harness 入去。

---

## 四、刻意**唔**改（同原因）

| 唔改嘅嘢 | 為何 |
|---|---|
| **Journal 顯示 product id**（`🧴 5680cffc…`） | 修法係 `/summary` 要 resolve id → name。技術上細，但會改 API response shape + 前端 types，屬「改形狀」多過「執 bug」—— 想你決定之後才動。 |
| **`/api/settings` 報 configured 而唔係 resolved model** | 屬 #14 嘅 provenance 政策一部分，一齊改才好。 |
| **Vite 之外仲有 Config drift（D8/D10 部分）** | 已交文件 sweep 處理；剩低涉及行為嗰啲等決定。 |
| **`archive/skinfile/`** | 博物館，唔動。 |
| **Demo video** | 要真人錄。 |

---

## 五、審計自己嘅更正（誠實記錄）

1. **我曾經寫錯真 DB 嘅失敗形狀。** 我報過「`/summary` 同 `/correlations` 回 500」，錯。實測：`/health`、`/api/conversations`、`/summary`、`/correlations`、`/messages` **全部 200**；只有兩個寫入 500。而且呢個版本更陰險 —— 冇嘢睇落壞，`/correlations` 仲會安慰用戶「影多啲相就會開始比較」，但餵佢嘅 diet 事由根本寫唔入。已喺 #18 / #3 / 地圖更正。（源頭係一個已經被撤回嘅 repro，我未核實就轉載 —— 同呢個審計一直捉嘅毛病一模一樣。）
2. **D16 係假 finding。** 審計話 `docs/demo-script.md:35` 引用嘅「方向 02」唔存在；實際上 `design/index.html:51` 有定義。文件 sweep 拒絕改，正確。
3. **`run_log_enabled` 唔係 run log 消失嘅原因。** 我 charting 時猜係 feature flag（仲引錯 `config.py:59`）。真相：`run_log_enabled` 預設 `True`（`config.py:58`），係 `trace_consult.py` 繞過咗唯一嘅 writer。已更正，而且今次順手修好。

---

## 六、第二輪（商品評估／指南／影片）—— 2026-09

第一輪（上面）係「逐條驗證 claims 表」。第二輪做三件新功能，順便再撞出幾個真 bug。
以下每一項都係**今次實測過**，唔係「應該冇問題」。

### 6.1 已經做咗而且驗過

| 做咗咩 | 點證明 |
|---|---|
| **T1–T5：一條訊息唔再等於一次打卡**（假 Entry 覆蓋當日讀數、假「改善」永久凍結、假 note、假「暗瘡：正常」記憶、`first_checkin` 被問題消耗） | 閘＝`SkinAnalysis.observes_skin`（LLM 判）`or vision_used`。真 LLM 實測：問產品 → `entry_written: false, timeline_lines: 0, insights_created: 0`；描述皮膚 → `true, true, 6 attributes`。`tests/test_persist_evidence.py` 8 個 |
| **`TOOL_GUIDE` 令真 LLM 撞死**（產品問題 5/7 次 `OutputParserException: Unknown tool type`） | 改措辭（唔可以寫「你可以 call 呢啲工具」）＋`llm._invoke` 帶 `FORMAT_CORRECTION` 重試＋`service` 轉 HTTP 503。改後 3/3 成功、0 parse failure（改前 2 次入面 1 次爆） |
| **guardrail 睇唔到 `Advice.reply`**（用戶真係睇到嘅 bubble 完全冇掃） | 掃描範圍加 `reply`；`"mg"` 由 substring 改成 `DOSE_RE`（要有數字前綴）。`tests/test_guardrails.py` |
| **`DELETE /api/conversations/{cid}` 冇刪檔** | 實測：上載一張相 → 刪 conversation → `.jpg` 仍然喺 disk。修法係喺 cascade **之前**收集路徑。再實測：7 張相 + 2 條片 → `files_removed: 9`，data dir 乾淨 |
| **`video_file()` 搵唔到壓縮過嘅片**（`compress_video` 寫 `<id>.c.mp4`） | 條片既搵唔到亦刪唔到，`DELETE` 會靜靜報「冇嘢刪」。修法：兩個 spelling 都認。`tests/test_video.py` 封住 |
| **影片上載**（≤20 秒、≤6 格、>40MB 自動重編碼、串流寫 disk、`Video` row） | 真瀏覽器 CDP 實測：20 秒橫掃片 → 6 張相（全部 200 `image/jpeg`）、20 秒定鏡片 → **1 張**＋警告、相機 tooltip 有「鏡頭慢慢掃過成塊肌」。真 LLM 睇咗 6 張之後照實講「睇唔到皮膚紋理」而唔係亂評 |
| **商品評估（chat 內）** | 兩條入口共用 `product_context.py`；`looks_like_ingredient_list()` 結構判斷（12 句口語 0 false positive）；真 LLM 實測貼 `成份：…` → `unknown: 0`、`matched: [菸鹼醯胺, 水楊酸]`、reply 完全跟程式算出嚟嘅事實、**當日真打卡 Entry 冇被改** |
| **指南（男士護膚基本資料）** | 「應該用咩產品」由 `recommend.RULES` **生成**，所以指南同 agent 推薦唔可能唔一致；10 條引文對真 DB 逐條驗 |
| **文件事實修正**（我自己寫錯嘅） | ① 「影片冇大細上限」係錯，上限係 `video.MAX_BYTES` = 100MB（>100MB 回 413）② 「匯出唔包含片」係錯，`export_zip()` 用 `rglob` 所以一直在內（`test_export_includes_stored_clips` 封住）③ `backend-flow.md` §3.4 寫住 `Entry` 係「無條件」寫入 —— 嗰個係修好**之前**嘅行為 |

### 6.2 剩低未做

| 項目 | 狀態 | 要咩 |
|---|---|---|
| **成份字典 31 / 目標 ≥200** | 種子都係 IECIC 真名 + 逐條 `corpus=` 引文（`tests/test_ingredients.py` 對真 DB 驗） | 要你批一個 IECIC 來源／授權，唔可以由我手寫成份名（= 憑空造事實）。見 `docs/product-eval-plan.md` D4 |
| **`Product.ingredients` / `Product.category` 從來冇被寫過** | 靜態欄位，冇任何 code path 填 | 要決定：係咪真係要儲成份表？儲咗就有「用戶產品庫」同過期問題 |
| **`/products/evaluate` endpoint 前端未用** | 程式化入口；chat 已經覆蓋同一個功能（而且係用戶揀嘅做法） | 睇你要唔要一個「產品庫」畫面；唔要就當佢係 integration surface |
| **前端完全冇自動化測試** | 手機版同影片 UI 都係我用 ad-hoc CDP script（喺 `/tmp`，冇入 repo）量過 | 要開 [#12](https://github.com/shulaplai/male_skincare_agent/issues/12) 個決定：要唔要真 harness |
| **真 vision smoke test（真臉相）** | FakeLLM 永遠唔行 vision，所以 `--fake` 完全冇覆蓋 | 要真人用手機拍一張 |
| **壓縮率未實測真手機片** | 合成片內容太平淡，達唔到 40MB 門檻 | 要一條真 4K 片。壓縮**路徑**已有確定性測試 |

### 6.3 第二輪學到嘅（同類 bug 嘅形狀）

三次都係同一個形狀：**同一個概念有兩個實作，中間有盲點**。

1. `guardrails` 掃 `items`、`eval/safety` 又掃 `items` → 互相照唔到，`reply` 冇人掃。
2. 商品評估 route 同 graph 各自砌 inputs → 遲早對「用邊個 profile」有分歧。
   所以收埋喺 `product_context.py`，`test_the_route_and_the_chat_path_agree` 逐 field 比對。
3. 影片檔名：`video_file()` 認 `<id>.mp4`，`compress_video()` 寫 `<id>.c.mp4` → 刪唔到。

**推論**：呢個 repo 每次「同一個概念寫兩次」都出事。加新功能時先問「呢個概念已經有冇
一個定義？」，有就一定要經過佢。

---

## 七、點自己驗返

```bash
cd backend
./.venv/bin/python -m pytest -q                    # 373 passed（2026-10-21）
./.venv/bin/python -m eval.run_eval --fake         # exit 0
md5 -q data/skincoach.db                           # 應該係 40823465d6041edf11c05a44f07d88b9

# migration 會喺下次 backend 啟動時自動修好舊 schema；
# 想先睇效果（安全，唔掂真 DB）：
cp data/skincoach.db /tmp/check.db
SKINCOACH_DATABASE_URL=sqlite:////tmp/check.db SKINCOACH_DATA_DIR=/tmp/checkdata \
  ./.venv/bin/python -c "from app.db import init_db; init_db()"

docker compose config | grep FASTEMBED_CACHE_PATH   # 應該見到 /app/data/.fastembed-cache
cd ../frontend && npm run typecheck && npm run build
```

> **⚠️ 一個要留意嘅副作用**：`init_db()` 嘅 rebuild 會 `DROP TABLE` 再 rename。實測行數、index、內容都保留，但呢類操作永遠值得先備份：
> `cp backend/data/skincoach.db backend/data/skincoach.db.bak`

---

## 八、第三輪：真用戶試用（2026-09-30）—— 見 `docs/user-trial-findings.md`

前兩輪係**審計 code 同 claim**（由上而下）。第三輪相反：唔睇 code，用真瀏覽器＋真 LLM 由零行一次
完整流程（14 次 consult），逐格量度。詳情、數字同證據路徑全部喺 **`docs/user-trial-findings.md`**。

最重要嗰四條（**全部已修**，附 test 同瀏覽器量度）：

1. **桌面對話一長（≈5 條訊息）輸入框跌出畫面 ~10,000px** —— `.app` grid child 冇 `min-height: 0`
   （實測 26 條訊息 → `scrollHeight 10771 / innerHeight 900`；修好後 900、thread 內部 scroll）。
   **唔係工作樹 regression**，HEAD 嘅 `.app` 一樣。
2. **iPhone 預設 HEIC 相上載 → HTTP 500**（Pillow 冇 `pillow-heif`，冇人接 exception）→ 改回 415 ＋
   可讀廣東話指示。
3. **首次純文字打卡會講「呢張相已經幫你建立咗 baseline」**（無相）—— `prompts` 嘅 `first_checkin`
   分支無條件寫「呢張相」；呢個係 #15 嘅鏡像（一個講有相、一個講冇相）。
4. **手機版對話完全 scroll 唔到、輸入框唔喺畫面**（**用戶喺真手機上撞到，即場修**）——
   `.chat` 冇 `min-height: 0`，flex（`.shell-scene`）同 grid（`.shell-chat`）兩邊都撐到內容高度
   （390×844 實測 `.chat` 4237px、`.thread` scrollable 0、`.compose` top 4221，而
   `.app.layout-mobile` 係 `overflow: hidden` → 冇任何方法 scroll）。**同第 1 條同一個 family，
   只係喺再落一層。** 順手加「跟住最新一句」（`.thread` 係內部 scroll 容器，reload 之後原本永遠
   停喺最舊一條；`<img onLoad>` 都要重新 pin，因為相係 async 載入）。

> **方法論教訓（值得記住）**：第三輪「窄屏實測通過」係**假綠**——只量咗 page 層
> （`scrollWidth == innerWidth`、tab bar 齊），而 thread 當時只有 2 條訊息。**長內容 ＋
> 量到「composer 喺唔喺 viewport 內」** 才會抓到。第四條係用戶自己用手機用出嚟嘅。

**未修、要你決定**（已開 issue，見 `docs/agents/issue-tracker.md`）：同日 Entry 覆蓋政策、
偵測到嘅事件 chip 保存、上載完冇送出嘅相檔案殘留、HEIC 原生支援（#21–#24）。

> 你自己試用時撞到嘅嘢 → 寫入 **`docs/user-notes.md`**（空白模板 ＋ 已知未修問題嘅重現步驟）。


---

## 九、第四輪：手機 UI/UX（2026-10-01，用戶逐項指令）

用戶喺手機上實際用（Tailscale `100.120.154.43:5174`）之後逐項指出 8 個問題。今次**唔係審計**，
係產品 owner 直接下指令，全部已實作＋量度驗證。詳情／數字見下面；每個改動都有「點解」（唔係純口味）。

| # | 用戶要求 | 做咗咩 | 證據 |
|---|---|---|---|
| 1 | 以後永遠雲端、唔好再顯示雲／本地，但用戶一定要畀 consent | 新增 `User.photo_cloud_consent` + `consent_at`（`_COLUMN_MIGRATIONS`）；`GET/POST /api/consent`；`ConsentGate` 一次性同意畫面（要打勾＋撳掣）；**刪走** conversation 級 toggle（route 冇埋）、ShellTop 嘅「雲分析」掣、composer 嘅 `☁️/🔒` chip、側欄／Settings 嘅模式標示。Gate 喺 `service.run_consult`（server-side） | `tests/test_consent.py`（6 個）；apps 未同意時 `/api/consult` 有相 → `cloud_analysis: False` |
| 2 | Tab 要真係跳 page，reload 唔應該跌返第一頁 | `hooks/useSceneRoute.ts`：scene 寫 URL（`?scene=chat`，home 唔寫）＋`pushState`＋`popstate`；`MobileShell`／`StandardShell` 都改用 | 撳「對話」→ `/?scene=chat`；reload 後仍然 `對話` active、6 條訊息；上一頁 → `/?`＋`今日` |
| 3 | 相上載完要模糊，撳「顯示」先睇；size 再細 | `components/BlurPhoto.tsx`（每次 render 由模糊開始，唔記「睇過」；`alt` 跟狀態）；對話相 168×224（3:4）／手機 132、composer 預覽 46–48px | 量到 `blurred 2 → 撳一次 → blurred 1 / shown 1`；手機相闊 132（blur 時視覺 145 = ×1.1 防邊） |
| 4 | composer 三個 icon 只留一個（相機） | 刪相簿掣（同相機本來係同一個 file input，冇功能損失）、刪「＋ 今日記錄」quickbar | `.compose .iconbtn` = **1** |
| 5 | 底部 5 個 icon 用返正常 nav UI icon、同文字對齊 | 新增 `layouts/navIcons.tsx`（inline SVG：屋／氣泡／清單／柱狀圖／滑桿，`stroke: currentColor`），`TabScene` 收窄＋`Record` 逼編譯期齊全 | 5 個 tab `iconTop`/`labelTop` 完全一樣（800.1／825.1），pitch 78px |
| 6 | chat 捲到最底，bar 下面有空位 | 高度鏈改 `html, body, #root, .app { height: 100% }`＋`body { overflow: hidden }`（唔用 `100dvh`：dvh 跟 URL bar 動態變，喺 nested scroller 捲動時 re-layout 落後） | `tabBar.bottom = 844 = innerH`；`docScrollable = 0` |
| 7 | 發送掣用箭嘴 icon | `.send` 變 44px 圓形箭嘴 SVG；送緊時換轉圈（`@keyframes spin`），冇文字 | `sendSvg: true`、`sendText: ""` |
| 8 | 輸入框要識得撐大 | `<input>` → auto-grow `<textarea>`（量 `scrollHeight`，上限 132px 之後自己 scroll）；`.compose { align-items: flex-end }`；**Enter 送、Shift+Enter 換行、擋 `isComposing`**（中文輸入法確認候選字會 fire Enter） | 桌面 45→87→45；手機 72→132（cap）→送完 72；Shift+Enter 只加行（`msgs` 不變） |

**順手修好嘅真 bug（唔喺用戶清單，但係佢第 1 項講嘅現象嘅根因）**：
`Chat.tsx` render `msg ${m.role}` = `msg user`，而 CSS 分邊係 `.msg.me`（`row-reverse` + `margin-left: auto`）
—— **由頭到尾冇 match 過**，所以用戶自己講嘅嘢同 AI 一樣靠左（390px 實測兩邊都由 x=57 開始、`.a.user` 冇色）。
加 `role → me/coach` mapping 之後：`me` = `row-reverse`、右邊內縮 57px（同教練嗰邊左內縮對稱）。

**刻意未做／要你決定**：
1. 「今日記錄（飲食／產品）」嘅手動入口隨住 #4 消失（`POST /api/conversations/{cid}/events` 同
   `applyEvents` 都仍然在，AI 偵測到嘅「我留意到…✅ 記低」chip 亦照用）。要唔要搬入「記錄」tab？
2. 撤回同意：API 有（`POST /api/consent {granted:false}`），但 UI 冇入口。
3. 手機底部空位：Chromium 量到完全貼底。如果實機 **Android** 見到嘅空位係 system bar inset
   （`viewport-fit=cover` 之下 `env(safe-area-inset-bottom)`），要唔要照樣畫落去？要實機再影一張對照。

### 九之二、同日追加（用戶第二輪指令）

| 要求 | 做咗咩 | 證據 |
|---|---|---|
| Consent 預設 `true`（「基本上都係得我用」） | `settings.require_photo_consent=False` 為預設 → `get_or_create_default_user` 直接寫 `photo_cloud_consent=True`，`init_db._normalise_consent_policy()` 補返舊 row（**只補 `consent_at IS NULL`**，撤回過嘅唔會自動開返）。`SKINCOACH_REQUIRE_PHOTO_CONSENT=true` 就變返多用戶模式（同一條 code path，gate 照樣 server-side） | `tests/test_consent.py` 9 個（含「撤回之後重啟唔可以自動開返」）；`GET /api/consent` → `{"granted":true,"at":"2026-10-01T09:47:42","required":false}` |
| 飲食／產品要由 AI 喺對話抽取出嚟 | 機制本身係 `Advice.detected_events` +「我留意到…✅ 記低」，但**以前只存在 browser live state，reload 就消失**（issue [#22](https://github.com/shulaplai/male_skincare_agent/issues/22)）→ 已修：`persist` 寫入 coach payload、`format.ts` restore、確認後標 `events_applied`（有 message id 用 id，session 內新訊息用事件內容配對）。Prompt 亦由「明確講到」放寬到「**順口講都要抽**」，一句講幾樣就出幾個事件 | `tests/test_detected_events.py` 5 個；浏览器：mock payload 出 2 個 chip → 撳 ✅ 記低 → POST 帶 `message_id: 6` → reload 後 chips 唔再出 |
| 用 app 嘅指南 + AI 要教「每日點記錄」 | ① 新 prompt 常數 `RECORDING_GUIDE`（20 秒片、鏡頭要動、影相、打幾隻字、**聲唔會記錄**）注入 first check-in 兩個分支；② 純文字打卡（非首次）再加**一句**輕提（deterministic：`vision_reason == "no_photo"`）；③ app 內指南新增「點樣記錄最準確」一節（標明係 app 建議，唔係文獻） | `tests/test_prompt_recording_guide.py` 7 個；`GET /api/guide` sections 加 `logging`；`?scene=guide` 直接 deep-link 都 render 到 |

**順手修好**：`useSceneRoute` 之前只認 tab 名，所以 `?scene=guide` reload 會靜靜跌返第一頁 → 改用 `defs.SHELL_SCENES`（所有 scene）。實測：Settings → 指南 → reload 仍然停喺指南。

### 九之三、同日追加（第三批用戶指令）

| 要求 | 做咗咩 | 證據 |
|---|---|---|
| 上載影片時唔好「停喺一格格縮圖」、要見到條片同上載進度；**唔好俾用戶知抽格／壓縮** | composer 改成「🎬 皮膚影片 ＋ 本地預覽 ＋ 真進度條」（`fetch` 冇 upload progress → 改用 XHR）；刪走「抽咗 6 張相／已壓縮 62MB→5MB／格太似」全部文案；送出後對話只出中性 chip。後端加 `video:{duration,frames}` → `state["clip"]` → 寫入 user payload，reload 都唔會出抽格相；prompt 明文禁止講「幾張相／格數／抽格」，`frames<2` 改為一句「鏡頭慢慢掃過成塊面」 | `tests/test_clip_prompt.py`（7 個）；瀏覽器：上載中 `.clip-chip.uploading` ＋ `.clip-bar`、`frameThumbs = 0`、`mentionsFrames = false`、送出 POST 帶 `video:{duration:12.4,frames:6}`、對話出 `.clip-bubble` |
| 底部 icon 下面嘅文字仲係冇對齊 | **量到真原因**：唔係盒模型（五個 item 完全一樣），係 **icon 自己嘅 ink** —— emoji 字形來源唔同；換咗自己手畫 SVG 之後仍然係 17／17／16.5／**14**／**12** CSS px、中心差 1.25px。改用 **vendored Lucide** path（ISC）＋ 0.4 unit 校正 → 五個 icon ink 中心一致 | `w1_tabbar_ink.py`：icon ink `cy` 43.0／43.5×4、`cx` 全部 43.5、label ink 完全一致 |
| 「睇吓有咩 skill／工具可以裝，方便執手機版 UI」 | 交咗 **`docs/ui-plan.md`**：量度式審計（tap target <44 共 8 類、<12px 文字 12 個／scene、對比度最低 **1.0:1**、911 個 raw px、0 `:focus-visible`、0 `prefers-reduced-motion`）＋ 四階段計劃 ＋ skill／工具清單 ＋ 驗收門檻 | 今次**冇**改 UI（等用戶逐項批） |

**未做（誠實列出）**：條片／語音**冇做轉文字**（DeepSeek 冇 audio，HK 直連 OpenAI Whisper 係 403，local whisper 要新依賴）→ 所以指南寫明「講出嚟冇用，要打字（可以用鍵盤語音輸入）」。呢件事已經開咗 issue [#26](https://github.com/shulaplai/male_skincare_agent/issues/26)（`ready-for-human`）；用戶 2026-10-05 問過，答案係**「暫時唔做」**，原因同四個 STT 方案嘅代價記錄喺 `.out-of-scope/voice-audio-transcription.md`（留存歷史決定用；一旦用戶要返就刪嗰個檔、開新 issue）。

---

## 十、第三輪（用戶六項 UI／數據要求）—— 2026-10-20

用戶原話（大意）：「①底部 nav 嘅字同 icon 冇對齊 ②UI 剩低嘅 emoji 換成手機 UI 嘅 icon
③首頁寫『今日』但其實冇今日 data，有就唔好寫；今日 data 區要短、唔要相 ④composer：冇輸入時
收埋 send 掣、個 ↑ 改做 →、加咗片之後排版亂 ⑤條片明明冇睇過（舊 bug）但顯示『已睇片』
⑥教練回覆要逐字打出嚟」。

六項全部做完，每一項都有量度數字（唔係「應該得」）。

### 10.1 每項做咗咩＋點證明

| # | 問題（實測根因） | 改動 | 證據 |
|---|---|---|---|
| 1 | 唔係左右偏：五個 tab 嘅 `btnCx == iconCx == labelCx`（差 **0.00px**）。真因係 **icon 筆墨高度唔一致** —— 22px 盒內 Lucide 純幾何高度 16.50（message-square／chart-column）／17.42（house）／18.33（clipboard-list／settings）→ icon 底到 label 頂空隙差 1.8px | `MobileShell` 加 `ti-<scene>` class；`index.css` `transform: scale(var(--ink-scale,1))` 逐個 scale（0.927／0.976／1.03） | Playwright 390×844 `?layout=mobile`：修前 inkH 16.5–18.33、gap 差 1.8px；修後**五個 inkH 16.99–17.00、inkCy 808.17、gap 5.5px** |
| 2 | `src/` 唯一仍然 render 嘅 emoji 係 `Conversation.icon`（DB 存 '🧔'／'🧴'）→ `Chat.tsx`／`ShellTop.tsx`／`Sidebar.tsx` 三處 | `Icon.tsx` 加 `user-round`（Lucide `<circle cx=12 cy=8 r=5>` ＋ `M20 21a8 8 0 0 0-16 0`）；三處改 `<Icon name="user-round">`；`ShellTop` 個 `icon` prop 整個刪走（兩個 caller 一齊改） | `grep -n "🧔\|🧴" src/` 0 命中；DB 欄位留住（唔使 migration，只係唔再 render） |
| 3 | `MobileHome.tsx` `latest = entries[0]`（`/summary` 係 `date desc`）→ 冇今日 data 時仍然寫「今日膚況／今日指標／今日記低咗 N/6」，但 kicker 又寫 `10-01 週四`（自相矛盾） | 加 `todayYmd()`＋`isToday`；非今日時標題改「最近一次記錄／最近一次指標」、副題「上次記錄係 10-01 週四。撳下面打卡記低今日。」、chip row 下面加「呢啲係 10-01 週四 嘅數字。」；6 行 `LevelDots` 改成 `.entry-metrics` chip row；**刪走「最近幾日」卡嘅相 grid** | fixture（今日 2026-10-20、最新 entry 2026-10-01）實測：hero 讀「最近一次記錄」＋「上次記錄係 10-01 週四」、卡標題「最近一次指標」、`imgs=0`、`overflowX=0`、home 高 1290→1250 |
| 4 | `.send` 永遠 render；↑ icon；`.compose` 係**單一 flex row**，clip chip（54px 縮圖＋兩行 meta）同 textarea 係兄弟，390px 之下 textarea 被壓到 ~120px | 分兩層：`.compose-attach`（clip chip／相／錯誤，可 wrap）＋`.compose-row`（`.tools`＋textarea＋send）；`canSend = draft.trim() !== '' \|\| attached.length > 0 \|\| clip !== null`，send 掣 `{(canSend \|\| sending) && …}`；`Icon name="arrow-right"`（新加）；textarea `padding: 12px → 10px`（實際高度 48→44 ＝ 掣高） | 390×844 實測：空白時 `sendExists=false`、`.compose-attach` 0×0；打字後 send 44×44 y=733 cy=755、textarea 310×44 cy=755（修前 camera cy=755 vs textarea cy=753，差 2px）；加片後 attach 366×54 y=669、input row 仍然 y=733 textarea 44×254（唔再壓扁） |
| 5 | **最嚴重**：`Chat.tsx` 只送 `video:{duration,frames}`、`photo_paths=[]` → 後端 `has_photo=False` → vision 冇跑 → prompt 只有 placeholder「（已上傳皮膚影片）」→ model 當咗係證據、自己作六個 attribute、`observes_skin=True`、寫入當日 Entry | 見 §10.2（三處一起改才夠） | 真 DB 重跑：修前六個 attribute acne1/oiliness2/redness1/dryness1/pores2/texture1（全部作出嚟、coach `vision_used=False` 但寫「睇你條片」）→ 重跑後 **acne1/oiliness1/redness0/dryness0/pores1/texture1**、`vision_used=True`、回覆照實講 |
| 6 | 回覆一次過出現（無打字效果），而 scroll 模型係「`messages.length` 變才 pin 底部」→ 打字期間唔會 pin | `Bubble` 逐字顯示（`step = ceil(len/72)`、18ms、首次延遲 60ms ≈ 1.3s；`prefers-reduced-motion` 即出全句）；`onGrow={pinToBottom}` 令每 tick 都重新 pin；`Message.fresh` 只喺**成功**回覆設 true，切 scene 唔會重播（`TYPED` Set 記已打過 id） | `tests/ui/consult-stream.spec.ts` 新 test：`reducedMotion: 'no-preference'` 之下先見到部分文字（長度 < 全句）→ 最後 `toHaveText(FULL)`、貼住底部 |

### 10.2 第 5 項：點解「有片＝已睇過」會發生（同三處修法）

**根因鏈**（每一步都實測過）：
1. `Chat.tsx` `submit()` 只將 `video: {duration, frames}` 放入 request；`photo_paths` 保持 `[]`。
2. `graph.analyze` 見 `has_photo=False` → 走 text-only，`build_analyze_prompt(user_text, False, …)` 只出「（無相，純文字）」；`user_text` 係 placeholder「（已上傳皮膚影片）」。
3. 模型讀到「已上傳皮膚影片」就當自己睇過，回覆寫「睇你條片…泛紅由 0 回升到 1 分」，並自行填六個 attribute、`observes_skin=True`。
4. `persist` 見 `observes_skin=True` → 寫入當日 Entry（真 DB：`entries` 2026-10-20、note `（已上傳皮膚影片）`）。

**修法（三處，缺一都唔夠）**：
1. **後端 resolve**：`ClipInfo.video_id`；`service.resolve_clip_frames(photo_paths, clip)` 由 `Video.frames` 砌返 `photo_paths`（client 自己帶相就唔動）；攞唔到格就標 `{frames: 0, unavailable: True}`（UI 仍然出一條片 chip）。`consult_stream` route 喺 `open_consult` **之前**行，`run_consult` 第一行亦行（所以 `retry` 都修好）。
2. **prompt 老實**：`build_analyze_prompt` 加 `elif clip:` 分支 → 「你**冇**睇過，唔好講『睇你條片』或者任何具體讀數，叫佢再拍一次」。次序係 `has_photo and photo_viewed and clip` → `has_photo and photo_viewed` → `has_photo and photo_unreadable` → **`elif clip`** → `elif has_photo` → 純文字。
3. **persist 唔好 leak**：`clip_turn` 之下 `attach_ids=[]`、`note_text=""`（格係 backstage，唔係用戶影嘅相；格嘅檔案由 `Video.frames`＋message payload 保住）。coach payload 加 `vision_clip: bool`，前端 `visionClaim(used, hasClip)` 講「已睇片分析（雲端）」／「文字分析（未睇片）」。

**舊數據**：`backend/scripts/repair_clip_entry.py`（dry-run 預設）用真格重跑一次真 vision，覆寫當日數字並清走嗰對假訊息。真 DB 執行前備份 `/tmp/skincoach.before-repair.db`。
⚠️ 呢個 script 只處理「note 含 placeholder ＋ 同日有可用片」嘅 row；**其他環境／其他日**如果都有同類假數據，要自己行一次（dry-run 會列出所有命中）。

### 10.3 兩個順手發現（同類 bug 嘅形狀又出現）

1. `backend/app/main.py` `/api/videos` 個 docstring 一直寫「client 會將 `frames` ids 當 `photo_paths` 送去 consult」—— **從來冇發生過**。假文件令個 bug 睇落「已設計好」。已改寫（`docs/backend-flow.md` §7 亦記低）。
2. 修好 script 之後即刻見到第二個 leak：抽格變咗當日 6 張 `Photo`（「記錄」顯示「今日 6 張相」）。同一個概念（「今日有咩相」）有兩個來源（`entry.photos` vs 用戶真係上載嘅相）→ 同 §6.3 一樣嘅形狀。

### 10.4 未做／要留意

- **Snapshot 全部重生過**（`npm run ui:update` → 62 passed；2026-10-20 第二輪之後再重生一次，**63 passed**）。因為改動係視覺嘅（nav icon scale、chips、composer 兩層、首頁文案），**diff 要人手望一次**（我只驗到「gate 綠 ＋ DOM 數字對」，冇逐張睇圖）。
- **`?layout=mobile` 以外嘅三套 shell 冇逐個量**：改動集中喺 `MobileShell`／`MobileHome`／`Chat.tsx`（composer 同 bubble 係四套共用），`ui:check` 63 個 test（4 layout × 6 scene ＋ 暗色 ＋ 橫向 ＋ 平板 ＋ 760/761）全綠。
- **打字效果只用 Playwright 驗**（假 API chunk）。真 LLM 之下 SSE 係逐段到，`fresh` 只喺最終訊息設 → 仍然係「成段一次過打」，唔係跟 SSE token 打。想要真 streaming 打字要改 `App.tsx` 收 SSE delta（未做，亦唔喺用戶要求之內）。

## 十一、第五輪（回覆三段式／收埋內部狀態／tab bar 冇文字）—— 2026-10-20

用戶原話（三個要求一齊落）：底部五個 icon 同文字「文字一係索性擺喺 icon 嘅右邊，唔好擺下邊，下邊嗰個位對唔準呀」；
「回應非常唔穩定，同埋有啲抖震」→ 要拆成「1 標題 2 正文 3 項目分析」；「一體化分析（雲端或者佢用咗啲咩模型嗰啲），全部隱藏咗佢」。

### 11.1 做咗咩

| 要求 | 改動 | 證據 |
|---|---|---|
| 三段式 | `Advice.title`（新欄，`ADVISE_SYSTEM` 限 12 字、唔可以講藥名）；`guardrails.advice_text()` 改成 `title+reply+items` 一次掃描、`ESCALATION_TITLE` 連標題一齊換；`persist` 寫 `payload["title"]`；前端 `Bubble` 逐段出（標題 ~0.2 s → 正文 ~1.3 s → 分析卡），`TYPED.add()` 最後才做 | `pytest` 348（+2 guardrail test、+1 payload assert）；真 DeepSeek（temp DB）出 `title='下巴爆瘡：先減刺激控油'`（11 字） |
| 收埋徽章 | 刪 `visionClaim()`／`provenanceLabel()`、`.vision-badge` CSS、`Chat.tsx` 兩個 badge block；`vision_used`／`vision_clip`／`provenance` 仍然寫入 payload、`/api/consult` response、`data/runs.jsonl` | `tests/ui/provenance.spec.ts` 重寫成「唔准 leak」（`.vision-badge` 0 個＋`雲端`／`FakeLLM`／model 名全部唔可以出現） |
| tab bar | 最後決定 **icon-only**（`aria-label` 保留無障礙名）；`.tl` 連 CSS 一齊刪 | 390／320px 量到五個 `inkCx == btnCx`、button textContent 0 字、`overflowX 0` |

### 11.2 為咩唔係「文字擺右邊」收貨

真係試過（橫排 `gap: 2px`），量出嚟「墨跡右緣 → 字左緣」係 **4.7／4.7／9.3／10.3／4.7px** —— 因為每個 Lucide path 自己右邊留白唔同（`settings`／`clipboard-list` 留得少，`house`／`message-square` 留得多）。要逐個調 padding 就變成另一個 `--ink-scale` 式校正表，字級一改就失效。用戶原本就講「一係非常近，一係索性冇」→ 揀後者。

### 11.3 未做／要留意

- **41 張 snapshot 係機械重生**（`npm run ui:update` → 63 passed），我冇逐張人眼睇 diff。
- **打字仍然唔係跟 SSE token**：SSE 係逐 node 到，最終文字仍然一次過落 `fresh` 訊息 → 「成段一次過打」。要真 token streaming 要改 `App.tsx` 收 delta（唔喺今次要求內）。
- **`title` 係 LLM 生成**：真 LLM 今次出 11 字合規，但 prompt 只係「≤12 字」嘅指示，冇 deterministic 截斷。如果將來見到超長標題，前端會照 render（`coach-title` 冇 clamp）—— 要嘛加 `.slice` 截斷，要嘛喺 guardrail 加長度檢查。

## 十二、DeepSeek 上游模型改咗（2026-10-21）

用戶報「upload 相／片好似成功咗，你 check 下係咪一定要用 vision-exp」。查 `GET /v1/models`（用真 key，冇 print key）：

| id | input modalities | 備註 |
|---|---|---|
| `deepseek-flash` | `["text","image"]` | V4.1-Flash、1M context、`effort` low/high/max（default high） |
| `deepseek-v4-pro` | `["text"]` | 純文字 |

`deepseek-v4-flash` 同 `deepseek-v4-flash-vision-exp` **已經唔喺 list 入面**（但仍然 resolve 成 alias）。實測三個 id **全部**接受圖片（`structured_vision` 都成功回覆），所以「vision 一定要另一個 model」呢個前提已經消失。

改動：`app/config.py` 兩個 default 都改 `deepseek-flash`（保留 `deepseek_text_model`／`deepseek_vision_model` 兩個設定，將來想 pin `deepseek-v4-pro` 做文字都得），`docker-compose.yml`／`backend/README.md`／`README.md`／`docs/architecture.md`／`blog-post`／`user-notes`／`adr/0009`／`learn/02-llm.md`／`AGENTS.md`／`frontend/tests/ui/fixtures.ts` 一齊改。

驗證：真端到端（temp DB + 合成圖）`vision_used=True`、`images_loaded=1`，而模型**照實講**「睇唔到真實皮膚紋理，只見到兩個色斑」——即係冇作嘢。`pytest` 348、`eval --fake` EXIT 0、`ui:check` EXIT 0（63 passed）。

⚠️ 仲未做：**真人真相／真片**嘅 smoke test（我只可以用合成圖證明 wiring）。

## 十三、「顧問」：人設＋主動問候（2026-10-21）

用戶要求（原話意思）：介面而家叫「教練」，想改成「顧問」，Settings 可以設定人設（性別／種族／自由文字，default 一位有多年經驗嘅皮膚科醫生），令佢講嘢人性化啲；回覆可以分 2–4 個 message；就算用戶冇開口，每日朝早／夜晚各問候一次。排咗喺 18:00 之後做。

四個決定（用戶逐個揀）：①回覆**一條 bubble**（標題＋正文＋分析卡，維持 2026-10-20 嘅三段式，唔拆多條）②人設存**後端 DB** ③問候 **09:00 ＋ 21:00、每日上限 2、23:00–08:00 靜音** ④UI **全部改叫「顧問」**。

### 13.1 做咗咩

| 部分 | 實作 | 證據 |
|---|---|---|
| 人設資料 | `User.persona_gender`／`persona_ethnicity`／`persona_prompt`／`greet_enabled` ＋ `db._COLUMN_MIGRATIONS` 補欄 | `tests/test_memory_guards.py::test_column_migrations_target_existing_model_columns`（更新 expected 清單） |
| 人設邏輯 | `backend/app/persona.py`：`Persona`／`normalise()`（trim ＋ 400 字硬上限）／`prompt_block()`（**每次都帶 `SAFETY_LINE`**）／`as_dict()` | `tests/test_persona.py` |
| prompt 注入 | `app/agent/state.py` 加 `persona: dict`；`service._load_persona()` 每次 consult 由 DB 讀一次；`build_advise_prompt` 第一段就係人設 | 同上 |
| API | `GET /api/persona`、`PATCH /api/persona`（含 `greet_enabled`） | round-trip test |
| 主動問候 | `app/greeting.py`（純：窗口／去重／prompt／長度）＋ `app/scheduler.py`（DB＋LLM）＋ `main` lifespan 每 60s 嘅 `_greeting_loop()` ＋ `POST /api/greet/run` 手動入口 | 窗口／去重／opt-out／fake 四個 test |
| UI | `SettingsView` 新增「顧問」卡（性別 segmented、背景、人設 textarea、主動問候 switch、儲存）；`api.getPersona/patchPersona`；`tests/ui/fixtures.ts` 加 `PERSONA` | `ui:check` 63 passed；390／760px 量過冇 overflow、所有 tap target ≥44 |

### 13.2 真 LLM 實測（1 次 call）

`POST /api/greet/run {"slot":"evening","force":true}` →

> 「夜晚啦，仲未瞓呀？你之前話下半面好易出暗瘡，呢幾日點呀，有冇試新嘢搽？」

**佢引用咗真 DB 入面最後一條 entry 嘅原話**（「下半面好易出暗瘡」），冇作數、冇講分數。呢句已經寫入真 conversation（`payload.proactive="evening"`），所以今晚唔會再發第二次。

### 13.3 刻意嘅限制（避免變成 spam）

- 背景 loop **只喺 server 行緊嗰陣**才會 tick；server 唔行就唔會發（唔用系統 cron，唔會偷偷用 API credit）。
- `FakeLLM` 模式**唔會**寫問候（罐頭文字寫入真對話就係假問候）。
- 同一 slot 每日一次（靠 `payload.proactive`，重啟都唔會重複）；窗口外（深夜／靜音）唔發。
- 長度硬上限 180 字（`greeting.compose`）＋ prompt 明講 1–2 句。
- **從來唔寫 `Entry`**：打招呼唔係皮膚觀察，所以唔會污染當日數據。

### 13.4 未做／要留意

- **Persona 唔會傳去 `analyze`**（只影響 `advise`）。刻意：分析結果要跨人設一致，否則換個顧問就會影響歷史比較。
- **問候時間固定喺 code**（09:00／21:00），Settings 未有得改時間；要改就加兩個欄位 + UI。
- **測試用 `greet_enabled` 關掉背景 loop**（`tests/conftest.py` autouse fixture）—— test 唔可以靠「fake 唔會寫」呢重閘。
- 41 張 snapshot 又重生過一次（`教練→顧問` 出現在 nav／meta／多處文案 ＋ 新增 Settings 卡），**diff 未逐張人眼睇**。
