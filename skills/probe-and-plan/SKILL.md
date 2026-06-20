---
name: probe-and-plan
description: Phase 1 planning workflow for coding agents. Use when clarifying requirements, investigating unclear bugs, designing features or refactors, splitting work, creating feature branches, writing coding instructions, or preparing a handoff to an implementation agent. Emphasizes run real commands, ask early, avoid overthinking, and ground discussion in concrete scenarios.
---

# Probe and Plan

Your job is to turn vague work into executable coding instructions. Do not write production code. Run commands to gather evidence, ask when intent is unclear, agree on the shape of the solution, then hand off to an implementation agent.

Core rule: **run first, ask early, do not overthink**.

---

## Operating Model

1. **Probe before theorizing.** If a command can verify a claim, run it. Reading files is not a substitute for execution.
2. **Ask before inventing.** If intent, acceptance criteria, branch, or file ownership is missing, surface the gap. Do not silently make design decisions that should belong to the user.
3. **Present the smallest useful scenario.** Use scenario traces, pseudocode, or test sketches to make the proposed behavior concrete.
4. **Delete speculative complexity.** Keep only what the scenario forces you to keep. Add back details only after a command, user answer, or concrete edge case requires them.
5. **Handoff cleanly.** Produce instructions that an implementation agent can execute without rediscovering the plan.

---

## Git Reconnaissance

Before planning in a git repository, run:

```bash
git log --oneline -20
git branch -a
git status --short
```

Then read the project `AGENTS.md` if it exists.

Use this to understand recent changes, active branches, dirty state, and project-level worktree setup rules. If the working tree is dirty, do not overwrite unrelated changes. Plan around them or report the conflict.

---

## Worktree Environment Policy

Before writing instructions for a task that will require an implementation worktree, check `AGENTS.md` for a project-level policy named like:

- `Worktree environment reuse`
- `Worktree Environment`
- `Dependency Cache`
- `Setup Reuse`

If the policy is missing, ask the human to add project-level rules before handoff. Do not guess a cache strategy in the coding instruction.

Coding instructions should avoid concrete cache implementations unless `AGENTS.md` already defines them. Prefer:

```text
Environment setup: follow AGENTS.md worktree environment reuse policy.
```

Do not globally prescribe reuse for `node_modules`, `.venv`, `target`, package-manager stores, or similar language-specific caches from this platform-independent skill.

---

## Command Discipline

Run the real command that exercises the claim:

- Bug report: run the reproduction command before reading source as the primary investigation path.
- Feature behavior: run an existing demo, CLI, endpoint, or minimal script that would exercise the expected path.
- Tool availability: run the tool, do not infer from package files alone.
- Verification: use command output and exit codes, not file presence.

If the command cannot run because required input is missing, ask for that input and state exactly what is blocked.

---

## Use Scenarios

Use a scenario when it lowers ambiguity. Pick the abstraction level that exposes the problem.

Architectural trace:

```text
User message
  -> Gateway.ingest()
    -> Router.match()
      -> Conversation.enqueue()
        -> Actor runs agent turn
          -> Capability call
            -> Integration sends response
```

Debug trace:

```text
Request
  -> API gateway route lookup
    -> matches legacy rule
      -> forwards /api/v2/users to v1 service
        -> v1 router has no endpoint
          -> 404
```

When presenting a fix, show:

```text
Current path: request -> wrong owner does X -> failure
Target path:  request -> correct owner does Y -> expected result
```

Avoid dumping implementation details unless the discussion is already at implementation level.

---

## Task Classification

Classify the request before writing instructions:

| Request shape | Route |
| --- | --- |
| Error, crash, broken behavior, failing command | Bug |
| New capability, support for a case, integration | Feature |
| Cleanup, simplification, architecture correction | Refactor |
| Unclear or mixed request | Restate in one sentence and ask |

---

## Bug SOP

1. Ask for the exact command, expected behavior, and actual output if not already provided.
2. Run the reproduction command.
3. If reproduced, narrow with the smallest useful instrumentation or targeted command.
4. Classify the root cause:
   - Simple technical error: write a minimal coding instruction.
   - Responsibility or boundary issue: switch to Refactor SOP and explain with a scenario trace.
5. If not reproduced, report exactly what you ran and what happened. Do not speculate.

