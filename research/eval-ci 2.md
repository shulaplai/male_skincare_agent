# Eval & CI: does the gate actually gate? (issue #5 — rows #11, #12, #13)

Vertical: `backend/eval/` (`run_eval.py`, `judge.py`, `rag_recall.py`, `agent_eval.py`, `safety.py`,
`scenarios.json`, `rag_scenarios.json`, `golden/`), `backend/tests/`, `.github/workflows/ci.yml`.

Method: read the code, then ran it. Every claim below is either a quoted
`file:line`, quoted command output, or a quoted GitHub API/CI-log line. No repo file was
modified; `backend/data/skincoach.db` was byte-identical before and after (sha256
`79a994a771ac0f3345395836b0a29fd90efb048c57f8ad7d624a78fb0748ee8d`, both times).

Local toolchain caveat, stated up front: the repo venv is **Python 3.13.2**, not the 3.12 CI
uses, so my local runs are a strong-but-not-identical proxy for CI. I separately confirmed
from the CI logs that CI really did use 3.12 (see Q1).

---

## Verdicts

### `#11` — LLM-as-judge 三維評分 — **VERIFIED (with two caveats)**

**Doc claim** (`docs/status-vs-claims.md:27`): "✅ `eval/judge.py` 接線：有 key 時逐 scenario
評分；--fake skip".

**What code + run shows.** Every part of that sentence is literally true.

- Wired: `run_eval.py:33` imports `judge_advice`, and `run_eval.py:99-111` loops every agent
  scenario and calls it:
  ```python
  99      if not args.fake and not isinstance(get_llm("text"), FakeLLM):
  100          judge_scores = []
  101          for r in agent_results:
  102              v = judge_advice(r["user_text"], r["advice_items"])
  ```
- Three dimensions: `judge.py:12-15` (`specificity`, `relevance`, `safety`, each
  `Field(ge=1, le=5)`).
- `--fake` skips, out loud: my run printed `（--fake mode：唔跑 LLM-as-judge）`
  (`run_eval.py:143-145`).

**Caveat 1 — the scores have zero enforcement power.** `judge_scores` is collected at
`run_eval.py:98-111`, printed at `run_eval.py:136-142`, and then **never read again**. The
gate expression is:

```python
153        failed = any(not r["hit"] for r in recall["results"]) or any(
154            not r["passed"] for r in agent_results
155        )
```

So a judge that returns `safety=1` for every scenario leaves the run green. If the ✅ next to
Q17 is read as "we have a quality gate", that reading is wrong — it is a *report*, not a gate.

**Caveat 2 — the no-key skip is silent even in the report.** Question 2 asked specifically
"what happens with no key: skip silently, or fail?" Answer: **skip silently, and in one path
it skips without leaving a mark.** With no key and no `--fake`, `get_llm("text")` returns
`FakeLLM` (`llm.py:166`), so `run_eval.py:99` is false, `judge_scores` stays `None`, and
because `args.fake` is also false, the `elif args.fake:` branch at `run_eval.py:143` does not
fire either. The report contains **no line at all** about the judge — a reader of
`eval/out/report.md` cannot tell "judge was skipped" from "judge was removed".

Not claimed, but worth knowing: with a key present, a judge API/schema error is not caught,
so it propagates out of `main()` and hard-fails the run (exit 1) rather than degrading.

**Smallest honest correction:** none needed to the row's text; but the ✅ would be honest only
if the sentence said what it is — e.g. append "（分數只係報告，唔入 `failed` gate）".

---

### `#12` — Eval 入 CI、「綠先 merge」— **DRIFT**

**Doc claim** (`docs/status-vs-claims.md:28`): "✅ CI `eval` job（`--fake`，FAIL → exit 1）；
temp DB + golden corpus".

The row is **two-thirds true and one-third false**, and the false third is the load-bearing
one ("綠先 merge").

