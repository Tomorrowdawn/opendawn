---
title: "Repository Pattern: Decoupling Data Access"
category: case-study
tags:
  - repository
  - data-access
  - abstraction
  - storage
  - decoupling
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/serde-boundary.md
summary: "Unified data access abstraction — business logic depends on a Repository Protocol, never on a specific database, file system, or API."
---

# Repository Pattern: Decoupling Data Access

## 场景

用户管理涉及 10 个业务 Service（`AuthService`、`ProfileService`、`NotificationService` 等），每个都直接写 ORM 查询——`User.filter(name=name).first()`、`User.filter(status="active").all()`。数据访问逻辑散布在多个文件中，迁移 ORM 或调整查询策略时需要修改所有文件。

## 坏代码

```python
# auth_service.py
from tortoise.models import Model


class User(Model):
    id: int
    name: str
    email: str
    status: str
    created_at: str


class AuthService:
    async def authenticate(self, name: str, password: str) -> User | None:
        user = await User.filter(name=name, status="active").first()
        if user is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


# profile_service.py —— 同样的查询模式散布在另一个文件
class ProfileService:
    async def get_profile(self, user_id: int) -> dict | None:
        user = await User.filter(id=user_id, status="active").first()
        if user is None:
            return None
        return {"name": user.name, "email": user.email}

    async def search_by_name(self, keyword: str) -> list[User]:
        return await User.filter(name__icontains=keyword, status="active").all()


# notification_service.py —— 又一个文件，又一次重复
class NotificationService:
    async def notify_active_users(self, message: str) -> int:
        users = await User.filter(status="active").all()
        count = 0
        for user in users:
            await send_notification(user.id, message)
            count += 1
        return count
```

## 为什么坏

1. **数据访问逻辑重复**：`User.filter(status="active").first()` 在 10 个文件中出现——如果"活跃用户"的判断条件增加 `AND deleted_at IS NULL`，需要修改 10 处。
2. **业务层与持久层耦合**：`AuthService` 直接依赖 Tortoise ORM 的 `filter().first()` 语法。迁移到 SQLAlchemy 或原生 SQL 需要重写所有 Service。
3. **无法统一缓存/日志**：想在"查询用户"时统一记录慢查询日志或添加缓存层，没有单一的插入点——需要侵入每个 Service。
4. **测试需真实数据库**：测试 `AuthService.authenticate` 必须启动真实数据库并插入测试数据，因为 ORM 调用是硬编码的。无法用内存字典替代。

## 好代码

```python
from __future__ import annotations

from typing import Protocol


class UserRepository(Protocol):
    """用户仓储协议——定义数据访问接口，隔离业务层与持久层。"""

    async def find_by_id(self, user_id: int) -> User | None: ...
    async def find_by_name(self, name: str) -> User | None: ...
    async def find_active_by_name(self, name: str) -> User | None: ...
    async def find_all_active(self) -> list[User]: ...
    async def search_by_name(self, keyword: str) -> list[User]: ...
    async def insert(self, user: User) -> User: ...
    async def update(self, user: User) -> None: ...
    async def delete(self, user_id: int) -> None: ...


class TortoiseUserRepository:
    """Tortoise ORM 实现——所有查询细节集中在此，对外不可见。"""

    async def find_by_id(self, user_id: int) -> User | None:
        return await User.filter(id=user_id).first()

    async def find_by_name(self, name: str) -> User | None:
        return await User.filter(name=name).first()

    async def find_active_by_name(self, name: str) -> User | None:
        return await User.filter(name=name, status="active").first()

    async def find_all_active(self) -> list[User]:
        return await User.filter(status="active").all()

    async def search_by_name(self, keyword: str) -> list[User]:
        return await User.filter(name__icontains=keyword, status="active").all()

    async def insert(self, user: User) -> User:
        await user.save()
        return user

    async def update(self, user: User) -> None:
        await user.save()

    async def delete(self, user_id: int) -> None:
        await User.filter(id=user_id).delete()


# --- 业务层依赖协议而非实现 ---

class AuthService:
    """只依赖 UserRepository 协议——不知道背后是 Tortoise 还是内存字典。"""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def authenticate(self, name: str, password: str) -> User | None:
        user = await self._users.find_active_by_name(name)
        if user is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


class ProfileService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def get_profile(self, user_id: int) -> dict | None:
        user = await self._users.find_by_id(user_id)
        if user is None or user.status != "active":
            return None
        return {"name": user.name, "email": user.email}

    async def search_by_name(self, keyword: str) -> list[User]:
        return await self._users.search_by_name(keyword)


# --- 测试：内存仓储轻松替换 ---
class InMemoryUserRepository:
    """测试替身——无需数据库，纯内存操作。"""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    async def find_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    async def find_active_by_name(self, name: str) -> User | None:
        for user in self._users.values():
            if user.name == name and user.status == "active":
                return user
        return None

    async def find_all_active(self) -> list[User]:
        return [u for u in self._users.values() if u.status == "active"]

    async def search_by_name(self, keyword: str) -> list[User]:
        return [u for u in self._users.values()
                if keyword.lower() in u.name.lower() and u.status == "active"]

    async def insert(self, user: User) -> User:
        self._users[user.id] = user
        return user

    async def update(self, user: User) -> None:
        self._users[user.id] = user

    async def delete(self, user_id: int) -> None:
        self._users.pop(user_id, None)


async def test_authenticate_active_user() -> None:
    repo = InMemoryUserRepository()
    user = User(id=1, name="alice", status="active", hashed_password="hash_xxx")
    await repo.insert(user)

    auth = AuthService(users=repo)
    result = await auth.authenticate("alice", "correct_password")
    assert result is not None
```

## 为什么好 / 关键差异

1. **单一修改点**："活跃用户"的定义改变时，只需改 `TortoiseUserRepository` 中的查询方法——10 个 Service 无需任何修改。
2. **持久层与技术栈解耦**：业务层只依赖 `UserRepository` 协议——从 Tortoise 迁移到 SQLAlchemy 只需新建一个 `SqlAlchemyUserRepository` 实现同一协议，业务代码零修改。
3. **横切关注点天然插入**：在 `UserRepository` 协议和 `TortoiseUserRepository` 之间可以插入装饰器仓储——`CachedUserRepository` 包装 `TortoiseUserRepository`，添加 `@timed` 慢查询日志——所有 Service 自动获益。
4. **测试速度质变**：`InMemoryUserRepository` 纯内存操作，测试从 200ms（启动数据库）降到 0.5ms，且完全隔离、可并行运行。
