# §08 詞彙表

> 用廣東話解釋，右邊寫「喺呢個 repo 邊度見到」。

## LLM 基本

| 詞 | 解釋 | 喺邊 |
|---|---|---|
| **LLM** | 大型語言模型：預測下一個 token 嘅神經網絡 | `llm.py` |
| **Token** | 模型處理文字嘅單位（中文字大約 1 字 1–2 token） | 你睇唔到，但影響成本 |
| **Prompt** | 你送俾模型嘅文字（system + user） | `prompts.py` |
| **System prompt** | 「你係邊個、要點做」嘅指示 | `ANALYZE_SYSTEM` / `ADVISE_SYSTEM` |
| **Temperature** | 隨機度。0 = 盡量穩定；越高越creative | （呢個 repo 唔特別設，用預設） |
| **Context window** | 一次可以塞幾多 token | 影響你塞幾多檢索結果 |
| **Hallucination** | 模型作故事（聽落好合理但錯） | 用 RAG + 引文規矩對抗 |
| **Inference** | 叫模型跑一次（相對「訓練」） | 每次 consult 2 次 |
| **Structured output** | 強制模型輸出符合 JSON schema | `with_structured_output(schema)` |

## Agent 相關

| 詞 | 解釋 | 喺邊 |
|---|---|---|
| **Agent** | LLM ＋ 可以叫工具嘅 loop | `graph.py` |
| **Tool / Function call** | 模型「要求」程式做嘢（唔係自己做） | `tools.py`（whitelist） |
| **Whitelist** | 只准用呢幾個工具 —— 安全邊界 | `tools.py:13` |
| **State** | 流程中傳遞嘅資料袋 | `state.py:21` |
| **Node** | 流程中嘅一站 | `graph.py` 5 個 |
| **Graph / State machine** | 用 node + edge 描述流程 | LangGraph `StateGraph` |
| **Trace** | 每站做咗咩嘅紀錄 | `state["trace"]`、`runs.jsonl` |
| **Guardrail** | 唔靠 model 嘅安全檢查 | `guardrails.py` |
| **Deterministic core** | 用普通 code 做判斷嘅部分 | `attributes/memory/guardrails/…` |
| **Harness** | 包住 LLM 嘅所有周邊工程 | §01 |

## RAG 相關

| 詞 | 解釋 | 喺邊 |
|---|---|---|
| **Embedding** | 文字 → vector（一串數） | `rag/embeddings.py` |
| **Vector / 維度** | 例如 384 個浮點數 | `FastembedEmbedder` |
| **Cosine similarity** | 比兩個 vector 方向嘅相似度（1 = 一樣） | `vectorstore._cosine` |
| **Chunk** | 文章切出嚟嘅一段 | `chunking.py` |
| **Chunking / overlap** | 切段同重疊（避免切斷句子） | 500 字 / 80 字重疊 |
| **Ingest** | 文章 → chunk → embed → 入 DB | `ingest.py` |
| **Retrieval** | 用 query 搵最相似嘅 chunk | `retrieve.py` / `hybrid.py` |
| **Hybrid search** | 語意 + 關鍵詞 re-rank | `search_hybrid`（runtime 用） |
| **Recall@k / MRR** | 檢索質素指標 | `eval/rag_recall.py` |
| **Corpus** | 語料庫（呢個 repo 係護膚文獻） | `data/corpus/`、`eval/golden/` |
| **Citation** | 引文（每句主張要有出處） | `guide.py`、`ingredients.py` |

## 呢個 repo 特有

| 詞 | 解釋 | 喺邊 |
|---|---|---|
| **Entry** | 每日結構化讀數（data truth） | `models.py` |
| **ChatMessage** | 對話氣泡（display truth） | `models.py` |
| **Insight / Memory** | 長期記憶（帶 confidence／expiry） | `memory.py` |
| **Attributes** | 六個固定指標 × 0–3 | `attributes.py` |
| **vision_reason** | 今次有冇真係睇到相 | trace |
| **consent / cloud_analysis** | 用戶同意相片上雲未 | `service.run_consult` |
| **first_checkin** | 呢個對話未有 Entry | `graph.tools` |
| **detected_events** | AI 抽出嘅自報事件（等用戶確認） | `Advice.detected_events` |
| **FakeLLM** | 假 adapter（測試／教學） | `llm.py:35` |
| **Eval** | 比 unit test 更似真嘅檢查層 | `eval/` |
| **Gate** | 每次改嘢都要跑嘅自動檢查 | pytest／eval／ui:check |