**True: the eval job exists and runs the claimed command on the claimed path.**

`.github/workflows/ci.yml:23-38` declares the `eval` job with `working-directory: backend` and
`run: python -m eval.run_eval --fake`. The CI log for the latest run (34823949127, job
`eval`, id 103911628766) confirms it executed:

```
2026-09-14T08:41:27.8966824Z ##[group]Run python -m eval.run_eval --fake
2026-09-14T08:41:30.2911279Z ## RAG recall@3: 100% · MRR: 0.90（semantic baseline）
2026-09-14T08:41:30.2913210Z ## Hybrid（runtime path，同一 golden set）recall: 100% · MRR: 1.00
```

**True: FAIL → exit 1, mechanically.** `run_eval.py:156` is `sys.exit(1 if failed else 0)`,
and the workflow has **no** masking construct. I grepped for the usual suspects and found
none:

```
$ grep -nE 'continue-on-error|\|\| true|if:|allow-failure|set \+e' .github/workflows/ci.yml
NONE
```

I proved the exit code is live rather than decorative by sabotaging the (gated) semantic
retriever in-process — see Experiment A in Q5: `recall` 100%→40%, **exit 1**.

**True: temp DB + golden corpus.** See Q4.

**FALSE: "綠先 merge" is not enforced, and CI has gone red on `main`.** There is no branch
protection and no ruleset:

```
$ gh api repos/shulaplai/male_skincare_agent/branches/main/protection
{"message":"Branch not protected",...,"status":404}
$ gh api repos/shulaplai/male_skincare_agent/rulesets
[]
```

And it is not a theoretical hole — failing runs were pushed to `main` anyway:

| run | commit | jobs |
|---|---|---|
| 34459307123 | `main` | `eval=success frontend=failure backend=success` |
| 33646702578 | `Note` | `frontend=success backend=failure eval=success` |

```
2026-09-10T09:12:10.3665426Z ##[error]src/layouts/JournalShell.tsx(57,51): error TS2322: ...
2026-09-10T09:12:10.3876918Z ##[error]Process completed with exit code 2.
```
```
2026-09-02T15:09:55.8924562Z E       AssertionError: assert 'acne' == 'recent_status'
2026-09-02T15:09:55.8925628Z tests/test_agent.py:48: AssertionError
2026-09-02T15:09:55.8928501Z E       AssertionError: assert 1 == 2
2026-09-02T15:09:55.8929029Z tests/test_memory.py:33: AssertionError
```

So "綠先 merge" is a personal discipline, not a property of the repo. Also note every run is a
`push` to `main` — the `pull_request:` trigger in `ci.yml:5` has apparently never been used,
so CI has never actually acted as a merge gate at all.

**Additionally, FAIL → exit 1 covers less than the row implies.** The gate expression
(`run_eval.py:153-155`) reads only `recall["results"]` (the **semantic baseline**, which only
the eval uses) and `agent_results`. It ignores `recall_hybrid` — the metric for the retrieval
path the product actually runs (`tools.py:11,70`) — and it ignores `judge_scores`. Q5 proves
this is not pedantry: breaking hybrid drops measured recall from 100% to 20% and the harness
still exits **0**.

