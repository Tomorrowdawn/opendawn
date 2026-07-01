---
name: scenario-communication
description: Use to explain behavior, bugs, designs, and trade-offs as scenario traces that align humans and agents.
user-invocable: true
---

# Scenario Communication

Use scenario traces to align the human and the agent on what is happening end to
end. A good scenario helps the human spot wrong assumptions, missing context,
bad ownership, and deeper design problems.

## Core Shape

Write the path from trigger to observable outcome:

```text
Trigger
  -> Boundary receives input
    -> Owner reads or changes state
      -> Core decision uses context
        -> Output / side effect becomes observable
```

Pick the abstraction level that exposes the issue:

- Product requirement: user action -> system state -> user-visible result.
- Architecture: boundary -> owner -> state/context -> result.
- Bug: reproduction trigger -> wrong branch/owner/context -> failure.
- Fix: current path vs target path.

## Current vs Target

For bugs, refactors, and design changes, prefer:

```text
Current path:
Request
  -> Facade accepts payload
    -> Core needs Tenant
      -> Tenant is not exposed by Context
        -> code reaches into GlobalContext

Target path:
Request
  -> Facade authenticates Tenant
    -> ContextCollector attaches Tenant
      -> Core receives declared Context
        -> selected capability runs without hidden global access
```

## Rules

- Start at the real trigger, not the middle of the call stack.
- End at something observable: output, state, error, persisted record, or user
  experience.
- Compress unimportant steps; expand the step where ownership, context, or
  state changes.
- Do not hide uncertainty. Mark it as `unknown` or `needs probe`.
- Do not turn traces into implementation instructions unless the human asks.

## Why It Matters

Scenario traces are not decorative explanation. They are a shared audit surface:
the human can see whether the agent is solving the right problem, and the agent
can see whether the flow is missing context, ownership, lifecycle, or facade
details.
