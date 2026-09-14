# Agent core audit — rows #1, #3, #4, #5, #26, #27 (issue #2)

Scope: `backend/app/agent/` (`graph.py`, `service.py`, `llm.py`, `schemas.py`, `prompts.py`, `tools.py`, `state.py`), `backend/app/config.py`, `backend/app/photo.py`, `backend/app/main.py`, `backend/scripts/trace_consult.py`, `backend/eval/`, `backend/tests/`, plus the frontend surfaces that consume `vision_used`.
Method: read the exact code path **and** run it. No app code was modified, no real LLM API was called, the real embedder was never instantiated, `backend/data/skincoach.db` was never opened (API probes ran against a temp DB and a monkeypatched `DeterministicEmbedder`).

## Commands actually run (quoted output)

```
$ cd backend && ./.venv/bin/python -m pytest -q
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 1.81s

$ cd backend && ./.venv/bin/python -m eval.run_eval --fake >/dev/null 2>&1; echo $?
eval --fake exit code: 0

$ cd backend && ./.venv/bin/python scripts/trace_consult.py --text "下巴爆瘡點算？"
LLM: FakeLLM / vision: FakeLLM | embedder: DeterministicEmbedder
▸ analyze  (0.1 ms)  {"has_photo": false, "cloud_consent": false, "vision_attempted": false, "vision_used": false, "images_loaded": 0, "vision_error": null, "tool_calls": ["get_skin_profile", "search_knowledge"], "attributes": 3, "metrics": 2}
▸ tools  (5.3 ms)    {"requested": ["get_skin_profile","search_knowledge"], "ran": [{"tool":"get_skin_profile","rows":0,"error":null},{"tool":"search_knowledge","rows":1,"error":null}], "recent_messages": 0, "first_checkin": true}
▸ advise  (0.0 ms)   {"prompt_chars": 708, "tool_rows": 1, "items": 2, "reply_chars": 99, "detected_events": 0}
▸ guardrail  (0.0 ms) {"escalate": false, "items_replaced": 0, "disclaimer_added": true}
▸ persist  (8.9 ms)  {"entry_reused": false, "attributes": 3, "photos_added": 0, "timeline_lines": 0, "insights_created": 3, "insights_strengthened": 0, "insights_superseded": 0}
escalate=False vision_used=False
```
(The five `▸` lines are the trace exactly as printed by `trace_consult.py`; only the `tools` line was reflowed from the console's wrapped form onto one line — values unchanged. The full `seed_demo`-free run wrote 3 insights + 2 chat messages into a throwaway temp DB, which is what the `persist` line reports.)

Environment: langgraph 1.2.11, langchain-core 1.6.1, langchain-openai 1.6.0, pydantic 2.13.5.
Extra probes (throwaway scripts under `/tmp/skc_probe/`, nothing written into the repo): consent/byte gating, missing-photo silent degrade, no-key adapter selection, tool-dispatch matrix, drift-gate firing, `POST /api/consult` run-log write, checkpointer/continuity, provider-resolution matrix, vision request payload construction, schema-description propagation.

## Verdicts

| Row | Verdict | One-line reason |
|---|---|---|
| #1 vision | **VERIFIED** (1 caveat, 1 offline gap) | Photo really is read → base64 → `vision-exp` only after consent; text path says "睇唔到張相"; badge is flag-driven but the false branch is a claim. |
| #3 tiering | **DRIFT (minor — reporting, not routing)** | Routing matches the table for the shipped DeepSeek config; no dead config; but `/health` + `/api/settings` can name a model that is *not* the one serving analyze/advise. |
| #4 no Ollama / FakeLLM | **DRIFT** | No Ollama, FakeLLM is deterministic — but a FakeLLM turn is written into the real DB and rendered identically to a real analysis, with no marker anywhere. |
| #5 checkpointer | **VERIFIED** | `checkpointer: None`; continuity = last 10 `ChatMessage` rows + `Insight` memory, injected into the advise prompt (shown). |
| #26 tool discovery | **VERIFIED** (gate exists and fires; 2 documented limits) | All three sources agree exactly, description reaches the provider payload, pytest gate fires on drift. |
| #27 observability | **DRIFT** | Every node is traced and the run log *works* — but `data/runs.jsonl` is absent because the documented debug CLI never writes it, and embedder fallback + one vision failure mode never reach the trace. |

---

## #1 vision — VERIFIED (caveats C1, offline gap O1)

**Doc claims** — `docs/status-vs-claims.md:17`: "analyze 有相＋`cloud_analysis` consent → 送 `deepseek-v4-flash-vision-exp`；off 時純文字並標「未睇相」；UI badge 顯示"; the same row itself adds "需真實相 smoke test 過" (checklist `docs/status-vs-claims.md:54`). `AGENTS.md:53` ("送相上雲前一定要 check conversation `cloud_analysis`…唔好同 model 講「無相」").

**What code + run shows**

1. Consent is a code gate *before* the bytes are touched. `backend/app/agent/graph.py:87-89`:
   ```python
   has_photo = bool(state.get("photo_paths"))
   consent = bool(state.get("cloud_analysis"))
   vision = has_photo and consent and not isinstance(vllm, FakeLLM)
   ```
   and `load_photo_b64` is only reached inside `if vision:` (`graph.py:94-100`). The consent value comes from the DB row, not the request body: `service.py:71-78` reads `conv.cloud_analysis` and passes it into the graph state (`service.py:86-94`); `main.py:190-193` never accepts a consent flag from the client.
   Probe (real JPEG on disk, `cloud_analysis=False`, tracing `graph.load_photo_b64`):
   ```
   === B) photo + consent=False (bytes must NOT be read) ===
   vision model called: 0 | load_photo_b64 calls: 0 | vision_used: False
   ```
   Same probe with `cloud_analysis=True`:
   ```
   vision model called: 1 | images: 1 | b64 chars: 844 | media_type: image/jpeg
   photo file read calls: 1 | vision_used: True
   analyze prompt sent to vision model: （有用戶上傳嘅皮膚相，相已附上俾你分析）
   ```
2. The photo really becomes provider bytes on the `deepseek-v4-flash-vision-exp` adapter. `llm.py:125-137` builds an OpenAI-compatible `image_url` data URL; intercepting the runnable (no network):
   ```
   adapter model id: deepseek-v4-flash-vision-exp | base_url: https://api.deepseek.com/v1
   human content blocks: ['text', 'image_url']
   image_url prefix: data:image/jpeg;base64,/9j/4AAQSkZ ... | total chars: 883
   payload decodes to real JPEG bytes: True
   ```
   The model id comes from `config.py:35` via `service.py:82` (`get_llm("vision")` → `llm.py:150-152`).
3. The text-only path says "there is a photo but I can't see it", not "there is no photo" — `prompts.py:47-51`, emitted only when `has_photo and not photo_viewed`. Verified string (printed by the probe, matching `prompts.py:49-50` verbatim, including the trailing clause "唔好話用戶冇提供相片"):
   `（用戶上傳咗皮膚相，但而家係本地模式：相唔會離開用戶部機、你睇唔到張相。請只靠文字評估，並喺回覆講明你睇唔到張相，唔好話用戶冇提供相片。）`
4. Badge: `frontend/src/components/Chat.tsx:76-79` renders `👁 已睇相分析（雲端）` / `✍️ 文字分析（未睇相）` from `m.vision_used`; the live turn takes it from the API response (`App.tsx:164` ← `res.vision_used`, forced to `bool` at `service.py:95`), reload takes it from the persisted payload (`format.ts:58` ← `payload.vision_used`, written at `graph.py:398`). Verified the payload key exists on a real write: `payload keys: ['advice','attributes','disclaimer','escalate','metrics','reply','summary','vision_used'] | value: False`.

**Caveat C1 (badge can render without a flag).** `vision_used` is optional in the UI type (`frontend/src/types.ts:54`), `format.ts:58` passes it through without a default, and `Chat.tsx:78` treats *any* falsy value as a positive negative claim ("未睇相"). Producers that omit it are reachable: any coach message persisted before the field existed (the payload dict has no schema), and `POST /api/import` restores a whole foreign data dir (`app/main.py:88-91` → `app/export.py:25-34`), so an imported thread renders "✍️ 文字分析（未睇相）" for turns that may in fact have been vision-analysed. Smallest honest correction: make `vision_used` non-optional and render a third, non-committal state (`未記錄`) when the key is absent.

**Offline gap O1.** "Is a photo ever *really* sent" cannot be closed offline: I verified framing, model id, adapter payload and gate, but the network leg was not exercised (constraint: no real API calls). The row already flags this as an open pre-interview item, so the doc is honest here, not overclaiming.

---

## #3 tiering — DRIFT (minor: reporting, not routing)

**Doc claims** — `docs/status-vs-claims.md:19`: "✅ 分層：analyze=vision-exp、advise/text=deepseek-v4-flash；dead config 已刪"; `docs/architecture.md:28,83`.

**What code + run shows (routing matches the docs).**
- `analyze` uses the **vision** adapter only on the photo+consent path (`graph.py:89,103-108` → `vllm = vision_llm or llm`, `graph.py:83`); every other analyze (no photo, or consent off, or FakeLLM) uses the **text** adapter (`graph.py:114-115`). So the table's "analyze=vision-exp" is conditional, not absolute.
- `advise` always uses the text adapter: `graph.py:207` `advice = llm.structured(ADVISE_SYSTEM, prompt, Advice)`.
- `service.py:80-85` wires both adapters correctly (`llm=get_llm("text")`, `vision_llm=get_llm("vision")`); `config.py:34-35` = `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp`.
- Probe of `get_llm`:
  ```
  provider=deepseek + deepseek key      text-> OpenAICompatLLM:deepseek-v4-flash  vision-> OpenAICompatLLM:deepseek-v4-flash-vision-exp
  ```
- Dead config: **none found.** Every field in `config.py:17-59` is referenced somewhere (`settings.X` usage count ≥ 1 for all 16 fields, including `cloud_analysis_default` → `crud.py:35`), and every variable in `.env.example` maps to a real field. No `ollama`/`bge-m3`/`deepseek-chat` dead config remains outside of explanatory comments (`config.py:25`, `backend/README.md:39`, `.env.example:3`).

**The drift (verified by probe).** `llm_provider` is only honoured when a matching key exists; otherwise the resolver silently switches provider (`llm.py:154-165`):
```
provider=openai, ONLY anthropic key set   text-> AnthropicLLM:claude-sonnet-5  vision-> AnthropicLLM:claude-sonnet-5
provider=gemini (typo/invalid) + deepseek key  text-> OpenAICompatLLM:deepseek-v4-flash  vision-> ...vision-exp
```
Meanwhile the two read-only endpoints report the *configured* provider/model, not the effective one: `main.py:73-75` returns `{"status":"ok","app":"SkinCoach","llm_provider":"deepseek"}` and `main.py:333-351` returns `model`/`vision_model` derived from `settings.llm_provider` (`main.py:341-343` also sets `vision_model = text_model` for every non-DeepSeek provider). Observed live with **no key set at all**: `GET /health -> {'status': 'ok', 'app': 'SkinCoach', 'llm_provider': 'deepseek'}` while `get_llm("text")` returned `FakeLLM`.
Smallest honest correction: have `/api/settings` (and `/health`) report the *resolved* adapter — e.g. `type(get_llm("text")).__name__` plus `getattr(llm, "model", None)` — or fail loudly when `llm_provider` has no matching key instead of falling through. Otherwise the row's "分層" claim is true for the shipped config but the one place a reader would check it lies.

---

## #4 no Ollama / FakeLLM — DRIFT

**Doc claims** — `docs/status-vs-claims.md:20`: "冇 Ollama；冇 key = FakeLLM 示範模式"; `docs/architecture.md:53` "冇 API key 時行 FakeLLM（deterministic 罐頭輸出…）—— 唔係 Ollama"; `AGENTS.md:53` (privacy consent is a code gate), `AGENTS.md:75` ("FakeLLM 唔係「真 offline」" — about the embedder, not the LLM).

**What code + run shows.**
- No Ollama anywhere: grep for `ollama` over tracked files matches only prose that says it does not exist.
- Selection is deterministic: `llm.py:140-166` — configured provider *with* key → that adapter; else first key present (deepseek → anthropic → openai); else `FakeLLM()`. Probe with all keys blank: `get_llm('text') -> FakeLLM | get_llm('vision') -> FakeLLM`. With consent + a photo and `FakeLLM` as the vision adapter, the graph short-circuits to text-only (`graph.py:89` `not isinstance(vllm, FakeLLM)`), so a fake never pretends to have seen an image — `vision_used` stays `False`.

**The drift: a fake answer IS presented as a real analysis in a real data path.** Probe (no keys, temp DB, real graph through the persisted path):
```
result keys returned to /api/consult: ['advice','analysis','cloud_analysis','conversation_id','escalate','first_checkin','photo_paths','recent_messages','tool_results','trace','user_text','vision_used']
any 'fake'/'demo'/'mode' marker? []
Entry written from FakeLLM analysis -> attributes: [('acne', 2), ('oiliness', 2), ('redness', 1)] | metrics: [{'key':'新暗瘡','value':'+2','dir':'bad'}, {'key':'油光','value':'-18%','dir':'good'}]
coach msg text starts: 睇咗你嘅情況：下巴有兩粒新暗瘡、T 字位偏油，兩頰就中性 | payload['vision_used']: False
```
So with no key the canned Cantonese analysis is persisted as a genuine `Entry` (`graph.py:259-267`) and a genuine coach `ChatMessage` (`graph.py:385-401`), returned with no provenance field, and rendered by `Chat.tsx:76-79` exactly like a real answer. Two further provenance holes: the trace records no adapter/model id (each node only logs its own counters, `graph.py:62-69`), and `GET /health` still reports `llm_provider: deepseek` (above). The only tell is in a different screen (`SettingsView.tsx:80` `未設定（會用 FakeLLM）`, fed by `has_api_key` from `main.py:348-350`).
Smallest honest correction (either one):
1. add `"llm_mode": "fake" | "live"` + resolved model ids to the `run_consult` result and to the run-log record (`service.py:47-63`, `service.py:95-96`), and render a "示範模式（無 API key）" chip in the chat bubble next to the vision badge; or
2. refuse to persist FakeLLM turns into a real conversation (keep them session-only), so canned output can never become data truth.

---

## #5 checkpointer — VERIFIED

**Doc claim** — `docs/status-vs-claims.md:21`: "冇用 checkpointer；stateless consult + SQLite + 最近 10 條 messages"; `docs/architecture.md:46`.

**What code + run shows.** `build_graph` ends with `g.compile()` and no `checkpointer=` argument (`graph.py:423-435`); no conditional edges, no `thread_id`, no `Saver` anywhere in tracked Python (grep for `checkpointer|Saver|thread_id` returns nothing under `backend/`). Probe:
```
compiled graph type: CompiledStateGraph | checkpointer: None
```
Continuity comes from three DB-backed sources, all inside the graph:
- last 10 chat turns, oldest-first, rendered as `你：…/教練：…` — `graph.py:160-170` (`.limit(10)`, `reversed`), injected into the advise prompt by `prompts.py:59-61`;
- long-term `Insight` memory read by the `get_skin_profile` tool (`tools.py:17-42`, conversation-scoped **plus** global `conversation_id IS NULL`);
- the day's `Entry` upsert + change detection (`graph.py:259-306`).
Probe of two consecutive turns in one conversation (`我今日食咗辣`, then `咁我點算？`):
```
-- turn: 咁我點算？ | tools trace recent_messages=2 first_checkin=False
   advise prompt continuity block:
     | 最近對話（供參考，唔好重複問）:
     | 你：我今日食咗辣
     | 教練：睇咗你嘅情況：…
```
This is a fair reading of "conversational continuity": the doc's account is accurate. (Note the practical limit: it is a 10-turn window, and `run_agent_eval` runs all three scenarios against one conversation, so scenario 2/3 also see scenario 1's turns — harmless for the current gates but worth knowing when adding scenarios.)

