# Backend 流程：一次對話由邊度去到邊度

> 呢份文件答一個問題：**一個請求入到嚟，究竟經過啲咩、寫咗啲咩落 DB？**
> 每個步驟都標 `file:line`，可以即刻核對。真 LLM 同 FakeLLM **行同一條路**，
> 唯一分別喺 `get_llm()` 回邊個 adapter —— 詳見 §4。

## 1. 三個入口

| 入口 | 位置 | 用途 |
|---|---|---|
| `POST /api/consult` | `app/main.py:374` | 產品路徑。UI 每次 send 都係呢個 |
| `POST /api/consult/stream` | `app/main.py:382` | 同一件事，但 SSE 逐個 node 報進度（UI 而家行呢個） |
| `scripts/trace_consult.py` | CLI | Debug。預設 temp DB + FakeLLM；`--real` 用真 LLM |
| `python -m eval.run_eval` | `eval/run_eval.py` | Eval。temp DB；`--fake` 用 FakeLLM |

三個入口最後都係 **`service.run_consult` 或者 `build_graph(...).invoke(...)`** ——
即係共用同一套 5 個 node。

## 1.1 `POST /api/consult/stream`：同一個 pipeline，兩個 transport

串流**唔係**第二套邏輯：`service.stream_consult()` 同 `run_consult()` 一樣行
`open_consult()`（404 ＋ consent 判斷）、`_build_consult_graph()`、`_consult_state()`，
最後一樣 `_finish_consult()`（`vision_used` ＋ `write_run_log`）。唯一分別係
`graph.invoke()` 變 `graph.stream(state, stream_mode=["updates", "values"])`：

- `updates` → 邊個 node 行完（`analyze`／`tools`／`advise`／`guardrail`／`persist`），
  連佢自己嗰句 `trace[].ms`；
- `values` → 最後嗰個 chunk 就係完整 state（唔使自己重現 `Annotated` list reducer）。

出街嘅 frames 係一個 JSON 一個 frame：

```
data: {"type":"node","node":"analyze","ms":2513}
data: {"type":"node","node":"tools","ms":41}
…
data: {"type":"result", … 同 POST /api/consult 一模一樣嘅 payload …}
data: {"type":"error","detail":"我今次分析唔到（…）"}   ← 失敗時代替 result
```

⚠️ **三條唔可以踩嘅規則**：

1. **404 一定要喺 route 度答**（`open_consult()` 喺 `StreamingResponse` 之前行）。
   一開始寫 frame，HTTP status 就已經送出咗，之後只可以用 in-band `error`。
2. **解析失敗唔可以 raise 503**（同 `run_consult` 唔同）：`OutputParserException`
   喺 generator 度 catch，出 `error` frame，內容同 503 body 共用同一個常數
   `service.CONSULT_PARSE_FAILED`，唔可以有兩句唔同嘅失敗訊息。
3. **`nginx.conf` 要 `proxy_buffering off`**：nginx 預設儲夠 buffer 先轉發，咁樣
   逐個 frame 送就等於冇串流（本機 Vite proxy 冇呢個問題，所以只會喺 Docker 撞到）。

前端 `api.consultStream()` 自己 parse frame；`res.body` 唔存在（舊瀏覽器／代理冇
stream）就 fallback 去 `consult()`。`App.tsx` 每個 node 換一句顯示文字，字串放喺
前端（後端只講「邊個 node」）。測試：`tests/test_consult_stream.py`（6 個，包括
「404 唔可以係 200 串流」同「串流路徑都要寫 run log」）、
`frontend/tests/ui/consult-stream.spec.ts`（2 個）。

## 2. HTTP 請求路徑（逐步）

```
POST /api/consult  {conversation_id, text, photo_paths}
  │
  ├─ app/main.py:335  consult()
  │     └─ 冇 validation、冇 loading，直接轉手
  │
  └─ app/agent/service.py:70  run_consult()
       ├─ :71-88  讀 privacy consent → 之後入 state：
       │             `cloud_analysis = conversation.cloud_analysis AND user.photo_cloud_consent`
       │           （全雲端政策之下第一個永遠 True；第二個係一次性同意）
       │           有相但唔夠條件 → log warning，最後行純文字
       │           搵唔到 conversation → HTTP 404
       ├─ :80-84  build_graph(llm=get_llm("text"), vision_llm=get_llm("vision"), …)
       ├─ :86-94  graph.invoke(state)
       ├─ :96     write_run_log(...) → data/runs.jsonl（每個 consult 一行）
       └─ return result（trace 喺裡面）
```

