---
name: senior-dev
description: Human-invoked handbook for senior development judgment.
user-invocable: true
---

# Senior Dev

This skill is loaded only when the human explicitly asks for it. It is a compact
engineering-judgment checklist for implementation after design is stable.

## Posture

Write simple, direct code that makes the design true. The developer reads core,
lifecycle, and facade designs for contracts, then chooses implementation
details using local project conventions.

## Practices

- Prefer boring code over clever abstractions.
- Fail fast at trust boundaries; trust validated data inside the boundary.
- Use precise types, but avoid type gymnastics.
- Prefer direct access over defensive probing when the contract guarantees data.
- Avoid `get()` / `hasattr()` / broad catch blocks that hide broken contracts.
- Add an abstraction only when it removes real duplication or isolates a real
  extension point already identified by design.
- Use an existing dependency when it clearly removes substantial code and fits
  the project; do not add dependencies for trivial helpers.
- Keep I/O and external resources at boundaries where practical.
- Preserve observability for real failures; do not add noisy logs for normal
  control flow.
- Delete dead paths instead of preserving historical scaffolding.

## Trade-Offs

Make trade-offs explicit when they matter:

```text
Chose direct synchronous file write because writes happen at shutdown only.
Upgrade path: async batched writer if shutdown latency becomes observable.
```

Do not over-document obvious code. A short note is useful only when it records a
real design or operational trade-off.

## Final Quality Bar

The implementation should look like it was written by someone who understood
the contracts, trusted them, and kept the code maintainable for the next change.
