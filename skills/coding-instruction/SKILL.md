---
name: coding-instruction
description: Specification for instruction-driven large-task workflow. Loaded manually by YuuDev when writing *-instructions.md, and by YuuCoder when executing one. Defines the instruction format, Change Scope semantics, Test Boundary requirements, blocker protocol, worktree lifecycle, task sizing, and PR doc contract. NOT for direct-mode work — only for work large enough to warrant a dedicated worktree and preflight audit.
user-invocable: true
---

# Coding Instruction

This is a **specification**, not a workflow. Humans opt into it when a task is large enough that the diff alone won't be a sufficient audit. Two roles consume the same spec:

- **Writer** (YuuDev): produces `*-instructions.md` for one YuuCoder run each.
- **Executor** (YuuCoder): reads one `*-instructions.md`, executes inside scope and test boundary.

Both sides reference this file for shared semantics.

## When to Use This

- Task spans multiple modules or files and the user wants to lock scope before execution.
- Task has subtle acceptance criteria (security, concurrency, data integrity) where diff review alone misses "should-have-but-didn't" gaps.
- Task is one slice of a multi-phase plan — needs declarations for parallel/sequential dependencies.
- User explicitly asks for an instruction artifact.

For everything else: direct mode (YuuDev implements, commits) is lighter and sufficient. Don't invoke this spec for trivial work.

## Artifact Layout

```text
.tmp/{task}/
  design.md                      # Optional: from probe-and-plan
  {slug}-instructions.md         # One per YuuCoder run
  pr.md                          # YuuCoder appends here
  worktree/                      # Often the assigned git worktree
```

All task artifacts stay under one root. Never scatter planning or PR files. If a long-running task already has a clean worktree, keep assigning that same worktree so implementation continues in place.

## Instruction Format

Write at `.tmp/{task}/{slug}-instructions.md`:

```markdown
# Coding Instruction: {summary}

**Phase**: {Phase 1 | Phase 2 | ...}
**Branch**: `{type}/{slug}`
**Worktree**: `.tmp/{task}/worktree/` or another preassigned clean checkout
**Estimated scope**: {single YuuCoder run}
**Depends on**: {none | phase | instruction path}
**Can run in parallel with**: {none | instruction path}
**Environment setup**: follow AGENTS.md worktree environment reuse policy

## Objective
{One sentence}

## Background
{Scenario showing why the change is needed}

## Change Scope
May modify:
- `{existing/path-or-glob}` - {why this task owns edits here}

May create:
- `{new/path-or-glob}` - {what kind of new files may be added}

May update if required:
- `{side-effect/path-or-glob}` - {barrel export, registry, generated index, snapshot, metadata, etc.}

Do not touch:
- `{path-or-glob}` - {hard exclusion}

## Pseudocode / Abstract Design
{Data flow, boundaries, decision points. Avoid implementation trivia.}

## Test Boundary
Public entrypoint/API to test:
- `{entrypoint}` - {why this is the boundary}

Observable outcome:
- {User-visible or externally observable behavior that proves success}

Required red test:
- Shape: {test setup, action through the public boundary, assertion on observable outcome}
- Command: `{exact command YuuCoder must run to prove red, then green}`
- Red failure must show missing behavior, not syntax error, bad fixture, missing dependency, or environment failure.

Forbidden test styles:
- Private implementation tests.
- Interaction tests against internals owned by this codebase.
- Brittle unit tests that constrain valid refactoring.
- Removing or rewriting existing bad tests unless `## Change Scope` allows it.

## Implementation Steps
1. {Ordered step}

## Acceptance Criteria
- [ ] {Command or behavior that can be verified}

## Constraints
- Follow: `{convention-doc-path}`
```

### Required Fields

An instruction is incomplete without: `## Objective`, `## Change Scope`, `## Test Boundary`, `## Implementation Steps`, `## Acceptance Criteria`. Missing fields → YuuCoder records a blocker; no implementation starts.

Acceptance criteria must be runnable or directly observable. No acceptance criteria means no handoff. The test boundary must name the public entrypoint, observable outcome, red-test shape, and exact command. No test boundary means no handoff.

## Change Scope Semantics

Four categories. A path must match one allowed category before YuuCoder edits, creates, deletes, moves, or regenerates it. `Do not touch` overrides every other category — if a path matches both, record a blocker.

| Category | Meaning |
|----------|---------|
| `May modify` | Existing files/globs the task may edit |
| `May create` | New file paths/globs the task may add |
| `May update if required` | Narrow side-effect files (barrel exports, registries, generated indexes, snapshots, metadata) — only when the implementation requires it |
| `Do not touch` | Hard exclusion, overrides everything |

Use `none` for empty categories. Pseudocode implying a file outside scope → YuuCoder notes it as a side note, does not patch around it, records a blocker if implementation truly requires it.

## Test Boundary Semantics

The test boundary locks the **public contract**. It defines:

1. Public entrypoint/API to test
2. User-visible or externally observable outcome proving success
3. Required red-test shape
4. Exact command to prove red, then green
5. Forbidden test styles

The red failure must prove **missing behavior**, not:
- Syntax error
- Type error unrelated to the missing behavior
- Bad fixture or malformed test setup
- Missing dependency
- Environment failure
- Assertion against private implementation detail
- Failure caused by unrelated existing behavior

If a valid red test cannot be written within the declared boundary and scope → blocker. YuuCoder does not redesign the boundary.

Use the `yuutest` skill for the red-green subworkflow details.

## Worktree Lifecycle

YuuDev or the human prepares the branch and assigned clean worktree **before** YuuCoder starts. YuuCoder only consumes — it never creates, switches, pulls, rebases, merges, pushes, or otherwise manages branches/worktrees.

