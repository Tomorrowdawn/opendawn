---
name: python-purist
description: Opinionated Python coding standards — type safety, explicit over implicit, composition over inheritance, coroutines over threads. Triggers on Python code authoring, refactoring, code review. Use scripts/purist to browse best practices and case studies.
user-invocable: true
---

# Python Purist

> "Code is written for humans to read, and only incidentally for machines to execute."
> Python's flexibility is a gift and a trap — this skill helps you write rigorous, maintainable Python that stands the test of time.

## Browsing the Skill

This skill contains 10 **best-practice** docs and 26 **case-study** docs. Do NOT hardcode file lists — use the auxiliary CLI instead:

```bash
# List all docs with titles, tags, and summaries
scripts/purist list [best-practice|case-study|all]

# Show docs related to a specific one
scripts/purist related composition-over-inheritance.md

# Print the quality checklist
scripts/purist checklist

# Scan a codebase for anti-patterns
scripts/purist check src/
```

To search across all docs for a specific topic, use your native search tools (grep, rg) directly on the `skills/python-purist/` directory. There are only 36 files — no need for an index.

## Code Has Five Facets

Every module and function crosses five concerns. Before writing code — and before reviewing code — an Agent must examine all five:

> **Core logic becomes pure and testable only when the other four facets are pushed out to the boundaries.**

| Facet | Question to Ask | Case Studies |
|-------|-----------------|-------------|
| **Configuration** | How does this code receive its settings? Where do defaults live? Can I swap the config source without touching logic? | `factory-pattern.md` |
| **Runtime Resources** | What external resources does this code hold? How are they acquired, pooled, recycled, and released? Is there a single owner of the lifecycle? | `runtime-resources.md`, `dependency-injection.md` |
| **Persistence** | How does data enter and leave? Where is the serialization boundary? Can I swap the storage backend without touching business logic? | `repository-pattern.md`, `serde-schema.md` |
| **Core Logic** | What does this code actually _do_? Is it pure? Is it testable without mocking infrastructure? | `decorator-pattern.md`, `observer-pattern.md`, `strategy-pattern.md`, `builder-pattern.md`, `facade-pattern.md` |
| **Observability** | How do I know what happened? Are metrics, traces, logs, and alerts routed through dedicated channels? Can a telemetry failure break the application? | `structlog-pattern.md`, `event-bus-observability.md`, `loguru-antipattern.md`, `print-is-not-logging.md` |

**The litmus test**: if you remove configuration parsing, resource lifecycle management, persistence I/O, and observability instrumentation from a function, does the remaining code express a pure business intent? If not, one of the four outer facets is still entangled with the core.

Each facet has its own design patterns, its own failure domain, and its own per-environment assembly. They must not share the same call stack or the same error handling.

## Core Principles

These principles apply across all five facets:

| Principle | Best-Practice Doc |
|-----------|-------------------|
| Fail fast — validate at boundaries, crash at entry | `fail-fast.md` |
| Explicit over implicit — no magic, no hidden side effects | `explicit-over-implicit.md` |
| Red → Green → Refactor — TDD iron law | `red-green-tdd.md` |
| Types are documentation that compiles — ban `Any`, `type: ignore` | `type-safety.md` |
| Coroutines over threads — native async | `coroutine-vs-thread.md` |
| Process isolation — strong boundary defense | `process-isolation.md` |
| Serialization boundary is an explicit contract | `serde-boundary.md` |
| Three inheritance types don't mix — code sharing → composition, interface → Protocol, data → specialization | `composition-over-inheritance.md` |
| Naming is design — readability is priority one | `naming-and-readability.md` |
| Structured logging — events are dicts, not strings. Never print(). Log to stderr, use structlog. | `structured-logging.md` |

Each best-practice doc has related case studies showing the anti-pattern and its correction. Use `scripts/purist related <filename>` to discover them.

## Workflow

When working with Python code, follow this loop:

```
1. Define the problem → 2. Read the relevant best-practice → 3. Study related case studies
→ 4. Design types & interfaces first → 5. Write a failing test (red) → 6. Pass it minimally (green)
→ 7. Review against case studies → 8. Regression test (green)
```

1. **Define the problem and identify the facets** — clarify what you're solving and which of the five facets it touches. Is this a configuration concern? Runtime resource lifecycle? Persistence boundary? Core business logic? Observability instrumentation? Most real-world changes span 2-3 facets — identify them before writing a single line.

2. **Read the best-practice** — find the relevant principle doc from the table above. Read it before writing code.

3. **Study case studies** — use `scripts/purist related <doc>` to find related cases. See what the anti-pattern looks like and how it's corrected.

4. **Design types and interfaces first** — define Protocols, TypedDicts, and dataclasses before implementations. Let types exist before logic. Push the four outer facets to the boundaries: config schemas, resource managers, repository protocols, telemetry subscribers.

5. **Red test** — write a test that fails. If you can't write the test, the interface is wrong.

6. **Green** — write the minimum code to pass. No over-engineering. No premature abstraction.

7. **Review against case studies** — does your implementation have hidden initialization? Swallowed exceptions? Type black holes? Are the five facets cleanly separated, or is observability code entangled with core logic?

8. **Green regression** — run all tests. Ensure nothing is broken.

## When to Trigger

Load this skill when:

- **Writing** new Python modules, packages, or API endpoints
- **Refactoring** existing Python code (function decomposition, class restructuring, dependency untangling, inheritance simplification)
- **Reviewing** Python PRs (type safety, exception handling, testability, inheritance compliance)
- **Designing** Python interfaces or data models (Protocol vs ABC choice, dataclass / msgspec Struct, specialization vs composition)
- **Debugging** hard-to-reproduce Python bugs (check implicit behavior and exception swallowing first)
- **Migrating** Python versions or third-party dependencies

## Quality Checklist

Run `scripts/purist checklist` to see the full checklist. Key items:

- [ ] All function parameters and return values are fully type-annotated?
- [ ] Zero usage of `Any`, `type: ignore`, `# noqa`?
- [ ] Serialization/deserialization has explicit schema, not bare `dict`?
- [ ] Three inheritance types kept separate? Code sharing → composition. Interfaces → Protocol. Specialization → LSP-compliant, ≤2 levels.
- [ ] Template Method pattern replaced with decorator/wrapper?
- [ ] Every public function has at least one test?
- [ ] Zero `except: pass` or silent exception swallowing?
- [ ] Untrusted input validated immediately at boundaries (fail fast)?
- [ ] External resources (subprocesses, DB, files) managed by a single owner with explicit acquire/pool/recycle/release lifecycle?
- [ ] Resource lifecycle is auditable by reading one class, not scattered across module-level globals?
- [ ] All log events are structured (dict-based, not string interpolation)?
- [ ] Zero usage of `print()` for logging, `loguru`, or bare stdlib `logging`?
- [ ] Log output goes to stderr only — application never opens log files?
- [ ] Every log event carries context (request_id, user_id) via automatic propagation?
- [ ] Metrics, traces, and alerts routed through a dedicated telemetry channel — NOT embedded in core logic and NOT routed through the logging pipeline?
- [ ] Telemetry subscribers have independent fault isolation — a crashed subscriber never breaks the application or silences other subscribers?
- [ ] Immutable objects used as dict keys — hash contract never violated?

---

**Pre-audit your code**: run `scripts/purist check <your_source_dir>` before submitting a PR.
