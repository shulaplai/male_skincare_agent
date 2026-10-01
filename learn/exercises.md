# 習題（附錄 —— 唔係 script，係要你自己改 code）

> 三個練習，由易到難。每個都要求你**跑 gate**（test／eval），因為呢個就係 harness 嘅日常。

## 練習 1（15 分鐘）：令回覆短啲

**做咩**：`backend/app/agent/prompts.py` 嘅 `ADVISE_SYSTEM` 而家要求「2–5 句」。改成「2–3 句」。

**檢查**
```bash
cd backend
./.venv/bin/python -m pytest -q                          # 有冇 test 壞？
./.venv/bin/python -m eval.run_eval --fake                # 情境有冇退步？
./.venv/bin/python scripts/trace_consult.py --real --text "下巴爆瘡點算？"   # 真行為
```
**問題**：邊個 test 其實喺度保護「唔可以太短」？（搵 `tests/test_prompt_*.py`）

---

## 練習 2（45 分鐘）：加一個 tool

**做咩**：加 `get_product_history` —— 讀用戶用過／停用過嘅產品（`products` table）。

**步驟**（`AGENTS.md` 有同樣嘅清單）
1. `app/agent/tools.py`：`WHITELIST` 加名 + `run_tool` 加分支
2. `app/agent/prompts.py`：`TOOL_GUIDE` 加名 —— ⚠️ **唔可以**寫成「你可以 call 呢啲工具」（會令真 model 掛）
3. `app/agent/schemas.py`：`SkinAnalysis.tool_calls` 嘅 description 加名
4. 寫 test：`tests/test_observability.py` 會驗三處一致；自己加一個 test 驗 tool 回傳形狀
5. 跑 gate

**問題**：如果只改 1 同 3 而漏咗 2，會發生咩事？（提示：真 model 唔會叫呢個工具，但 FakeLLM 照叫）

---

## 練習 3（30 分鐘）：紅旗都要硬改寫文案

**背景**：lab07 發現「紅旗只設 flag、唔改寫文案」。呢個係保證嘅邊界。

**做咩**：喺 `app/agent/guardrails.py` 嘅 `apply_guardrails` 加：
```python
if escalate:
    reply = ESCALATION_MESSAGE
    items = [ESCALATION_MESSAGE]
```
**但要小心**：呢個會令**所有**紅旗都變成罐頭句（可能太硬）。所以你要做一個決定：
- (a) 全部硬改寫（最安全，但冇人情味）
- (b) 只喺冇任何轉介字眼時改寫
- (c) 維持現狀，靠 prompt + eval

**寫落 `learn/notes.md`**：你揀邊個、為咩。然後跑：
```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m eval.run_eval --fake
```
**問題**：`eval/safety.py` 而家驗咩？（睇完你就知點解呢個決定唔可以隨手改）

---

## 練習 4（60 分鐘，進階）：寫一個 30 行 agent 做對照

**目標**：唔用 LangGraph、唔用 Pydantic，用最原始嘅方式做一個「LLM ＋ 一個 tool」嘅 agent。
你會**親手感受到**為咩要 framework，同為咩要 harness。

```python
# learn/labs/my_first_agent.py（你自己寫，唔要抄）
# 1. 定義一個工具：def get_weather(city) -> str
# 2. 砌 prompt：「你有呢啲工具：get_weather。要用地話，回 JSON {"tool": "...", "arg": "..."}」
# 3. 叫 LLM（用 FakeLLM 或者真 model）→ parse JSON
# 4. 如果有 tool → 執行 → 再叫一次 LLM
# 5. 印出成個 loop 嘅每一步
```

**對照問題**（寫落 `learn/notes.md`）
1. 你嘅版本邊度會因為 model 亂出格式而爆？SkinCoach 用咩擋？
2. 你嘅版本有冇 trace？出事你點知係邊一步？
3. 你嘅版本點防止「model 亂叫一個唔存在嘅工具」？
4. 如果要有 5 個工具、3 種 event type、記憶同 timeline，你個版本會變成幾多行？
