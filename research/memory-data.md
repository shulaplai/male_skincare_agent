# Memory & data layer audit — issue #3 (rows #6, #15, #16, #17, #19, #23)

Scope: `backend/app/memory.py`, `preferences.py`, `self_report.py`, `correlation.py`, `models.py`,
`db.py`, `photo.py`, `export.py`, `crud.py`, `agent/graph.py` (persist node), `agent/tools.py`, the
related routes in `app/main.py`, plus the frontend surfaces that call the delete/edit routes.

Method: read the code **and** run it. Every rule below was reproduced, and every "is there a test
that would fail if this regressed?" question was answered by **mutation testing**: a copy of
`backend/` was made at `/tmp/skc-mut`, each rule was deliberately broken there, and the real suite
was run. A mutation that leaves **73/73 green** means no test guards that rule.

## Constraints honoured

* No tracked file modified (`git status --porcelain` → only `M AGENTS.md`, `?? .wayfinder/`,
  `?? docs/agents/`, `?? research/` — none of it mine).
* `backend/data/skincoach.db` was **never opened**: before/after
  `md5 -q data/skincoach.db` = `40823465d6041edf11c05a44f07d88b9`, `mtime=2026-09-10T11:16:07`,
  `size=37445632` — identical. Only filesystem *metadata* (`stat`) was read from it, and the schema
  question it raises is handed back as a one-line check (see MIGRATION-1).
* No real LLM API called, real embedder never instantiated (`FakeLLM` + `DeterministicEmbedder`,
  or `FakeLLM` through the graph with `DeterministicEmbedder`).
* Nothing posted to GitHub.

## Commands actually run (quoted output)

```
$ cd backend && SKINCOACH_DATABASE_URL=sqlite:////tmp/skc-audit/pytest.db \
    SKINCOACH_DATA_DIR=/tmp/skc-audit/data \
    ./.venv/bin/python -m pytest -q
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 1.54s

$ git check-ignore -v backend/.env backend/data backend/data/skincoach.db backend/.hf-cache data
.gitignore:13:.env	backend/.env
.gitignore:16:data/	backend/data
.gitignore:16:data/	backend/data/skincoach.db
.gitignore:19:.hf-cache/	backend/.hf-cache
.gitignore:16:data/	data

$ git ls-files | grep -iE "\.env|(^|/)data/"
backend/.env.example
```

(The suite was run with the DB/data dir redirected to `/tmp` so it could not touch the real DB;
the prod defaults would have been `sqlite:///./data/skincoach.db`. md5 of the real DB was
identical before and after.)

Mutation sweep (`/tmp/skc-audit/mutation_sweep.py`, patch → pytest → restore, on the copy):

```
mutation                                                       file                   result
#6a graph.persist ignores expiry (no is_expired gate)          app/agent/graph.py     73 passed in 1.61s
#6b reconcile compares TEXT instead of tag+direction           app/memory.py          1 failed, 72 passed || FAILED tests/test_memory.py::test_same_direction_strengthens_even_with_different_text
#6c DECAY_DAYS 30 -> 1                                         app/memory.py          73 passed in 1.44s
#6d supersede no longer versions the new insight               app/memory.py          1 failed, 72 passed || FAILED tests/test_memory.py::test_direction_flip_supersedes_and_versions
#15 chat_messages are never persisted                          app/agent/graph.py     2 failed, 71 passed || FAILED tests/test_messages.py::test_consult_persists_user_and_coach_messages; ::test_second_consult_sees_first_as_recent_context
#16a diet event written conversation-scoped instead of global  app/self_report.py     1 failed, 72 passed || FAILED tests/test_self_report.py::test_apply_events_writes_entry_timeline_and_product
#16b /summary stops merging global timeline events             app/main.py            3 failed, 70 passed || FAILED tests/test_api_layers.py::test_summary_merges_global_events_and_insights; ::test_summary_second_conversation_sees_global_diet; ::test_delete_entry_removes_entry_photos_and_same_day_conv_events
#17 per-product fact hook never runs                           app/self_report.py     1 failed, 72 passed || FAILED tests/test_self_report.py::test_apply_events_writes_entry_timeline_and_product
#17b product row never created from self-report                app/self_report.py     1 failed, 72 passed || FAILED tests/test_self_report.py::test_apply_events_writes_entry_timeline_and_product
#19 import_zip loses the traversal guard                       app/export.py          1 failed, 72 passed || FAILED tests/test_export.py::test_import_rejects_path_traversal
#19b export_zip stops including the DB                         app/export.py          1 failed, 72 passed || FAILED tests/test_export.py::test_export_import_roundtrip
#23a entry delete keeps same-day conv timeline events          app/main.py            1 failed, 72 passed || FAILED tests/test_api_layers.py::test_delete_entry_removes_entry_photos_and_same_day_conv_events
#23b photo delete matches Photo.id instead of path             app/main.py            73 passed in 1.80s
#23c insight delete leaves superseded_by dangling              app/main.py            73 passed in 1.42s
#23d global insights become undeletable from any conversation  app/main.py            1 failed, 72 passed || FAILED tests/test_api_layers.py::test_delete_global_insight_permitted_from_any_conversation
migration table loses `direction` (like `diet` today)          app/db.py              73 passed in 1.41s
preferences never extracted after apply_events                 app/self_report.py     73 passed in 1.44s
get_skin_profile stops seeing global memory                    app/agent/tools.py     73 passed in 1.42s
#16c preferences diet counting drops global events             app/preferences.py     2 failed, 71 passed || FAILED tests/test_preferences.py::test_diet_preference_after_repeated_days; ::test_preference_throttled_no_rewrite_same_day
#17c correlation detector drops global diet causes             app/correlation.py     73 passed in 1.58s
```

