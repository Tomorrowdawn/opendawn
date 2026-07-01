---
name: lifecycle-design
description: Human-invoked handbook for lifecycle design.
user-invocable: true
---

# Lifecycle Design

This skill is loaded only when the human explicitly asks for it. Use it after
the core process is stable. If you need design prose conventions, read
`design-language`.

## Goal

Describe how the core components live over time while staying at design level.
Natural language is preferred. Include serialization rules only as far as they
affect lifecycle and interoperability; do not write detailed implementation
schemas unless the human asks.

## Lifecycle Surface

Cover the phases that matter:

- Configuration deserialization into design concepts.
- Component construction and dependency injection.
- Runtime initialization order.
- State creation, mutation, persistence, reload, and discard.
- Cache population, invalidation, and refresh ownership.
- Resource ownership and cleanup.
- Error/retry behavior when lifecycle operations fail.
- Upgrade or migration behavior when stored state changes shape.

## Boundaries

Lifecycle design may say:

```text
RuntimeState is serialized under the workspace data directory.
Session snapshots are append-only and reloaded at startup before actors resume.
Cache entries are disposable; missing cache never blocks reconstruction.
```

Lifecycle design should not say:

```text
Write src/runtime/state_store.ts with function loadState().
Use /var/app/foo/v3/state.json exactly unless facade requires that path.
```

Precise external paths, commands, APIs, and transport protocols belong to
`facade-design`.

## Stability Rule

Do not design lifecycle before the core behavior is stable. Core changes often
rewrite initialization, state, cache, and cleanup. Premature lifecycle detail is
high-churn design debt.

## Final Quality Bar

A new developer should understand what must exist before the core runs, what
changes while it runs, what survives after it stops, and who owns cleanup.
