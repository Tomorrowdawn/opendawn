---
title: "Dependency Injection: Testable by Default"
category: case-study
tags:
  - dependency-injection
  - runtime-resources
  - testing
  - composition
  - factory
  - decoupling
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/fail-fast.md
  - runtime-resources.md
summary: "Eliminating hardcoded factory calls inside modules — every layer becomes independently testable, swappable, and explicit about its dependencies."
---

# Dependency Injection: Testable by Default

## 场景

系统需要一个数据库连接池，多个 `Service` 类（`UserService`、`OrderService`、`ProductService`）都需要查询数据库。常见做法是在模块顶层创建全局单例 `DB`，各处通过 `from app import DB` 引用。

## 坏代码

```python
# db.py
import asyncpg

DB: asyncpg.Pool | None = None


async def init_db(dsn: str) -> None:
    global DB
    DB = await asyncpg.create_pool(dsn)


# user_service.py
from db import DB  # 隐式全局依赖


class UserService:
    async def find_by_id(self, user_id: int) -> dict | None:
        assert DB is not None  # 运行时防御，编译器无法检查
        async with DB.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
            return dict(row) if row else None


# order_service.py
from db import DB  # 同样的 import 散布在 10+ 个文件中


class OrderService:
    async def list_by_user(self, user_id: int) -> list[dict]:
        assert DB is not None
        async with DB.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM orders WHERE user_id=$1", user_id)
            return [dict(r) for r in rows]


# main.py —— 必须按精确顺序初始化
import asyncio
from db import init_db
from user_service import UserService
from order_service import OrderService

async def main():
    await init_db("postgresql://...")  # 必须在 import Service 之后、调用之前
    user_svc = UserService()
    order_svc = OrderService()
    ...
```

## 为什么坏

1. **无法测试替换**：单元测试时无法将真实 PostgreSQL 连接池替换为内存 SQLite 或 mock——必须 patch 全局变量或启动真实数据库。
2. **隐式依赖**：阅读 `UserService.find_by_id` 时看不到它依赖数据库——必须钻入方法体发现 `from db import DB`，破坏了局部推理能力。
3. **启动顺序耦合**：`init_db` 必须在所有 `Service` 调用之前执行，但编译器无法验证这一时序——只能靠运行时 `assert DB is not None` 来防御。
4. **全局可变状态**：任何模块都可以在运行时 `DB = None` 或替换为另一个 pool，排查问题极为困难。

## 好代码

```python
from __future__ import annotations

import asyncpg


class UserService:
    """依赖通过构造函数注入——显式、可替换、可检查。"""

    def __init__(self, db: asyncpg.Pool) -> None:
        self._db = db

    async def find_by_id(self, user_id: int) -> dict | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
            return dict(row) if row else None


class OrderService:
    def __init__(self, db: asyncpg.Pool) -> None:
        self._db = db

    async def list_by_user(self, user_id: int) -> list[dict]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM orders WHERE user_id=$1", user_id)
            return [dict(r) for r in rows]


# --- 组合根（Composition Root）——依赖装配的唯一地点 ---
async def build_services(dsn: str) -> tuple[UserService, OrderService]:
    """所有依赖的创建和注入集中在此——main 函数调用一次。"""
    pool = await asyncpg.create_pool(dsn)
    try:
        return UserService(pool), OrderService(pool)
    except Exception:
        await pool.close()
        raise


# --- 测试中轻松替换 ---
class FakePool:
    """测试替身——实现 asyncpg.Pool 的必要接口。"""
    async def acquire(self):
        return FakeConnection()


async def test_find_by_id() -> None:
    service = UserService(db=FakePool())
    result = await service.find_by_id(1)
    assert result is not None
```

## 为什么好 / 关键差异

1. **显式依赖**：`UserService.__init__` 的签名明确宣告"我需要一个 `asyncpg.Pool`"——IDE 和类型检查器可以验证调用者是否正确传递了参数。
2. **测试零摩擦**：不需要 patch 全局变量或启动数据库，直接传入 `FakePool`，测试变成纯内存操作——快且隔离。
3. **生命周期清晰**：`build_services` 作为唯一创建点，`Service` 不需要知道 pool 从何而来。关闭 `pool` 的时机也集中在一处，不会出现"忘记关闭全局连接"的问题。
4. **面向接口而非实现**：进一步改进时可将 `asyncpg.Pool` 替换为 `PoolProtocol`，彻底解耦数据库实现——但这是第二步优化；构造函数注入本身就是迈向可测试性的第一步，也是最重要的一步。
