# Deploy & docs honesty — audit of issue #7 (rows #2, #7, #18, #20, #24)

Scope: `docker-compose*.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`,
`backend/scripts/seed_demo.py`, all of `docs/*.md`, `README.md`, `backend/README.md`, `AGENTS.md`,
`archive/skinfile/`. Read-only on tracked files; nothing posted to GitHub.

## What I actually ran (and what I did not)

Ran, with real output quoted below:

| Command | Result |
|---|---|
| `docker compose config` | exit 0, no warnings |
| `docker compose config --format json` | parsed; per-service `env_file` + environment keys listed |
| `docker compose config` from `/tmp/dc-noenv` (compose copy, no `backend/.env`) | exit 0, no warnings |
| `docker info --format '{{.ServerVersion}}'` / `docker ps` | `27.4.0`; 2 unrelated containers running |
| `backend/.venv/bin/python -m pytest --collect-only -q` | `73 tests collected` |
| `backend/.venv/bin/python -m pytest -q` | `73 passed in 1.53s` |
| `backend/.venv/bin/python -m eval.run_eval --fake` | exit 0; recall 100% / MRR 0.90 + hybrid 100% / 1.00 + 3 agent PASS |
| `frontend`: `npm run typecheck`, `npm run build` | both exit 0 (`✓ 54 modules transformed`, `✓ built in 818ms`) |
| `python scripts/seed_demo.py --out /tmp/seedcheck.XXXX/demo.db` | exit 0, `93 entries · 90 日`; ran against a **temp** path only |
| read-only probe of that temp demo DB via `app.correlation.conversation_candidates` + `attributes.anchor_comparisons` | 13 candidates / 8 `strong`; 6 anchor rows |
| `git ls-files`, `git ls-files -s archive`, `git check-ignore -v` | archive/CI/golden trackship confirmed |
| `curl` against a throwaway `npx vite --port 5199` (killed after) | `GET /health` → `200 text/html`; `GET /api/settings` → 500 |

**I verified `backend/data/skincoach.db` was never touched**: `mtime=1789010167 size=37445632` before and after every run above; `ls backend/data/` listing unchanged.

**NOT run — and therefore not claimed**:

- **No `docker build` / `docker compose up`.** My verdict on #18 is *static only*. Docker Compose v2.31.0 and a **running** daemon are present on this machine, but starting a build was outside my brief — so the honest statement is "config validated, image never built", not "it works".
- **No real LLM call, no real photo upload, no LLM-as-judge run** (all need a paid key).
- No demo video; no browser-driven UI test.

Note: I did run `npm run build`, which rewrote the untracked, gitignored `frontend/dist/` (there is no way to verify a green build without emitting). No tracked file was modified.

---

# Verdicts

## #18 — DRIFT (deployability claim over-stated in `roadmap.md`) / UNVERIFIABLE OFFLINE for the runtime question

