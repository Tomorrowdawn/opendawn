---
name: design-language
description: "Use when writing or reviewing an implementation-independent design artifact: introduce concepts from a concrete problem, define a compact concept language, derive ideal folder structure and impact maps, and describe runtime pseudocode without turning the design into implementation instructions."
user-invocable: true
---

# Design Language

Use this skill to write a `design.md` that is clear enough for human review and stable enough to hand off, without pretending to be implementation code. This skill is an experimental peer to `probe-and-plan`; do not modify another workflow just because this skill is loaded.

## Purpose

A good design introduces the language needed to make the problem simple. Follow the order used by good textbooks:

1. Start with a concrete problem example.
2. Extract the concepts that simplify the problem.
3. Define those concepts with a compact language.
4. Describe the runtime algorithm using those concepts.

The result should shield the reader from incidental complexity. If the design is finished, the designer should see no unresolved model problem left inside it.

## Concept Language

Concepts are not just data types. A concept can be an entity, collection, role, property, boundary, owner, invariant, lifecycle, or behavior-defining idea.

Use compact definitions:

```text
User = (name, id, profile = {avatar, phone_number, ...})
Group = list[User]
Pivot = element where partition(Array, Pivot) => {left < Pivot, right > Pivot}
Session = (actor = User | LLM, input, state, output)
Boundary = (input, output, invariant = {...})
Owner = (owns = {ConceptA, ConceptB}, must_not = {ConcernX})
```

Prefer the shortest definition that makes later explanation cheaper. If a concept is best defined by a property, role, invariant, or scenario, define it that way instead of forcing it into fields. Once a concept is defined, use the name directly: "select Pivot", "partition around Pivot", "Group receives Session", "Owner rejects ConcernX".

## Artifact Format

Write the design in this order:

```markdown
# Design: {summary}

## 1. Problem Example
{A concrete scenario that exposes the design problem}

## 2. Concept Introduction
{The small set of concepts that makes the problem easier to discuss}

## 3. Concept Language
{Compact definitions using tuple/property/role notation}

## 4. Ought-To-Be Model
{Ideal ownership, lifecycle, data direction, and invariants, using defined concepts}

## 5. Ideal Folder State
{Directory tree derived from concept cohesion and layering}

## 6. Impact Map
Upstream:
Downstream:
Modify:
Create:
Delete:
Unknown / needs probe:

## 7. Runtime Algorithm
{Implementation-independent pseudocode using defined concepts}

## 8. Behavior / Red-Light Intent
Public boundary:
Observable outcome:
Expected red failure:
Forbidden test style:
```

## Section Rules

### Problem Example

Use one real scenario, trace, command result, or user request. Do not start with abstract architecture vocabulary before the reader has seen the problem it explains.

### Concept Introduction

Name only the concepts needed to compress the design. A concept earns its place when later sections become shorter and clearer because the name exists.

### Concept Language

Definitions should be implementation-independent. Do not imply a class, database schema, private function, framework route, or file format unless the model itself requires that shape.

Allowed forms:

- `Name = (field, field = value, property = {...})`
- `Name = list[OtherConcept]`
- `Name = Role where property`
- `Name = state transition: A -> B when Condition`
- `Name = owner of {A, B}; not owner of {C}`

### Ought-To-Be Model

Describe who owns what, where data flows, what lifecycle is authoritative, and what must never happen. Use the concept names instead of re-explaining their fields.

### Ideal Folder State

The folder tree is part of the design because it is the projection of the concept model. Organize by concept cohesion and layer boundaries, not by the current accidental layout.

Annotate each folder or important file with the concept it owns. This is a target information architecture, not a step-by-step edit script.

### Impact Map

Derive the impact map from the ideal folder state and current repo reality.

- `Upstream`: callers, producers, configs, or schemas that feed the designed path.
- `Downstream`: consumers, renderers, integrations, or persisted outputs affected by it.
- `Modify`: existing files whose concepts remain but need to change.
- `Create`: new files required by the concept model.
- `Delete`: files or concepts that should disappear in the target model.
- `Unknown / needs probe`: facts that require more inspection before an implementation instruction can be written.

`Unknown / needs probe` is allowed during drafting. It is not allowed in the final design.

### Runtime Algorithm

Write pseudocode like an algorithms textbook: inputs, state, branches, loops, and outputs. It should explain what the system does when an endpoint actor, such as a user or LLM, provides input.

Good pseudocode names concepts and decisions:

```text
on Input from Actor:
  Boundary validates Input
  Session records Actor, Input, State
  Owner selects TargetConcept
  TargetConcept produces Output
  Boundary returns ObservableResult
```

Do not write implementation procedure:

- No private helper names.
- No ordered refactor steps.
- No exact package imports.
- No framework-specific wiring unless the framework is part of the model boundary.

### Behavior / Red-Light Intent

State the behavior that would prove the design is missing today. Keep it at test-intent level:

- Public boundary to exercise.
- User-visible or externally observable outcome.
- The red failure that should happen before implementation.
- Test styles that would be invalid because they test internals or incidental shape.

Exact test files, commands, and change scopes belong in a later coding instruction, not in this design.

## Completion Rule

Final designs do not contain `Open Questions`. If there is an unresolved model, scope, naming, ownership, behavior, folder-structure, or probe question, resolve it before publishing the design. If it cannot be resolved without user input or more evidence, do not present the artifact as final.

## Anti-Patterns

- Defining concepts that are never used again.
- Treating tuple notation as a type system instead of an explanation tool.
- Writing target code, private function names, or step-by-step implementation order.
- Hiding design uncertainty in an `Open Questions` section.
- Describing a folder tree that does not follow from the concept model.
- Writing red tests that assert internals instead of observable behavior.
