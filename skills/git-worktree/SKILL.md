---
name: git-worktree
description: Safe git development workflow using worktrees for isolated coding, conventional commits, mandatory self-review, and PR documentation. Triggers on any code change that touches git — implementing features, fixing bugs, refactoring, or preparing code for review.
user-invocable: true
---

# Git Worktree — Safe Development Workflow

> "Work in isolation. Review before delivery. Never touch main."

This skill enforces a disciplined git workflow designed to prevent mistakes before they happen. Every code change happens in an isolated git worktree, passes a mandatory self-review, and produces a documented handoff artifact.

---

## Core Principles

### 1. Worktree Isolation — Never Touch the Main Tree

All code changes happen in an isolated `git worktree` — an independent checkout with its own working directory. Commits happen inside the worktree. Pushes never happen. The main working tree is never touched.

```
.tmp/{task}/
  worktree/          # git worktree — ALL code changes happen here
  pr.md              # PR document written after implementation
```

This means:
- Multiple parallel tasks on the same branch → each gets its own worktree
- Worktree gets dirty or broken → delete and recreate, main tree is untouched
- Branch is shared, working directories are isolated

### 2. Design Decisions Are Settled Before Code

Implementation does not question design. If a coding instruction is ambiguous (but most likely intent is clear), implement the most obvious interpretation. If key information is missing and cannot be inferred, **stop and ask**.

### 3. Scope Is Sacred

Every task has a declared set of files it owns. You must NOT create or modify files outside this set. If the implementation implies touching a file outside scope → stop and report, do not patch around it. Do not "improve" adjacent code. Do not fix things you notice outside scope.

### 4. Enough Is Enough

Scope completed → stop immediately. Do not:
- Refactor code the task didn't touch
- Add "nice-to-have" improvements
- Fix tangential issues (note them in the PR document instead)

---

## SOP: Setup

### Step 1 — Create Worktree

Create an isolated working directory from the feature branch:

```bash
git worktree add .tmp/{task}/worktree {branch}
```

Multiple parallel workers on the same branch share the branch via separate worktrees.

### Step 2 — Enter Worktree

```bash
cd .tmp/{task}/worktree
```

### Step 3 — Sync with Parallel Workers

Before starting work, pull changes from others on the same branch:

```bash
git pull --rebase origin {branch} 2>/dev/null || true
```

