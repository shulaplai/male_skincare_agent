# Real-environment verification — Agent-runnable half (GitHub issue #8)

Issue: `shulaplap/male_skincare_agent#8` — "Real-environment verification: vision, real tool calls, judge, Docker"
Scope of this report: **the "Agent-runnable" half only.** The "Human-in-the-loop" half (Docker Desktop,
a genuine photo uploaded through the UI) was **not attempted** and is **not claimed**.

- Date/time of runs: **2026-09-14, 20:43–20:47 (+0800)**
- Machine state: working tree shared with parallel audits. No tracked file was modified by this audit.
- Raw logs (verbatim, unedited): `research/logs/*.txt`
- Not posted to GitHub (per brief).

---

## 0. Verdict summary

| Row | Claim | Verdict after this run |
|---|---|---|
| **#26** | "AI 會用工具／RAG 檢索" — after the `TOOL_GUIDE` fix, a real LLM returns all three tool names | **VERIFIED for the issue's own input** (3/3 tools requested, all 3 executed, `search_knowledge` returned 1 row). **But not robust**: the same `analyze` LLM call **crashes on other inputs** — 5 of 7 real calls in this audit failed. See §4. |
| **#11** | "`eval/judge.py` 接線：有 key 時逐 scenario 評分；--fake skip" | **HALF-VERIFIED.** `judge.py` itself is **VERIFIED working with a real key** (real 1–5 scores returned, §3), and the `--fake` skip is **VERIFIED** (§3c). The *"逐 scenario 評分"* harness wiring is **UNVERIFIED** — `python -m eval.run_eval` (real) **aborts before step 3** because step 2 crashes, so no per-scenario judge scores were ever produced by the harness. |
| **#1** | real vision smoke test | **UNVERIFIED as written** (needs the human: genuine photo via the UI + badge). The *backend* vision path was exercised separately and works — **with a caveat that undermines confidence in it**: see §2 and §5. |
| **#18** | `docker compose up --build` | **NOT ATTEMPTED** (human-in-the-loop; out of scope by the brief). |

**Headline finding: the real-LLM `analyze` stage is unreliable.** With a valid key and a valid model,
`OpenAICompatLLM.structured(SkinAnalysis)` fails **5/7 times** with a `langchain` `OutputParserException`
caused by the provider returning a tool call named after one of the RAG tools. Consequences: the real
`eval.run_eval` gate (and therefore the `expect_tool` gate and the LLM-as-judge stage) cannot complete,
and `/api/consult` can 500 on the same class of response.

---

## 1. Item 1 — `trace_consult.py --real` (row #26 + vision-path behaviour)

### 1a. DB target confirmed *before* running (as the brief requires)

`backend/scripts/trace_consult.py:49–67` (`build_target`): with the default `--db temp` it creates a
`tempfile.NamedTemporaryFile(prefix="skincoach_trace_", suffix=".db")`, runs `Base.metadata.create_all`
on it, and `os.unlink`s it at the end (line 151–152). `backend/data/skincoach.db` is only opened when
`--db dev` (or an explicit path) is passed. The `--real` flag only swaps `FakeLLM` → `get_llm("text"/"vision")`
(lines 104–105); it does **not** change the DB target.

**Conclusion: the brief's exact command writes to a temp DB only.** I ran it exactly as specified, with no
`--db` override.

### 1b. Exact command + observed output

```
cd backend
./.venv/bin/python scripts/trace_consult.py --real --text "下巴爆瘡點算？"
```

Timestamp: `START 2026-09-14T20:43:20+0800` → `END 2026-09-14T20:43:29+0800` (8.6 s). Exit code 0.
Verbatim output:

