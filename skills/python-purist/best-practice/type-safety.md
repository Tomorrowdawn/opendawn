---
title: "Type Safety"
category: best-practice
tags:
  - types
  - mypy
  - pyright
  - typeddict
  - protocol
  - generics
  - msgspec
related:
  - ../case-study/type-black-holes.md
  - ../case-study/serde-schema.md
summary: "Ban Any, dict[str, Any], object, and type: ignore. Enforce strict mypy/pyright. Use type narrowing over cast(). Types are documentation that compiles."
---
# Type Safety

## 原则

**类型模糊是 bug 的温床。** 每一个 `Any`、`object`、`dict[str, Any]` 都在对类型检查器说"我不知道这里是什么"，也在对未来的维护者说"你得自己读代码才能弄明白"。

## 禁止的模糊类型

```python
# ❌ 禁止——模糊类型丢失所有信息
def process(data: dict[str, Any]) -> Any:
    return data.get("result")

# ❌ 禁止——object 意味着"什么都可以"
def handle(payload: object) -> None:
    ...

# ❌ 禁止——Any 传染：一旦出现，整个调用链失去类型安全
from typing import Any
result: Any = get_something()  # result.foo() 不会报类型错误
```

## 精确类型的正确用法

### TypedDict —— 有明确键名的字典

```python
from typing import TypedDict

class CreateUserRequest(TypedDict):
    name: str
    age: int
    email: str | None  # 明确可选的字段用 | None

def create_user(req: CreateUserRequest) -> User:
    ...
```

### Protocol —— 结构化类型（鸭子类型的静态化）

```python
from typing import Protocol

class HasName(Protocol):
    name: str

def greet(entity: HasName) -> str:
    return f"Hello, {entity.name}"  # 任何有 name: str 的对象都接受
```

### 泛型 —— 保留容器内部的类型信息

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Repository(Generic[T]):
    def get(self, id: str) -> T | None: ...
    def list(self) -> list[T]: ...

# 使用时明确类型参数
user_repo: Repository[User] = Repository()
user = user_repo.get("123")  # 类型是 User | None，不是 Any
```

### 用 msgspec / attrs 定义数据结构

```python
# msgspec —— 高性能序列化 + 类型安全
import msgspec

class User(msgspec.Struct):
    name: str
    age: int
    tags: list[str] = []  # 明确 list 内部的类型

# 反序列化自动验证类型
user = msgspec.json.decode(b'{"name":"Alice","age":30}', type=User)
```

```python
# attrs —— 丰富的验证和转换
import attrs

@attrs.define
class User:
    name: str = attrs.field(validator=attrs.validators.instance_of(str))
    age: int = attrs.field(converter=int)

User(name="Bob", age="30")  # age 自动转为 int
```

## 总结

类型系统是你和类型检查器之间的契约。`Any` 意味着你放弃了契约的保护。使用 `TypedDict` 明确字典结构，使用 `Protocol` 表达接口约定，使用泛型保留容器类型信息，使用 `msgspec`/`attrs` 让数据结构自带验证。类型越精确，bug 越少。
