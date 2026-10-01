# §03 Embedding 同 RAG：agent 點樣「查資料」

> 你第三個問題：「embedding 嗰啲喺邊度做？」

## 1. LLM 有兩個大問題，embedding 係其中一個嘅解藥

| 問題 | 解藥 |
|---|---|
| 佢會作故事（hallucination） | **RAG**：先檢索真資料，塞入 prompt，叫佢只可以根據資料答 |
| 佢唔識「搵相似」 | **Embedding**：把文字變成 vector，用距離搵相近嘅嘢 |

RAG = Retrieval Augmented Generation。三個步驟：

```
（事前）文章 → 切 chunk → embed → 存 DB
（查詢）問題 → embed → 搵 cosine 最近嘅 N 個 chunk → 塞入 prompt → LLM 寫答案
```

## 2. Embedding 係咩（用你識嘅嘢理解）

- 一個 vector 就係 `list[float]`，例如 384 個數。
- 「意思相近」→ 方向相近。所以比較用 **cosine similarity**（1 = 一樣方向、0 = 無關）。
- 大細（長度）唔重要，方向先重要。
- **維度係型別嘅一部分**：384 維同 128 維唔可以比（見 §4 陷阱）。

跑 `lab04_embeddings.py` —— 呢個 lab 有個驚喜：

| 句子對 | hash embedder（128 維） | 真 model（384 維） |
|---|---|---|
| 暗瘡 ↔ 出油（應該似） | **0.067**（唔似） | **0.738** ✅ |
| 暗瘡 ↔ 防曬（應該冇咁似） | **0.286**（最似！） | 0.220 |
| 火鍋 ↔ 防曬（應該最唔似） | 0.105 | **0.033** ✅ |

⭐ **反轉咗**：因為 `DeterministicEmbedder` 只係「字元 bigram 掟入 hash 桶」，
量到嘅係**字面重疊**，唔係語意。真 MiniLM 先識「暗瘡同出油係同一件事」。

## 3. Codebase 入面：embedding 喺邊

| 位置 | 做咩 |
|---|---|
| `app/rag/embeddings.py:17` `class Embedder(Protocol)` | 介面（同 LLM adapter 一樣嘅思路） |
| `app/rag/embeddings.py:21` `DeterministicEmbedder` | 128 維 hash（教學／test 用） |
| `app/rag/embeddings.py:38` `FastembedEmbedder` | **384 維真 model**（multilingual-MiniLM） |
| `app/rag/chunking.py:20` `chunk_text(text, 500, 80)` | 切 chunk（500 字、重疊 80） |
| `app/rag/ingest.py:34` `ingest_text(...)` | 切 + embed + 寫入 `chunks` table |
| `app/rag/vectorstore.py:51` `add_chunks(...)` | 寫入（會檢查維度一致） |
| `app/rag/vectorstore.py:76` `search(...)` | 讀出全部 chunk、計 cosine、排序 |
| `app/rag/vectorstore.py:28` `_cosine(a, b)` | 就係你 lab04 自己寫嗰條公式 |
| `app/rag/hybrid.py:25` `search_hybrid(...)` | 語意 + 關鍵詞 re-rank（**runtime 用呢個**） |
| `app/rag/retrieve.py:8` `retrieve(...)` | 純語意（eval 用嘅基準） |

⚠️ 留意 `search()` 係「讀晒所有 chunk 落 Python 再算 cosine」—— 對呢個規模（幾千 chunk）
完全夠快，但**唔係** vector database。想學 production 級，就係換成 pgvector／Qdrant 呢類。

## 4. 三個真實陷阱

### 陷阱 A：維度唔一致（靜靜出錯）

384 維嘅 chunk 撞 128 維嘅 query，`_cosine` 用 `zip()` 只會比前 128 個數
→ **分數完全冇意義但唔報錯**。防禦：
- `add_chunks` 見到維度唔同會 raise
- `search` 會跳過維度唔夾嘅 chunk 並 log warning
- 所以一定要設 `FASTEMBED_CACHE_PATH`（唔係 fastembed 會 fallback 去 hash 版）

### 陷阱 B：hybrid 唔可以拆走

runtime 用 `search_hybrid`：語意分 + `BOOST × 關鍵詞重疊`。
中文短查詢（「下巴生瘡」）語意分有時分唔開，關鍵詞 re-rank 幫到手。
eval 嘅 recall 用純 `retrieve()` 做基準 —— **兩個都要留**（`AGENTS.md` 有明文警告）。

### 陷阱 C：語料庫空 = RAG 等於冇

新安裝嘅 app，`chunks` table 係空嘅。跑 `lab05` 步驟 5 你會見到檢索回 `[]`。
所以 `scripts/ingest_corpus.py` 一定要跑過。而且 trace 會誠實顯示 `rows=0`
（唔會扮有料）。

## 5. 「引文」規矩：呢個 repo 特別嚴嘅位

因為係健康相關產品，`ingredients.py`（成份字典）同 `guide.py`（指南）嘅每個功效主張
都要有 `corpus="source :: title"` 引文，而 `tests/test_ingredients.py` 會**對真 DB 逐條驗**。

- 唔可以手寫成份名（連中文名都唔可以）——咁就係憑空造事實
- 引文要抄到完全一樣（連尾句號、連 non-breaking space）
- 冇 corpus 來源嘅建議，要**明文標明「app 建議」**，唔可以當文獻結論

📌 呢個係 harness 思維延伸到「知識」層：**唔准 LLM 自由生成事實。**

## 6. 本章練習

1. 跑 `lab04_embeddings.py`，然後改 `TEXTS` 加入你自己嘅句子，睇兩個矩陣點變。
2. 跑 `lab05_rag_retrieval.py`，將 `KNOWLEDGE` 改成你寫嘅三篇，睇檢索名次。
3. 進階：跑真 embedder
   ```bash
   cd backend
   FASTEMBED_CACHE_PATH=./data/.fastembed-cache ./.venv/bin/python -m eval.run_eval --fake
   ```
   （eval 會用 golden corpus 計 recall@3 同 MRR）

## 本章重點

1. Embedding = 文字變 vector；cosine 比方向；維度係型別嘅一部分。
2. RAG = 先檢索、後生成；檢索質素 = embedding 質素。
3. 三個陷阱：維度唔夾、拆走 hybrid、語料庫空。知識要有引文。
