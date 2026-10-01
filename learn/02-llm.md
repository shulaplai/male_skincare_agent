# §02 LLM：adapter、prompt、結構化輸出

> 你第二個問題：「LLM 係靠咩、點行，喺個 code 入邊點走？」呢章由最抽象講到最實際。

## 1. LLM 本質：一個「接龍」機器（但接得非常準）

- 你俾佢一串文字（**prompt**），佢預測**下一個 token**（可以理解為「字／詞碎」）。
- 逐個 token 生成，所以係 streaming、有延遲、而且**每次可能唔同**（temperature > 0）。
- 佢冇記憶：每次 call 都係獨立。你想要「記憶」就要自己塞落 prompt（或者用工具查 DB）。
- 上下文有上限（context window）。塞太多嘢 → 貴、慢、而且會「忘記」中間。

呢啲性質決定咗 harness 嘅設計（§01）：合約、狀態、留底。

## 2. Codebase 入面：LLM 收窄成兩個 method

`backend/app/agent/llm.py`：

| 位置 | 係咩 |
|---|---|
| `llm.py:35` `class FakeLLM` | 假嘅（罐頭輸出，零成本） |
| `llm.py:77` `class AnthropicLLM` | Anthropic adapter（香港直連會 403） |
| `llm.py:108` `class OpenAICompatLLM` | **DeepSeek 用呢個**（OpenAI 相容 API） |
| `llm.py:186` `def get_llm(kind)` | 揀邊個 adapter（`"text"` / `"vision"`） |

兩個 method（三個 adapter 都要有）：

```python
def structured(self, system: str, user: str, schema: type[T]) -> T
def structured_vision(self, system: str, user: str, schema: type[T], images: list[dict]) -> T
```

⭐ **Adapter pattern 嘅價值**：整條 pipeline（5 個 node、guardrail、persist）完全唔知
你用邊個 model。想換 model／換供應商／本機跑，只改 `get_llm()` 一個位。

跑 `lab01_first_llm_call.py` 你會見到 `get_llm('text')` 回 `OpenAICompatLLM`
（因為 `backend/.env` 有真 key），但實驗照樣傳 FakeLLM 入去 —— 唔會燒錢。

## 3. Prompt：你唯一嘅「非程式碼邏輯」

Prompt 住喺 `backend/app/agent/prompts.py`（純函數，冇 DB、冇 DOM，所以隨時 import 測試）。

| 函數 | 做咩 |
|---|---|
| `ANALYZE_SYSTEM` | analyze 站嘅系統指示（六個 attribute 點評 0–3） |
| `build_analyze_prompt(text, has_photo, …, clip)` | 砌 analyze 嘅 user prompt |
| `build_advise_prompt(state)` | 砌 advise 嘅 prompt（會帶記憶、檢索結果、分析） |
| `ADVISE_SYSTEM` | advise 站嘅寫作規則（2–5 句、唔開藥、detected_events） |

Prompt 有一條**反直覺**但重要嘅規則（`AGENTS.md` 有寫）：

> `observes_skin` 唔可以漏入 advise 嘅 prompt。

因為真 model 會照讀欄位名（「分析顯示 observes_skin=false」），
又會將「唔係打卡」誤讀成「睇唔到皮膚」→ 叫用戶補相，完全冇答佢問嘅問題。
所以 `build_advise_prompt` 一定要 `pop` 走佢，改用廣東話描述情況。

📌 **Lesson**：prompt 係介面，唔係雜物袋。每一句都要有理由，而且要有 test 封住（`tests/test_prompt_*.py`）。

## 4. 「結構化輸出」點做到？

`OpenAICompatLLM.structured()` 內部做咗：`self._client().with_structured_output(schema)`
（`llm.py:168`）——即係用 provider 嘅 **JSON schema mode**，強制輸出符合 schema。

Model 唔聽話點算？`_invoke()` 有 retry，而且**重試嗰陣會 append 一段糾正訊息**
（唔係原封不動再問一次 —— 實測原封不動連續失敗）。最多 3 次，仲失敗就拋
`OutputParserException`，`service.run_consult` 接住轉成 **HTTP 503 可讀訊息**
（唔會裸 500，亦**唔會造假分析**）。

## 5. 兩個真實陷阱（呢啲就係 harness 的價值）

### 陷阱 A：DeepSeek V4 thinking mode（`llm.py:124` 附近）

DeepSeek V4 **預設開 thinking**，而 thinking 模式**唔准**強制 `tool_choice`
（`with_structured_output` 會噉做）→ HTTP 400。

解法（已寫入 code，唔好移除）：

```python
extra_body={"thinking": {"type": "disabled"}}   # "off" 呢個字串唔得，會 400
```

### 陷阱 B：真 model 唔識叫 tool

以前 `TOOL_GUIDE` 寫成「你可以 call 呢啲工具」，DeepSeek 就真係 emit 一個
叫 `search_knowledge` 嘅 *function call* → `OutputParserException: Unknown tool type`。
而 FakeLLM 硬編碼 tool 名，所以 test 全綠、上線即爆。

現行寫法係「**你唔可以 call 任何 function**，只可以喺 `tool_calls` 欄位填字串」，
而 `tests/test_observability.py` 有斷言封住。§04 會講 tool call 點運作。

## 6. Vision：另一個 model

```python
service.run_consult(...)  # 同時傳 llm=get_llm("text") 同 vision_llm=get_llm("vision")
```

- 有相 + 用戶同意 → 用 **vision model**（`deepseek-v4-flash-vision-exp`）睇相
- 冇相／唔同意 → 用 **text model**，而且 prompt 會講明「用戶有相但你睇唔到」
- **唔可以**用 text model 去 call `structured_vision`（會靜靜 fallback，你就以為睇咗相）

判別方法：看 trace 嘅 `analyze.detail.vision_reason`：
`used` / `no_photo` / `consent_off` / `photo_unreadable` / `vision_error` / `fake_llm`。

## 7. 成本同延遲：一次 consult 幾多 call？

```
analyze  → 1 個 LLM call（有相就係 vision）
tools    → 0 個（純 Python：SQL + embedding 計算）
advise   → 1 個 LLM call
guardrail→ 0 個
persist  → 0 個
```

即係**一次對話 2 個 call**（真 LLM 大約 5–10 秒）。呢個就係為咩
UI 要寫「教練諗緊…約 5–10 秒」，同為咩要 `graph.stream()` 令前端可以顯示進度。

## 8. 本章練習

1. 跑 `lab01_first_llm_call.py`，指出邊一行 code 真正「打去 model」。
2. 跑 `lab02_structured_output.py`，睇 Pydantic 點擋一個亂出嘅 `severity: 5`。
3. 想做真 call：`./backend/.venv/bin/python learn/labs/lab09_real_llm.py --real`（會用你嘅 key）。
4. 打開 `prompts.py`，搵出「唔好講『呢張相』」呢句，想想為咩要寫到咁死。

## 本章重點

1. LLM 喺 code 入面收窄成 `structured(system, user, schema)` 一個 method。
2. Adapter pattern 令換 model 唔使改 pipeline；`get_llm()` 係唯一入口。
3. Prompt 係要維護嘅介面；結構化輸出 + retry + 可讀 503 就係 harness。
