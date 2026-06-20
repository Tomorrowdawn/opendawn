---
title: "对象初始化模式：__init__ 之后立即可用"
category: cookbook
tags:
  - initialization
  - constructor
  - dependency-injection
  - factory
  - classmethod
  - from-config
  - msgspec
  - attrs
  - define
  - builder
  - design-pattern
  - object-creation
related:
  - ../best-practice/struct-vs-define.md
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/fail-fast.md
  - ../case-study/hidden-initialization.md
  - ../case-study/factory-pattern.md
  - ../case-study/dependency-injection.md
summary: "每个类都需要初始化——选对模式：纯数据用 msgspec.Struct、行为类用 @define + DI、配置驱动用 from_config、多来源用 from_*。零 I/O 在 __init__ 里，零二次初始化。"
---

# 对象初始化模式

> **黄金法则：`__init__` 只做字段赋值。对象创建后立即可用。零 I/O，零副作用。**

---

## 决策树

```
这个类会被序列化/反序列化吗（JSON/YAML/MessagePack）？
 │
 ├─ 是 → 纯数据容器 → 模式 1: msgspec.Struct
 │       例：Config schema、API DTO、Domain entity、Event
 │
 └─ 否 → 进程内的行为类
          │
          ├─ 需要外部配置才能创建依赖（DB 连接、API 客户端）？
          │   └─ 是 → 模式 3: @define + from_config
          │
          ├─ 同一个类有多种创建来源（YAML/DB/API）？
          │   └─ 是 → 模式 4: @define + from_* classmethods
          │
          └─ 否 → 依赖直接注入 → 模式 2: @define + DI
                  例：Service、Repository、Policy、Handler
```

---

## 模式 1：纯数据容器 → `msgspec.Struct`

**何时用**：这个类会变成 JSON/YAML/MessagePack 字节流。配置 schema、API 请求/响应、领域实体、事件 DTO。

**怎么做**：声明字段，msgspec 处理一切。不需要写 `__init__`。

```python
import msgspec

# Config schema —— 从 YAML/JSON 反序列化
class DatabaseConfig(msgspec.Struct, frozen=True):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "app"

# API DTO —— FastAPI 自动序列化
class TaskCreateRequest(msgspec.Struct):
    title: str
    description: str = ""

# Domain entity —— 纯数据，在各层之间传递
class Task(msgspec.Struct, frozen=True):
    id: str
    title: str
    status: str = "todo"
```

**规则**：
- `frozen=True` 用于配置和不可变实体（如果可变，则不需要，避免滥用）
- 默认值放在字段声明中
- 不要给 Struct 加行为方法（如需行为，拆为 Struct + `@define` 行为类）
- 用 `msgspec.convert(raw, Type)` 在边界处验证一次

> 详见 `best-practice/struct-vs-define.md`、`case-study/serde-schema.md`

---

## 模式 2：行为类 → `@define` + 依赖注入

**何时用**：有方法、有依赖、有内部状态的服务/客户端/策略/处理器。永远不参与序列化。

**怎么做**：用 `@define` 声明平摊字段。依赖通过构造函数注入，不在 `__init__` 里创建任何东西。

```python
from attrs import define

@define
class UserService:
    """依赖通过构造函数注入——显式、可替换、可检查。"""
    repo: UserRepository
    notifier: Notifier

    async def create_user(self, name: str) -> User:
        user = User(id=generate_id(), name=name)
        await self.repo.insert(user)
        await self.notifier.notify(f"User {user.id} created")
        return user


# --- 组合根（Composition Root）—— 依赖装配的唯一地点 ---
def build_services(db_pool, redis_client) -> UserService:
    repo = UserRepository(pool=db_pool)
    notifier = Notifier(redis=redis_client)
    return UserService(repo=repo, notifier=notifier)


# --- 测试中轻松替换 ---
def test_create_user():
    service = UserService(repo=FakeRepo(), notifier=FakeNotifier())
    user = await service.create_user("Alice")
    assert user.name == "Alice"
```

