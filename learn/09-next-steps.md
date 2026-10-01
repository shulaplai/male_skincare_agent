# §09 學完之後：點繼續落去

## 1. 你已經掌握嘅（自我檢查）

- [ ] 講得出 agent 同普通 backend 嘅分別，同「LLM 只佔兩站」
- [ ] 講得出 `structured(system, user, schema)` 三個參數各自負責咩
- [ ] 講得出 embedding 係咩、為咩 384 同 128 唔可以混
- [ ] 講得出五個 node 順序同各自責任
- [ ] 講得出 `entry_written` 點解唔可以交俾 LLM 決定
- [ ] 講得出邊啲安全保證係 code、邊啲係 prompt

## 2. 五條進階路線（由易到難）

### 路線 A：改 prompt（最容易，但要小心）
```bash
# 改 prompts.py 一段文字 → 跑 test 睇有冇爆 → 跑 eval
cd backend && ./.venv/bin/python -m pytest -q tests/test_prompt_photo_claims.py
./.venv/bin/python -m eval.run_eval --fake
./.venv/bin/python scripts/trace_consult.py --real --text "下巴爆瘡點算？"
```
⚠️ 改 prompt 一定要三件事齊：test（措辭有冇守住）、eval（情境有冇退步）、真 LLM trace（行為有冇變）。

### 路線 B：加一個 node
例如「sleep node」：由輸入抽睡眠時數，寫入 timeline。步驟：
1. `state.py` 加欄位 → 2. `graph.py` 加 `def sleep(state)` → 3. `g.add_node/add_edge` → 4. 寫 test。
（`AGENTS.md` 有「點樣加一個新功能」嘅八步順序。）

### 路線 C：加一個 tool
```python
# 1. tools.py 加落 WHITELIST + run_tool 實作
# 2. prompts.TOOL_GUIDE 加名（⭐ 措辭要保留「唔可以 call」）
# 3. schemas.SkinAnalysis.tool_calls description 加名
# 4. tests/test_observability.py 會檢查三處一致
```

### 路線 D：加一層 eval
例如「回覆一定要有 2–5 句」：
1. `eval/agent_eval.py` 加檢查 → 2. `eval/scenarios.json` 加情境 → 3. 跑 `--fake` 睇紅定綠。
⭐ eval 係「幫你記住產品要求」嘅機制 —— 比 prompt 註解可靠。
⚠️ **加完一定要反轉條件確認佢識紅** —— 完整流程見 §06 `06-writing-eval.md`，實作見 `labs/lab10_own_eval.py`。

### 路線 E：換 model（最實用）
- 換供應商：`llm.py` 加一個 adapter（照抄 `OpenAICompatLLM`），`get_llm()` 加 branch。
- 用本機模型：Ollama 有 OpenAI 相容 API → 其實只改 base_url + model 名。
- 換 embedding：`rag/embeddings.py` 加 class，記得**重新 index** 成個語料庫。

## 3. 三個唔好踩嘅坑（呢個 repo 用血換返嚟）

1. **唔好靠 prompt 做安全**。要就寫 code（見 lab07）。
2. **唔好靜靜吞錯誤**。fallback／例外一定要 log + 入 trace，否則你會 debug 到懷疑人生。
3. **假 LLM 綠燈唔等於真 model 啱**。每個新功能都要 `--real` 跑一次（尤其 tool call 同 vision）。

## 4. 想再深入：建議閱讀順序

| 順序 | 睇咩 | 為咩 |
|---|---|---|
| 1 | `docs/architecture.md` | 全系統鳥瞰 |
| 2 | `docs/backend-flow.md` | 由請求到 DB 嘅逐步流程（引真行號） |
| 3 | `backend/app/agent/graph.py` | 讀 5 個 node 嘅實作 |
| 4 | `backend/eval/run_eval.py`＋`scenarios.json` | 產品要求點變成自動檢查（先讀 §06） |
| 5 | `docs/status-vs-claims.md` | 邊啲 claim 有實測、邊啲冇（誠實文化） |
| 6 | `AGENTS.md` 嘅「陷阱」一節 | 30 條真實教訓，等於 30 課 |

## 5. 你嘅下一步（我建議）

1. 跑齊 10 個 lab（大約 50 分鐘），每個 lab 睇完寫一句「呢個 lab 教我咩」落 `learn/notes.md`（自己開）。
2. 揀路線 A（改一句 prompt）做一次完整循環：改 → test → eval → 真 trace。
3. 揀路線 C（加一個 tool）—— 呢個係最接近日常 AI 工程工作嘅任務。
4. 有興趣睇「唔用 framework 嘅版本」：`exercises.md` 練習 4 教你寫一個 30 行 agent 做對照。
