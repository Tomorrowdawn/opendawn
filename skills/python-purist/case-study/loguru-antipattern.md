---
title: "Loguru Anti-Pattern: The Siren Song of the Global Singleton"
category: case-study
tags:
  - loguru
  - logging
  - anti-pattern
  - global-state
  - implicit
  - explicit-over-implicit
related:
  - ../best-practice/structured-logging.md
  - ../best-practice/explicit-over-implicit.md
summary: "loguru's from loguru import logger is a global mutable singleton. It enables import-time side effects, implicit handler configuration, and silently sabotages test isolation. Reject it."
---

# Loguru Anti-Pattern: The Siren Song of the Global Singleton

## Scenario

You are drawn to `loguru`'s concise API: one line `from loguru import logger`, colorized logs with zero configuration, `logger.add("file.log", rotation="500 MB")` for file rotation. You introduce it into a multi-contributor backend project.

## Bad Code: loguru's Implicit Global State

```python
# services/payment.py
from loguru import logger  # ← global mutable singleton

# logger is already a pre-configured global object -- who configured it? where? you don't need to know!
logger.add("payment.log", rotation="1 week")  # ← mutating global state at module top-level!

class PaymentService:
    async def charge(self, order_id: str) -> dict:
        logger.info("charging order={}", order_id)  # f-string style, not structured
        ...


# services/notification.py
from loguru import logger  # ← same global singleton

class NotificationService:
    async def send(self, user_id: str, msg: str) -> None:
        logger.info("sending notification user={} msg={}", user_id, msg)
        ...


# tests/test_payment.py
from loguru import logger  # ← tests share the same global singleton!

def test_charge():
    # Production handler is still active! Test output is written to payment.log!
    # The only isolation mechanism is logger.remove() -- which affects ALL other tests!
    logger.remove()
    svc = PaymentService()
    result = await svc.charge("order_42")
    assert result["status"] == "ok"
    # Did you forget to restore the handler? The next test module loses its logs.
```

## Why It's Bad

1. **Global mutable singleton `from loguru import logger`**: The entire process shares a single `logger` instance. Module A adding a handler affects Module B. Test A removing a handler destroys Test B. This "action-at-a-distance" violates the most fundamental rule of this skill -- **code behavior must be inferable from the code itself.**

2. **`logger.add()` at module top-level produces import-time side effects**: `import payment` silently executes `logger.add("payment.log")` -- importing a module mutates the global log pipeline. Which import runs first is non-deterministic (depends on import order), yielding Heisenbugs where "sometimes logs go to payment.log, sometimes they don't."

3. **String interpolation instead of structured events**: `logger.info("charging order={}", order_id)` is essentially `str.format()` in disguise, producing an opaque string. Elasticsearch/Loki cannot auto-index the `order_id` field.

4. **`logger.bind()` is a mutable operation**: `log = logger.bind(user_id="42")` looks like it returns a new object, but the handler chain is shared. In multi-threaded/async environments, bind/unbind timing issues are nearly impossible to debug.

5. **`@logger.catch` decorator silently swallows exceptions**: `@logger.catch` catches exceptions, logs them, and silently returns `None`. You lose stack propagation. The caller has no idea an error occurred. System state is silently corrupted.

6. **`logger.remove()` in tests is a disaster**: loguru documentation suggests `logger.remove()` in tests to clear handlers. But tests run concurrently (pytest-xdist) -- one test removes handlers, another test's logs disappear. This is **untestable design**.

7. **The code reader is confused**: Seeing `from loguru import logger`, you cannot answer: what handlers does this logger have? Where do logs go? What format? What level? -- You need a global grep for `logger.add()` and `logger.configure()` to piece together the answer.

## Good Code: structlog + Explicit Configuration

```python
# services/payment.py
import structlog

logger = structlog.get_logger(__name__)  # not a global singleton -- managed by structlog.configure()


class PaymentService:
    async def charge(self, order_id: str) -> dict:
        # structured event, not string interpolation
        logger.info("payment_charge_started", order_id=order_id)
        ...


# services/notification.py
import structlog

logger = structlog.get_logger(__name__)


class NotificationService:
    async def send(self, user_id: str, msg: str) -> None:
        logger.info("notification_sent", user_id=user_id, msg_len=len(msg))
        ...


# main.py -- log configuration at application entry point, NOT at module top-level
def configure_logging(*, debug: bool = False) -> None:
    import structlog
    import logging

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO,
        ),
        cache_logger_on_first_use=True,
    )


# tests/test_payment.py
import structlog
import logging
import pytest


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog to test config before each test -- no cross-test pollution."""
    structlog.configure(
        processors=[structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        cache_logger_on_first_use=True,
    )


async def test_charge():
    svc = PaymentService()
    result = await svc.charge("order_42")
    assert result["status"] == "ok"
    # Next test's logger is unaffected -- structlog.configure() is idempotent
```

## Why It's Good / Key Differences

- **No global singleton**: `structlog.get_logger()` returns a logger bound to the module name, but the processor chain is managed centrally by `structlog.configure()`. Module-level `logger = structlog.get_logger(__name__)` is not a mutable object -- it is a reference to a binding point.
- **Explicit configuration entry point**: The log processing pipeline is configured once in `main()` or `app_factory()`, never scattered across `logger.add()` calls.
- **Test isolation**: `structlog.configure()` is idempotent -- every test can safely call it to set up test configuration without affecting other tests.
- **Structured events**: `logger.info("payment_charge_started", order_id=order_id)` produces a dict that log aggregation systems can index.

> Core principle: Never permit a global mutable singleton -- especially for logging, which cuts across the entire process. Configure explicitly once; everywhere is predictable.