## Verdicts

| Row | Verdict | One-line reason |
|---|---|---|
| #6 | **DRIFT** (rule true, decay claim overstated; 2 rules unguarded) | `reconcile()` really is tag+direction and really is called from `persist` — but `expires_at` is honoured **only at write time**: expired insights stay active, stay in `/summary`, and stay in the coach's prompt, with the *stale* row carrying the higher confidence. |
| #15 | **VERIFIED** (1 unclaimed gap) | `chat_messages` + `GET /api/conversations/{cid}/messages` + reload path all real (200 / `[]` / 404 reproduced); but pending `detected_events` confirm chips are *not* persisted, so they vanish on reload. |
| #16 | **VERIFIED** (code + tests) · ⚠️ **runtime-blocked on the live DB** | diet really writes `conversation_id=NULL` and `/summary` really merges with `is_(None)`; both reproduced. But see MIGRATION-1: on a pre-2026-09-02 DB every global write raises `IntegrityError`, and the live DB's birth time says it is such a DB. |
| #17 | **VERIFIED** (data layer) · **DRIFT** (display) | Product row, `Entry.products` and the per-product fact hook all fire and are test-guarded — but the journal UI renders the raw 32-hex product **id** (`🧴 5680cffc23d4…`), and no other view shows products at all. |
| #19 | **VERIFIED** | `.env` + `data/` genuinely ignored (nothing tracked but `.env.example`); the export archive contains no key bytes and round-trips byte-exactly. Caveats: import is API-only, and import overwrites/merges with no backup. |
| #23 | **VERIFIED** (behaviour, all three reproduced) · ⚠️ 2 of 3 sub-rules unguarded | Same-day conv events deleted + global kept; photo matched by **path**; `superseded_by` cleared. But deleting a *superseding* insight resurrects the stale one, and neither photo-delete nor pointer-clearing has any test. |

---

## #6 — 三類 memory + 30 日衰減 + 矛盾 versioning — **DRIFT**

**Doc claims**

* `docs/status-vs-claims.md:22` — 「三類 memory（fact/derived/preference）+ **30 日衰減** + 矛盾 versioning … ✅ **per-attribute reconcile 真**（tag+direction，Q47）」
* `README.md:8` — 「derived per-attribute reconcile（tag+direction：strengthen / supersede versioning + 30 日 expiry）」
* `backend/README.md:59` — 「同 tag 同 direction → strengthen（confidence 升、expiry 延長、text 更新）；flip → supersede（version+1）。**30 日 expiry**。」
* `docs/architecture.md:61` — 「derived | … | **30 日 expiry 衰減**；再評估可延長/升 confidence」
* `docs/blog-outline.md:41` / `docs/demo-script.md:29` — 「衰減同矛盾係 code，唔係 prompt 祈求」

**What the code does (tag + direction: TRUE, and wired)**

* Pure rule: `backend/app/memory.py:96-134` — `reconcile()` early-returns both unchanged for
  non-derived (`:109-110`) or different tag (`:111-112`); same tag + same direction → `strengthened`
  with `text=candidate.text`, expiry extended (`:114-125`); direction flip → `old.superseded_by =
  candidate.id` + `version=existing.version + 1` (`:127-133`). Direction is the *state category*, not
  a trend: `memory.py:15-16` + `agent/attributes.py:60-62` (`severity >= 2 → problem`).
* Caller (the answer to "a rule with no caller is drift" — this one *has* a caller):
  `agent/graph.py:56` imports it, `graph.py:316` computes `direction_for(attr.severity)`,
  `graph.py:325-330` loads the active insight for that tag, `graph.py:331-356` calls
  `is_expired`/`reconcile` and writes back, `graph.py:357-370` handles the no-live-insight case.
* End-to-end proof (`/tmp/skc-audit/reconcile_probe.py`, FakeLLM reports acne=2 → `problem`):

```
A) after consult #1: 1 acne row(s)  id=603490 dir='problem' conf=0.6 v=1
   persist trace #2: {'entry_reused': True, 'insights_created': 0, 'insights_strengthened': 3, 'insights_superseded': 0}
A) after consult #2 (same day, same direction): 1 acne row(s)  id=603490 conf=0.65 v=1
B) after consult (direction flip normal -> problem):
    id=dced05 dir='normal'  conf=0.8 v=1 superseded_by=41f209 text='暗瘡：正常'
    id=b7af57 dir='problem' conf=0.6 v=2 superseded_by=-      text='暗瘡：中等'
```

