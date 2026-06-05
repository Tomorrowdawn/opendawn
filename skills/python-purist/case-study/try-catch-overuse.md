---
title: "Try-Catch Overuse: The Fail-Fast Antithesis"
category: case-study
tags:
  - exception
  - try-catch
  - error-handling
  - fail-fast
  - defensive-programming
related:
  - ../best-practice/fail-fast.md
  - exception-swallowing.md
summary: "Wrapping every function in try/except Exception doesn't make code robust — it creates invisible failure modes. Catch specific, catch at boundaries, let the rest crash."
---

# Try-Catch Overuse: The Fail-Fast Antithesis

## 场景

你有一个后台任务管线：从消息队列拉取事件 → 调用下游服务 → 写入数据库。线上偶尔出现"任务静默丢失"——没有异常日志，没有告警，但数据就是少了。

## 坏代码

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

class PipelineWorker:
    async def process_event(self, event: dict) -> bool:
        """处理单个事件，返回 True/False。任何失败都返回 False。"""
        try:
            await self._validate(event)
        except Exception:
            return False  # 校验失败 → 静默丢弃

        try:
            enriched = await self._enrich(event)
        except Exception:
            return False  # 下游富化失败 → 静默丢弃

        try:
            await self._persist(enriched)
        except Exception:
            return False  # 写入失败 → 静默丢弃

        return True

    async def run_pipeline(self, queue: asyncio.Queue) -> None:
        """主循环：从队列取事件，失败就打日志，绝不崩溃。"""
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                pass  # 队列异常也吞掉

            try:
                ok = await self.process_event(event)
                if not ok:
                    logger.warning("事件处理失败 event=%s", event.get("id"))
            except Exception:
                logger.error("非预期错误，继续运行")

    async def fire_and_forget(self, event: dict) -> None:
        """发后不管 — 调度了就不管了。"""
        asyncio.create_task(self.process_event(event))
        # 任务可能抛异常，但没人 await，异常永远丢失
```

### CI/CD 场景的同类问题

```python
import subprocess

def deploy() -> None:
    try:
        subprocess.run(["pytest"], check=True)
    except subprocess.CalledProcessError:
        print("测试失败，但继续部署...")  # ← 静默上线损坏的代码

    try:
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError:
        print("依赖安装可能有问题，继续...")  # ← 生产环境缺少关键库
