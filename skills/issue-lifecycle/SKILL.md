---
name: issue-lifecycle
description: Issue lifecycle management for the roadmap/issues/ system. Provides scripts to transition Issue status (draft→approved→in-progress→implemented) with automatic commits, to list Issues by status, and to track net working time via local gitignored timesheets. yuupm uses list.py for triage, priority/milestone cross-checks, and sprint assembly; YuuDev uses transition.py when starting implementation (approved→in-progress, BEFORE opening a worktree) and at merge time (in-progress→implemented). YuuDev may also call timesheet.py at any point while an Issue is in-progress to capture pause/resume events for the net_effort metric. YuuCoder does not use this skill. Loaded by yuupm (always) and YuuDev (before any Issue state change).
user-invocable: true
---

# issue-lifecycle

Manages the state machine for `roadmap/issues/ISSUE-NNNN-*.md`. State changes are script-mediated so the commit record stays consistent with the frontmatter — never edit the `status` field by hand once an Issue is `approved`.

State and timing are decoupled: the Issue **lifecycle state machine** (4 states, below) never edits the `status` field for pause/resume events — those are tracked in a separate, local, gitignored timesheet (see `timesheet.py` under Scripts). Lifecycle transitions always commit; timesheet events never do. The schema distinguishes three timing fields accordingly: `cycle_hours` (wall-clock, always computable from git), `net_effort_hours` (true working time, only if the timesheet was used), and `efficiency` (their ratio).

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
cycle_hours: 8.5
net_effort_hours: 3.0
efficiency: 0.35
implemented_by: <commit/branch/ref>
regression_test: <path or scenario ref>
---
```

- `milestone` — **urgency axis**: which milestone the Issue rolls up into. Concretely, the urgency context is *whether this Issue is bound to the currently-active (WIP) milestone* — `M-N` (links to a specific entry in `roadmap/milestones.md`), `all` (cross-milestone, almost always paired with `priority: P0`), or `none` (organically collected, not bound to a milestone).
- `priority` — **importance axis**, set at `approved` by yuupm with the user after consulting `milestones.md` status. P0 = cross-milestone critical; P1 = load-bearing for its linked milestone; P2 = core incremental, skippable; P3 = minor polish. yuupm applies cross-check rules (an Issue bound to a WIP milestone must be ≥ P2; one that decides the milestone's final shape must be ≥ P1).
- `estimated_work_hours` — set at `approved`, by yuupm with the user, from scenario + `explore` reconnaissance + past Issue git-trend. Recorded **before** sprint selection; never adjusted to fit the 12h core budget.
- `cycle_hours` — **wall-clock cycle time**, auto-derived by `transition.py` at `→implemented`. The script reverse-looks-up the commit that moved this Issue `→in-progress` (matched on the formatted `chore(issue): ISSUE-NNNN …→in-progress` subject) and takes the wall-clock delta between that commit's committer date and the `→implemented` commit (rounded to 0.1h). Includes lunch, sleep, and cross-task interruptions — **deliberately**, because cycle length is itself a signal of environmental friction (long cycle ≠ laziness; long cycle hints at context-switching cost). If no `→in-progress` commit is found, the field is left unset and a warning is printed.
- `net_effort_hours` — **true working time**, auto-derived by `transition.py` at `→implemented` from the local, gitignored timesheet at `roadmap/issues/.timetracking/ISSUE-NNNN.jsonl` (populated by `timesheet.py pause/resume`). Sums all `resume→pause` segments; if the tail is an un-closed `resume`, auto-closes it with `now`. **Leaving the timesheet empty is legal** — the field is then left unset (and a warning is printed); `cycle_hours` is still computed. Used to answer "did the next issue actually take the time we estimated?" — calibration for `estimated_work_hours` on future Issues.
- `efficiency` — density signal = `net_effort_hours / cycle_hours` (rounded to 0.01). Left unset if either input is missing or zero, or if net > cycle (timesheet may be corrupt). 0.35 means "35% of the cycle was actual working time"; 0.8 means "almost no interruptions". Displayed as a percentage column in `list.py` for at-a-glance friction spotting across Issues.
- `implemented_by` / `regression_test` — set at `implemented`. `regression_test` is the anchor REFACTOR uses to decide which E2E tests survive.

> Re-tiering: editing only `priority` and/or `milestone` (no scenario change) is a re-tier. yuupm does this by editing the frontmatter directly and committing `chore(issue): ISSUE-NNNN re-tier {brief}` — `transition.py` is not used (no state transition occurs).

## User-facing commands (`/ytask-start`, `/pause-ytask`)

Two opencode commands live at `.opencode/commands/` and route to `agent: yuudev`. They are the canonical wrappers over the working-clock loop and are designed to be **re-runnable without thought**:

| Command | What it does | Idempotence |
|---------|--------------|-------------|
| `/ytask-start ISSUE-NNNN` | YuuDev runs `transition.py ISSUE-NNNN in-progress` then `timesheet.py ISSUE-NNNN resume`. This is the canonical "I'm starting work on this Issue" entry point; it advances lifecycle state to `in-progress` **and** opens a working-clock `resume` segment in one shot. | Both calls are idempotent: `transition.py` no-ops when already `in-progress`; `timesheet.py resume` no-ops when the timesheet tail is already `resume`. Repeat invocations are safe. |
| `/pause-ytask [note]` | YuuDev runs `timesheet.py <current-issue> pause --note "<note>"`. The agent infers the current Issue from session context (most recent `/ytask-start`, or the worktree's name). If multiple/no Issues are current, YuuDev asks. | `timesheet.py pause` is **strict, not idempotent**: a `pause` against an already-resting tail is a real error (the user would otherwise silently lose intent). This is intentional — pause is always a *human* action and repeat-pause means a state confusion worth surfacing. |

**YuuDev's reminder hook**: at any natural round-end checkpoint (test complete + awaiting verification, scenario implemented + awaiting decision, MANAGER-mode reports collected + awaiting merge instruction), YuuDev appends a one-line boilerplate reminder:

> 提示:如要离开可 `/pause-ytask [原因]` 暂停计时。

This keeps the option visible without becoming noise. YuuDev does **not** remind after `→implemented` (the timesheet is closed and archived at that point); instead it surfaces the accounting line `net=Xh / cycle=Yh (efficiency Z)`.

## Scripts

All three scripts live at `<skill-path>/scripts/`. Resolve `<skill-path>` to this skill's installed directory — `skills/issue-lifecycle` in this repo, or `.opencode/skills/issue-lifecycle` via symlink.

```bash
python3 <skill-path>/scripts/transition.py <ISSUE-ID-or-path> <new-status> \
  [--implemented-by REF] [--regression-test REF] [--no-archive]
