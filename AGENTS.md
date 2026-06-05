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
.opencode/         → dogfooding config (custom agents + commands)
external-wiki/     → reference docs for the OpenCode plugin system
```

### Skills (`skills/`)

Platform-independent agent skills distributed via the `npx skills` CLI (Vercel ecosystem). Each skill is a directory with a `SKILL.md` containing YAML frontmatter + markdown body. Name must match `^[a-z0-9]+(-[a-z0-9]+)*$` and the directory name.

## Constraints

- Do **not** commit a lockfile. It is intentionally absent.
- Do **not** add tests or CI unless explicitly requested — the repo is intentionally minimal.
- The `external-wiki/` directory contains curated reference docs about the OpenCode plugin API. Do not delete or reorganize it.
