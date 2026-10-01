# 跟住 lab03 睇 trace（5 分鐘導讀）

> `lab03_agent_loop.py` 係成個課程最重要嘅一個檔，但佢一次過印 45 行。
> 呢份導讀幫你**逐格對照**：你應該見到咩、點解係咁、邊度最易睇漏。
>
> 呢份文件唔係摘要 —— 佢假設你已經開住個 terminal 跑緊。

## 開跑之前（30 秒）

```bash
# Terminal A —— 跑 lab
cd <repo root>
./backend/.venv/bin/python learn/labs/lab03_agent_loop.py

# Terminal B —— 開住實作，隨時對照
cd backend && $EDITOR app/agent/graph.py     # 睇 547–557 行（add_node / add_edge）
```

一句提醒：**你自己跑出嚟嘅輸出，唔會同下面 100% 一樣**。`ms` 一定唔同（你部機嘅速度），
`conversation_id` 每次新。但所有**布林值／數目字**（`vision_used`、`rows`、`entries`…）
喺 FakeLLM 之下係穩定嘅 —— 唔穩定就代表有嘢唔對路。

---

## 步驟 1：五站嘅骨架

```
g = StateGraph(AgentState)
g.add_node("analyze", analyze)     # 睇相／睇字 → 結構化分析
g.add_node("tools", tools)         # 跑 model 要求嘅工具（記憶／RAG）
g.add_node("advise", advise)       # 寫回覆（會帶埋工具結果）
g.add_node("guardrail", guardrail) # deterministic 安全閘
g.add_node("persist", persist)     # 寫 DB：Entry／記憶／timeline／chat
g.add_edge(START, "analyze") → tools → advise → guardrail → persist → END
```

**要留意**：呢六行係**文字**，但佢哋同 `graph.py:547–557` 嘅真 code 係一一對應。
呢個 lab 幫你省咗「由 558 行 code 搵出骨架」嘅工夫 —— 但你要親眼確認過一次，
否則之後所有討論都係信我。

💡 **點解係 5 個 node 而唔係 1 個？** 因為每一站都想單獨驗證。如果全部塞入一個
「consult()」function，你就冇得講「今次係檢索有問題定係寫文案有問題」。

---

## 步驟 2：準備

```
temp DB: /var/folders/.../T/learn_XXXXXX.db
conversation_id: 7d3a7b711691474ca414c7554e371c35
```

**要留意**：DB 路徑係 `/var/folders/...`（即 macOS 嘅臨時目錄），**唔係** `backend/data/`。
呢個就係「實驗永遠唔會掂你真 data」嘅實現方式 —— `_common.temp_db()` 用 `tempfile` 開一個新檔。

`conversation_id` 係 32 位 hex。留意個 ID 唔係「1」或者「abc」—— 呢個 repo 用 uuid4 hex。

---

## 步驟 3：逐站 delta（⭐ 呢段最重要）

`graph.stream()` 唔係回最終結果，而係**逐 node 吐 delta**。所以每印一行，
就代表「呢一站啱啱做完，佢更新咗 state 嘅呢幾個 key」。

### 3a　analyze

```
→ analyze    更新咗 state 嘅: ['analysis', 'vision_used']
    analyze trace: {'keys': [...10 個 key...], 'detail': {...}}
    analysis.observes_skin = True
    analysis.tool_calls    = ['get_skin_profile', 'search_knowledge']
    vision_used = False / vision_reason = no_photo
```

三個要點：

1. **`更新咗 state 嘅: ['analysis', 'vision_used']`** —— 呢句係全個 lab 最容易被略過嘅一句。
   `analyze` 只回兩個 key。`vision_reason`、`tool_calls` 等**唔喺 state 度**，
   佢哋只存在於 trace detail（所以下面第 4 步先睇到 `vision_reason: 'no_photo'`）。
   ⚠️ 呢個係真陷阱：「node 冇回嘅欄位，state 就冇」。我寫呢個 lab 嘅第一版就中咗 ——
   直接寫 `delta.get("vision_reason")` 永遠印 `None`，睇落好似 app 壞咗。
2. **`vision_used = False` 而 `vision_reason = 'no_photo'`** —— 兩個一齊睇先有意思。
   `False` 係結果，`'no_photo'` 係**原因**。`vision_reason` 嘅可能值有 6 個：
   `used` / `no_photo` / `consent_off` / `fake_llm` / `photo_unreadable` / `vision_error`（`graph.py:135–145`）。
   今次係 `no_photo` —— 你冇送相，所以根本冇試過 vision。**唔係**「睇唔到」。
   呢個分別好重要：`photo_unreadable` 要同用戶講「張相睇唔到」，`no_photo` 就當純文字。
3. **`observes_skin = True`** —— 你只講咗「下巴爆咗兩粒瘡，T 字位好油」，呢個係皮膚觀察，
   所以後面 `persist` 會寫 Entry。如果呢句係「呢支精華幾錢？」就會係 `False`（見 lab08）。