---

## #26 tool discovery — VERIFIED (two documented limits D2, D3)

**Doc claims** — `docs/status-vs-claims.md:43`: the prompt never named any tool → real DeepSeek returned `tool_calls: []` → retrieval/memory never ran → hidden behind 60 green tests; fix = `prompts.TOOL_GUIDE` + schema description + an `expect_tool` eval gate; "✅ 已修＋有 test／eval gate". `AGENTS.md:76` names `tests/test_observability.py` as the enforcing test.

**What code + run shows.**
1. All three sources agree **exactly** (probe):
   ```
   WHITELIST               : ['get_recent_entries', 'get_skin_profile', 'search_knowledge']
   TOOL_GUIDE bullet names : ['get_recent_entries', 'get_skin_profile', 'search_knowledge']
   schema description names: ['get_recent_entries', 'get_skin_profile', 'search_knowledge']
   all three identical?    : True
   TOOL_GUIDE inside ANALYZE_SYSTEM: True
   ```
   Sources: `tools.py:13`, `prompts.py:11-19` (concatenated into `ANALYZE_SYSTEM` at `prompts.py:27`), `schemas.py:40-47`.
2. The description is not cosmetically lost in the pydantic→provider conversion (the trap flagged in `AGENTS.md`). Converting the schema the same way `OpenAICompatLLM._runnable` does (`llm.py:117-120`, `with_structured_output(..., method="function_calling")`) yields:
   ```
   provider payload description: "要執行嘅工具名，只可以用：get_skin_profile（讀長期記憶）、get_recent_entries（讀最近紀錄）、search_knowledge（檢索護膚知識庫）。唔需要就留空 array。"
   ```