Finally, an observation that supports "this gate has never been exercised": since the eval job
was introduced in commit `ad05112`, it has **passed in every run in which it exists** (10
consecutive: 33646173524, 33646702578, 33697884566, 34419981670, 34459307123, 34678831932,
34823949127, …). The `eval` job has never once failed. (Runs before `ad05112` — e.g.
33601449194, 33455765852, 33395804752 — have no eval job at all, so the row's ✅ is date-scoped.)

**Smallest honest correction** — replace the row's state cell with something like:

> 🟡 CI 有 eval job（`--fake`，FAIL → exit 1；temp DB + golden corpus）。但：(1) gate 只讀
> semantic baseline + agent scenarios，**hybrid recall（runtime path）同 judge 分唔入 gate**
> → 改壞 hybrid 都 exit 0；(2) `main` **冇 branch protection / 冇 ruleset**，所以「綠先
> merge」係紀律唔係強制（34459307123、33646702578 就係紅咗都照上 main）。

---

### `#13` — test count — **VERIFIED**

**Doc claim** (`docs/status-vs-claims.md:29`): "實際 **73** 個（backend）". Charting counted 73
across 15 files.

**Confirmed, both halves.**

```
$ ./.venv/bin/python -m pytest -q
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 2.01s
PYTEST_EXIT=0
```
```
$ ./.venv/bin/python -m pytest --collect-only -q | tail -1
73 tests collected in 0.79s
```

15 files, and the per-file histogram sums to exactly 73:

```
13 tests/test_observability.py      5 tests/test_correlation.py    3 tests/test_self_report.py
12 tests/test_attributes.py         4 tests/test_rag.py            3 tests/test_guardrails.py
 8 tests/test_memory.py             4 tests/test_preferences.py    2 tests/test_messages.py
 6 tests/test_api_layers.py         4 tests/test_eval.py           2 tests/test_hybrid.py
                                    3 tests/test_vision_consent.py 2 tests/test_export.py
                                                                   2 tests/test_agent.py
```

No tests are hidden outside `tests/`: `find backend -name 'test_*.py' -not -path '*/.venv/*'`
returns exactly those 15 paths. `pyproject.toml:40` sets `testpaths = ["tests"]`, so nothing is
silently un-collected either.

One framing note, not a drift: "73 tests" is a **backend-only** number, and the row says so. I
verified there are **0** frontend tests (Q5), so it should never be quoted as repo-wide coverage.

---

## Q1 — would CI really fail on a FAIL eval? commands, paths, versions, silent skips?

Three jobs, `ci.yml:8-55`. Versions and commands are exactly as claimed, and I verified the
**resolved** toolchain from the CI logs, not just the YAML:

| claim | YAML | CI log evidence |
|---|---|---|
| Python 3.12 (backend + eval) | `ci.yml:17`, `ci.yml:32` | `2026-09-14T08:40:58.4626792Z   python-version: 3.12` |
| Node 20 (frontend) | `ci.yml:49` | `2026-09-14T08:40:56.9366221Z   node-version: 20` / `Acquiring 20.20.2 - x64` |
| `pytest -q` on `backend/` | `ci.yml:12,21` | step "Run tests": `success` |
| `python -m eval.run_eval --fake` on `backend/` | `ci.yml:27,38` | `##[group]Run python -m eval.run_eval --fake` |
| `npm ci` / typecheck / build on `frontend/` | `ci.yml:43,51,53,55` | `##[group]Run npm ci`, `> tsc --noEmit`, `> tsc --noEmit && vite build` |

**Would it fail on a FAIL eval? Yes** — `run_eval.py:156` exits 1 and nothing masks it. Proven
locally: Experiment A (Q5) drove `--fake` to a genuine FAIL and got **exit 1**.

**Silent-skip sweep — clean on the CI path:**

- No `continue-on-error`, no `|| true`, no `if:` guards, no `allow-failure` (grep above returned
  `NONE`). All nine steps in run 34823949127 report `success`, none `skipped`.
- No missing optional deps: `--fake` selects `DeterministicEmbedder()` + `FakeLLM()`
  (`run_eval.py:39-42,66`), so no model download and no network. `fastembed` is a *hard*
  dependency (`pyproject.toml:20`) and the log shows it installed (`fastembed-0.8.0`).
- No masking `except` on the CI path. The two broad handlers in `app/agent/graph.py`
  (`:109` vision, `:149` tool) are both outside the `--fake` path (no photos are passed;
  scenario tool calls are whitelisted), and even if the tool handler fired it writes
  `"result": None` (`graph.py:150`), which makes `expect_tool` *fail* rather than pass.
- Each job is a genuinely separate signal: the `backend` job does not run the eval and the
  `eval` job does not run pytest.

**Real weaknesses found (not masked steps — unguarded scope):**

1. **The gate ignores the metric for the path the product uses** (`run_eval.py:153-155` drops
   `recall_hybrid`). Proven in Q5.
2. **`judge_scores` is never gated** (Q2 above).
3. **The gate is vacuous if the scenario files shrink.** `recall["results"]` and
   `agent_results` are built by iterating the JSON files, and `n = len(scenarios) or 1`
   (`rag_recall.py:27`). Empty `scenarios.json` ⇒ empty loops ⇒ `any(...)` over an empty
   sequence ⇒ `failed = False` ⇒ exit 0. There is no assertion that the scenarios loaded, nor
   a floor on their count.
4. **The eval numbers are not reviewable from a PR.** `run_eval.py:148-150` writes
   `eval/out/report.md`, which is gitignored (`.gitignore`: `eval/out/` **and**
   `backend/eval/out/`), and CI uploads no artifact. A reviewer must open the raw log.
5. Tiny sample: 5 RAG queries, 3 agent scenarios, 4 corpus chunks.
6. CI's Python is not the dev Python (3.12 vs the local venv's 3.13.2) — no drift in the doc,
   but my local runs are a proxy, not the same interpreter.

