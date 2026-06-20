---
name: what-should-i-do
description: Human-invoked only morning orientation skill for explaining what matters now from roadmap, local work records, task artifacts, and recent git activity. AI agents must not proactively read, invoke, or use this skill during ordinary planning or implementation.
---

# What Should I Do

This skill is for direct human invocation only. AI agents must not proactively read, invoke, or use it during ordinary planning, implementation, review, or handoff work.

Use this skill when a human asks what they should focus on now, especially at the start of a work session. Your job is to build an evidence-based orientation from project records and recent actual activity, then explain the likely next moves with enough scenario context that the human can choose confidently.

Core rule: **orient from evidence, explain scenarios, avoid inventing requirements**.

---

## Sources To Scan

Read these sources in this order when they exist:

1. `roadmap/`
   - Treat this as the git-tracked home for stable long-term plans, target shapes, and desired final states.
   - Use it to understand where current work appears to sit relative to the larger direction.
   - Warn clearly if it is missing, stale, too vague, or too chaotic to orient work.

2. `warroom/`
   - Treat this as local, high-frequency work state if present.
   - Expect rough notes, active decisions, reminders, and near-term coordination.
   - Do not assume it is complete or authoritative unless the project docs say so.

3. `.tmp/{task}/`
   - Treat these as disposable agent execution artifacts and worktrees if present.
   - Look for instruction files, designs, PR notes, worktree state, and blockers.
   - Distinguish unfinished execution artifacts from stable project direction.

4. Git activity
   - Run commands such as:

```bash
git log --oneline --decorate -20
git branch --all
git status --short --branch
git diff --stat
```

   - Use recent commits, branches, dirty state, changed areas, and visible momentum as the primary evidence for recently completed work.

5. Optional external trackers
   - Check external task tools only when project docs such as `AGENTS.md`, `README.md`, or roadmap files explicitly mention them.
   - If no project doc mentions an external tracker but the workflow appears to depend on one, remind the human to record that workflow in `AGENTS.md`.

Do not treat any one source as absolute. Reconcile conflicts by naming them: "roadmap says X, recent git activity suggests Y, dirty worktree contains Z."

---

## Output Contract

Report exactly these four sections.

### 1. Recent Completed Work Summary

Summarize what appears to have been completed recently.

Base this primarily on git evidence:

- recent commits
- branches
- dirty state
- changed areas
- visible momentum

If external task tools are documented in `AGENTS.md` or nearby project docs, mention that you checked or would check them. If they are not documented but appear necessary, remind the human to record that workflow in `AGENTS.md`.

### 2. Roadmap Position

Explain where current development appears to sit relative to `roadmap/`.

Call out whether the roadmap is:

- clear enough to orient work
- stale
- missing key current-state context
- too vague to constrain decisions
- too chaotic to prevent drift

Use this section to help the human avoid overengineering, fake requirements, and work that only feels urgent because it is nearby.

### 3. Current Important Todos

Identify the likely next actions from:

- `roadmap/`
- `warroom/`
- `.tmp/{task}/`
- dirty worktree state
- recent git history

For each important todo, include a short scenario trace that explains why it matters in the workflow.

Use this format:

```text
- Todo: {action}
  Scenario: {actor/context} -> {problem or decision point} -> {why this action matters now}
```

Prefer a few meaningful todos over a long grab bag. If the evidence is weak, say so and frame the todo as a candidate.

### 4. Brief Encouragement

End with one short, grounded encouragement line.

Keep it human and non-cheesy. Tie it to the actual project situation when possible.

---

## Judgment Rules

- Separate facts from inferences.
- Prefer recent git reality over stale planning notes.
- Prefer `roadmap/` for long-term direction over `.tmp/` execution details.
- Prefer `warroom/` for local active context over old commit messages.
- Do not invent deadlines, priorities, or external obligations.
- Do not create or edit files unless the human explicitly asks.
- Do not use this skill as a substitute for a normal planning or implementation workflow.
