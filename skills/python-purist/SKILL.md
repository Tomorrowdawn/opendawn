---
name: python-purist
description: Opinionated Python coding standards — type safety, explicit over implicit, composition over inheritance, coroutines over threads. Triggers on Python code authoring, refactoring, code review. Use `uv run python scripts/purist` to browse best practices, case studies, and cookbook recipes. Read this **every time** you write or review Python code.
user-invocable: true
---

# Python Purist

> "Code is written for humans to read, and only incidentally for machines to execute."
> Python's flexibility is a gift and a trap — this skill helps you write rigorous, maintainable Python that stands the test of time.

## Prerequisites

> **Important**: Always invoke `scripts/purist` via `uv run python scripts/purist <args>` (or your project's Python interpreter). Do **not** run it directly as `scripts/purist` or `python scripts/purist` — this would use the global Python and may cause version/compatibility issues.

`uv run python scripts/purist check` uses **ruff** for function complexity analysis (McCabe + too-many-statements). On first run, it auto-installs ruff via `uv` if available. Recommended setup:

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# In your project, ruff will be auto-installed on first purist check
# Or install it explicitly:
uv add --dev ruff
```

Without uv, purist falls back to `python -m ruff` or bare `ruff` if already installed. Line-count checks run without any dependency.

## Workflow (MANDATORY — DO NOT SKIP STEPS)

Every step exists because agents that skip it produce code that fails review. Follow this sequence **every time** you write or modify Python code:

```
1. Identify facets → 2. Read cookbook (if applicable) OR best-practice → 3. STUDY CASE STUDIES → 4. Design types first → 5. Red test → 6. Green → 7. Review against cases → 8. Green regression
```

**Fast path**: if you're building a new CRUD app, REST API, or common application pattern, go to Step 2a (Cookbook) first — you'll get a complete annotated template. For everything else, Step 2b (Best-Practice) has the principles.

### Step 1: Identify Which Facets Are Involved

Before writing a single line, ask which of the five facets your change touches:

| Facet | Question |
|-------|----------|
| **Configuration** | How does this code receive settings? Can I swap config source without touching logic? |
| **Runtime Resources** | What external resources? Single owner of lifecycle? |
| **Persistence** | How does data enter/leave? Where is the serialization boundary? |
| **Core Logic** | What does this code actually _do_? Is it pure and testable? |
| **Observability** | How do I know what happened? Are metrics/logs/traces/alerts separated? |

Most changes span 2-3 facets. Identify them first, or you will entangle them.

### Step 2a: Check the Cookbook First (Application Patterns)

If you're building a **complete application pattern** or tackling a **structural refactoring** (CRUD app, REST API, large file decomposition, config patterns), the cookbook has annotated recipes you can copy and adapt. Each recipe is a working pattern — find the `🔌` markers, swap in your domain, done.

| If you're... | Read |
|--------------|------|
| **Writing ANY class** (constructor, DI, from_config) | `cookbook/initialization-patterns.md` ← **MANDATORY** |
| Building a CRUD REST API with FastAPI | `cookbook/crud-fastapi.md` |
| Decomposing a large file (>400 lines) | `cookbook/large-file-decomposition.md` |
| Persisting typed models to ORM without round-trip | `cookbook/orm-typed-persistence.md` |

More recipes coming. **Cookbook recipes eliminate 80% of structural decisions** — use them when the shape of your task matches.

> ⚠️ **`cookbook/initialization-patterns.md` is mandatory reading for ANY class you write.** Every class needs a constructor — choose the wrong pattern and you'll redo the work. Decision tree + 4 patterns + anti-pattern reference.

### Step 2b: Read the Relevant Best-Practice Doc

For everything not covered by a cookbook recipe, use this table to find the right doc. **Read it fully** before writing code:

| If your code involves... | Read |
|--------------------------|------|
| External input, JSON, YAML, API responses, config files | `serde-boundary.md` + `type-safety.md` |
| Data structures, type annotations, class design | `type-safety.md` + `composition-over-inheritance.md` + `struct-vs-define.md` |
| Async operations, I/O, concurrency | `coroutine-vs-thread.md` |
| Class hierarchies, inheritance | `composition-over-inheritance.md` |
| Choosing `@define` vs `msgspec.Struct` | `struct-vs-define.md` (also see `cookbook/initialization-patterns.md`) |
| Creating classes, constructors, `__init__`, DI, from_config | `cookbook/initialization-patterns.md` |
| Logging, debugging output | `structured-logging.md` |
| Resource lifecycle (DB, files, subprocess) | `process-isolation.md` |
| Error handling, input validation | `fail-fast.md` |
| Function/method signatures, side effects | `explicit-over-implicit.md` |
| New function/class naming | `naming-and-readability.md` |
| Guard clauses, defensive patterns, hasattr, dict.get, input patching | `direct-over-indirect.md` |
| Type system trust issues (to_builtins, cast abuse, phantom protocols, dynamic type creation) | `trust-your-types.md` |
| Writing or verifying regression tests | `verify-regression-tests.md` |

### Step 3: Search and Study Case Studies

**Every case study exists because someone already made that mistake and had to fix it.** Skip this step = repeat known mistakes.

Find relevant cases efficiently:
```bash
# First: see what tags exist — pick the right keyword for your problem
uv run python scripts/purist tags                  # list all 150+ tags with file counts
uv run python scripts/purist tags init             # filter tags by substring (e.g., initialization)

# Primary workflow: find all cases related to a best-practice doc
uv run python scripts/purist related direct-over-indirect.md

# Search by keyword across titles, tags, and summaries
uv run python scripts/purist search hasattr
uv run python scripts/purist search initialization

# Browse all case studies with titles and tags
uv run python scripts/purist list case-study
```

> 💡 **Tip**: Always run `uv run python scripts/purist tags` first to discover what tags are available before searching. The tag system was designed for agent search — find the right tag and you'll find the right doc.

For each matching case study:
1. Read the anti-pattern (the "wrong" code). Understand what makes it bad.
2. Read the corrected code. Understand WHY the fix works.
3. **Check**: does your planned code resemble the anti-pattern? If yes, redesign now.

The 31 case studies are this skill's most valuable asset — they encode failure patterns that took real debugging hours to discover. Use them.

### Step 4: Design Types and Interfaces First

Define Protocols, TypedDicts, msgspec.Struct, and dataclasses **before** writing implementations. Types exist before logic.

### Step 5: Write a Failing Test (Red)

If you can't write the test, your interface is wrong. Go back to Step 4.

### Step 6: Minimum Code to Pass (Green)

No over-engineering. No "I might need this later."

### Step 7: Review Against Case Studies

Re-read the case studies from Step 3. Run the quality checklist and verify your code against every item:

```bash
uv run python scripts/purist checklist
```

If any checklist item fails, find the relevant case study to understand the correct pattern:
```bash
uv run python scripts/purist search "<keyword from the failing item>"
```

Also run the automated scan to catch anti-patterns:
```bash
uv run python scripts/purist check src/
```

### Step 8: Regression Test (Green) + Self-Verify

Run all tests. Full pass? Now self-verify: **break one line on the critical path, re-run the test — it MUST fail.** If it still passes, the test didn't touch real code; rewrite it. See `best-practice/verify-regression-tests.md`.

---

## When to Trigger

Load this skill when:
- **Writing** new Python modules, packages, or API endpoints
- **Refactoring** existing Python code
- **Reviewing** Python PRs
- **Designing** Python interfaces or data models
- **Debugging** hard-to-reproduce Python bugs (check implicit behavior first)
- **Migrating** Python versions or dependencies

## Five Facets

> **Core logic becomes pure and testable only when the other four facets are pushed out to the boundaries.**

| Facet | Question to Ask | Key Case Studies |
|-------|-----------------|-------------|
| **Configuration** | How does this code receive settings? Where do defaults live? | `cookbook/initialization-patterns.md` |
| **Runtime Resources** | What external resources? Single owner of lifecycle? | `runtime-resources.md`, `dependency-injection.md` |
| **Persistence** | Where is the serialization boundary? Can I swap storage? | `cookbook/crud-fastapi.md`, `cookbook/orm-typed-persistence.md`, `repository-pattern.md`, `serde-schema.md`, `roundtrip-serialization.md` |
| **Core Logic** | What does this code _do_? Is it pure and testable? | `strategy-pattern.md`, `facade-pattern.md`, `observer-pattern.md` |
| **Observability** | Are metrics/logs/traces/alerts separated? Can telemetry fail without breaking the app? | `structlog-pattern.md`, `event-bus-observability.md`, `loguru-antipattern.md` |

**The litmus test**: remove config parsing, resource management, persistence I/O, and observability from a function — does the remainder express pure business intent? If not, facets are entangled.

## Core Principles

Only seven. Each is a concrete "how", not an abstract "whether". Specific rules and examples live in the best-practice docs — search them with `uv run python scripts/purist search <keyword>`.

| # | Principle | Best-Practice Doc |
|---|-----------|-------------------|
| 1 | **Direct over indirect** — reach, don't check. do, don't ask. dot access, not `hasattr`. let errors propagate, don't layer try-catch. validate once at boundaries, trust internally. abstract when the pattern appears, not before. | `direct-over-indirect.md` |
| 2 | **Fail fast** — untrusted data validated at system boundaries. bad input crashes at entry point, not 10 layers deep. zero `except: pass`, zero bare `except`. | `fail-fast.md` |
| 3 | **Explicit over implicit** — naming is design; a wrong name is a wrong design. zero magic methods, zero `*args/**kwargs` abuse. signatures tell the truth. | `explicit-over-implicit.md` + `naming-and-readability.md` |
| 4 | **Types are documentation that compiles** — ban `Any`, `type: ignore`, `# noqa`. schema at every serialization boundary. precise types eliminate defensive checks. | `type-safety.md` + `serde-boundary.md` |
| 5 | **Core logic is pure** — push I/O, resources, and side effects to the edges. composition over inheritance. single owner per resource lifecycle. async over threads; process isolation for strong boundaries. | `composition-over-inheritance.md` + `coroutine-vs-thread.md` + `process-isolation.md` |
| 6 | **Structured observability** — logs are events (dicts), not strings. structlog only. output to stderr, never open log files. telemetry fault-isolated from the app. | `structured-logging.md` |
| 7 | **Red → Green → Refactor** — write a failing test first. minimum code to pass. refactor with the test safety net. | `red-green-tdd.md` |

## Browsing the Skill

```bash
uv run python scripts/purist list [best-practice|case-study|cookbook|all]  # list docs with tags
uv run python scripts/purist related <filename.md>                # find related docs
uv run python scripts/purist tags [<filter>]                      # list all tags with file counts
uv run python scripts/purist search <keyword>                     # search by keyword across all docs
uv run python scripts/purist checklist                            # quality checklist
uv run python scripts/purist check src/                           # scan for anti-patterns
```

**Tip for agents**: Run `uv run python scripts/purist tags` first to discover what tags exist, then use `uv run python scripts/purist search <tag>` to find the exact doc. This is faster than guessing keywords.

Search across all docs with grep/rg directly on `skills/python-purist/`. Only 49 files.

## Quality Checklist

Run `uv run python scripts/purist checklist` for the full list. Eight concrete items — each is a yes/no question you can answer in 5 seconds. Details for any item: `uv run python scripts/purist search <keyword>`.

- [ ] All function params and returns fully type-annotated? Zero `Any`, `type: ignore`, `# noqa`?
- [ ] Serialization boundaries have explicit schema (msgspec.Struct)? Data validated once at boundary, never patched downstream?
- [ ] Zero `hasattr()` or `dict.get(key, default)` masking missing data? Zero input patching chains?
- [ ] Zero `except: pass` or bare `except`? Errors propagate to the layer that can actually handle them?
- [ ] Core logic functions free of I/O? External resources have a single lifecycle owner?
- [ ] Every public function has a test? Test written before implementation? Regression tests self-verified (break key line, test must fail)?
- [ ] All logging structured (structlog)? Zero `print()` or `loguru`? Output to stderr only? Telemetry fault-isolated?
- [ ] Files ≤ 400 lines (warning) / ≤ 600 lines (error)? Functions pass `purist check` complexity checks?

---

**Pre-audit your code**: run `uv run python scripts/purist check <your_source_dir>` before submitting a PR.