**规则**：
- `__init__` 零 I/O、零副作用。只做字段赋值（`@define` 自动生成）
- 依赖通过构造参数注入，不在类内部创建
- 集中一个 `build_*` 工厂函数作为组合根
- 测试时传入 Fake/Mock，不需要真实资源

> 详见 `case-study/dependency-injection.md`、`case-study/hidden-initialization.md`

---

## 模式 3：配置驱动 → `@define` + `from_config`

**何时用**：类需要从配置 schema（YAML/JSON → `msgspec.Struct`）创建其内部依赖——如数据库连接池、HTTP 客户端、LLM 客户端。

**核心**：`from_config` 不是简单转发 config 对象，而是**递归创建子对象、组装平摊字段、返回构造好的实例**。

```python
from attrs import define
import msgspec

# ============================================================
# 1. 子组件的 Config schema（msgspec.Struct）
# ============================================================
class DatabaseConfig(msgspec.Struct, frozen=True):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "app"

# ============================================================
# 2. 子组件：平摊字段 + from_config 做真正的创建
# ============================================================
@define
class Database:
    """数据库组件 —— 平摊字段，创建后立即可用。"""
    pool: asyncpg.Pool
    host: str
    port: int

    @classmethod
    async def from_config(cls, config: DatabaseConfig) -> "Database":
        """from_config 做真正的创建工作：读 config、建连接、组装返回。"""
        pool = await asyncpg.create_pool(
            host=config.host, port=config.port,
            user=config.user, password=config.password,
            database=config.database,
        )
        return cls(pool=pool, host=config.host, port=config.port)


# ============================================================
# 3. 顶层 Config：组合所有子 Config（Struct 嵌套 Struct）
# ============================================================
class AppConfig(msgspec.Struct, frozen=True):
    db: DatabaseConfig = DatabaseConfig()
    cache: CacheConfig = CacheConfig()

# ============================================================
# 4. 顶层 App：平摊字段 + 递归组装
# ============================================================
@define
class App:
    db: Database
    cache: CacheManager

    @classmethod
    def from_config(cls, config: AppConfig) -> "App":
        """递归组装：调用每个子组件的 from_config，平摊到自身字段。"""
        return cls(
            db=Database.from_config(config.db),
            cache=CacheManager.from_config(config.cache),
        )

# ============================================================
# 5. 启动代码：一行
# ============================================================
def main():
    raw = yaml.safe_load(Path("config.yaml").read_text())
    config = msgspec.convert(raw, AppConfig)  # 边界处验证一次
    app = App.from_config(config)             # 递归组装
```

**多来源扩展**：新增数据来源 = 新增 `from_*`，不改 `from_config`。

```python
@define
class Database:
    pool: asyncpg.Pool
    host: str
    port: int

    @classmethod
    def from_config(cls, config: DatabaseConfig) -> "Database":
        """唯一真正做创建工作的入口。"""
        ...

    @classmethod
    def from_yaml(cls, path: str) -> "Database":
        """从 YAML 创建 → 先构造 config schema → 委托给 from_config。"""
        raw = yaml.safe_load(Path(path).read_text())
        config = DatabaseConfig(
            host=raw["host"], port=raw["port"],
            user=raw["user"], password=raw.get("password", ""),
            database=raw["database"],
        )
        return cls.from_config(config)  # 委托给统一入口
```

---

## 模式 4：多来源构建 → `from_*` classmethods

**何时用**：同一个类需要从多种来源创建（YAML 文件、数据库行、API 响应），每种来源的数据结构不同。

**怎么做**：一个 `@classmethod` 一个来源。每个只负责"将外部数据转为字段值"，然后委托给 `cls(...)`。

