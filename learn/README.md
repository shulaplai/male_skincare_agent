# AI Agent 入門課 — 用 SkinCoach 做教材

> 呢個課程係為「**識 Python、寫過 API，但完全未接觸過 AI／LLM**」嘅人寫嘅。
> 唔會教你 `for` loop，會教你 **agent 係咩、LLM 喺 code 邊度、embedding 做咩、思考過程點行**。

## 一句話：呢門課要你帶走咩

| 問題 | 你會喺邊一章搵到答案 |
|---|---|
| LLM 喺 code 入面到底係咩？ | §02（`app/agent/llm.py`） |
| 為咩要有 Pydantic schema？ | §01 §02（`app/agent/schemas.py`） |
| Embedding 喺邊做？RAG 係咩？ | §03（`app/rag/`） |
| 「AI 思考過程」逐步係點？ | §04（`app/agent/graph.py`）＋ [lab03 導讀](walkthrough-lab03.md) |
| 點解 agent 唔會亂開藥？ | §01 §04（`app/agent/guardrails.py`） |
| Harness engineering 係做咩？ | §01（全章） |
| 呢啲 code 喺 Python 環境點行？ | §05 |
| 點證明自己冇搞爛個系統？ | §06（`backend/eval/`） |

## 課程結構（9 章 ＋ 1 附錄 ＋ 10 個實驗）

| # | 章節 | 大約時間 | 配搭實驗 |
|---|---|---|---|
| — | [README](README.md)（你睇緊） | 5 分鐘 | — |
| 00 | [心智模型：agent 同普通 backend 有咩分別](00-what-is-an-agent.md) | 15 分鐘 | — |
| 01 | [Harness engineering：包住 LLM 嘅骨架](01-harness.md) | 40 分鐘 | lab09 |
| 02 | [LLM：adapter、prompt、結構化輸出](02-llm.md) | 40 分鐘 | lab01、lab02、lab09 |
| 03 | [Embedding 同 RAG](03-embeddings-rag.md) | 40 分鐘 | lab04、lab05 |
| 04 | [Agent 嘅思考過程：5 個 node 逐步](04-agent-loop.md) | 60 分鐘 | lab03、lab06、lab08 |
| 05 | [Python 環境同請求生命週期](05-python-runtime.md) | 30 分鐘 | — |
| 06 | [**點樣寫自己嘅 eval**](06-writing-eval.md) | 35 分鐘 | ⭐ lab10 |
| 07 | [實驗索引同思考題](07-labs.md) | — | 全部 |
| 08 | [詞彙表（中英對照）](08-glossary.md) | 參考用 | — |
| 09 | [學完之後：點繼續落去](09-next-steps.md) | 20 分鐘 | — |
| 附 | [習題（要你自己改 code）](exercises.md) | 3 小時 | — |
| 附 | [**lab03 逐格導讀**](walkthrough-lab03.md) | 15 分鐘 | lab03 |

**建議路線**：00 → 01 → 02 → 04（核心，配 lab03 導讀）→ 03 → 05 → 06 → 07 嘅思考題。
想快：直接跑 `lab03_agent_loop.py`，見到五站嘅真 trace，再返去讀 §04。
想知「點證明冇搞爛」：直接跳去 §06 ＋ `lab10_own_eval.py`。

## 點跑實驗

```bash
# 由 repo root（唔使 cd 入 backend，script 自己處理 import path）
./backend/.venv/bin/python learn/labs/lab03_agent_loop.py

# 全部實驗都係：FakeLLM + 臨時 SQLite → 零 API 費用、零真 data 風險
ls learn/labs/
```

| 實驗 | 示範咩 |
|---|---|
| `lab01_first_llm_call.py` | 一個 LLM call 由頭到尾係咩樣（prompt → schema → 物件） |
| `lab02_structured_output.py` | Pydantic 合約點擋垃圾；schema description 就係提示 |
| `lab03_agent_loop.py` | ⭐ 5 個 node 逐步 + 真 trace ＋ 寫咗咩入 DB |
| `lab04_embeddings.py` | ⭐ embedding：hash 版 vs 真 model 嘅相似度**反轉**（語意 vs 字面） |
| `lab05_rag_retrieval.py` | ingest → 檢索 → 入 prompt；空語料庫會點 |
| `lab06_tools.py` | tool whitelist（安全邊界）＋ model 要求 vs 程式執行 |
| `lab07_guardrail.py` | Deterministic 安全閘；唔靠 model 做安全判斷 |
| `lab08_persist_gate.py` | ⭐ 為咩問產品唔會變成「一日皮膚數據」 |
| `lab09_real_llm.py` | FakeLLM vs 真 LLM（要 `--real`，會用你嘅 key） |
| `lab10_own_eval.py` | ⭐ 跑真 eval、自己加檢查、**驗證個檢查識紅** |

## 前置

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 273 passed
cd ../frontend && npm run ui:check                     # 51 passed（UI gate）
```

兩個都綠，就代表你嘅環境同「出貨狀態」一致 —— 之後你改任何嘢，都可以即刻知有冇搞爛。
