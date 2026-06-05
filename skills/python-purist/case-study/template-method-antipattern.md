---
title: "Template Method Anti-Pattern: When Base Classes Control Flow"
category: case-study
tags:
  - template-method
  - abc
  - inheritance
  - anti-pattern
  - decorator
related:
  - ../best-practice/composition-over-inheritance.md
summary: "Base class defines the algorithm skeleton, subclass fills in the blanks — replaces with decorator wrapping for testability, clarity, and loose coupling."
---

# Template Method Anti-Pattern: When Base Classes Control Flow

## 场景

你需要一个数据仓储，支持多种存储后端（Postgres、内存字典、文件）。所有实现都要附加一个"追踪已操作对象"的能力——把每个 `add` 或 `get` 拿到的对象记录到 `seen` 集合中。

## 坏代码：模板方法 + ABC 混合继承

```python
import abc

class AbstractRepository(abc.ABC):
    """基类既定义接口又共享代码——三种继承类型混在一起。"""
    seen: set[Product]

    def __init__(self) -> None:
        self.seen: set[Product] = set()

    # 公共 API——控制流在基类
    def add_product(self, product: Product) -> None:
        self._add_product(product)       # ← 调子类方法
        self.seen.add(product)           # ← 基类逻辑

    def get_by_sku(self, sku: str) -> Product | None:
        product = self._get_by_sku(sku)  # ← 调子类方法
        if product:
            self.seen.add(product)       # ← 基类逻辑
        return product

    # 子类填空
    @abc.abstractmethod
    def _add_product(self, product: Product): ...

    @abc.abstractmethod
    def _get_by_sku(self, sku: str) -> Product | None: ...


class PostgresRepository(AbstractRepository):
    """子类实现——控制流在子类和基类之间来回跳跃。"""

    def _add_product(self, product: Product) -> None:
        self._conn.execute("INSERT INTO products ...")

    def _get_by_sku(self, sku: str) -> Product | None:
        return self._conn.execute("SELECT ... WHERE sku = ?", sku).fetchone()
```

## 为什么坏

1. **三种继承类型混在一起**：ABC 既定义 `add_product` / `get_by_sku` 的接口契约（类型 2），又通过模板方法共享 `seen` 追踪逻辑（类型 1）。这是继承混乱的元凶。

2. **控制流上下跳跃**：用户调用 `repo.add_product(p)` → 基类 `AbstractRepository.add_product` → 子类 `PostgresRepository._add_product` → 回到基类 `self.seen.add(p)`。阅读者需要在基类和所有子类之间来回跳转才能理解完整行为。

3. **公共 API 在基类不在子类**：用户实例化 `PostgresRepository`，但它的公共方法 `add_product` 定义在 `AbstractRepository` 中。文档工具往往只展示子类的直接方法，用户需要点进父类才能看到可用 API。

4. **隐式契约**：子类必须实现 `_add_product` 和 `_get_by_sku`——但方法名拼错一个字母会导致静默失败，基类找不到时可能什么都不调用或者报错信息极其隐晦。

5. **不可组合**：如果只需要追踪 `add` 而不追踪 `get`，或者想对部分仓储加缓存、部分不加，模板方法完全无法应对——你只能再创建一个新的基类。

## 好代码：Protocol + 装饰器模式

```python
from typing import Protocol, runtime_checkable

# --- 第一步：定义纯粹的接口协议（类型 2）---
@runtime_checkable
class Repository(Protocol):
    def add_product(self, product: Product) -> None: ...
    def get_by_sku(self, sku: str) -> Product | None: ...


# --- 第二步：独立的后端实现——只知道自己的存储逻辑 ---
class PostgresRepository:
    def __init__(self, conn) -> None:
        self._conn = conn

    def add_product(self, product: Product) -> None:
        self._conn.execute("INSERT INTO products ...")

    def get_by_sku(self, sku: str) -> Product | None:
        return self._conn.execute("SELECT ... WHERE sku = ?", sku).fetchone()


class DictRepository:
    def __init__(self) -> None:
        self._storage: dict[str, Product] = {}

    def add_product(self, product: Product) -> None:
        self._storage[product.sku] = product

    def get_by_sku(self, sku: str) -> Product | None:
        return self._storage.get(sku)


# --- 第三步：追踪能力作为独立的装饰器层 ---
class TrackingRepository:
    """包装任意 Repository，添加 seen 追踪——纯组合，零继承。"""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self.seen: set[Product] = set()

    def add_product(self, product: Product) -> None:
        self._repo.add_product(product)
        self.seen.add(product)

    def get_by_sku(self, sku: str) -> Product | None:
        product = self._repo.get_by_sku(sku)
        if product:
            self.seen.add(product)
        return product


# --- 使用：装饰器链自由组合 ---

# 生产环境：Postgres + 追踪
repo = TrackingRepository(PostgresRepository(conn))

# 测试环境：内存 + 追踪
test_repo = TrackingRepository(DictRepository())

# 不带追踪的纯粹存储——也可以直接使用
bare_repo = DictRepository()
```

## 为什么好 / 关键差异

| 对比维度 | 模板方法 | 装饰器模式 |
|---------|---------|-----------|
| **职责分离** | 基类同时管契约和追踪逻辑 | Repository 只管存储，TrackingRepository 只管追踪 |
| **控制流** | 基类 ↔ 子类 来回跳跃 | 单向：`TrackingRepository → inner._repo` |
| **API 归属** | 公共 API 在基类，远离使用者 | 每个类的 API 都在自己身上，无继承查找 |
| **可组合性** | 零——焊死 | 任意层级嵌套：`Cached(Tracked(Logged(Postgres())))`  |
| **测试** | 需实例化完整子类才能测试追踪 | 注入 mock Repository 即可独立测试 TrackingRepository |
| **契约约束** | `@abc.abstractmethod` | Protocol 结构子类型——实现者无需继承 |

核心技术洞察（Hynek Schlawack）：**模板方法其实不过是用继承语法写了装饰器模式——只是命名空间混在一起、控制流混淆了。把它还原成独立的包装类即可。**

## 决策路径

```
你有一个基础行为 + 所有变体都需要的前置/后置逻辑？

├─ 用模板方法继承 → ❌ 三种继承类型混杂，控制流跳跃
└─ 用装饰器包装类 → ✅ 单向调用，职责独立，可自由组合
```

> 核心教训：如果基类的公共方法调用了子类实现的方法——不是在 specialization 层（类型 3），而是在代码共享层（类型 1）——这就是模板方法反模式。用装饰器包装替代。
