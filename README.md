# opendawn

Agent skills and custom agents for AI coding tools — OpenCode, Claude Code, and the `npx skills` ecosystem.

## Quick Install

Install into your current project (default):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh)
```

Install globally (`~/.config/opencode`, `~/.claude`):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -g
```

Non-interactive (overwrite all without asking):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -y
```

Or clone manually:

```bash
git clone https://github.com/Tomorrowdawn/opendawn.git
cd your-project
bash ../opendawn/scripts/install.sh      # local, interactive
bash ../opendawn/scripts/install.sh -g   # global
bash ../opendawn/scripts/install.sh -y   # non-interactive
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
| `YuuDev` | Phase 1 — requirement exploration, design consensus, coding instruction authoring |
| `YuuCoder` | Phase 2 — reads coding instructions, implements in worktree, commits, self-reviews |

### Custom Commands (`.opencode/commands/`)

| Command | Description |
|---------|-------------|
| `/yuucode` | Skip design, delegate directly to YuuCoder for implementation |

### Skills (`skills/`)

Platform-independent agent skills.

| Skill | Description |
|-------|-------------|
| `python-purist` | Opinionated Python coding standards — type safety, composition over inheritance, coroutines over threads |

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
├── .opencode/
│   ├── agents/                    # OpenCode agent definitions
│   │   ├── yuudev.md
│   │   └── yuucoder.md
│   └── commands/                  # Custom slash commands
│       └── yuucode.md
├── scripts/
│   └── install.sh                 # One-liner install script
├── external-wiki/                 # Reference docs for OpenCode plugin system
├── opencode.json
└── package.json
```

## License

MIT — see [LICENSE](./LICENSE)
