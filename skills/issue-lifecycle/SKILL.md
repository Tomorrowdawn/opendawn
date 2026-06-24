---
name: issue-lifecycle
description: Issue lifecycle management for the roadmap/issues/ system. Provides scripts to transition Issue status (draft→approved→in-progress→implemented) with automatic commits, and to list Issues by status. yuupm uses list.py for triage, priority/milestone cross-checks, and sprint assembly; YuuDev uses transition.py when starting implementation (approved→in-progress, BEFORE opening a worktree) and at merge time (in-progress→implemented). YuuCoder does not use this skill. Loaded by yuupm (always) and YuuDev (before any Issue state change).
user-invocable: true
---

# issue-lifecycle

Manages the state machine for `roadmap/issues/ISSUE-NNNN-*.md`. State changes are script-mediated so the commit record stays consistent with the frontmatter — never edit the `status` field by hand once an Issue is `approved`.

## State machine

```
draft ──[yuupm]──→ approved ──[YuuDev: BEFORE opening worktree]──→ in-progress ──[YuuDev: at user-instructed merge]──→ implemented
```

| Transition | Owner | Trigger |
|------------|-------|---------|
| `draft → approved` | yuupm | User aligns on the scenario. yuupm also sets `priority` and `milestone` at this point (two-axis classification). |
| `approved → in-progress` | YuuDev | **Before** opening the worktree / creating the implementation branch. The transition commit lands first, then YuuDev branches off. |
| `in-progress → implemented` | YuuDev | **At merge time** — when the user instructs YuuDev to merge (direct mode: final verified commit; MANAGER mode: after collecting YuuCoder reports and merging). YuuDev transitions every Issue associated with the merged branch. |

`implemented` is terminal. A new requirement replacing an implemented one goes through ISSUE-CHANGE (see yuupm's triage), not a backwards transition.

## Issue frontmatter schema

```yaml
---
id: ISSUE-0001
slug: {kebab-case-slug}
status: draft | approved | in-progress | implemented
milestone: M-01            # which milestone this issue rolls up into — M-N | all | none
priority: P1               # importance axis — P0 | P1 | P2 | P3
estimated_work_hours: 4
actual_work_hours: 3
implemented_by: <commit/branch/ref>
regression_test: <path or scenario ref>
---
```

- `milestone` — **urgency axis**: which milestone the Issue rolls up into. Concretely, the urgency context is *whether this Issue is bound to the currently-active (WIP) milestone* — `M-N` (links to a specific entry in `roadmap/milestones.md`), `all` (cross-milestone, almost always paired with `priority: P0`), or `none` (organically collected, not bound to a milestone).
- `priority` — **importance axis**, set at `approved` by yuupm with the user after consulting `milestones.md` status. P0 = cross-milestone critical; P1 = load-bearing for its linked milestone; P2 = core incremental, skippable; P3 = minor polish. yuupm applies cross-check rules (an Issue bound to a WIP milestone must be ≥ P2; one that decides the milestone's final shape must be ≥ P1).
- `estimated_work_hours` — set at `approved`, by yuupm with the user, from scenario + `explore` reconnaissance + past Issue git-trend. Recorded **before** sprint selection; never adjusted to fit the 12h core budget.
- `actual_work_hours` — **auto-derived by `transition.py`** at `→implemented`, never filled in by the agent. The script reverse-looks-up the commit that moved this Issue `→in-progress` (matched on the formatted `chore(issue): ISSUE-NNNN …→in-progress` subject) and takes the wall-clock delta between that commit's committer date and the `→implemented` commit (rounded to 0.1h). If no `→in-progress` commit is found, the field is left unset and a warning is printed. Used to display the velocity trend over time.
- `implemented_by` / `regression_test` — set at `implemented`. `regression_test` is the anchor REFACTOR uses to decide which E2E tests survive.

> Re-tiering: editing only `priority` and/or `milestone` (no scenario change) is a re-tier. yuupm does this by editing the frontmatter directly and committing `chore(issue): ISSUE-NNNN re-tier {brief}` — `transition.py` is not used (no state transition occurs).

## Scripts

Both scripts live at `<skill-path>/scripts/`. Resolve `<skill-path>` to this skill's installed directory — `skills/issue-lifecycle` in this repo, or `.opencode/skills/issue-lifecycle` via symlink.

### transition.py

```bash
python3 <skill-path>/scripts/transition.py <ISSUE-ID-or-path> <new-status> \
  [--implemented-by REF] [--regression-test REF]
```

- `<ISSUE-ID-or-path>` accepts: `ISSUE-0001`, `0001`, `1`, or a full path to the `.md` file.
- Validates the transition is legal per the state machine. Illegal transition → non-zero exit, no edit.
- Edits the `status` frontmatter field. When transitioning to `implemented`, also writes `implemented_by` / `regression_test` if the flags are provided, and **auto-computes `actual_work_hours`** from git (see schema above). Preserves `priority` / `milestone` / `estimated_work_hours` (and any other fields) in the canonical frontmatter order.
- **No `--actual-hours` flag** — timing is always derived from the formatted transition commits, never supplied by the agent.
- Commits with `chore(issue): ISSUE-NNNN <old>→<new>` **only if a transition actually occurred**. No-op (exit 0, no commit) if the Issue is already in the target status.
- Does **not** handle re-tiering (priority/milestone-only edits) — that's yuupm's direct-edit + `chore(issue): ... re-tier` commit, because no state transition occurs.

### list.py

```bash
python3 <skill-path>/scripts/list.py [status-filter]
```

- Scans `roadmap/issues/ISSUE-*.md`, parses frontmatter, prints a table.
- No filter → all Issues. Filter → one of `draft | approved | in-progress | implemented`.
- Columns: `ID`, `Slug`, `Status`, `Priority`, `Milestone`, `Est.h`, `Act.h`, `Title` (first H1).
- yuupm reads Priority (sorted) and Milestone to apply cross-check rules during triage and sprint assembly.

## Who calls what

| Agent | Script | When |
|-------|--------|------|
| yuupm | `list.py` | Triage, two-axis cross-checks (priority + milestone), sprint assembly from the approved backlog, drift detection. |
| yuupm | — (edits file directly, then commits `chore(issue): ISSUE-NNNN draft→approved`) | Sets `status: approved` and sets `priority` + `milestone` at approval. |
| yuupm | — (edits frontmatter directly) | Re-tiering priority/milestone with no state transition — commits `chore(issue): ISSUE-NNNN re-tier {brief}`. |
| YuuDev | `transition.py ... in-progress` | **Before** opening the worktree / creating the implementation branch for an approved Issue. |
| YuuDev | `transition.py ... implemented` | **At merge time** — when the user instructs a merge. Transitions every Issue associated with the merged branch. `actual_work_hours` is auto-computed; pass `--implemented-by` / `--regression-test`. |
| YuuCoder | — | Never. Pure implementation. |

> **Note on `draft → approved`**: yuupm owns the writing phase and may edit the Issue file freely (scenario, frontmatter including priority/milestone) before approval. Once `status: approved` is set, the Issue is a contract — only `transition.py` touches the `status` field after that, and only YuuDev invokes it. yuupm may still edit `priority`/`milestone` (re-tier) post-approval without a state transition. yuupm sets `approved` by editing the frontmatter directly and committing with `chore(issue): ISSUE-NNNN draft→approved`.
