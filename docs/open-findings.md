# 未完成嘅 findings（handover）

> 用途：一次審計（`docs/status-vs-claims.md` 全部 27 行逐行驗證）之後嘅**交收清單**。
> 分三類：**已經修好**、**要你決定先可以改**、**環境／人手先做得到**。
> 決策嗰啲唔喺呢份文件重複 —— 佢哋住喺 GitHub issues（見 `docs/agents/issue-tracker.md`，搵 `wayfinder:map` label）。
> 最後更新：第一次修復 pass（audit 之後）。

---

## 一、已經修好（有驗證）

全部改動都跑過 `pytest -q`（77 綠）+ `npm run typecheck` + `npm run build` + `eval.run_eval --fake`（exit 0）。

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

---

## 四、刻意**唔**改（同原因）

| 唔改嘅嘢 | 為何 |
|---|---|
| **Journal 顯示 product id**（`🧴 5680cffc…`） | 修法係 `/summary` 要 resolve id → name。技術上細，但會改 API response shape + 前端 types，屬「改形狀」多過「執 bug」—— 想你決定之後才動。 |
| **Docker 內 `FASTEMBED_CACHE_PATH` 未設**（model cache 落 containers temp，recreate 就重新 download） | 一行 compose 改動，但**呢部機冇 build 過 image**，我改完無法驗證，唔想寫未驗證嘅嘢入 compose。 |
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

## 六、點自己驗返

```bash
cd backend
./.venv/bin/python -m pytest -q                    # 77 passed
./.venv/bin/python -m eval.run_eval --fake         # exit 0
md5 -q data/skincoach.db                           # 應該係 40823465d6041edf11c05a44f07d88b9

# migration 會喺下次 backend 啟動時自動修好舊 schema；
# 想先睇效果（安全，唔掂真 DB）：
cp data/skincoach.db /tmp/check.db
SKINCOACH_DATABASE_URL=sqlite:////tmp/check.db SKINCOACH_DATA_DIR=/tmp/checkdata \
  ./.venv/bin/python -c "from app.db import init_db; init_db()"

cd ../frontend && npm run typecheck && npm run build
```

> **⚠️ 一個要留意嘅副作用**：`init_db()` 嘅 rebuild 會 `DROP TABLE` 再 rename。實測行數、index、內容都保留，但呢類操作永遠值得先備份：
> `cp backend/data/skincoach.db backend/data/skincoach.db.bak`