Docs claim:
- `docs/status-vs-claims.md:11` — "CI 有 pytest + eval + frontend jobs"; `:34` (#18) — "🟡 已修：frontend nginx `/api`+`/health` proxy → backend、optional `env_file: ./backend/.env`（`required: false`）+ `${VAR:-default}` environment、`./data` bind volume、corpus bake／empty-chunks ingest entrypoint、兩邊 .dockerignore、healthcheck。`docker compose config` ✅ PASS。**實際 build 未跑**（本機 Docker daemon 未開）"
- `docs/roadmap.md:11` — "Docker Compose + Dockerfile ✅"; `docs/roadmap.md:50` — "Docker 部署（compose up 撳得郁）✅（以 status #18 為準）"
- `README.md:77` — "`docker compose up --build` 提供 production 形態"

What code + runs show:

1. **`docker compose config` really does pass**, and the mechanism the docs describe is real:
   - `docker-compose.yml:37-40` optional `env_file` (`path: ./backend/.env` / `required: false`) parses cleanly even with **no `.env` present** — I proved this by running `docker compose config` in `/tmp/dc-noenv` containing only a copy of the compose file: `exit=0`, empty stderr. (`required: false` needs Compose ≥ 2.24; local is `v2.31.0-desktop.2`.)
   - `docker-compose.yml:23-36` `${VAR:-default}` environment renders sane defaults (`SKINCOACH_LLM_PROVIDER: deepseek`, `SKINCOACH_DEEPSEEK_TEXT_MODEL: deepseek-v4-flash`, `SKINCOACH_CLOUD_ANALYSIS_DEFAULT: "false"`).
   - `docker-compose.yml:46-52` healthcheck uses `python -c` + `urllib` (correct: `python:3.12-slim` has no `curl`), `start_period: 120s`.
   - `backend/Dockerfile:18-26` bakes `corpus/` + `scripts/` and never copies `data/` (`backend/.dockerignore` excludes `data`, `.env`, `.env.*`, `.venv`).
   - `backend/docker_entrypoint.sh:9-35` = `init_db()` → count `chunks` → ingest only when `0` → `exec uvicorn`; ingest failure is non-fatal and logged.
   - `frontend/nginx.conf:20-28,31-37` proxies `/api/` (URI passed through) and `= /health`; `frontend/Dockerfile:6-9` runs `npm ci` + `npm run build` from the `frontend/` context (lockfile present).
   - `docker-compose.yml:45` `- ./data:/app/data` and the json config confirms `create_host_path: true`.

2. **The stated blocker is stale**: `docs/status-vs-claims.md:34` says the build was not run because "本機 Docker daemon 未開". On this machine the daemon is **up**: `docker info --format '{{.ServerVersion}}'` → `27.4.0`, `docker ps` → two running containers (`supabase_db_…`, `supabase_studio_…`). The honest wording is "build never attempted", not "Docker unavailable". Same stale reason at `docs/status-vs-claims.md:48` ("要喺有 Docker 嘅機…行一次").

3. **`roadmap.md` contradicts its own authority.** `docs/roadmap.md:50` marks Docker deploy ✅ "以 status #18 為準", but the row it defers to is 🟡 and says the build never ran. `docs/roadmap.md:11` also says ✅. Under the project's own rule (`docs/status-vs-claims.md:10`), a ✅ must not rest on an unrun step.

Specific failure modes visible by reading (none of these are runtime-verified):

- **Dimension-poisoning on a first offline boot (sticky).** `backend/docker_entrypoint.sh:26-35` ingests only when `chunks == 0`; `backend/scripts/ingest_corpus.py:25` builds `FastembedEmbedder()`, which on any load failure falls back to the 128-dim hash embedder and only logs a warning (`backend/app/rag/embeddings.py:63-74`). If the first boot is offline, `chunks` becomes non-zero **with 128-dim vectors in the persistent volume**, and every later boot skips ingest. Queries then run at 384 dims and `backend/app/rag/vectorstore.py:76-92` skips every mismatched chunk: RAG returns nothing, permanently, until someone clears `chunks` — a procedure no doc gives for the Docker path. `docker-compose.yml:8-9` explicitly advertises the no-key/offline boot as a supported scenario.
- **`HF_HOME` does not control fastembed's cache** (see D10) — the model download lands in the container's temp dir, not on the volume, so a recreated container re-downloads.
- **nginx upstream IP pinning.** `frontend/nginx.conf:21,32` use a literal `backend:8000`; `docker-compose.yml:59-60` gives the frontend only `depends_on: [backend]` (`condition: service_started`, per the json config) and no healthcheck. nginx resolves the name at start and caches the IP, so a later `compose up --build` that recreates the backend can leave the frontend proxying a dead IP until the frontend container is restarted.
- **`README.md:66-67`'s cloud-analysis instruction is a no-op under Docker** (see D11).

Smallest honest correction: `docs/roadmap.md:11,50` → 🟡 "config 驗證過（`docker compose config` exit 0），冇 build 過"; `docs/status-vs-claims.md:34,48` → drop the daemon excuse and state "build 未嘗試".

## #2 — VERIFIED (one intentional historical string survives)

Docs claim: `docs/status-vs-claims.md:18` — "實際 5 nodes：analyze→tools→advise→guardrail→persist"; "✅ docs 已改（5-node）".

Code: `backend/app/agent/graph.py:423-435` — exactly five `g.add_node(...)` calls (`analyze`, `tools`, `advise`, `guardrail`, `persist`) and a purely linear edge chain `START → analyze → tools → advise → guardrail → persist → END`. `grep -c add_node` = 5.

Sweep (`grep -rn` over `*.md`/`*.py`/`*.ts`/`*.tsx`, excluding `node_modules`, `.venv`, `archive/`):

- "5 nodes / 5-node / 5 個 node" appears in `README.md:6,26`, `AGENTS.md:32,101`, `docs/architecture.md:17,23`, `docs/roadmap.md:5,29`, `docs/demo-script.md:21`, `docs/blog-outline.md:28`, `docs/blog-post.md:36`, `backend/scripts/trace_consult.py:3` — all five-node, all consistent.
- The **only** surviving "6-node" string anywhere in the tree is `docs/status-vs-claims.md:18`, in the **left-hand "Docs claim" column** of the audit table (its own right-hand column says "✅ docs 已改（5-node）"). That is a quotation of the retired claim, not a live assertion. No stale 6-node claim survives in prose.
- `docs/blog-post.md:42` ("其他三個 node —— 工具分派、guardrail、persist —— 全部係我自己寫嘅 deterministic code") is arithmetically consistent (5 − 2 LLM nodes = 3).

Nit worth one line: the column header `Docs claim（位置）` at `docs/status-vs-claims.md:15` makes those left cells look like present-tense claims; a skim reader can read row 2's left cell as "docs say 6 nodes". If the table is meant to be defensible at a glance, prefix the historical cells with "（舊）".

## #7 — VERIFIED (and the "一年 trace" stretch is genuinely retired)

Docs claim: `docs/status-vs-claims.md:23` — "deterministic change detect + timeline（threshold 先寫）；rolling multi-anchor 對比（vs 上次／1M／3M）已上 UI（`/summary.anchors`，Q12）… 「一年視圖」stretch 唔再做"; `docs/architecture.md:108`, `docs/roadmap.md:39`, `backend/README.md:75`.

Code + run:

- API: `backend/app/main.py:264-270` computes `anchors = anchor_comparisons(severity_map(latest.attributes or []), history, latest.date)` and `:311` returns `"anchors": anchors` from `GET /api/conversations/{cid}/summary`.
- Semantics: `backend/app/agent/attributes.py:44-48` — `MONTH_WINDOW_DAYS = 28`, `QUARTER_WINDOW_DAYS = 90`, `ANCHOR_TOLERANCE_DAYS = 7`; `:176-204` returns per-attribute `prev` / `month` / `quarter` rows with `{date, old, delta}`. That matches the UI copy "約 1 個月 / 約 3 個月（±7 日內最接近嗰日）".
- UI: `frontend/src/types.ts:135` (`anchors: AttributeAnchor[]`), `frontend/src/components/ProgressView.tsx:136-152` (table with columns 最新 / vs 上次 / vs 1 個月 / vs 3 個月), and the dashboard home `frontend/src/layouts/DashHome.tsx:103-130`. Both render empty states when there is nothing to compare, so no fake numbers.
- Arbitrary `--out` hazard: see #24 below.
- Empirically, the anchor machinery produces real rows on real data — against the seeded temp demo DB I got `anchors rows: 6`, first row `{'key': 'acne', …, 'prev': {'date': '2026-09-13', 'old': 2, 'delta': 0}, 'month': {'date': '2026-08-17', …}, 'quarter': {'date': '2026-06-16', 'old': 1, 'delta': 1}}`.
- Retired stretch: `grep -rn "一年|12 個月|year trace"` → only `docs/status-vs-claims.md:23` (retiring it) and `docs/blog-post.md:127` (listing it under "再遠" future work). No doc sells a one-year view as shipped.

## #20 — VERIFIED

Verdict from a dedicated read-only pass (full evidence in Appendix A): `archive/skinfile/` is **inert**.

- 44 files tracked under `archive/` (19 `.tsx`, 12 `.ts`, 6 `.json`, 4 `.md`, 2 `.css`, 1 `.html`; **0 `.py`, 0 `.sh`**), mode `100644` only, no symlinks/gitlinks/submodules. `git status --short archive` → clean.
- `git check-ignore -v archive/skinfile/AGENTS.md` → no output, exit 1: archive is **not** gitignored (it ships in every clone — a repo-size surface, not a build path).
- Zero references from `frontend/**`, `.github/workflows/**`, `docker-compose.yml`, either Dockerfile, either `.dockerignore` (all greps exit 1). The only `backend/**` hits are docstring prose (`app/memory.py:3`, `app/agent/prompts.py:1`, `app/photo.py:4`) plus an unrelated homonym in the zip-import path guard (`app/export.py:33` "unsafe path in archive:").
- Outside both build contexts: `docker-compose.yml:22,56` use `build: ./backend` / `build: ./frontend` with no `context:` key; `backend/Dockerfile:18-26` copies only `pyproject.toml`, `app`, `corpus`, `scripts`, `docker_entrypoint.sh` (no `COPY . .`). The frontend does use `COPY . .` (`frontend/Dockerfile:8`) but its context root is `frontend/`, so `archive/` is a sibling.
- `frontend/tsconfig.json:18` is `include: ["src"]`, no `exclude`/`references`; `frontend/vite.config.ts` sets no `root`/`alias`/`input`. Built output confirms: `grep -ril skinfile frontend/dist` → nothing.
- `backend/pyproject.toml:38-40` `testpaths = ["tests"]`, `pythonpath = ["."]`, and `:35-36` `include = ["app*"]`; archive has no `.py` and no `conftest.py`, so neither pytest nor packaging can reach it.
- Docs that legitimately mention it as a museum: `README.md:42,90`, `AGENTS.md:4,46`, `docs/architecture.md:3,56,100`, `docs/roadmap.md:13`, `docs/status-vs-claims.md:36`.

Only caveat to record: "inert" ≠ "invisible" — 44 tracked files that nothing builds and nothing imports are dead weight in every clone and in every doc-reading path. That is a completeness note, not a contradiction of the #20 claim.

## #24 — VERIFIED for the default path; the "cannot write `skincoach.db`" half is only true by default (DRIFT-lite)

Docs claim: `docs/status-vs-claims.md:40` (#24) — "`scripts/seed_demo.py` → 獨立 `data/demo.db`（90 日 synthetic + global diet events 令 correlation 有得睇）；唔掂真 data"; `backend/README.md:107` — "起一個**獨立** DEMO DB（`data/demo.db`…）；唔掂真 data"; `backend/scripts/seed_demo.py:3-4` docstring — "it never touches your real dev DB (`data/skincoach.db`)".

What code + run shows:

- Path is `--out`-driven and CWD-relative: `backend/scripts/seed_demo.py:71` `--out` default `./data/demo.db`, `:75-79` `Path(args.out)` → `mkdir(parents=True)` → **`if out.exists(): out.unlink()`** → `create_engine(f"sqlite:///{out}")` → `Base.metadata.create_all`. There is no guard, no name check, no "refuse to touch skincoach.db" logic anywhere (`grep -rn skincoach.db` finds only the docstring at `:4` and the closing print at `:238`).
- **It does not touch the real DB by construction**: it never imports `app.db.engine`/`SessionLocal` for writing (only `Base`), and `create_engine` for a file SQLite does not connect eagerly. Proof by run: I executed it into a temp dir — `./.venv/bin/python scripts/seed_demo.py --out /tmp/seedcheck.PryO/demo.db` → `✅ demo DB written: /tmp/seedcheck.PryO/demo.db（93 entries · 90 日）`, exit 0 — and `backend/data/skincoach.db` kept the identical `mtime=1789010167 size=37445632` before and after, with `ls backend/data/` unchanged.
- The seeded data is real enough for the demo claims. Read-only queries against that temp DB: 2 conversations (`面部皮膚` cloud=True, `頭皮`), 93 entries (91 face + 2 scalp = a 90-day window), **12 global timeline events** + 1 conv event, 8 insights, 3 products, 2 chat messages, and `conversation_candidates` → **13 candidates, 8 `strong`**, led by `辣嘢 -> redness up strong=True occ=4` — i.e. the docstring's stated purpose ("so the correlation detector finds a repeated pattern in the demo data") holds.
- **The hazard the docs omit**: because `--out` is unvalidated and `:77-78` unlinks whatever already sits at that path, `python scripts/seed_demo.py --out ./data/skincoach.db` would **delete the 36 MB real DB** (and the same for any typo'd path). "It cannot write `skincoach.db`" is therefore false as a property of the script; it is true only for the default invocation. Nothing in `README.md:69-71`, `backend/README.md:20-22`, `docs/status-vs-claims.md:40,59` or `docs/roadmap.md:20,64` warns about `--out`.
- Two smaller inaccuracies in the same file: the docstring at `:100-102` says "two spicy-diet episodes" while `:103` seeds **four** (`spicy_days = [70, 45, 22, 6]`); and the printed re-run hint at `:236` renders `sqlite:////tmp/...` (four slashes from `f"sqlite:///{out}"` when `out` is absolute) — correct for SQLAlchemy, but the docstring's copy-paste example at `:11` uses the relative form.

Smallest honest correction: add a guard in `seed_demo.py` (`if out.resolve() == Path("data/skincoach.db").resolve(): raise SystemExit(...)`) or, docs-only, state in `backend/README.md:107` that `--out` deletes the target path and must never point at `data/skincoach.db`.

---

# Question 6 — the systematic docs-vs-reality sweep

Every item below is a **numeric or structural claim in a doc that the code contradicts** (or a verification artifact that does not exist). Ordered by severity: credibility-bearing first.

### D1. Docker deployability ticked ✅ in `roadmap.md` against its own 🟡 source row
- Doc says: `docs/roadmap.md:11` "Docker Compose + Dockerfile ✅"; `docs/roadmap.md:50` "Docker 部署（compose up 撳得郁）✅（以 status #18 為準）".
- Code/reality: `docs/status-vs-claims.md:34` — the row it defers to — is 🟡 and states "**實際 build 未跑**". No image has ever been built on this machine.
- Smallest correction: 🟡 in `roadmap.md:11,50`, pointing at #18 as unverified.

### D2. The stated reason the Docker build was not run is false now
- Doc says: `docs/status-vs-claims.md:34` "**實際 build 未跑**（本機 Docker daemon 未開）"; `:48` "要喺有 Docker 嘅機…行一次".
- Reality: `docker info --format '{{.ServerVersion}}'` → `27.4.0`; `docker ps` → two running containers. The daemon is up and has been serving unrelated workloads.
- Smallest correction: "build 未嘗試" (and drop the daemon explanation).

### D3. The documented dev flow makes the Settings connection test permanently fail, while AGENTS.md marks it "已做"
- Doc says: `AGENTS.md:100` "Settings 測試連線已做"; `AGENTS.md:24` / `README.md:64` / `backend/README.md:18` describe local dev as "proxy /api -> 8001".
- Code: `frontend/vite.config.ts:8-10` proxies **only** `'/api'`; `frontend/src/api.ts:161-162` `health()` fetches `'/health'`; `frontend/src/components/SettingsView.tsx:33,41` calls it and `:86-91` renders "✓ 連線正常 / ✗ 連唔到". Under nginx it works (`frontend/nginx.conf:31-37` proxies `= /health`), under Vite it cannot.
- Ran it: on a throwaway `npx vite --port 5199`, `curl -i http://127.0.0.1:5199/health` → `HTTP/1.1 200 OK … Content-Type: text/html` (the SPA `index.html`), while `/api/settings` → `status=500` (proxy attempted, backend down). `frontend/src/api.ts:41` then calls `res.json()` on HTML → throws → `.catch(() => setConn('fail'))`.
- Smallest correction: add `'/health': 'http://localhost:8001'` to the Vite proxy (code), or state that the indicator is only meaningful in the Docker/nginx path.

### D4. "confidence 0.82" in three docs is a number the live system cannot produce
- Doc says: `docs/architecture.md:61` "derived | 「T 字位偏油」confidence 0.82"; `docs/demo-script.md:29` narration "佢會記住『T 字位偏油』（confidence 0.82）"; `docs/blog-post.md:69` "| derived | 「暗瘡：中等」confidence 0.82".
- Code: derived insights are created at `confidence=0.6` (`backend/app/agent/graph.py:321` and `:365`) and strengthen by `CONFIDENCE_STEP = 0.05` capped at `MAX_CONFIDENCE = 0.97` (`backend/app/memory.py:24-25,117`). The reachable ladder is 0.60, 0.65, 0.70 … — **0.82 is unreachable**. The value is inherited from the archived demo data (`archive/skinfile/src/lib/demoData.ts:166` `confidence: 0.82`).
- Why it matters: `docs/demo-script.md` is a script the presenter reads *on camera*; the UI will show `0.60` / `0.65`. This is precisely the "真數據路徑唔可以有假嘢" rule (`AGENTS.md:59`).
- Smallest correction: 0.82 → 0.60 (or "0.60 起，每次強化 +0.05，上限 0.97") in the three files.

### D5. `docs/eval-report-sample.md` is not the current report format — it silently drops the whole Hybrid block
- Doc says (`docs/eval-report-sample.md:1` "sample — 最新格式"): `:15` "（golden corpus：4 chunks · fake mode）", `:17` "## RAG recall@3: 100% · MRR: 0.90", then 5 scenario lines, then agent scenarios.
- Actual generator output (`backend/eval/out/report.md`, reproduced by my `python -m eval.run_eval --fake` run): line 5 is `## RAG recall@3: 100% · MRR: 0.90（semantic baseline）`, then a **`## Hybrid（runtime path，同一 golden set）recall: 100% · MRR: 1.00`** section, and the agent lines carry tool counts (`tools: get_skin_profile=0 · search_knowledge=3`).
- Contradictions: (a) the "（semantic baseline）" qualifier is missing, so the sample reads as *the* retrieval number; (b) the hybrid/runtime row — the one #9 is about — is absent from the sample; (c) tool counts absent. Knock-on: `docs/roadmap.md:63` and `docs/blog-post.md:103` both quote only "recall 100% / MRR 0.90".
- Smallest correction: paste the real `backend/eval/out/report.md` body into `eval-report-sample.md`.

### D6. `status-vs-claims.md:41` (#25) cites a verification artifact that does not exist
- Doc says: "headless DOM smoke（3 套 shell + scene 切換 + drawer + picker）零 console error" — given as evidence for a ✅.
- Code: `frontend/package.json:6-11` has `dev`/`build`/`preview`/`typecheck` — **no `test` script, no test runner**; no jsdom/vitest/jest/playwright/puppeteer in `frontend/package.json` or `frontend/src/**`; `find frontend -name "*smoke*"` → nothing. The only things I could verify are `npm run typecheck` and `npm run build` (both exit 0) — neither can observe a console error.
- Smallest correction: drop the smoke sentence, or replace it with "typecheck + build 綠（`frontend/package.json:8,10`）；冇 DOM 測試 harness".

### D7. `data/runs.jsonl` is cited as a live artifact in two docs; it does not exist
- Doc says: `AGENTS.md:78` "…`/api/consult` 回最終 trace，`data/runs.jsonl` 留紀錄"; `AGENTS.md:101`; `docs/status-vs-claims.md:44` (#27) "`data/runs.jsonl` run log"; `docs/status-vs-claims.md:60` checklist "`data/runs.jsonl` 有紀錄".
- Reality: `ls backend/data/` → `corpus demo.db photos server.log skincoach.db` (no `runs.jsonl`); `ls data/runs.jsonl` → No such file or directory. The writer exists (`backend/app/agent/service.py:40-67`) and is enabled by default (`backend/app/config.py:58 run_log_enabled: bool = True`) at `./data/runs.jsonl` (`config.py:59`, CWD-relative).
- Precise claim: the *code path* is real; the *artifact* has never been produced in this working tree.
- Smallest correction: "writer exists（`service.py:40`），未有任何 run 產生過檔".

### D8. `docs/blog-outline.md:65` still lists shipped work as "下一步"
- Doc says: "- 下一步：真 vision model 接相分析、多用戶 auth、Postgres+pgvector 升級。"
- Contradicted by: `README.md:7`, `docs/architecture.md:83-84` (§7 tiering table), `docs/status-vs-claims.md:17` (#1 ✅ 真), `backend/README.md:34,45`, `backend/app/config.py:35`, `backend/app/agent/llm.py:140` (`get_llm("vision")`). Vision analysis is implemented and *is* the default tiering.
- Smallest correction: delete "真 vision model 接相分析" from that line.

### D9. `AGENTS.md:38` model list is stale — `products` is missing
- Doc says: "SQLAlchemy tables：users / conversations / entries / photos / insights / timeline_events / chat_messages / chunks" (8).
- Code: `backend/app/models.py` defines **9** tables — `users:28`, `conversations:40`, `entries:67`, `photos:84`, `insights:102`, `timeline_events:128`, `chat_messages:150`, **`products:168`**, `chunks:181`. `Product` is load-bearing (`backend/app/agent/tools.py:9,53`, `backend/scripts/seed_demo.py:37,94-97`).
- Symmetric drift: `docs/roadmap.md:16` lists products but omits `chunks` (the RAG table).
- Smallest correction: add `products` to `AGENTS.md:38`; add `chunks` to `docs/roadmap.md:16`.

### D10. `HF_HOME` does not control fastembed's cache — the Dockerfile comment and `.env.example` give false instructions
- Doc says: `backend/Dockerfile:30-31` "Where fastembed caches models downloaded on first ingest (needs network)." + `ENV HF_HOME=/app/.hf-cache`; `.env.example:30-32` "fastembed 嘅 model cache 位置… 指去 data dir 就唔會再重新 download".
- Code: fastembed's default cache is `os.path.join(tempfile.gettempdir(), "fastembed_cache")`, overridable only by `FASTEMBED_CACHE_PATH` (`.venv/lib/python3.13/site-packages/fastembed/common/utils.py:53-54`); `grep -rn HF_HOME fastembed/` → **no matches**. In the container neither `FASTEMBED_CACHE_DIR` nor `SKINCOACH_EMBEDDER_CACHE_DIR` is set (`docker-compose.yml:23-36`; `backend/.env` holds only provider/db-url/cloud-default), so the model lands in the container temp dir — **not** on the `./data` volume — and is re-downloaded whenever the container is recreated.
- Second half: `.env.example`'s knob is honored **only** by the runtime path (`backend/app/agent/service.py:36`, `backend/scripts/trace_consult.py:77`). The documented corpus-rebuild command ignores it: `backend/scripts/ingest_corpus.py:25` is `FastembedEmbedder()` with no `cache_dir`; same at `scripts/crawl_ingest.py:29`, `expand_pmc.py:46`, `crawl_zh.py:90`, `expand_dermnet.py:52`, `eval/run_eval.py:42`.
- Smallest correction: set `FASTEMBED_CACHE_PATH=/app/data/.fastembed-cache` in compose, pass `cache_dir=settings.embedder_cache_dir or None` in `ingest_corpus.py`, and fix the Dockerfile comment.

### D11. README's documented way to enable cloud analysis is a no-op under Docker
- Doc says: `README.md:66-67` — `echo "SKINCOACH_CLOUD_ANALYSIS_DEFAULT=true" >> backend/.env   # 再 restart backend`.
- Code/config: `docker-compose.yml:36` pins `SKINCOACH_CLOUD_ANALYSIS_DEFAULT: ${SKINCOACH_CLOUD_ANALYSIS_DEFAULT:-false}` under `environment:`, which **overrides** `env_file` — as `docker-compose.yml:15-18` itself states, but that note enumerates only "the API keys". Proof by run: with `backend/.env` containing `SKINCOACH_CLOUD_ANALYSIS_DEFAULT=true`, `docker compose config` renders `SKINCOACH_CLOUD_ANALYSIS_DEFAULT: "false"`.
- The local-dev path *does* work (verified: `SKINCOACH_DATABASE_URL` env override applied, and `settings.cloud_analysis_default` stayed `True` from `backend/.env`).
- Smallest correction: add the cloud flag to the compose comment's override list, and note in `README.md:66-67` that under Docker it must be exported in the shell / root `.env`.

### D12. Agent-scenario `expect_tool` gate covers only 2 of 3 scenarios, but the docs imply all three
- Doc says: `docs/status-vs-claims.md:11` "3 agent scenarios PASS（含 `expect_tool` gate）"; `AGENTS.md` (eval row) "agent scenario 有 `expect_tool` gate"; `docs/demo-script.md:41` "3 個 agent 場景全綠".
- Code: `backend/eval/scenarios.json:2-4` — `acne_normal` and `dry_normal` declare `expect_tool: "search_knowledge"`; **`red_flag` declares none** (only `expect_escalate`). `backend/eval/agent_eval.py:41` applies the gate only `if "expect_tool" in sc`.
- Consequence: the escalation path is exactly the scenario with no tool assertion, so a regression that stops tool calls on red-flag inputs stays green.
- Smallest correction: reword to "2/3 scenarios 有 `expect_tool` gate" (or add the expectation).

### D13. `backend/README.md:15` documents a `/health` body that the endpoint does not return
- Doc says: `curl http://localhost:8001/health  # {"status":"ok","llm_provider":"deepseek"}`.
- Code: `backend/app/main.py:73-75` returns `{"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}` — an extra `app` key. `frontend/src/api.ts:161` types only `{status, llm_provider}`, so the frontend is fine; the doc is just inaccurate.
- Smallest correction: include `"app":"SkinCoach"` in the comment.

### D14. Docs index is incomplete in both top-level guides
- `git ls-files docs` → `architecture.md, blog-outline.md, blog-post.md, demo-script.md, eval-report-sample.md, roadmap.md, status-vs-claims.md`.
- `README.md:41` lists 5 of them (missing `blog-post.md`, `eval-report-sample.md`; also no `design/`, `archive/` is there). `AGENTS.md` (docs row) lists 6 (missing `blog-post.md`).
- Smallest correction: one line each.

### D15. `AGENTS.md:106` points at a doc that is not committed
- Doc says: "**Issue tracker**：`docs/agents/issue-tracker.md` —— …".
- Reality: `git status --short` → `?? docs/agents/`; `git ls-files docs/agents` → empty. The file exists on disk (46 lines, matches its own description) but a fresh clone has no such file while `AGENTS.md` tells you to read it. (`docs/agents/triage-labels.md`, `CONTEXT.md`, `docs/adr/` genuinely do not exist — `AGENTS.md:108` admits that.)
- Smallest correction: `git add docs/agents/issue-tracker.md`.

### D16. `docs/demo-script.md:35` references "方向 02", which exists nowhere
- Doc says: "方向 02 嗰啲數據（指數、sparkline、指標）全部收埋喺側邊 panel。"
- Reality: that string is unique in the tree (`grep -rn "方向 02"`). `design/` holds `mockup-1-chat-first.html`, `mockup-2-dashboard-first.html`, `mockup-3-checkin-first.html` — no "方向" numbering exists.
- Smallest correction: name the actual mockup file, or delete the reference.

### D17. `backend/README.md:71` API table omits an existing route
- Doc row: "`GET/POST /api/conversations`、`PUT/DELETE /api/conversations/{cid}` | 部位 conversation CRUD".
- Code: `GET /api/conversations/{cid}` exists at `backend/app/main.py:109` (alongside `PUT:128`, `DELETE:142`).
- Smallest correction: add `GET` to that cell. (Every other route in the table maps to a real handler; I checked all 22 `@app.*` decorators at `main.py:73-416` against the table.)

### D18. Docker deployment reads a *different* data dir than local dev, and no doc says so
- Doc says: `docker-compose.yml:6` "Data `./data` (SQLite db + photos, bind-mounted at /app/data)"; `README.md:77` "data 用 bind volume".
- Reality: the bind source is the **repo-root** `./data` (`docker-compose.yml:45`), which is currently **empty** (`ls data/` → nothing), while every documented local-dev path is `backend/data/…` (you `cd backend` first: `README.md:50-54`, `AGENTS.md:9-11`, and the settings are CWD-relative: `backend/app/config.py:19-20`). A reader can reasonably expect their existing records (36 MB `backend/data/skincoach.db`, real corpus under `backend/data/corpus`) to appear in the Docker UI; they will not.
- Smallest correction: one sentence in `README.md:77` — "Docker 用 repo 根 `./data`（同 `backend/data` 分開；首次開會自動 ingest `corpus/`）".

### D19. Historical numbers that cannot be checked offline (flagged, not counted as drift)
- `docs/status-vs-claims.md:43` (#26) — "pytest 60 綠 + eval --fake PASS 都 detect 唔到" (a past-state number). The present count is 73; nothing in the tree pins a 60-test commit.
- `docs/architecture.md:83` — "image ≈384 tok" (vendor pricing/tokenization claim).
- `docs/architecture.md:100` / `backend/README.md:31` — "HK 直連 Anthropic/OpenAI 係 403" (external, requires live network probes).
- `docs/eval-report-sample.md:35-38` — concrete per-scenario judge scores (5/5/5, 4/5/5, 5/5/5) presented as "real mode" output. The *section format* matches the generator (`backend/eval/run_eval.py:136-145`), but no artifact backs those digits; `backend/eval/out/` holds only `report.md`. Treat as illustrative, or label it "示例（非真實輸出）".

### Claims I checked *and found accurate* (so the sweep is auditable both ways)

73 tests (`pytest --collect-only -q` → `73 tests collected`; `pytest -q` → `73 passed`); 5 nodes (`graph.py:423-435`); 3 tools (`tools.py:13`, `prompts.py:11-19` all three named — the #26 fix is real); 6 attribute keys × 0–3 (`attributes.py:22-29`); 30-day expiry (`memory.py:23`); cap 0.97 + step 0.05 (`memory.py:24-25`); direction thresholds `problem ≥2 / normal ≤1` (`attributes.py:60` `direction_for`); preference window 21 days / `≥3` distinct days for diet **and** product (`preferences.py:21-23`); correlation `strong` at 2 occurrences, `MIN_DELTA = 1` (`correlation.py:29-33`); hybrid `RECALL_K = 80` (`hybrid.py:13`); recent-context limit 10 messages (`graph.py:164`); eval numbers `recall 100% / MRR 0.90` + hybrid `100% / 1.00` + 3/3 agent PASS (reproduced); eval uses a temp DB (`run_eval.py:69-74`, `:158` `os.unlink`); eval exits 1 on FAIL (`run_eval.py:156`) and CI runs it (`ci.yml:38`); golden corpus **is** committed (`git ls-files backend/eval` → 3 golden files), so "clean clone 可重現" holds; judge scores are skipped in `--fake` (`run_eval.py:139-145`); frontend typecheck+build green; `data/` and `.env` gitignored; export/import zip exists (`main.py:78,88`); `/summary` merges conv + global events and global insights (`main.py:236-262`, `:278-300`); global 🌐 badge renders (`ProgressView.tsx` scope-badge); escalate banner + vision badge render (`Chat.tsx:68,77-78`); no "78 分" score anywhere in `frontend/src/`; every file `AGENTS.md` names under `frontend/src/{components,hooks,layouts}` exists; `photo.py:21` is the 32-hex shape check; no stale "20/40/42 tests" claim survives anywhere.

---

## Bottom line for this batch

- **#2 — VERIFIED.** Five nodes everywhere; one historical "6-node" string survives inside the audit table's quotation column.
- **#7 — VERIFIED.** Anchors are wired API→UI with the documented 28/90-day windows ±7 days; the one-year view is retired and never sold as shipped.
- **#18 — DRIFT on the ✅, UNVERIFIABLE on the runtime.** `docker compose config` genuinely passes (including with no `backend/.env`), all the listed fixes exist in the files, but no image was ever built — and the docs' stated reason (daemon down) is factually false on this machine. Three nameable static hazards: hash-embedder dimension poisoning that the entrypoint's "chunks>0 → skip" rule makes sticky, fastembed cache not on the volume, and nginx upstream IP pinning.
- **#20 — VERIFIED.** `archive/skinfile/` is inert: no import, no build, no CI, outside both Docker contexts (44 tracked files ship in clones, but nothing executes them).
- **#24 — VERIFIED with a caveat.** The default `data/demo.db` is genuinely independent (proved by running it into a temp dir: 93 entries, 12 global diet events, 8 strong correlation candidates, real DB mtime/size unchanged). But "cannot write `skincoach.db`" is not a property of the script: `--out` is unvalidated and line 78 unlinks whatever is at that path, so `--out ./data/skincoach.db` would delete the real 36 MB DB.
- **Docs honesty: mixed, and worse than the status table implies.** The status table's own numbers (73, 5 nodes, eval metrics, temp DB, CI gate) all reproduce. The failures cluster in three places: (1) **✅ marks that outrun their evidence** — Docker ✅ in `roadmap.md` against a 🟡 source row, and #25's ✅ resting on a DOM smoke harness that does not exist; (2) **stale generated artifacts presented as live** — the eval sample missing the hybrid section, `data/runs.jsonl`, `confidence 0.82`, `blog-outline`'s "vision as next step"; (3) **copy-paste runbooks that don't work as printed** — README's cloud-analysis echo under Docker, and the Vite dev proxy that makes Settings report "✗ 連唔到" in exactly the flow the README tells you to use.

---

## Appendix A — archive inertness evidence (independent read-only pass)

```
$ git ls-files archive | wc -l          → 44
$ git ls-files -s archive | awk '{print $1}' | sort -u   → 100644   (no symlinks/gitlinks)
$ git check-ignore -v archive/skinfile/AGENTS.md          → (no output), exit 1
$ git status --short archive                              → (no output)
$ grep -rn "skinfile|archive" frontend/ (excl node_modules)  → exit 1
$ grep -rn "skinfile|archive" .github/workflows/              → exit 1
$ grep -rn "skinfile|archive" docker-compose.yml *Dockerfile *.dockerignore → exit 1
$ git grep -n -i -E "archive|skinfile" -- . ':(exclude)archive/*'  → only docs prose + the
  unrelated zip-path guard at backend/app/export.py:33 ("unsafe path in archive: {name}")
$ grep -ril skinfile frontend/dist ; grep -ril archive frontend/dist   → nothing
$ frontend/tsconfig.json:18  "include": ["src"]   (no exclude/references/extends)
$ frontend/vite.config.ts    no root / build.input / resolve.alias / publicDir
$ backend/pyproject.toml:38-40  testpaths = ["tests"], pythonpath = ["."]
$ backend/pyproject.toml:35-36  include = ["app*"]
$ docker-compose.yml:22,56  build: ./backend / ./frontend   (no context: key → context = that dir)
$ frontend/Dockerfile:8  COPY . .   ← scoped to the frontend/ context, archive/ is a sibling
$ backend/Dockerfile:18-26  explicit COPYs only (no COPY . . / no parent-relative source)
$ find . -type l → empty ; git submodule status → empty ; no .gitmodules
$ root package.json / tsconfig.json / Dockerfile / Makefile / workspaces / file: deps → none
$ git config --get core.hooksPath → exit 1 ; .git/hooks/* are all .sample
```

Honest caveat: `archive/` is tracked and not gitignored, so its 44 files are part of every clone and every whole-repo read; they are simply never built, imported, tested, or copied into an image.

## Appendix B — non-claims

- I did **not** build or run any container, so nothing in this report should be read as "`docker compose up --build` works".
- I did **not** call any real LLM/vision/judge endpoint, so #26's "修完實測真 LLM 回齊三個 tool" and #1's real-photo smoke test remain **UNVERIFIABLE OFFLINE** from my side.
- I did **not** run `seed_demo.py` against any path inside the repo.
- `frontend/dist/` (untracked, gitignored) was regenerated by `npm run build`; `backend/eval/out/report.md` (untracked, gitignored) was regenerated by `eval.run_eval --fake`. No tracked file was modified; `backend/data/skincoach.db` was never touched (mtime/size identical before and after every run).