**注意**：`get_llm()` 喺**每次 consult 都叫一次**（`:81-82`），冇 cache。
真 adapter 嘅 `_client()` 亦係 lazy（`llm.py:103`），所以冇 key 就永遠唔會建 HTTP client。

## 3. Graph：5 個 node，一條直線

`app/agent/graph.py` — `StateGraph` 冇分支、冇循環、冇 conditional edge：

```
START → analyze → tools → advise → guardrail → persist → END
```

| node | 行 | 用 LLM？ | 讀 | 寫落 state |
|---|---|---|---|---|
| `persist` | `:481-517` | 冇 LLM | — | ChatMessage（user＋coach）；coach `payload` 帶 `detected_events`（reload 出返 chips）、`events_applied` 由 confirm route 補 |

| `analyze` | `:91-165` | ✅ **text 或 vision** | `user_text`、`photo_paths`、`cloud_analysis` | `analysis`（`SkinAnalysis`）、`vision_used`、`trace` |
| `tools` | `:167-261` | ❌ | `analysis.tool_calls`、`user_text` + DB | `tool_results`、`product_eval`、`recent_messages`、`first_checkin`、`trace` |
| `advise` | `:263-286` | ✅ text | `analysis`、`tool_results`、`product_eval`、`recent_messages`、`first_checkin` | `advice`（`Advice`）、`trace` |
| `guardrail` | `:288-324` | ❌ | `advice`、`user_text`、`product_eval` | `advice`（可能被改）、`escalate`、`trace` |
| `persist` | `:326-547` | ❌ | 全部 | **DB 寫入**、`trace` |

**LLM 只出現喺 `analyze` 同 `advise`**（doctrine #1）。其餘三個 node 係純 code。

`tools` 除咗跑 tool 之外，仲會做**商品評估**：`ingredients.looks_like_ingredient_list(user_text)`
命中（用戶貼咗 INCI 表）就經 `product_context.evaluate_for_conversation()` 計出
coverage／verdict／conflicts，放入 `state["product_eval"]`。**成份嘅事實係 code 算嘅，
LLM 只負責寫成句子**（見 §8）。

### 3.1 `analyze` 內部嘅 vision 決策（`graph.py:91-165`）

```
has_photo = bool(photo_paths)
consent   = bool(state["cloud_analysis"])   # = conv flag AND User.photo_cloud_consent（見 service.py）
vision    = has_photo and consent and not isinstance(vllm, FakeLLM)   # :95
vision_attempted = 同上面一樣（刻意喺 fallback 之前計）              # :104
```

- `vision` 為 True → `load_photo_b64` 讀相 → `vllm.structured_vision(...)`（`:114`）
- 讀唔到相（`images_loaded == 0`）→ `photo_unreadable = True`（`:128`）
- 失敗或唔行 vision → `_text_only_analysis(...)`（`:130`），`vision = False`
- `vision_reason ∈ {photo_unreadable, vision_error, used, consent_off, fake_llm, no_photo}`（`:132-143`）

⚠️ **`FakeLLM` 永遠唔會行 vision**（`isinstance(vllm, FakeLLM)`）→ 所以 `--fake` 完全冇覆蓋呢條路。

### 3.2 `analyze` 收到嘅 prompt（**由白紙開始**）

`prompts.build_analyze_prompt(user_text, has_photo, …)`（`:44`）只回：

```
用戶訊息：<user_text>
<一句關於相嘅 note>
```

**冇歷史 attributes、冇之前 Entry、冇舊 note。** 而 `ANALYZE_SYSTEM`（`prompts.py:21`）寫：

> 對每個 attribute 逐個評 0–3…**睇唔到或未提及就畀 0**

→ 呢兩句合埋就係 `docs/product-eval-plan.md` §2.5 嗰個 bug 嘅源頭。

### 3.3 `tools`：白名單，LLM 只可以「提名」

