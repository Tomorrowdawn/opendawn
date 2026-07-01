---
name: probe-and-plan
description: Human-invoked deep-dive for root-cause investigation.
user-invocable: true
---

# Probe and Plan

This skill is loaded only when the human explicitly asks for a deep probe,
step-back analysis, or root-cause investigation.

## Purpose

Use this when local fixes keep moving the symptom, the architecture may be
wrong, or the human wants to pause implementation and understand the real
problem.

## Method

1. Probe before theorizing. Run commands when commands can settle facts.
2. Trace the current scenario end to end.
3. Step back and name the mismatch.
4. Describe the ought-to-be model at the highest useful abstraction.
5. Separate model problems from implementation problems.
6. Ask for human confirmation before writing durable artifacts.

## Scenario Trace

Use traces to make the problem auditable:

```text
Current path:
User action
  -> Boundary accepts input
    -> Wrong owner patches missing context
      -> Core makes decision with partial state
        -> Observable failure

Target path:
User action
  -> Boundary builds complete context
    -> Correct owner validates state
      -> Core makes decision
        -> Observable result
```

## Output

The output may be a short explanation, a design sketch, or a recommendation to
continue with `core-design`, `lifecycle-design`, `facade-design`, or
`extensibility-audit`. Do not auto-enter those skills unless the human asks or
the active human-invoked skill references them.
