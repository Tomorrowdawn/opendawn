---
title: "Runtime Resources: Lifecycle, Allocation, and Recycling"
category: case-study
tags:
  - runtime-resources
  - lifecycle
  - allocation
  - connection-pool
  - context-manager
  - graceful-shutdown
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/fail-fast.md
  - dependency-injection.md
summary: "Runtime resources (DB pools, HTTP sessions, Redis connections) demand explicit lifecycle management — acquire, pool/recycle, release. Global singletons and implicit initialization are bugs waiting for production. Async context managers + composition root make resource ownership provable at the type level."
---

# Runtime Resources: Lifecycle, Allocation, and Recycling

## Scenario

Your application holds three runtime resources: a PostgreSQL connection pool, an `httpx.AsyncClient` session (with connection pooling), and a Redis connection. These are acquired at startup, reused across the process lifetime, and must be released on shutdown. Each resource has its own initialization order dependency — Redis must be ready before the HTTP client can validate auth tokens against cache.

## Bad Code: Global Singletons with Implicit Lifecycle

```python
# db.py
import asyncpg

pool: asyncpg.Pool | None = None

async def init_pool(dsn: str) -> None:
    global pool
    pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)


# http_client.py
import httpx

client: httpx.AsyncClient | None = None

async def init_client() -> None:
    global client
    client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100),
        timeout=httpx.Timeout(30.0),
    )


# redis_client.py
import redis.asyncio as aioredis

redis: aioredis.Redis | None = None

async def init_redis(url: str) -> None:
    global redis
    redis = await aioredis.from_url(url, max_connections=50)


# main.py — fragile startup sequence, no shutdown
import asyncio
from db import init_pool
from http_client import init_client
from redis_client import init_redis

async def main():
    await init_redis("redis://localhost:6379/0")  # must come first
    await init_pool("postgresql://localhost/mydb")
    await init_client()

    ...  # application logic

    # Shutdown? What shutdown? Resources leak on exit.
    # If any init fails, the others are never cleaned up — partial-state deadlock.
```

## Why It's Bad

1. **No ownership — no single point that knows all resources**: `init_pool` lives in `db.py`, `init_client` in `http_client.py`, `init_redis` in `redis_client.py`. No module owns the full lifecycle. If startup fails midway, the resources already acquired are leaked — there is no single `finally` block that can clean up everything.

2. **Implicit initialization order**: `init_redis` must run before `init_client` — but this dependency is documented nowhere except a comment in `main.py`. A future refactor that reorders the calls produces a runtime crash that the type checker cannot catch.

3. **No recycling discipline**: The connection pool `max_size=20` is set once and forgotten. There is no health check to detect stale connections, no backpressure when the pool is exhausted, and no circuit breaker when the database is down. If `asyncpg` connections silently die (network partition, PG restart), the pool sits there holding dead connections until the first query times out.

4. **No graceful shutdown**: SIGTERM arrives — `asyncio.run()` cancels all tasks. The pool's `close()` method is never called. PostgreSQL sees abrupt connection drops. Redis buffers are lost. The HTTP client's in-flight requests are abandoned mid-TCP-handshake.

5. **Not testable**: Every test that touches `db.py` or `http_client.py` inherits the global mutable singleton. You cannot spin up a test-specific pool with different settings without monkey-patching globals.

## Good Code: Async Context Manager + Pool Discipline + Composition Root

