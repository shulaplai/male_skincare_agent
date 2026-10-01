# §04 Agent 嘅思考過程：5 個 node 逐步

> 你第四個問題：「成個思考過程係點一步一步嚟？」呢章就係嗰個答案。
> **先跑 `./backend/.venv/bin/python learn/labs/lab03_agent_loop.py` 再讀** —— 你會有畫面。

## 0. 先搞清楚「state」係咩

`backend/app/agent/state.py:21`：

```python
class AgentState(TypedDict, total=False):
    conversation_id: str
    user_text: str
    photo_paths: list[str]
    cloud_analysis: bool          # 用戶同意咗未（privacy gate）
    clip: dict | None             # 今次係一條片（唔係相）
    analysis: dict | None         # ① 寫
    tool_results: list[dict]      # ② 寫
    recent_messages: list[str]    # ② 寫
    first_checkin: bool           # ② 寫
    product_eval: dict | None     # ② 寫（貼成份表時）
    advice: dict | None           # ③ 寫（④ 可能改寫）
    escalate: bool                # ③④ 寫
    trace: Annotated[list, operator.add]   # ⭐ 每個 node 都 append
```

⭐ `trace` 用 `operator.add` reducer：每個 node **只 append 自己嗰行**，
LangGraph 幫你合併。所以 `graph.stream()` 吐嘅每個 delta 只係「呢一站加咗嘅 trace」
（lab03 示範咗要自己 append 先睇得到全部）。

## 1. 五站總覽

| 站 | 檔案位置 | 係唔係 LLM | 輸入 | 輸出 |
|---|---|---|---|---|
| ① analyze | `graph.py:91` | ✅ **LLM** | 用戶文字／相 | `analysis`、`vision_used` |
| ② tools | `graph.py:169` | ❌ code | `analysis.tool_calls` | `tool_results`、`recent_messages`、`first_checkin` |
| ③ advise | `graph.py:265` | ✅ **LLM** | analysis + tool_results + 記憶 | `advice` |
| ④ guardrail | `graph.py:290` | ❌ code | `advice` + 用戶原文 | 改寫後嘅 `advice`、`escalate` |
| ⑤ persist | `graph.py:328` | ❌ code | 全部 | DB 寫入（Entry／insight／timeline／chat） |

## 2. ① analyze：唯一「睇」嘅位

做三件事：
1. 決定要唔要用 vision（`has_photo and consent and not FakeLLM`）
2. Call LLM（text 或 vision）→ `SkinAnalysis`
3. 記低 `vision_reason`（`used` / `no_photo` / `consent_off` / `photo_unreadable` / `vision_error`）

真 trace（lab03，純文字）：
```
analyze  0.1ms  detail: {has_photo: False, cloud_consent: True, vision_attempted: False,
                         vision_used: False, images_loaded: 0, vision_reason: 'no_photo',
                         tool_calls: ['get_skin_profile', 'search_knowledge'],
                         attributes: 3, metrics: 2}
```

**Privacy 重點**：`cloud_analysis` 一眼關乎「相可唔可以離開部機」。
呢個 flag 由 `service.run_consult` 讀 DB 決定（唔靠前端），所以 UI 收埋個掣都擋唔到。

## 3. ② tools：唯一「查資料」嘅位

Model 喺 `analysis.tool_calls` 填咗工具名（字串），呢站負責**真係去跑**：

```python
WHITELIST = {"get_skin_profile", "get_recent_entries", "search_knowledge"}   # tools.py:13
```

真 trace：
```
tools  7.2ms  detail: {requested: ['get_skin_profile', 'search_knowledge'],
                       ran: [{tool: 'get_skin_profile', rows: 0},
                             {tool: 'search_knowledge', rows: 0}],
                       recent_messages: 0, first_checkin: True}
```

睇得明呢行，你就識 debug 一半嘅 agent 問題：
- `requested` 空 → model 冇要求工具（RAG／記憶完全冇跑）
- `rows = 0` → 工具跑咗但冇資料（chunks 空／記憶空）
- `first_checkin = True` → 呢個對話未有 Entry（所以 onboarding 語氣）

## 4. ③ advise：唯一「講」嘅位