3. **The gate exists and I made it fire.** `tests/test_observability.py:78-81` (TOOL_GUIDE ↔ WHITELIST), `:84-86` (guide inside ANALYZE_SYSTEM), `:89-92` (schema description names every whitelisted tool). Injecting a tool into the whitelist without touching the prompt/description:
   ```
   === GATE 1: pytest gate vs TOOL_GUIDE/WHITELIST drift ===
   RESULT: gate FIRED -> prompt 講嘅 tool {...} ≠ whitelist {...'retrieve_beauty_kb'...}
   schema-description gate FIRED ->
   ```
   Baseline (unmodified) run of the same tests: `tests/test_observability.py ... 13 passed in 0.89s`; the four tool-discovery tests individually `4 passed in 0.58s`.
4. **The eval side also fires, but only for the failure mode it can see.** `eval/agent_eval.py:41-43` is the `expect_tool` gate; `eval/scenarios.json` puts `"expect_tool": "search_knowledge"` on two of three scenarios. Replacing the model's tool list with `[]` (exactly what pre-fix real DeepSeek did):
   ```
   --fake, FakeLLM hardcoded tools        -> exit 0
   --fake, model returns tool_calls:[]    -> exit 1
   acne_normal: FAIL (... tools: 冇 tool 跑過)
   dry_normal: FAIL (... tools: 冇 tool 跑過)
   ```

