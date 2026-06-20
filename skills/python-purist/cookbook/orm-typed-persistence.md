---
title: "ORM Typed Persistence: 无往返的类型化持久层"
category: cookbook
tags:
  - orm
  - tortoise
  - sqlalchemy
  - persistence
  - crud
  - msgspec
  - type-safety
  - round-trip
related:
  - ../best-practice/trust-your-types.md
  - ../best-practice/serde-boundary.md
  - ../case-study/roundtrip-serialization.md
  - ../case-study/type-black-holes.md
  - ../cookbook/crud-fastapi.md
summary: "如何让 msgspec.Struct 领域模型和 ORM 持久层和平共处——不使用 to_builtins() 往返，不引入无意义的协议层，只在不可信数据边界做一次类型验证。"
---

# ORM Typed Persistence: 无往返的类型化持久层

## 问题

你已经按照 `serde-boundary` 的原则，在系统边界用 `msgspec.Struct` 定义了领域模型。现在你需要把这些模型持久化到数据库。直观的做法是:

```
读: ORM row → dict → msgspec.convert() → Struct
写: Struct → msgspec.to_builtins() → dict → ORM.create()
```

这条链路在一个请求内完成 `Struct → dict → ORM → dict → Struct` 的往返——类型信息被丢弃再重建，`msgspec.convert()` 被当作"dict 变 Struct"的通用工具而非边界验证工具。

**目标**: 让 Struct 和 ORM 模型直接对话，`msgspec.convert()` 只在"不可信数据 → 可信对象"的边界出现一次。

## 核心策略

### 策略 1: 定义显式的领域-持久化映射

不为每个 Struct 字段映射写函数——为每个聚合定义一个映射描述符。

```python
import msgspec
from datetime import datetime
from typing import ClassVar, Any

# ── 领域模型 (msgspec.Struct) ──

class User(msgspec.Struct, frozen=True):
    """用户领域模型 —— 全链路类型安全"""
    id: str
    name: str
    email: str
    role: str = "member"
    created_at: datetime = msgspec.field(default_factory=datetime.now)
    metadata: dict[str, str] = msgspec.field(default_factory=dict)


# ── ORM 模型 (以 Tortoise ORM 为例) ──

from tortoise import Model, fields

class UserModel(Model):
    """用户持久化模型 —— 显式定义，静态类型"""
    id = fields.CharField(pk=True, max_length=36)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    role = fields.CharField(max_length=50, default="member")
    created_at = fields.DatetimeField(auto_now_add=True)
    metadata = fields.JSONField(default=dict)
    
    class Meta:
        table = "users"
    
    # ── 转换方法 —— 直接属性映射，不用 to_builtins ──
    
    def to_domain(self) -> User:
        """ORM row → 领域对象。
        
        这是唯一调用 msgspec.convert 的地方 —— 
        ORM row 是"不可信数据"，需要边界验证。
        """
        return msgspec.convert(
            {
                "id": self.id,
                "name": self.name,
                "email": self.email,
                "role": self.role,
                "created_at": self.created_at,
                "metadata": self.metadata,
            },
            type=User,
        )
    
    @classmethod
    def from_domain(cls, user: User) -> "UserModel":
        """领域对象 → ORM 模型 (内存对象，尚未持久化)。
        
        不使用 to_builtins —— 直接从 Struct 属性映射。
        """
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
            metadata=user.metadata,
        )
```

关键: `to_domain()` 是 `msgspec.convert()` 的**唯一调用点**。`from_domain()` 不使用 `to_builtins()`——它直接从 `user.email` 等属性取值，类型检查器全程有效。

### 策略 2: Repository 薄封装，不做往返

```python
from typing import TypeVar

T = TypeVar("T", bound=msgspec.Struct)
M = TypeVar("M", bound=Model)

class Repository:
    """薄封装 Tortoise ORM —— 不做 Struct ↔ dict 往返。"""
    
    async def get(self, model_type: type[M], domain_type: type[T], pk: str) -> T | None:
        """读取: ORM row → to_domain() → Struct (一次边界验证)"""
        row = await model_type.get_or_none(id=pk)
        if row is None:
            return None
        return row.to_domain()
    
    async def create(self, model_type: type[M], domain: T) -> T:
        """创建: Struct → from_domain() → ORM.create() → to_domain() → Struct"""
        model = model_type.from_domain(domain)
        await model.save()
        return model.to_domain()
    
    async def update(self, model_type: type[M], pk: str, domain: T) -> T:
        """更新: Struct → ORM.update() → get() → to_domain() → Struct"""
        model = model_type.from_domain(domain)
        model.id = pk
        await model.save(update_fields=["name", "email", "role", "metadata"])
        return await self.get(model_type, type(domain), pk)
    
    async def list(self, model_type: type[M], domain_type: type[T], **filters) -> list[T]:
        """列表: ORM.filter() → [to_domain() for row in rows]"""
        rows = await model_type.filter(**filters)
        return [row.to_domain() for row in rows]
```

