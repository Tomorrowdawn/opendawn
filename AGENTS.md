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
roadmap/           → git-tracked long-term plans and desired final states
.opencode/         → dogfooding config (custom agents + commands)
external-wiki/     → reference docs for the OpenCode plugin system
```

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
| `python-purist` | Opinionated Python coding standards |
| `probe-and-plan` | Phase 1 planning — run real commands, clarify quickly, design with scenarios, write coding instructions |
| `what-should-i-do` | Human-invoked morning orientation — summarize recent progress, roadmap position, and important next todos |
| `yuucoder` | Phase 2 implementation — execute instructions in a worktree, commit, verify, self-review, report blockers |

## Constraints

- Do **not** commit a lockfile. It is intentionally absent.
- Do **not** add tests or CI unless explicitly requested — the repo is intentionally minimal.
- Use `roadmap/` for git-tracked long-term plans; keep local high-frequency work state in `warroom/` when present and disposable execution state in `.tmp/`.
- The `external-wiki/` directory contains curated reference docs about the OpenCode plugin API. Do not delete or reorganize it.