**Where the docs stop being true: the 30-day decay has no read path**

`grep -rn "expires_at" app/ eval/ scripts/ tests/` returns exactly one consumer outside
`memory.py` itself:

```
app/agent/graph.py:335:   existing.expires_at = r.expires_at
app/agent/graph.py:349:   expires_at=r.expires_at,
app/agent/graph.py:366:   expires_at=expiry_for(now),
```

`is_expired()` is called **only** at `graph.py:331`, i.e. to decide "strengthen the old row, or
insert a new one". Nothing else in the app ever looks at `expires_at`:

* `/summary` insight query — `app/main.py:237-245`: filters `conversation_id` and
  `superseded_by.is_(None)`; **no expiry filter**.
* coach memory tool `get_skin_profile` — `app/agent/tools.py:21-30`: same two filters; **no expiry
  filter**.
* no purge job, no `models` event, no `expires_at < now` predicate anywhere.

Consequence, reproduced (`/tmp/skc-audit/decay_probe.py`: one derived acne insight, `expires_at`
yesterday, direction `normal`; one consult through the real graph):

```
persist trace: {'entry_reused': False, 'attributes': 3, 'insights_created': 3, 'insights_strengthened': 0, 'insights_superseded': 0}

1) insights table after one consult:
   kind=derived tag=acne dir='normal'  conf=0.85 v=1 expired=True  superseded_by=None text='暗瘡：正常'
   kind=derived tag=acne dir='problem' conf=0.6  v=1 expired=False superseded_by=None text='暗瘡：中等'
   …

2) /summary query (same filters as app/main.py:237-245):
   [derived/acne] 暗瘡：中等  (conf=0.6)
   [derived/acne] 暗瘡：正常  (conf=0.85)

3) get_skin_profile tool result handed to the LLM:
   [{'kind': 'derived', 'text': '暗瘡：正常', 'confidence': 0.85, …},
    {'kind': 'derived', 'text': '暗瘡：中等', 'confidence': 0.6, …}, …]
```

So an expired insight is never forgotten: it stays active, it is shown in the UI, and the coach gets
**both** the expired and the fresh statement — with the expired one at the *higher* confidence
(0.85 vs 0.6), because `strengthen` is the only path that raises confidence and the new row after
expiry starts at the `0.6` baseline. "30 日衰減" describes a write-time decision, not memory that
decays.

**Smallest honest corrections**

1. `docs/` + both READMEs: say what the code does — 「derived insight 30 日後**唔會再 strengthen**，
   會另開一條新 insight；舊條目仍然留在 `/summary` 同 `get_skin_profile`（只有 UI 冇 expiry
   過濾）」. Either that, or add the missing read-path filter (a 1-line
   `.filter(or_(Insight.expires_at.is_(None), Insight.expires_at > now))` in `main.py:237-245` and
   `tools.py:21-30`) — that is the change that would make the current docs true.
2. `backend/app/models.py:108` — the column comment is a third, contradictory definition of the
   same field: `direction: … # better|worse|same — derived attribute trends`. The code only ever
   writes `problem`/`normal` (`attributes.py:60-62`, `memory.py:27-29`), never `better|worse|same`.
   Fix the comment (it is exactly the kind of stale comment that re-seeds the old text-based rule).
3. `memory.py:83-89 make_fact()` — **orphan pure function**: `grep` over `app/` shows no caller; it
   is imported only by `tests/test_memory.py:9`. Facts are written raw in `main.py:162-168` and
   `self_report.py:79/86`. Dead code that reads like the canonical way to make a fact.
4. `graph.py:333-339` — the trace counter lies on a supersede: the `r.id == existing.id` branch
   increments `insights_strengthened` even when that row was *superseded* (probe B trace:
   `insights_strengthened: 1, insights_superseded: 1`). Anyone reading `data/runs.jsonl` to count
   strengthens is misled.

**Test that would fail if the rule regressed**

