---
title: "Decorator Pattern: Cross-Cutting Without Copy-Paste"
category: case-study
tags:
  - decorator
  - cross-cutting
  - wrapper
  - composition
related:
  - ../best-practice/composition-over-inheritance.md
summary: "Using Python native decorators for cross-cutting concerns (logging, timing, auth) instead of copy-paste or inheritance chains."
---

# Decorator Pattern: Cross-Cutting Without Copy-Paste

## 场景

系统中多个核心函数——`process_message`、`sync_resources`、`execute_actor`——都需要记录执行耗时，同时附带函数名和参数摘要日志。此外，部分函数还需要重试、限流、缓存等横切关注点。

## 坏代码

```python
import time
import logging

logger = logging.getLogger(__name__)


async def process_message(msg_id: str, content: str) -> bool:
    start = time.perf_counter()
    logger.info("process_message start | msg_id=%s", msg_id)
    try:
        # ... 实际业务逻辑 40 行 ...
        result = await _do_process(msg_id, content)
        elapsed = time.perf_counter() - start
        logger.info("process_message done | msg_id=%s | %.3fs", msg_id, elapsed)
        return result
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("process_message failed | msg_id=%s | %.3fs", msg_id, elapsed)
        raise


async def sync_resources(resource_ids: list[str]) -> int:
    start = time.perf_counter()
    logger.info("sync_resources start | count=%d", len(resource_ids))
    try:
        # ... 实际业务逻辑 30 行 ...
        count = await _do_sync(resource_ids)
        elapsed = time.perf_counter() - start
        logger.info("sync_resources done | synced=%d | %.3fs", count, elapsed)
        return count
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("sync_resources failed | %.3fs", elapsed)
        raise
```

## 为什么坏

1. **横切关注点侵入核心逻辑**：计时和日志代码与业务逻辑混杂，业务逻辑被淹没在样板代码中——阅读者需要跳过 8 行才能看到实际做了什么。
2. **违反 DRY 原则**：每个函数复制粘贴相同的 `start`/`elapsed`/`logger.info` 模板。如果要改日志格式（比如加 `trace_id`），需要修改 N 处。
3. **意外不一致**：`process_message` 的日志格式是 `msg_id=%s`，`sync_resources` 是 `count=%d`——极易出现一个函数改了而另一个没改。
4. **测试负担**：单元测试必须 mock `time.perf_counter` 和 `logger`，即便只关心业务逻辑本身。

## 好代码

```python
from __future__ import annotations

import time
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def timed(
    *,
    name: str | None = None,
    log_args: bool = True,
) -> Callable[[F], F]:
    """装饰器：为异步函数自动记录执行耗时和参数摘要。

    作为 Python 一等公民，装饰器将横切关注点从业务逻辑中分离。
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        @wraps(func)  # 保留原函数的 __name__、__doc__、类型签名
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if log_args:
                logger.info("%s start | args=%s kwargs=%s", func_name, args, kwargs)
            else:
                logger.info("%s start", func_name)

            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info("%s done | %.3fs", func_name, elapsed)
                return result
            except Exception:
                elapsed = time.perf_counter() - start
                logger.exception("%s failed | %.3fs", func_name, elapsed)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# --- 纯净的业务逻辑，零样板代码 ---

@timed()
async def process_message(msg_id: str, content: str) -> bool:
    """处理用户消息，返回是否成功。"""
    return await _do_process(msg_id, content)


@timed(name="sync_resources_task")
async def sync_resources(resource_ids: list[str]) -> int:
    """同步资源，返回同步数量。"""
    return await _do_sync(resource_ids)
```

## 为什么好 / 关键差异

1. **横切关注点分离**：业务函数只包含业务逻辑——计时和日志被提升到 `@timed` 装饰器中，职责单一、清晰可读。
2. **单一修改点**：改变日志格式（如添加 `trace_id`、改用结构化日志）只需改 `timed` 一处，所有被装饰的函数自动生效。
3. **`@wraps` 保留元数据**：装饰后的函数保留原 `__name__`、`__doc__`、类型签名，IDE 自动补全和 Sphinx 文档生成不受影响。
4. **可组合**：Python 装饰器天然支持堆叠——`@retry(attempts=3) @timed() @rate_limit(max_per_sec=10)`，先后顺序精确可控，无需侵入函数体。
5. **参数化**：`@timed(name="custom", log_args=False)` 允许按需定制行为，灵活性远超硬编码模板。
