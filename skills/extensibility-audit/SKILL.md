---
name: extensibility-audit
description: Human-invoked audit for open-closed design pressure.
user-invocable: true
---

# Extensibility Audit

This skill is loaded only when the human explicitly asks for it. Use it to scan
a core/lifecycle/facade design for open-closed pressure. If you need design
prose conventions, read `design-language`.

## Goal

Find places where adding a new capability, plugin, integration, event, context
requirement, or storage variant would force edits to stable core code. The
output is an audit: what extension pressure exists, where it lands, and whether
the design accepts or removes that pressure.

Assume the code will be maintained after the first implementation. The question
is not whether the current feature can be coded once; it is whether likely
future edits land in the right place. Unstable business boundaries and context
hubs need explicit extension room. Stable core definitions need the opposite
discipline: do not add fields unless the design argues the information is
already necessary and sufficient for the core operation.

## Audit Questions

- What are the likely future additions?
- For each addition, which existing concept would need to change?
- Is the change in a stable core flow or in an extension/registration layer?
- Can a new extension declare its own needs?
- Can required context be collected without widening every core interface?
- Is there a registry, provider, adapter, strategy, or capability boundary?
- Does the facade expose enough protocol surface for future variants?
- Which closed set is intentionally closed, and why?
- Which proposed core fields are actually subcomponent needs that should be
  reached through context, provider, capability, or registry extension instead?

## Context Growth

Context is a common open-closed failure point.

Bad pressure:

```text
CoreContext = User + Session + RuntimePolicy
New extension needs Tenant
  -> modify CoreContext
    -> modify every constructor/call site
      -> core changes for each extension
```

Better pressure:

```text
Extension declares ContextRequirement(Tenant)
Facade/Lifecycle context collectors resolve declared requirements
Core receives only the context required for the selected extension
Missing declared context fails at the boundary
```

This mechanism may be too heavy for small systems. If the human accepts a fixed
context or global context, record the trade-off explicitly.

## Audit Output

Use concise findings:

```text
Extension pressure: new capability needs extra context.
Current design: CoreContext is fixed, so every addition edits core call sites.
Target design: capability declares ContextRequirement; facade collector resolves it.
Accepted alternative: keep fixed context until a second capability appears.
```

## Final Quality Bar

The human should know which future changes the design absorbs through extension
points and which changes intentionally require editing core code.
