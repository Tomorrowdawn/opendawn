---
name: lifecycle-design
description: Human-invoked handbook for lifecycle design.
user-invocable: true
---

# Lifecycle Design

Use after the core process is stable. If design prose style matters, read
`design-language`.

## Goal

Describe how core components are constructed, run, reloaded, persisted,
migrated, and cleaned up while staying at design level. Do not drift into file
paths, router code, driver details, or private helper names unless the interface
itself is the design.

Natural language can explain intent, but lifecycle-critical concepts need
concrete shapes and flows. A new developer should not need to invent the major
records, owners, or startup order before implementation can begin.

## Cover

- Config deserialization into design concepts.
- Construction, dependency injection, and initialization order.
- Durable state creation, mutation, persistence, reload, migration, and discard.
- Runtime-only state reconstruction and cleanup.
- Cache population, invalidation, and refresh ownership.
- Resource ownership, child ownership, shutdown, and reverse-order cleanup.
- Failure, retry, rollback, disabled-state, and exposed error behavior.

## Shapes

When a design names a lifecycle record or boundary, show its shape directly:
`DeploymentConfig`, `ApplicationState`, `RuntimeState`, `ActorRecord`,
`IntegrationState`, `HistoryItem`, `CacheEntry`, `TaskState`, etc.

Shapes should be short and information-rich. They do not need to be compilable
classes. Use TypeScript-ish object notation with `ts` when highlighting helps
nested structure, or no fence for very short shapes. Avoid `text` for structured
content.

```ts
DeploymentConfig = {
  data_dir: Path
  server: { host: string = "127.0.0.1", port: number = 8765 }
  database: DatabaseConfig
  secrets: SecretPolicy
  initial_actors: ActorSeed[] = []
  // new fields need defaults or migration
}
```

Each important shape should make clear:

- Required startup fields.
- Optional fields and defaults.
- Durable, derived, or ephemeral fields.
- Reader, mutator, and owner.
- Additive, migrated, or rejected future fields.

## Registry And Factory Flow

Polymorphic lifecycle records must serialize an explicit `type` key. Runtime
construction resolves that key through a registry, validates subtype config, and
delegates construction to the subtype factory. Do not infer subtypes by guessing
field combinations.

```ts
ToolRecord = {
  type: "builtin.execute_python"
  config: JsonObject
  schema_version: number
}
```

```py
tool_cls = ToolRegistry.resolve(record.type)
tool_config = tool_cls.config_schema().load(record.config)
tool = tool_cls.from_config(tool_config, runtime)
```

Owned runtime children should expose explicit construction and cleanup
contracts:

```py
class RuntimeChild:
  @classmethod
  def from_config(cls, config, runtime): ...
  async def close(self): ...
```

Parents construct children, keep the handles they own, and close them in
reverse ownership order. Adding a Tool, Integration, Actor subtype, provider,
cache backend, or storage adapter should register a new type and factory rather
than modify a central switch statement.

## Operation Pseudocode

For startup, reload, enable/disable, create/remove, shutdown, and migration,
write concise pseudocode that exposes call structure. Prefer `py` fences. Use
design-level calls such as `load`, `persist`, `construct`, and `close`; do not
spell out low-level file I/O unless it is the lifecycle boundary.

```py
async def startup(config_path):
  config = migrate(load(DeploymentConfig, from_=config_path))
  registries = create_registries(config.registries)
  db = await Database.open(config.database)
  app_state = await migrate(load(ApplicationState, from_=db), registries)
  runtime = RuntimeState(config, db, registries)

  for state in app_state.integrations.enabled():
    try:
      runtime.integrations[state.name] = await construct_from_registry(
        registries.integrations, state, runtime
      )
    except LifecycleError as error:
      await persist(state, last_error=error)

  await runtime.gateway.start_after_routes_and_mailboxes_exist()
  return runtime
```

Pseudocode should show what is already persisted, what rolls back, what remains
disabled, what is cleaned up, and what error is exposed. Numbered lists are fine
for tiny linear checklists, but not as the main expression of lifecycle flow.

## Quality Bar

Before accepting a lifecycle design, check every named lifecycle object:

- Source and concrete shape are written if it is read at startup.
- Durable owner and version behavior are written if it is stored.
- Reconstruction inputs are written if it is rebuilt.
- `type`, registry, typed config, and factory are written if it is extensible.
- Owner, trigger, and reverse-order cleanup are written if it owns resources.
- Failure state, retry rule, and exposed error are written if it can fail.

Use assertive lifecycle language: `is`, `owns`, `creates`, `persists`,
`discards`, `rejects`, and `must`. Use `may` only for intentional extension
points or genuinely unresolved product decisions.