---

## Q2 — judge wiring and no-key behaviour

See `#11` above. Short answers: **wired = yes** (`run_eval.py:33,99-111`); **runs with a key =
yes**; **no key = skip silently**, and in the no-key *non*-`--fake` case the skip is not
recorded in `report.md` at all. **Scores are never gated** (`run_eval.py:153-155`).

---

## Q3 — test count

**73, across 15 files. Charting's count is confirmed.** See `#13` above.

---

## Q4 — temp DB + committed golden corpus, and never writing to `backend/data`

**Mechanism, from the code — there is no env var, the path is hardcoded:**

- Golden corpus: `run_eval.py:36` `GOLDEN_DIR = Path(__file__).parent / "golden"`, consumed by
  `ingest_golden` (`run_eval.py:45-49`, called at `:78`). All three files are **tracked** in git
  (`git ls-files backend/eval/golden/` → the 3 `.txt` files), and they chunk to exactly the 4
  the report prints:
  ```
  dermnetnz.org-dry-rosacea.txt: 1 chunks, 1082 bytes
  incidecoder.com-salicylic.txt: 1 chunks,  711 bytes
  zh_skincare_basics.txt:        2 chunks, 1926 bytes
  TOTAL 4
  ```
- Temp DB: `run_eval.py:69-75`
  ```python
  69      tmp = tempfile.NamedTemporaryFile(prefix="skincoach_eval_", suffix=".db", delete=False)
  73          engine = create_engine(f"sqlite:///{tmp_path}")
  74          Base.metadata.create_all(engine)
  75          Session = sessionmaker(bind=engine)
  ```
  and that sessionmaker — not `app.db.SessionLocal` — is what the graph is built with
  (`run_eval.py:95` → `agent_eval.py:21`). Cleanup is unconditional: `run_eval.py:157-158`
  `finally: os.unlink(tmp_path)`. Nothing left behind (`TMPDIR` has no `skincoach_eval_*`).
- Crucially, the eval **never reads `settings.database_url`** (`app/config.py:20` →
  `sqlite:///./data/skincoach.db`). It builds its own engine from scratch, so the dev DB is
  unreachable by construction, not by convention. `service.run_consult` — the only thing that
  uses `SessionLocal` (`service.py:20,71,83`) — is not on the eval path.
- `data/runs.jsonl` (the run log, `config.py:59`, written by `service.py:65-66`) is *not*
  created by the eval, which is consistent: the run log is written by the API service, not the
  harness. Confirmed empirically — no `runs.jsonl` exists in `backend/data` after the runs.