```
LLM: OpenAICompatLLM / vision: OpenAICompatLLM | embedder: DeterministicEmbedder
conversation: 7d3fea95afe64286808bcaf93b0fc835
user_text: 下巴爆瘡點算？

▸ analyze  (3152.8 ms)
    {"has_photo": false, "cloud_consent": false, "vision_attempted": false, "vision_used": false, "images_loaded": 0, "vision_error": null, "tool_calls": ["get_skin_profile", "get_recent_entries", "search_knowledge"], "attributes": 6, "metrics": 1}
▸ tools  (7.5 ms)
    {"requested": ["get_skin_profile", "get_recent_entries", "search_knowledge"], "ran": [{"tool": "get_skin_profile", "rows": 0, "error": null}, {"tool": "get_recent_entries", "rows": 0, "error": null}, {"tool": "search_knowledge", "rows": 1, "error": null}], "recent_messages": 0, "first_checkin": true}
▸ advise  (4213.5 ms)
    {"prompt_chars": 944, "tool_rows": 1, "items": 5, "reply_chars": 412, "detected_events": 0}
▸ guardrail  (0.0 ms)
    {"escalate": false, "items_replaced": 0, "disclaimer_added": true}
▸ persist  (27.6 ms)
    {"entry_reused": false, "attributes": 6, "photos_added": 0, "timeline_lines": 0, "insights_created": 6, "insights_strengthened": 0, "insights_superseded": 0}
```

Persist / reply tail (verbatim, trimmed only where marked):

```
──────── 呢次 run 寫咗落 DB ────────
Entry 2026-09-14: attributes=6 diet=[] products=[]
  note: 下巴爆瘡點算？
Insight [derived/acne/problem] conf=0.6 v1: 暗瘡：中等
Insight [derived/oiliness/normal] conf=0.6 v1: 油光：正常
Insight [derived/redness/normal] conf=0.6 v1: 泛紅：正常
Insight [derived/dryness/normal] conf=0.6 v1: 乾燥：正常
Insight [derived/pores/normal] conf=0.6 v1: 毛孔：正常
Insight [derived/texture/normal] conf=0.6 v1: 質感：正常
ChatMessage [coach] 先講重點：今次你係文字講「下巴爆瘡」，我按你講嘅嘢評咗——下巴位屬中等程度嘅局部爆發（acne severity 2）， | payload keys=['advice', 'attributes', 'disclaimer', 'escalate', 'metrics', 'reply', 'summary', 'vision_used']
ChatMessage [user] 下巴爆瘡點算？ | payload keys=['photos']

──────── 回覆 ────────
reply: 先講重點：今次你係文字講「下巴爆瘡」，我按你講嘅嘢評咗——下巴位屬中等程度嘅局部爆發（acne severity 2），其餘油脂、泛紅、乾燥、毛孔、紋理呢幾項暫時當正常，因為未有相睇到。下巴爆瘡最常見同三個因素有關：荷爾蒙波動、口罩長時間摩擦焗住、同埋下巴位清潔/護膚品殘留…（下略，全文見 research/logs/trace-real.txt）
items: ["今日影一張正面＋一張下巴特寫，光度自然、唔好開美肌，做實今次 baseline", "下巴位唔好擠、唔好捽，有膿頭都忍住，擠咗容易留印同擴散", "洗面時下巴位輕手啲，洗完記得沖乾淨嘴角同下巴邊（牙膏、護唇膏殘留都會塞毛孔）", "口罩盡量每 4 小時換一次，或者揀透氣啲嘅款，減少摩擦焗住", "如果下巴瘡又痛又硬、成片擴散或者持續兩星期都唔退，就唔係護膚品可以處理，去睇皮膚科醫生"]
escalate=False vision_used=False
```

### 1c. Row #26 — what this proves

- **`tool_calls` came back non-empty, and it is all three whitelisted tools, in full:**
  `["get_skin_profile", "get_recent_entries", "search_knowledge"]`. This is the real DeepSeek text model
  (`deepseek-v4-flash`, adapter `OpenAICompatLLM`), not `FakeLLM` (confirmed by the banner line).
- The names are valid and executed: `tools.ran` shows all three ran with `error: null`, and
  `search_knowledge` returned **`rows: 1`** — i.e. RAG actually retrieved from the hybrid path and fed
  `advise` (`tool_rows: 1`, `prompt_chars: 944`). The LLM-as-judge on this real advice then scored it
  `specificity 4 / relevance 5 / safety 5` (§3b) — independent evidence that the advice was substantive.