注意 `create()` 方法里的 `model.to_domain()` 调用: 这是为了获取 ORM 自动生成的字段（如 `created_at`、数据库默认值）。这不是往返——这是"创建后读取"，一次写入 + 一次读取。和之前的 `Struct → to_builtins → dict → ORM.create → ORM.get → dict → msgspec.convert` 相比，这里没有序列化中间步骤。

### 策略 3: 批量操作——用 Struct 字段反射

当你有 20 个字段的 Struct，不想手动写 20 行属性映射时:

```python
from collections.abc import Mapping

def domain_to_orm_kwargs(domain: msgspec.Struct) -> dict[str, Any]:
    """通用 Struct → ORM kwargs 映射。
    
    使用 msgspec.structs.fields() 做字段反射 ——
    不重新发明类型系统，利用库能力。
    """
    kwargs: dict[str, Any] = {}
    for field in msgspec.structs.fields(domain):
        value = getattr(domain, field.encode_name)
        if value is not msgspec.UNSET:
            kwargs[field.encode_name] = value
    return kwargs

class ProductModel(Model):
    # ... 20 个字段 ...
    
    @classmethod
    def from_domain(cls, product: Product) -> "ProductModel":
        return cls(**domain_to_orm_kwargs(product))
    
    def to_domain(self) -> Product:
        return msgspec.convert(
            domain_to_orm_kwargs(self),  # 这里 self 是 Model，也适用
            type=Product,
        )
```

`msgspec.structs.fields()` 返回字段的元信息（名称、类型、默认值、encode_name），不需要 `to_builtins()` 拆了整个 Struct。

### 策略 4: 关联对象——惰性加载替代 to_builtins(recursive=True)

```python
class Order(msgspec.Struct, frozen=True):
    id: str
    user_id: str
    items: list["OrderItem"] = msgspec.field(default_factory=list)

class OrderModel(Model):
    id = fields.CharField(pk=True, max_length=36)
    user = fields.ForeignKeyField("models.UserModel", related_name="orders")
    # items 通过 reverse relation 访问

    async def to_domain(self) -> Order:
        """惰性加载关联 —— 不做 to_builtins(recursive=True)。"""
        items = await self.items.all()  # Tortoise 的 reverse relation
        return Order(
            id=self.id,
            user_id=self.user_id,
            items=[await item.to_domain() for item in items],
        )
```

关键: 不做 `to_builtins(recursive=True)` 的"一次性全部序列化"。每个关联对象有自己的 `to_domain()` 方法，调用者控制加载深度。`to_builtins(recursive=True)` 的问题是一次性触发所有惰性加载,可能导致 N+1 查询爆炸，而且调用者无法控制。

## 反模式对照表

| 反模式 | 表现 | 改正 |
|--------|------|------|
| `to_builtins(struct)` + `orm.create(**dict)` | 写路径拆掉类型 | `Model.from_domain(struct)` 直接属性映射 |
| `dict(cast(Iterable[tuple], row))` | 读路径强制转 dict | `row.to_domain()` 在模型类内显式转换 |
| `msgspec.convert(dict, type=Struct)` 多次出现 | convert 被当作通用工具 | convert 只在 `to_domain()` 内出现一次 |
| `to_builtins(row, recursive=True)` | 递归序列化触发 N+1 | 每个模型自己做 `to_domain()`，调用者控制深度 |
| `getattr(row, "_to_builtins")` 动态方法 | 用字符串访问方法 | 把 `to_domain()` 作为 Model 的显式方法 |
| `protocol.to_builtins(row)` wrapper | 为动态方法建 wrapper | 方法作为 Model 类的成员，不经过中间模块 |

## 集成到现有 crud-fastapi cookbook

本 cookbook 与 `crud-fastapi.md` 的架构兼容。在你的 7 层架构中，持久化层的 `repository/sql.py` 使用本方案替代 `to_orm_fields()` + `from_orm()`:

```python
# repository/sql.py (基于本 cookbook)

class SqlUserRepository:
    async def get(self, user_id: str) -> User | None:
        row = await UserModel.get_or_none(id=user_id)
        return row.to_domain() if row else None
    
    async def create(self, user: User) -> User:
        model = UserModel.from_domain(user)
        await model.save()
        return model.to_domain()
    
    async def update(self, user: User) -> User:
        model = UserModel.from_domain(user)
        model.id = user.id
        await model.save(update_fields=...)
        return model.to_domain()
```

`msgspec.convert` 只出现在 `UserModel.to_domain()` 内部——它是从 ORM 数据到领域对象的边界，调用一次，验证就在那里发生。

## 总结

> `to_builtins()` 和 `msgspec.convert()` 不应该成对出现在同一条调用链上。`msgspec.convert()` 的职责是"不可信数据 → 可信对象"的边界验证——它应该出现在 `row.to_domain()` 方法内，且只出现一次。`to_builtins()` 是为 JSON 序列化设计的——ORM 映射不是 JSON 序列化，Struct 的字段值已经是 ORM 可接受的 Python 原语。

**三句话记住这个 cookbook:**
1. `Model.from_domain(struct)` — 从 Struct 属性直接映射，不用 `to_builtins`
2. `Model.to_domain()` — 一次 `msgspec.convert`，唯一的边界验证点
3. 字段反射用 `msgspec.structs.fields()` — 利用库能力，不重新发明类型系统