```python
from attrs import define

@define(frozen=True)
class AgentConfig:
    """统一 Schema —— __init__ 只接受明确的字段。"""
    name: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        """YAML 来源的字段映射逻辑。"""
        raw = yaml.safe_load(Path(path).read_text())
        return cls(
            name=raw["name"],
            model=raw.get("model", "gpt-4"),
            temperature=raw.get("temperature", 0.7),
            max_tokens=raw.get("max_tokens", 4096),
        )

    @classmethod
    def from_db_row(cls, row: dict) -> "AgentConfig":
        """DB 来源的字段映射逻辑——字段名可能不同。"""
        return cls(
            name=row["agent_name"],
            model=row.get("llm_model", "gpt-4"),
            temperature=float(row.get("temp", 0.7)),
            max_tokens=row.get("tokens", 4096),
        )

    @classmethod
    def from_api_response(cls, payload: dict) -> "AgentConfig":
        """API 来源的字段映射逻辑——可能嵌套。"""
        agent = payload["agent"]
        return cls(
            name=agent["name"],
            model=agent.get("model_name", "gpt-4"),
            temperature=agent.get("temperature", 0.7),
            max_tokens=payload.get("limits", {}).get("max_tokens", 4096),
        )

# 使用：意图清晰，类型安全
config = AgentConfig.from_yaml("config.yaml")
db_config = AgentConfig.from_db_row({"agent_name": "helper", "llm_model": "claude-3"})
api_config = AgentConfig.from_api_response({"agent": {"name": "bot"}})
```

**规则**：
- `__init__` / `cls(...)` 只做字段赋值，不包含任何解析逻辑
- 每个来源 = 一个独立的 `@classmethod`，互不污染
- 新增来源只增方法，不改现有代码
- 与模式 3 的关系：当数据来源多但都经过 Config schema 统一时，用模式 3（`from_config` 做统一入口）；当各来源格式完全不同、无法/不值得统一时，用模式 4（并存多个 `from_*`）

> 详见 `case-study/factory-pattern.md`（反模式对比）

---

## 反模式速查

| 反模式 | 症状 | 解法 | 详见 |
|--------|------|------|------|
| **`__init__` 中分支** | 根据 `source` 参数在 `__init__` 里 `if/elif` | 模式 4：每个来源一个 `@classmethod` | `case-study/factory-pattern.md` |
| **隐藏初始化** | `__init__` 里读配置、建连接、调 I/O | 模式 2：依赖注入。外部创建依赖，`__init__` 只接收 | `case-study/hidden-initialization.md` |
| **两阶段初始化** | `obj = X(); await obj.setup()` | 模式 3：`from_config` 一次性创建完整对象 | `case-study/hidden-initialization.md` |
| **持有 config 对象** | `self._config = config`，字段不"平摊" | 模式 3：`@define` 平摊字段，`from_config` 拆开 config | 本文模式 3 |
| **全局单例** | `from db import DB` + `assert DB is not None` | 模式 2：构造函数注入 + 组合根 | `case-study/dependency-injection.md` |
| **裸 `class` + `__init__`** | 手写 `self.x = x` | 模式 2/3/4：`@define` | `best-practice/struct-vs-define.md` |
| **Struct 中有行为方法** | `msgspec.Struct` 里有 `def process(self)` | 拆为 Struct（数据）+ `@define`（行为） | `best-practice/struct-vs-define.md` |

---

## 快速参考卡

```
我要写一个类，怎么初始化？

数据容器（会序列化）
  → msgspec.Struct + frozen=True
  → 默认值放字段声明
  → 边界处 msgspec.convert() 验证一次

服务/仓库/策略（有方法、有依赖）
  → @define + 平摊字段
  → 依赖注入，不在 __init__ 里创建任何东西
  → 组合根集中装配

需要配置/启动代码？
  → Config = msgspec.Struct（schema）
  → 组件 = @define + from_config(config)（真正创建）
  → 顶层 = App.from_config(config)（递归组装）

多种数据来源？
  → @define + from_yaml / from_db_row / from_api_response
  → 每个 @classmethod 负责自己的字段映射
  → cls(field1=value, field2=value) 只做赋值
```
