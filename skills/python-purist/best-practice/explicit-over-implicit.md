---
title: "Explicit Over Implicit"
category: best-practice
tags:
  - explicit
  - magic-methods
  - getattr
  - setattr
  - implicit
  - readability
related:
  - ../case-study/magic-methods.md
  - ../case-study/args-kwargs-abuse.md
summary: "Code behavior must be inferable from the code itself. Reject __getattr__/__setattr__ magic, implicit type coercion, and hidden side effects."
---

# Explicit Over Implicit

## 原则

**代码的行为必须能从代码本身直接推断。** 每当你使用元编程技巧隐藏了逻辑，就意味着每一个阅读代码的人——包括三个月后的你自己——都必须额外记住一个隐式约定。

## 反对 `__getattr__` / `__setattr__` 滥用

魔术方法让属性访问变得不可预测。阅读者看到 `obj.name`，以为是一次普通的属性访问，实际上可能触发了数据库查询、网络请求或全局状态修改。

```python
# ❌ 隐式——属性访问隐藏了复杂逻辑
class Proxy:
    def __getattr__(self, name: str):
        return self._fetch_from_remote(name)  # 网络请求！

# ✅ 显式——方法签名诚实
class Proxy:
    def fetch(self, name: str) -> Any:
        """明确告知调用者：这会发起网络请求"""
        return self._fetch_from_remote(name)
```

唯一可接受的 `__getattr__` 场景是实现代理模式时，且行为仅限于属性转发，不应包含副作用：

```python
# ✅ 可接受——纯粹转发，无副作用
class LazyProxy:
    def __getattr__(self, name: str):
        if self._wrapped is None:
            self._wrapped = self._factory()
        return getattr(self._wrapped, name)
```

## 反对 `inspect` 栈帧黑魔法

不要用 `inspect.stack()` 或 `sys._getframe()` 来推断调用者身份、获取调用者的局部变量或修改调用栈。这类代码：

- 破坏函数签名的隔离性——函数行为依赖"谁调用了我"
- 在调试器、装饰器、异步上下文中行为不可预测
- 无法被类型检查器理解

```python
# ❌ 栈帧黑魔法——功能依赖调用者的帧
def get_caller_name() -> str:
    import inspect
    return inspect.stack()[1].function  # 脆弱、隐式、不可测试

# ✅ 显式——调用者直接传入所需信息
def get_caller_name(caller: str) -> str:
    return caller
```

## 反对隐藏副作用

函数签名必须诚实。如果一个函数会修改全局状态、写入文件、发送网络请求，这些必须从签名和返回值中体现——要么通过命名，要么通过异常声明，要么通过返回类型。

```python
# ❌ 隐式副作用——签名上看不出来
def process(items: list[Item]) -> list[Result]:
    _global_counter += len(items)  # 修改全局状态！
    return [...]

# ✅ 显式——副作用通过返回值体现
def process(items: list[Item]) -> tuple[list[Result], int]:
    processed_count = len(items)
    return [...], processed_count
```

## 总结

Python 给了我们强大的元编程能力，但能力越大，责任越大。每当你准备使用魔术方法或栈帧技巧时，问自己：**"一个不熟悉这段代码的同事，能在不读实现的情况下理解它的行为吗？"** 如果答案是不能，那就需要让它更显式。