`tools.WHITELIST = {get_skin_profile, get_recent_entries, search_knowledge}`（`app/agent/tools.py:15`）。
`analyze` 將想要嘅 tool 名放入 `SkinAnalysis.tool_calls`（只係字串），
執行喺 `tools` node 由 code 做（`:176`）。唔喺白名單 → 忽略 + 記落 trace（`:180-182`）。

`first_checkin = session.query(Entry.id)...first() is None`（`:220-224`）
→ **語意係「呢個 conversation 從來冇任何 Entry」**，唔係「今日未打卡」。

### 3.4 `persist`：唯一會寫 DB 嘅 node

| 寫咩 | 行 | 條件 |
|---|---|---|
| `Entry`（upsert by `conversation_id + date`） | `:354-374` | **`observes_skin or vision_used`**（`:349`）。唔過閘就**完全跳過**，包括 TimelineEvent |
| `Photo` | `:376-398` | 相真存在（`photo_exists`）＋未加過＋有 Entry 可以掛 |
| `TimelineEvent`（`source="agent"`） | `:400-424` | 同上 ＋ **一日只准一個**（`if existing_agent_event is None`）＋變化夠 notable |
| `Insight`（`kind="derived"`） | `:424-478` | 每個 attribute 一個；tag+direction reconcile；**同樣要過 `observes_skin` 閘** |
| `ChatMessage` × 2（user + coach） | `:486-503` | **無條件**（display truth） |

`entry.note` / `entry.metrics` / `entry.attributes` 都係 **`=`（覆蓋）** —— 所以「寫唔寫」
一定要先決定好，`observes_skin` 閘就係嗰個決定（§6 講嘅 T1–T5 全部源自佢）。

⚠️ **呢張表以前寫住 `Entry` 係「無條件」**，即係修好之前嘅行為。如果你喺舊版本嘅文檔
見到「無條件」，嗰個已經唔係現實。

## 4. 真 LLM 同 FakeLLM 嘅分別（**唯一分岔點**）

分岔完全喺 `app/agent/llm.py:163 get_llm()`：

```
provider + 對應 key  →  該 provider 嘅 adapter
否則 deepseek key      →  OpenAICompatLLM(deepseek)
否則 anthropic key     →  AnthropicLLM
否則 openai key        →  OpenAICompatLLM(openai)
全部都冇               →  FakeLLM()          ← 只有呢一種情況至會 fake
```

`backend/.env` 有真 DeepSeek key → **產品路徑（`/api/consult`）會用真 LLM**。

### 4.1 FakeLLM 係咩嚟 —— 唔係「dummy 冇用」

`FakeLLM`（`llm.py:26-62`）係**寫死輸出**：`SkinAnalysis` 例牌回 acne 2／oiliness 2／redness 1
＋ `tool_calls=["get_skin_profile","search_knowledge"]`；`Advice` 回一段固定示範文。

| FakeLLM 存在嘅理由 | 詳細 |
|---|---|
| **冇 key 都行得**（offline demo） | `get_llm` 最後一個 fallback |
| **test 唔可以打真 API** | `tests/conftest.py` 有 autouse guard patch `_client()`（撞過：一個 test 花咗 6 次真 call） |
| **eval `--fake` CI 穩定** | 同一輸入永遠同一輸出，`exit code` 才有意義 |

⚠️ **FakeLLM 唔可以當「真 offline」**（`AGENTS.md` 已有）：冇 key 時
`service` 仍然會 instantiate `FastembedEmbedder`，首次會 download model。

⚠️ **FakeLLM 係「假綠燈」來源**：佢硬編碼 `tool_calls`，所以
「真 LLM 唔識叫 tool」（#26）、「真 LLM tool 名撞 parse」（見 §6）**兩次都係
`--fake` 全綠之下發生**。

### 4.2 兩條路嘅實際差異

| | 真 LLM | FakeLLM |
|---|---|---|
| `analyze` 輸出 | 由 model 產生，每次都唔同 | 固定常數 |
| vision | 有 key + consent + 有相 → **會行** | **永遠唔會行**（`isinstance` 檢查） |
| `OutputParserException` | 真係會發生 | 唔會 |
| `advise` 正文 | 真廣東話推理 | 一段固定示範文 |
| `guardrail` | 可能攔到嘢 | 幾乎永遠攔唔到（示範文乾淨） |
| 成本 | 每次 consult 2 個 call | 零 |

