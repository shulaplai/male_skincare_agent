# Residual rows: #21 (correlation detector) and #22 (preference extraction)

Completeness check for the two rows the batch split never verdict-ed. Method is the
audit's standard: read the code, run it, and mutate it on a **copy** — never the
working tree.

| Row | Claim (status-vs-claims.md) | Verdict | One-line reason |
|---|---|---|---|
| **#21** correlation detector | L37: `✅ \`app/correlation.py\` + \`GET /correlations\` + ProgressView「相關性觀察」；deterministic candidate、標明唔等於因果` | **DRIFT** | Real, wired, and mostly guarded — but the documented diet input (`architecture.md:106`) is the one unguarded half (mutation → 73 green) **and** is unwritable on the live DB (#18), so the ✅ covers a capability that has never run on the author's data. Product→attribute half is genuine. |
| **#22** preference extraction | L38: `✅ \`app/preferences.py\`：diet tag ≥3 日／產品 ≥3 日 → preference；text 冇變唔 rewrite` | **DRIFT** | Rule, thresholds and throttle all match code and are guarded — but the *wiring* (`apply_events` → `extract_preferences`) has **zero** coverage (mutation → 73 green), and the diet branch cannot write on the live DB (#18) even with the timeline defect removed. |

Nothing here is `UNVERIFIABLE OFFLINE`: every claim was executed against temp/in-memory
SQLite. No LLM call, no model download, no GitHub write, no tracked file modified.

---

## Row #21 — correlation detector

### 1. Is the rule real and wired? Yes, end to end

Naming note: there is no `detect_correlations`. The real symbols are
`correlation.conversation_candidates` (DB adapter) and `correlation.detect_candidates`
(pure rule).

- Route → adapter: `backend/app/main.py:315-321`
  `@app.get("/api/conversations/{cid}/correlations")` … `return correlation.conversation_candidates(db, cid)`
  (404 guard at `:318-319`).
- Adapter → pure rule: `backend/app/correlation.py:251` `candidates = detect_candidates(entries, causes)`.
- Inputs the adapter gathers: entries `:199-208`; product first-use causes `:217-229`; diet causes from
  `source == "user"` timeline events where `conversation_id == conv_id` **or** `IS NULL` `:230-249`
  (`(TimelineEvent.conversation_id == conv_id) | (TimelineEvent.conversation_id.is_(None))`, `:234-236`).
- Rule constants `:29-33`: `BASELINE_DAYS = 7`, `LOOKAHEAD_DAYS = 4`, `MIN_DELTA = 1`,
  `STRONG_OCCURRENCES = 2`, `EPISODE_GAP_DAYS = 3`; `strong` set at `:146` `occurrences >= STRONG_OCCURRENCES`.
- UI: `frontend/src/api.ts:131-132` → `GET /api/conversations/{id}/correlations`;
  `ProgressView.tsx:158-160` renders the card titled `相關性觀察（自動偵測 · 唔等於因果）`
  (same block reused by the dash layout: `layouts/DashHome.tsx:134-135` → `blocks.tsx:110 CorrelationList`),
  body rendered per candidate at `ProgressView.tsx:61-71` (`cause_label → attribute_label`, `c.note`,
  `occurrences 次觀察`). The UI uses `candidate.note`; the API's `lines`/`explain_candidates` (`correlation.py:169-181`)
  is payload-only for the frontend.
- Ran it (temp DB, current schema, global diet cause seeded at today−4, baseline today−8 redness 1,
  follow-ups today−3/−1 redness 2):

```
[B2] GET /correlations -> 200
   entry_days=3 cause_episodes=1 candidates=1
   -> diet:diet:spicy -> redness up x1 strong=False
   note=暫時只係單次觀察，未夠證據落結論；繼續記錄先，同一模式出現多次我先會講。
```

  (the doubled `diet:` is my print prepending `cause_type`; the stored `cause_key` is `diet:spicy`).

### 2. Is it guarded? Halves are guarded; one documented half is not

Mutation harness: pristine copy of `backend/{app,tests,eval,scripts}` at `/tmp/mut`, one literal
edit per run, `python -m pytest -q --tb=no -rf`. Sandbox baseline **73 passed** (matching the
in-repo run: `73 passed in 1.71s`).

