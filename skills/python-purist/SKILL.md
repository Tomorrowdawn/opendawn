---
name: python-purist
description: Human-invoked Python handbook for patterns and anti-patterns.
user-invocable: true
---

# Python Purist

This skill is loaded only when the human explicitly asks for it. It is a Python
handbook, not a mandatory coding workflow.

## Purpose

Use the bundled material to look up Python coding patterns, anti-patterns,
case studies, and cookbook recipes. Do not read the whole skill by default.
Search for the pattern you need, read the matching files, then return to the
actual task.

## Browse

First identify this skill's installed path. In this repository it is
`skills/python-purist`; other installs may use `.agents/skills/python-purist`.

```bash
uv run python <python-purist-skill-dir>/scripts/purist list all
uv run python <python-purist-skill-dir>/scripts/purist tags
uv run python <python-purist-skill-dir>/scripts/purist search <keyword>
uv run python <python-purist-skill-dir>/scripts/purist related <filename.md>
```

Direct `rg` over the skill directory is also fine.

## What To Look For

- `cookbook/` for reusable implementation shapes.
- `best-practice/` for focused engineering guidance.
- `case-study/` for concrete failure patterns and corrected designs.

Common lookups:

```text
initialization -> cookbook/initialization-patterns.md
serde boundary -> best-practice/serde-boundary.md
direct access  -> best-practice/direct-over-indirect.md
fail fast      -> best-practice/fail-fast.md
typing         -> best-practice/type-safety.md
composition    -> best-practice/composition-over-inheritance.md
```

## Working Style

Prefer short, targeted reads:

```text
question -> search -> read one or two matching docs -> apply locally
```

Avoid turning Python work into a ceremony. The handbook exists to supply a
missing pattern or sharpen a judgment, not to replace normal engineering sense.