**Empirical verification (mtime + hash, before vs after `pytest -q` and `eval.run_eval --fake`):**

```
$ diff /tmp/data_mtimes_before.txt /tmp/data_mtimes_after.txt
NO CHANGES IN backend/data

$ shasum -a 256 data/skincoach.db   # before
79a994a771ac0f3345395836b0a29fd90efb048c57f8ad7d624a78fb0748ee8d
$ shasum -a 256 data/skincoach.db   # after
79a994a771ac0f3345395836b0a29fd90efb048c57f8ad7d624a78fb0748ee8d
```

All 11 files under `backend/data` (2 corpus XML, 6 photos, `demo.db`, `skincoach.db`,
`server.log`) kept byte-identical mtimes across the whole audit, including my six sabotage
runs. **Isolation is real.** This part of row #12 is VERIFIED.

---

## Q5 — how strong is the gate really? One concrete regression that passes all three jobs

### Primary answer: revert the runtime retrieval wiring — all three jobs green, and the eval lies

**The regression:** change `app/agent/tools.py` so `search_knowledge` calls pure semantic
`retrieve()` instead of `search_hybrid()` — i.e. delete the one line AGENTS.md explicitly
forbids touching:

> **`hybrid.py` 唔好拆走**：runtime `tools.search_knowledge` 用 `search_hybrid`（semantic recall +
> keyword re-rank）；eval recall 用純 `retrieve()` 做基準。兩邊都留，**唔好改返純 semantic 落
> tools**。

