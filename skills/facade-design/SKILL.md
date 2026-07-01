---
name: facade-design
description: Human-invoked handbook for facade and interface design.
user-invocable: true
---

# Facade Design

This skill is loaded only when the human explicitly asks for it. Use it after
core and lifecycle design are stable enough to expose clear interfaces. If you
need design prose conventions, read `design-language`.

## Goal

Turn the design into explicit external interfaces that development can implement
directly. This is where design becomes concrete at the boundary: entrypoints,
paths, commands, transport protocols, storage locations, and output contracts.

Facade design is still not an implementation plan. It defines what external
callers can rely on; the developer chooses internal files, helpers, classes, and
sequencing.

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
