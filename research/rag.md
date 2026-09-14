# RAG audit — is the knowledge base real, and does retrieval reach the model?

Scope: GitHub issue #4, rows **#8 / #9 / #10** of `docs/status-vs-claims.md`, vertical `backend/app/rag/*`,
`backend/corpus/`, `backend/data/corpus/`, `backend/eval/rag_recall.py`, `backend/eval/golden/`.

Method: read every file in the vertical, then **run** things. Read-only on tracked files; the real
`backend/data/skincoach.db` was **copied to `/tmp/ragcopy_skincoach.db` and read from the copy**
(original never opened for write); all re-ingestion went to `tempfile` DBs; no LLM API was called;
no model was downloaded (real-embedder runs are therefore out of reach — see the UNVERIFIABLE items).

Sanity check on the brief itself: the line counts quoted in the issue (`chunking.py 33`, `embeddings.py 86`,
`hybrid.py 34`, `ingest.py 67`, `retrieve.py 14`, `vectorstore.py 93`, `crawler.py 53`) all match the current
files. The brief is accurate about the code it points at.

---

## 0. The measured numbers (everything below is derived from these)

| Quantity | Measured | How |
|---|---|---|
| Committed golden corpus (what eval measures) | **3 files → 4 chunks** | `eval/golden/*.txt` re-ingested |
| Golden chunk lengths | 402, 291, 500, 272 chars | `chunk_text()` on golden files |
| Clean-clone rebuild of the *real* corpus dirs | **22 chunks** | `ingest_corpus.py` dirs, temp DB |
| Production index (`data/skincoach.db`) | **3220 chunks / 218 sources / 384 dims** | `SELECT COUNT(*) FROM chunks` on the copy |
| Production chunk text | avg **2520** chars, max **53172** chars | `AVG/MIN/MAX(LENGTH(text))` |
| Production chunks beyond the model's 512-token window | **1046 / 3220 (32.5%)** (>2048 chars, char/4 heuristic) | bucket query |
| Production chunks containing CJK | **250 / 3220 = 7.8%** (2 of 218 sources) | regex scan |
| Production `section` column populated | **0 / 3220** | `SUM(section<>'')` |
| Production `url`/`title` populated | 3208 / 3220 | `SUM(url<>'')` |
| eval `--fake` semantic baseline | recall@3 **1.000**, MRR **0.900** | `python -m eval.run_eval --fake` |
| eval `--fake` hybrid (runtime path) | recall@3 **1.000**, MRR **1.000** | same run |
| **Random-ranking baseline on the same 4-chunk index** | recall@3 **0.849**, MRR **0.563** | 200k-trial uniform permutation simulation |
| Hybrid candidate pool vs production index | `RECALL_K=80` of 3220 = **2.5%** | `hybrid.py:13` |
| Max keyword boost for the golden `oily` query | **0.0257** (0.18 × 1/7 tokens) | `_tokenize()` on the real index |
| CLI exit code when the runtime RAG path returns **zero** chunks | **0 (green)** | sabotage test, §2 |

---

## 1. `#8` — DRIFT

**Doc claim** (`docs/status-vs-claims.md:24`):
> `| 8 | RAG：PDF→OCR→chunk→embed→sqlite-vec | RAG 真（chunks + cosine）；冇 OCR（pypdf 抽 text）；embedding 存 JSON | (a) | ✅ docs 已改 |`

**Also** `README.md:11` ("文字/PDF 語料 → chunk → embed → SQLite（Python cosine，升級路徑留咗）"),
`README.md:29`, `docs/architecture.md:72-76`, `docs/roadmap.md:24`.

### What is verified (the correction itself is honest)

The original pipeline claim is **gone from the docs**, and the replacement text is accurate:

