# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## State of this repo (2026-10-05)

Chosen: **the default five, unchanged.** Measured against the live repo:

- `wontfix` already existed (GitHub's default label set) → reused as-is, no duplicate created.
- `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human` did **not** exist and were created with `gh label create`.
- The repo's pre-existing GitHub defaults (`bug`, `enhancement`, `documentation`, `question`, …) are **not** part of this vocabulary and are left alone. `wayfinder:*` labels belong to `/wayfinder` (see `issue-tracker.md`).
