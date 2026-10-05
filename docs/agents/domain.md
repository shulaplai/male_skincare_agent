# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo (most repos):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## This repo: **single-context**

Chosen (2026-10-05) because exploration found **no monorepo signals**: no `pnpm-workspace.yaml`, no `workspaces` field in `frontend/package.json`, no `packages/*`, no `yarn.lock`/`pnpm-lock.yaml`. `backend/` and `frontend/` are two apps in one repo with one shared domain, not separate bounded contexts, so one `CONTEXT.md` + `docs/adr/` at the root is right.

**Where the vocabulary already lives, and why it still needs a `CONTEXT.md`:** `AGENTS.md` is 51 KB and mixes four different kinds of text — build commands, a directory map, ten numbered *design conventions*, and a long list of *real bugs we hit*. The conventions are rules (`Deterministic core 行先`, `固定 attribute schema`) and the pitfalls are history (`2026-10-01 用戶指示：片＝一條片`). Nothing separates them, so a reader cannot tell which lines are load-bearing constraints and which are incident reports. `/domain-modeling` should lift the settled decisions into `docs/adr/` and leave `AGENTS.md` pointing at them.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
