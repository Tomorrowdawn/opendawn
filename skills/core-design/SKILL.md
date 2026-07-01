---
name: core-design
description: Human-invoked handbook for core process design.
user-invocable: true
---

# Core Design

This skill is loaded only when the human explicitly asks for it. Before writing
or revising core design prose, read `design-language` and use its narration
style.

## Goal

Iterate the core process until it is theoretically complete. The result should
explain what the system does, what information it needs, how that information
can reach the process, and what state/output follows.

Assume external components already exist and can be injected. Do not design
initialization, storage paths, protocols, caches, or shutdown here; those belong
to `lifecycle-design` and `facade-design`.

## Core Questions

- What concrete scenario is this core process meant to satisfy?
- What are the named concepts?
- What input starts the process?
- What context is required to make the decision?
- Is every required context theoretically available?
- How does context reach the core: argument, injected dependency, session,
  runtime provider, storage lookup, or global context?
- What state changes?
- What decisions are made?
- What output is produced?
- What invariant must always hold?

## Context Access

Most implementation failures are context failures: a lower layer needs
information that no interface exposes, so code starts reaching through globals,
singletons, hidden stores, or defensive fallbacks.

Core design must make this explicit:

```text
Core needs: User, Session, CapabilityRegistry, RuntimePolicy
Source:
  User <- Facade-authenticated request
  Session <- Runtime session store
  CapabilityRegistry <- injected dependency
  RuntimePolicy <- injected dependency
Access path:
  Facade builds CoreInput
  Runtime resolves Session
  Runtime calls Core with CoreInput + CoreContext
Missing context:
  none
Accepted debt:
  GlobalContext supplies RuntimePolicy to avoid widening every call site.
  Cost: weaker explicitness; future policy consumers may hide requirements.
```

A black-hole global context can be a valid human-approved trade-off, but it must
be named as debt. Do not let it appear accidentally.

## Iteration Loop

The expected human workflow is conversational:

```text
draft core design
  -> review context access and process completeness
    -> revise concepts / access paths
      -> repeat until the core flow is stable
```

Only after core behavior stabilizes should the design move to lifecycle,
facade, or development.

## Final Quality Bar

A new developer should be able to read the final core design and understand the
current intended model without knowing the failed historical attempts. The text
should be a positive description of the design, not a changelog.