**Limit D2 — why this bug hid, and still would in CI.** With `--fake` the eval feeds `FakeLLM`, whose `tool_calls` are hardcoded (`llm.py:36`) and whose `structured()` ignores the system prompt entirely, so CI (`pytest -q` + `eval.run_eval --fake`, `.github/workflows/ci.yml`) can *never* reproduce the #26 failure mode; the eval gate only bites on a real-LLM run (`run_eval.py:66` `llm = get_llm("text")`), which CI does not do. The regression protection that actually holds is the *source-sync* pytest gate above. The row's phrasing "已修＋有 test／eval gate" is therefore true but reads stronger than reality: the eval half is inert in CI by construction, and the honest correction is to say so ("pytest gate covers prompt/schema/whitelist drift; the eval `expect_tool` gate only covers a real-LLM run and is therefore not exercised in CI").

**Limit D3 — one stale pointer.** `prompts.py:6-7` says the invariant is "enforced by tests/test_prompts.py". That file does not exist (`backend/tests/` has no `test_prompts.py`); the real enforcer is `tests/test_observability.py:78-92`. Smallest correction: fix the filename in that comment.

---

## #27 observability — DRIFT (three concrete defects C2/C3/C4)

**Doc claims** — `docs/status-vs-claims.md:44`: node trace + `graph.stream()` + `/api/consult` returns the trace + `data/runs.jsonl` run log + `trace_consult.py` CLI, and "vision／tool 失敗同 embedder fallback 由「靜靜吞」改為 log + trace"; `AGENTS.md:78,101` the same, including "`data/runs.jsonl` 留紀錄" and "embedder fallback 全部要 log + 入 trace"; checklist `docs/status-vs-claims.md:60` "`scripts/trace_consult.py --text …`；`data/runs.jsonl` 有紀錄".

