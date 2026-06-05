---
name: reviewer-loop
description: Review completed work against defined goals and either approve completion or trigger a rework cycle with specific feedback. Agent-agnostic review pattern.
compatibility: opencode
license: MIT
metadata:
  audience: reviewers
  workflow: quality-gate
---

## What I Do

- Examine workspace changes (diffs, modified files) against a goal specification
- Evaluate completeness: are all requirements met?
- Evaluate quality: tests, error handling, edge cases, code standards
- Return a clear verdict: APPROVED or REJECTED with specific feedback
- On REJECTED: provide actionable, specific rework instructions

## When to Use Me

Use this skill when you need an independent quality gate before accepting work as done. Works as a standalone review checkpoint in any development workflow.

## Review Process

1. Read the goal specification and acceptance criteria
2. Inspect all workspace changes (`git diff`, `git log`)
3. Read modified files and any new files
4. Run tests if a test command is available
5. Check for:
   - Requirement completeness
   - Test coverage for new/changed code
   - Error handling and edge cases
   - Code style and project conventions

## Response Format

```
APPROVED
[optional: brief summary of what was verified]

or

REJECTED: <specific reason>
- Missing: <requirement not met>
- Issue: <quality problem>
- Suggestion: <concrete fix>
```

## Integration

Use as a standalone quality gate. Invoke the reviewer after development work signals completion, and use its verdict to determine whether to accept the work or request rework.
