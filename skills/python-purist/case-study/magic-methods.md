---
title: "Magic Method Traps: __getattr__ / __setattr__"
category: case-study
tags:
  - magic-methods
  - getattr
  - setattr
  - implicit
  - debugging
related:
  - ../best-practice/explicit-over-implicit.md
summary: "__getattr__/__setattr__ hiding DB queries, network calls, or state mutations behind innocent attribute access — code becomes unpredictable."
---

# Magic Method Traps: __getattr__ / __setattr__

## 场景

你有一个用户配置类 `UserSettings`，希望通过属性访问时自动做日志记录和类型转换。比如访问 `settings.theme` 时，自动将底层存储的值转换为枚举，同时记录访问日志。

## 坏代码

```python
class UserSettings:
    _storage: dict[str, str] = {}

    def __getattr__(self, name: str):
        """拦截所有属性访问做日志+转换"""
        if name.startswith("_"):
            raise AttributeError(name)
        raw = self._storage.get(name)
        if raw is None:
            raise AttributeError(f"no setting: {name}")
        print(f"[LOG] get {name} = {raw}")
        return int(raw) if raw.isdigit() else raw

    def __setattr__(self, name: str, value: object):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        print(f"[LOG] set {name} = {value}")
        self._storage[name] = str(value)

settings = UserSettings()
settings.theme = "dark"   # → _storage["theme"] = "dark"
settings.count = "42"     # → _storage["count"] = "42"
print(settings.theme)     # → "dark"
print(settings.count + 1) # TypeError: can't add int to str — 吞了转换？
```

## 为什么坏

1. **IDE 完全失明**：`__getattr__` 使得任意属性名都合法，IDE 无法推断 `settings.theme` 的类型，补全、跳转、重构全部失效。
2. **调试灾难**：属性访问触发隐式副作用（打印日志、类型转换），调试点分散在 `__getattr__` 中，异常堆栈指向魔法方法内部而非调用处。
3. **无限递归陷阱**：`__getattr__` 内访问 `self._storage` 如果 `_storage` 未在 `__init__` 中提前设置，会再次触发 `__getattr__`，导致 `RecursionError`。
4. **语义污染**：`hasattr(settings, "anything")` 永远返回 `True`，因为 `__getattr__` 不抛 `AttributeError` 就意味着属性存在，silent bugs 在所难免。

### 栈帧黑客的额外危害

```python
import inspect

def skip_context_manager(func):
    """用 inspect 跳过 with 块 —— 真正的黑魔法"""
    frame = inspect.currentframe().f_back
    frame.f_locals["_skip"] = True  # 修改调用者的局部变量
    return func
```

这种代码：依赖 CPython 实现细节（PyPy/Jython 不兼容），绕过 Python 语义保证，安全审计工具无法追踪。

## 好代码

```python
from dataclasses import dataclass, field
import logging
from typing import Callable

logger = logging.getLogger(__name__)

@dataclass
class UserSettings:
    _raw: dict[str, str] = field(default_factory=dict)

    def get_theme(self) -> str:
        value = self._raw.get("theme", "light")
        logger.debug("读取 theme: %s", value)
        return value

    def set_theme(self, value: str) -> None:
        logger.debug("设置 theme: %s", value)
        self._raw["theme"] = value

    def get_count(self) -> int:
        raw = self._raw.get("count", "0")
        try:
            return int(raw)
        except ValueError:
            logger.warning("count 值非法: %r，使用默认值 0", raw)
            return 0

# 调用方
settings = UserSettings()
settings.set_theme("dark")
settings.set_count(42)
print(settings.get_theme())  # IDE 可推断返回 str
```

### 如果确实需要属性式访问，用 `property`

```python
class UserSettings:
    def __init__(self):
        self._raw: dict[str, str] = {}

    @property
    def theme(self) -> str:
        logger.debug("读取 theme: %s", self._raw.get("theme", "light"))
        return self._raw.get("theme", "light")

    @theme.setter
    def theme(self, value: str) -> None:
        logger.debug("设置 theme: %s", value)
        self._raw["theme"] = value
```

`property` 是 Python 内置的描述器协议，IDE 和类型检查器完整支持，行为可预测，调试堆栈清晰。

## 为什么好 / 关键差异

- **显式 > 隐式**：每一个可访问属性都有明确定义，IDE 和 mypy/pyright 可以完整推导类型。
- **副作用可追踪**：日志记录在明确的 getter/setter 方法中，不会偷偷发生在 `__getattr__` 的黑盒里。
- **避免递归陷阱**：不再需要 `startswith("_")` 这种脆弱的守卫逻辑。
- **私有变量直接访问没有圣光**：`__dunder__` 的名字改写（name mangling）仅用于防止子类意外覆盖，不是安全机制。外部代码应通过公开 API 交互，而非 `obj._ClassName__secret`。
