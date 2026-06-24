---
description: Begin work on an Issue — idempotently advance to in-progress and start a timesheet segment. No thought required.
agent: yuudev
---

Begin work on Issue **$1**. This is the canonical "I'm starting work" entry point — run these two commands **unconditionally, in order**, and treat whatever they print as the result. Do not pre-check the Issue's status or timesheet state; the scripts are idempotent and report their state.

## Step 1 — advance the Issue to in-progress (idempotent)

```bash
python3 .opencode/skills/issue-lifecycle/scripts/transition.py $1 in-progress
```

- If already `in-progress`, the script prints `no-op: ... already in-progress` and exits 0 — this is normal, continue to Step 2.
- If `approved`, the script performs the transition and prints `ISSUE-NNNN approved→in-progress committed: ...` — this is normal too.
- Non-zero exit = real error (e.g. Issue is `draft` and needs approval first, or `implemented` and is terminal). In that case, **stop and surface the error to the user**; do not continue to Step 2.

## Step 2 — start a timesheet segment (idempotent resume)

```bash
python3 .opencode/skills/issue-lifecycle/scripts/timesheet.py $1 resume --note "ytask-start"
```

- This opens a new `resume→` segment against the local, gitignored timesheet so the `net_effort_hours` metric will be captured when the Issue is later `→implemented`.
- If the timesheet's tail is already `resume` (e.g. the user re-ran `/ytask-start` without pausing), the script prints `no-op: ISSUE-NNNN already active` and exits 0 — this is normal, continue.
- If the tail was `pause`, a new `resume` event is appended and timing resumes. This is the restart-after-lunch case.

## Step 3 — confirm and remind

After both steps print their result, report a one-line status to the user and then, in a short trailing note, remind them:

> 工作计时已开启。如果接下来临时有事（吃饭、下班、切换去别的 Issue、长时间等待），可以输入 `/pause-ytask` 暂停当前 Issue 的计时；下次再用 `/ytask-start ISSUE-NNNN` 一键继续。

This reminder matters because `pause` is always a *human* action — the agent never pauses on its own — and the user will otherwise forget and the `net_effort_hours` metric at `→implemented` will be diluted by idle wall-clock.

## Step 4 — open the worktree

Only now, after the transition commit has landed and the timesheet segment is open, open the worktree / implementation branch as usual for the Issue's coding-instruction workflow. Do **not** open the worktree first — the `→in-progress` transition must land before branching so the commit record stays consistent with the worktree's branch base.
