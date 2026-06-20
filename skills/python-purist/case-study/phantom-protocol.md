---
title: "Phantom Protocol: 单实现的接口抽象"
category: case-study
tags:
  - protocol
  - interface
  - abstraction
  - anti-pattern
  - runtime-checkable
  - isinstance
  - yagni
related:
  - ../best-practice/trust-your-types.md
  - ../best-practice/direct-over-indirect.md
  - ../case-study/inheritance-vs-composition.md
summary: "Protocol 的设计意图是多态。当只有一个实现时，Protocol 不提供抽象价值——它只是在调用者和实现者之间插入一组无法追踪的间接层。"
---

# Phantom Protocol: 单实现的接口抽象

## 场景

你设计了一个 LLM 会话系统。你担心未来可能更换 LLM 提供商，于是定义了三个 Protocol:

```python
# 接口层 (llm_session.py — 28 行)
class LlmSession(Protocol):           ...
class LlmSessionFactory(Protocol):    ...
class SelectableLlmSessionFactory(LlmSessionFactory, Protocol): ...
```

然后发现整个代码库里只有一个实现: `YuuSession` 和 `ProviderPoolSessionFactory`。然后你在调用处还要做 `isinstance(factory, SelectableLlmSessionFactory)` —— 用运行时反射验证你自己定义的编译期契约。

这个模式来自 `yuuagents/llm_session.py` 的真实代码。

## 坏代码

```python
from typing import Protocol, runtime_checkable

# ── 三层 Protocol，每层都是纯接口定义 ──

@runtime_checkable
class LlmSession(Protocol):
    @property
    def history(self) -> yuullm.History: ...
    def append(self, msg: yuullm.Message) -> None: ...
    async def stream(self, **options) -> yuullm.StreamResult: ...

@runtime_checkable
class LlmSessionFactory(Protocol):
    def create_session(self, history: yuullm.History) -> LlmSession: ...

@runtime_checkable
class SelectableLlmSessionFactory(LlmSessionFactory, Protocol):
    def with_selector(self, selector: str) -> LlmSessionFactory: ...

# ── 唯一的实现 ──

class ProviderPoolSessionFactory:
    def create_session(self, history: yuullm.History) -> YuuSession:
        return YuuSession(history=history, pool=self.pool)

    def with_selector(self, selector: str) -> "ProviderPoolSessionFactory":
        return ProviderPoolSessionFactory(pool=self.pool.with_selector(selector))

class YuuSession:
    @property
    def history(self) -> yuullm.History: ...
    def append(self, msg: yuullm.Message) -> None: ...
    async def stream(self, **options) -> yuullm.StreamResult: ...

# ── 调用处 —— Protocol 没有消歧调用，反而引入了反射 ──

def select_llm_session_factory(
    factory: LlmSessionFactory,
    selector: str | None,
) -> LlmSessionFactory:
    if selector is not None and isinstance(factory, SelectableLlmSessionFactory):
        # ↑ 运行时 isinstance 检查 —— 这是在验证你自己写的代码
        return factory.with_selector(selector)
    return factory

# 链路的实际调用:
# select_llm_session_factory(ProviderPoolSessionFactory(), "fast")
# → isinstance 永远返回 True（因为只有一个实现）
# → with_selector 永远可用
# → Protocol 在运行时零作用，在编译期只增加了一层跳转
```

## 为什么坏

1. **零多态价值的抽象**。`@runtime_checkable` Protocol 的核心能力是 structural subtyping —— 允许任何满足接口的对象被当作该类型使用。但这里整个系统只有一个实现。Protocol 定义的每一个方法签名，在具体类里都要再写一遍——这是纯粹的重复，不是抽象。

2. **`@runtime_checkable` + `isinstance()` 是信任危机的信号**。Protocol 本质是类型检查器的工具——它告诉 mypy/pyright "这个类型满足这个接口"。`@runtime_checkable` 把它变成了运行时工具——你不再信任类型检查器，转而用 `isinstance` 在运行时验证。但如果只有一个实现，`isinstance(factory, SelectableLlmSessionFactory)` 永远返回 `True`，这段代码没有任何分支价值。

