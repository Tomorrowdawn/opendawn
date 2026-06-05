# Skills Ecosystem (`skills` CLI)

> **Package**: `skills` (npm) — The CLI for the open agent skills ecosystem
> **Repo**: [github.com/vercel-labs/skills](https://github.com/vercel-labs/skills)
> **Reference repo**: [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) (27.6k ★)

---

## Install Skills

```bash
npx skills add vercel-labs/agent-skills
```

### Source Formats

| Format | Example |
|--------|---------|
| GitHub shorthand | `npx skills add vercel-labs/agent-skills` |
| Full GitHub URL | `npx skills add https://github.com/vercel-labs/agent-skills` |
| Subdirectory | `npx skills add https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines` |
| GitLab URL | `npx skills add https://gitlab.com/org/repo` |
| Any git URL | `npx skills add git@github.com:user/repo.git` |
| Local path | `npx skills add ./my-local-skills` |

### Options

| Option | Description |
|--------|-------------|
| `-g, --global` | Install to `~/.config/` instead of project |
| `-a, --agent <agents...>` | Target specific agents (`claude-code`, `codex`, `opencode`, `cursor`...) |
| `-s, --skill <skills...>` | Install specific skills by name (`'*'` = all) |
| `-l, --list` | List available skills without installing |
| `--copy` | Copy files instead of symlinking |
| `-y, --yes` | Skip all confirmation prompts |

### Use Without Installing

```bash
# Generate a prompt for one skill
npx skills use vercel-labs/agent-skills --skill nextjs

# Start an agent interactively with the prompt
npx skills use vercel-labs/agent-skills --skill nextjs --agent claude-code
```

---

## Supported Agents

OpenCode, Claude Code, Codex, Cursor, Windsurf, Kilo Code, Amazon Q, Antigravity, Augment, Cline, Continue, CoStrict, Crush, Cursor, Factory, Gemini CLI, GitHub Copilot, Goose, Kilo Code, Kiro, OpenCode, Pi, Qoder, Qwen Code, RooCode, Trae, and 40+ more.

---

## Skill File Format

### Directory Convention

```
skills/
└── <skill-name>/          # Directory name = skill name
    ├── SKILL.md           # Required — YAML frontmatter + Markdown body
    ├── scripts/           # Optional — helper scripts
    └── references/        # Optional — supporting docs
```

### SKILL.md Frontmatter

```yaml
---
name: goal-driven                    # Required: 1-64 chars, lowercase-hyphenated
description: Drive development...    # Required: 1-1024 chars
license: MIT                         # Optional
compatibility: opencode              # Optional
metadata:                            # Optional: string→string map
  audience: developers
  workflow: goal-driven
---
## What I Do
...
```

### Name Validation Regex

```
^[a-z0-9]+(-[a-z0-9]+)*$
```

- No uppercase, no consecutive `--`, no leading/trailing `-`
- Must match the directory name

---

## Publishing Skills for `npx skills`

1. Create a GitHub repo with a `skills/` directory at root
2. Each subdirectory = one named skill with `SKILL.md`
3. Users install: `npx skills add <user>/<repo>`
4. Individual skill: `npx skills add <user>/<repo> --skill <name>`

### Optional: `skills.sh.json` badge

```json
{ "name": "opendawn", "description": "Goal-driven workflow skills" }
```

Used by [skills.sh](https://skills.sh) to generate a shield badge.
