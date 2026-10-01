# §01 Harness engineering：包住 LLM 嘅骨架

> 「點做 harness engineering」係你第一個問題。呢章用 SkinCoach 逐件零件拆俾你睇。

## 1. 咩係 harness？

**Harness = 令一個非確定性嘅零件（LLM）可以安全出貨嘅所有周邊工程。**

打個比喻：LLM 係一個好聰明但唔可靠嘅實習生。你唔會同佢講「記得唔好開錯藥」就算數，
你會：

1. 俾佢一份**表格填**（唔准自由發揮）→ 型別合約
2. 佢填完，**你自己核對**（唔係佢自己講冇問題）→ deterministic core
3. 佢只可以**叫你做嘢**，唔可以直接改你嘅系統 → tool whitelist
4. 每一步都**留底**，出事追得到 → tracing
5. 你有一個**假的實習生**（一秒回覆、唔會出錯）俾你日日測試 → FakeLLM
6. 每次改嘢都跑**一堆自動檢查** → gates

SkinCoach 成個 repo 就係呢六件事。以下逐件指去真 code。

---

## 2. 零件一：型別合約（`backend/app/agent/schemas.py`）

```python
class SkinAnalysis(BaseModel):        # schemas.py:32
    observes_skin: bool
    summary: str
    metrics: list[Metric]
    attributes: list[Attribute]       # key 只可以係六個固定值，severity 0–3
    tool_calls: list[str]
```

LLM 唔係「寫篇文章」，係「填呢張表格」。填錯 → Pydantic 拋錯 → 唔會流入系統。

📌 **為咩要咁做**：LLM 輸出係文字。你嘅下游 code（記憶、timeline、相關性）要嘅係數字。
合約就係兩者之間嘅唯一介面。詳情 §02 同 lab02。

---

## 3. 零件二：Deterministic core（唔靠 model 做判斷）

呢個 repo 有一條明文約定（`AGENTS.md` 約定 #1）：

> **Deterministic core 行先，LLM 只做模糊層。**

| 判斷 | 邊個做 | 檔案 |
|---|---|---|
| 「呢句係唔係皮膚觀察」 | LLM（模糊） | `prompts.py` + `analyze` node |
| 「要唔要寫 Entry」 | **code**（`observes_skin or vision_used`） | `graph.py:348` |
| 嚴重度變化／改善定惡化 | **code** | `attributes.py` |
| 記憶要唔要取代／加強 | **code**（tag + direction） | `memory.py` |
| 有冇醫療字眼 | **code**（regex + 詞表） | `guardrails.py` |
| 相關性（食辣 → 之後爆瘡） | **code** | `correlation.py` |
| 成份識別 | **code**（字典 + 引文） | `ingredients.py` |

⭐ 一句話：**LLM 負責「睇」同「講」，code 負責「判斷」同「記錄」。**

跑 `lab07_guardrail.py` 你會見到：同一句「每日口服抗生素 50mg」放喺 `reply` 或 `items`，
都會被換成轉介句 —— 因為檢查係 code，唔係 prompt 願望。

---

## 4. 零件三：可預測嘅流程（LangGraph，`graph.py:547`）

```python
g.add_node("analyze", analyze)      # 唯一「睇」嘅位（LLM）
g.add_node("tools", tools)          # 唯一「查資料」嘅位（code）
g.add_node("advise", advise)        # 唯一「講」嘅位（LLM）
g.add_node("guardrail", guardrail)  # 唯一「安全」嘅位（code）
g.add_node("persist", persist)      # 唯一「寫入」嘅位（code）
```

好處：
- **邊度都可能出錯，但你知道係邊度**（trace 逐站有記錄）。
- **要加功能，就加一個 node 或者改一站**，唔使喺一個 1000 行 function 入面加 if。
- 每一站嘅輸入輸出都係 `state`（一個 dict），所以容易測試。

§04 會逐站拆。

---

## 5. 零件四：Observability（唔准靜靜壞掉）