**即係：`--fake` 綠燈完全唔代表產品路徑冇壞。** 呢個係成個 audit 嘅核心。

## 5. 一覽：一次 consult 嘅完整寫入集

```
1 個 Entry（upsert，attributes 被覆蓋）
0–N 個 Photo
0–1 個 TimelineEvent（source=agent，一日一個）
6 個 Insight（每個 attribute 一個，會 reconcile／version bump）
2 個 ChatMessage
+ 1 行 data/runs.jsonl
```

## 6. ✅ 曾經會打亂時間線嘅位（全部同一根源）—— **已修**

根源：**pipeline 冇「呢條訊息係唔係打卡？」呢個概念** —— 每條訊息都當係打卡。

**修法**：`SkinAnalysis.observes_skin`（由 LLM 判斷「呢條訊息有冇描述而家嘅皮膚」）
＋ `persist` 用 `observes_skin or vision_used` 做閘。唔過閘就**只寫 `ChatMessage`**，
唔寫 `Entry`／timeline／insight。改動喺 `graph.persist`、`prompts.ANALYZE_SYSTEM`。

**點解用 LLM 判而唔用關鍵詞**：「呢支會唔會令我爆瘡？」（問題）同「下巴爆咗兩粒」
（觀察）都含「瘡」—— 判斷呢句係唔係在描述皮膚狀態係語言工作，屬於模糊層。

**真 LLM 實測（`trace_consult.py --real`）**：

```
產品問題「呢支精華有 2% 水楊酸…值唔值得買？」
  observes_skin: false  entry_written: false  timeline_lines: 0  insights_created: 0
  → 只寫 2 條 ChatMessage；回覆正面比較成份、答「值唔值得買」

皮膚描述「今晚塊面爆緊瘡，T 字位好油」
  observes_skin: true   entry_written: true   attributes: 6      insights_created: 6
```

⚠️ **仲有一個副作用要記住**：`observes_skin` **唔可以**漏入 `advise` 嘅 prompt。
第一次實測時 model 將欄位名照讀返俾用戶（「分析顯示 observes_skin=false」），
而且將「唔係打卡」誤讀成「睇唔到皮膚」→ 叫用戶補相，**完全冇答產品問題**。
所以 `build_advise_prompt` 會 strip 咗個 flag，改用廣東話描述情況，
而且 onboarding 引導塊**只喺真打卡時**才出（`first_checkin` 嘅語意係「從來冇 Entry」，
一個只有問題嘅首個 turn 都會滿足佢）。

| 代號 | 傷害 | 修好之後 | regression test |
|---|---|---|---|
| **T1** | 當日 `Entry.attributes` 被覆蓋 | ✅ 唔會再寫，原有 entry 完全唔動 | `test_today_entry_is_untouched_by_a_later_question` |
| **T2** | **時間線永久錯**（假 event 霸咗「一日一個」） | ✅ 假 event 根本唔會產生 | 同上（斷言 timeline 不變） |
| **T3** | `Entry.note` 被覆蓋 | ✅ 唔會 | 同上（斷言 note 不變） |
| **T4** | 假 memory「暗瘡：正常」 | ✅ `insights_created: 0` | 同上 + `test_a_question_writes_no_entry_no_timeline_and_no_memory` |
| **T5** | `first_checkin` 被「問問題」消耗 | ✅ 問題唔會消耗 | `test_a_question_does_not_consume_first_checkin` |

**實測（stub 忠實跟 prompt 指示）：**

```
① 全新用戶只問「呢支精華有 2% 水楊酸，得唔得？」
   Entry  day1  acne=0 oiliness=0     note='呢支精華有 2% 水楊酸，得唔得？'
   Insight      v1 normal「暗瘡：正常」
   first_checkin = True

② 之後真打卡「今晚塊面爆緊瘡，T 字位好油」
   Entry  day1  acne=3 oiliness=3     ← 修返對
   Insight      v1 normal「暗瘡：正常」 + v2 problem「暗瘡：嚴重」
   first_checkin = False               ← onboarding 分支冇咗

   但時間線仍然係： 暗瘡 改善↓（嚴重 → 正常，同上次比）   ← 假嘅，而且改唔返
```

