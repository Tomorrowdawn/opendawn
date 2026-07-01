---
name: lifecycle-design
description: Human-invoked handbook for lifecycle design.
user-invocable: true
---

# Lifecycle Design

This skill is loaded only when the human explicitly asks for it. Use it after
the core process is stable. If you need design prose conventions, read
`design-language`.

## Goal

Describe how the core components live over time while staying at design level.
The document must reduce implementation uncertainty. Natural language may
explain intent, but it is not enough for lifecycle-critical objects. When a
configuration, durable record, runtime state, resource owner, or reload boundary
is named, write its concrete shape.

Include serialization rules as far as they affect lifecycle and
interoperability. Do not drift into file-level implementation work, but do not
hide lifecycle facts behind vague prose.

## Lifecycle Surface

Cover the phases that matter:

- Configuration deserialization into design concepts.
- Component construction and dependency injection.
- Runtime initialization order.
- State creation, mutation, persistence, reload, and discard.
- Cache population, invalidation, and refresh ownership.
- Resource ownership and cleanup.
- Error/retry behavior when lifecycle operations fail.
- Upgrade or migration behavior when stored state changes shape.

## Concrete Shapes

Lifecycle design must define the concrete records that cross time boundaries.
If a section names a lifecycle concept such as `DeploymentConfig`,
`ApplicationState`, `RuntimeState`, `DurableState`, `IntegrationState`,
`ActorRecord`, `HistoryItem`, `CacheEntry`, or `TaskState`, it should show the
fields directly.

Prefer:

```text
DeploymentConfig = {
  data_dir: Path,
  server: ServerConfig,
  database: DatabaseConfig,
  secrets: SecretPolicy,
  initial_llms: list[LLMClientConfig],
  initial_actors: list[ActorSeed],
  # new fields are appended here with default / migration semantics
}
```

Over:

```text
DeploymentConfig is the read-only startup configuration, for example data dir,
server parameters, database location, secret policy, and initial actor
declarations.
```

The prose version does not lower uncertainty. It leaves the developer guessing
which fields exist, what owns them, and where future fields belong.

Each shape should answer:

- Which fields are required at startup.
- Which fields are optional and what default they use.
- Which fields are durable, derived, or ephemeral.
- Which component reads or mutates the field.
- Whether new fields are additive, migrated, or rejected.

Use comments inside the shape when that is the clearest way to state lifecycle
rules:

```text
IntegrationState = {
  id: str,
  type: str,
  name: str,
  enabled: bool,
  config: JsonObject,
  secret_refs: dict[str, SecretRef],
  schema_version: int,
  last_error: ConfigError | StartupError | None,
  # additive fields must default cleanly for disabled integrations
}
```

## Assertive Definitions

Lifecycle prose should be assertive. Do not write as if the design is a loose
survey of possibilities when the lifecycle contract needs a decision.

Use:

```text
RuntimeState is reconstructed from DeploymentConfig + ApplicationState.
RuntimeState is not serialized.
```

Avoid:

```text
RuntimeState generally represents in-memory facts and may be recreated from
configuration in most cases.
```

Use "may" only for intentional extension points or explicitly unresolved product
decisions. If a rule is part of correctness, say "must", "is", "owns",
"creates", "persists", "discards", or "rejects".

## Maintenance Assumption

Design for maintained code, not one-shot code. Lifecycle records will be edited
as the product changes: business records gain fields, context centers gain new
derived values, and old fields may need deletion or migration. For unstable
boundaries, leave explicit extension room in the record shape and say how new
fields are added, defaulted, migrated, or rejected.

This does not mean every core object should grow. Core lifecycle state should be
minimal and justified: if DeploymentConfig, RuntimeState, or a durable record
contains a field, the design should explain which lifecycle operation needs it.
If a future subcomponent needs new information, prefer extending that
subcomponent's config/state or its context access path instead of widening the
core lifecycle record.

## Boundaries

Lifecycle design may say:

