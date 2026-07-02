---
name: facade-design
description: Human-invoked handbook for facade and interface design.
user-invocable: true
---

# Facade Design

This skill is loaded only when the human explicitly asks for it. Use it after core and lifecycle design are stable enough to expose clear interfaces. If you need design prose conventions, read `design-language`.

## Goal

Turn the design into explicit external interfaces that development can implement
directly. This is where design becomes concrete at the boundary: entrypoints,
paths, commands, transport protocols, storage locations, and output contracts.

Facade design is still not an implementation plan. It defines what external
callers can rely on; the developer chooses internal files, helpers, classes, and
sequencing.

**Be specific, be assertive**. Do not hedge. Do not say "we might" or "we could". If this is intentionally an extension point, say so. You must make a decision, obtaining something and sacrificing something else.


## Facade Surface

Name each entrypoint and protocol precisely:

- API function: name, parameters, return value, raised errors.
- HTTP: method, path, request body, response body, status codes.
- WebSocket: channel, message shape, event order, close/error behavior.
- CLI: command, flags, stdin/stdout/stderr contract, exit codes.
- WebHook: endpoint, authentication signal, payload, retry semantics.
- File interface: system-relative location, format, read/write ownership.
- Background job: trigger, input source, output/side effect.

## Interface Contract

For each facade, answer:

```text
Entrypoint:
Input protocol:
Context collection:
Core call:
Output protocol:
Error protocol:
Persistence or file location:
Compatibility:
```

`Context collection` is important: if core design says a process needs
context, facade design must say which boundary gathers or exposes it.

## Maintenance Assumption

Design for maintained code, not one-shot code. Facades sit at unstable business
boundaries, so their contracts should say where compatible extension happens:
new request fields, new response fields, new event kinds, versioned messages,
optional capabilities, and rejected incompatible changes.

Leave extension room at the boundary without polluting the core. A new external
field should map to a facade adapter, context collector, provider, capability,
or subcomponent when possible. It should not force a new core field unless the
core design can prove the information is part of the core decision or invariant.

## Development Handoff

After facade design, the developer should be able to read:

```text
core design
lifecycle design
facade design
```

and implement without a separate instruction artifact. The design defines
contracts; development owns implementation detail.

## Final Quality Bar

A new developer who has never seen the project should know exactly how outside
systems call this feature, what data crosses the boundary, what comes back, and
where persistent boundary-visible files live.