```

## 为什么坏

1. **假安全感**：每个函数包一层 `try/except Exception` 看起来"防御性很强"，实际上是把所有失败模式统一映射成 `return False`。调用方不知道是校验失败、网络超时、还是代码里的 `AttributeError` bug——全部退化成一个布尔值。

2. **违背 Fail Fast 原则**：`fail-fast.md` 明确要求"在入口处崩溃，不将错误状态传播到系统深处"。但这里的 `process_event` 在每一层都主动拦截异常，让错误状态（`False`）继续向下游流动。原本应该在 `_validate` 处就暴露的 `TypeError`（参数错误），被吞掉后变成了"偶尔丢失事件"的幽灵 bug。

3. **异常黑洞**：`fire_and_forget` 中 `asyncio.create_task()` 创建的协程，如果没人 `await`，它的异常只会在垃圾回收时以 `"Task exception was never retrieved"` 形式出现——一条事后警告，没有堆栈追踪，无法定位根因。

4. **CI/CD 静默上线损坏代码**：`subprocess.run` 失败了但 `try/except` 吞掉，导致破坏性变更直接进入生产。这正是 Xygeni 文章指出的核心风险：**try-catch 在 DevSecOps 流程中隐藏脆弱点**。

5. **`return False` 不是错误处理**：把一个丰富的异常信息（异常类型、消息、堆栈追踪、`__cause__` 链）压缩成一个布尔值，是信息论意义上的"有损压缩"。下游不知道发生了什么，无法做任何有意义的恢复。

## 好代码

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

class PipelineError(Exception):
    """业务层异常——每条消息失败带足够上下文"""
    def __init__(self, message: str, event_id: str, original: Exception | None = None):
        super().__init__(message)
        self.event_id = event_id
        self.original = original

class PipelineWorker:
    async def process_event(self, event: dict) -> None:
        """处理单个事件。成功则返回，失败则抛出 PipelineError。"""
        event_id = event.get("id", "unknown")

        try:
            await self._validate(event)
        except ValueError as e:
            raise PipelineError(f"校验失败: {event_id}", event_id, original=e) from e
        except TypeError as e:
            # TypeError 是代码 bug，不应该吞掉
            logger.critical("代码缺陷 _validate 参数类型错误 event=%s", event_id, exc_info=True)
            raise

        try:
            enriched = await self._enrich(event)
        except httpx.TimeoutException as e:
            raise PipelineError(f"富化超时: {event_id}", event_id, original=e) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "富化下游返回异常 event=%s status=%d body=%s",
                event_id, e.response.status_code, e.response.text[:200],
            )
            raise PipelineError(
                f"富化下游错误({e.response.status_code}): {event_id}",
                event_id, original=e,
            ) from e

        await self._persist(enriched)

    async def run_pipeline(self, queue: asyncio.Queue) -> None:
        """主循环：已知的业务异常记录后继续，未知异常传播到顶层。"""
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            try:
                await self.process_event(event)
            except PipelineError as e:
                logger.warning("事件处理失败 event=%s reason=%s", e.event_id, e)
                # 可重试、可写入死信队列、可告警——由外层策略决定
            # 非 PipelineError 的异常不捕获，直接传播到全局异常处理器

    async def fire_and_await(self, events: list[dict]) -> list[dict]:
        """安全并发：用 TaskGroup 确保所有异常都被收集。"""
        results: list[dict] = []
        failed: list[dict] = []

        async with asyncio.TaskGroup() as tg:
            for event in events:
                tg.create_task(self._handle_one(event, results, failed))

        logger.info("批量处理完成 success=%d failed=%d", len(results), len(failed))
        return {"success": results, "failed": failed}

    async def _handle_one(
        self, event: dict, results: list[dict], failed: list[dict],
    ) -> None:
        try:
            await self.process_event(event)
            results.append(event)
        except PipelineError as e:
            failed.append({"event_id": e.event_id, "reason": str(e)})
```

### CI/CD 场景的正确写法

```python
import subprocess
import sys

def deploy() -> None:
    # ✅ 不吞异常：任何失败直接终止管线
    subprocess.run(["pytest"], check=True)          # 测试失败 → 管线终止
    subprocess.run(["pip", "check"], check=True)    # 依赖冲突 → 管线终止
    subprocess.run(["python", "setup.py", "build"], check=True)
    # 只有全部通过才继续部署
```

## 为什么好 / 关键差异

- **捕获具体异常类型**：`httpx.TimeoutException`、`httpx.HTTPStatusError`、`ValueError`——每种失败有独立的处理逻辑，日志包含足够上下文。不用 `except Exception` 一网打尽。
- **代码 bug 不吞**：`TypeError`（参数错误）是开发者错误，不是业务异常。用 `logger.critical` + `raise` 确保它不被静默隐藏。
- **边界处理，内部传播**：`process_event` 在调用外部依赖（`_enrich`、`_validate`）的边界处捕获可预期的异常并包装为 `PipelineError`。主循环只捕获 `PipelineError`（已知的业务失败），其他异常任其传播到全局处理器。
- **`asyncio.TaskGroup` 替代 fire-and-forget**：Python 3.11+ 的 `TaskGroup` 确保组内任何一个 task 抛出未捕获异常时，所有 task 被取消，异常传播给调用者。零丢失。
- **CI/CD 管线 Fail Loud**：`check=True` 让失败可见。测试失败 = 管线终止。依赖冲突 = 管线终止。部署只有在一切正常时才发生。
- **结构化日志携带上下文**：每条异常日志包含 `event_id`、状态码、响应体摘要等关键信息。故障发生后可以直接定位到具体事件和根因。

> 核心原则：**只捕获你知道如何恢复的异常。在系统边界捕获并包装，在内部任其传播。吞掉的异常不是"已处理"——它是"埋下的地雷"。Fail fast 的精髓不是不写 try，而是让异常在最合适的层级被看见、被理解、被处理。**