| Mutation (file) | Suite | Failing test(s) |
|---|---|---|
| drop global diet causes — `TimelineEvent.conversation_id.is_(None)` clause removed (`correlation.py:234-236`) | **GREEN — 73 passed** | none |
| drop product causes — `prod_rows = []` (`correlation.py:218`) | RED — 1 failed | `test_conversation_candidates_db_path` |
| `STRONG_OCCURRENCES = 99` (`:32`) | RED — 1 failed | `test_detect_candidates_repeated_episode_marks_strong` |
| disable episode clustering (`cluster_dates`, `:77`) | RED — 1 failed | `test_detect_clusters_close_episodes` |
| `MIN_DELTA = 5` (`:31`) | RED — 4 failed | `test_detect_candidates_repeated_episode_marks_strong`, `…_single_observation_not_strong`, `test_detect_clusters_close_episodes`, `test_conversation_candidates_db_path` |
| route replaced by a stub returning empty `candidates` **and** `entry_days: 0` (`main.py:321`) | RED — 1 failed | `test_correlations_endpoint` — and only on `assert 0 == 3`: the endpoint guard fires on `entry_days`, never on emptiness. The empty-candidates case is the 21a row above, which stays green. |

So the detector **core** (deltas, clustering, strong threshold, product causes) is genuinely
guarded by `tests/test_correlation.py:13,40,55,70,96`. The documented diet input is not:
`test_api_layers.py:126-136` asserts only `assert "candidates" in body and "note" in body` and
`body["entry_days"] == 3` — never a non-empty candidate. So with the global clause deleted the route
returns `candidates: []` on that fixture and the test still passes on key presence alone. This is
exactly the prior batch's `correlation detector drops global diet causes → 73 passed`, reproduced here.

No end-to-end guard exists either: `eval.run_eval --fake` passes (RAG recall@3 100%, 3/3 agent
scenarios PASS) but `grep -rn 'correlation\|preference' backend/eval/*.py` returns **nothing** — the
eval harness has no gate touching either row. The frontend has no test runner at all
(`frontend/package.json` scripts: `dev`, `build`, `preview`, `typecheck`), so the "相關性觀察" card is
guarded by nothing.

### 3. Does it survive the live-DB defect (#18)? The diet half does not

Simulated on temp DBs (`/tmp/livedb-sim/*.db`) by rebuilding `timeline_events`/`insights` with
`conversation_id NOT NULL` — the live DB's shape, verified by
`PRAGMA timeline_events.conversation_id notnull = 1`.

| Sim | Setup | Result |
|---|---|---|
| A | legacy schema; `POST /api/conversations/{cid}/events` with confirmed diet `食咗辣底` | **500** `NOT NULL constraint failed: timeline_events.conversation_id`; global timeline rows = 0; `GET /correlations` → **200** with `cause_episodes=0 candidates=0`, `note=未有重複嘅「原因 → 皮膚變化」模式。會繼續觀察。` |
| B | can a NOT NULL table even *hold* a pre-existing global row? | `INSERT INTO timeline_events SELECT * FROM timeline_events_old` → `IntegrityError: NOT NULL constraint failed`. A global row is **unrepresentable**, so #18's `global_events|0` is forced, not incidental — there is no "old rows survive" escape hatch. |
| C | legacy schema, one batch with `product_start` + `diet` | 500; `Product rows = 0`, `timeline rows = 0`, entries with product ref = 0 — the diet failure rolls the whole batch back, so even the conv-scoped product write is lost. |
| D | current schema (control), same diet POST | 200 `{"written":1,"diet":1,"product":0,"preferences":0}`; global timeline rows = 1 |

