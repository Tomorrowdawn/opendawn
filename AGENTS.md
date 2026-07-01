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

Three agents: `YuuDev` (primary developer), `YuuCoder` (subagent executor), and
`YuuPM` (primary requirements/roadmap maintainer). YuuDev and YuuCoder share
code-level discipline; YuuPM owns requirements and never touches code.
Their system prompts embed git discipline, scenario communication, and commit
hygiene directly.

Skills are human-invoked by default, with one exception:
`scenario-communication` may load automatically because scenario traces are the
default alignment surface between human and agent. Other skill descriptions are
intentionally brief and human-facing; agents should not proactively load those
skills during ordinary work.
The main design flow is conversational and optional:

```
design-language
  -> core-design
    -> extensibility-audit
    -> lifecycle-design
      -> facade-design
        -> development
```

Humans can iterate `core-design` and `extensibility-audit` with the LLM until
the core flow and context-access model are stable, then iterate lifecycle, then
facade. Development reads the final core/lifecycle/facade design artifacts and
implements with senior engineering judgment. Not every task needs this flow.

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
| `scenario-communication` | Auto-loadable scenario trace method for human-agent alignment. |
| `design-language` | Human-invoked notes for design narration language. |
| `core-design` | Human-invoked handbook for core process design and context access. |
| `extensibility-audit` | Human-invoked audit for open-closed design pressure. |
| `lifecycle-design` | Human-invoked handbook for lifecycle design. |
| `facade-design` | Human-invoked handbook for facade and interface design. |
| `senior-dev` | Human-invoked handbook for senior development judgment. |
| `probe-and-plan` | Human-invoked deep-dive for root-cause investigation. |
| `python-purist` | Human-invoked Python handbook for patterns and anti-patterns. |
| `what-should-i-do` | Human-invoked morning orientation — summarize recent progress, roadmap position, and important next todos |

## Constraints

- Do **not** commit a lockfile. It is intentionally absent.
- Do **not** add tests or CI unless explicitly requested — the repo is intentionally minimal.
- Use `roadmap/` for git-tracked long-term plans; keep local high-frequency work state in `warroom/` when present and disposable execution state in `.tmp/`.
- The `external-wiki/` directory contains curated reference docs about the OpenCode plugin API. Do not delete or reorganize it.
- To locate OpenCode runtime logs or session data (SQLite at `~/.local/share/opencode/opencode.db`, text logs at `~/.local/share/opencode/log/`), see `external-wiki/opencode-logs.md` for paths and ready-to-use `sqlite3` queries.
