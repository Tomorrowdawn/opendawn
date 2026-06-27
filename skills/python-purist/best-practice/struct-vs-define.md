---
title: "Struct vs Define: 数据类与行为类的分界线"
category: best-practice
tags:
  - msgspec
  - attrs
  - define
  - struct
  - serialization
  - serde
  - data-class
  - behavioral-class
  - class-design
  - mutability
  - frozen
related:
  - serde-boundary.md
  - composition-over-inheritance.md
  - ../case-study/serde-schema.md
  - ../case-study/factory-pattern.md
  - ../case-study/frozen-overuse.md
summary: "msgspec.Struct 用于跨序列化边界的数据容器；@define 用于进程内的行为类。自然的区分线：这个类会出现在序列化/反序列化场景中吗？是 → Struct，否 → @define。"
---

# Struct vs Define

## 原则

> **是否出现在序列化/反序列化场景中——这是唯一的分界线。**
>
> - `msgspec.Struct`：数据容器。会变成 JSON / YAML / MessagePack 字节流。出现在 API 边界、配置文件、消息队列、数据库行映射。
> - `@define`：行为类。有方法、有注入的依赖、有内部状态。永远停留在进程内存中，不会被序列化。
> - 禁止：`@define`、裸 `class` + `__init__`、pydantic `BaseModel`。

> **不要机械使用 `frozen=True`。** `frozen` 是运行时约束，不是“代码里约定不要改”的文档标记。只有当对象在整个生命周期中真的不能被原地更新，或需要满足 hash / 共享并发 / 跨线程跨进程消息的不可变契约时，才冻结。

## 快速决策

```
这个类会变成 JSON 吗？
 │
 ├─ 是 → msgspec.Struct（纯数据，无行为）
 │       例：API Request/Response、Config schema、Domain entity、Event DTO
 │
 └─ 否 → @define（有行为，有依赖）
         例：Service、Repository、Client、Policy、Handler、Orchestrator
```

## `msgspec.Struct` — 数据容器

用于任何需要被序列化/反序列化的数据。定义在边界处，通过 `msgspec.convert()` 验证一次后，内部链路传递强类型对象。

```python
import msgspec

# ✅ Config schema —— 从 YAML/JSON 反序列化
class DatabaseConfig(msgspec.Struct, frozen=True):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""

# ✅ API DTO —— FastAPI 自动序列化
class TaskCreateRequest(msgspec.Struct):
    title: str
    description: str = ""

# ✅ Domain entity —— 纯数据，可在各层之间传递
class Task(msgspec.Struct):
    id: str
    title: str
    status: str = "todo"
```

**Struct 不包含行为方法**（除了可能的 `@classmethod` 工厂如 `from_config`）。如果你发现自己给 Struct 加 `def process(self)`，说明这个类应该拆分为 Struct + `@define` 行为类。

## `frozen=True` — 真实冻结，不是概念冻结

`frozen=True` 的含义是：这个对象创建后不允许字段赋值。它会改变更新方式、hash 行为、测试写法和 API ergonomics。因此它必须来自真实约束，而不是来自“看起来更纯”“防止别人误改”。

**可以冻结：**
- 配置对象：启动时加载，之后不应被任何业务路径修改。
- 值对象 / hash key：对象会进入 `dict` key、`set`、cache key，参与 hash 的字段必须终身不变。
- 已完成事件 / 消息：发布后被多个消费者读取，不能被生产者或消费者原地改写。
- 分布式系统里的快照：冻结用来避免共享引用上的竞态或 TOCTOU 问题。

**不要冻结：**
- 需要被业务流程更新的实体，例如 task status、session state、order lifecycle。
- 聚合根或工作集，尤其是内部有 `list` / `dict` / `set` 的结构。
- append-only 结构。append-only 的意思是“只能追加，不能改历史”，不是“整个容器不能变”。
- 只是为了表达“这里不该乱改”的字段。那是 API 设计、封装、命名和测试的职责，不是 `frozen=True` 的职责。

**不要为了冻结把 `list` 强行改成 `tuple`。** 如果领域操作是追加、删除、重排或批量更新，保留可变容器并把修改集中在明确的方法或函数里。把 list 变成 tuple 只会把一次清晰的更新变成到处 `replace(x, items=(*x.items, item))` 的噪音。

```python
# ✅ append-only history：历史记录不可改，但集合本身允许追加
class Conversation(msgspec.Struct):
    id: str
    messages: list[Message]

def append_message(conversation: Conversation, message: Message) -> None:
    conversation.messages.append(message)


# ✅ 真正不可变的发布事件：构造完成后只读
class MessagePublished(msgspec.Struct, frozen=True):
    conversation_id: str
    message_id: str
    created_at: str
```

如果用户说“这个结构是 frozen / immutable”，先判断他说的是哪一种：