Create branch in a task-local worktree only when the user agrees to proceed with a coding instruction:

```bash
git worktree add .tmp/{slug}/worktree -b {type}/{slug} {base-branch}
```

Branch naming:
- `feature/{slug}` for new capability
- `fix/{slug}` for bug fix
- `refactor/{slug}` for structural change

Branches are local-only unless the user explicitly requests a push.

Before handing to YuuCoder: target worktree must exist, be on the intended branch, and be clean. If dirty, resolve or report before handoff; YuuCoder stops on dirty start state.

## Worktree Environment Policy

Before writing instructions for a task requiring an implementation worktree, check `AGENTS.md` for a project-level policy named like:

- `Worktree environment reuse`
- `Worktree Environment`
- `Dependency Cache`
- `Setup Reuse`

If missing, ask the human to add the project-level rule before handoff. Do not guess a cache strategy in the instruction.

Coding instructions should avoid concrete cache implementations unless `AGENTS.md` already defines them. Prefer:

```text
Environment setup: follow AGENTS.md worktree environment reuse policy.
```

Do not globally prescribe reuse for `node_modules`, `.venv`, `target`, package-manager stores, or similar language-specific caches. That is the project's call.

## Task Sizing

One coding instruction must fit in one YuuCoder run. Split larger requests into phases.

Parallel tasks must have:
- No data dependency within the same phase
- Non-overlapping `## Change Scope` entries
- The same assigned branch for the feature
- A preassigned clean worktree for each YuuCoder run, selected by YuuDev or the human

Sequential tasks must declare dependencies.

Example:

```text
Branch: feature/telegram

Phase 1, parallel:
  - model/types instruction
    Worktree: .tmp/telegram/model-types/worktree
    Change Scope:
      May modify: src/model/telegram.ts, src/types/telegram.ts
      May create: none
      May update if required: none
      Do not touch: src/gateway/**, src/capability/**
  - gateway/config instruction
    Worktree: .tmp/telegram/gateway-config/worktree
    Change Scope:
      May modify: src/gateway/telegram.ts, src/config/telegram.ts
      May create: none
      May update if required: src/gateway/index.ts
      Do not touch: src/model/**

Phase 2, after Phase 1:
  - capability instruction
    Worktree: .tmp/telegram/capability/worktree
    Change Scope:
      May modify: src/capability/telegram.ts
      May create: tests/capability/telegram*.test.ts
      May update if required: src/capability/index.ts
      Do not touch: src/gateway/**
```

## PR Doc Contract

YuuCoder appends to `.tmp/{task}/pr.md` after execution. If the file doesn't exist, create it. If it exists, **append** a `## Update: {task-slug}` section — never overwrite prior entries.

```markdown
# PR: {task-slug}

**Branch**: `{branch-name}`
**Worktree**: `{current-worktree-path}`
**Base**: `{base-branch}`
**Instruction**: `.tmp/{task}/{slug}-instructions.md`
**Design**: `.tmp/{task}/design.md` if exists

## Summary
Old scenario:
{What happened before}

Change:
{What changed}

New scenario:
{What happens now}

## Changes
| File | Change |
| --- | --- |
| `{path}` | {One-line description} |

## Commits
- `{sha}` {message}

## Verification
- [x] `{command}` -> {result}
- [x] Acceptance criteria: {N}/{N} met

## Side Notes
{Issues noticed outside scope, not fixed; any `lazy:` deviations taken}
```

Summary should be a **scenario trace**, not prose.

## Blocker Protocol

When YuuCoder encounters an issue during preflight or implementation, it records a blocker and reports:

```text
{task-slug} blocked

Blockers:
1. {specific missing input, scope violation, command failure, or design conflict}
   Evidence: {command output or file reference}
   Needed from user/planner: {exact decision or instruction update}
```

| Situation | Action |
|-----------|--------|
| Intent clear, minor detail unspecified | Use the most obvious local convention |
| Missing acceptance criteria | Record blocker; continue read-only preflight |
| Missing test boundary | Record blocker; continue read-only preflight |
| Missing `## Change Scope` | Record blocker; continue read-only preflight |
| Declared worktree missing or not a git worktree | Record blocker; continue read-only preflight |
| Assigned worktree dirty at start | Record blocker; continue read-only preflight |
| File outside `## Change Scope` required | Record blocker; continue read-only preflight |
| Declared test boundary cannot be tested without internals or expanded scope | Record blocker; continue read-only preflight |
| Existing architecture contradicts instruction | Record blocker; inspect safely for related blockers; report |
| Verification fails | Fix current step; do not proceed |
| Scope complete | Stop; do not add extras |

Before stopping for preflight blockers, YuuCoder finishes every read-only safe check and reports all blockers **at once**. Does not stop after the first missing field or mismatch. Does not edit files, install deps, or run lifecycle git commands while blockers exist.

## Absolute Constraints (executor side)

1. No acceptance criteria → no implementation. Continue read-only preflight; report blockers.
2. No test boundary → no implementation. Continue read-only preflight; report blockers.
3. No `## Change Scope` → no implementation. Continue read-only preflight; report blockers.
4. Work only in the instruction-declared worktree, or current git top-level when not declared.
5. Verification fails → stay on current step.
6. Scope violation → record blocker; do not patch around it.
7. Never touch files outside `## Change Scope`.
8. Scope complete → stop.
9. Self-review (types, debris, acceptance, external libs) → all must pass before delivery.
10. Never create, switch, pull, rebase, merge, push, or otherwise manage branches/worktrees.
11. All artifacts under `.tmp/{task}/`.
12. Run commands to verify. Reading files is not verification.
13. Append to PR docs. Never overwrite prior handoff content.
14. Report all blockers discoverable by safe read-only checks in one response.