| Rule | Guarded? | Guard |
|---|---|---|
| tag+direction, not text | ✅ | `tests/test_memory.py:17` (mutation #6b → red) |
| supersede + version bump | ✅ | `tests/test_memory.py:40` (mutation #6d → red) |
| confidence cap, different tags untouched, facts/prefs never reconcile | ✅ | `tests/test_memory.py:31`, `:55`, `:64` |
| derived expires (pure function) | ✅ | `tests/test_memory.py:73`, `:81` |
| **`persist` honours expiry (`graph.py:331`)** | ❌ | mutation #6a — deleting `and not is_expired(...)` keeps **73 passed** |
| **`DECAY_DAYS == 30` as documented** | ❌ | mutation #6c — `DECAY_DAYS = 1` keeps **73 passed** (the pure test uses its own `NOW+31d` offsets) |

## #15 — chat 歷史 persist / reload 唔清空 — **VERIFIED** (1 unclaimed gap)

**Doc claims** — `docs/status-vs-claims.md:31`; `docs/architecture.md:38,109`（「`chat_messages`
持久化，reload 唔清空」）; `backend/README.md:55,64,77`; `README.md` feature list.

**Table / endpoint / empty behaviour (all reproduced, `/tmp/skc-audit/delete_probe.py`)**

```
=== #15 messages endpoint ===
existing conv, 2 messages -> 200 ['user', 'coach']
existing conv, 0 messages -> 200 []
unknown cid -> 404 {'detail': 'conversation not found'}
coach payload keys -> ['advice','attributes','disclaimer','escalate','metrics','reply','summary','vision_used']
'detected_events' persisted in payload? -> False
```

* Table: `ChatMessage` / `chat_messages` — `models.py:140-157` (auto-increment `id`, JSON `payload`).
* Endpoint: `main.py:204-225` (`GET /api/conversations/{cid}/messages`), ordered by `ChatMessage.id`
  ascending. Empty-conversation behaviour is a plain `200 []`; `404` only when the *conversation*
  does not exist (`main.py:207-209`).
* Write side: `graph.py:377-401` — user turn (with `payload.photos`) + coach turn carrying
  summary/reply/metrics/attributes/advice/disclaimer/escalate/vision_used. So a reload re-renders
  the reply identically, without re-running the agent.
* Frontend reload chain: `api.ts:113-115 getMessages` → `App.tsx:68-86` (on `activeId`+`online`) →
  `format.ts:31-60 fromServerMessage` → rendered by `Chat` in all three shells
  (`ChatShell.tsx:32-48`, `StandardShell.tsx:60-77`, `JournalHome.tsx:204-217`).
* Mutation #15 (drop coach message persistence) → 2 tests red → the *persistence* is guarded by
  `tests/test_messages.py:31,49`.

**Unclaimed gap (worth knowing, not a doc lie):** the confirm chips for LLM-detected events are
live-only. `graph.py:390-399` does not store `detected_events`; `App.tsx:165` attaches them from the
live consult response; `fromServerMessage` (`format.ts:32-59`) never sets `events`, and
`types.ts` `ServerMessage.payload` has no such field. After a reload, a detected diet/product event
that the user had not yet confirmed is gone with no way to confirm it. Claim #15 only says the
thread survives — which it does.

Also unguarded-but-true: no test exercises the `/messages` **route** at all (`grep -rn "messages"
tests/` → only `test_messages.py`, which asserts on DB rows/state, not on an HTTP call), so a bug in
the endpoint's serialisation would not be caught.

## #16 — diet 寫 global，`/summary` merge 埋 — **VERIFIED** (code+tests) · ⚠️ runtime-blocked on the live DB

**Doc claims** — `docs/status-vs-claims.md:32`（「global 寫手已做：diet → global timeline（Q31）」）;
`docs/architecture.md:68`; `backend/README.md:60`（「diet → 當日 `Entry.diet` + **global** timeline
event（`conversation_id=NULL`）」）; `AGENTS.md` 陷阱條目.

**Code**

* Write: `self_report.py:119-132` — `TimelineEvent(conversation_id=None, date=today, text=…,
  source="user")`, with a cross-conversation dedupe set built at `:106-109`
  (`TimelineEvent.conversation_id.is_(None)`). Non-diet events stay conv-scoped (`:144-156`).
  `Entry.diet` is appended at `:117`.
* Merge: `main.py:246-263` — `conv_events` (`:248-253`) + `global_events` (`:254-259`, `is_(None)`),
  merged with `sorted(..., key=(date, created_at))` and tagged `scope` at `:307`.
* Insights merge: `main.py:239-241` — `(Insight.conversation_id == cid) | is_(None)`.
* Every other global-aware reader also handles NULL: `agent/tools.py:21-30`,
  `preferences.py:88-95`, `correlation.py:231-239`.
* Reproduced end-to-end (`/tmp/skc-audit/events_probe.py`, `POST /events` on 面部皮膚, then read
  頭皮):

```
POST /events -> 200 {'written': 2, 'diet': 1, 'product': 1, 'preferences': 0}
TimelineEvent rows: [('打邊爐·辣底', 'GLOBAL'), ('開始用：水楊酸 Toner', 'conv')]

/summary of the OTHER conversation (頭皮):
  timeline: [('2026-09-14', '打邊爐·辣底', 'global')]
  insights: []
```

* Tests: `tests/test_self_report.py:66-73` (global row, no conv-scoped copy),
  `tests/test_api_layers.py:95-113` + `:115-123` (merge + second conversation sees it),
  `tests/test_preferences.py:37-60`. Mutations #16a, #16b, #16c all go red.

**Two honest gaps**

1. **Unguarded**: mutating `tools.get_skin_profile` to drop `is_(None)` keeps **73 passed**; so does
   mutating `correlation.py` to drop global diet causes. The doc line 「global fact/preference 可見於
   summary + coach tools」 has no test behind the "coach tools" half.
2. **Correction is asymmetric**: `delete_entry` keeps global events (`main.py:393`, by design), so
   deleting the day still leaves its same-day diet cause on every timeline. Reproduced: after
   `DELETE /api/conversations/{cid}/entries/{eid}` the timeline was
   `[('2026-01-03', '食咗辣底', 'global')]` — the record is gone, the cause it generated stays.
3. `docs/architecture.md:105` still claims 「**每個部位有獨立** entries/photos/insights/timeline/
   messages」, which contradicts `architecture.md:68` and Q31 in the same file (timeline and
   insight lists are deliberately shared for body-spanning causes/facts). Smallest fix: note the
   global exception on line 105.

## #17 — Product 庫 + per-product fact hook — **VERIFIED** (data layer) · **DRIFT** (display)

**Doc claims** — `docs/status-vs-claims.md:33`（「products table 真（self-report 確認創建 +
Entry.products + per-product fact）」）; `docs/architecture.md:68`; `backend/README.md:60`;
`docs/roadmap.md:16,36`.

**Code paths (all real)**

* Route: `main.py:180-187` → `apply_events(db, cid, req.events)`.
* Product row: `self_report.py:46-59` `_get_or_create_product()` (case-insensitive dedupe by name,
  `flush()` so the id exists), called at `:134`.
* `Entry.products` reference: `:136-140` (start adds the id, stop removes it).
* Per-product fact hook: `:62-88` `_upsert_product_fact()` — tag `product_use:<lower name>`, text
  「由 {date} 開始用「{name}」」, refreshed in place on change, called at `:142`.
* Models: `models.py:160-175` `Product(conversation_id NOT NULL, name, category, ingredients)`.
* Reproduced (`events_probe.py`):

```
Product rows: [('水楊酸 Toner', '其他', True)]
Entry.diet: ['打邊爐·辣底'] | Entry.products (ids): ['5680cffc23d24b43a723efd1d93d4d45']
Insight rows: [('fact', 'product_use:水楊酸 toner', '由 2026-09-14 開始用「水楊酸 Toner」')]
same product again (case-different name): Product count: 1 | fact rows unchanged
```

* Guarded: `tests/test_self_report.py:38-80` asserts the row, `entry.products` membership and the
  fact text; mutations #17 and #17b both go red.

**The drift: the UI prints the raw product id**

* `main.py:286` returns `"products": e.products` — the 32-hex **ids** stored in the JSON column.
* `frontend/src/layouts/JournalHome.tsx:129-133`:

```tsx
{(entry.products ?? []).map((product) => (
  <span key={product} className="chip">🧴 {product}</span>
))}
```

There is no id→name resolution anywhere on the client (`grep -rn "products" frontend/src` →
`types.ts:84` (`products?: string[]`), `JournalHome.tsx:129`, `JournalHome.tsx:140` only), and the
server never resolves them outside `tools.py:51-53` (`get_recent_entries`, which *does* map ids to
names for the LLM). So the journal layout renders `🧴 5680cffc23d24b43a723efd1d93d4d45`; the chat,
records and progress views show no products at all. `npm run typecheck` stays green because the type
is a bare `string[]`.

*Smallest honest correction*: either resolve names in `/summary` (or in `JournalHome` via
`getSummary`+product map) before claiming 「products table 真 … UI 有 product chip」, or drop the
product chip from the 「feature parity」 claim (#25). Secondary: `Entry.products` is *mutated in
place* — a same-day start-then-stop leaves no product id on that day's entry (only the fact row
records it), so the day's chips silently lose the product.

## #19 — `.env` / `data/` gitignored, export-import 唔漏 key — **VERIFIED**

**Doc claims** — `docs/status-vs-claims.md:35`（「`.env` gitignored、data gitignored、export/import
zip」）; `backend/README.md:81`; `app/export.py:1-4`.

**Ignore rules — real**

* `.gitignore:13` `.env`, `.gitignore:16` `data/`, `.gitignore:19` `.hf-cache/`;
  `git check-ignore -v` confirms all of them (quoted above), and `git ls-files` shows
  **`backend/.env.example` is the only env/data-ish tracked file**. `git grep` for
  `(sk|gho|ghp)_[A-Za-z0-9_-]{20,}` over tracked files → none found. `.env.example` is a clean
  template (empty key values). (Side note: `backend/:memory:.ses` is ignored by the accidental
  pattern at `.gitignore:20`, a stray from a shell redirect — harmless, but it is not a real rule.)

**Export/import — real, and no key can get in**

`export_zip()` walks `settings.data_dir` recursively (`export.py:14-22`) and `import_zip()`
extracts it with a traversal guard (`export.py:25-34`). `settings.data_dir` defaults to `./data`
(`config.py:19`) while secrets are read from `.env` in the CWD
(`config.py:11-15` `env_file=".env"`), so the archive cannot contain the key file. Reproduced with a
fake key planted exactly where the app reads it (`/tmp/skc-audit/export_probe.py`):

```
settings.database_url = sqlite:///./data/skincoach.db
settings.data_dir     = ./data
did .env load the key?  True
archive members: ['photos/abc.jpg', 'skincoach.db']
archive size: 257 bytes
contains .env?           False
key bytes inside blob?   False
restored files: ['photos/abc.jpg', 'skincoach.db']
db bytes match: True
photo bytes match: True
.env written into restore dir? False
```

Guarded by `tests/test_export.py:7` (round-trip byte-equality) and `:27` (traversal → `ValueError`);
mutations #19/#19b both go red.

**Caveats to state honestly (the claim is "✅" but the feature is half-wired)**

1. **Import is API-only.** `grep -rn "api/import" frontend/src` → nothing; only `/api/export` is
   linked (`RecordsView.tsx:65`, `SettingsView.tsx:142`). So "export/import zip" from the UI means
   "export link + curl to restore".
2. `import_zip` merges instead of replacing (`export.py:34`, `extractall` with no prior cleanup) and
   **overwrites the live DB with no backup, confirmation or validation** that the archive even holds
   a SkinCoach DB. A wrong zip = silent data loss, which is the opposite guarantee from
   「local-first, it's your machine」.
3. The export is "everything in the data dir", not "your record": with
   `SKINCOACH_EMBEDDER_CACHE_DIR=./data/.fastembed-cache` (the value suggested by
   `backend/.env.example`) the archive would include the whole fastembed ONNX cache, plus
   `runs.jsonl` (per-consult trace incl. `user_text`, `service.py:40-67`). The current `.env` does not
   set the cache dir and the data dir currently holds no cache, so this is latent — but the docs
   never mention it.

## #23 — delete/edit as real correction — **VERIFIED** (all three reproduced) · ⚠️ 2 of 3 unguarded

**Doc claims** — `docs/status-vs-claims.md:39`（「改 entry note、刪 entry（連相 + 同日 conv
events）、刪單相、刪 insight（清 superseded_by 指針）」）; `AGENTS.md` 陷阱條目.

**1. Entry delete: conv timeline events out, global in — VERIFIED**

* `main.py:378-396`: unlinks the entry's photo **files** (`:389-390` via `_delete_photo_file`,
  `:359-364`), deletes `Photo` rows (`:392` — bulk delete bypasses ORM cascade, as the comment
  says), deletes `TimelineEvent` for `(conversation_id=cid, date=entry.date)` (`:393`), deletes the
  entry (`:394`).
* Reproduced: `DELETE entry -> 200`; timeline became `[('2026-01-03', '食咗辣底', 'global')]`
  (conv event 「尋晚冇瞓好」 gone, global diet kept); photo **file** removed from disk:
  `file exists after: False`, `photo rows left: 0`.
* Guarded by `tests/test_api_layers.py:139`; mutation #23a goes red.

**2. Photo delete matches by path, not `Photo.id` — VERIFIED (and unguarded)**

* `main.py:399-413`: `path = f"photos/{photo_id}.jpg"`, then
  `db.query(Photo).filter_by(entry_id=eid, path=path).first()` (`:406-407`).
* Reproduced (row whose `Photo.id` deliberately differs from the file id):

```
Photo.id=26c6391daa8646e79147fc0d891a2973  Photo.path=photos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg
DELETE by Photo.id     -> 404 {'detail': 'photo not found'}
DELETE by file id      -> 200 {'status': 'ok', 'deleted': 'aaaa…'}
file removed from disk -> True
```

* The frontend derives that same id from the path (`useEntryActions.ts:35-45`,
  `JournalHome.tsx:103-104`, `RecordsView.tsx:51-59`), so client and server agree.
* ❌ **No test**: mutation #23b (match by `Photo.id`) keeps **73 passed** — the exact rule the issue
  asks about is unguarded. Also unguarded: the file-on-disk removal.

**3. Insight delete clears `superseded_by` — VERIFIED (and unguarded)**

* `main.py:416-428`: `db.query(Insight).filter(Insight.superseded_by == iid).update({"superseded_by":
  None})` (`:425`) before `db.delete(ins)` — and the pointer targeting is *any* insight, and the
  route also enforces that the row is this conversation's or global (`:422-423`).
* Reproduced (old insight superseded by new):

```
before: old.superseded_by = d89bc521c71b4f928618239797e888c0
DELETE new insight -> 200
after:  old.superseded_by = None
dangling refs left: 0
old insight visible in /summary again? True
```

* Guarded for the *global-visibility* half only (`tests/test_api_layers.py:175`; mutation #23d goes
  red). ❌ Mutation #23c (drop the pointer-clearing line) keeps **73 passed**.

**Honest consequences worth documenting**

* **Resurrection**: clearing the pointer makes the previously superseded row *active* again. Since
  nothing filters `expires_at` (see #6), a stale, contradictory insight can come back into
  `/summary` and into the coach's memory as the result of a "delete this wrong memory" action. That
  is a real correction-semantics bug in a memory system whose selling point is honest versioning.
* **Chat thread is not corrected**: `delete_entry` does not touch `ChatMessage` rows. Reproduced:
  after deleting the day's entry, `messages still there: ['下巴爆瘡', '建議…']`,
  `chat_messages rows for conv: 2`. The journal feed drops the day, the conversation still shows it.
* **Docstring precision**: the route docstring (`main.py:382-384`) says the same-day events were
  "generated for this record", but the delete removes *every* conv-scoped event on that date,
  including user-sourced `product_start`/`product_stop` confirmations that the user recorded by
  hand (`self_report.py:144-156`).

## Are the delete/edit operations reachable from the frontend, or API-only?

**Reachable — every one of them.** Evidence:

| Action | Chat shell | Journal shell | Dash shell | Implementation |
|---|---|---|---|---|
| edit entry note | ✅ `RecordsView.tsx:28-41` | ✅ `JournalHome.tsx:47-54` | ✅ via `RecordsView` tab | `PUT …/entries/{eid}` (`api.ts:135`) |
| delete entry | ✅ `RecordsView.tsx:43-49` | ✅ `JournalHome.tsx:95` | ✅ via tab | `DELETE …/entries/{eid}` (`api.ts:149`) |
| delete single photo | ✅ `RecordsView.tsx:51-59` | ✅ `JournalHome.tsx:110-117` | ✅ via tab | `DELETE /api/entries/{eid}/photos/{pid}` (`api.ts:153`) |
| delete insight | ✅ `RightPanel.tsx:86-92,165` | ✅ `JournalHome.tsx:180` | ✅ `DashHome.tsx:26,141` | `DELETE …/insights/{iid}` (`api.ts:157`) |

All three shells can reach `RecordsView`: `ChatShell.tsx:50`, and for journal/dash via the
`records` tab (`defs.ts:63` journal, `defs.ts:77` dash) rendered by `StandardShell.tsx:78`. Import (`POST /api/import`)
is the only data-layer action with **no** UI caller.

Minor drift vs `AGENTS.md`（「新結構嘅 data／動作一律用 hooks」）: only `JournalHome`/`DashHome` use
the hooks; `RecordsView.tsx:34,45,55` and `RightPanel.tsx:90` call `api.*` directly, duplicating the
`window.confirm` copy and the error handling in three places (`useEntryActions.ts:19-45`,
`useInsightActions.ts:14-21`). Not a bug — but the "single source for these actions" claim is not
true today.

## Migration safety — does it go through `_COLUMN_MIGRATIONS`, and can `init_db()` destroy data?

**The mechanism works for the columns it lists.** `db.py:44-56` inspects the live DB, then
`ALTER TABLE … ADD COLUMN` only for missing columns; `init_db()` is `makedirs` + `create_all` +
`_migrate_columns` (`db.py:59-65`). Reproduced by hand-building a Phase-1-era schema in
`/tmp/skc-audit/old_schema.db` and running the real `init_db()`:

```
entries: ['id','conversation_id','date','note','metrics','products','created_at','attributes']
insights: ['id',…,'created_at','direction']
timeline_events: ['id','conversation_id','date','text','created_at','source']
conversations: ['id','user_id','body_part','icon','created_at','cloud_analysis']
rows in entries after init_db(): [(1, '舊紀錄')]   # nothing destroyed
```

**No destroy path found.** `grep -rn "drop_all" app/ scripts/ eval/` → nothing; the only deletes are
the user-facing ones in `main.py` plus temp-file cleanup in `eval/run_eval.py:158` and
`scripts/trace_consult.py:152`. `init_db()` cannot drop or rewrite a table, so 「init_db 唔會毀
data」 is true. Four residual hazards, none of which is `init_db()` itself:

* `scripts/seed_demo.py:75-79` does `if out.exists(): out.unlink()` with **no guard**:
  `--out ./data/skincoach.db` would delete the real DB. Default is `demo.db`, so it takes a typo —
  but the doc claim 「唔掂真 data」 is enforced only by the default value.
* `import_zip` can replace the live DB with no backup (see #19 caveat 2).
* `data_dir`/`database_url` are CWD-relative (`config.py:19-20`), so starting uvicorn from the repo
  root silently uses a *different*, empty DB (repo-root `data/` exists and is empty) instead of
  `backend/data/skincoach.db`. Not destructive — but a silent "my data is gone" trap the docs never
  warn about.

### MIGRATION-1 (the real drift): `_COLUMN_MIGRATIONS` can only ADD columns, and a nullability change was never migrated

* `7d0ce75` (`2026-09-02 22:29`) made `Insight.conversation_id` and `TimelineEvent.conversation_id`
  nullable — `git log -S'conversation_id: Mapped[str | None]' -- backend/app/models.py` → `7d0ce75`
  only. Before that both were `Mapped[str]` → **NOT NULL**. Proven by replaying that commit's
  `models.py` against a temp DB:

```
insights [('id','NOT NULL'), ('conversation_id','NOT NULL'), ('kind','NOT NULL'), …]
timeline_events [('id','NOT NULL'), ('conversation_id','NOT NULL'), ('date','NOT NULL'), …]
```

* `db.py` was touched in only two commits ever (`a28ae61`, `7d0ce75`) and the migrations table at
  HEAD (`db.py:28-41`) holds **four `ADD COLUMN`s and nothing about nullability**. SQLite cannot
  drop `NOT NULL` with `ALTER TABLE`, and nothing in this repo rebuilds a table.
* Reproduced on a synthetic pre-`7d0ce75` DB (`/tmp/skc-audit/nullable_probe.py`):

```
insights [ … ('conversation_id','NOT NULL') … ]     # init_db() did NOT fix this
timeline_events [ … ('conversation_id','NOT NULL') … ]

-- global fact (POST /facts with global_scope) --
   IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: insights.conversation_id
-- confirmed diet event (must write conversation_id=NULL, Q31) --
   IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: timeline_events.conversation_id
```

* **Why this may not be latent on this machine**: `stat` (metadata only — the file was never opened)
  gives the live DB a **birth time of `2026-08-31T20:42:08`**, i.e. *between* `a28ae61`
  (`2026-08-31 19:37`, Phase 1) and `7d0ce75` (`2026-09-02 22:29`). `create_all` never changes an
  existing table and no code path recreates the file (birth time would change if it had), so the
  live 36 MB DB is very likely still `conversation_id NOT NULL` — which would make **every** global
  write path fail at runtime, i.e. exactly claim #16's "global 寫手已做":
  `POST /facts` with `global_scope=true` (`main.py:162-168`), any confirmed diet event
  (`self_report.py:124-131`), and the global diet preference (`preferences.py:106`) — the diet case
  rolls back the whole event batch at `self_report.py:158` and returns 500.
* **Not verified by me** (the DB is off-limits), and this is the single highest-value check left.
  One read-only line settles it:

```bash
sqlite3 -readonly backend/data/skincoach.db \
  "PRAGMA table_info(insights); PRAGMA table_info(timeline_events);"
# conversation_id notnull=1 anywhere  -> global writes 500 on this DB (#16/#17 broken at runtime)
# all notnull=0                       -> the schema is fine; this stays a latent trap only
```

*Smallest honest correction*: either (a) claim 「加 column 用 `_COLUMN_MIGRATIONS` auto-ALTER」
  (`docs/roadmap.md:16`) becomes 「**只限加 column**；改 nullability／型別要手動 rebuild table」, or
  (b) add the rebuild migration. Note the shape of the failure: `/health` and `/api/conversations`
  keep returning 200 while `/summary` returns 500 (reproduced on the missing-`diet` schema:
  `summary -> 500 Internal Server Error`, `correlations -> 500`), so the app looks alive while the
  records/progress views are dead — the same "green tests, broken runtime" pattern as issue #26.

*Secondary, latent-only*: `entries.diet` is **not** in `_COLUMN_MIGRATIONS` either (`db.py:32-34`
  lists only `attributes`). I first read that as a live bug and reproduced
  `OperationalError: no such column: entries.diet` → `/summary` 500. **That repro is invalid as
  evidence about this repo**: `git show a28ae61:backend/app/models.py` shows `diet` and `products`
  existed in the very first schema commit, so no shipped schema state lacks `diet`. The honest
  finding is only that the list is hand-maintained and nothing tests that it covers the models —
  mutation "remove the `direction` migration" keeps **73 passed**.

## Test-coverage summary (what would fail, what would not)

| Documented behaviour | Guarded by | Unguarded (mutation → 73 passed) |
|---|---|---|
| reconcile = tag+direction, strengthen/supersede/version | `test_memory.py:17,40,55,64` | — |
| derived expiry (pure) | `test_memory.py:73,81` | `DECAY_DAYS` value; **`persist` honouring expiry** |
| thread persistence | `test_messages.py:31,49` | the `/messages` route itself |
| diet → global timeline; `/summary` merge | `test_self_report.py:66`, `test_api_layers.py:95,115` | `get_skin_profile` global visibility; correlation using global diet causes |
| product row + `Entry.products` + per-product fact | `test_self_report.py:38` | UI id→name rendering (no engine test at all) |
| export/import round-trip + traversal guard | `test_export.py:7,27` | — |
| entry delete → photos + same-day conv events | `test_api_layers.py:139` | photo **file** removal |
| photo delete by path | — | **entirely unguarded** |
| insight delete clears `superseded_by` | — (only global-visibility half: `test_api_layers.py:175`) | **the pointer-clearing rule** |
| preferences after `apply_events` | `test_preferences.py:37-126` (direct calls only) | the `apply_events` → `extract_preferences` wiring |
| migration list covers the models | — | **entirely unguarded** |

## What I could not verify offline

1. **The live DB's column nullability / schema** — MIGRATION-1. Metadata says the file predates the
   nullable change; confirming it means opening `backend/data/skincoach.db`, which this audit was
   told not to do. The one-line `sqlite3 -readonly … PRAGMA table_info` above is the decisive check.
2. Anything requiring a real LLM round-trip (whether a real model actually emits `detected_events`
   for the confirm chips, and whether an expired-but-active insight visibly changes a real reply) —
   out of scope by constraint; the *data* the coach receives is shown above instead.
3. Real-browser reload behaviour: the frontend chain was verified by reading
   `api.ts`/`App.tsx`/`format.ts`, not by driving a browser.