| 用户意图 | 代码表达 |
|----------|----------|
| “运行时绝不能更新，避免 hash/并发/共享消息问题” | `frozen=True`，内部字段也选不可变类型 |
| “不要修改历史记录，只能追加” | 可变容器 + append-only API + 测试 |
| “调用方不应该碰内部细节” | 封装在行为类里，不暴露可变字段 |
| “这个配置加载后不许变” | `frozen=True` config schema |
| “这里是约定，不要乱改” | 命名、模块边界、文档注释、测试，不是机械冻结 |

## `@define` — 行为类

用于有行为的对象：服务、客户端、策略、处理器、编排者。有注入的依赖、有方法、有内部状态。

```python
from attrs import define, field

# ✅ 服务类 —— 注入依赖，有业务方法
@define
class TaskService:
    repo: TaskRepository
    notifier: Notifier

    async def create_task(self, request: TaskCreateRequest) -> Task:
        task = Task(id=generate_id(), title=request.title)
        await self.repo.insert(task)
        await self.notifier.notify(f"Task {task.id} created")
        return task

# ✅ 策略类 —— 注入配置，有执行方法
@define
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 1.0

    async def execute(self, fn):
        for attempt in range(self.max_retries):
            try:
                return await fn()
            except Exception:
                await asyncio.sleep(self.base_delay * (2 ** attempt))
        raise

# ✅ 编排者 —— 组合子组件，自身无实现细节
@define
class DataFetcher:
    http: HttpClient
    cache: CacheManager
    retry: RetryPolicy
    parser: ResponseParser

    async def fetch(self, path: str) -> dict:
        cached = self.cache.get(path)
        if cached is not None:
            return self.parser.parse(cached)
        raw = await self.retry.execute(lambda: self.http.get(path))
        result = self.parser.parse(raw)
        self.cache.set(path, raw)
        return result
```

**`@define` 类永远不参与序列化。** 你不会 `msgspec.convert(response, Service)`，也不会在 FastAPI 路由中返回一个 `@define` 实例。

## 边界类：Config 对象的双层结构

配置类天然处于边界——它从 YAML/JSON 反序列化而来。Struct（数据 schema）和 `@define`（行为组件）之间通过 `from_config` 桥接。

> **完整方案见 `cookbook/initialization-patterns.md`**（模式 3：配置驱动 → `@define` + `from_config` 递归组装）。
>
> 核心：`AppConfig`（msgspec.Struct）在 YAML/JSON 和 Python 之间转换；`App`（@define）活在进程内存中，组合行为组件；`from_config` 是桥接点。

## 为什么不用 `@dataclass`

不用。用 `@define`。

## 为什么废弃裸 `class` + `__init__`

手写 `__init__(self, x: int, y: str)` 没有任何工具能生成它的价值——类型检查器不会自动推导参数顺序，IDE 补全也不如 `@define` 生成的 `__init__` 精确。更重要的是：

1. **重复劳动**：`self.x = x` 写十遍不产生任何信息增益。`@define` 从类型注解自动生成。
2. **不一致的默认值处理**：`def __init__(self, x: int = 0)` vs `x: int = field(default=0)`——前者是 CPython 约定，后者是 attrs 语义，混用导致混乱。
3. **无 `__attrs_post_init__` hook**：裸 `__init__` 中放了大量初始化逻辑（读文件、建连接、调 I/O），违反 fail-fast 原则。`@define` + `from_config` 强制将创建逻辑移到工厂方法中。

```python
# ❌ 手写 __init__ —— 无价值重复
class HttpClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

# ✅ @define —— 等价且更短
@define
class HttpClient:
    base_url: str
    timeout: int = 30
```

## 违规信号

以下信号说明你应该切换到 `msgspec.Struct` 或 `@define`：

| 你写了... | 应该用... | 原因 |
|-----------|----------|------|
| `@define` | `@define`（行为类）或 `msgspec.Struct`（数据类） | 废弃；见上文三种缺陷 |
| `class X: def __init__(self, ...)` | `@define` | 无价值重复，无 hook |
| `class X(BaseModel)` | `msgspec.Struct` | pydantic 不是本技能推荐的序列化方案 |
| Struct 中有 `def process(self)` 方法 | 拆为 Struct + `@define` | Struct 是纯数据容器 |
| `json.dumps(service_instance)` | 不应该发生 | 行为类不应参与序列化 |
| 为了 `frozen=True` 把业务列表改成 tuple | 保留 list，集中更新 API | 这是概念冻结误写成运行时冻结 |

## 相关文档

- `best-practice/serde-boundary.md` — 序列化边界的位置和设计
- `best-practice/composition-over-inheritance.md` — `@define` 组合子组件的理论基础
- `case-study/serde-schema.md` — `msgspec.Struct` 的完整用法
- `case-study/factory-pattern.md` — `@classmethod` 工厂 + Config schema 创建 `@define` 实例
- `case-study/frozen-overuse.md` — 区分概念冻结和运行时冻结