### 3b　tools

```
→ tools      更新咗 state 嘅: ['tool_results', 'product_eval', 'recent_messages', 'first_checkin']
    requested（model 要求）: ['get_skin_profile', 'search_knowledge']
    跑咗: [('get_skin_profile', 0), ('search_knowledge', 0)]
    first_checkin = True / recent_messages = 0
```

⭐ **呢度係 `tool_rows = 0` 嘅謎底**（第 4 步你會再見到 `tool_rows: 0`）。

`requested` 係 model **要求**嘅；`跑咗` 後面嘅 `0` 係**真係回咗幾多行**。
兩個工具都跑咗，但都回 0 行，因為：

- `get_skin_profile` → 呢個係全新 temp DB，之前冇任何 Entry／記憶 → 0 行
- `search_knowledge` → `temp_db()` 冇 ingest 過語料庫 → 0 行

**所以「tool 跑過」同「tool 有料到」係兩件事。** `eval/agent_eval.py:128` 個
`expect_tool` 檢查就係特登驗「有冇真嘅 rows」，唔係驗「有冇叫過」——
因為後者做到，前者先有意義。

`first_checkin = True` 係同一個原因嘅另一個講法：呢個 conversation 未有 Entry → 係第一次打卡。

### 3c　advise

```
→ advise     更新咗 state 嘅: ['advice']
    prompt_chars = 990 / tool_rows = 0
    reply（頭 60 字）: 睇咗你嘅情況：下巴有兩粒新暗瘡、T 字位偏油，兩頰就中性。…
    items: 2 條
```

**要留意 `prompt_chars = 990`**。呢個係「送俾 LLM 嘅 prompt 有幾長」——
即係你嘅成本同延遲。留意佢係**包含**工具結果嘅：今次 `tool_rows = 0`，
所以 990 字全部係 system prompt ＋ 記憶 ＋ 用戶輸入。如果檢索返 3 條 chunk，
呢個數會明顯升。

`reply` 同 `items` 係分開嘅：`reply` 係用戶睇到嘅正文（對話氣泡），
`items` 係行動清單。`guardrail` 兩樣都會掃（見 3d）。

### 3d　guardrail

```
→ guardrail  更新咗 state 嘅: ['advice', 'escalate']
    escalate = False / disclaimer_added = True
```

喺第 4 步嘅 trace 你會見到 detail 有四個 key：
`escalate / items_replaced / disclaimer_added / forced_by_product_eval`。

**呢四格就係「deterministic 安全閘」嘅全部輸出**：

| key | 今次 | 意思 |
|---|---|---|
| `escalate` | `False` | 冇紅旗 → 唔出轉介 banner |
| `disclaimer_added` | `True` | 加咗「如有疑問請諮詢醫生」類嘅免責句（喺 code 加，唔靠 prompt） |
| `items_replaced` | `0` | 幾多條 item 因為含醫療字眼被換走 |
| `forced_by_product_eval` | `False` | 有冇被「處方成份硬停」覆寫 `reply` |

`disclaimer_added = True` 值得停一秒：**免責句唔係 model 寫嘅**。
你改 prompt 改到出花都好，呢句一定出 —— 呢個就係「保證寫喺 code」嘅意思。

### 3e　persist

```
→ persist    更新咗 state 嘅: （冇）
    entry_written = True / insights_created = 3
    attributes 寫咗 = 3 / photos_added = 0
```

**`（冇）` 係唔係 bug？** 唔係 —— 而係一個好靚嘅教學點。
`persist` 係最後一站，佢冇嘢要交俾下一個 node，所以佢**只回 trace**，
唔回任何 state key。但佢明明寫咗 1 個 Entry、3 條 insight 入 DB。

👉 **「改咗 state」同「改咗世界」係兩件事。** state 係流程內部嘅資料袋；
DB 係外部世界。`persist` 嘅工作係改世界，唔係改袋。
debug 嘅時候，睇 state key 係睇「下一站收到咩」，唔係睇「有冇做嘢」。

---

## 步驟 4：成個 trace 一覽

```
node            ms  摘要
analyze        0.1  {...'vision_reason': 'no_photo', 'tool_calls': [...], 'attributes': 3...}
tools          6.9  {...'ran': [{'tool': 'get_skin_profile', 'rows': 0, 'error': None}, ...]}
advise         0.1  {...'prompt_chars': 990, 'tool_rows': 0, 'items': 2, 'reply_chars': 99...}
guardrail      0.1  {...'items_replaced': 0, 'disclaimer_added': True...}
persist       12.3  {...'entry_written': True, 'insights_created': 3, 'attributes': 3...}
```

⭐ **呢個表就係 `state["trace"]`，亦係 `POST /api/consult` 回俾前端嘅同一個陣列。**
換句話講：唔係「教學專用嘅 debug 輸出」—— production 每次答你都有呢份紀錄。

**睇 `ms` 一欄**（你嘅數字會唔同，但比例會似）：

