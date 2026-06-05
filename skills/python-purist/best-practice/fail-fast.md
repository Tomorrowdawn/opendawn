---
title: "Fail Fast: Validate at Boundaries, Crash at Entry"
category: best-practice
tags:
  - validation
  - error-handling
  - defensive-programming
  - boundary
  - exception
related:
  - ../case-study/hidden-initialization.md
  - ../case-study/exception-swallowing.md
  - ../case-study/try-catch-overuse.md
summary: "Validate at system boundaries, crash immediately on bad data. Never let invalid state propagate deep into the system."
---

# Fail Fast: Validate at Boundaries, Crash at Entry

## 原则

**在边界处验证，在入口处崩溃。** 输入验证必须在数据进入系统的第一道边界完成——`__init__`、函数入口、反序列化时。不要将错误状态传播到系统深处，让问题在最早的时刻暴露。

## 核心理念

错误越早暴露，调试成本越低。一个在 `__init__` 中抛出的 `ValueError`，其堆栈跟踪清晰指向调用者；而一个在深层嵌套逻辑中因 `None` 值引发的 `AttributeError`，可能需要数小时定位。

## 边界验证

数据进入系统的边界包括：

1. **构造器** —— `__init__` 中验证所有参数
2. **函数入口** —— 函数体的前三行完成参数校验
3. **反序列化** —— JSON/配置/API 响应解析后立即验证

```python
from dataclasses import dataclass

@dataclass
class User:
    name: str
    age: int

    def __post_init__(self) -> None:
        # 边界验证：构造完成即刻检查
        assert isinstance(self.name, str), "name must be str"
        assert len(self.name) > 0, "name must not be empty"
        assert 0 < self.age < 150, f"age {self.age} out of range"
```

## assert vs 显式 raise

- **`assert`**：用于"绝不应该发生"的条件，表示程序员的假设。适合内部一致性检查。
- **显式 `raise`**：用于可预期的输入错误，向调用者传递明确的错误信息。

```python
def create_user(data: dict) -> User:
    # 函数入口边界验证
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, got {type(data)}")

    name = data.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a string")

    age = data.get("age")
    if not isinstance(age, int) or age <= 0:
        raise ValueError(f"Invalid age: {age}")

    return User(name=name, age=age)
```

## 禁止的行为

```python
# ❌ 吞掉异常——错误被静默隐藏
try:
    user = create_user(data)
except ValueError:
    user = None  # 调用者不知道发生了什么

# ❌ 返回错误码——强迫每个调用者检查
def create_user(data: dict) -> tuple[User | None, str | None]:
    ...

# ✅ 让异常传播——调用者决定如何处理
def create_user(data: dict) -> User:
    ...
```

## 总结

快速失败不是粗暴，而是精确。在数据进入系统的第一时间验证它，用清晰的异常类型传达问题，让调用者承担处理异常的责任。吞掉异常只会让 bug 在系统中潜伏，最终以更隐蔽的方式爆发。
