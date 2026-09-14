# Frontend: what is actually verified? (rows #14, #25)

Issue: [#6](https://github.com/shulaplai/male_skincare_agent/issues/6) · Vertical: `frontend/src`, `frontend/package.json`, `vite.config.ts`, `nginx.conf`
Audited at HEAD `a7feff60b230b848ba7a4695d581802a9e00b02a` (branch `main`, 30 commits) · read-only; no tracked file modified, no destructive git command, `backend/data` untouched.
Commands run: `gh issue view 6 --comments`, `npm run typecheck`, `npm run build`, plus ~40 read-only `git log`/`git cat-file`/`grep` probes.

Vertical as stated (verified by `wc -l`): `App.tsx` 285, `api.ts` 163, `types.ts` 154, `format.ts` 60, `index.css` 1882, `vite.config.ts` 12, `nginx.conf` 43, `package.json` 23. `components/` 1176 lines over 7 files, `hooks/` 131 over 4, `layouts/` 803 over 9.

---

## #25 — DRIFT

### Doc claim

`docs/status-vs-claims.md:41` (row 25), introduced verbatim in `9ee4ba8` and byte-identical at HEAD:

> ✅ `layouts/` registry（`defs.ts` 定義 chat/journal/dash）＋ Settings「介面結構」揀選（CSS wireframe 縮圖、即時切換、`localStorage skc-layout` persist）；`?layout=` preview override；三套共用同一批 view 元件（Chat / RecordsView / ProgressView / SettingsView + `blocks.tsx`），feature parity；**headless DOM smoke（3 套 shell + scene 切換 + drawer + picker）零 console error**；typecheck + build 綠

The whole cell is graded `✅ **真**`. `AGENTS.md` repeats the paraphrase: "`?layout=chat|journal|dash`：URL preview override（唔會寫入偏好），**demo／smoke 用**".

### What code + run shows

**The cited harness does not exist and never did.** Every artefact-bearing thing the claim could point at was checked:

| Probe | Result |
|---|---|
| `git log --all --diff-filter=D --name-only` | 4 files ever deleted: `backend/:memory:.ses`, `frontend/src/data.ts`, `frontend/src/layouts/DashShell.tsx`, `frontend/src/layouts/JournalShell.tsx`. **None test-like.** |
| Union of every path in all 30 commits (171) minus HEAD (167) | exactly those same 4 paths |
| `git ls-tree -r` at **every** commit, filtered `(test\|spec\|smoke\|harness\|e2e)` | only `backend/tests/*.py` — **zero** `frontend/**` hits, ever |
| `git log --all -S` for `jsdom`, `happy-dom`, `linkedom`, `vitest`, `jest`, `puppeteer`, `testing-library`, `test-utils` | **0 commits** (no output) |
| `git log --all -S playwright` | 2 commits — `dcbce0d` + `ad05112`, both the **backend RAG crawler** |
| every version of `frontend/package.json` (only 2 distinct: `16a0a57`, `a7feff6`) | scripts = `dev / build / preview / typecheck`; devDeps = `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `typescript`, `vite`. `git log --all -p -- frontend/package.json \| grep '^\+.*"test'` → **empty; a `test` script was never added** |
| `.github/workflows/ci.yml` across the 20 commits that touched it | frontend job steps ever added: `npm ci`, `npm run typecheck`, `npm run build` only. No smoke/headless step ever existed |
| **blob-level** scan of all 543 objects across all refs for `jsdom\|happy-dom\|linkedom\|vitest\|jest\|puppeteer\|react-dom/test-utils\|testing-library\|renderToString\|headless` | only hits are **2 commit messages** (`9ee4ba8`, `6f1c185`) and **2 revisions of `docs/status-vs-claims.md`**. No harness blob |
| `git stash list` | empty |
| `git fsck --lost-found` | no dangling/unreachable objects |
| `git status --porcelain -uall` | untracked = `.wayfinder/*.md`, `docs/agents/issue-tracker.md`, `research/logs/*.txt` + ` M AGENTS.md`. **No harness on disk either** |

`headless` is the only surviving trace, and it is prose:

```
9ee4ba8  …headless DOM smoke over 3 shells + scene switching + drawer + picker: zero
         console errors. Docs: status-vs-claims #25, AGENTS.md traps/現況, README.
6f1c185  Bug found by the headless smoke while refactoring: useLayout() was read in App
         (which renders the provider) so the chosen structure was always the default
         chat. Layout reading now lives in LayoutHost inside the provider.
         Verified: typecheck + vite build green; headless CDP smoke on all three
         structures (grid cols, tabs, day/dash cards, journal FAB drawer, settings
         picker): zero console errors.
```

The only headless-Chromium code in the entire object database is `backend/scripts/crawl_zh.py`, which rules itself out in its own docstring: *"Crawl Chinese beauty websites using Playwright (JS rendering) + trafilatura … plain httpx returns empty shells. This renders each page in headless Chromium, then runs trafilatura on the rendered HTML."* It renders third-party web pages for the RAG corpus; it cannot smoke 3 shells, scene switching, a drawer or a picker. The museum predecessor (`archive/skinfile/package.json:10` `"eval": "tsx eval/run-eval.ts"`) is a Node LLM-judge runner importing `src/lib/ai.ts` + `prompts.ts` — no DOM, no jsdom, and it predates the three shells, which do not exist in that generation.

### Explicit verdict: did the harness ever exist?

**No — not as a repository artefact, in any form, at any commit, on any branch, ever.** There was never a script, a dev-only page, a deleted file, a `test` script, a CI step, or a stash entry. The only thing that ever existed was an **ad-hoc, uncommitted, throwaway run**, asserted after the fact in two commit messages (`9ee4ba8`, `6f1c185`). That assertion is not worthless — the `useLayout`-in-`App` bug it reports is real and the fix is in the tree today (`App.tsx:17-28`, `LayoutHost`) — but an assertion in a commit message is not a verification artefact: a reviewer cannot see it, CI cannot re-run it, and it cannot fail. The row cites it as if it were the former.

The doc contradicts itself on the same page. Row 25 asserts the smoke was run; the checklist 20 lines below still has it undone:

```
docs/status-vs-claims.md:61:- [ ] 三套結構試一次（#25）：`/?layout=chat|journal|dash` 或 Settings「介面結構」切換；
                                journal FAB 開對話 drawer、dash 大廳 CTA 入 chat scene
```

Also true, and wrong in the row's component list: `blocks.tsx` **is not** a three-shell shared component. It is imported exactly twice — `frontend/src/layouts/JournalHome.tsx:3` and `frontend/src/layouts/DashHome.tsx:1`. The `chat` shell renders it nowhere; its memory/timeline/correlations come from duplicated inline copies in `RightPanel.tsx:6-10,18-47,83-84` and `ProgressView.tsx:6-23,47,158-160`. `blocks.tsx:5-6` says so itself: *"舊 view（RightPanel / ProgressView）暫時仍有自己嘅版本，之後收返嚟呢度。"*

### Smallest honest correction

Replace the harness clause with a statement of what was actually done and what CI actually gates:

> `layouts/` registry（`defs.ts` 定義 chat/journal/dash）＋ Settings「介面結構」揀選（CSS wireframe 縮圖、即時切換、`localStorage skc-layout` persist）；`?layout=` preview override；三套共用同一批 view 元件（Chat / RightPanel / RecordsView / ProgressView / SettingsView），**動作／API 層** feature parity（每套都去到全部功能；`blocks.tsx` 只係兩個 home 用，chat 用 RightPanel 自己嗰份）；**手動 headless smoke 試過一次（3 套 shell + scene 切換 + drawer + picker，當時零 console error）—— 但係一次過冇 commit，冇留存 artifact，CI 唔會重跑；自動化驗證只有 typecheck + build**

Keep `typecheck + build 綠` — that part is real (see §6). If the row wants a ✅ on behaviour, the cheapest fix is to commit the smoke script (a ~40-line Playwright/CDP script under `frontend/` plus a `smoke` npm script and a CI step) rather than to reword — the throwaway clearly worked.

---

## #14 — VERIFIED

### Doc claim

`docs/status-vs-claims.md:30`:

> ✅ chat-first 真；右 panel live（真 attributes/insights/timeline，global 🌐 標記）；假 78 分刪走

### What code + run shows

Right panel is live. Whole-panel provenance is one call: `RightPanel.tsx:56` / `:68` `api.getSummary(conversation.id)` → `api.ts:109-111` `fetch(\`/api/conversations/${conversationId}/summary\`)` → `backend/app/main.py:228-312`. Re-fetch is wired on `[conversation.id, refreshKey]` (`RightPanel.tsx:64-78`), and `refreshKey` is bumped after send/confirm/quick-record/delete (`App.tsx:171, 200, 216, 241`) and threaded in from both shells (`ChatShell.tsx:47`, `StandardShell.tsx:75`). No fixture, no fallback array, no score.

| Rendered value | Origin | Verdict |
|---|---|---|
| `conversation.bodyPart` | prop ← `App.tsx:14` ← `api.ts:5` `body_part` ← `main.py:276` | real |
| `☁️ 雲分析` / `🔒 本地` | `RightPanel.tsx:100-105` ← `api.ts:7` `cloud_analysis`; write `api.ts:74-82` | real |
| severity dots / `severityText` / `x/3` | `RightPanel.tsx:114-133,125-127` ← `summary.entries[0].attributes` ← `main.py:284` ← `models.py:74` | real |
| `↑ 惡化 / ↓ 改善` | `RightPanel.tsx:117-120` computed locally from `entries[0]` vs `entries[1]`; order pinned by `main.py:234` `.order_by(Entry.date.desc())` | real local derivation |
| sparklines | `RightPanel.tsx:18-34,36-47,134-146` computed from real severities; `max = Math.max(...series, 1)` is an anti-÷0 floor; gated on `s.sev.length < 2` | real local derivation |
| `kindLabel` 推導記憶/偏好/事實 | `RightPanel.tsx:6-10` maps `Insight.kind` (`models.py:97`) — uses `preference`, not `pref` | benign constant |
| `confidence 0.xx` + bar | `RightPanel.tsx:171-177` ← `main.py:295` ← `models.py:110` | real |
| 因果時間線 date/text/source | `RightPanel.tsx:191-199` ← `main.py:302-310` | real |
| empty states 「未有指標…」「未有記憶。」「未有事件…」 | `RightPanel.tsx:149, 156, 188` — literal text, no numbers | real |

Nothing is fabricated. The panel renders no score, no product list and no counts (products `main.py:286` and anchors `main.py:311` are in the payload but never read by `RightPanel.tsx`).

**Global 🌐 marking keys off a real field**, not a heuristic: `RightPanel.tsx:163` `{m.scope === 'global' && <span className="scope-badge">🌐 全局</span>}` and `RightPanel.tsx:195-197` `e.source === 'agent' ? 'AI 偵測' : e.scope === 'global' ? '🌐 飲食（全局）' : '你'` (same pair duplicated at `blocks.tsx:69`, `blocks.tsx:100`). The backend derives it from the DB column: `main.py:298` and `main.py:307` `"scope": "global" if i.conversation_id is None else "body_part"`, over `models.py:105` (Insight) and `models.py:131` (TimelineEvent) `conversation_id: Mapped[str | None]`, documented `models.py:125` `NULL conversation_id = global scope (affects all body parts)`. Merge at `main.py:237-245, 254-263`; writer is diet only (`self_report.py:119-131`, `conversation_id=None`, "Global cause event (Q31)"). Pinned by `backend/tests/test_api_layers.py:99-107`.

**Fake 78 removed — confirmed.** `value: 78` lived in the deleted `frontend/src/data.ts:66` (`export const score: SkinScore = { value: 78, … }`), deleted in `ad05112` (`git show --numstat ad05112 -- frontend/src/data.ts` → `0 77`). `SkinScore` is gone from `types.ts` too (`git log --all -S SkinScore -- frontend/src` → `ad05112`, `9c4f7c4`, `46e2d9a` only). Nothing imports it: repo-wide grep for `from '…/data'` over `*.ts/*.tsx/*.js` (excl. `node_modules`, `archive`) → 0 hits. `grep -rn "score\|SkinScore\|78" frontend/src --include='*.ts*'` → 0 hits; the only `78` left in the frontend is inside the colour `--muted: #a1878f` (`index.css:7`).

Independent hardcoded-demo sweep over all 26 `.ts`/`.tsx` in `frontend/src`, nothing excluded: `Math.random` **0 hits**; fake names (`小明`/`Alice`/`Bob`) **0 hits**; hardcoded dates **0 hits**; `?? <number>` **4 hits, all `length` comparisons against `0`** (`JournalHome.tsx:101,139,140,141`), never rendered as data. `demo|mock|fake|sample|placeholder|TODO|FIXME` → 9 hits, all benign text (`App.tsx:57` "no demo content (Q10)", `App.tsx:136`, `SettingsView.tsx:80` `'未設定（會用 FakeLLM）'` which is real backend state, four `placeholder=` attributes, `JournalHome.tsx:186` 「真數據，冇 demo」).

Non-blocking blemishes found while checking (none changes the verdict, none is a fabricated number):

- `RightPanel.tsx:196` hard-labels **every** global timeline row 飲食. True today only because diet is the sole writer of `conversation_id IS NULL` timeline rows (`self_report.py:125`; agent rows are conv-scoped at `graph.py:299-306`) — the scope is real, the label is inferred.
- `App.tsx:50` invents `isDefault` from a name match (`c.body_part === '面部皮膚'`) and `Sidebar.tsx:91` renders it as 「主對話」; there is no such backend column.
- `Chat.tsx:238` shows a static 「約 5–10 秒」 latency hint — a UX hint, outside the data path. (Contrast `ProgressView.tsx:141` / `DashHome.tsx:109`, where 「±7 日…約 1 個月」 does match real constants `attributes.py:46,48`.)
- `index.css:678-720` keeps 8 dead `.score*` rules (incl. `.score .big { font-size: 46px }`) from the deleted score card; zero `score` references in any `.ts`/`.tsx`.

---

## 3. Any automated verification of *behaviour*? — No. Only types.

`frontend/package.json` is the whole story:

```json
"scripts": { "dev": "vite", "build": "tsc --noEmit && vite build",
             "preview": "vite preview", "typecheck": "tsc --noEmit" }
```

No test script, no runner, no assertion of any kind. Beyond that: **no linter either** — no `.eslintrc*`, no `eslint.config.*`, no `.prettierrc*` anywhere in the repo. And `tsconfig.json` stops at `strict: true` / `noUnusedLocals` / `noUnusedParameters`; there is no runtime validation of API payloads — `api.ts:41` is `return res.json() as Promise<T>`, a bare cast, against hand-written `types.ts` that has no codegen link to the backend's Pydantic schemas. (Same conclusion in the other direction: `ci.yml`'s frontend job runs `npm ci && npm run typecheck && npm run build` and nothing else.)

### The class of bug that can ship undetected

Any defect the type system cannot express: hook/dependency ordering, stale-response overwrites, context-provider placement, `localStorage`/URL semantics, error-vs-empty-state confusion, and backend↔frontend contract drift. Types describe shapes; nothing here observes behaviour.

**Concrete example, against a real component.** `frontend/src/hooks/useSummary.ts:21-34`:

```ts
const reload = useCallback(() => {
  setLoading(true); setError(null)
  api.getSummary(cid).then(setSummary).catch(…)      // ← no cancellation guard
}, [cid])
useEffect(reload, [reload, refreshKey])
```

Its two sibling call sites both carry the guard that this one is missing — `useCorrelations.ts:15-26` (`let alive = true … if alive`, cleanup `alive = false`) and the equivalent inline effect in `RightPanel.tsx:64-78`. Both `DashHome.tsx:24` and `JournalHome.tsx:36` call `useSummary(cid, p.refreshKey)`. `journal`/`dash` can switch body part from the `ShellTop.tsx:40-43` dropdown, so: switch A→B, A's response resolves last, `setSummary(A)` wins, and the dashboard/journal renders **A's severity dots, 記憶 and 時間線 under B's heading** (`JournalHome.tsx:57-71`, `DashHome.tsx:34-54`) while the AI-memory and timeline cards stay silently wrong. `tsc --noEmit` is green; no other gate exists.

(Honest scoping: I did not reproduce the interleaving. Reproducing it needs a renderer and installing a test runner is out of scope per the issue constraints. The evidence is the asymmetry between three call sites that need identical semantics — the guard's presence in two and absence in the third — not an observed failure.)

Two more of the same class, both live in the tree:

- `frontend/src/layouts/LayoutContext.tsx:10` `createContext<LayoutValue>({ layout: 'chat', setLayout: () => {} })` — a silent no-op default. Reading `useLayout()` outside the provider compiles and yields `'chat'` with a dead setter, which is *precisely* the bug `6f1c185` fixed by hand. The fix today is a comment (`App.tsx:17-20`) plus discipline; no test defends it.
- `blocks.tsx:5-6` vs `RightPanel.tsx:6-10,18-47,83-84` vs `ProgressView.tsx:6-23,47,158-160` — the same `kindLabel`/`Spark`/`attrSeries`/`CorrelationList` logic exists in three copies. Fixing one copy is invisible to the others; nothing detects the divergence.

---

## 4. #25 layout switching — VERIFIED (code-level), with one unenforced-invariant caveat

`frontend/src/layouts/LayoutContext.tsx` is 45 lines and answers all three claims.

**`localStorage['skc-layout']` really persists — yes.**

```tsx
:23  const [layout, setLayout] = useState<LayoutId>(() => {
:24    const preview = urlPreview()
:25    if (preview) return preview
:26    if (typeof localStorage !== 'undefined') {
:27      const saved = localStorage.getItem('skc-layout')
:28      if (isLayoutId(saved)) return saved
:29    }
:30    return 'chat'
:31  })
:33  useEffect(() => {
:34    if (urlPreview()) return // preview link：唔寫入偏好
:35    try { localStorage.setItem('skc-layout', layout) } catch { /* ignore */ }
:40  }, [layout])
```

Read at mount, written on every change, `try/catch` for private-mode/quota. `isLayoutId` (`:12`) rejects junk. Key matches the convention used for theme (`index.html:9` reads `skc-theme`). Honest-write path is real.

**`?layout=` really overrides without writing the preference — yes.** `urlPreview()` (`:15-19`) parses `URLSearchParams`, and `:24-25` gives it precedence over `localStorage`; `:34` short-circuits the write. So the override lasts exactly one page load and never becomes the stored preference — which is what the row and `AGENTS.md` claim.

One behavioural subtlety worth recording, because it is not a drift but is also not what "即時切換" implies: *while a `?layout=` preview is active*, clicking a different structure in the Settings picker changes the session's UI but is **never persisted** — `:34` short-circuits on every render of the effect, so the user's explicit choice silently reverts on the next plain load. An invalid `?layout=bogus` is simply ignored by `isLayoutId` and the preference behaves normally.

**`useLayout()` is only read inside the provider — yes, at every call site.**

```
$ grep -rn "useLayout\|LayoutProvider\|LayoutContext" frontend/src
App.tsx:2:import { LayoutProvider, useLayout } from './layouts/LayoutContext'
App.tsx:22:  const { layout } = useLayout()          ← inside LayoutHost
App.tsx:280:      <LayoutProvider>
App.tsx:282:      </LayoutProvider>
LayoutContext.tsx:10,22,42,45
LayoutPicker.tsx:51:  const { layout, setLayout } = useLayout()
```

`LayoutHost` is rendered as `<LayoutHost p={shellProps} />` at `App.tsx:281`, i.e. a child of `<LayoutProvider>` (`App.tsx:280-282`). `LayoutPicker` is rendered by `SettingsView.tsx:56`, inside a shell, inside the same provider. `App()`'s own body never calls `useLayout`. The recorded bug ("喺 App body 讀 = 永遠 default `chat`") is genuinely fixed, and the fix is documented at `App.tsx:17-20` and in `AGENTS.md`.

**Caveat:** the invariant is protected only by a comment. `LayoutContext.tsx:10`'s no-op default means a future violation *compiles clean and misbehaves silently*. Given `6f1c185`'s message records this exact bug biting once, it is the top candidate for a first regression test.

---

## 5. Feature parity — holds at the action/API layer; row #25's wording is over-broad

All three shells reach every view through one of two branches, and both branches pass byte-identical props:

```tsx
// Shells.tsx:20
if (layout === 'chat') return <ChatShell {...p} />
// Shells.tsx:23
return <StandardShell p={p} tabs={def.tabs} home={HOMES[layout as 'journal' | 'dash']} />
```

`StandardShell` is parameterised **only** by `tabs` + `home` (`StandardShell.tsx:13-29`); the only places `tabs` is read are the label (`:47`) and the sidebar highlight (`:37`). Its scene block (`:58-91`) is the single shared mount point for `Chat` + `RightPanel` / `RecordsView` / `ProgressView` / `SettingsView`, plus `<Home p={p} nav={nav} />` (`:59`). The `home` component is rendered as a **JSX element**, not called as a function — `home: Home` is destructured to a capitalised alias at `:25` precisely so JSX treats it as a component type — which is the `AGENTS.md` rule honoured.

Capability matrix (every action demonstrably reachable in every shell): send message, attach photo, edit entry note, delete entry, delete photo, delete insight, product/diet check-in, self-report confirm, settings page, layout picker, test-connection, day/night toggle, conversation rename, conversation delete, export, cloud/consent toggle, and correlations/anchors/memory/timeline display. **No capability is reachable in one shell but not another.** Import is absent from all three (vacuous parity).

Chat shell reachability did **not** regress in the `6f1c185` refactor: `git diff 9ee4ba8..HEAD -- frontend/src/layouts/ChatShell.tsx` is empty, and `ChatShell.tsx:50-62` still mounts `RecordsView`/`ProgressView`/`SettingsView` off the non-compact `Sidebar.tsx:111-120` NAV. The deleted `JournalShell.tsx`/`DashShell.tsx` carried the same scene block, so the refactor merged two ~95 %-identical files without changing what was reachable.

Where the row **is** over-broad:

1. **`blocks.tsx` is not a three-shell shared component.** Imported only by `JournalHome.tsx:3` and `DashHome.tsx:1`. The `chat` shell renders it nowhere — its memory/timeline/correlations are the duplicated inline copies in `RightPanel.tsx` and `ProgressView.tsx` (see #14). `blocks.tsx:5-6` concedes this.
2. **Surface asymmetries are real, even though actions are not.** `journal` is the only shell that renders per-entry product chips (`JournalHome.tsx:129-133`) and the per-recorded-day coach-reply card (`:165-170`); `dash` is the only one with the home widget hall + CTA trio (`DashHome.tsx:40-48, 80-150`); `chat` has **no home scene at all** (`defs.ts:47-53` has no `tabs`, it opens straight into the chat scene at `ChatShell.tsx:16`) and is the only shell with the full site NAV (`Sidebar.tsx:111-135` under `{!compact && …}`, since `StandardShell.tsx:34` passes `compact`). Tab key sets for journal and dash are **equal and in the same order** (`home, chat, records, progress, settings`; `defs.ts:60-66` vs `:74-80`) — only the `home` tab's label/icon differ. So "feature parity" is literally true at the action/API layer, which is the layer that matters, but not at the render-surface layer.

Latent type-lie found en route, all shells affected equally: `StandardShell.tsx:37` casts `'home'` to `View`, but `types.ts:3` defines `View = 'chat' | 'records' | 'progress' | 'settings'` — `tabs[0].key` is `'home'`, not a member. Harmless today only because `compact` suppresses the NAV that consumes `view`. A typecheck-invisible cast (`as View`) is exactly the escape hatch that keeps such a defect green.

---

## 6. `npm run typecheck` and `npm run build`

Both green, exit code 0. Quoted verbatim.

```
$ npm run typecheck
> skincoach-frontend@0.1.0 typecheck
> tsc --noEmit
TYPECHECK_EXIT=0
```

```
$ npm run build
> skincoach-frontend@0.1.0 build
> tsc --noEmit && vite build

