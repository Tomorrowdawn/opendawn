# OpenCode SDK (`@opencode-ai/sdk`)

> **Docs**: https://opencode.ai/docs/sdk/
> **Install**: `npm install @opencode-ai/sdk`
> **Types**: [types.gen.ts](https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts)

---

## Client Creation

### Start server + client

```ts
import { createOpencode } from "@opencode-ai/sdk"

const { client, server } = await createOpencode({
  hostname: "127.0.0.1",
  port: 4096,
  config: { model: "anthropic/claude-sonnet-4-20250514" },
})

console.log(server.url)  // http://127.0.0.1:4096
```

Options: `hostname`, `port`, `signal` (AbortSignal), `timeout` (ms, default 5000), `config`

### Client only (connect to running server)

```ts
import { createOpencodeClient } from "@opencode-ai/sdk"

const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })
```

---

## Session API ★ (most used)

### Create & manage

```ts
// Create
const session = await client.session.create({
  body: { title: "My session" }
})
const id = session.data.id

// List
const sessions = await client.session.list()

// Get one
const detail = await client.session.get({ path: { id } })

// Children (subagent sessions)
const children = await client.session.children({ path: { id } })

// Update title/meta
await client.session.update({ path: { id }, body: { title: "New title" } })

// Delete
await client.session.delete({ path: { id } })
```

### Send prompts ★

```ts
// Full prompt (get AI response)
const result = await client.session.prompt({
  path: { id },
  body: {
    parts: [{ type: "text", text: "Hello!" }],
    model: { providerID: "anthropic", modelID: "claude-sonnet-4-20250514" },
  },
})
// result.data.info → AssistantMessage
// result.data.parts → Part[] (text, tool_use, etc.)

// Context-only injection (no AI response) — useful for plugins
await client.session.prompt({
  path: { id },
  body: { noReply: true, parts: [{ type: "text", text: "You are a helper." }] },
})
```

### Send commands

```ts
const result = await client.session.command({
  path: { id },
  body: { command: "init" },
})
```

### Shell execution

```ts
const result = await client.session.shell({
  path: { id },
  body: { command: "npm test" },
})
```

### Messages

```ts
// List all messages in a session
const messages = await client.session.messages({ path: { id } })
// → { info: Message, parts: Part[] }[]

// Get specific message
const msg = await client.session.message({ path: { id, messageID: "..." } })
```

### Undo / Redo

```ts
await client.session.revert({ path: { id }, body: { messageID: "..." } })
await client.session.unrevert({ path: { id } })
```

### Abort

```ts
await client.session.abort({ path: { id } })
```

### Init (create AGENTS.md)

```ts
await client.session.init({ path: { id } })
```

### Summarize

```ts
await client.session.summarize({ path: { id }, body: { /* options */ } })
```

### Share / Unshare

```ts
const shared = await client.session.share({ path: { id } })
await client.session.unshare({ path: { id } })
```

### Permission response

```ts
await client.postSessionByIdPermissionsByPermissionId({
  path: { id, permissionID: "..." },
  body: { action: "allow" },
})
```

---

## Structured Output (JSON Schema)

```ts
const result = await client.session.prompt({
  path: { id },
  body: {
    parts: [{ type: "text", text: "Analyze this and return structured data" }],
    format: {
      type: "json_schema",
      schema: {
        type: "object",
        properties: {
          summary: { type: "string" },
          score: { type: "number" },
        },
        required: ["summary", "score"],
      },
      retryCount: 2,  // validation retries (default 2)
    },
  },
})
// result.data.info.structured_output → { summary: "...", score: 85 }
```

---

## File Search & Read

```ts
// Search text in files
const matches = await client.find.text({
  query: { pattern: "function.*auth" },
})
// → { path, lines, line_number, absolute_offset, submatches }[]

// Find files by name
const files = await client.find.files({
  query: { query: "*.ts", type: "file", limit: 50 },
})

// Find directories
const dirs = await client.find.files({
  query: { query: "src", type: "directory", limit: 20 },
})

// Read a file
const content = await client.file.read({
  query: { path: "src/index.ts" },
})
// → { type: "raw" | "patch", content: string }

// File status (tracked files)
const status = await client.file.status()
```

---

## TUI Control

```ts
// Append to prompt input
await client.tui.appendPrompt({ body: { text: "Review this code" } })

// Submit current prompt
await client.tui.submitPrompt()

// Clear prompt
await client.tui.clearPrompt()

// Execute command
await client.tui.executeCommand({ body: { command: "init" } })

// Show toast notification
await client.tui.showToast({
  body: { message: "Task done", variant: "success" },
})

// Open UI panels
await client.tui.openHelp()
await client.tui.openSessions()
await client.tui.openThemes()
await client.tui.openModels()
```

---

## Events (SSE Stream) ★

```ts
const events = await client.event.subscribe()

for await (const event of events.stream) {
  console.log(event.type, event.properties)
  // Types: session.idle, session.error, session.compacted,
  //        tool.execute.after, tool.execute.before,
  //        command.executed, message.updated, ...
}
```

---

## Other APIs

### Global

```ts
const health = await client.global.health()
// → { healthy: true, version: "..." }
```

### Project

```ts
const projects = await client.project.list()
const current = await client.project.current()
```

### Config

```ts
const cfg = await client.config.get()
const { providers, default: defaults } = await client.config.providers()
```

### Path

```ts
const pathInfo = await client.path.get()
```

### Auth

```ts
await client.auth.set({
  path: { id: "anthropic" },
  body: { type: "api", key: "sk-..." },
})
```

### App

```ts
// Write log entry
await client.app.log({
  body: { service: "my-app", level: "info", message: "Done" },
})

// List available agents
const agents = await client.app.agents()
```