```python
from __future__ import annotations

import asyncio
import asyncpg
import httpx
import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)


class AppResources:
    """Single owner of all runtime resources. Acquire → use → recycle → release."""

    def __init__(
        self,
        *,
        db_dsn: str,
        redis_url: str,
        db_pool_min: int = 5,
        db_pool_max: int = 20,
        http_max_connections: int = 100,
    ) -> None:
        self._db_dsn = db_dsn
        self._redis_url = redis_url
        self._db_pool_min = db_pool_min
        self._db_pool_max = db_pool_max
        self._http_max_connections = http_max_connections

        # Owned resources — None until acquired
        self.db_pool: asyncpg.Pool | None = None
        self.http: httpx.AsyncClient | None = None
        self.redis: aioredis.Redis | None = None

    async def __aenter__(self) -> "AppResources":
        """Acquire all resources in dependency order. Fail fast on any error."""
        try:
            # 1. Redis first — other components may depend on cache availability
            self.redis = await aioredis.from_url(
                self._redis_url,
                max_connections=50,
                health_check_interval=30,  # recycle: detect and replace dead connections
            )
            await self.redis.ping()
            logger.info("redis_connected", url=self._redis_url)

            # 2. Database — pooled with min/max
            self.db_pool = await asyncpg.create_pool(
                self._db_dsn,
                min_size=self._db_pool_min,
                max_size=self._db_pool_max,
            )
            logger.info(
                "db_pool_created",
                dsn=self._db_dsn,
                min_size=self._db_pool_min,
                max_size=self._db_pool_max,
            )

            # 3. HTTP client — connection pooling built into httpx
            self.http = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=self._http_max_connections),
                timeout=httpx.Timeout(30.0),
            )
            logger.info("http_client_ready", max_connections=self._http_max_connections)

            return self

        except Exception:
            # If any acquisition fails, release everything already acquired.
            # This is why ownership matters — only one place knows the full picture.
            await self.__aexit__(type, None, None)
            raise

    async def __aexit__(self, *args: object) -> None:
        """Release all resources in reverse dependency order. Idempotent — safe to call
        even if acquisition partially failed."""
        errors: list[Exception] = []

        if self.http is not None:
            try:
                await self.http.aclose()
                logger.info("http_client_closed")
            except Exception as exc:
                errors.append(exc)

        if self.db_pool is not None:
            try:
                await self.db_pool.close()
                logger.info("db_pool_closed")
            except Exception as exc:
                errors.append(exc)

        if self.redis is not None:
            try:
                await self.redis.aclose()
                logger.info("redis_closed")
            except Exception as exc:
                errors.append(exc)

        # Log release errors but don't raise — shutdown should not be blocked by
        # a single resource failing to close. The OS will clean up.
        if errors:
            logger.warning(
                "resource_release_errors",
                count=len(errors),
                errors=[str(e) for e in errors],
            )

    async def health_check(self) -> bool:
        """Verify all resources are alive. Call before accepting traffic."""
        try:
            await self.redis.ping()
            async with self.db_pool.acquire() as conn:  # acquire → use → recycle
                await conn.execute("SELECT 1")
            await self.http.get("https://example.com/health")
            return True
        except Exception:
            logger.exception("health_check_failed")
            return False


# ── Composition Root ─────────────────────────────────────────────────────

async def build_services() -> tuple[AppResources, UserService, OrderService]:
    """Single entry point: create resources + inject into services."""
    resources = await AppResources(
        db_dsn="postgresql://localhost/mydb",
        redis_url="redis://localhost:6379/0",
    ).__aenter__()

    user_svc = UserService(db=resources.db_pool)
    order_svc = OrderService(db=resources.db_pool, http=resources.http)
    return resources, user_svc, order_svc


# ── Graceful Shutdown with Signal Handling ────────────────────────────────

async def main() -> None:
    resources, user_svc, order_svc = await build_services()

    shutdown_event = asyncio.Event()

    def _handle_signal():
        logger.info("shutdown_signal_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(SIGTERM, _handle_signal)
    loop.add_signal_handler(SIGINT, _handle_signal)

    try:
        await shutdown_event.wait()  # run until signal
    finally:
        # Resources released in reverse order — always executed
        await resources.__aexit__(None, None, None)
        logger.info("shutdown_complete")
```

## Why It's Good / Key Differences

1. **Single owner, single lifecycle**: `AppResources` is the sole owner of all runtime resources. You can look at one class and answer: "What resources does this process hold? How are they acquired? In what order are they released?" The answer is not scattered across 10 files.

2. **Acquire → use → recycle**: `async with self.db_pool.acquire()` in `health_check` demonstrates the pool's recycling contract — connections are borrowed, used, and returned. The pool handles dead connection detection (`health_check_interval` on Redis), backpressure (max_size limits concurrency), and recycling (idle connections are pruned or replaced).

3. **Graceful shutdown is an architectural property, not an afterthought**: SIGTERM triggers `__aexit__`, which releases resources in reverse dependency order. Even if one resource fails to close, the others are still released. The try/except in `__aexit__` ensures shutdown is never blocked by a single misbehaving connection.

4. **Partial acquisition is cleaned up**: If Redis connects but PostgreSQL fails, `__aenter__` calls `__aexit__` to release Redis before re-raising. No resource leaks on startup failure.

5. **Health check at the boundary**: `health_check()` verifies all resources are alive before the application accepts traffic. This is the runtime equivalent of "fail fast" — catch resource failures before they become user-facing errors.

6. **Testable without real infrastructure**: A test can create `FakeResources` implementing the same interfaces — no globals to monkey-patch, no real databases to spin up.

> Core principle: Runtime resources are not free variables. Their lifecycle (acquire → pool/recycle → release) must be owned by a single type that is injected at the composition root. If a resource allocation is not auditable by reading one class, you have a lifecycle bug.

