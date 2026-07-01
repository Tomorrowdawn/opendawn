---
name: design-language
description: Human-invoked notes for design narration language.
user-invocable: true
---

# Design Language

This skill is loaded only when the human explicitly asks for it, or when another
human-invoked skill references it. It defines narration language, not a document
template.

## Purpose

Good design prose should move from concrete experience to named concepts, then
use those concepts to describe the system positively. Avoid writing historical
digressions, failed attempts, or implementation trivia into the final design
artifact. If a historical lesson matters, record it separately as a lesson; do
not pollute the development-facing design.

## Narrative Pattern

1. Start with one concrete scenario or pressure.
2. Name the concepts that make that scenario easier to discuss.
3. Define each concept in the shortest useful form.
4. Describe flows, boundaries, state, and invariants using those names.
5. End with the intended model, not a diary of how the model was discovered.

## Concept Language

Concept definitions are explanatory, not type declarations. Use whatever form
makes later prose shorter:

```text
Session = conversation state owned by Runtime
Context = information available to Core when deciding the next action
Boundary = place where untrusted input becomes a trusted design concept
Owner = component responsible for lifecycle and invariants of Concept
State transition: Draft -> Published when Validation succeeds
```

Useful concept kinds:

- Actor, input, output, state, context, boundary, owner, invariant.
- Collection, registry, provider, capability, event, command, resource.
- Lifecycle phase, access path, failure mode, extension point.

## Positive Description

Final design artifacts should describe the target model directly:

```text
Request enters Facade.
Facade validates Payload and builds Context.
Core selects Capability using Context.
Capability returns Result.
Facade serializes Result for the caller.
```

Avoid final-artifact prose shaped like:

```text
Previously we tried X, but it failed because Y, so now we patch Z.
```

That history may be useful as a lesson, but a new developer should not need to
understand old mistakes before understanding the current design.

## Maintenance Assumption

Design prose should assume the code will be maintained, edited, and extended
after the first implementation. It is not a one-way path from one problem to one
code patch that nobody revisits.

For unstable areas, especially business boundaries and context hubs, name the
extension room: how fields, variants, providers, capabilities, or records can be
added, removed, defaulted, rejected, or migrated. For stable core concepts, use
the opposite discipline: argue that the current information is sufficient for
the core operation, and avoid adding speculative fields. Future variation should
usually extend a child component or context access path, not widen the core
domain itself.

## Guardrails

- Do not force a fixed file format.
- Do not prescribe implementation steps.
- Do not name private helpers unless the interface itself is the design.
- Do not turn examples into requirements accidentally.
- Do not keep open questions in a document presented as final.