`build_advise_prompt(state)` 會帶住：分析、工具結果、最近對話、first_checkin 標記。
真 trace：
```
advise  0.1ms  detail: {prompt_chars: 990, tool_rows: 0, items: 2, reply_chars: 99, detected_events: 0}
```

⭐ `prompt_chars` 同 `tool_rows` 係最有用嘅兩個數：
- `tool_rows = 0` → 檢索結果冇入到 prompt → model 係**憑空答**（唔應該當可靠建議）
- `prompt_chars` 突然大 → 可能塞得太多（貴、慢、model 會分心）

真回覆（lab03）：
> 睇咗你嘅情況：下巴有兩粒新暗瘡、T 字位偏油，兩頰就中性。新暗瘡多數同最近變數有關，
> 我建議先暫停新產品三日，用單一變數測…

## 5. ④ guardrail：唯一「安全」嘅位

```python
escalate = contains_any(user_text, RED_FLAGS)          # guardrails.py:23
if contains_medical_advice(advice_text(advice)):       # guardrails.py:78
    reply = ESCALATION_MESSAGE                          # 改寫**正文**
    items = [ESCALATION_MESSAGE]                        # 同**bullet**
```

真 trace：
```
guardrail  0.0ms  detail: {escalate: False, items_replaced: 0, disclaimer_added: True,
                           forced_by_product_eval: False}
```

⚠️ 記住 lab07 嘅發現：**紅旗只係設 flag（UI 出 banner），改寫文案只喺「有醫療字眼」時發生。**
紅旗嘅語氣係由 prompt + eval 守 —— 知道邊個保證係 code、邊個係 prompt，係 harness 功課。

## 6. ⑤ persist：唯一「寫入」嘅位 + 閘門

```python
observes_skin = bool(analysis.observes_skin) or bool(state.get("vision_used"))   # graph.py:348
if not observes_skin:
    # 只寫 ChatMessage，唔寫 Entry
```

真 trace（lab08 情境 A：問產品）：
```
persist  3.6ms  detail: {observes_skin: False, entry_written: False, attributes: 0,
                         insights_created: 0, timeline_lines: 0}
Entry 數量 = 0 ✅   ChatMessage 數量 = 2
```

真 trace（lab08 情境 B：真打卡）：
```
persist  7.8ms  detail: {observes_skin: True, entry_written: True, attributes: 3, insights_created: 3}
Entry 數量 = 1 ✅
```

📖 **為咩要閘門**（真實事故）：以前每條訊息都當打卡，而 `ANALYZE_SYSTEM` 話
「未提及就畀 0」→ 問一句產品問題就寫入**全 0** 當日讀數，覆蓋你真實紀錄；
而且因為「一日只准一個 agent event」，假嘅「改善」會被**永久凍結**。

## 7. 兩個睇流程嘅方法

```bash
# 逐 node 吐 delta（教學／debug 用；lab03 就係噉做）
for chunk in runner.stream(state): print(chunk)

# 等跑完一次過攞最終 state（production 用；`/api/consult` 就係噉）
result = runner.invoke(state)
```

Production 入口：`main.py:365` `POST /api/consult` → `service.run_consult:71`。

## 8. 本章練習

1. 跑 `lab03`，指出邊一站係你可以改 prompt 就影響到嘅、邊一站只能改 code。
2. 跑 `lab06`，用 `run_tool` 叫一個唔喺 whitelist 嘅工具名，睇佢點回應。
3. 跑 `lab08`，將情境 A 嘅 `observes=False` 改成 `True`，睇 Entry 數量變化。
4. 進階：喺 `graph.py` 加一個 `print` 落 `advise` node 頭一行，跑 `trace_consult.py`，
   睇 prompt 實際有幾長（記得之後刪走）。

## 本章重點

1. 五站、只有 ①③ 係 LLM；每一站都有明確責任，所以 trace 一行就知邊度出事。
2. `trace.detail` 四個數最有用：`vision_reason`、`tool_calls`/`rows`、`tool_rows`、`entry_written`。
3. 寫入閘門係「結構化判斷 + code 決定」，唔係靠關鍵詞猜。
