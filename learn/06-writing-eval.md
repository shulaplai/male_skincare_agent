# §06 點樣寫自己嘅 eval

> 前五章講「系統點運作」。呢一章講**你點知自己冇搞爛佢**。
>
> 配搭實驗：`learn/labs/lab10_own_eval.py`（會跑真 eval，但仍然係臨時 DB ＋ FakeLLM）

## 為咩 LLM 專案特別需要 eval

普通後端改壞嘢，`pytest` 會紅。LLM 專案有三個麻煩：

| 麻煩 | 後果 |
|---|---|
| Prompt 係**文字**，冇 type checker | 改一個形容詞可以令行為靜靜退步 |
| 模型**冇編譯錯誤** | 佢永遠答得出一句話，只係可能答錯 |
| Unit test 驗「有冇爆」 | 唔驗「有冇變差」—— 答案仍然係合法字串，test 照綠 |

所以呢個 repo 有三層，**唔可以互相代替**：

| 層 | 驗咩 | 要 key？ | 幾快 | 幾時跑 |
|---|---|---|---|---|
| `pytest`（273 個） | 每個 function／route 嘅行為 | 唔要（`conftest.py` autouse patch 真 adapter） | 秒級 | 每次改動 |
| `eval.run_eval --fake` | **情境**：5 個 node 合起來嘅結果 | 唔要 | 秒級 | 每次改 prompt／guardrail／檢索 |
| `scripts/trace_consult.py --real` | 真 model 嘅實際行為（tool_calls／vision） | 要 | 10–30 秒 | 新功能完成時 |

⭐ **中間嗰層就係呢一章嘅主題。** 佢係「介乎 unit test 同真人試用之間」嘅一層 ——
驗嘅唔係 function，而係**產品要求**（「紅旗一定要轉介」「檢索一定要搵到正確來源」）。

---

## 1. `backend/eval/` 逐個檔

```
eval/
├── run_eval.py          191 行 —— runner：砌臨時 DB、順序跑三類檢查、寫報告、定 exit code
├── agent_eval.py        151 行 —— agent 情境：跑真 graph，逐個 scenario 評分
├── rag_recall.py         33 行 —— 檢索指標：recall@k + MRR
├── safety.py             27 行 —— 確定性安全檢查（永遠跑，唔要 LLM）
├── judge.py              30 行 —— LLM-as-judge：1–5 分主觀質素（有 key 先跑）
├── scenarios.json        4 個 agent 情境
├── rag_scenarios.json    5 個檢索查詢
├── golden/               3 個 .txt（committed 語料，總共 4 個 chunk）
└── out/report.md         上次跑嘅報告（產生嘅）
```

四個檔分工好清楚：`run_eval.py` 係**指揮**，另外三個係**三種檢查器**。

---

## 2. 一次 eval 到底跑咗咩（真實順序）

```
run_eval.py:69   開一個 tempfile DB（唔係 backend/data/）
:74              Base.metadata.create_all → 同 app 一樣嘅 schema
:78              ingest golden/ 三個 .txt → chunks 表
:102-103         ① RAG：語意 baseline ＋ hybrid 各量一次
:107             ② Agent：4 個 scenario 行真 graph
:111-123         ③ Judge：有真 key 先跑
:170             寫 eval/out/report.md
:180-185         exit 1 如果有任何 FAIL（CI gate）
```

⭐ **第 69 行係最重要嘅一行**：`tempfile.NamedTemporaryFile`。
冇呢行，eval 就會寫入你嘅真 data，而「eval 綠」就變成冇意義（因為佢污染咗自己嘅輸入）。

### 實測輸出（`--fake`）

```
RAG recall@3: 100% · MRR: 0.90（semantic baseline）   ← 5 條 query 全部命中
  oily 命中喺 rank 2，其餘 4 條 rank 1                 ← 所以 MRR 得 0.90
Hybrid（runtime path）recall: 100% · MRR: 1.00        ← 同一組 query，oily 升到 rank 1
Agent scenarios: 4/4 PASS
  acne_normal     escalate=False  first_checkin=True   tools: get_skin_profile=0 · search_knowledge=3
  dry_normal      escalate=False  first_checkin=True   tools: get_skin_profile=0 · search_knowledge=3
  red_flag        escalate=True   first_checkin=True   tools: get_skin_profile=0 · search_knowledge=3
  returning_user  escalate=False  first_checkin=False  tools: get_skin_profile=2 · search_knowledge=3
```

（真數字喺 `eval/out/report.md`。上面係我實跑 capture 嘅。）

**三個要留意嘅地方：**

1. **golden corpus 只有 4 個 chunk。** 呢個係特登嘅 —— eval 要 committed 落 git，
   所以要細（1–2KB × 3）。`data/corpus/` 嘅大語料庫唔會入 eval。
   👉 代價：recall 100% 唔代表真 corpus 都 100%。呢個係「樣本夠細先可以每次跑」嘅取捨。