- **No OCR**: no `pytesseract`/`tesseract`/OCR code anywhere in `app/`; `pyproject.toml:6-22` has no OCR dep.
- **pypdf text extraction**: `app/rag/ingest.py:6` `from pypdf import PdfReader`, `ingest.py:14-16`.
- **JATS XML extraction too** (the row omits this, but it is the 88%-of-corpus path): `ingest.py:19-31`.
- **No sqlite-vec**: `pyproject.toml` has no vector-store dep; the only occurrence of `sqlite-vec` in code is a
  future-tense comment at `app/rag/vectorstore.py:4` ("the upgrade path (sqlite-vec / pgvector) is isolated").
- **JSON embeddings + Python cosine**: `app/models.py:189` `embedding: Mapped[list] = mapped_column(JSON)`,
  `vectorstore.py:28-34` `_cosine()` with `zip()`, `vectorstore.py:76-92` full-table `session.query(Chunk).all()`.
- **`section` metadata claimed but never used**: `chunking.py:3-5` says "Section-aware chunking (heading metadata
  from HTML) is layered in by callers via the `section` argument", but no caller in `app/`, `eval/` or `scripts/`
  ever passes `section=` (`grep -rn "section=" backend/{app,scripts}` → only `ingest.py:47` and `vectorstore.py:67`,
  i.e. the plumbing, never a producer). Consistent with `section` being empty in **0/3220** real chunks.

### Where it drifts — three things the ✅ hides

**(a) The chunker does not chunk ~88% of the corpus.** `app/rag/chunking.py:9`:
```python
_SENT_BOUNDARY = re.compile(r"(?<=[。！？!?；;])")
```
That class contains full-width `。！？；`, and ASCII `!` `?` `;` — **not ASCII `.`**. So English prose is never
split into sentences, and the packer at `chunking.py:22-32` can only break where a "sentence" exceeds
`chunk_size`. Measured on the two real PMC XML files:

```
  split("Acne is common. It affects many people. Treatment works.") -> 1 part
  split("暗瘡好常見。要治療。")                                       -> 3 parts
  data/corpus/PMC10709101.xml: 35139 chars -> 7 chunks, lengths [3748, 121, 5297, 10971, 13606, 570, 1306]
  data/corpus/PMC11031619.xml: 39507 chars -> 3 chunks, lengths [2687, 102, 36878]
```
The result is visible in the production index: **avg 2520 chars/chunk, max 53172 chars**, with
**1046/3220 (32.5%) above ~2048 chars** — while `chunk_size=500` (`chunking.py:12`). Only 1342/3220 (41.7%)
are actually ≤500. The configured chunk size is effectively ignored for every non-CJK source.
Why it matters beyond tidiness: the embedder is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
documented in fastembed's own registry as **"512 input tokens truncation"**
(`.venv/.../fastembed/text/pooled_embedding.py:53`) — so for a 36,878-char chunk only the first ~6% of the text
is embedded, and the remainder is unreachable by semantic search. This is not an edge case: it is the dominant
path, because 2833/3220 chunks (88.0%) come from Europe PMC JATS XML.
`tests/test_rag.py:14-26` cannot catch this: both chunking tests use CJK text ending in `。`.

**(b) The real corpus cannot be rebuilt from the repo, so "the knowledge base" is a build artefact.**
`scripts/ingest_corpus.py:19` scans `./corpus:./data/corpus`. Measured, into a temp DB:
```
  SKIP corpus/sources.txt
  corpus/zh_skincare_basics.txt   ->  2 chunks
  corpus/zh_sources_curated.txt   -> 10 chunks     <-- see (c)
  data/corpus/PMC10709101.xml     ->  7 chunks
  data/corpus/PMC11031619.xml     ->  3 chunks
  TOTAL                             22 chunks      (production DB: 3220)
```
`backend/data/corpus/` (gitignored, `.gitignore:16`) holds **two** XML files today; the production DB holds
chunks from **211** distinct PMC sources plus 7 crawled web sources. `backend/README.md:63` and `AGENTS.md`
still describe `data/corpus/` as the "大 corpus" — it is 10 chunks, 240 KB, and produces 0.3% of the index.
There are **no PDFs anywhere** in the repo (`find backend -iname "*.pdf"` → none), so `extract_text_from_pdf`
(`ingest.py:14-16`) is dead code in practice.