**其他寫入路徑冇呢個問題**（已核）：`self_report.apply_events` 只寫
`entry.diet` / `entry.products`（唔掂 `attributes`）；改筆記 route 只改 `note`；
`/facts`、`preferences` 只寫 Insight。

## 6.1 ⚠️ 另一個同源問題：產品問題會令 consult **crash**（已修）

同 §6 一樣係「prompt 措辭同結構化輸出冇分清楚」，但唔關時間線事，係路徑本身斷。

**徵狀**（真 LLM 實測）：

```
structured output parse failed (Unknown tool type: 'search_knowledge'.
                                 Available tools: SkinAnalysis) — retrying once
KeyError: 'search_knowledge'   → 整個 consult 掛掉
```

**根源**：`TOOL_GUIDE` 本來寫「你**可以喺 `tool_calls` 要求**以下工具」——
model 讀成「呢啲係你可以 call 嘅 function」，於是 DeepSeek 真嘅 emit 一個叫
`search_knowledge` 嘅 function call。但結構化輸出只登記咗 `SkinAnalysis` 一個
function → parser `KeyError`。

**為何特別打中產品問題**：問成份／產品嗰陣，model 最想用 `search_knowledge`。

**修法（已落，3 部分）**：
1. `prompts.TOOL_GUIDE` 改寫成明確講「你唔可以 call 任何 function，只可以喺
   `tool_calls` **欄位填字串**」；`schemas.SkinAnalysis.tool_calls` 嘅
   description 同樣加清楚。`tests/test_observability.py` 加斷言封住措辭。
2. `llm._invoke` 由「重試同一組 messages」改成 **帶糾正訊息嘅有界重試**
   （最多 3 次；retry 時 append `FORMAT_CORRECTION` 做第二個 system message）。
3. 仍然失敗 → `service.run_consult` 拋 **HTTP 503 + 可讀訊息**（唔再係裸 500，
   亦唔會造假分析；訊息只承諾真嘅嘢：「你嘅紀錄冇被改動」）。

**驗證**：
- 受控測試（runnable 層確定性觸發失敗 → 真 DeepSeek 收糾正）→ **成功**，
  attempt 1/3 失敗、attempt 2 回得正。
- reword 後同一條產品問題跑 **3/3 成功、0 次 parse 失敗**
  （改前：同一條問題 2 次入面 1 次爆）。

## 6.2 同一日再打卡：只覆寫今次真係有提及嘅 attribute（政策 B，issue #21）

§6 個閘只擋「完全唔觀察皮膚」嘅訊息。一條**部分觀察**嘅訊息（「今朝爆多咗兩粒」）
仍然會整條覆寫當日 `Entry`，因為 `ANALYZE_SYSTEM` 對未提及嘅 attribute 一律畀 0。
實測後果：acne 2→1、6 條 memory 用假 0 strengthen、`recommend.TRIGGER_FLOOR = 2`
令商品評估由 `good` 變 `caution`。

**決定**（用戶揀，純產品語意）：**B. 只覆寫今次真係有講嘅 attribute**。

```
analyze  →  每個 Attribute 多一個 `mentioned`
            （今次真係講到／睇到 → true；「未提及所以畀 0」→ false）
persist  →  entry.attributes = merge_attributes(舊, 今次)   ← mentioned=false 沿用舊讀數
            entry.metrics    = merge_metrics(舊, 今次)      ← 按 metric key 合併
            entry.note       = merge_note(舊, 今次)         ← 當日講過嘅全部保留（換行分隔）
memory   →  只為 mentioned=true 嘅 attribute 更新（唔會用假 0 strengthen）
trace    →  persist detail 多一個 `attributes_kept: ["oiliness", …]`
```

- `mentioned` **default True**：省略了呢個欄位（舊 payload／FakeLLM fixture）就照舊覆寫，
  唔會靜靜凍結當日讀數。
- 有相嘅 turn，vision 睇到嘅 attribute 都係 `true`，所以影相照樣覆寫。
- `mentioned` 同 `observes_skin` 一樣**唔會入 `advise` prompt**（model 會照讀返個欄位名）。
- 真實後果：相對講法（「爆多咗」）唔會再被當成絕對 severity 覆蓋其他讀數；
  但 model 仍然可能將「爆多咗」評成一個絕對值 —— 呢個要睇 prompt 質素，唔係 merge 嘅責任。

