---
name: req-lifecycle
description: Requirement lifecycle management for the roadmap/reqs/ system. Provides scripts to transition REQ status (draft→approved→in-progress→implemented) with automatic commits, and to list REQs by status. yuupm uses list.py for triage and sprint sync; YuuDev uses transition.py when starting implementation (approved→in-progress) and at branch merge (in-progress→implemented). YuuCoder does not use this skill. Loaded by yuupm (always) and YuuDev (before any REQ state change).
user-invocable: true
---

# req-lifecycle

Manages the state machine for `roadmap/reqs/REQ-NNNN-*.md`. State changes are script-mediated so the commit record stays consistent with the frontmatter — never edit the `status` field by hand.

## State machine

```
draft ──[yuupm]──→ approved ──[YuuDev: start implement]──→ in-progress ──[YuuDev: branch merge]──→ implemented
```

| Transition | Owner | Trigger |
|------------|-------|---------|
| `draft → approved` | yuupm | User aligns on the scenario. |
| `approved → in-progress` | YuuDev | Starting implementation of the REQ. Commit on transition. |
| `in-progress → implemented` | YuuDev | At branch merge (sub-dev-branch → dev branch). Commit on transition. |

`implemented` is terminal. A new requirement replacing an implemented one goes through REQ-CHANGE (see yuupm's triage), not a backwards transition.

## REQ frontmatter schema

```yaml
---
id: REQ-0001
slug: {kebab-case-slug}
status: draft | approved | in-progress | implemented
derived_from: sprint.md#milestone-X
estimated_work_hours: 4
actual_work_hours: 3
implemented_by: <commit/branch/ref>
regression_test: <path or scenario ref>
---
```

- `estimated_work_hours` — set at `approved`, by yuupm with the user.
- `actual_work_hours` — set at `implemented`, by YuuDev. Used to correct the velocity coefficient over time.
- `implemented_by` / `regression_test` — set at `implemented`. `regression_test` is the anchor REFACTOR uses to decide which E2E tests survive.

## Scripts

Both scripts live at `<skill-path>/scripts/`. Resolve `<skill-path>` to this skill's installed directory — `skills/req-lifecycle` in this repo, or `.opencode/skills/req-lifecycle` via symlink.

### transition.py

```bash
python3 <skill-path>/scripts/transition.py <REQ-ID-or-path> <new-status> \
  [--implemented-by REF] [--regression-test REF] [--actual-hours N]
```

- `<REQ-ID-or-path>` accepts: `REQ-0001`, `0001`, `1`, or a full path to the `.md` file.
- Validates the transition is legal per the state machine. Illegal transition → non-zero exit, no edit.
- Edits the `status` frontmatter field. When transitioning to `implemented`, also writes `implemented_by` / `regression_test` / `actual_work_hours` if the flags are provided.
- Commits with `chore(req): REQ-NNNN <old>→<new>` **only if a transition actually occurred**. No-op (exit 0, no commit) if the REQ is already in the target status.

### list.py

```bash
python3 <skill-path>/scripts/list.py [status-filter]
```

- Scans `roadmap/reqs/REQ-*.md`, parses frontmatter, prints a table.
- No filter → all REQs. Filter → one of `draft | approved | in-progress | implemented`.
- Columns: `ID`, `Slug`, `Status`, `Est.h`, `Act.h`, `Title` (first H1).

## Who calls what

| Agent | Script | When |
|-------|--------|------|
| yuupm | `list.py` | Triage, sprint sync, drift detection. |
| yuupm | — (edits file directly, then `transition.py` is not used for draft→approved) | `draft → approved` is committed by yuupm editing the frontmatter directly; the script exists for YuuDev's transitions. *(See note below.)* |
| YuuDev | `transition.py ... in-progress` | Starting implementation of an approved REQ. |
| YuuDev | `transition.py ... implemented` | At branch merge completing a REQ. |
| YuuCoder | — | Never. Pure implementation. |

> **Note on `draft → approved`**: yuupm owns the writing phase and may edit the REQ file freely (scenario, frontmatter) before approval. Once `status: approved` is set, the REQ is a contract — only `transition.py` touches the `status` field after that. yuupm sets `approved` by editing the frontmatter directly and committing with `chore(req): REQ-NNNN draft→approved`.