```text
RuntimeState is serialized under the workspace data directory.
Session snapshots are append-only and reloaded at startup before actors resume.
Cache entries are disposable; missing cache never blocks reconstruction.
```

Lifecycle design should not say:

```text
Write src/runtime/state_store.ts with function loadState().
Use /var/app/foo/v3/state.json exactly unless facade requires that path.
```

Precise external paths, commands, APIs, and transport protocols belong to
`facade-design`. Concrete lifecycle records do not. A design-level shape such
as `DeploymentConfig = {...}` or `HistoryItem = ...` belongs here because it
defines what must survive construction, reload, shutdown, and migration.

## Deserialization And Factory Tree

Lifecycle design should describe deserialization as a standard dynamic
reflection flow, not as field guessing. Extensible systems usually restore
runtime objects from records that name a type, class, plugin, provider, or
registry key. The lifecycle design must say which key is serialized, which
registry resolves it, which typed config is produced, and which factory creates
the runtime object.

Prefer:

```text
ToolRecord = {
  type: "builtin.execute_python",
  config: JsonObject,
  schema_version: int,
}

tool_cls = ToolRegistry.resolve(record.type)
tool_config = tool_cls.config_schema().load(record.config)
tool = tool_cls.from_config(tool_config, runtime)
```

Over:

```text
If the record has python fields, create ExecutePython; if it has shell fields,
create BashTool.
```

Do not infer object classes by guessing field combinations. Field guessing
breaks open-closed design because every new subtype forces edits to the central
deserializer. The closed code path should deserialize the common envelope,
resolve the registered type, validate the subtype config, and delegate
construction to that subtype's factory.

Core lifecycle classes should therefore expose explicit factory and cleanup
contracts when they can own children:

```py
class RuntimeChild:
  @classmethod
  def from_config(cls, config, runtime):
    pass

  async def close(self):
    pass
```

The lifecycle graph should be a recursive ownership tree. Parents construct
children from typed configs, keep the handles they own, and close children in
reverse ownership order. This tree is what preserves open-closed behavior:
adding a new Tool, Integration, Actor subtype, provider, cache backend, or
storage adapter should register a new type and factory, not modify a central
switch statement.

## Operation Sequences

For each important lifecycle operation, include an ordered sequence or
pseudocode. At minimum cover startup, enable/disable or create/remove for major
runtime objects, shutdown, reload, and migration when relevant.

Good:

```text
startup:
  1. read DeploymentConfig
  2. open Database from DeploymentConfig.database
  3. load ApplicationState
  4. validate IntegrationState against registry
  5. construct RuntimeState
  6. start inbound services only after routes and mailboxes exist
```

Weak:

```text
Startup loads configuration and initializes runtime resources in the right
order.
```

The sequence should make failure boundaries visible: what is already persisted,
what is rolled back, what remains disabled, and what error is exposed.

## Anti-Vagueness Bar

Reject lifecycle text that only gives categories. A sentence shaped like
"X includes A, B, C, and so on" is usually not enough. Replace it with the
record, state transition, or operation sequence.

Before accepting a lifecycle design, check every named lifecycle object:

- If it is read at startup, its source and shape are written.
- If it is stored, its durable owner and version behavior are written.
- If it is reconstructed, the reconstruction inputs are written.
- If it is polymorphic or extensible, its serialized type key, registry, typed
  config, and factory are written.
- If it is cleaned up, the owner and trigger are written.
- If it owns children, recursive initialization and reverse-order recursive
  cleanup are written.
- If it can fail, the failure state and retry rule are written.

## Stability Rule

Do not design lifecycle before the core behavior is stable. Core changes often
rewrite initialization, state, cache, and cleanup. Premature lifecycle detail is
high-churn design debt.

## Final Quality Bar

A new developer should understand what must exist before the core runs, what
changes while it runs, what survives after it stops, and who owns cleanup. They
should not need to invent fields for the major lifecycle records before they can
start implementation.