**regression test**：`tests/test_entry_merge.py`（`merge_*` 純函數 ＋ 行真 `graph.invoke`
嘅兩次同日打卡；其中一條斷言冇提及嘅 memory row 一個字都冇變）。

## 7. 影片上載（`POST /api/videos`）嘅位置

```
POST /api/videos?cid=<conv>  (multipart)
  ├─ conversation 存在？唔存在 → 404（未寫任何嘢落 disk）
  ├─ 串流寫落 data/videos/<32hex>.mp4     ← 本機儲（產品要求）＋解碼器要求
  │    每 1MB 讀一次，邊寫邊 check_size()  ← 超 100MB 即刻 413 + 刪走半截檔
  ├─ extract_frames(path)                  ← ≤20 秒、≤6 格、去重、平均分佈
  ├─ >40MB → compress_video()              ← 縮 1280px / CRF 26 / 丟音軌；失敗唔致命
  ├─ 每格 save_photo(uuid4().hex, jpeg) → data/photos/<32hex>.jpg
  └─ 寫 Video row（id, conversation_id, path, duration, frames[], created_at）
       return {video_id, path, duration, frames:[{id,path}], sampled, dropped,
               timestamps, original_bytes, stored_bytes, compressed, compress_error}
```

### 實測：抽幾多格（合成片、30fps）

| 片長 | 鏡頭動作 | 候選點 | 丟重複 | **相片數** | 解碼 |
|---|---|---|---|---|---|
| 3s | 靜止 | 24 | 23 | **1** | 115ms |
| 10s | 微動 | 24 | 21 | **3** | 133ms |
| 10s | 慢掃 | 24 | 18 | **6** | 133ms |
| 30s | 橫掃 | 24 | 18 | **6** | 216ms |
| 30s | 橫掃 | 24 | 18 | **6** | ~250ms |

（`MAX_SECONDS` 後來由 30 收緊到 **20 秒** —— 用戶決定。30 秒 → 5.2 秒一格；
20 秒 → 約 3.3 秒一格。）

**最少 1 張、最多 6 張。片長唔影響相片數。** 候選點永遠係
`min(nframes, max_frames × 4) = 24` 個、等距分佈，去重之後留最多 6。

⚠️ **產品含意**：覆蓋範圍取決於**鏡頭有冇移動**，唔係拍幾長 ——
一條 60 秒定鏡片只會出 1 張相（全被當重複），而一條 10 秒橫掃片出足 6 張。
UI 一定要提示「鏡頭慢慢掃過成塊面」，否則用戶拍長片但得 1 張。

### 大細：上限 **100MB**，>40MB 自動壓縮

⚠️ **呢一節曾經寫錯**（寫成「冇上限」）。實際行為係三層：

| 原始大細 | 行為 |
|---|---|
| ≤ 40MB（`COMPRESS_OVER_BYTES`） | 原檔直接留低 |
| 40–100MB | `compress_video()` 重新編碼（縮 1280px、CRF 26、**`-an` 丟音軌**），原檔刪走，data dir 只留一份 |
| > 100MB（`MAX_BYTES`） | **413**，訊息講明上限、換算（20 秒 ≈ 40 Mbps）、同建議（改 1080p／剪短） |

1. **串流寫落 disk** —— 唔可以用 `await file.read()`：20 秒 4K 可以 200MB+，
   一次過讀入 RAM 就 OOM。`check_size()` 係喺串流**途中**逐 1MB 驗，所以超標嘅
   上載會喺半路被截，唔會先寫滿成個檔落 disk。
2. 丟音軌係雙重理由：app 由頭到尾都唔分析聲音，留住就等於無故儲低用戶嘅錄音。
   呢個同 `photo.save_photo` 一致 —— 相都係壓縮後才儲，唔係儲原檔。
3. **壓縮失敗唔會令功能失敗** —— 保留原檔、log warning、response 有 `compress_error`。
4. Response 報 `original_bytes` / `stored_bytes` / `compressed`，令 UI 可以話俾用戶知。

