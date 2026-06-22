# AGENTS.md — opendawn

Platform-independent agent skills.

## Quick commands

```bash
pnpm install          # install dependencies (no lockfile — resolved on install)
pnpm check            # type-check (tsc --noEmit) — the primary verification step
pnpm build            # compile with tsc (only needed for npm publish)
```

- Package manager is **pnpm** (workspace root has `pnpm-workspace.yaml`). Do not use npm/yarn.
- There is **no lockfile committed**. Dependencies resolve fresh on `pnpm install`.
- There are **no tests, no linter, no CI**. Type-checking is the sole quality gate.

## Architecture

```
skills/            → platform-independent skills installed via `npx skills`
.opencode/         → dogfooding config (custom agents)
roadmap/           → git-tracked long-term plans and desired final states
external-wiki/     → reference docs for the OpenCode plugin system
```

Two agents: `YuuDev` (primary, default direct mode + opt-in batch-launcher mode)
and `YuuCoder` (subagent, large-task worktree executor). Their system prompts
embed git discipline, scenario communication, and commit hygiene directly.
YuuCoder also inlines the lazy reflection ladder; YuuDev does not — scenario
output is its dominant pressure, and anti-verbosity reflexes must be opt-in
(`probe-and-plan` / `coding-instruction`) to avoid suppressing scenarios.
Skills are opt-in for deep-dive (`probe-and-plan`) and large-task spec
(`coding-instruction`).

The `ponytail` skill (MIT, external) is installed by `install.sh` and
referenced from YuuCoder's prompt; the ladder core is inlined there.
YuuDev loads lazy reflection only on explicit user signal.

## Worktree environment reuse

Agents may create git worktrees under `.tmp/{task}/worktree/`.

This project uses pnpm. Source changes must stay isolated per worktree, but pnpm's global content-addressed store should be reused.

Use:

```bash
pnpm install
pnpm check
```

Do not commit a lockfile. Do not use npm or yarn. Do not copy dependencies from another worktree manually unless explicitly instructed.

### Skills (`skills/`)

Platform-independent agent skills distributed via the `npx skills` CLI (Vercel ecosystem). Each skill is a directory with a `SKILL.md` containing YAML frontmatter + markdown body. Name must match `^[a-z0-9]+(-[a-z0-9]+)*$` and the directory name.

| Skill | Purpose |
|-------|---------|
| `probe-and-plan` | Opt-in deep-dive — take-a-step-back, ought-to-be, design format. Loaded only when symptoms recur or architecture mismatch is suspected. |
| `coding-instruction` | Spec for large-task workflow — instruction format, Change Scope, Test Boundary, blocker protocol, worktree lifecycle, task sizing. |
| `yuutest` | Red-green subworkflow used during the test-first phase of a coding instruction. |
| `python-purist` | Opinionated Python coding standards |
| `what-should-i-do` | Human-invoked morning orientation — summarize recent progress, roadmap position, and important next todos |
| `ponytail` *(externally installed)* | Lazy reflection ladder. Both agents' prompts inline the ladder core and reference this skill. |

## Constraints

- Do **not** commit a lockfile. It is intentionally absent.
- Do **not** add tests or CI unless explicitly requested — the repo is intentionally minimal.
- Use `roadmap/` for git-tracked long-term plans; keep local high-frequency work state in `warroom/` when present and disposable execution state in `.tmp/`.
- The `external-wiki/` directory contains curated reference docs about the OpenCode plugin API. Do not delete or reorganize it.