**(c) A URL seed list is ingested as skincare knowledge.** `ingest_corpus.py:30` skips exactly one filename:
```python
if p.name == "sources.txt":  # URL seed list, not content
    continue
```
`corpus/zh_sources_curated.txt` (10,297 B, 192 lines) is the *same kind of file* — a `#`-commented URL list —
and it is ingested as **10 chunks of retrievable "knowledge"**. Sample stored chunk:
```
'# SkinCoach 中文護膚語料 seed（每行一個 URL，# 係註解） # 用途：男性護膚 coach 嘅內部知識庫，中文優先。 ...'
```
Caveat, stated fairly: on the current docker path this file is a large fraction of the shipped index —
`backend/Dockerfile:23` copies only `corpus/` (not the gitignored `data/corpus/`), and
`docker_entrypoint.sh:26-35` ingests when `chunks` is empty. So a `docker compose up --build` deployment
seeds **12 chunks, 10 of which are a URL list** — and `README.md:33`/`#18` advertise "corpus bake".

**Smallest honest correction:** keep the corrected row text, but stop calling the corpus "真" without
qualification. Replace the row's `RAG 真（chunks + cosine）` with something like:
`RAG 存儲真（chunks + JSON + cosine）；但 chunker 只對中日韓標點有效 → 88% 語料（PMC 英文）平均 2520 字/chunk、最大 53172 字，超出 MiniLM 512-token 窗；`data/corpus/` 只有 10 chunks，3220-chunk 生產索引唔可以 clean clone 重建；`zh_sources_curated.txt`（URL list）被當內容 ingest（10 chunks）。`

---

## 2. `#9` — VERIFIED (wiring) / DRIFT (the value it is credited with)

**Doc claim** (`docs/status-vs-claims.md:25`):
> `| 9 | Hybrid retrieval | ✅ **已接線**：tools.search_knowledge 行 rag/hybrid.py（semantic recall + keyword re-rank）；eval recall 行純 retrieve() 做基準 | (a) | ✅ 唔再係 orphan |`

**Wiring — verified exactly as claimed.** Proof by import graph, not by reading:
```python
import app.main  →  app.rag.{chunking,embeddings,hybrid,ingest,retrieve,vectorstore} loaded
```
- `app/agent/tools.py:11` `from ..rag.hybrid import search_hybrid`; `tools.py:70`
  `results = search_hybrid(session, state["user_text"], embedder, top_k=3)`. This is the only runtime caller.
- `eval/rag_recall.py:10` `retriever = retriever or default_retrieve`; `eval/run_eval.py:90` calls
  `evaluate_recall(...)` with no `retriever` (→ plain `retrieve()`), `run_eval.py:91` passes
  `retriever=search_hybrid` for the second measurement. Claim is accurate.
- Note `app/rag/retrieve.py` has **no production caller at all** — it is eval/test-only
  (`grep -rn "retrieve(" app/ eval/ tests/` → `retrieve.py:8` def, `run_eval.py:86` comment, `tests/test_rag.py:35`).

### Is the keyword re-rank meaningful, or a no-op?