**What is verified.**
- Every node is traced, in order, with ms + a small detail dict: `graph.py:62-69` (`_step`), returned by all five nodes (`:120-136`, `:181-199`, `:210-226`, `:237-247`, `:404-418`), merged via `state.py:35` (`Annotated[list, TraceStep], operator.add`). Both the CLI and the API show `['analyze','tools','advise','guardrail','persist']` (quoted output above; API probe below).
- The run log genuinely works when the API path is used. Probe A (temp DB, `DeterministicEmbedder` monkeypatched in, no keys, `SKINCOACH_RUN_LOG_PATH` pointed at a temp file):
  ```
  POST /api/consult status: 200
  trace nodes in response: ['analyze', 'tools', 'advise', 'guardrail', 'persist']
  runs.jsonl exists before: False ... runs.jsonl exists after : True
  run log keys: ['conversation_id','escalate','tool_calls','tools','trace','ts','user_text','vision_used']
  run log trace nodes: ['analyze','tools','advise','guardrail','persist']
  ```
- `settings.run_log_enabled` default is **True** (`config.py:58`), and `backend/.env` sets no `SKINCOACH_RUN_LOG_ENABLED` (only provider, three keys, database URL, cloud default). So the gate is **open** — `.wayfinder/map.md:31`'s implication that the absent file is explained by `run_log_enabled` (it even cites `config.py:59`, which is `run_log_path`) is wrong.

