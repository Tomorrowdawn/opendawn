---
title: "Observer Pattern: Events Over Callbacks"
category: case-study
tags:
  - observer
  - event-bus
  - callback
  - decoupling
  - pub-sub
related:
  - ../best-practice/composition-over-inheritance.md
  - event-bus-observability.md
summary: "Event bus replacing callback hell for loosely-coupled inter-module communication — publishers and subscribers know nothing about each other."
---

# Observer Pattern: Events Over Callbacks

## 场景

资源管理系统中，资源变更（创建、更新、删除）发生后需要通知多个订阅者：刷新缓存、更新性能指标、写出审计日志。订阅者数量会随着系统演进增加——未来可能加入 Webhook 推送、ElasticSearch 索引同步等。

## 坏代码

```python
from __future__ import annotations

import logging
from typing import Any

from yuubot.resources.repository import ResourceRepository

logger = logging.getLogger(__name__)
repository = ResourceRepository()


class ResourceService:
    async def create_resource(self, data: dict[str, Any]) -> str:
        resource_id = await repository.insert(data)

        # 硬编码的三方调用——每增加一个订阅者就要改这里
        cache.clear()  # 缓存刷新
        metrics.increment("resource.created", tags={"type": data["type"]})
        logger.info("Resource created | id=%s type=%s", resource_id, data["type"])

        return resource_id

    async def update_resource(self, resource_id: str, data: dict[str, Any]) -> None:
        await repository.update(resource_id, data)

        cache.clear()
        metrics.increment("resource.updated")
        logger.info("Resource updated | id=%s", resource_id)


    async def delete_resource(self, resource_id: str) -> None:
        await repository.delete(resource_id)

        cache.clear()
        metrics.increment("resource.deleted")
        logger.info("Resource deleted | id=%s", resource_id)
```

## 为什么坏

1. **违反开闭原则**：每新增一个订阅者（如 Webhook、搜索索引），必须修改 `create_resource` / `update_resource` / `delete_resource` 三个方法。
2. **职责混乱**：`ResourceService` 既要管理资源持久化，又要协调缓存刷新、指标采集、日志记录——类承载了过多无关职责。
3. **调用顺序隐式耦合**：如果 Webhook 推送失败导致异常，是否会阻止前面的 `cache.clear()` 生效？调用是串行的，一个订阅者崩溃会影响后续。
4. **无法按需订阅**：A/B 实验或环境切换时无法动态开启/关闭某个订阅者（如开发环境不写审计日志）。

## 好代码

```python
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceEvent:
    action: str  # "created" | "updated" | "deleted"
    resource_id: str
    resource_type: str
    payload: dict[str, Any]


class ResourceListener(Protocol):
    """资源变更监听器协议——所有订阅者实现此接口。"""

    async def on_resource_changed(self, event: ResourceEvent) -> None: ...


class EventEmitter:
    """轻量级事件发射器——管理订阅者注册和事件分发。"""

    def __init__(self) -> None:
        self._listeners: list[ResourceListener] = []

    def subscribe(self, listener: ResourceListener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: ResourceListener) -> None:
        self._listeners.remove(listener)

    async def emit(self, event: ResourceEvent) -> None:
        """通知所有订阅者，单个订阅者异常不影响其他。"""
        for listener in self._listeners:
            try:
                await listener.on_resource_changed(event)
            except Exception:
                logger.exception(
                    "Listener %s failed for event %s",
                    type(listener).__name__, event.action,
                )


class CacheInvalidator:
    async def on_resource_changed(self, event: ResourceEvent) -> None:
        cache.invalidate(f"resource:{event.resource_id}")


class MetricsCollector:
    async def on_resource_changed(self, event: ResourceEvent) -> None:
        metrics.increment(f"resource.{event.action}", tags={"type": event.resource_type})


class AuditLogger:
    async def on_resource_changed(self, event: ResourceEvent) -> None:
        logger.info(
            "Resource %s | id=%s type=%s", event.action, event.resource_id, event.resource_type,
        )


# --- 装配 ---
emitter = EventEmitter()
emitter.subscribe(CacheInvalidator())
emitter.subscribe(MetricsCollector())
emitter.subscribe(AuditLogger())


class ResourceService:
    def __init__(self, emitter: EventEmitter, repository: ResourceRepository) -> None:
        self._emitter = emitter
        self._repository = repository

    async def create_resource(self, data: dict[str, Any]) -> str:
        resource_id = await self._repository.insert(data)
        await self._emitter.emit(ResourceEvent(
            action="created", resource_id=resource_id,
            resource_type=data["type"], payload=data,
        ))
        return resource_id
```

## 为什么好 / 关键差异

1. **开闭原则（O 端）**：新增订阅者——比如 `WebhookNotifier`——只需新建一个实现 `ResourceListener` 协议的类型并调用 `emitter.subscribe()`，**零修改** `ResourceService`。
2. **单点发射**：`emitter.emit()` 是唯一的事件出口，添加跨事件切面逻辑（如限流、异步批处理）只需改一处。
3. **故障隔离**：`emit` 循环内每个 `listener` 都有独立 `try/except`——缓存刷新失败不会阻止指标采集或审计日志写入。
4. **按环境装配**：在 `EventEmitter` 层面按环境订阅不同监听器——生产环境挂 Webhook，开发环境跳过——无需修改任何监听器代码。