python3 <skill-path>/scripts/timesheet.py <ISSUE-ID-or-path> <pause|resume|status> \
  [--note "..."]
python3 <skill-path>/scripts/list.py [status-filter]
```

### transition.py

```bash
python3 <skill-path>/scripts/transition.py <ISSUE-ID-or-path> <new-status> \
  [--implemented-by REF] [--regression-test REF] [--no-archive]
```

- `<ISSUE-ID-or-path>` accepts: `ISSUE-0001`, `0001`, `1`, or a full path to the `.md` file.
- Validates the transition is legal per the state machine. Illegal transition → non-zero exit, no edit.
- Edits the `status` frontmatter field. When transitioning to `implemented`:
  - writes `implemented_by` / `regression_test` if the flags are provided,
  - **auto-computes `cycle_hours`** from git (wall-clock delta from the `→in-progress` commit),
  - **auto-computes `net_effort_hours`** from the local timesheet jsonl (sum of `resume→pause` segments; auto-closes a trailing `→resume` with `now`),
  - **auto-computes `efficiency`** = net/cycle (skipped if either input is missing or net > cycle),
  - **archives the timesheet** to `.timetracking/archive/ISSUE-NNNN.jsonl` (or deletes it with `--no-archive`).
  - Preserves `priority` / `milestone` / `estimated_work_hours` (and any other fields) in the canonical frontmatter order.
- **No `--cycle-hours` / `--net-effort-hours` / `--efficiency` flags** — timing is always derived from git + the local timesheet, never supplied by the agent.
- Commits with subject `chore(issue): ISSUE-NNNN <old>→<new>`. When transitioning to `implemented`, the commit **body** carries an accounting line so `git show` reveals the timing breakdown without bloating the log:
  ```
  chore(issue): ISSUE-0001 in-progress→implemented

  actual: net=3.0h / cycle=8.5h (efficiency 0.35)
  ```
  If no timesheet events were recorded:
  ```
  chore(issue): ISSUE-0001 in-progress→implemented

  actual: cycle=8.5h (no timesheet; net_effort not tracked)
  ```
- No-op (exit 0, no commit) if the Issue is already in the target status. **This makes `transition.py ISSUE-NNNN in-progress` idempotent** — re-running it after the Issue is already `in-progress` is safe and is exactly what `/ytask-start` relies on (it calls the transition unconditionally; the no-op message is the normal "already started" branch). The same applies to `timesheet.py ... resume` (idempotent when the timesheet tail is already `resume`); **`timesheet.py ... pause` is strict** — pause-after-pause is an error, because pause is always a human action and a repeat means the user lost track of state.
- Does **not** handle re-tiering (priority/milestone-only edits) — that's yuupm's direct-edit + `chore(issue): ... re-tier` commit, because no state transition occurs.

### timesheet.py

```bash
python3 <skill-path>/scripts/timesheet.py <ISSUE-ID-or-path> <pause|resume|status> \
  [--note "..."]