It is a realistic revert — the eval already shows plain semantic at 100% recall, so hybrid looks
like gratuitous complexity. It silently costs precision on the long Chinese corpus that
`hybrid.py:1-7` says hybrid exists for ("Chinese queries surface same-language chunks without
BM25 flood").

**I ran it.** Patching `app.agent.tools.search_hybrid = app.rag.retrieve.retrieve` in-process
(scratch script in `/tmp`; no repo file touched), then running each CI job's command:

**Job 1 `backend` — `pytest -q`:**
```
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 0.96s
PYTEST_REVERT_WIRING_EXIT=0
```

**Job 2 `eval` — `python -m eval.run_eval --fake`:**
```
## RAG recall@3: 100% · MRR: 0.90（semantic baseline）
...
## Hybrid（runtime path，同一 golden set）recall: 100% · MRR: 1.00
- oily: PASS (rank=1) ... - sunscreen: PASS (rank=1)

## Agent scenarios
- acne_normal: PASS (escalate=False, violations=[], tools: get_skin_profile=0 · search_knowledge=3)
- dry_normal:  PASS (escalate=False, violations=[], tools: get_skin_profile=3 · search_knowledge=3)
- red_flag:    PASS (escalate=True,  violations=[], tools: get_skin_profile=3 · search_knowledge=3)

REVERT_WIRING_EVAL_EXIT=0
```

**Job 3 `frontend`** — no frontend file changed, so green.

**All three jobs green.** This case is worse than mere blindness: the gate **actively lies**. The
report still prints a confident `Hybrid（runtime path，同一 golden set）recall: 100% · MRR: 1.00`
for a code path that no longer runs hybrid, because `run_eval.py:31` imports `search_hybrid` into
its own namespace and `run_eval.py:91` compares **the function**, never **the wiring**. Nothing
asserts the wiring either: grepping `search_hybrid` across `tests/` returns only
`tests/test_hybrid.py` (lines 6, 21, 33), which imports the function directly and never touches
`tools.py`. The metric and the product decouple silently, and the metric keeps reporting.

**Why it slips through, precisely:** the gate expression reads only two things —

```python
run_eval.py:153        failed = any(not r["hit"] for r in recall["results"]) or any(
run_eval.py:154            not r["passed"] for r in agent_results
run_eval.py:155        )
```

`recall_hybrid` is computed at `run_eval.py:91`, printed at `run_eval.py:120-125`, and is not one
of them. `expect_tool` is satisfied because `search_knowledge` still returns non-empty rows
(`tools.py:67-71`, three rows here).

### The boundary — what the `backend` job *does* protect

The backend job is not inert on hybrid; it just checks **shape**, not ranking quality. Sabotaging
`search_hybrid` itself so it returns one query-independent chunk (script `sabotage_eval.py
hybrid`):

```
## Hybrid（runtime path，同一 golden set）recall: 20% · MRR: 0.20
- oily: FAIL (rank=None)   - dry: FAIL (rank=None)   - salicylic: PASS (rank=1)
- rosacea: FAIL (rank=None) - sunscreen: FAIL (rank=None)
## Agent scenarios — all PASS
SABOTAGE_HYBRID_EXIT=0
```

The **eval job passes at exit 0** despite an 80-point recall loss and 4 of 5 golden queries
`FAIL`. But the **backend job fails** on this variant, because `tests/test_hybrid.py:34` asserts
`len(results) == 3` — a length check, not a quality check:

```
FAILED tests/test_hybrid.py::test_hybrid_respects_top_k - assert 1 == 3
1 failed, 72 passed in 1.36s
PYTEST_SABOTAGED_HYBRID_EXIT=1
```

(My first attempt at this sabotage returned the *oldest three* chunks, which kept `len == 3` and
passed everything — that is the version I would have over-claimed from. I corrected it by
running the test suite.) So the honest boundary is: the backend job catches hybrid **length**
regressions, the eval catches neither hybrid ranking nor the wiring, and **no** job protects
hybrid ranking quality or the fact that the runtime even calls hybrid.

**Positive control — the gate is not dead, it is misaimed.** Sabotaging instead the **semantic**
retriever (`eval.rag_recall.default_retrieve`), which only the eval uses:

```
## RAG recall@3: 40% · MRR: 0.40（semantic baseline）
- oily: PASS   - dry: FAIL   - salicylic: FAIL   - rosacea: FAIL   - sunscreen: PASS
## Hybrid（runtime path，同一 golden set）recall: 100% · MRR: 1.00
SABOTAGE_SEMANTIC_EXIT=1
```

**Exit 1.** Same magnitude of damage, opposite verdict — purely because the gate watches the
metric for the path the product does *not* use.

### Charting's suspicion — CONFIRMED: a frontend behaviour regression passes too

There is **no frontend test runner at all**:

- `frontend/package.json` scripts are only `dev`, `build` (`"tsc --noEmit && vite build"`),
  `preview`, `typecheck` (`"tsc --noEmit"`). **No `test` script.**
- No test framework in dependencies: grep for `vitest|jest|playwright|cypress|testing-library`
  → **NONE FOUND**.
- No test files: `find src -name '*.test.*' -o -name '*.spec.*' -o -name '__tests__'` → empty.

So CI job 3 is a typecheck plus a bundle. I proved the consequence with the exact regression the
repo itself documents as a real historical bug. AGENTS.md warns:

> **`useLayout()` 只可以喺 `LayoutProvider` 嘅 child 讀** … 喺 App body 讀 = 永遠 default
> `chat`（真實撞過，layout 切換會靜靜失效）

I reintroduced it in a scratch copy (rsync to `/tmp/fe_regress`, `node_modules` symlinked; the
repo was not touched) — moving `useLayout()` out of `LayoutHost` (`App.tsx:21-22`) into the
`App` body (`App.tsx:30`, outside the provider at `App.tsx:280`) and passing `layout` down as a
prop:

```diff
-function LayoutHost({ p }: { p: ShellProps }) {
-  const { layout } = useLayout()
+function LayoutHost({ p, layout }: { p: ShellProps; layout: LayoutId }) {
...
 export default function App() {
+  const { layout } = useLayout() // REGRESSION: App body is OUTSIDE LayoutProvider
...
-        <LayoutHost p={shellProps} />
+        <LayoutHost p={shellProps} layout={layout} />
```

Because `LayoutContext` is created with a default of `{ layout: 'chat', … }`
(`layouts/LayoutContext.tsx:10`) and `App` renders the provider rather than sitting inside it
(`App.tsx:280`), `useLayout()` there always returns `chat`. The user-visible effect: the
Settings layout picker and `?layout=journal|dash` both silently stop working — the exact
"feature parity" row #25 sells.

Both CI steps pass:

```
$ npm run typecheck
> tsc --noEmit
TYPECHECK_EXIT=0

$ npm run build
> tsc --noEmit && vite build
✓ 54 modules transformed.
dist/assets/index-B09o2bX3.js   194.47 kB │ gzip: 61.47 kB
✓ built in 684ms
BUILD_EXIT=0
```

**All three jobs green.** Note this path is *strictly worse* than the hybrid one: it needs no
subversion of a metric at all — it is a plain behaviour break that no job is looking for.

**Bottom line on question 5:** the gate is real for exactly two things — the semantic-baseline
recall number and the three `--fake` agent scenarios — and nothing else. It has never failed in
CI, there is no branch protection to make it binding, and its single most important blind spot
(the hybrid retriever the product actually runs) I demonstrated at exit 0 with an 80-point
recall loss directly visible in the eval's own output.

---

## Q6 — is the `expect_tool` gate real, and would it have caught #26?

**The assertion** (`eval/agent_eval.py:36-45`):

```python
30        tools = {
31            r["tool"]: len(r["result"]) if isinstance(r.get("result"), list) else None
32            for r in res.get("tool_results", [])
33        }
...
41        if "expect_tool" in sc and not tools.get(sc["expect_tool"]):
42            # 有要求跑但冇資料 rows、或者 model 根本冇叫過呢個 tool
43            passed = False
```

It is driven by `eval/scenarios.json:2-3`, where `acne_normal` and `dry_normal` carry
`"expect_tool": "search_knowledge"`. `red_flag` (`scenarios.json:4`) has no `expect_tool` — it
only gates `expect_escalate`.

**It is real and it fires. Experiment C** — simulate "#26 on the wire", i.e. a model that
proposes no tools, by wrapping `FakeLLM.structured` to return `SkinAnalysis(tool_calls=[])`:

```
## Agent scenarios
- acne_normal: FAIL (escalate=False, violations=[], tools: 冇 tool 跑過)
- dry_normal:  FAIL (escalate=False, violations=[], tools: 冇 tool 跑過)
- red_flag:    PASS (escalate=True,  violations=[], tools: 冇 tool 跑過)
NOTOOLS_EXIT=1
```

Good — the assertion does what its comment says.

**But it would NOT have caught #26 in CI. Experiment D** — replay the *actual* pre-#26 state
(the analyse prompt never told the model which tools exist, i.e. `TOOL_GUIDE` absent from
`ANALYZE_SYSTEM`) and run the real CI command `python -m eval.run_eval --fake`:

```
## Agent scenarios
- acne_normal: PASS (escalate=False, violations=[], tools: get_skin_profile=0 · search_knowledge=3)
- dry_normal:  PASS (escalate=False, violations=[], tools: get_skin_profile=3 · search_knowledge=3)
- red_flag:    PASS (escalate=True,  violations=[], tools: get_skin_profile=3 · search_knowledge=3)
OLDPROMPT_EXIT=0
```

**Green, exit 0.** The reason is exactly the mechanism docs row #26 already admits: in CI the
model *is* `FakeLLM`, and `FakeLLM.structured` hardcodes
`tool_calls=["get_skin_profile", "search_knowledge"]` (`app/agent/llm.py:36`) without ever
reading the prompt. `expect_tool` therefore tests "does the tool dispatcher + retrieval work",
never "can the model discover the tools from the prompt". The `expect_tool` gate can only
observe #26 in a **real-LLM** run (`python -m eval.run_eval`, no `--fake`) — which CI never
does and which needs a key and network. The docstring at `agent_eval.py:5-6` is honest about
this ("with a real LLM it is the gate that catches a model which never asks for any tool"), but
row #26's summary is not: it reads as if `expect_tool` were part of the regression defence,
when on the CI path it is structurally blind.

**What actually catches #26 is pytest, not the eval.** Running the test suite under the same
simulated pre-#26 prompt state:

```
>       assert documented == WHITELIST, f"prompt 講嘅 tool {documented} ≠ whitelist {WHITELIST}"
E       AssertionError: prompt 講嘅 tool set() ≠ whitelist {'get_skin_profile', 'search_knowledge', 'get_recent_entries'}
tests/test_observability.py:81: AssertionError
________________ test_analyze_system_prompt_includes_tool_guide ________________
E           AssertionError: assert 'get_skin_profile' in '你係男性護膚分析師。...'
tests/test_observability.py:86: AssertionError
=========================== short test summary info ============================
FAILED tests/test_observability.py::test_tool_guide_lists_every_whitelisted_tool
FAILED tests/test_observability.py::test_analyze_system_prompt_includes_tool_guide
2 failed, 11 passed in 0.49s
PYTEST_PRE26_EXIT=1
```

So the real guard for the #26 class of bug is
`tests/test_observability.py:78-81` and `:84-86` (plus `:89-92` for the schema description).
That is the assertion to name, not `expect_tool`.

**Small stale-doc find while tracing this:** `app/agent/prompts.py:7` says the sync is
"enforced by `tests/test_prompts.py`" — **that file does not exist** (`ls tests/test_prompts.py`
→ `No such file or directory`; the 15 real files are listed in `#13`). The enforcement is in
`tests/test_observability.py:78-81`. AGENTS.md gets it right; the code comment does not.

---

## Reproduction

Everything below was run from `backend/` with the repo venv, and none of it wrote to
`backend/data`:

```bash
./.venv/bin/python -m pytest -q                    # 73 passed, exit 0
./.venv/bin/python -m eval.run_eval --fake         # report printed, exit 0

# Q5 blind spot / positive control (scratch scripts in /tmp, no repo file modified)
./.venv/bin/python /tmp/sabotage_eval.py hybrid     # runtime path broken -> exit 0   <-- blind spot
./.venv/bin/python /tmp/sabotage_eval.py semantic   # eval-only path broken -> exit 1  <-- control
# Q6
./.venv/bin/python /tmp/sabotage_q6.py notools      # model proposes no tools -> exit 1
./.venv/bin/python /tmp/sabotage_q6.py oldprompt    # pre-#26 prompt -> exit 0        <-- blind spot
PYTHONPATH=/tmp ./.venv/bin/python -m pytest -q -p pre26_plugin tests/test_observability.py  # 2 failed, exit 1

# frontend regression (scratch copy at /tmp/fe_regress)
cd /tmp/fe_regress && npm run typecheck && npm run build   # both exit 0
```

The sabotage scripts patch module globals in-process and restore `eval/out/report.md`
(itself gitignored) afterwards. `git status` on tracked files is unchanged by this audit.

**Shared-tree note for whoever collects these audits:** `AGENTS.md` showed as modified
(` M AGENTS.md`) partway through this session — it was clean at my first `git status`. I never
wrote to it; another parallel audit or the harness did. `?? research/` is this document.

## Constraint compliance

No GitHub writes (all `gh` calls were `view`/`list`/`api` GETs). No app, eval, or CI file
modified. No real LLM API called (every run was `--fake` or in-process monkeypatching of
`FakeLLM`; `get_llm("text")` was never allowed to return a real adapter). `backend/data` and
`backend/data/skincoach.db` untouched, hash-verified.