On the eval corpus it is the *only* thing producing MRR 1.00 — but the eval corpus makes the other half of
hybrid vacuous. `hybrid.py:13` sets `RECALL_K = 80`; the golden index has **4** chunks, so
`semantic_search(..., top_k=80)` returns **the entire index for every query** (verified: `RECALL_K=80 returned
4 candidates (index size 4)` for all 5 golden queries). The "semantic recall" stage therefore filters nothing,
and hybrid degenerates to "boost-and-sort a 4-item list". Concrete, from the `--fake` run:
```
--- oily: 我塊面好油，點控油？ (expected zh_skincare_basics.txt)
  SEM  #1 cos=0.2242 src=incidecoder.com-salicylic.txt
  SEM  #2 cos=0.2198 src=zh_skincare_basics.txt     <-- the "rank=2" that costs MRR 0.10
  HYB  #1 score=0.2455 src=zh_skincare_basics.txt   <-- +0.0257 = 0.18 × (1/7 query tokens)
```
The recorded MRR gap between the "semantic baseline" (0.90) and "runtime path" (1.00) is a **0.0257 boost
overtaking a 0.0044 cosine difference**, on a corpus of four chunks, one of which is about salicylic acid and
none of which is about oiliness. Worth noting: the golden corpus contains **no chunk about oily skin**, so
`oily → zh_skincare_basics.txt` is a *file-level* label — the "correct" chunk actually retrieved is the
BHA/salicylic one.

**On the production index, measured without a model.** The boost depends only on query text and chunk text,
so I measured its ceiling against all 3220 real chunks:
```
  q='我塊面好油，點控油？'   query tokens=7  per-token=0.02571 | 21/3220 chunks get ANY boost | max boost=0.0257
  q='皮膚乾燥點保濕？'      query tokens=6  per-token=0.03000 | 95/3220 chunks | max boost=0.1200
  q='水楊酸對暗瘡有咩用？'   query tokens=8  per-token=0.02250 |  2/3220 chunks | max boost=0.0675
  q='下巴爆瘡點算？'        query tokens=5  per-token=0.03600 |  1/3220 chunks | max boost=0.0360
  q='點解要每日搽防曬？'     query tokens=7  per-token=0.02571 | 51/3220 chunks | max boost=0.0514
```
So on the real index the whole re-ranker touches **1–95 chunks out of 3220 (0.03%–2.9%)** with at most
+0.18 × (matched query tokens / query tokens). It is a genuine re-ranker, but it is bounded twice over:
it can only reorder **inside the semantic top-80** (2.5% of the index), so **it cannot fix a recall miss** —
a relevant chunk that the embedder ranks 81st is unreachable by keyword boost. Reusing stored 384-dim vectors
as stub queries over 200 random real chunks, hybrid changed the top-3 in **114/200** cases but the **top-1 in
only 1/200** — i.e. it shuffles ranks 2–3, it does not change what gets retrieved. `docs/blog-post.md:88`
("中英混雜 query 會優先浮返中文 chunks") is a claim this evidence does not support.

### The runtime number is not gated — proven, not inferred

`eval/run_eval.py:153-156`:
```python
failed = any(not r["hit"] for r in recall["results"]) or any(not r["passed"] for r in agent_results)
```
Only the *semantic baseline* and the agent scenarios gate the exit code. I patched `search_hybrid` to
`return []` (runtime RAG completely dead) and ran the real entrypoint:
```
## Hybrid（runtime path，同一 golden set）recall: 0% · MRR: 0.00
- oily: FAIL (rank=None)  ... (all 5 FAIL)
-> run_eval --fake exit code with DEAD hybrid path: 0     # CI green
```
The advertised "hybrid recall 100% / MRR 1.00（runtime path）" (`status-vs-claims.md:11`) can regress to 0%
without turning CI red. `eval/agent_eval.py:41`'s `expect_tool` gate is about **invocation**, and
`agent_eval.py:30-33` does record rows — but the reported `search_knowledge=3` in the happy path is not a
quality signal (`run_tool` returns 3 chunk texts; it would also pass with 3 irrelevant ones).

**Smallest honest correction:** keep "已接線" (true), change the value claim to something like:
`Runtime 行 hybrid（tools.search_knowledge → search_hybrid，僅此 caller）；但 eval 量到嘅 100%/1.00 係 4-chunk index 上嘅 re-rank 結果（RECALL_K=80 > index size，semantic 階段空轉）；hybrid 數字冇入 exit-code gate（實測：search_hybrid 回 [] 仍然 exit 0）。`