- `analyze` / `advise` / `guardrail` 都係 **0.x ms** —— 因為用 FakeLLM，冇網絡請求
- `tools` **6.9 ms** —— 建 DB session ＋ 兩個 SQL query
- `persist` **12.3 ms** —— 寫 1 Entry ＋ 3 Insight ＋ 2 ChatMessage ＋ commit

👉 **真 LLM 之下呢個圖會完全反轉**：`analyze` 同 `advise` 會變 1–4 **秒**，其餘仍然係 10 ms 級。
呢個反差就係「LLM 貴喺邊」嘅最直接答案。想睇真數字：`lab09_real_llm.py --real`。

**每個 node 一定有一行**。冇嘅話就係有 node 靜靜死咗 —— 呢個 repo 明文禁止（見 `AGENTS.md` 陷阱）。

---

## 步驟 5：最終 state 有咩 key

```
advice, analysis, escalate, first_checkin, product_eval, recent_messages, tool_results, trace, vision_used
```

9 個 key。對照 `app/agent/state.py` 個 `AgentState` 型別 —— 佢宣告咗 **14 個**。
少咗嘅 5 個係 `conversation_id`／`user_text`／`photo_paths`／`cloud_analysis`／`clip`，
全部係「你入去之前已經有、今次冇人改過」嘅輸入欄位。

👉 原因：`stream()` 吐嘅 delta **只含 node `return` 嘅 key**，唔會重覆你輸入嘅嘢。
所以「最終 state」唔等於「累積咗所有欄位」—— 想睇全部就要用 `graph.invoke()`
（`lab10` 就係咁做），或者自己 `final.update(initial)`。

👉 **呢 9 個 key 就係「agent 嘅記憶體」。** 唔係對話歷史（對話歷史喺 DB），
而係「今次呢一個 turn 內部流傳嘅資料」。搞清呢個分別，你就明為咩
`invoke()` 要由零開始砌一個 dict 入去。

---

## 步驟 6：寫咗入 DB 咩

```
{"entries": 1, "insights": 3, "timeline": 0, "chat_messages": 2}
```

逐個對：

| 表 | 數 | 為咩 |
|---|---|---|
| `entries` | 1 | `observes_skin=True` → 過閘 → 寫當日讀數 |
| `insights` | 3 | 由 3 個 attributes（`attributes 寫咗 = 3`）推導出記憶 |
| `timeline` | 0 | 第一次打卡，冇「之前」可比 → 冇變化可報 |
| `chat_messages` | 2 | 1 條 user ＋ 1 條 coach（display truth） |

⚠️ **`timeline: 0` 唔係漏寫。** 變化偵測要同歷史比，第一次冇歷史。
想睇 timeline 有嘢，跑 `lab08` 或者喺 `eval/agent_eval.py` 用 `seed_days` 播歷史。

---

## 「我跑出嚟唔同」對照表

| 你見到 | 意思 | 點做 |
|---|---|---|
| `ms` 唔同 | 正常，機器速度 | 唔理 |
| `vision_reason = fake_llm` | 你唔小心用咗真 adapter 路徑 | 檢查 `lab03` line 32 係 `FakeLLM()` |
| `vision_reason = no_photo` | ✅ 預期 | 冇相 = 冇試 vision |
| `tool_calls = []` | 唔正常 | FakeLLM 應該固定回兩個 tool；睇下有冇改過 `llm.py` |
| `rows` 大過 0 | 你嘅 temp DB 唔乾淨 | `_common.temp_db()` 每次應該係新檔 |
| `entry_written = False` | 你改咗 `user_text` 做非皮膚問題 | 呢個係**正確行為**，見 lab08 |
| `ImportError: app` | 用錯 python | 一定係 `./backend/.venv/bin/python` |
| Trace 少咗一站 | 真 bug，唔係你錯 | 開 issue；同時係 `lab03` 練習 3 要你想嘅嗰件事 |

---

## 帶走三句

1. **「node 更新咗咩 state key」比「node 做咗咩」更好用** —— 睇 key 就知有冇人偷嘢做。
2. **`tools` 有四格數字（requested / ran / rows / error）** —— 「要求」同「成功」永遠要分開睇。
3. **`persist` 只回 trace、但改咗 DB** —— state 同世界係兩件事，debug 時唔好搞亂。

---

## 下一步

| 想做 | 去邊 |
|---|---|
| 逐站讀實作 code | `../backend/app/agent/graph.py`：`analyze` 喺 **91**、`tools` **169**、`advise` **265**、`guardrail` **290**、`persist` **328** |
| 睇 trace 喺真 LLM 之下變成點 | `lab09_real_llm.py --real` |
| 睇「唔係打卡」嗰條路 | `lab08_persist_gate.py` |
| 一次過睇所有 node 嘅詳細欄位 | §04 `04-agent-loop.md` |
| 自己寫一個新檢查 | §06 `06-writing-eval.md` ＋ `labs/lab10_own_eval.py` |
