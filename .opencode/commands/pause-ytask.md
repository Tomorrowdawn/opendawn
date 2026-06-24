---
description: Pause the current Issue's timesheet clock. Invoke this when stepping away — lunch, end of day, switching to another Issue, or a long wait. The agent never pauses on its own; this is a human-initiated cooldown.
agent: yuudev
---

Pause timing on the Issue you are **currently** working on. This is the human-initiated cooldown command — the agent never pauses a clock by itself, so the presence of this command means the user is stepping away.

## Determine the current Issue

From the running session's context (the most recent `/ytask-start ISSUE-NNNN` you executed, or the worktree you currently have open — its name encodes `ISSUE-NNNN`), determine the canonical issue id of the Issue currently being worked on.

- If you can identify exactly one Issue currently being worked on, use its id.
- If the session has no clear current Issue (no `ytask-start` has been run, no worktree is open that names an Issue), **ask the user** which Issue they want to pause: "你想暂停哪个 Issue 的计时？请提供 ISSUE-NNNN 或 slug。" Do not guess.

Once you have the issue id, run **only** the following:

## Step 1 — close the timesheet segment (pause)

```bash
python3 .opencode/skills/issue-lifecycle/scripts/timesheet.py <ISSUE-ID> pause --note "$ARGUMENTS"
```

- `$ARGUMENTS` after the command is treated as the pause note (e.g. `/pause-ytask lunch` → note is `lunch`). If empty, default the note to `"user pause"`.
- This appends a `pause` event to the gitignored timesheet, closing the currently-open `resume→` segment so it stops accumulating wall-clock.
- If the script reports `illegal timesheet event: last event was pause`, that means the clock was already paused — confirm to the user: "Issue ISSUE-NNNN 的计时已经是暂停状态。" Do not treat this as an error.

## Step 2 — confirm to the user

Report a one-line confirmation, e.g.:

> ISSUE-0001 计时已暂停（lunch）。下次继续可直接 `/ytask-start ISSUE-0001` ——命令会幂等地恢复 in-progress 状态并重新 resume 一段计时。

Do **not** transition the Issue out of `in-progress`. Pausing the timesheet is orthogonal to the Issue lifecycle — the Issue remains `in-progress` in the roadmap; only the *clock* has stopped. This is the design: pause/resume is high-frequency, so it stays in the gitignored timesheet and never shows up in `git log`.