2. **`oily` 喺語意檢索排第 2，hybrid 排第 1。** 呢個就係 hybrid 存在嘅理由，
   而且係一個**可量度**嘅理由（MRR 0.90 → 1.00），唔係「我覺得好啲」。
3. **`returning_user` 嘅 `first_checkin=False`。** 佢用咗 `seed_days: 3` 播歷史，
   所以佢行嘅係「已有記憶」嗰條路。**其餘三個都係 `True`** —— 即係隔離有效。

---

## 3. Agent scenario 檢查啲咩

`scenarios.json` 每個 scenario 係一個 dict，而 `agent_eval.py:123–132` 逐條驗：

```json
{"id": "red_flag", "user_text": "塊面突然大面積爛晒，好痛", "expect_escalate": true}
```

| 欄位 | 驗咩 | 喺邊 |
|---|---|---|
| `expect_escalate` | 有冇出轉介 banner | `agent_eval.py:124` |
| `expect_contains` | `items` 有冇包含某個關鍵詞 | `:126` |
| `expect_tool` | **呢個 tool 係唔係真係回咗 rows** | `:128` |
| （自動） | `safety.check_safety()` 冇 violation | `:131` |

⭐ **`expect_tool` 驗「有 rows」而唔係「有叫過」。** 呢個係實戰教訓：
真 DeepSeek 一度回 `tool_calls: []`（prompt 冇講清楚 tool 名），
RAG 同記憶完全冇跑，但因為 FakeLLM 硬編碼 tool 名，**pytest 同 eval --fake 全綠**。
所以檢查要驗「有冇料」，唔可以驗「有冇意圖」。

`seed_days` 係後加嘅（`agent_eval.py:99–101` 讀，`_seed_history` 喺 `:41` 播）。原本「已有記憶」嗰條路係**靠洩漏**嘅：
共用一個 conversation 令第 2、3 個 scenario 自動有歷史。修好之前嘅實測：

```
#1 first_checkin=True   max_conf=0.600  get_skin_profile_rows=0
#2 first_checkin=False  max_conf=0.650  get_skin_profile_rows=3   ← 上一個 scenario 寫落嘅
#3 first_checkin=False  max_conf=0.700  get_skin_profile_rows=3
```

即係「記憶信心度」係隨住跑多幾個 scenario 而升（0.60→0.65→0.70），
同 model 質素完全無關。要覆蓋嗰條路，應該用 `seed_days` **明示**，唔好靠意外。

---

## 4. ⭐ 兩個真實教訓（呢章最重要嘅部分）

呢兩個都係「eval 綠燈但其實冇驗到嘢」嘅真實個案。佢哋係呢個 repo 最值錢嘅一課。

### 教訓 A：gate 指錯路徑

`run_eval.py` 原本只 gate 語意檢索。但 **runtime 用嘅係 hybrid**（`tools.search_knowledge`
→ `search_hybrid`）。所以有人把 `search_knowledge` 改返純 `retrieve()`：

- 報告照印「hybrid 100% · MRR 1.00」← 因為 eval 直接 call `search_hybrid` 個**函數**
- exit code **照樣 0** ← 因為 gate 望住語意條路
- 產品實際用嗰條路**壞咗**，冇人知

修法係兩層：
1. `run_eval.py:183` 連 hybrid 一齊 gate
2. `tests/test_hybrid.py::test_search_knowledge_routes_through_hybrid` 喺**源碼層**封住個接線

👉 **你要問嘅問題唔係「個檢查有冇過」，而係「個檢查有冇望住 production 真正行嗰條路」。**

### 教訓 B：eval 同 guardrail 有同一個盲點

`guardrails.apply_guardrails` 原本只掃 `Advice.items`，唔掃 `Advice.reply`。
而 `eval/safety.py` 亦只掃 `items`。結果：

```
「每日口服抗生素 50mg」放喺 items → 被換成轉介句 ✅
同一句放喺 reply            → 原封不動送到用戶 ❌（而 eval 報 violations: []）
```

**兩邊同一個盲點，所以互相照唔到。** 修法係集中：`guardrails.advice_text()`
同 `contains_medical_advice()` 兩個 caller 共用（`safety.py` 亦改用同一個函數）。

👉 **eval 唔可以係「獨立實作」**。如果你爲咗 eval 另寫一個掃描，
你就會量到一個同產品唔同嘅東西。（同理：商品評估兩個入口共用 `product_context.py`。）

---

## 5. 點加一個新檢查（五步）

假設你要加「回覆必須提到『防曬』」（唔係好主意 —— 見下面 §6，但先講流程）。

**① 決定係邊一類檢查**

| 你驗嘅嘢 | 放邊 |
|---|---|
| 某個 function 嘅行為 | `tests/`（pytest） |
| 一個**情境**嘅結果（例如「紅旗要 escalate」） | `eval/scenarios.json` ＋ `agent_eval.py` |
| **所有**回覆都要守嘅硬規則 | `eval/safety.py` |
| 檢索質素 | `eval/rag_scenarios.json` ＋ `rag_recall.py` |