If pull fails (conflicts with parallel worker's changes) → **Stop.** Rebase conflict indicates overlapping file claims — a planning defect.

### Step 4 — Verify State

```bash
git status --short
git branch   # confirm on the assigned branch
```

Dirty working tree? → **Stop.** Report: "Worktree is dirty. Cannot start with unclean state."

---

## SOP: Implement

### Incremental Execution

Implement **one step at a time**, as ordered.

After each step:
1. Type-check — run the project's type-check command
2. Build — if the project requires a build step, run it
3. Run relevant tests — run the exact test command from acceptance criteria

Verification passes → continue to next step. Verification fails → **stay on current step.** Fix the issue. Do not proceed.

### Commit Discipline

Commit after each **logically complete unit**, not after each file save.

**Commit message format:**

```
{type}({scope}): {brief description}

{Optional body — why, not what}
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`
Scope: the module/package name

**Example:**

```
feat(auth): add JWT refresh token rotation

Refresh tokens are now single-use. Each refresh issues a new
token pair and invalidates the previous refresh token.
```

---

## SOP: Self-Review

Four mandatory checks. All must pass before delivery.

### Check 1: Types & Imports

Run the project's type-check command. Then manually verify:
- Function signatures match call sites
- All import paths resolve (confirm files exist)
- No circular dependencies introduced

### Check 2: Debris Scan

Search changes for:
- `console.log` / `print` / debug statements
- `TODO` / `FIXME` / `HACK` comments
- Hardcoded secrets, tokens, passwords
- Empty `try`/`catch` blocks

### Check 3: Acceptance Criteria — Run the Commands

Go through each acceptance criterion one by one. **Run the exact command** that exercises it. Do not substitute a weaker check.

- Criterion says "test X passes" → run the test command, check exit code and output.
- Criterion says "feature Y works" → run the program with expected input, check output.
- Criterion says "endpoint Z returns" → curl it, check the response body, not just the status code.

One criterion unmet → fix before delivering.

### Check 4: External Library Verification

If external libraries were used → run a test that actually exercises the library in context. Never rely on training-data memory for this check.

### Self-Review Pass Mark

```
Self-Review: ✅ Types | ✅ Imports | ✅ No debris | ✅ Criteria met (N/N) | ✅ External libs OK
```

---

## SOP: Deliver

### Step 1 — PR Document

Write a PR document at `.tmp/{task}/pr.md`:

```markdown
# PR: {task-slug}

**Branch**: `{branch-name}`
**Worktree**: `.tmp/{task}/worktree/`
**Base**: `main`

## Summary

{
  The Old Scenario
  Changes
  The New Scenario
}

## Changes

| File | Change |
|------|--------|
| `{path}` | {One-line description} |

## Commits
- `{sha}` {message}

## Verification
- [x] Type check passes
- [x] Lint passes
- [x] Tests pass: `{test command + result}`
- [x] Acceptance criteria: {count}/{count} met

## Side Notes
{Any issues noticed outside scope, NOT fixed}
```

### Step 2 — Report Completion

```
✅ {task-slug} COMPLETED

Worktree: .tmp/{task}/worktree/
Branch: {branch-name}
PR document: .tmp/{task}/pr.md
Commits: {count}

Self-Review: ✅ Types | ✅ Imports | ✅ No debris | ✅ Criteria met (N/N) | ✅ External libs OK

Side notes: {if any}
```

---

## Branch Lifecycle

### Branch Naming

- `feature/{slug}` — new capability or significant addition
- `fix/{slug}` — bug fix
- `refactor/{slug}` — restructuring without behavior change

### Branch Rules

- Branches are **local-only** until explicitly merged. No push. No remote.
- One feature = one branch. All phases share the same branch.
- Parallel workers on the same branch use separate worktrees.

### Merge Gate

After all work on a branch is complete, do NOT auto-merge. Wait for an explicit human command:

```
MERGE REQUIRED: feature/{slug} is complete.
Ready to merge to {base-branch}. Say "merge feature/{slug} to {base-branch}" when ready.
```

When the human explicitly says to merge:

```bash
git checkout {base-branch}
git merge feature/{slug}
```

**Never auto-merge. Never assume. The human decides when the branch lands.**

### Cleanup

If work is abandoned:

```bash
git branch -D feature/{slug}
rm -rf .tmp/{task}/
git worktree prune
```

---

## Exception Handling

| Situation | Action |
|-----------|--------|
| Instruction ambiguous (but likely intent clear) | Implement the most obvious interpretation. Do NOT interrupt. |
| Instruction missing key info (cannot infer) | **Stop.** "Instruction lacks {info}. Cannot proceed." |
| Task touches file outside declared scope | **Stop.** "File {path} is outside scope. Scope violation." |
| Rebase conflict with parallel worker | **Stop.** "Rebase conflict. File claims overlap — planning defect." |
| Implementation requires changing files outside scope | **Stop.** "This requires changes to {files} — outside scope." |
| Implementation conflicts with existing architecture | **Stop.** "Conflict: {description}. This should be resolved before implementation." |
| Test/lint/typecheck failure mid-implementation | **Stop.** Fix the current step. Do not skip ahead. |
| Worktree creation fails | **Stop.** Report the exact error. |
| Worktree dirty at start | **Stop.** Report dirty state. |

---

## File Organization — All Under One Root

All task artifacts live under a single task directory:

```
.tmp/{task}/
  design.md          # Design document (read-only for implementation)
  instructions.md    # Coding instructions
  pr.md              # PR document (written after implementation)
  worktree/          # Git worktree — ALL code changes happen here
```

Rules:
- NEVER create files outside `.tmp/{task}/`.
- ALWAYS edit existing files. Do NOT create new files when an existing one can hold the content.
- When in doubt: can this task be cleaned up with `rm -rf .tmp/{task}/`? If no, files are scattered.

---

## Absolute Constraints

1. **No acceptance criteria → no start.** Cannot verify completion.
2. **No branch assigned → no start.** No place to commit.
3. **No file scope declared → no start.** Cannot determine boundaries.
4. **Verification fails → stay on current step. Do not proceed.**
5. **Scope violation → stop and report. Do not patch around it.**
6. **Never touch files outside declared scope.**
7. **Scope completed → stop immediately. No extras.**
8. **Self-review 4 checks → all must pass before delivery.**
9. **Never push. Never touch the main working tree.** Worktree only. PR document is the handoff artifact.
10. **ALL artifacts under `.tmp/{task}/`.**
11. **Run commands to verify. Reading files is not verification.** Run the exact commands from acceptance criteria.

---

## When to Trigger

Load this skill when:
- **Implementing** any code change — feature, bug fix, or refactor
- **Working with git** — creating branches, committing, reviewing changes
- **Preparing code for review** — writing PR documents, self-review
- **Coordinating** parallel work with other developers/agents
- **Establishing** git workflow conventions for a project
