# opendawn

Agent skills ecosystem for AI coding agents.

## What's Inside

### Platform-Independent Skills (`skills/`)

Installable via `npx skills` CLI. Works with OpenCode, Claude Code, Codex, Cursor, and 67+ agents.

```bash
npx skills add Tomorrowdawn/opendawn
```

| Skill | Description |
|-------|-------------|
| `reviewer-loop` | Quality gate — review completed work and approve or trigger rework |

## Development

```bash
pnpm install
pnpm check          # TypeScript type checking
```

## Structure

```
opendawn/
├── skills/                        # Platform-independent agent skills
│   └── reviewer-loop/SKILL.md
├── .opencode/                     # Dogfood config
├── external-wiki/                 # Reference docs
├── opencode.json
└── package.json
```

## License

MIT — see [LICENSE](./LICENSE)