3. **调用链路无法追踪**。当你在 IDE 里 Cmd+Click `factory.with_selector(selector)`：
   - 你跳到 `SelectableLlmSessionFactory.with_selector` 的 Protocol 声明——一个只有 `...` 的空函数体
   - 你无法从这个 Protocol 声明追踪到实际实现
   - 你需要手动搜索 `def with_selector` 来找真正的代码
   - Protocol 在这里不是桥，是迷宫

4. **三层 Protocol 的认知负载**。读代码的人需要理解 `LlmSession` → `LlmSessionFactory` → `SelectableLlmSessionFactory` 三层抽象关系，然后发现——它们全映射到同一个 `ProviderPoolSessionFactory` 上。三层概念，零价值信息。

5. **违反了"模式出现再抽象"**。`direct-over-indirect` 规则 6 说：在同一个模式出现三次之前，不要提取抽象。这里模式出现了零次——你只有一个实现，但在它就抽象出了三层 Protocol。

## 好代码

```python
# ── 直接使用具体类型 —— 等第二个实现出现再考虑 Protocol ──

class YuuSession:
    """LLM 会话的具体实现。"""
    history: yuullm.History
    pool: ProviderPool
    
    def append(self, msg: yuullm.Message) -> None:
        self.history.append(msg)
    
    async def stream(self, **options) -> yuullm.StreamResult:
        model = options.pop("model", self.pool.default_model)
        return await self.pool.stream(self.history, model=model, **options)


class ProviderPoolSessionFactory:
    """会话工厂 —— 管理 provider 选择逻辑。"""
    pool: ProviderPool
    
    def create_session(self, history: yuullm.History) -> YuuSession:
        return YuuSession(history=history, pool=self.pool)
    
    def with_selector(self, selector: str) -> "ProviderPoolSessionFactory":
        return ProviderPoolSessionFactory(pool=self.pool.with_selector(selector))


# ── 调用处 —— 直接使用具体类型，零反射 ──

def resolve_session_factory(
    factory: ProviderPoolSessionFactory,
    selector: str | None,
) -> ProviderPoolSessionFactory:
    if selector is not None:
        return factory.with_selector(selector)
    return factory

# ── 当真正出现第二个实现时，再引入 Protocol ──
# class AnthropicPoolSessionFactory:
#     def create_session(self, history) -> AnthropicSession: ...
#     def with_selector(self, selector) -> "AnthropicPoolSessionFactory": ...
# 
# # 此时——在第二个实现出现后——再定义 Protocol:
# class SessionFactory(Protocol):
#     def create_session(self, history: History) -> Session: ...
#     def with_selector(self, selector: str) -> "SessionFactory": ...
```

## 为什么好 / 关键差异

1. **直接调用，可追踪**。Cmd+Click `factory.with_selector(selector)` → 直接跳到 `ProviderPoolSessionFactory.with_selector` 的具体实现。不需要经过空白的 Protocol 声明。

2. **零反射**。不再需要 `isinstance(factory, SelectableLlmSessionFactory)`。你直接调用 `factory.with_selector(selector)`，类型检查器已经确认了这个方法存在。

3. **`@runtime_checkable` 消失**。没有 Protocol 就没有 `@runtime_checkable`。运行时不再验证编译期契约——类型检查器在编译期已经完成了这个工作。

4. **Protocol 延迟到真正需要时**。等到第二个实现出现（如 `AnthropicPoolSessionFactory`），此时提取 `SessionFactory` Protocol 是"消除重复"——你确实有了两个需要统一接口的实现。Protocol 此时产生了真正的价值。

### 核心原则

> Protocol 是为多态而生的工具。没有多个实现，就不需要 Protocol。`@runtime_checkable` 是信任危机的信号——你在运行时验证一个编译期契约。如果只有一个实现，这两个东西都是零价值的间接层。