Conclusion: correlation can detect a **product**→attribute pattern on the live DB (products are
conv-scoped, `models.py:153`), but it can **never** detect a diet→attribute pattern, because diet is
written *only* as a global timeline row (`self_report.py:112-132`: "conversation-scoped copy is
intentionally NOT written") and that insert cannot succeed. `architecture.md:106` explicitly sells
this input: "correlation detector 亦睇 global diet 事件".

One correction to record: on my faithful reproduction of the nullability defect, `GET /correlations`
returns **200 with an empty result and a reassuring note**, not 500 — and `/summary` returned 200 too.
#18's note records both as 500 against the live DB copy, so that extra 500 has some other cause I
cannot reach without opening the live DB (forbidden here). Either way the UX outcome is the dangerous
one: the progress card looks healthy and says "繼續觀察" while nothing can ever be observed.

### 4. Do the documented numbers match?

- `docs/architecture.md:107`: "≥2 次重複先算 strong（UI 明示「唔等於因果」）" → `STRONG_OCCURRENCES = 2`, `correlation.py:146`; UI title carries the caveat. **Match.**
- `backend/README.md:62`: identical claim ("cause episodes（product 首次使用日 / diet 事件日）→ 前後 window 嘅 attribute delta；≥2 次重複先算 strong candidate"). **Match.**
- `backend/README.md:76` documents `GET /api/conversations/{cid}/correlations`. **Match** (`main.py:315`).
- `AGENTS.md:35` "cause episodes → attribute deltas，repeated = strong". **Match.**
- The window lengths (7-day baseline, 4-day lookahead, 3-day episode gap) appear **nowhere** in docs; "前後 window" is unspecified. Not a contradiction, but the only place they are stated is the code.
- `docs/status-vs-claims.md:50` "correlation / preference 嘅「重複模式」要靠真數據 collect 幾星期先有意義 —— code 已 ready，等 data" — "等 data" is not the blocker for the diet half; the data *cannot be collected* on the live DB. **Contradicted** (see #3 / row #16).
- `docs/blog-post.md:125` "Correlation detector 已上（deterministic candidate，標明唔等於因果）——等真數據 collect 幾星期先有意義。" — same "等 data" framing, same contradiction.
- The status table's legend types these rows `(b)` = `真數據路徑缺口 → 做真 code` (`docs/status-vs-claims.md:4`) under an overview that promises `真數據路徑 100% 真` (`:8`), and `:63` names `#1/3/6/7/11/12/14/21/22` as the designated interview "真 claim" set. For the diet half of this row that promise is false on the author's own DB — which is what makes the ✅ worth correcting rather than harmless.
- The suite's claimed coverage of these modules (`backend/README.md:98-99` and `docs/eval-report-sample.md:53`: "… / correlation / preferences / API layers") is file-level, not seam-level: both files exist and are green, but neither unguarded seam lives in them.

---

## Row #22 — preference extraction

### 1. Is the rule real and wired? Yes, and it does run after `apply_events`

- Hook: `backend/app/self_report.py:159-163`
  ```
      if with_preferences:
          from .preferences import extract_preferences

          prefs = extract_preferences(session, conv_id)
          stats["preferences"] = prefs["written"]
  ```
  reached from the API because `apply_events` defaults it on (`self_report.py:91`
  `*, with_preferences: bool = True`) and `main.py:186` calls `apply_events(db, cid, req.events)`
  without the flag. Confirmed by running it on a temp DB: `POST /events` →
  `{"written":1,"diet":1,"product":0,"preferences":0}`. No caller passes the flag at all —
  `grep -rn apply_events` finds only `main.py:186` and `tests/test_self_report.py:42,88,92`, and no
  test asserts `stats["preferences"]` (`test_self_report.py:52-53` checks `diet`/`product` only).
- Rule `preferences.py:75-125`: diet branch `:86-106` counts distinct days per trigger tag over
  `conversation_id == conv_id OR IS NULL` events with `source == "user"` and upserts a **global**
  preference (`_upsert(session, None, f"diet:{tag}", …)`, `:106`); product branch `:108-122` upserts
  conv-scoped `product:<name>`. `session.commit()` at `:124`.
- Code vs docs numbers — `AGENTS.md:34`, `docs/architecture.md:67`, `backend/README.md:61`,
  `docs/status-vs-claims.md:38` all say "diet trigger tag ≥3 個唔同日（21 日 window）→ global
  preference「近排成日食…」；同一產品 ≥3 日 → conversation preference「常用產品：…」；text 冇變就唔 rewrite".
  Code: `PREFERENCE_WINDOW_DAYS = 21`, `DIET_MIN_DAYS = 3`, `PRODUCT_MIN_DAYS = 3` (`:21-23`);
  `_within` counts distinct dates with `(today - d).days <= window_days` (`:34-36`); text templates
  `近排成日食{zh}（最近 21 日內 {n} 日）` / `常用產品：{name}（最近 21 日內 {n} 日）` (`:105`,`:121`);
  throttle = skip when `cur.text == text` (`:53-55`). **All match.**
- Nuances worth knowing (not doc contradictions): the throttle is text-equality, and the text embeds
  the day count `n`, so the same row is rewritten once per new trigger day (`n` grows) — "低頻" is
  per distinct-day, not per tag; and `<= 21` days inclusive of today is 22 calendar days, i.e. one
  more than the doc's "21 日 window". Future-dated events would also count (negative age ≤ 21), but
  `apply_events` always dates events `today`, so that edge is unreachable from the API.
- Surfacing: preferences reach the UI only as insights (`/summary` merges global insights), rendered
  with `preference: '偏好'` labels (`ProgressView.tsx:8`, `blocks.tsx:12`, `RightPanel.tsx:8`).

### 2. Is it guarded? The rule is; the wiring is not

Same harness, same sandbox baseline (73 passed).

| Mutation (file) | Suite | Failing test(s) |
|---|---|---|
| never extracted after `apply_events` — preferences block replaced by `pass` (`self_report.py:159-163`) | **GREEN — 73 passed** | none |
| diet counting drops global events — `IS NULL` clause removed (`preferences.py:89-92`) | RED — 2 failed | `test_diet_preference_after_repeated_days`, `test_preference_throttled_no_rewrite_same_day` |
| throttle removed — `if cur.text == text:` → `if False:` (`:54`) | RED — 1 failed | `test_preference_throttled_no_rewrite_same_day` |
| `DIET_MIN_DAYS = 1` (`:22`) | RED — 1 failed | `test_below_threshold_writes_nothing` |
| `PREFERENCE_WINDOW_DAYS = 1` (`:21`) | RED — 3 failed | `test_diet_preference_after_repeated_days`, `test_preference_throttled_no_rewrite_same_day`, `test_product_preference_after_three_days` |
| product preference scope → global (`_upsert(session, None, …)`, `:122`) | RED — 1 failed | `test_product_preference_after_three_days` |

`tests/test_preferences.py:37,63,84,112` guards the thresholds, the window, the throttle and both
scopes — solid. But the *hook* is unguarded: nothing asserts that the confirmed-events endpoint
produces a preference, so the whole feature can be disconnected (mutation 1 → 73 green, eval --fake
still PASS) with the suite none the wiser. That is a different failure mode from #26 (prompt/tool
discovery) but the same shape, and it is the reason this row cannot be called simply VERIFIED.

### 3. Does it survive the live-DB defect (#18)? Its diet branch dies independently

Isolated run (`/tmp/livedb-sim/pref.db`): freeze **only** `insights.conversation_id` NOT NULL and leave
`timeline_events` nullable, so #16's timeline defect cannot be what fails first. Three global diet
events are seeded successfully (nullable timeline), then:

```
PRAGMA timeline_events.conversation_id notnull = 0
PRAGMA insights.conversation_id notnull = 1
seeded global timeline rows = 3  (nullable table, so these land)
extract_preferences -> IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: insights.conversation_id
preference rows written = 0
```

So `preferences.py:106` (`_upsert(session, None, …)`) is dead on the live DB on its own merits, not
merely as collateral of #16 — and it raises, so it would also take down the surrounding
`POST /events` request. The product branch (`conversation_id = conv_id`) is unaffected and still
works. This is a second row whose ✅ depends on a global write that the live schema rejects.

### 4. Do the documented numbers match?

Everything numeric matches (see §1); the 21-day / ≥3-day rule is also stated in prose at
`docs/blog-post.md:80` ("同一 diet trigger（例如「辣」）喺 21 日內出現 ≥3 個唔同日 → global preference
「近排成日食辣嘢」。**Text 冇變就唔 rewrite**"), which matches the code too. The claims the code
contradicts are the status lines: `docs/status-vs-claims.md:38` `✅ Layer 2 **完成**` — for the diet
half, "完成" is a code-complete claim over a write path that the live DB refuses;
`docs/status-vs-claims.md:50` and `docs/blog-post.md:125` likewise treat the remaining gap as "等 data"
rather than "unreachable on this DB"; and the row is typed `(b)` = `真數據路徑缺口 → 做真 code` (`:4`)
under an overview promising `真數據路徑 100% 真` (`:8`), with `:63` naming #22 one of the interview
"真 claim"s. `README.md:8` and `docs/roadmap.md:37` restate the same feature list and inherit the
same caveat.

---

## Baseline evidence (commands actually run)

```
backend$ ./.venv/bin/python -m pytest -q                      -> 73 passed in 1.71s
backend$ ./.venv/bin/python -m eval.run_eval --fake           -> exit 0; RAG recall@3 100%, hybrid 100%,
                                                                 3/3 agent scenarios PASS, no correlation/
                                                                 preference gate anywhere
/tmp/mut$ .venv python -m pytest -q                           -> 73 passed in 1.76s  (mutation baseline)
```

Mutation edits were applied to `/tmp/mut` (a copy of `backend/app`, `tests`, `eval`, `scripts`) and
restored from the pristine copy after every run; no tracked file was touched, and `pytest` was never
run with an edit in the working tree. Temp DBs live under `/tmp/livedb-sim/`; `backend/data/skincoach.db`
was never opened. Harnesses kept for reproduction: `/tmp/run_mutations.py`,
`/tmp/livedb_matrix.py`, `/tmp/pref_isolate.py`.

## What this changes for the map

- Rows #21 and #22 can now be marked with a verdict: **both DRIFT** — the code-side rules are real,
  wired and (for their cores) genuinely guarded, but each row's ✅ rests on a global write
  (`diet → global timeline` for #21, `diet → global preference` for #22) that the live DB rejects, and
  each row has one unguarded seam (diet causes for #21; the `apply_events` hook for #22) that the
  73-test suite and `eval --fake` both sail past. Neither row is unfixable or fabricated; they are
  over-ticked.
- Both verdicts are **not separable** from #18, exactly as the ticket anticipated: the shared fix
  (repairing the two tables, or teaching `_COLUMN_MIGRATIONS` to rebuild) is what would make the diet
  halves live, and two cheap tests (assert a diet cause reaches `/correlations`; assert `POST /events`
  yields `preferences >= 1`) are what would make the seams guarded.
