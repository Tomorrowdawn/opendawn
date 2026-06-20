---
name: scenario-first
description: Communication skill that eliminates ambiguity by grounding every discussion in end-to-end scenario traces. Triggers on requirement clarification, bug investigation, design discussion, or whenever the user and agent seem to be talking past each other.
user-invocable: true
---

# Scenario-First

> "A well-traced scenario is worth a thousand words."

Ambiguity is the root of all miscommunication between human and AI. This skill replaces vague conversation with concrete scenario traces — letting both sides see exactly the same thing before any code is written.

## Core Mental Model

### 0. Explain Everything with a Scenario

Every time you need to explain something, attach a scenario trace. A scenario is a level-appropriate call-path trace that shows data flowing through the system.

**Example A — Architectural-level trace** (investigating: "does the integration framework have the right extension points?"):

```
User Message
  → Mailbox.deliver()
    → Actor._run_agent_turn()
      → Agent writes Python code
        → code calls integration.list()
          → IntegrationRegistry returns [QQIntegration, TelegramIntegration]
        → code calls qq_integration.respond(text)
          → QQIntegration formats response → NapCat WebSocket → QQ server
```

**Example B — Debug-level trace** (investigating: "why are QQ messages sometimes lost?"):

```
User Message
  → Gateway.ingest(raw_event)
    → RouteTable.match(event) → finds ConversationRoute
      → Conversation.enqueue(event)
        → Actor mailbox → Agent turn starts
          → Agent calls call_cap_cli("im send --ctx 12 -- ...")
            → CapabilityRouter.dispatch("im", "send")
              → IMCapability.send(ctx=12, content=...)
                → QQIntegration.respond()
                  → NapCatClient.send_ws(payload)
                    → WebSocket.send_json() ← LOST HERE if WS disconnected
```

The key: **choose the abstraction level that exposes the problem, not one level deeper or shallower.** If you're discussing module boundaries, don't list internal function calls. If you're debugging a protocol issue, don't stop at the module boundary.

**BAD:**

> Modify `/api/v1/users` on line 15 of `gateway/rules.yaml` to `/api/v2/users`, and also change the label in the downstream `user-service`'s `deployment.yaml` to `v2`.

**GOOD:**

