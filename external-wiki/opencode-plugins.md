# OpenCode Plugin System

> **Docs**: https://opencode.ai/docs/plugins/
> **Type package**: `@opencode-ai/plugin` — provides `Plugin` type + `tool()` helper
> **Reference**: [opencode-goal-plugin](https://github.com/willytop8/OpenCode-goal-plugin) (38 ★)

---

## Plugin Loading

### Local files (auto-loaded)

| Location | Scope |
|----------|-------|
| `.opencode/plugins/` | Per-project |
| `~/.config/opencode/plugins/` | Global (all projects) |

Place `.js` or `.ts` files directly — auto-loaded at startup.

### npm packages (config)

```json
{
  "plugin": ["opencode-goal-plugin", "@my-org/custom-plugin"]
}
```

Installed automatically via Bun into `~/.cache/opencode/node_modules/`.

### Load order

1. Global config (`~/.config/opencode/opencode.json`)
2. Project config (`opencode.json`)
3. Global plugin dir (`~/.config/opencode/plugins/`)
4. Project plugin dir (`.opencode/plugins/`)

---

## Plugin Structure

### Minimal (JavaScript)

```js
export const MyPlugin = async ({ project, client, $, directory, worktree }) => {
  return {
    "session.idle": async (input, output) => { /* ... */ }
  }
}
```

### TypeScript

```ts
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async (ctx) => {
  return {
    // type-safe hooks
  }
}
```

### Context (`ctx`)

| Property | Description |
|----------|-------------|
| `project` | Current project info |
| `directory` | Working directory |
| `worktree` | Git worktree path |
| `client` | OpenCode SDK client (full session/files/tui API) |
| `$` | Bun shell API for executing commands |

---

## Hooks Reference

### Session Hooks (★ most useful for workflow plugins)

| Hook | Trigger | Use case |
|------|---------|----------|
| `session.idle` | Agent finishes a response | **Auto-continue**, wake agent |
| `session.compacted` | Context compaction finished | Resume after compaction |
| `session.created` | New session opens | Initialize plugin state |
| `session.deleted` | Session removed | Cleanup |
| `session.error` | Error occurs | Handle/report errors |
| `session.diff` | Session diff generated | Track changes |
| `session.status` | Status change | Monitor progress |
| `session.updated` | Session metadata changed | React to updates |

### Compaction Hooks (★ critical for long-running goals)

```ts
"experimental.session.compacting": async (input, output) => {
  // Inject goal context that survives compaction
  output.context.push("## Custom Context\n...")

  // OR replace the entire compaction prompt:
  output.prompt = "You are generating a continuation prompt..."
}
```

When `output.prompt` is set, it **replaces** the default prompt; `output.context` is ignored.

### Tool Hooks

| Hook | Trigger |
|------|---------|
| `tool.execute.before` | Before any tool call — can **block** or **modify** |
| `tool.execute.after` | After tool completes — inspect output, track usage |

```ts
"tool.execute.before": async (input, output) => {
  if (input.tool === "read" && output.args.filePath.includes(".env")) {
    throw new Error("Do not read .env files")
  }
}
```

### TUI Hooks

| Hook | Trigger |
|------|---------|
| `tui.prompt.append` | Text appended to prompt |
| `tui.command.execute` | User types `/command` — **intercept custom commands** |
| `tui.toast.show` | Toast notification shown |

### Command Hooks

| Hook | Trigger |
|------|---------|
| `command.executed` | A command finishes executing |

### Message Hooks

| Hook | Trigger |
|------|---------|
| `message.part.removed` | Part of a message removed |
| `message.part.updated` | Message content updated |
| `message.removed` | Full message removed |
| `message.updated` | Message changed |

### Permission Hooks

| Hook | Trigger |
|------|---------|
| `permission.asked` | Permission prompt shown |
| `permission.replied` | User responds to permission prompt |

### Shell Hooks

| Hook | Trigger |
|------|---------|
| `shell.env` | Inject env vars into all shell executions |

---

## Custom Tools

```ts
import { type Plugin, tool } from "@opencode-ai/plugin"

export const CustomToolsPlugin: Plugin = async (ctx) => {
  return {
    tool: {
      mytool: tool({
        description: "This is a custom tool",
        args: {
          foo: tool.schema.string(),
        },
        async execute(args, context) {
          const { directory, worktree } = context
          return `Hello ${args.foo} from ${directory}`
        },
      }),
    },
  }
}
```

- `tool.schema` = Zod schema helpers (`string()`, `number()`, `object()`, etc.)
- If a plugin tool shares a name with a built-in tool, the **plugin tool wins**.

---

## Dependencies (local plugins)

Local plugins that need npm packages require a `package.json` in the config directory:

```json
// .opencode/package.json
{ "dependencies": { "shescape": "^2.1.0" } }
```

OpenCode runs `bun install` at startup.

---

## Logging

Use `client.app.log()` instead of `console.log`:

```ts
await ctx.client.app.log({
  body: {
    service: "my-plugin",
    level: "info",        // debug | info | warn | error
    message: "Plugin initialized",
    extra: { foo: "bar" },
  },
})
```

---

## Plugin-level Options (config.json pattern)

```json
{
  "plugin": [
    ["opencode-goal-plugin", {
      "maxTurns": 10,
      "maxDurationMs": 900000,
      "maxTokens": 200000
    }]
  ]
}
```

The options object is passed as the second argument to the plugin factory function.

---

## TypeScript Compilation

TS plugins are compiled at load time by OpenCode. For npm-published plugins, pre-compile with `tsc`:

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "outDir": "dist",
    "declaration": true
  }
}
```