**C2 — `backend/data/runs.jsonl` is absent, and the documented debug route cannot create it.** `find . -name runs.jsonl` → nothing (the file is also gitignored via `.gitignore:16` `data/`). The only writer is `service._write_run_log` (`service.py:40-67`), called only from `service.run_consult` (`service.py:96`), which is called only by `POST /api/consult` (`main.py:190-193`). `scripts/trace_consult.py` builds the graph itself (`trace_consult.py:36-41`, `:109`) and never touches `service` — so `trace_consult.py --text "…"` can never produce a run-log line, and the checklist item "`trace_consult.py …`；`data/runs.jsonl` 有紀錄" (`status-vs-claims.md:60`) is false as written. Supporting evidence that the API was simply never called with run logging on: the only HTTP request line in `backend/data/server.log` (line 5) is `INFO: 127.0.0.1:54185 - "GET /health HTTP/1.1" 200 OK`, between a startup and a shutdown — no consult request was ever served; and the newest real data file (`data/skincoach.db`, mtime 2026-09-10) predates the run-log code (mtime 2026-09-12). So the *claim* is true of the code path and false in practice for this working tree — and the "cause" is not the feature flag but "no `POST /api/consult` has run since, plus the CLI's bypass".
Smallest honest correction: add a `--log` (or always-on) call to `service._write_run_log`-equivalent in `scripts/trace_consult.py`, **or** rewrite the checklist line to "run log 只喺 `POST /api/consult` 之後出現；CLI trace 唔會寫 run log".

