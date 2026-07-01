# opendawn

Agent skills and custom agents for AI coding tools: OpenCode, Claude Code, and
the `npx skills` ecosystem.

## Quick Install

Install into your current project:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh)
```

Install globally:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -g
```

Non-interactive:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -y
```

`npx skills` CLI users:

```bash
npx skills add Tomorrowdawn/opendawn
```

## Architecture

Opendawn is a small set of human-invoked skills plus lightweight agent prompts.
The current design philosophy is:

- Fewer skills, each with a narrow job.
- Skill descriptions are brief and human-facing, except the scenario skill.
- Agents should not proactively load skills during ordinary work, except
  `scenario-communication`.
- Final design docs should describe the current intended model, not historical
  failed attempts.

The optional design flow is:

```text
design-language
  -> core-design
    -> extensibility-audit
    -> lifecycle-design
      -> facade-design
        -> development
```

Humans usually iterate `core-design` and `extensibility-audit` with the LLM until
the core flow and context-access model are stable. Then lifecycle is refined,
then facade contracts are made precise, then development starts. Not every task
needs this workflow.

## Custom Agents

| Agent | Role |
|-------|------|
| `YuuDev` | Primary developer. Implements directly, debugs, reviews, and discusses design. Uses skills only when explicitly invoked. |
| `YuuCoder` | Subagent executor for scoped implementation tasks. Reads design artifacts as contracts when provided. |
| `YuuPM` | Roadmap and requirements maintainer. Writes docs, not code. |

## Skills

| Skill | Description |
|-------|-------------|
| `scenario-communication` | Auto-loadable scenario trace method for human-agent alignment. |
| `design-language` | Human-invoked notes for design narration language. |
| `core-design` | Human-invoked handbook for core process design and context access. |
| `extensibility-audit` | Human-invoked audit for open-closed design pressure. |
| `lifecycle-design` | Human-invoked handbook for lifecycle design. |
| `facade-design` | Human-invoked handbook for facade and interface design. |
| `senior-dev` | Human-invoked handbook for senior development judgment. |
| `probe-and-plan` | Human-invoked deep-dive for root-cause investigation. |
| `python-purist` | Human-invoked Python handbook for patterns and anti-patterns. |
| `what-should-i-do` | Human-invoked morning orientation. |

## Development

```bash
pnpm install
pnpm check
```

## Structure

```text
opendawn/
├── skills/                    # Platform-independent skills
├── roadmap/                   # Git-tracked long-term project plans
├── .opencode/agents/          # OpenCode agent definitions
├── scripts/install.sh         # Installer
├── external-wiki/             # Reference docs for OpenCode plugin system
├── opencode.json
└── package.json
```

## License

MIT, see [LICENSE](./LICENSE).
