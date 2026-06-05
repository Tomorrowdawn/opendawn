---
title: "*args / **kwargs Abuse: The Cost of Lazy Signatures"
category: case-study
tags:
  - args
  - kwargs
  - function-signature
  - type-safety
  - readability
related:
  - ../best-practice/explicit-over-implicit.md
  - ../best-practice/type-safety.md
summary: "Passthrough *args/**kwargs destroys function signature readability and all type safety guarantees — the caller has no idea what's expected."
---

# *args / **kwargs Abuse: The Cost of Lazy Signatures

## 场景

你需要实现一个消息发送函数 `send_message`，支持各种配置：目标渠道、重试次数、超时时间、是否加密、优先级等等。随着需求增长，参数列表不断膨胀。

## 坏代码

```python
def send_message(*args, **kwargs):
    """
    发送消息到指定渠道。
    支持的 kwargs: channel, content, retries, timeout, encrypt, priority, ...
    """
    channel = kwargs.get("channel", "default")
    content = kwargs.get("content", "")
    retries = kwargs.get("retries", 3)
    timeout = kwargs.get("timeout", 30)
    encrypt = kwargs.get("encrypt", False)
    priority = kwargs.get("priority", 0)

    if encrypt:
        content = _encrypt(content)

    for attempt in range(retries):
        try:
            _do_send(channel, content, timeout=timeout)
            return
        except TimeoutError:
            if attempt == retries - 1:
                raise

# 调用方
send_message(
    channel="slack",
    content="hello",
    retries=5,
    timeout=60,
    encrypt=True,
    priorty=1,          # 拼写错误！静默忽略，退化为 0
    unknown="oops",     # 多余参数，静默吞掉
)
# 没人知道这个函数实际接受什么参数
```

## 为什么坏

1. **零可发现性**：IDE 无法显示参数列表，调用者必须阅读函数实现（甚至 docstring）才能知道传什么。AI 补全工具也爱莫能助。
2. **拼写错误无保护**：`priorty` 打错→ `kwargs.get("priority", 0)` 返回默认值 `0`，静默吞错。编译器、类型检查器、linter 全部沉默。
3. **多余参数无警告**：`unknown="oops"` 被安静忽略，可能是调用者以为这个参数有用，实际上什么也没发生。
4. **重构无保障**：参数改名后（`retries` → `max_retries`），所有旧的调用点静默退化到默认值，不会有任何编译错误或运行时警告。
5. **签名撒谎**：函数签名 `*args, **kwargs` 暗示"我接受任何参数"，但实际实现只认几个特定 key。任何参数都是合法的→任何参数也都是危险的。

## 好代码

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class MessageConfig:
    channel: str = "default"
    content: str = ""
    retries: int = 3
    timeout: float = 30.0
    encrypt: bool = False
    priority: int = 0

def send_message(config: MessageConfig) -> None:
    content = config.content
    if config.encrypt:
        content = _encrypt(content)

    for attempt in range(config.retries):
        try:
            _do_send(config.channel, content, timeout=config.timeout)
            return
        except TimeoutError:
            if attempt == config.retries - 1:
                raise

# 调用方
send_message(MessageConfig(
    channel="slack",
    content="hello",
    retries=5,
    timeout=60,
    encrypt=True,
    priority=1,
))
# 拼写错误现在会触发 AttributeError / mypy 报错
```

## 为什么好 / 关键差异

- **类型安全**：`MessageConfig` 的每一个字段都有明确类型，mypy/pyright 可以验证调用方传参的正确性。
- **IDE 友好**：输入 `MessageConfig(` 后，IDE 弹出所有可用字段及其类型和默认值，零文档成本。
- **拼写错误即时报错**：`priorty=1` 会触发 `unexpected keyword argument`，运行前就能发现。
- **单一真相来源**：所有参数的名称、类型、默认值集中在 `MessageConfig` dataclass 中，不存在 docstring 与实际代码不一致的风险。
- **可组合、可复用**：`MessageConfig` 可以被序列化、被其他函数复用、被部分覆盖（`dataclasses.replace`），远比散落的 kwargs 灵活。

### 可选模式：`TypedDict` 显式 kwargs

```python
from typing import TypedDict, Unpack

class SendOptions(TypedDict, total=False):
    retries: int
    timeout: float
    encrypt: bool

def send_message(channel: str, content: str, **options: Unpack[SendOptions]) -> None:
    retries = options.get("retries", 3)
    ...
```

> 核心原则：函数签名是 API 契约。让每一个参数都显式声明，类型检查器才能守护你的代码。