vite v5.4.21 building for production...
transforming...
✓ 54 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.99 kB │ gzip:  0.53 kB
dist/assets/index-DvL7yFVz.css   31.45 kB │ gzip:  6.52 kB
dist/assets/index-D92s1t-Q.js   194.45 kB │ gzip: 61.46 kB
✓ built in 671ms
BUILD_EXIT=0
```

No warnings. Disclosure: `npm run build` rewrote the untracked, gitignored `frontend/dist/` (`.gitignore:2 dist/`) — the brief permits running build. Before the rebuild, `dist/` was already newer than every file in `src/` (dist mtime `2026-09-14 20:44:34`; newest source `App.tsx` `2026-09-12 14:12:11`), i.e. **not** stale, and the bundle contained none of the demo-era content (`78`, `阿軒`, `initialConversations`, `helloText` → 0 hits) while containing current-source strings (`get("layout")`, `真數據，冇 demo`, `vs 1M`, `介面結構`). This is only evidence that someone had run `npm run build` recently; it is not evidence about behaviour.

---

## Verdict summary

| Row | Verdict | One-line justification |
|---|---|---|
| **#25** | **DRIFT** | The row's load-bearing verification clause — *"headless DOM smoke (3 套 shell + scene 切換 + drawer + picker) 零 console error"* — cites a harness that **never existed in the repository in any form, at any commit**: no file (the only 4 files ever deleted are non-test), no `test` script in any revision of `frontend/package.json`, no CI step in 20 revisions of `ci.yml`, no stash, no dangling object, and no blob in any of the 543 objects across all refs. The only trace is prose in two commit messages describing an ad-hoc uncommitted run, plus this row. The row also over-claims `blocks.tsx` as three-shell shared (it is imported by the two homes only), and contradicts the unchecked checklist on the same page (`docs/status-vs-claims.md:61`). Everything else in the cell checks out: registry, picker, wireframe thumbs, `skc-layout` persist, `?layout=` override, cross-shell component sharing, typecheck + build green. |
| **#14** | **VERIFIED** | Every right-panel value traces to `/api/conversations/{cid}/summary` (`RightPanel.tsx:56/68` → `api.ts:109-111` → `main.py:228-312`), with deltas/sparklines as local derivations of real fields; the 🌐 marking keys off the real `scope` field computed from `conversation_id IS NULL` (`main.py:298/307`, `models.py:105/131`, pinned by `backend/tests/test_api_layers.py:99-107`); the fake 78-score went away with `frontend/src/data.ts` in `ad05112`, has no importer, and leaves zero residue in `frontend/src` or in `dist`. |
| **#4 (layout switching)** | **VERIFIED** | `LayoutContext.tsx:26-29`/`:33-40` persist `skc-layout`; `:15-19` + `:24-25` + `:34` make `?layout=` a strictly one-page-load override that never writes the preference; `useLayout()` is called only at `App.tsx:22` (inside `LayoutHost`, itself a child of the provider at `App.tsx:280-282`) and `LayoutPicker.tsx:51`. Caveat: `LayoutContext.tsx:10`'s no-op context default means the invariant is defended by a comment, not by an enforced test. |
| **#5 (feature parity)** | **VERIFIED at the action/API layer; row wording DRIFT** | All three shells reach every view and every action through `Shells.tsx:20/23` with identical props; nothing is reachable in one shell only. `chat` reachability was unchanged by `6f1c185` (`ChatShell.tsx` byte-identical since `9ee4ba8`). But `blocks.tsx` is home-only, and render surfaces genuinely differ (journal-only product chips + day cards; dash-only widget hall; chat has no home scene). |
| **#3 (behaviour verification)** | **UNVERIFIABLE OFFLINE — because it does not exist** | There is no automated behaviour verification in this repo: no `test` script, no runner, no linter, no runtime response validation (`api.ts:41 as Promise<T>`). Only `tsc --noEmit` + `vite build`. Concrete undetectable bug: `useSummary.ts:21-34` lacks the `alive` guard its siblings `useCorrelations.ts:15-26` and `RightPanel.tsx:64-78` both have, so a fast body-part switch can render one conversation's metrics/memory/timeline under another's heading in `JournalHome.tsx`/`DashHome.tsx`. |