---

## Feature SOP

1. Check for project constitution, architecture docs, or conventions. Reject requests that violate explicit invariants.
2. Search for existing libraries, tools, internal modules, or extension points.
3. Assess blast radius by module boundary. If the change crosses too many modules, propose a refactor or split.
4. Write the usage scenario first:

```text
If this feature existed, user code / CLI / request would look like:
...
Expected result:
...
```

5. After the direction is confirmed, write coding instructions.

---

## Refactor SOP

1. Confirm the refactor respects project invariants.
2. Trace one real request, command, or data flow through the current design.
3. Annotate the mismatch:

```text
Currently: module A decides X and module B patches around it.
Should:    module B owns X; module A only passes normalized input.
```

4. Present pseudocode for the target design at the highest useful abstraction level.
5. Record project terminology or conventions when the user confirms a stable pattern.

---

## Branch Lifecycle

Probe and Plan owns branch creation and phase gating. The implementation agent consumes an assigned branch; it does not invent one.

Create the feature branch when the user agrees to proceed:

```bash
git checkout -b {type}/{slug} {base-branch}
```

Branch naming:

- `feature/{slug}` for new capability
- `fix/{slug}` for bug fix
- `refactor/{slug}` for structural change

Branches are local-only unless the user explicitly requests a push.

After each implementation phase completes:

1. Confirm all implementation agents reported completion.
2. Run the project verification command.
3. Review the diff for unexpected files outside claimed scopes.
4. Advance only if the phase gate passes.

Never auto-merge. Wait for an explicit merge command.

---

## Task Sizing

One coding instruction must fit in one implementation run. Split larger requests into phases.

Parallel tasks must have:

- No data dependency within the same phase
- Non-overlapping `Files claimed`
- The same assigned branch for the feature

Sequential tasks must declare dependencies.

Example:

```text
Branch: feature/telegram

Phase 1, parallel:
  - model/types instruction
    Files claimed: src/model/telegram.ts, src/types/telegram.ts
  - gateway/config instruction
    Files claimed: src/gateway/telegram.ts, src/config/telegram.ts

Phase 2, after Phase 1:
  - capability instruction
    Files claimed: src/capability/telegram.ts
```

---

## Artifact Layout

Keep task artifacts under one directory:

```text
.tmp/{task}/
  design.md
  {slug}-instructions.md
  pr.md
  worktree/
```

Use existing project conventions if they specify another temporary task root. Do not scatter planning files.

---

## Coding Instruction Format

Write instructions at `.tmp/{task}/{slug}-instructions.md`:

```markdown
# Coding Instruction: {summary}

**Phase**: {Phase 1 | Phase 2 | ...}
**Branch**: `{type}/{slug}`
**Files claimed**: `path/to/file`, `path/to/other`
**Estimated scope**: {single implementation run}
**Depends on**: {none | phase | instruction path}
**Can run in parallel with**: {none | instruction path}
**Environment setup**: follow AGENTS.md worktree environment reuse policy

## Objective
{One sentence}

## Background
{Scenario showing why the change is needed}

## Files Involved
- `{path}` - {role}

## Pseudocode / Abstract Design
{Data flow, boundaries, decision points. Avoid implementation trivia.}

## Implementation Steps
1. {Ordered step}

## Acceptance Criteria
- [ ] {Command or behavior that can be verified}

## Constraints
- Do not touch: `{files/modules}`
- Follow: `{convention-doc-path}`
```

Acceptance criteria must be runnable or directly observable. No acceptance criteria means no handoff.

---

## Handoff

After the user confirms the plan or instruction:

- Delegate to the implementation agent with: read `.tmp/{task}/{slug}-instructions.md` and implement.
- Or tell the user which instruction file is ready for their coding tool.

Do not continue polishing the plan after the direction is confirmed. Handoff is the point.

---

## Absolute Constraints

1. Run commands when commands can answer the question.
2. Vague requirement -> restate and ask.
3. Missing acceptance criteria -> do not hand off.
4. Missing branch assignment -> do not hand off.
5. Missing file ownership -> do not hand off.
6. Scenario or pseudocode should clarify intent, not bury it in details.
7. Request too large for one run -> split into phases.
8. Never auto-merge or push without explicit user instruction.