---

## 3. `#10` — VERIFIED (guard + model) / DRIFT (one parenthetical)

**Doc claim** (`docs/status-vs-claims.md:26`):
> `| 10 | Embedding model env / bge-m3 | ✅ dead config 已刪；code 用 MiniLM-L12-v2（fastembed 預設） | (a) | ✅ |`

**Which model / what dimension — verified against the library, offline.**
`app/rag/embeddings.py:49`: `model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"`.
fastembed is installed at **0.8.0**; its registry entry for that model
(`.venv/lib/python3.13/site-packages/fastembed/text/pooled_embedding.py:50-55`) is:
```
model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", dim=384,
"Text embeddings, Unimodal (text), Multilingual (~50 languages), 512 input tokens truncation"
size_in_GB=0.22
```
So: **384-dim, multilingual, 512-token input cap** — and the production DB agrees: `json_array_length(embedding)`
= **384 for all 3220 rows**. `embeddings.py:41` documents "384 dims" correctly.

**DRIFT:** "（fastembed 預設）" is wrong. `TextEmbedding.__init__`'s default is
`model_name: str = "BAAI/bge-small-en-v1.5"` (`text_embedding.py:81`, registry `dim=384, 0.067 GB`) — an
**English-only** model. The code passes MiniLM *explicitly*; nothing in this repo uses the library default.
This is not pedantry: if a future edit "simplified" the code to rely on the default, Chinese queries would
break silently (same 384 dims, so the dimension guard would not fire).

