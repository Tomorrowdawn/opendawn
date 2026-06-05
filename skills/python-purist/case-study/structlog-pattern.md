---
title: "Structlog Pattern: Structured Events, Not Strings"
category: case-study
tags:
  - structlog
  - structured-logging
  - observability
  - context
  - trace-id
related:
  - ../best-practice/structured-logging.md
  - ../best-practice/explicit-over-implicit.md
  - event-bus-observability.md
summary: "Traditional stdlib logging with %-formatting hides event data in opaque strings. structlog treats log entries as typed dicts with automatic context propagation — making production debugging possible without reproduction."
---

# Structlog Pattern: Structured Events, Not Strings

## Scenario

You run an order processing service: receive HTTP request → validate inventory → charge payment → update database → send notification. Tens of thousands of orders per day in production. When an order fails, you are hunting through a sea of `2026-06-05 14:23:01,045 - orders - INFO - Processing order 42` -- blind to trace_id, blind to API latency, blind to what the upstream returned.

## Bad Code: stdlib Logging String Hell

```python
import logging
import time
import httpx

logger = logging.getLogger(__name__)

async def process_order(order_id: str, amount: int) -> dict:
    logger.info("Processing order %s with amount %s", order_id, amount)

    try:
        start = time.perf_counter()
        resp = await httpx.AsyncClient().post(
            "https://payment.example.com/charge",
            json={"order_id": order_id, "amount": amount},
        )
        elapsed = time.perf_counter() - start
        logger.info(
            "Payment API returned %s for order %s in %.2fs",
            resp.status_code, order_id, elapsed,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Order %s payment success, tx_id=%s", order_id, data["tx_id"])
        return data
    except httpx.HTTPStatusError as e:
        logger.error(
            "Payment API error for order %s: %s %s",
            order_id, e.response.status_code, e.response.text,
        )
        raise
    except Exception:
        logger.exception("Unexpected error processing order %s", order_id)
        raise
```

## Why It's Bad

1. **Data embedded in strings**: `"Processing order %s with amount %s"` -- order_id and amount are part of an opaque string, not structured fields. Want to filter for "orders with amount > 10000"? You need a regex against log text.
2. **Inconsistent format**: First log is `"Processing order %s with amount %s"`, second is `"Payment API returned %s for order %s in %.2fs"`, third is `"Order %s payment success, tx_id=%s"` -- field names and ordering differ every time. Elasticsearch/Loki cannot auto-index.
3. **Context passed manually**: `request_id` and `user_id` must be manually spliced into every `logger.info()` call. Miss one? That log entry loses its context.
4. **Timing code invades business logic**: `time.perf_counter()` scattered in every try/except block -- repetitive and easy to omit.
5. **No type safety**: `logger.info("msg %s", 42)` and `logger.info("msg %s", "hello")` are both legal -- the type checker cannot help you.

## Good Code: Using structlog

```python
from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()


async def process_order(order_id: str, amount: int) -> dict:
    """Process an order -- zero boilerplate, zero manual timing."""

    # contextvars auto-propagate request_id/user_id; no manual threading needed
    logger.info(
        "order_processing_started",
        order_id=order_id,
        amount=amount,
    )

    try:
        resp = await httpx.AsyncClient().post(
            "https://payment.example.com/charge",
            json={"order_id": order_id, "amount": amount},
        )
        resp.raise_for_status()
        data = resp.json()

        logger.info(
            "order_payment_success",
            order_id=order_id,
            tx_id=data["tx_id"],
            status=resp.status_code,
        )
        return data

    except httpx.HTTPStatusError:
        logger.exception(
            "order_payment_failed",
            order_id=order_id,
            status=resp.status_code,
            response_body=resp.text[:500],
        )
        raise

    except Exception:
        logger.exception(
            "order_processing_unexpected_error",
            order_id=order_id,
        )
        raise
```

Output (production JSON mode):
```json
{
  "event": "order_payment_success",
  "order_id": "42",
  "tx_id": "tx_abc123",
  "status": 200,
  "request_id": "req_7f3a1b2c",
  "user_id": "user_99",
  "timestamp": "2026-06-05T14:23:01.045Z",
  "level": "info"
}
```

## Why It's Good / Key Differences

1. **Events are dicts, not strings**: `logger.info("order_payment_success", order_id=order_id, tx_id=data["tx_id"])` produces key-value pairs. Log aggregation systems (ELK, Loki, Datadog) can index `order_id`, `tx_id`, `status` directly -- no regex parsing required.
2. **Consistent field naming**: Every event uses `order_id`, not sometimes `order_id`, sometimes `order`, sometimes `id`. Query `order_id:"42"` in Grafana and find every log entry for that order.
3. **Context propagates automatically**: HTTP middleware binds with `structlog.contextvars.bind_contextvars(request_id=..., user_id=...)`. At any depth inside `process_order`, those fields appear in every log entry without manual threading.
4. **Timing separated from business logic**: Use a `@timed` decorator (see `decorator-pattern.md`) or structlog's `TimeStamper` processor -- business functions focus on business logic only.
5. **Rendering deferred to the last moment**: Business code never knows whether the final output is colored text or JSON. Dev uses `ConsoleRenderer`, prod uses `JSONRenderer` -- switch once in `configure_logging()`.

> Core principle: Logging is the emission of structured events. Events are dicts at creation time; they are rendered to strings at consumption time (writing to stderr / sending to aggregator). That rendering step does not live in your business code.
