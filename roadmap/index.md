# Roadmap

This directory is the project-level, git-tracked home for stable long-term plans, target shapes, and desired final states. It is organized as a **four-layer stack**, strictly top-down for derivation and strictly bottom-up for selection:

```
1. Charter       charter.md          Long-term vision + current-phase goal (with a stopping point)
2. Milestones    milestones.md       A chronological list of technical stopping points (grows freely)
3. Issues        issues/ISSUE-NNNN-*.md  Features / fixes / refactors from ANY source, triaged on two axes
4. Sprint        sprint.md           A frozen selection pulled FROM the issue backlog
```

Derivation flows **down** — the charter's phase goal spawns milestones; milestones (and ordinary product use) spawn issues.

A sprint is built **up** from issues — never the reverse. Issues accumulate first in the backlog, triaged on two axes: `priority` (P0–P3, importance) and `milestone` (M-N / all / none, urgency — concretely, whether the Issue is bound to the currently-active WIP milestone). The sprint then freezes a selection of already-triaged, already-estimated issues.

## What lives where

| Layer | File | Role |
|-------|------|------|
| **Charter** | `roadmap/charter.md` | The project's highest directive. Two parts: the durable long-term vision, and the current-phase goal with a definite stopping point. |
| **Milestones** | `roadmap/milestones.md` | A single chronological list. Each entry (`M-N`) is a technical stopping point — what it builds (design level, not implementation plan) and its observable stopping criterion. Status: `completed → WIP → draft` reads top-to-bottom. Frequently edited (by the human, or in dialogue with yuupm). |
| **Issues** | `roadmap/issues/ISSUE-NNNN-*.md` | Individual features / bug fixes / refactor phases, each a user-observable contract. Any source (milestone-derived, organically found, or cross-milestone). Classified on two axes: `priority` (P0–P3) and `milestone` (M-N / all / none). |
| **Sprint** | `roadmap/sprint.md` | A frozen selection from the approved backlog, sized to a 40h effective / 12h core budget (P0+P1 ≈ 12h core, P2/P3 fill to 40h). The `## Frozen Scope` section is locked once committed; mid-sprint changes go through ISSUE-CHANGE. |
| **Backlog (fuzzy)** | `roadmap/backlog.md` | Only for ideas too vague to write a scenario for yet. The bar for "too vague" is high — an Issue with no current sprint is still a perfectly valid Issue. |
| **Lessons** | `roadmap/lessons/lesson-*.md` | Records of Issue changes and their reasons (drift, correction, learning). |

## Other state

Use other locations for shorter-lived state:

- `warroom/` is for local, high-frequency work notes when present.
- `.tmp/` is for disposable agent execution state, task artifacts, and worktrees.

Roadmap notes should be specific enough to prevent drift, but stable enough that they do not need to change with every small implementation step — except the milestones list, which is expected to be edited frequently as the project's mid-term shape is negotiated.