**Is the 128 vs 384 mismatch really rejected rather than silently prefix-compared? — VERIFIED, and the guard
is load-bearing.** Measured in a temp DB with the real code path:
```
  stored 384-dim -> existing_dim = 384
  add_chunks(128-dim)        -> raised ValueError: "embedding 維度唔一致：DB 現有 384 維，今次想寫 128 維。…"
  search(128-dim query)      -> 0 results   + logged: "search: 跳過 1 條維度唔一致嘅 chunk（query=128 維）…"
  search(384-dim query)      -> 1 result
  _cosine([1,0,0,0],[1,0])   -> 1.0     <-- what would happen WITHOUT the guard
```
Code: `vectorstore.py:37-48` (`existing_dim`), `:51-60` (raise on mixed ingest), `:76-92` (skip + warn on
mismatch). Tests exist: `tests/test_observability.py:199-221`. The `_cosine` prefix hazard is real
(`zip()` at `vectorstore.py:29` returns 1.0 for a truncated prefix) and the guard is what prevents it.
`status-vs-claims.md:43` (#27) states this accurately.

### What actually happens when the real embedder is unavailable (measured consequence)

`embeddings.py:58-75` catches any model-load failure and sets `self._model = False`, then `:77-86` serves
`DeterministicEmbedder()` (128-dim, `embeddings.py:24`) **per call**, with a `logger.warning`. So:
```
  search_hybrid("下巴爆瘡點算？", DeterministicEmbedder(128)) on the real 384-dim index -> 0 chunks
  search(...)                                                                        -> 0 chunks
```
`tools.run_tool` then returns `{"result": []}` (`tools.py:71`), the advise prompt carries
`工具結果：[{"tool":"search_knowledge","result":[]}]` (`prompts.py:74`), and the agent answers with **no
knowledge at all**. Nothing raises, nothing is HTTP-500 — the consult succeeds with an empty knowledge base.
The trace records `tool_rows=0` (`graph.py:215-220`) but there is **no trace field saying "embedder fell back"**;
only a warning goes to the log. `AGENTS.md` ("embedder fallback … 全部要 log + 入 trace") is half true: log yes,
trace no. CI cannot see any of this, because `--fake` uses `DeterministicEmbedder` for **both** ingest and
query (`run_eval.py:41`), so dims always match and the fallback path is never exercised.
Secondary risk I could not rule out offline: fastembed 0.8.0 warns that this model "now uses mean pooling
instead of CLS embedding" (`text_embedding.py:98-110`), so 384-dim vectors written by a pre-0.8.0 ingest are
**not comparable** to 0.8.0 query vectors — and the dimension guard cannot detect that, because both are 384.
`pyproject.toml:20` pins only `fastembed>=0.4`, so which pooling a given environment gets is unpinned.

**Smallest honest correction:** `code 用 MiniLM-L12-v2（`embeddings.py:49` 明示指定；**唔係** fastembed 預設 —— fastembed 0.8.0 預設係英文 BAAI/bge-small-en-v1.5）；384 維、512-token 截斷；fallback 128 維會被 add_chunks／search 擋住，但 runtime 會靜靜變成「檢索 0 條」而唔會 trace。`

---

## 4. Question 4 — **ARTEFACT. `recall@3 = 100% / MRR 0.90` on a 4-chunk golden corpus is not evidence of retrieval quality.**

Plainly: on a 4-chunk index, `top_k=3` returns **75% of the entire corpus**. The metric is measured against a
3-file, 3,719-byte corpus in which two of the five queries point at a file holding **half of all chunks**.

Against a **uniformly random ranking**, on that exact corpus:
```
  oily       random recall@3 = 1.000   random MRR = 0.721
  dry        random recall@3 = 0.750   random MRR = 0.458
  salicylic  random recall@3 = 0.747   random MRR = 0.456
  rosacea    random recall@3 = 0.748   random MRR = 0.457
  sunscreen  random recall@3 = 1.000   random MRR = 0.722
  MEAN       random recall@3 = 0.849   MEAN random MRR = 0.563
  measured   semantic 1.000 / 0.900 ; hybrid 1.000 / 1.000
```
A retriever that **ignores the query entirely** scores **0.85 recall@3 and 0.56 MRR**. The measured numbers are
+0.15 recall and +0.34 MRR over coin-flipping, on 5 queries, with `n=5` so a single query is worth 20 points.
And the whole corpus is 3 hand-written Chinese summaries (`eval/golden/dermnetnz.org-dry-rosacea.txt` is 406
bytes of paraphrased bullet points headed "# …（dermnetnz.org 參考內容）") — not crawled pages — so the eval
does not even test retrieval over the corpus shape that runs in production.

Three structural problems make it unfixable at this scale, independent of the score:
1. **The index is not the index.** Production is 3220 chunks / 218 sources (7.8% CJK); eval is 4 chunks / 3 files.
2. **Labels are file/domain-level, not chunk-level.** `eval/rag_recall.py:19` is `if sc["expected_source"] in s`
   where `s` is `Chunk.source`. For crawled content `source` is the *netloc* (`scripts/crawl_ingest.py:26`
   passes `urlparse(url).netloc`), so a "hit" means "a chunk from the right website" — with 73 dermnetnz chunks
   in the real index, that is a much weaker question than "the right chunk". One `--fake` "rank=1" for `dry` is
   a hit on a 402-byte file that answers about both dry skin *and* rosacea.
3. **The advertised number is not gated** (§2) and, per `docs/eval-report-sample.md:17`, it is published in the
   docs as an achievement — where the sample report is also stale (it omits the hybrid section that
   `run_eval.py:120-125` now always prints).

**The numbers that would make this claim load-bearing:**
- Measure on the **production index scale: N ≥ 3000 chunks** (the 3220-chunk `chunks` table already exists),
  with `k/N ≤ ~0.1%` — i.e. **k=3 against N≥3000**, not k=3 against N=4. Then publish the N.
- **≥ 100 queries with chunk-level ground truth** (chunk id, not domain/filename), sampled across the corpus,
  covering the CJK/English mix that production actually has (7.8% CJK).
- **Publish the trivial baselines alongside**: random ranking and BM25-only. Current baseline to beat is
  **0.849 recall@3 / 0.563 MRR** — if the model does not clearly separate from that, the metric is not measuring retrieval.
- **Gate whatever you advertise**: `search_hybrid` must be part of the exit-code condition (today it can return
  `[]` with CI green), and re-run at least once in **real-embedder mode**. As of this audit that cannot be done
  offline: there is no cached model anywhere in the repo or the default cache
  (`find … -name "*.onnx"` → none; `/var/folders/…/T/fastembed_cache` empty), and `.env` does not set
  `SKINCOACH_EMBEDDER_CACHE_DIR`, so `service.py:36` passes `None` → fastembed's temp dir. A real run would
  download 0.22 GB, which the brief forbids.
- Until then, label the current figure for what it is: a **smoke test that the harness runs**, not a quality claim.
  For scale reference only (a strictly *easier* task, so not a quality claim either), reusing stored 384-dim
  vectors as stub queries against the real 3220-chunk index gives self-retrieval R@1 = 0.95, R@3 = 1.00 —
  which is exactly why self-similarity probes cannot substitute for labelled queries.

---

## 5. Is `rag/crawler.py` genuinely outside the runtime path? — **VERIFIED: yes.**

Proven by import graph rather than by reading: `import app.main` loads
`app.rag.{chunking,embeddings,hybrid,ingest,retrieve,vectorstore}` and **not** `app.rag.crawler`;
`"trafilatura" in sys.modules` is **False** (while `pypdf` is True, via `app/rag/__init__.py:3`).
`app/rag/__init__.py:1-14` does not export the crawler. Its only importers are offline scripts:
`scripts/crawl_ingest.py:15`, `scripts/crawl_zh.py:22`, `scripts/expand_dermnet.py:19` — and
`backend/README.md:108` admits those need `trafilatura`/`playwright`, "pyproject 未列入", so a clean
`pip install -e .` gives you a crawler you cannot import. No test imports it either.
(Note: `trafilatura` *is* present in this venv at 2.2.0 through some other path, but that is environment, not runtime.)

---

## 6. Findings beyond the three rows (all with evidence)

| Finding | Evidence |
|---|---|
| **The production index is 92.2% English-only** — a Chinese-first coach advising in Cantonese, retrieving English PMC abstracts | 250/3220 chunks contain CJK; **only 2 of 218 sources** contain any CJK |
| **99.2% of the Chinese content is one cosmetics press-release page** | `coolsis.cool-style.com.tw` = 248 of the 250 CJK chunks; its URL/title = `…/beauty/makeup/40635`, "VALENTINO BEAUTY奢金鉚釘快閃店…唇膏" — a lipstick pop-up store article, retrievable for acne queries. The other 2 CJK chunks are `zh_skincare_basics.txt` |
| **Top-3 chunk texts can total ~137k chars (~34k tokens) of prompt** | sum of the 3 longest real chunks = 53,172 + 43,778 + 40,458 = **137,408 chars**; `tools.py:71` returns full `c.text` for `top_k=3`, `prompts.py:74` inlines them |
| **`zh_sources_curated.txt` ingested as content** | `ingest_corpus.py:30` skips only `sources.txt`; measured → 10 chunks of URL list |
| **Docker ships a 12-chunk "knowledge base", 10 of them a URL list** | `Dockerfile:23` copies only `corpus/`; `docker_entrypoint.sh:26-35`; measured clean-dir ingest = 2 + 10 |
| **Docker RAG silently absent if the model cannot download** | `docker_entrypoint.sh:31` warns and continues; there is no chunk-count check afterwards |
| **The published sample report is stale vs the current harness** | `docs/eval-report-sample.md:15-27` has no hybrid section; `run_eval.py:120-125` always writes one (current `eval/out/report.md:12-17`) |
| **`roadmap.md:63` still lists the eval as unchecked** while `status-vs-claims.md:11` quotes it as a result | `docs/roadmap.md:63` `- [ ] eval.run_eval --fake PASS（recall 100%、MRR 0.90…）` |
| **JATS extraction duplicates section headings** | measured on both real XMLs: `'Antibiotics'` ×2, `'Oral Medications'` ×2, `'This figure is self-created…'` ×4 (`ingest.py:26-30` matches both `abstract`/`article-title` containers and their inner `p`/`title`). Minor, but it is real duplication in a chunk |
| **Provenance typo in the crawled corpus** | stored url for the incidecoder family is `https://inkeedecoder.com/ingredients/salicylic-acid` ("inkee**d**ecoder") |

---

## 7. Bottom line

| Row | Verdict |
|---|---|
| **#8** | **DRIFT** — the correction (no OCR, pypdf/JATS, JSON + Python cosine, no sqlite-vec) is accurate and the stale claim is gone from all docs. But "RAG 真" overstates: the chunker only splits CJK/`!?;` text, so 88% of the corpus is stored in 2520-char average chunks (max 53k) while the model truncates at 512 tokens; the 3220-chunk index is not reproducible from the repo (22 chunks from the corpus dirs); and a URL seed list is ingested as knowledge. |
| **#9** | **VERIFIED on wiring / DRIFT on claimed value** — `tools.search_knowledge → search_hybrid` and `eval → retrieve()` are exactly as documented. But the 100%/1.00 hybrid figure comes from a 4-chunk index where `RECALL_K=80` makes the semantic half vacuous, the re-rank's whole effect on the real index amounts to ≤+0.026 on 0.03–2.9% of chunks, and the runtime number can go to 0% with CI still green (proven by sabotage test). |
| **#10** | **VERIFIED / minor DRIFT** — model is `paraphrase-multilingual-MiniLM-L12-v2` at 384 dims (registry-confirmed) and the 128-vs-384 mismatch is genuinely refused, not prefix-compared (`add_chunks` raises, `search` skips + warns, tests at `test_observability.py:199-221`). DRIFT: "fastembed 預設" is false (default is English `BAAI/bge-small-en-v1.5`), and the fallback's real consequence — a *successful* consult with an empty knowledge base, logged but not traced — is undocumented. |
| **Q4** | **ARTEFACT.** 4 chunks, `top_k=3` of 4, file-level labels, random baseline 0.849/0.563, `n=5` queries, and the advertised number is outside the CI gate. Load-bearing requires N ≥ ~3000 chunks, ≥100 chunk-labelled queries, published random/BM25 baselines, and gating the runtime path — with one real-embedder run (not possible offline today: no cached model, 0.22 GB download). |
| **Q5** | **VERIFIED** — `crawler.py` is not in the runtime import graph at all (only 3 offline scripts, whose deps are not in `pyproject.toml`). |

## 8. Reproduction

```bash
cd backend
./.venv/bin/python -m eval.run_eval --fake                  # 4 chunks; 100%/0.90 semantic, 100%/1.00 hybrid; exit 0
cp data/skincoach.db /tmp/ragcopy.db                        # read the copy, never the original
sqlite3 /tmp/ragcopy.db "SELECT COUNT(*), json_array_length(embedding) FROM chunks GROUP BY 2;"   # 3220|384
sqlite3 /tmp/ragcopy.db "SELECT CAST(AVG(LENGTH(text)) AS INT), MAX(LENGTH(text)) FROM chunks;"   # 2520|53172
```
Probe scripts used for the numbers above were written under `/tmp/ragaudit/` (`probe.py`…`probe6.py`,
`gateprobe.py`); nothing was written into `backend/app`, `backend/data/corpus`,
`backend/data/skincoach.db` or any tracked file. Running the harness rewrites the **gitignored**
`backend/eval/out/report.md` (restored to the honest `--fake` content after the sabotage test).
`git status --porcelain` shows no tracked file changed by this audit.
