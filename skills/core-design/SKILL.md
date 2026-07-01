---
name: core-design
description: Human-invoked handbook for core process design and context access.
user-invocable: true
---

# Core Design

This skill is loaded only when the human explicitly asks for it. Before writing
or revising core design prose, read `design-language` and use its narration
style.

## Goal

Iterate the core process until it is theoretically complete. The result should
explain what the system does, what information it needs, how that information
can reach the process, and what state/output follows. A strong core design is
not just prose: it should make the executable shape visible through concrete
data shapes, parameter interfaces, and pseudocode for the central flow.

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
- What are the concrete parameter objects, method signatures, or message shapes
  that carry that input and context?
- What state changes?
- What decisions are made?
- What is the main algorithm or loop, written as pseudocode?
- What output is produced?
- What invariant must always hold?

## Concrete Shape

Core design prose should name concepts first, then pin down the useful shapes
that make those concepts implementable. Prefer lightweight examples over full
production code, but include enough structure that a developer can tell what
arguments exist, who owns them, and what is returned.

Good shapes include:

- Data records and message formats.
- Constructor or factory inputs.
- Public method signatures.
- Return values and event payloads.
- State machines, stream protocols, and stop reasons.
- Pseudocode for the central process.

Example:

```py
class CoreProcess:
  async def run(
    self,
    input: InputMessage,
    *,
    context: CoreContext,
    stop_event: Event,
  ) -> CoreResult:
    pass
```

```text
CoreContext = {
  user: User,
  session: Session,
  policy: RuntimePolicy,
  capabilities: CapabilityRegistry,
}
```

```py
async def run(input):
  history.append(input)

  while not stop_event.is_set():
    decision = decide(history, context)

    if decision.kind == "complete":
      return decision.result

    effects = await execute(decision.effects)
    history.append(effects)
```

These snippets are design instruments, not an implementation commitment. They
should expose the contract pressure: which values must exist, where they come
from, what can fail, and which layer owns the next step.

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

## Maintenance Assumption

Design for maintained code, not one-shot code. The system will be edited after
the first implementation: fields may be added or removed, business boundaries
may shift, and context hubs often grow. Unstable edges should have explicit
extension room, but the core domain should resist growth.

For the core itself, prefer a mathematical argument that the current information
is sufficient to run the process. Do not add core fields merely because a future
subcomponent might need them. Usually the extension should live in a child
component, provider, capability, registry, or context access path:

```text
New feature needs Tenant.
Good pressure: Capability reads context.tenant or declares TenantRequirement.
Bad pressure: CoreProcess grows tenant just in case every future feature needs it.
```

If a proposed core field cannot be tied to a core invariant, state transition,
or decision, it probably belongs outside the core.

## Interface Pressure

When a concept participates in the core process, give it the smallest useful
interface. Do not leave important behavior hidden behind vague verbs such as
"handle", "manage", "process", or "integrate" when the design already knows the
parameters.

Prefer:

```py
class Capability:
  async def execute(
    self,
    payload: Payload,
    *,
    context: CoreContext,
    timeout: float,
  ) -> CapabilityResult:
    pass
```

Over:

```text
Capability handles requests using the context.
```

The interface does not need to be final API syntax. It does need to answer:

- Who calls this?
- Which inputs are trusted, validated, or already deserialized?
- Which context arrives explicitly?
- Which resource or lifecycle owner is assumed to exist?
- What result, event, or state transition comes back?
- Which errors are part of the core model?

If the design cannot write the signature yet, that is usually a signal that the
concept boundary is still unstable.

## Pseudocode Bar

For the central flow, include pseudocode that shows ordering and ownership. The
reader should be able to answer what happens first, what repeats, what is
persisted, what emits events, where cancellation is observed, and which reasons
terminate or block the process.

Useful pseudocode is allowed to be incomplete in incidental details, but it must
be precise about core sequencing:

```py
async def run_loop(input):
  append_and_persist(input)

  resource = Resource.from_config(config, runtime)
  try:
    while True:
      output, reason = await step(input_state, resource)
      append_and_persist(output)

      if reason == "done":
        return output
      if reason == "needs_effect":
        effects = await gather_effects(output.effects)
        append_and_persist(effects)
        continue
      raise Blocked(reason)
  finally:
    await resource.close()
```

Avoid pseudocode that only restates prose:

```text
Process the input.
Call the dependencies.
Return the result.
```

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
current intended model without knowing the failed historical attempts. They
should also be able to sketch the first implementation without inventing hidden
parameters, surprise globals, or unmentioned state transitions.

The text should be a positive description of the design, not a changelog. It
does not need to compile, but the contracts and core pseudocode should be
specific enough that compilation would mostly be a matter of choosing local
names, modules, and exact types.