⚠️ **冇實測真手機片嘅壓縮率**：我試造一條 20 秒 1080p 合成片，但內容太平淡只壓到 7MB，
未達門檻，所以驗唔到壓縮比率。壓縮**路徑**由
`test_oversized_clip_is_re_encoded_smaller_with_no_audio` 確定性驗證（強制門檻 + 純噪聲內容）。

### 出咗片之後嘅路徑：**完全冇新路徑**

前端將 `frames[].id` 當 `photo_paths` 送去 `/api/consult` —— cloud consent gate、
photo 去重、`entry.photos`、`observes_skin or vision_used` 閘全部照用，
agent 亦唔需要知嗰啲係片。

⚠️ **解碼器嘅硬性約束**：`imageio` 個 ffmpeg plugin **唔收 `BytesIO`**（spawn ffmpeg
subprocess 讀檔）。所以「本機儲片」唔止係產品要求，係解碼器要求 —— 順帶亦令
`imageio-ffmpeg` 個 wheel 內建 ffmpeg binary（唔使系統安裝）。

### 片同 local-first 承諾（2026-09 修）

`Video` row 係**必要**嘅，唔係 nice-to-have：冇 row 就冇任何嘢知條片存在，
delete 同 export 都無從入手。

| 承諾 | 實作 | 證據 |
|---|---|---|
| 片可以匯出 | `export_zip()` 用 `data_dir.rglob("*")`，`videos/` 一直在內 | `tests/test_export.py::test_export_includes_stored_clips` |
| 刪 conversation 刪得乾淨 | `delete_conversation` 喺 cascade **之前**收集 `Photo.path`、`Video.id`、`Video.frames[]`，commit 之後逐個 unlink，回 `files_removed` | `tests/test_video.py::test_deleting_a_conversation_removes_the_files_from_disk` |
| 壓縮過嘅片都刪得到 | `video_file()` / `delete_video()` 兩個 spelling 都搵（`<id>.mp4` 同 `<id>.c.mp4`） | `tests/test_video.py::test_oversized_clip_is_re_encoded_smaller_with_no_audio` |

兩條曾經真實存在嘅漏洞：

1. **`delete_conversation` 淨係刪 row，冇刪檔**（實測：上載一張相 → 刪 conversation
   → `.jpg` 仍然喺 disk）。route docstring 寫住 "permanently delete a conversation and
   all its records"，而 DB cascade 永遠唔會掂 filesystem。修法：**先**收集路徑，
   因為 cascade 一行之後就冇嘢可以查。
2. **`video_file()` 搵唔到壓縮過嘅片**（`compress_video` 寫 `<id>.c.mp4` 而唔係
   `<id>.mp4`）→ 條片既搵唔到亦刪唔到，`DELETE` 會靜靜報「冇嘢刪」。
   所以 `delete_conversation` 用 `delete_video(vid)`（認兩個 spelling）而唔係
   自己砌 `data_dir / v.path`。

另外：後端接好唔等於功能接好 —— **前端仍然未接**：
`Chat.tsx` 個 file input 係 `accept="image/*"`，未識分 video 去 `POST /api/videos`
再將 frames 當附件；`original_bytes` / `stored_bytes` / `compressed` 亦未有 UI 顯示。

## 8. 商品評估：兩條入口，同一條算式

用戶嘅要求係「AI 推薦咗成份之後，用戶自己搵咗產品返嚟，教練要講返兩者夾唔夾」，
而且**唔要一個獨立 UI** —— 喺 chat 度出一個對話就夠。

```
入口 A：POST /api/conversations/{cid}/products/evaluate     ← 程式化（前端未用）
入口 B：POST /api/consult，message 係成份表                  ← 用戶實際行嘅路
          └─ graph.tools: ingredients.looks_like_ingredient_list(user_text)?
                 命中 → product_context.evaluate_for_conversation()   ← 純 code
                        → state["product_eval"]
                        → prompts.build_advise_prompt 加入事實塊
                        → advise 只負責寫成 2–4 句廣東話
                        → guardrail 見 escalate 就覆寫 reply
                        → persist：observes_skin=False → 唔寫 Entry
```

**兩條入口都經 `app/agent/product_context.py`**（`profile_inputs()`）。分開砌就會對
「用邊個 profile 比對」有分歧 —— 同 `guardrails` 以前掃 `items`／`reply` 兩個位
係同一類 bug。`tests/test_product_eval_api.py::test_the_route_and_the_chat_path_agree`
逐個 field 比對兩條路。

