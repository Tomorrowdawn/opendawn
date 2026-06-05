---
title: "Hidden Initialization: Two-Phase Init is an Anti-Pattern"
category: case-study
tags:
  - initialization
  - two-phase-init
  - constructor
  - fail-fast
related:
  - ../best-practice/fail-fast.md
  - ../best-practice/composition-over-inheritance.md
summary: "obj = MyClass() then obj.setup() — an object must be ready to use after __init__. Two-phase init hides dependencies and creates invalid intermediate states."
---

# Hidden Initialization: Two-Phase Init is an Anti-Pattern

## 场景

你有一个 `UserRepository` 类，需要通过数据库连接池执行查询。数据库地址和凭据来自配置文件。

## 坏代码：在 `__init__` 中创建一切

```python
import asyncpg
from yuubot.bootstrap.config import load_config

class UserRepository:
    def __init__(self):
        # 在构造器中读取配置、创建连接池
        self._config = load_config()  # 隐式 I/O
        self._pool = await self._create_pool()  # __init__ 不能是 async...

    async def _create_pool(self) -> asyncpg.Pool:
        return await asyncpg.create_pool(
            host=self._config.database.host,
            port=self._config.database.port,
            user=self._config.database.user,
            password=self._config.database.password,
            database=self._config.database.name,
        )

    async def get_by_id(self, user_id: str) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1", user_id
            )
            return dict(row) if row else None

# 使用
repo = UserRepository()
user = await repo.get_by_id("42")
```

## 为什么坏

1. **隐式副作用**：`UserRepository()` 的构造看起来是"创建对象"，实际却在做文件 I/O（读配置）和网络 I/O（连数据库）。构造一个对象可能失败，但构造函数没有返回错误的标准方式（`__init__` 返回 `None`）。
2. **async 构造器不可能**：`__init__` 不能是 `async def`，所以要么用同步阻塞（卡住事件循环），要么用 `await` + `__init__` 的变通方案（`await repo._create_pool()`），极其别扭且容易被忘记。
3. **测试被真实依赖绑架**：单元测试 `UserRepository.get_by_id()` 时，每次实例化都必须连接真实的 PostgreSQL。没有数据库 → 测试无法运行；测试数据隔离 → 需要额外清理逻辑；CI 环境 → 需要启动数据库容器。
4. **配置来源焊死**：`load_config()` 硬编码在构造器中，如果你想传入内存中的配置字典（测试场景），改不了。
5. **生命周期不可控**：连接池在对象创建时打开，但何时关闭？需要额外的 `close()` 方法，调用者未必记得调用。

## 好代码：依赖注入

```python
from dataclasses import dataclass
from typing import Protocol

class Pool(Protocol):
    """连接池协议 —— 生产和测试各有一套实现"""
    async def acquire(self) -> "Connection": ...
    async def close(self) -> None: ...

class Connection(Protocol):
    async def fetchrow(self, query: str, *args) -> "Row | None": ...
    async def execute(self, query: str, *args) -> str: ...

@dataclass
class UserRepository:
    pool: Pool  # 注入，不创建

    async def get_by_id(self, user_id: str) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1", user_id
            )
            return dict(row) if row else None

# 生产环境：组装
pool = await asyncpg.create_pool(dsn="postgresql://...")
repo = UserRepository(pool=pool)
user = await repo.get_by_id("42")

# 测试环境：传入 fake pool
class FakePool:
    def __init__(self, rows: list[dict]):
        self._conn = FakeConnection(rows)
    async def acquire(self):
        return self._conn
    async def close(self):
        pass

fake_pool = FakePool(rows=[{"id": "42", "name": "Alice"}])
test_repo = UserRepository(pool=fake_pool)
user = await test_repo.get_by_id("42")  # → {"id": "42", "name": "Alice"}
```

## 为什么好 / 关键差异

- **构造 = 赋值**：`__init__` 只做字段赋值，零 I/O，零副作用。对象构造永远不会失败（除非传入类型错误）。
- **测试完全隔离**：测试中传入 `FakePool`，不需要真实数据库、不需要 Docker、不需要网络。测试高速、可重复、无副作用。
- **配置来源解耦**：`pool` 由外部组装层创建（工厂函数、DI 容器、`main()` 函数），`UserRepository` 不关心它是怎么来的。
- **生命周期清晰**：`pool` 的创建和销毁由调用方控制，`UserRepository` 不负责也不应该负责。
- **显式契约**：`Pool` / `Connection` 协议定义了 `UserRepository` 真实依赖的最小接口，调用方和被调用方的契约一目了然。

> 核心原则：对象只应通过构造器接收其依赖，永远不要在构造器中创建依赖。