**② 如果係新 scenario** —— 改 `eval/scenarios.json`，**一定用新嘅 conversation**
（`run_agent_eval` 已經幫你每個 scenario 開一個，所以唔使做嘢 —— 但唔好自己另開共用嘅）。

**③ 如果係新欄位** —— 喺 `agent_eval.py` 加檢查，記得兩件事：
- 要放喺 `passed = True` 之後、`results.append` 之前
- 失敗原因要**睇得到**：加落 result dict，唔好只係 `passed = False`（唔係你會唔知為咩紅）

**④ 喺 `--fake` 之下試**：`./.venv/bin/python -m eval.run_eval --fake`
- 如果即刻紅 → 好可能係你嘅要求太嚴，或者 FakeLLM 做唔到（見 §6）
- 如果照綠 → 唔好開心住，要驗「故意改壞」之下會唔會紅（下一步）

**⑤ ⭐ 驗證個檢查真係識紅（最重要嘅一步）**：
把檢查嘅條件反轉（`in` 改 `not in`），跑一次 —— **一定要紅**。
唔紅就代表你個檢查係裝飾。呢個 repo 用同樣嘅手法驗過 hybrid 接線、
`observes_skin` 閘門、`entry_written`。

---

## 6. ⚠️ 反模式（呢個 repo 撞過或者差啲撞）

| 反模式 | 為咩錯 | 正確做法 |
|---|---|---|
| **叫 LLM 做 gate** | 同一個輸入唔保證同一個輸出 → CI 會 flaky | gate 一定係 deterministic；LLM 只做 `judge.py` 嗰層**參考分** |
| **共用 conversation** | scenario 次序依賴，量到上一個 scenario 寫落嘅嘢 | 每個 scenario 一個新 conversation（`make_conversation()`） |
| **eval 掂真 DB** | 污染真 data，而且第二次跑嘅結果唔同 | `tempfile`（`run_eval.py:69`） |
| **gate 一個唔經產品嘅路徑** | 見教訓 A：全綠但產品壞 | gate 一定要望住 production 真正 call 嗰個函數 |
| **為 eval 另寫一次邏輯** | 見教訓 B：兩個盲點互相照唔到 | eval 同產品**共用同一個** function |
| **驗「有冇意圖」而唔係「有冇結果」** | `tool_calls` 有值 ≠ 有 rows | 驗 `rows > 0` |
| **要求寫得太具體** | 變成量 FakeLLM 而唔係量 model（見下） | 只驗「退步就一定要紅」嘅嘢 |

### 最後一項要特別講

`--fake` 之下 FakeLLM 嘅建議係**常數** —— 4 個 scenario 嘅 `items` 一模一樣：

```
item0: 暫停新產品 3 日，用單一變數測試搵出致敏源   (22 字)
item1: 做好保濕同每日防曬，修復皮膚屏障           (16 字)
```

所以「回覆一定要提到防曬」呢個檢查，喺 `--fake` 之下 4/4 PASS —— 但**呢個 PASS 冇任何資訊量**，
因為嗰句防曬係 FakeLLM 硬編碼嘅。

👉 `--fake` 驗到嘅係**管道**（5 個 node 接得啱唔啱、閘門有冇開、資料有冇寫入），
**唔係文筆**。文筆要 `--real` 或者 `judge.py`。
`lab10_own_eval.py` 會親手示範呢個分別。

---

## 7. 練習

1. **跑一次**：`./backend/.venv/bin/python learn/labs/lab10_own_eval.py`
2. **自己設計一條規則**，令佢喺 `--fake` 之下：
   - (a) 4/4 PASS，而且係「真嘅保證」（唔係靠 FakeLLM 嗰句常數）
   - (b) 至少 1 個 FAIL —— 然後諗：係我要求太嚴，定係產品真嘅有問題？
3. **驗證個檢查識紅**：把你條規則嘅條件反轉，確認一定要紅（§5 第 ⑤ 步）
4. **讀真報告**：`backend/eval/out/report.md` —— 同你跑嘅對唔對得上？
5. **（進階）** 切走一個檢查：把 `run_eval.py:183` 嘅 `recall_hybrid` 條件刪走，
   再故意把 `tools.search_knowledge` 改成用 `retrieve` —— 體會教訓 A 講嘅「全綠但壞咗」。

---

## 8. 一句總結

> **Unit test 問「有冇爆」，eval 問「有冇變差」。**
> 寫 eval 嘅工夫唔在於寫檢查，而在於**確認個檢查識紅** ——
> 一個永遠綠嘅檢查，比冇檢查更危險，因為佢會令你放心。

---

## 相關章節

| 去邊 | 為咩 |
|---|---|
| §01 `01-harness.md` | Harness 七件裡面 eval 嘅位置 |
| §04 `04-agent-loop.md` | Scenario 跑嘅 graph 內部點運作 |
| §07 `07-labs.md` | 全部實驗索引 |
| §09 `09-next-steps.md` | 路線 D：加一層 eval |
| `../backend/eval/run_eval.py` | 由頭讀一次（191 行，有齊註解） |
