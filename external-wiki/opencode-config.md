# OpenCode Configuration Reference

> **Config docs**: https://opencode.ai/docs/config/
> **Schema**: `https://opencode.ai/config.json`

---

## Commands (`/command`)

> **Docs**: https://opencode.ai/docs/commands/

### File structure

```
.opencode/commands/<name>.md    # Per-project
~/.config/opencode/commands/    # Global
```

### Markdown format

```markdown
---
description: Run tests with coverage
agent: build
model: anthropic/claude-sonnet-4
---
Run the full test suite and show failures.
```

### JSON config (in `opencode.json`)

```json
{
  "command": {
    "test": {
      "template": "Run tests...",
      "description": "Run tests with coverage",
      "agent": "build",
      "model": "anthropic/claude-sonnet-4",
      "subtask": true
    }
  }
}
```

### Template variables

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments after the command |
| `$1`, `$2`, `$3`... | Positional arguments |
| `` !`command` `` | Inline shell output |
| `@filename` | Include file content |

### Options

| Field | Description |
|-------|-------------|
| `template` | **Required** — the prompt sent to LLM |
| `description` | Shown in TUI command palette |
| `agent` | Which agent executes this (default: current) |
| `subtask` | `true` → force subagent invocation (no context pollution) |
| `model` | Override the default model |

---

## Agents

> **Docs**: https://opencode.ai/docs/agents/

### File structure

```
.opencode/agents/<name>.md     # Per-project
~/.config/opencode/agents/     # Global
```

### Markdown format

```markdown
---
description: Code reviewer
mode: subagent
model: anthropic/claude-sonnet-4
temperature: 0.1
hidden: true
permission:
  edit: deny
  bash:
    git diff: allow
    git log*: allow
---
You are a code reviewer. Focus on security and performance.
```

### JSON config

```json
{
  "agent": {
    "my-agent": {
      "description": "...",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4",
      "temperature": 0.1,
      "steps": 10,
      "hidden": true,
      "color": "#ff6b6b",
      "prompt": "{file:./prompts/my-agent.txt}",
      "permission": {
        "edit": "deny",
        "bash": { "git *": "ask" },
        "task": { "*": "deny", "code-reviewer": "allow" }
      }
    }
  }
}
```

### Mode

| Value | Behavior |
|-------|----------|
| `primary` | Main agent, switchable via Tab key |
| `subagent` | Invoked by @mention or Task tool |
| `all` | Available in both contexts (default) |

### Built-in agents

| Agent | Mode | Description |
|-------|------|-------------|
| `build` | primary | Full tool access (default) |
| `plan` | primary | Read-only, edits/bash = ask |
| `general` | subagent | Full tool access, multi-step tasks |
| `explore` | subagent | Read-only codebase exploration |
| `scout` | subagent | Read-only external docs/deps research |

### Task permissions

Control which subagents an agent can invoke:

```json
{
  "permission": {
    "task": {
      "*": "deny",
      "code-reviewer": "allow",
      "explore": "ask"
    }
  }
}
```

Last matching rule wins. `hidden: true` hides from @mention autocomplete but not from Task tool.

### Steps limit

```json
{ "steps": 10 }
```

When reached, agent gets a system prompt to summarise and recommend next steps.

### Top P & Temperature

```json
{ "temperature": 0.3, "top_p": 0.9 }
```

### Pass-through provider options

```json
{ "reasoningEffort": "high", "textVerbosity": "low" }
```

---

## Native Agent Skills

> **Docs**: https://opencode.ai/docs/skills/

### Locations (loaded in order)

| Location | Scope |
|----------|-------|
| `.opencode/skills/<name>/SKILL.md` | Project |
| `~/.config/opencode/skills/<name>/SKILL.md` | Global |
| `.claude/skills/<name>/SKILL.md` | Claude-compatible (project) |
| `~/.claude/skills/<name>/SKILL.md` | Claude-compatible (global) |
| `.agents/skills/<name>/SKILL.md` | Agent-compatible (project) |
| `~/.agents/skills/<name>/SKILL.md` | Agent-compatible (global) |

Discovery walks up from cwd to git worktree for project paths.

### SKILL.md format

```yaml
---
name: git-release                    # Required: 1-64 chars, regex ^[a-z0-9]+(-[a-z0-9]+)*$
description: Create releases          # Required: 1-1024 chars
license: MIT                          # Optional
compatibility: opencode               # Optional
metadata:                             # Optional: string→string map
  audience: maintainers
---
## What I Do
...
```

Name must match the directory name. Unknown frontmatter fields ignored.

### Permissions

```json
{
  "permission": {
    "skill": {
      "*": "allow",
      "internal-*": "deny",
      "experimental-*": "ask"
    }
  }
}
```

Per-agent override:

```json
{
  "agent": {
    "plan": {
      "permission": { "skill": { "internal-*": "allow" } }
    }
  }
}
```

### Disable skill tool

```json
{
  "agent": {
    "plan": { "tools": { "skill": false } }
  }
}
```

---

## Permissions (Global)

```json
{
  "permission": {
    "read": "allow",
    "edit": "ask",
    "bash": {
      "*": "ask",
      "git status": "allow",
      "npm test": "allow"
    },
    "task": "allow",
    "webfetch": "deny",
    "external_directory": "deny"
  }
}
```

### Permission keys

| Key | Tools gated |
|-----|-------------|
| `read` | read |
| `edit` | write, edit, apply_patch |
| `glob` | glob |
| `grep` | grep |
| `list` | list |
| `bash` | bash (supports glob patterns) |
| `task` | task (subagent invocation) |
| `external_directory` | Any file I/O outside project worktree |
| `todowrite` | todowrite, todoread |
| `webfetch` | webfetch |
| `websearch` | websearch |
| `lsp` | lsp |
| `skill` | skill |
| `question` | question |

Values: `"allow"` | `"ask"` | `"deny"` or glob-patterned object for bash/edit.

---

## Plugin Config

```json
{
  "plugin": [
    "opencode-goal-plugin",
    ["opencode-wakatime", { "apiKey": "..." }],
    "file://./local-plugin.ts"
  ]
}
```

npm packages installed via Bun to `~/.cache/opencode/node_modules/`. Local file paths load directly.

---

## Key Config Fields (top-level)

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4",    // Global default model
  "plugin": [...],                          // Plugin list
  "agent": { ... },                         // Agent overrides + custom agents
  "command": { ... },                       // Custom commands
  "permission": { ... },                    // Global permission rules
  "tools": { "write": true, "bash": true }  // (Deprecated — use permission)
}
```