**C3 — embedder fallback is logged but never traced, contradicting the "log + trace" claim.** The fallback lives inside the embedder, which is not a graph node: `backend/app/rag/embeddings.py:68-77` (`logger.warning` on model-load failure) and `:83-85` (per-call fallback). Nothing in `graph.py`'s trace mentions the embedder, and no node records an embedder/model identity, so a consult that silently downgraded to the 128-dim hashing embedder shows only `tools.ran[].rows = 0` (`graph.py:187-194`) with no stated reason. Same class: dimension-mismatched chunks are warning-logged in `vectorstore.py:86-89` and skipped, again invisible in the trace. Smallest honest correction: either add an `embedder` trace step/field (adapter class + dim, read from the tools node) or soften both docs to "log only" for the embedder.

**C4 — one vision failure mode is still swallowed, and the trace then states something untrue.** `graph.py:94-116`:
```python
if vision:
    images = [img for pid in state["photo_paths"] if (img := load_photo_b64(pid)) is not None]
    images_loaded = len(images)
    if images:            # <-- empty images: no exception, no error recorded
        try: analysis = vllm.structured_vision(...)
        except Exception as e: vision_error = f"{type(e).__name__}: {e}"; ...
if analysis is None:
    analysis = _text_only_analysis(llm, state, has_photo)
    vision = False        # <-- reset happens BEFORE the trace is built
```
Probe: consent ON, photo id of valid shape but no file on disk →
```
analyze trace: {'has_photo': True, 'cloud_consent': True, 'vision_attempted': False, 'vision_used': False, 'images_loaded': 0, 'vision_error': None}
text-path prompt note: '（用戶上傳咗皮膚相，但而家係本地模式：相唔會離開用戶部機、你睇唔到張相。…）'
```
Two honest problems: (a) `vision_attempted` is reported `False` even though the code *did* enter the vision branch — the flag is computed from the post-reset variable (`graph.py:127`), so the trace misleads a debugger; (b) the model is told "本地模式" (photos never leave the machine) when consent was actually granted and the real cause is an unreadable photo — a fabricated privacy explanation that the model is then instructed to relay to the user (`prompts.py:49-50`). The exception path is fine (test `test_trace_records_vision_failure_instead_of_swallowing`, `tests/test_observability.py:156-176`), and "tool 例外／未知 tool 名" genuinely are logged + traced (below). Smallest honest correction: compute `vision_attempted = bool(has_photo and consent and not isinstance(vllm, FakeLLM))` before the fallback, add `"images_loaded": 0, "reason": "photo_unreadable"` to the detail, and give the model a distinct note for "photo attached but unreadable" instead of the local-mode one.