| 工具 | 做咩 |
|---|---|
| `state["trace"]`（`state.py:13`） | 每個 node 一行：node／ms／摘要。`/api/consult` 會回埋 |
| `graph.stream()` | 逐 node 吐 delta（lab03 就係用佢） |
| `data/runs.jsonl`（`service.write_run_log:41`） | 每次 consult 一行 JSON，事後追 |
| `scripts/trace_consult.py` | 一 command 睇成條路，附「trace 口訣」 |

`AGENTS.md` 明文規定：**「唔好再靜靜吞錯誤」**（vision 失敗、tool 例外、未知 tool 名、
embedder fallback 全部要 log + 入 trace）。呢句係撞過痛先寫落去嘅。

---

## 6. 零件五：FakeLLM ＋ 臨時 DB（`llm.py:35`）

```python
class FakeLLM:
    def structured(self, system, user, schema) -> T:   # 回罐頭答案
    def structured_vision(self, system, user, schema, images) -> T:
```

- **有 key** → `get_llm()` 回真 adapter（`llm.py:186`）
- **冇 key** → 回 FakeLLM（整條 pipeline 照跑得通）

所以：CI、教學、demo 都唔需要密鑰；`pytest -q` 4 秒跑完 273 個 test。

⚠️ **但呢個係陷阱**：`eval --fake` 全綠 **唔等於** model 行為正確。
歷史上真係撞過：FakeLLM 硬編碼 tool 名，而真 DeepSeek 完全唔識叫 tool
（`tool_calls: []`）→ 上線即爆，RAG 同記憶完全冇跑。所以仲要 `--real` 驗（lab09）。

---

## 7. 零件六：Gates（每次改嘢都要跑）

| Gate | 命令 | 守住咩 |
|---|---|---|
| Backend test | `cd backend && ./.venv/bin/python -m pytest -q` | 273 個 unit／integration |
| Eval | `./.venv/bin/python -m eval.run_eval --fake` | RAG recall／agent 情境／safety |
| Frontend | `cd frontend && npm run ui:check` | typecheck ＋ eslint ＋ stylelint ＋ 51 個 UI test |
| Trace | `./.venv/bin/python scripts/trace_consult.py --text "…"` | 手動睇一次真流程 |

Eval 係「比 unit test 更似真」嘅一層：佢用 golden corpus 計 retrieval recall、
用假 LLM 跑固定情境、仲有 safety scenario（例如紅旗一定要轉介）。

---

## 8. 零件七：成文約定（呢個 repo 最值錢嘅嘢）

`AGENTS.md` 有一節「陷阱（真實撞過）」。每一條都係一句「唔好再犯」：

- `MEDICAL_TERMS` 唔可以有 bare `"mg"`（substring 會亂中）
- `TOOL_GUIDE` 措辭唔可以寫成「你可以 call 呢啲工具」（真 model 會當係 function → 掛）
- `.chat` 一定要有 `min-height: 0`（唔係長對話就爆版）
- 冇定義嘅 CSS 變數（`--bg2`）會令暗色模式淺底淺字

**Harness engineering 有一半係文件**：寫低點解要噉做，下一個人（包括三個月後嘅你）
就唔會拆咗個安全網。

---

## 9. 本章練習

1. 跑 `lab07_guardrail.py`，然後答：**邊啲保證係 code、邊啲係 prompt？**
   （提示：步驟 4 顯示紅旗只出 banner、唔改寫文案 —— 呢個就係保證嘅邊界。）
2. 打開 `backend/app/agent/graph.py`，搵出 `persist` node 嗰行 `observes_skin = ...`（第 348 行），
   同自己講一次「為咩寫入判斷唔交俾 LLM」。
3. 跑 `./backend/.venv/bin/python scripts/trace_consult.py --text "下巴爆瘡點算？"`，
   睇個 trace，然後讀嗰個 script 開頭嘅「trace 口訣」。

## 本章重點（背落嚟）

1. Harness = 令 LLM 可以出貨嘅周邊工程：合約、確定性核心、流程、留底、假拍檔、自動檢查、文件。
2. **LLM 只做「睇」同「講」；判斷同記錄係 code。**
3. 假 LLM 令測試快又免費，但佢**驗證唔到** model 行為 —— 要 `--real` 補。
