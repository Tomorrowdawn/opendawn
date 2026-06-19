# opendawn

Agent skills and custom agents for AI coding tools — OpenCode, Claude Code, and the `npx skills` ecosystem.

## Quick Install

Install into your current project (default):

```bash
curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh | bash
```

Install globally (`~/.config/opencode`, `~/.claude`):

```bash
curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh | bash -s -- -g
```

Or clone manually:

```bash
git clone https://github.com/Tomorrowdawn/opendawn.git
cd your-project
bash ../opendawn/scripts/install.sh      # local
bash ../opendawn/scripts/install.sh -g   # global
```

`npx skills` CLI users:

```bash
npx skills add Tomorrowdawn/opendawn
```

## What's Inside

### Custom Agents (`.opencode/agents/`)

OpenCode primary and subagent definitions.

| Agent | Role |
|-------|------|
| `YuuDev` | Phase 1 — requirement exploration, design consensus, encoding instruction authoring |
| `YuuCoder` | Phase 2 — reads encoding instructions, implements in worktree, commits, self-reviews |

### Skills (`skills/`)

Platform-independent agent skills.

| Skill | Description |
|-------|-------------|
| `python-purist` | Opinionated Python coding standards — type safety, composition over inheritance, coroutines over threads |
| `reviewer-loop` | Quality gate — review completed work against goals, approve or trigger rework |

## Development

```bash
pnpm install
pnpm check          # TypeScript type checking
```

## Structure

```
opendawn/
├── skills/                        # Platform-independent agent skills
│   ├── python-purist/SKILL.md
│   └── reviewer-loop/SKILL.md
├── .opencode/
│   └── agents/                    # OpenCode agent definitions
│       ├── yuudev.md
│       └── yuucoder.md
├── scripts/
│   └── install.sh                 # One-liner install script
├── external-wiki/                 # Reference docs for OpenCode plugin system
├── opencode.json
└── package.json
```

## License

MIT — see [LICENSE](./LICENSE)