**Bonus finding (gate honesty, same eval file).** `eval/run_eval.py:87-91` measures hybrid retrieval and the comment says it is measured "otherwise a hybrid regression would be invisible here" — but the exit code ignores it: `run_eval.py:153-156` computes `failed` only from `recall["results"]` (the pure-semantic baseline) and `agent_results`. Demonstrated by making the hybrid retriever return `[]`:
```
## Hybrid（runtime path，同一 golden set）recall: 0% · MRR: 0.00
- oily: FAIL (rank=None) … (all five FAIL)
--fake with hybrid retriever returning [] -> exit 0     # CI stays green
```
The runtime retrieval path (`tools.search_knowledge` → `search_hybrid`, `tools.py:11,70`) can therefore regress completely while `eval.run_eval --fake` exits 0. Smallest honest correction: include `recall_hybrid["results"]` in the `failed` expression (or drop the comment's promise).

---

## Facts requested by the issue

**Nodes and edges** (`graph.py:423-435`, verified at runtime: `trace nodes in response: ['analyze','tools','advise','guardrail','persist']`):
```
START -> analyze -> tools -> advise -> guardrail -> persist -> END
add_node: analyze, tools, advise, guardrail, persist  (5)
edges: START->analyze, analyze->tools, tools->advise, advise->guardrail,
       guardrail->persist, persist->END
```
There are **no** conditional edges and no `add_conditional_edges` call anywhere in `backend/app` or `backend/eval` — the graph shape is strictly linear. `START` is not a node and is not traced; the first trace entry is `analyze`.

**Does the `tools` node dispatch unconditionally?** Yes. `graph.py:430` is a plain edge, so `tools` runs on every consult even when the model asked for nothing; it is the node that also assembles `recent_messages` + `first_checkin` (`graph.py:158-180`), so it is load-bearing beyond tools. Probe matrix:

| model's `tool_calls` | nodes visited | `tools` trace | outcome |
|---|---|---|---|
| `[]` | all 5 | `{'requested': [], 'ran': [], 'recent_messages': 0, 'first_checkin': True}` | `tool_results=[]`, advise still produced |
| `["retrieve_beauty_kb"]` (unknown) | all 5 | `ran:[{'tool':'retrieve_beauty_kb','rows':None,'error':'unknown tool (not in whitelist)'}]` | error recorded, `stderr: tool retrieve_beauty_kb is not in the whitelist — ignored`, consult completes |
| `["search_knowledge","hack_the_planet"]` | all 5 | `search_knowledge rows=1` + unknown-flagged sibling | good tool still runs, bad one ignored, advise produced |

**Zero tool calls** → no exception, empty `tool_results`; `build_advise_prompt` still emits `工具結果：[]` (`prompts.py:74`) and the advice is generated (verified: `advise_ok=True`).
**Unknown tool name** → double-flagged: `run_tool` returns `{"result": None, "error": "unknown tool (not in whitelist)"}` (`tools.py:72-74`) and `graph.py:152-154` re-checks and `logger.warning`s; the trace carries `rows: None` + the error (`graph.py:187-194`).
**Tool that raises** → caught per-tool at `graph.py:149-151`: `{"result": None, "error": "TypeError: …"}` + `logger.warning`, the loop continues and the consult still completes (also locked in by `tests/test_observability.py:137-153`). Note `run_tool` is resolved at call time (`graph.py:148`), which is what makes the test's monkeypatch able to simulate it.
One naming wrinkle worth recording: because `state["analysis"]` is a `model_dump()` dict, the tool names arrive as arbitrary strings; the whitelist is enforced at execution, never at `analyze` time — so a hallucinated name is a logged no-op rather than a validation error. That is a deliberate design (`tools.py:1-6`), and it is correctly *observed*.

**Where the run log is written** — `Path(settings.run_log_path)` opened in append mode (`service.py:45-46,64-65`), `parent.mkdir(parents=True, exist_ok=True)`, one JSON line per consult, no photos/keys (`service.py:47-63`); failures are `OSError`-guarded so a read-only data dir cannot 500 a consult (`service.py:66-67`). Path is **CWD-relative**: `config.py:59` `run_log_path = "./data/runs.jsonl"` → `backend/data/runs.jsonl` only when the server is started from `backend/` (as `AGENTS.md:9` instructs); started from the repo root it would land in the (currently empty) root `data/`. Default `run_log_enabled = True` (`config.py:58`). Each consult also returns the full trace to the client (`main.py:190-193` → `service.py:86-97`).

---

## Bottom line

- Rows **#1, #5, #26** are true as written (with C1's badge caveat, D2/D3's gate caveats, and the row's own honest "needs a real-photo smoke test").
- Rows **#3, #4, #27** each claim more than the code delivers: #3's tiering is real for the shipped config but the endpoints that report it can name the wrong model; #4's "示範模式" is not distinguishable from a real analysis anywhere in the real data path; #27's `data/runs.jsonl` claim is false in practice because the documented CLI never writes it, and "embedder fallback … 入 trace" is not implemented at all. C4 (silent unreadable-photo degrade that also tells the model a false privacy reason) is the one residual silent-failure hole in an otherwise genuinely instrumented graph.
- The #26 lesson still stands and is worth generalising: this suite's green light is not evidence about model behaviour. The only gates that bite in CI are source-level assertions (`tests/test_observability.py:78-92`); every behavioural gate here (`expect_tool`, judge) needs a real key, and the hybrid recall number — the runtime retrieval path — is printed but not gated.