### 8.1 點判斷「呢條訊息係成份表」

`ingredients.looks_like_ingredient_list()`，**純結構判斷、唔查字典**：

| 訊號 | 門檻 |
|---|---|
| 逗號／分號／頓號／換行分隔嘅 token | ≥ 5 個 |
| 每個 token 係拉丁字名（可含數字、括號、`-`、`/`、`.`） | 剝走 `%` 之後 ≤ 60 字 |
| 拉丁字元總數 | ≥ 40 |
| 有 `成份`／`成分`／`INCI`／`Ingredients` marker | token 門檻降到 3 |

⚠️ **唔可以用「認得幾多個成份」做判斷**：真 INCI 表有 20–40 項而 seed 字典得 31 個，
所以真產品一定有一大堆我哋唔認得。用字典判斷 = 漏掉所有真產品。
**寧願漏（照平常答），唔好誤中（會用用戶冇貼過嘅成份嚟比對）。**
實測 12 句廣東話口語（`我用 CeraVe 同 The Ordinary`、`今日食咗雞蛋, 牛奶, 麥片`、
`早：CeraVe, 晚：Adapalene`…）**0 false positive**；6 張真成份表全部命中。

### 8.2 呢條路學到嘅三件事（全部都係實測撞出嚟）

1. **`成份：Aqua, …` 個標籤會黐落第一個成份**。`parse_ingredients` 之前唔剝標籤，
   所以 `成份：Aqua` 變成一個唔認得嘅成份，`Aqua`（水）永遠對唔上字典。
   真 LLM 於是回覆：「我認唔到第一個字『Aqua』…其實係水嚟嘅」。
   修法：`ingredients.strip_list_marker()` 喺 `parse_ingredients` **入面**做，
   兩條入口一齊修好；`Water (Aqua)` / `Aqua (Water)` 亦加做 `aqua` 嘅 alias。
2. **處方成份嗰陣 `recognised` 都要清**。本來只清 `matched`／`missing`，
   但 `recognised` 會 render 成「產品嘅其他認得嘅功效成份」—— 喺 `avoid` 隔籬
   列一排保濕劑一樣係「大致冇事，得一粒唔得」嘅讀法。實測 tretinoin 嗰條 case
   出 `('甘油','泛醇','尿囊素')`。`unknown` **故意保留**（老實講「我認唔到」）。
3. **模型會講「我幫你記錄低呢支產品」，但實際上冇**。`persist` 只寫 `ChatMessage`。
   所以 prompt 明確禁止呢句（真 LLM 再跑已經改口成「冇有為呢次寫入任何紀錄」）。

### 8.3 真 LLM 實測（`deepseek`, 2026-09）

用戶先做一次真打卡（`observes_skin: true`, 6 個 attribute, 寫 Entry），
再貼 `成份：Aqua, Glycerin, Niacinamide, Salicylic Acid, Panthenol,
Sodium Hyaluronate, Allantoin, Tocopherol, Madecassoside`：

```
tools.product_eval  = {verdict: "good", recognised: 7, unknown: 0,
                       matched: ["菸鹼醯胺", "水楊酸"], missing: [], conflicts: 0}
persist             = {observes_skin: false, entry_written: false, entry_reused: true,
                       attributes: 0, timeline_lines: 0, insights_created: 0}
```

回覆（節錄）：「呢支成份表同你『偏油＋易生瘡』嘅底子幾配合：菸鹼醯胺同水楊酸兩樣
都係你皮膚需要嘅成份…今次你只係貼成份，冇提到皮膚狀況，所以我唔會評價你而家嘅皮膚，
亦冇為呢次寫入任何紀錄。」

—— matchup 完全跟程式算出嚟嘅 `matched`，而且**當日真打卡嘅 Entry 一個字都冇改**
（`entry_reused: true`）。呢個就係 §6 嗰個閘喺新功能上仍然生效嘅證據。

## 9. 相關文件

- `docs/product-eval-plan.md` §2.5 —— T1–T5 嘅修法建議
- `docs/architecture.md` —— 設計約束（tool whitelist、privacy consent）
- `AGENTS.md` 陷阱一節 —— 全部撞過嘅嘢