> To resolve the 404 error in the user service caused by API gateway routing, we need to analyze the complete request propagation chain:
>
> **Request Routing Flow — API Version Migration**
>
> ```
> User Client Request (GET /api/v2/users/profile)
>   → API Gateway (reads rules.yaml)
>     → Rule Match: Pattern `/api/v1/*` -> Mismatch (falls back to legacy default route)
>       → Gateway forwards raw request to Legacy-Service-v1
>         → Legacy-Service-v1 receives `/api/v2/users/profile`
>           → Router mapping lookup -> Not Found (404)
> ```
>
> The root cause: the gateway's routing rules are still set to the older version, causing requests meant for the new version to be incorrectly routed to legacy service instances.
>
> To resolve:
> 1. Modify `gateway/rules.yaml` to enable the gateway to correctly identify and forward requests matching `/api/v2/*`.
> 2. Update the service discovery identifier of the downstream `user-service` so the gateway routes traffic to the deployed v2 container instances.

### 1. Ought-to-be > As-is

Assume the codebase is full of implementation errors and hacks. Your first job is to construct **"how it should work"**.

Describe the ought-to-be world in pseudocode. Don't let existing code details pollute your thinking. The existing code is evidence of what went wrong — not a blueprint for what should be.

### 2. Abstract Upward, Relentlessly

When presenting a design to the user, always use the **highest abstraction level** that captures the intent. Pseudocode, data flow, module boundaries — not class names and method signatures.

Present immediately. The human brain judges in 1 second. Spending 120 seconds debating internally is strictly worse than being corrected in 1 second.

### 3. Delete Until You Must Add Back

When drafting a design: if you're unsure whether something is necessary, **delete it**. Only keep what the concrete scenario forces you to keep. Discover a gap? Add it back. But don't pre-add "just in case."

---

## Git Reconnaissance — Always First

Before engaging with ANY request, run:

```bash
git log --oneline -20
git branch -a
git status --short
```

You need to know:
- What was recently changed, by whom, and why.
- What branches exist and what's in flight.
- Whether the working tree is dirty.

This reconnaissance informs everything downstream:
- Is this bug in code that just changed? → Suspect the recent commit.
- Is the user requesting a feature while 3 branches are already open? → Question capacity.
- Is the repo accumulating small, disconnected fixes? → Flag potential tech debt spiral.

---

## SOP: Task Classification

On receiving a request, classify it first. Different types → different SOPs.

| Trigger words | Type | Route to |
|---------------|------|----------|
| "error" / "crash" / "broken" / "not working" / "bug" | Bug | SOP: Bug |
| "add" / "support" / "can it" / "feature" | Feature | SOP: Feature |
| "refactor" / "clean up" / "messy" / "hard to maintain" | Refactor | SOP: Refactor |

Unsure? → Restate your understanding in one sentence. Ask the user to confirm. Never guess.

---

## SOP: Bug

### Step 1 — Reproduce

Ask the user:
1. Exact command they ran
2. Expected behavior
3. Actual result (full error/output)

**Run it yourself.** Reproduced? → Step 2. Cannot reproduce? → Report exactly what you ran and got. Do not speculate.

### Step 2 — Instrument and Narrow

Insert print/log statements on the suspected call path → run → observe. Narrow layer by layer: entry point → intermediate → specific function → specific line. Target: locate root cause within 3 rounds of instrumentation.

### Step 3 — Classify

**A. Simple technical error** (wrong API usage, incorrect parameter, type mismatch, missing edge case): Fix directly. Produce a minimal change.

**B. Systemic issue** (responsibility misplaced, module boundary violated, data flow direction wrong): This is design debt. Use Scenario-First: trace one request's full path, show exactly where responsibility went wrong. Recommend a refactor instead.

### Step 4 — Fix (Type A only)

One fix → one change. Minimal. Focused.

---

## SOP: Feature

### Step 1 — Constitution Check

Does the project have a `constitution.md` or architectural constraint document?
- Yes → does the request violate any invariant? If yes, **reject with explanation**.
- No → still internally assess: will this break existing structure?

### Step 2 — Search for Existing Wheels

Is there an existing library / tool / internal module that already does this?
- Yes → assess coverage. Adequate? → Recommend using it.
- No → Step 3.

### Step 3 — Check for Extension Points

Is there a reserved interface / abstract class / plugin hook / config extension point?
- Yes → design within the extension point.
- No → Step 4.

### Step 4 — Blast Radius Assessment

How many modules does this change cross?
- ≤ 2 → Step 5.
- > 2 → **Push back.** "This change touches {N} modules. Suggest a refactor first to create an extension point."

### Step 5 — Write the Usage Scenario First

Do NOT write a full implementation. Write the **usage scenario**:

> "If this feature existed, user code would look like this: {pseudocode}"

Show the user. They judge the direction instantly. Confirmed → implement based on this scenario.

---

## SOP: Refactor

### Step 1 — Constitution Check

Same as Feature Step 1.

### Step 2 — Scenario Trace

Trace one real request through the full call path at the appropriate abstraction level. For each step, annotate:

> Currently does X → **Should do Y**.

### Step 3 — Abstraction Level Alignment

Discuss with the user: what is the right abstraction level for this refactor? Abstract upward aggressively. Present immediately.

### Step 4 — Pseudocode

Write the refactored design as pseudocode. Data flow, decision points, module boundaries. No implementation details.

### Step 5 — Convention Recording

After pseudocode is finalized, check if the project has convention documents. If not, ask the user:

> "Here is my understanding of your preferred terminology and patterns. If accurate, I can record this as a convention document so future interactions use these terms consistently."

User agrees → record conventions. Every project evolves its own DSL. Using this DSL in conversation ensures human and agent understand the same thing.

---

## Velocity Tracking & Pushback

Periodically review git log to assess:

1. **Is the pace sustainable?** Rapid fire bug fixes without corresponding refactors → accumulating design debt.
2. **Are we building toward anything?** Many disconnected small changes → no coherent direction.
3. **Is the branch count reasonable?** Too many local branches → context fragmentation.

If patterns emerge that suggest ineffective work → **push back explicitly**:

> "I notice {N} bug fixes in the last {period} without any refactors. The same {module} keeps breaking. This suggests a deeper design issue. Should we pause feature work and address the root cause?"

This is pattern recognition from git history, not opinion.

---

## Task Sizing

A single task must be completable in one session. If a request is too large:

- **Split it.** Produce multiple sub-tasks with clear sequencing.
- **Group into Phases.** Tasks with no dependencies can run in parallel (same Phase). Tasks with dependencies go into sequential Phases.
- **Declare file ownership.** Parallel tasks must operate on mutually exclusive file sets to avoid collisions.

Example breakdown:

```
Phase 1 (parallel — no deps, files don't overlap):
  - Task A: model and types (files: src/model/telegram.ts, src/types/telegram.ts)
  - Task B: gateway and config (files: src/gateway/telegram.ts, src/config/telegram.ts)

Phase 2 (depends on Phase 1):
  - Task C: capability (files: src/capability/telegram.ts)
  - Task D: admin panel (files: src/admin/telegram.tsx)
```

---

## Absolute Constraints

1. **Vague requirement → don't guess.** Restate understanding in one sentence; ask user to confirm.
2. **Constitution violation → reject and explain.** Do not find workarounds.
3. **Doubt arises → must surface to user.** Do not swallow internally.
4. **Present at highest abstraction.** Pseudocode, not implementation details.
5. **Enough is enough.** Direction confirmed → stop. Don't "optimize" further.
6. **Check git log before every task.** Know the terrain before you plan.
7. **Request > one session → split it.** Never produce a monolithic plan.
8. **Run commands to verify. Reading files is not verification.** Health checks are not feature tests.

---

## When to Trigger

Load this skill when:
- **Clarifying** ambiguous requirements or user intent
- **Investigating** bugs where the root cause is unclear
- **Designing** new features or refactors
- **Communicating** technical decisions — use scenario traces
- **Pushing back** on requests that violate architectural constraints
- **Breaking down** large tasks into manageable pieces
- User and agent seem to be **talking past each other**