```

Append-only, **gitignored** jsonl at `roadmap/issues/.timetracking/ISSUE-NNNN.jsonl`. Each line is one event:

```jsonl
{"ts":"2026-06-24T09:00:00+08:00","event":"resume","note":"started work"}
{"ts":"2026-06-24T12:30:00+08:00","event":"pause","note":"lunch"}
{"ts":"2026-06-24T13:30:00+08:00","event":"resume","note":"back from lunch"}
{"ts":"2026-06-24T17:00:00+08:00","event":"pause","note":"end of day"}
```

- The first event MUST be `resume`; events alternate `resume → pause → resume → pause → …`. A violation (e.g. `pause` when the tail is already `pause`, or `resume` as the first event) → exit 1, no write.
- `status` command prints the tail state (`active` if the last event is `resume`, else `resting`), the count of segments, and the running net-effort total (including the open segment up to `now` if `active`).
- The file is **local and never enters git history** — `.gitignore` excludes `roadmap/issues/.timetracking/`. This avoids polluting `git log` with high-frequency pause/resume commits while keeping the per-Issue ledger accessible on the working machine.
- On `→implemented`, `transition.py` reads this file, computes `net_effort_hours`, writes the field to frontmatter, and moves the file to `.timetracking/archive/ISSUE-NNNN.jsonl` (or deletes it with `--no-archive`). The archive is also local-only.
- **Leaving the timesheet empty is legal.** An Issue implemented without any `timesheet.py` calls simply lacks `net_effort_hours` / `efficiency`; `cycle_hours` is still computed. The motivating case: if you only care about the cycle (wall-clock) signal for a quick issue, you don't have to babysit the timesheet.

### list.py

```bash
python3 <skill-path>/scripts/list.py [status-filter]
```

- Scans `roadmap/issues/ISSUE-*.md`, parses frontmatter, prints a table.
- No filter → all Issues, **capped at 15** to protect agent context. Explicit filter (one of `draft | approved | in-progress | implemented`) → **uncapped** (the agent asked for one status; show all of it).
- Sort order (applied whether or not a filter is set): **status-rank → priority-rank → ID**.
  - Status rank: `in-progress` (0) → `approved` (1) → `draft` (2) → `implemented` (3); unknown status sorts last. Active/incoming work surfaces first; terminal Issues truncate first when the cap bites.
  - Priority rank within a status group: `P0` → `P3`; unknown priority sorts last.
- Columns: `ID`, `Slug`, `Status`, `Pri`, `Milestone`, `Est.h`, `Cyc.h`, `Net.h`, `Eff%`, `Title` (first H1). `Cyc.h` / `Net.h` are empty for non-implemented Issues; `Eff%` is shown as a percentage (e.g. `35%`).
- When the cap truncates, a `(showing 15 of N — …)` notice prints after the table; pass a status-filter to see the rest of one status.
- yuupm reads Priority (sorted) and Milestone to apply cross-check rules during triage and sprint assembly. The `Net.h` / `Eff%` columns surface friction at a glance — an Issue with `net=3h` / `cycle=8.5h` / `Eff%=35%` was worked on for roughly the estimated time but the cycle was heavily interrupted.

## Who calls what

| Agent | Script | When |
|-------|--------|------|
| yuupm | `list.py` | Triage, two-axis cross-checks (priority + milestone), sprint assembly from the approved backlog, drift detection. |
| yuupm | — (edits file directly, then commits `chore(issue): ISSUE-NNNN draft→approved`) | Sets `status: approved` and sets `priority` + `milestone` at approval. |
| yuupm | — (edits frontmatter directly) | Re-tiering priority/milestone with no state transition — commits `chore(issue): ISSUE-NNNN re-tier {brief}`. |
| YuuDev | `transition.py ... in-progress` | **Before** opening the worktree / creating the implementation branch for an approved Issue. |
| YuuDev | `timesheet.py ... pause/resume` | Optional, at any point while an Issue is `in-progress`, to capture true working intervals for the `net_effort_hours` metric. Recommended before any context switch (lunch, EOD, switching to another Issue, waiting on a long review). Not invoking it is legal — the Issue simply lacks net_effort/efficiency at `→implemented`. |
| YuuDev | `transition.py ... implemented` | **At merge time** — when the user instructs a merge. Transitions every Issue associated with the merged branch. `cycle_hours` is auto-computed from git; `net_effort_hours` / `efficiency` are auto-computed from the local timesheet if present. Pass `--implemented-by` / `--regression-test`. |
| YuuCoder | — | Never. Pure implementation. |

> **Note on `draft → approved`**: yuupm owns the writing phase and may edit the Issue file freely (scenario, frontmatter including priority/milestone) before approval. Once `status: approved` is set, the Issue is a contract — only `transition.py` touches the `status` field after that, and only YuuDev invokes it. yuupm may still edit `priority`/`milestone` (re-tier) post-approval without a state transition. yuupm sets `approved` by editing the frontmatter directly and committing with `chore(issue): ISSUE-NNNN draft→approved`.

> **Note on timesheet vs lifecycle**: `timesheet.py` operates **inside** the `in-progress` state — it does not change the Issue's lifecycle `status` and never commits. Pause/resume is a high-frequency, local-only event; mixing it into the lifecycle state machine would (a) pollute `git log` with `chore(issue): ... paused` noise, and (b) conflate "the Issue's requirement lifecycle" (draft/approved/in-progress/implemented) with "the human's working rhythm". Keeping them separate means a 5-interruption Issue still produces exactly one `→implemented` commit, with the timing breakdown in its body.
