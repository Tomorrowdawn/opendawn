---
name: yuutest
description: Test-first boundary workflow for coding agents. Use when defining, writing, executing, or reviewing red-green tests, test boundaries, regression tests, or bad tests; especially when YuuCoder receives a coding instruction with a Test Boundary and must prove red before implementation and green after implementation.
---

# YuuTest

## Overview

Use this skill to keep behavior tests honest at the boundary selected by YuuDev. YuuTest is a reusable subworkflow for YuuCoder during the test-first phase; it is not a required third human-facing stage.

---

## Boundary Check

Before writing a test, confirm the instruction's `## Test Boundary` names:

- Public entrypoint/API to test.
- User-visible or externally observable outcome.
- Required red test shape and command.
- Forbidden test styles.
- Claimed files for both test and implementation work.

Block instead of improvising when the boundary is missing, private, unobservable, or cannot be tested without touching files outside `Files claimed`.

---

## Red-Green Workflow

1. Write the smallest test that exercises the declared public entrypoint/API.
2. Assert only the declared observable outcome.
3. Run the exact command from `## Test Boundary`.
4. Record the red failure.
5. Accept red only if it proves missing behavior.
6. Implement the behavior without weakening the test.
7. Run the same command again and record green.
8. Run any broader acceptance commands required by the instruction.

The red failure must not be:

- Syntax error.
- Type error unrelated to the missing behavior.
- Bad fixture or malformed test setup.
- Missing dependency.
- Environment failure.
- Assertion against private implementation detail.
- Failure caused by unrelated existing behavior.

If red is invalid, fix the test setup while staying within `Files claimed`, then rerun. If a valid red test cannot be written within the declared boundary and scope, report a blocker.

---

## Bad-Test Detection

Reject or report tests that:

- Call private functions when a public entrypoint is available.
- Mock or assert interactions against internals owned by this codebase.
- Snapshot incidental formatting not named as user-visible behavior.
- Assert call order, object shape, timing, or logging details that are not part of the external contract.
- Duplicate implementation logic in the assertion.
- Pass before implementation because the fixture does not exercise the missing path.
- Require broad rewrites outside the claimed files.

Existing bad tests may be removed or rewritten only when they are listed in `Files claimed` and the instruction explicitly allows that cleanup.

---

## Reporting

When reporting red-green execution, include:

- Test file changed.
- Command run for red and green.
- Red failure summary and why it proves missing behavior.
- Green result.
- Any bad tests removed or rewritten, with confirmation they were in `Files claimed`.