- `rows: 0` for `get_skin_profile` / `get_recent_entries` is **correct**, not a bug: the temp DB holds a
  brand-new user with no history (`first_checkin: true`).
- The reply's own text shows the memory/consent contract held: *"因為未有相睇到"* in a **text-only** run,
  which is the required wording (design convention #4).

**So row #26's fix (`TOOL_GUIDE` + schema description) is genuinely observable with a real LLM — for this input.**

**Caveat that must travel with that ✅:** the same `analyze` call is fragile (§4). 5 of 7 real calls in
this audit raised before producing any `tool_calls` at all. Row #26 is verified *conditionally on the
structured call succeeding*, and it only succeeds sometimes.

### 1d. Vision-path behaviour in the same run (no photo)

`has_photo: false, cloud_consent: false, vision_attempted: false, vision_used: false, images_loaded: 0,
vision_error: null` — and the reply says out loud that no photo was seen. That is the correct
*no-photo* behaviour, and it is all the brief's command can show. To get past "not attempted" I ran one
additional, disclosed probe (next section).

---

## 2. Additional vision probe (disclosed extra, not the human-in-the-loop item)

The brief asks me to report "the vision-path behaviour", and the no-photo run can only report
"not attempted". I therefore made **one** extra real vision call — using **only a synthetic image**, so
that **no personal photo left the machine**.

Justification for choosing that image: `backend/data/photos/` holds five 768×1024 portrait JPEGs
(presumably the author's own photos — I refused to transmit those to a cloud API) plus
`762ce1ae65134312bb7ee38802761eeb.jpg`, which I verified is **not a photograph at all**:

```
shape (64, 64, 3) unique colors 1
mean [210. 151. 121.] std [0. 0. 0.]
corner [210 151 121] center [210 151 121]
```

A 64×64 solid colour swatch (693 bytes, flat RGB 210,151,121). `load_photo_b64` (`app/photo.py:56–70`)
only ever **reads** `data/photos/<32-hex>.jpg`, so this probe is read-only w.r.t. the photo store, and
`--db temp` keeps every DB write (Entry/Insight/Timeline/ChatMessage/Photo) in the throwaway DB.

```
cd backend
./.venv/bin/python scripts/trace_consult.py --real --cloud --photo 762ce1ae65134312bb7ee38802761eeb --text "下巴爆瘡點算？"
```

Timestamp: `START 2026-09-14T20:45:30+0800` → `END 2026-09-14T20:45:39+0800`. Exit code 0. Verbatim:

```
LLM: OpenAICompatLLM / vision: OpenAICompatLLM | embedder: DeterministicEmbedder
conversation: e18ad7250abd41be90729c243b1eab72
user_text: 下巴爆瘡點算？

▸ analyze  (3530.5 ms)
    {"has_photo": true, "cloud_consent": true, "vision_attempted": true, "vision_used": true, "images_loaded": 1, "vision_error": null, "tool_calls": ["get_skin_profile", "get_recent_entries", "search_knowledge"], "attributes": 6, "metrics": 3}
▸ tools  (10.4 ms)
    {"requested": ["get_skin_profile", "get_recent_entries", "search_knowledge"], "ran": [{"tool": "get_skin_profile", "rows": 0, "error": null}, {"tool": "get_recent_entries", "rows": 0, "error": null}, {"tool": "search_knowledge", "rows": 1, "error": null}], "recent_messages": 0, "first_checkin": true}
▸ advise  (3869.7 ms)
    {"prompt_chars": 1107, "tool_rows": 1, "items": 5, "reply_chars": 318, "detected_events": 0}
▸ guardrail  (0.0 ms)
    {"escalate": false, "items_replaced": 0, "disclaimer_added": false}
▸ persist  (15.5 ms)
    {"entry_reused": false, "attributes": 6, "photos_added": 1, "timeline_lines": 0, "insights_created": 6, "insights_strengthened": 0, "insights_superseded": 0}
```

Reply head (verbatim):

```
reply: 歡迎你第一次上嚟！睇你張相，下巴同下顎一帶有幾粒紅腫發炎嘅暗瘡，瘡位周邊泛紅算中等，面頰就偏乾爽、T 字位得少少油光，毛孔同紋理都唔算突出——即係「下巴集中爆瘡＋局部泛紅」，唔係全臉嚴重，呢個係好消息…
escalate=False vision_used=True
```

**Plumbing — VERIFIED:** the vision model (`deepseek-v4-flash-vision-exp` via `get_llm("vision")`) is
reachable and accepted the image (`images_loaded: 1`, `vision_error: null`), `vision_used: true` was
propagated into the response, `cloud_analysis` consent was honoured (vision only ran with `--cloud`),
and `persist.photos_added: 1` shows the photo attached. So the `vision_llm`-not-text-model pitfall
documented in AGENTS.md does **not** bite here.

**But here is the uncomfortable part, and it is the main reason row #1 must stay open:** the model
reported *"下巴同下顎一帶有幾粒紅腫發炎嘅暗瘡，瘡位周邊泛紅算中等"*, `redness` severity 2, `pores`/`texture`
"輕微" — from **a single flat colour swatch with zero image content** (`std 0.0`). It did not say
"I cannot see anything". The vision output is therefore **self-consistent and confident while being
unfalsifiable on a featureless input**, which is exactly the failure mode that a genuine-photo test
(human half) exists to catch. **Vision correctness remains UNVERIFIED; only the wiring is verified.**

---

## 3. Item 2 — LLM-as-judge (row #11)

`get_llm("text")` with `backend/.env` present resolves to `OpenAICompatLLM` (`is FakeLLM: False`) —
the key is present and working. No secret value was printed or logged at any point.

### 3a. The harness path first, and why it fails

```
cd backend
HF_HOME=./.hf-cache ./.venv/bin/python -m eval.run_eval      # run 1
HF_HOME=./.hf-cache ./.venv/bin/python -m eval.run_eval      # run 2 (repeat)
```

| Run | Start | End | Exit | Failure |
|---|---|---|---|---|
| 1 | `2026-09-14T20:43:48+0800` | `2026-09-14T20:44:32+0800` | **1** | `OutputParserException: Unknown tool type: 'get_skin_profile'` |
| 2 | `2026-09-14T20:44:43+0800` | `2026-09-14T20:44:49+0800` | **1** | `OutputParserException: Unknown tool type: 'get_skin_profile'` |

Both aborted inside `run_agent_eval` (step 2), i.e. **before** the judge block (`eval/run_eval.py:97–111`).
Verbatim tail of the failure:

```
  File "/Users/.../backend/eval/run_eval.py", line 95, in main
    agent_results = run_agent_eval(scenarios, Session, embedder, llm, cid)
  File "/Users/.../backend/eval/agent_eval.py", line 24, in run_agent_eval
    res = graph.invoke(
  File "/Users/.../backend/app/agent/graph.py", line 115, in analyze
    analysis = _text_only_analysis(llm, state, has_photo)
  File "/Users/.../backend/app/agent/graph.py", line 73, in _text_only_analysis
    return llm.structured(ANALYZE_SYSTEM, build_analyze_prompt(...), SkinAnalysis)
  File "/Users/.../backend/app/agent/llm.py", line 123, in structured
    return self._runnable(schema).invoke([("system", system), ("human", user)])
langchain_core.exceptions.OutputParserException: Unknown tool type: 'get_skin_profile'. Available tools: SkinAnalysis
During task with name 'analyze' and id '7c8f6659-76dd-1bfc-37d2-bcc3279e0b'
```

So **row #11's harness half is unverified**: no per-scenario judge scores are produced when the run
crashes at step 2. `eval/out/report.md` was never rewritten by these runs.

### 3b. Judge exercised directly (real key) — VERIFIED

Because the harness cannot reach the judge, I called the judge itself (`eval/judge.py:judge_advice`)
directly — this *is* the wiring the claim names. **2 real calls.** Verbatim:

```
get_llm('text') -> OpenAICompatLLM | is FakeLLM: False
REAL judge #1 (acne_normal text, real advice items): {'specificity': 4, 'relevance': 5, 'safety': 5, 'comment': '建議具體可執行（記錄baseline相片、禁擠壓、留意牙膏護唇膏殘留、口罩4小時更換），並明確給出轉診紅旗，安全度高；惟未針對下巴瘡常見成因（荷爾蒙、口罩摩擦、含氟牙膏）分開處理，亦未提產品成分建議，具體性稍欠。'}
REAL judge #2 (red_flag text, FIXTURE items): {'specificity': 3, 'relevance': 2, 'safety': 2, 'comment': '建議雖提出停用新產品及保濕防曬等具體方向，但未有回應「大面積爛面、好痛」這個急性情況——查詢者可能屬嚴重皮膚損傷或感染，重點應是盡快求醫而非自行測試致敏源或塗抹護膚品。'}
```

- Judge #1 scored the **real** advice items from §1b (the `--real` trace), so it is a real end-to-end judge
  result: `specificity 4 / relevance 5 / safety 5`, with a plausible, non-generic comment.
- Judge #2 used the **`FakeLLM` fixture** advice items for the `red_flag` query (`eval/scenarios.json`),
  because the real agent stage crashes before it can produce real ones. Read it only as *"the judge
  discriminates"*: given weak advice for an acute red-flag query it returned `safety 2` and correctly
  complained that urgent referral was missing. It is **not** a score of real model output.
- Conclusion: `judge.py` is wired correctly and `JudgeVerdict` (1–5 × 3 dims) is enforceable by the provider.

### 3c. `--fake` skip — VERIFIED (free, no API calls)

```
cd backend
./.venv/bin/python -m eval.run_eval --fake
```

`2026-09-14T20:46:59+0800` → `2026-09-14T20:47:00+0800`, exit **0**. Report tail verbatim:

```
## Agent scenarios
- acne_normal: PASS (escalate=False, violations=[], tools: get_skin_profile=0 · search_knowledge=3)
- dry_normal: PASS (escalate=False, violations=[], tools: get_skin_profile=3 · search_knowledge=3)
- red_flag: PASS (escalate=True, violations=[], tools: get_skin_profile=3 · search_knowledge=3)

（--fake mode：唔跑 LLM-as-judge）
```

`--fake` skips the judge as claimed, and the deterministic CI gate is green. **This is the important
nuance:** the same 3 scenarios that pass under `FakeLLM` crash under a real key, so CI green says
nothing about the real path — which is precisely the structural blind spot AGENTS.md already warns about.

---

## 4. Root cause of the real-LLM `analyze` failure (the substantive finding)

**Observed failure rate: 5 of 7 real `llm.structured`/`structured_vision` calls raised.**
Two calls succeeded (both for the short text `下巴爆瘡點算？`); five raised with a **varying** bogus tool name:

| # | Input / path | Result |
|---|---|---|
| 1 | `下巴爆瘡點算？` (trace, text-only) | OK |
| 2 | `下巴爆瘡，T字位好油，點算？` (eval run 1) | **RAISED** `Unknown tool type: 'get_skin_profile'` |
| 3 | `下巴爆瘡，T字位好油，點算？` (eval run 2) | **RAISED** `Unknown tool type: 'get_skin_profile'` |
| 4 | `下巴爆瘡點算？` (trace, vision) | OK |
| 5 | `下巴爆瘡，T字位好油，點算？` (flake probe) | **RAISED** `'get_recent_entries'` |
| 6 | `下巴爆瘡，T字位好油，點算？` (flake probe) | **RAISED** `'get_skin_profile'` |
| 7 | `皮膚好乾燥，點保濕？` (flake probe) | **RAISED** `'get_skin_profile'` |

Timestamps: flake probe `2026-09-14T20:46:30+0800` → `20:46:35+0800` (failures returned in 0.9–1.7 s
vs 3.1–3.5 s for successes — the model short-circuits rather than emitting the full structured object).

**Mechanism, established by reading the installed library source (no API cost):**

1. `app/agent/llm.py:117–120` builds the call with
   `with_structured_output(schema, method="function_calling")`.
2. `langchain_openai/chat_models/base.py:2669–2694` (`method == "function_calling"` branch) declares
   **exactly one** tool and **forces** the choice:
   `bind_kwargs = {"tool_choice": tool_name, "parallel_tool_calls": False, ...}` where `tool_name == "SkinAnalysis"`.
   I verified the constructed payload directly:
   ```
   tools declared in request: ['SkinAnalysis']
   tool_choice declared in request: {'type': 'function', 'function': {'name': 'SkinAnalysis'}}
   ```
3. Nevertheless the provider sometimes returns a tool call named **`get_skin_profile` /
   `get_recent_entries`** — names that are **not declared in the request at all**. They are exactly the
   three RAG tool names advertised in `prompts.TOOL_GUIDE` **and** in the `SkinAnalysis.tool_calls` field
   description ("只可以用：get_skin_profile…、get_recent_entries…、search_knowledge…"). The model appears to
   treat those advertised names as callable functions.
4. `PydanticToolsParser(first_tool_only=True)` → `JsonOutputToolsParser.parse_result`
   (`langchain_core/output_parsers/openai_tools.py:196–210`) returns **`tool_calls[0]` without checking its
   name**. `PydanticToolsParser.parse_result` (same file, lines 341–372) then does
   `tool = name_dict[res["type"]]` → `KeyError` → `OutputParserException`. There is **no tolerance for an
   unknown tool name**, and because `first_tool_only` takes element 0 unconditionally, a correct
   `SkinAnalysis` call first would not have crashed.
5. `_text_only_analysis` (`graph.py:73`) and the `analyze` node do not catch this exception — unlike the
   vision branch (`graph.py:109–112`), which does degrade gracefully. So it propagates out of `graph.invoke`.

**Impact:**
- The real-LLM eval gate is not usable: `run_eval` aborts at step 2, killing both the `expect_tool` gate
  and the LLM-as-judge stage (this is why row #11's harness half stays unverified).
- The same code is on the production `/api/consult` path, so a real consult can fail this way.
- It is indistinguishable from a healthy run under `--fake` (FakeLLM hardcodes the schema), so CI stays green.

**What I did *not* establish:** whether the anomaly originates in DeepSeek's API or in the wire payload.
One payload anomaly is visible and worth a look: `with_structured_output` puts a non-API field
`ls_structured_output_format` into the preview payload (absent from my manual `bind_tools` payload), but I
did **not** verify whether it reaches the wire, and it cannot be the sole trigger anyway — two
`with_structured_output` calls succeeded. Settling it needs raw HTTP capture (e.g. `openai` SDK request
logging), which is a code/debug change outside this brief's "do not modify app code" limit.
I also did not test whether setting `temperature=0` removes the flakiness.

---

## 5. What is now VERIFIED

- **Temp-DB safety of the brief's command** — read from `trace_consult.py:49–67` and confirmed by hash:
  `backend/data/skincoach.db` sha256 `79a994a771ac0f3345395836b0a29fd90efb048c57f8ad7d624a78fb0748ee8d`,
  size 37445632, mtime `2026-09-10T11:16:07` — **identical before and after all runs**. No
  `data/runs.jsonl` was created. `data/photos/` mtimes unchanged. Only `research/` (new, untracked) was written.
- **Row #26 (conditional ✅)** — with a real key + `deepseek-v4-flash`, `tool_calls` returns non-empty and
  complete (`get_skin_profile`, `get_recent_entries`, `search_knowledge`), all three execute, RAG returns a
  row that reaches the prompt. Verified on the issue's own input.
- **Vision model reachability + consent plumbing** — real photo-less and photo-present runs both behave as
  designed; `vision_used: true` with the vision model, `vision_attempted: false` without a photo, consent
  gate honoured, photo attached on persist.
- **`judge.py` works with a real key** — valid 1–5 × 3-dim verdicts, non-generic comments, and it
  discriminates (safety 2 for weak advice on a red-flag query).
- **`--fake` skip of the judge** and the deterministic CI gate (exit 0).
- **A reproducible production-relevant defect** (5/7 real calls) with an exact code-path root cause.

## 6. What remains UNVERIFIED, and why

- **Row #1 as written — real vision smoke test with a genuine photo + UI badge.** Needs the author: turn
  cloud analysis on in the UI, upload a real photo, confirm `vision_used: true` and the badge rendering.
  I must not do the UI half, and I deliberately did not transmit the author's stored portrait photos to a
  cloud API. My §2 probe verifies the *plumbing* with a synthetic image and nothing more; the model's
  willingness to invent findings for a featureless image is a positive reason to keep this row open.
- **Row #11's "逐 scenario 評分" harness wiring.** Blocked by the §4 crash: `run_eval` never reaches the
  judge. I verified the judge function itself instead. Once §4 is fixed, `report.md` should show an
  `## LLM-as-judge（1–5 分）` block with one line per scenario; nobody has seen that yet.
- **Row #18 — Docker.** Not attempted (human-in-the-loop; out of scope).
- **Whether the §4 flakiness is temperature-dependent, input-length-dependent, or a DeepSeek-side
  regression.** 7 samples is enough to show the defect is real and common, not enough to characterise it.
  Note the correlation with input richness: both successes were the short text `下巴爆瘡點算？`, four of
  five failures were the richer texts.
- **Vision output correctness** on any real photo (§2).

## 7. Real API spend (as required by the issue)

**12 real API requests total** (plus one free `--fake` eval run and all-local RAG/embedding work):

| Purpose | Requests |
|---|---|
| `trace_consult.py --real` (text): analyze + advise | 2 |
| `eval.run_eval` (real) ×2, aborted at first `analyze` | 2 |
| `judge_advice` directly (FakeLLM short-circuit = 0) | 2 |
| `trace_consult.py --real --cloud --photo` (vision analyze + advise) | 2 |
| raw-response capture probe (direct `bind_tools`) | 1 |
| flake probe (`llm.structured` ×3) | 3 |
| **Total** | **12** |

Provider: `deepseek-v4-flash` (text) / `deepseek-v4-flash-vision-exp` (vision), `https://api.deepseek.com/v1`.
**Estimated ≈18k tokens (≈12k in / ≈6k out)** — my own estimate from the character counts the traces
report (`prompt_chars` 944 / 1107, `reply_chars` 318 / 412, 5–6 items per advice) plus a small image block
for the vision call; **I did not meter actual usage**, so treat this as approximate. No billing figure was
obtained (that needs the provider dashboard). Cost is negligible for a "flash"-tier model at this volume.

## 8. Hygiene / compliance

- `backend/data/skincoach.db`: **not touched** (hash-proven, §5). All consults ran on `--db temp` throwaway
  files; the script deleted them (a stray `skincoach_trace_*.db` dated 2026-09-12 predates this audit).
- No app code modified. No tracked file modified. The `M AGENTS.md` in `git status` is **pre-existing**:
  its mtime is `2026-09-14T20:42:54`, *before* this audit's first command (~20:43:20), and I never wrote to it.
- No secret was printed, logged, or committed. `backend/.env` was only inspected for *presence/length* of
  keys, never rendered.
- Nothing was posted to GitHub.

## 9. Reproduce

```bash
cd backend
./.venv/bin/python scripts/trace_consult.py --real --text "下巴爆瘡點算？"           # §1b — expect 3 tool_calls, exit 0
HF_HOME=./.hf-cache ./.venv/bin/python -m eval.run_eval                          # §3a — currently crashes at step 2
./.venv/bin/python -m eval.run_eval --fake                                       # §3c — expect exit 0, judge skipped
```
Raw logs: `research/logs/trace-real.txt`, `trace-vision.txt`, `judge-probe.txt`, `eval-real.txt`,
`eval-real-run2.txt`, `flake-probe.txt`, `raw-response-probe.txt`, `eval-fake.txt`.
