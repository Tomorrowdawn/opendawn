---
title: "Structured Logging & Observability"
category: best-practice
tags:
  - logging
  - structured-logging
  - structlog
  - observability
  - errors
  - stderr
related:
  - ../case-study/structlog-pattern.md
  - ../case-study/loguru-antipattern.md
  - ../case-study/print-is-not-logging.md
  - ../case-study/exception-swallowing.md
summary: "Logging is event emission, not string formatting. Use structlog for structured events. Never print(). Never log to files from application code. Every log event must carry diagnostic context."
---

# Structured Logging & Observability

## Principle

**Logging is the emission of structured events, not string formatting.** Your application must never manage log files, log rotation, or log transport -- those are the responsibilities of the operating system and process manager. Every log event must carry enough context that you can diagnose issues without reproducing the environment.

## Why Logging Needs a Rethink

The Python community's approach to logging is fragmented: the stdlib `logging` module ships with terrible defaults (bare `WARNING` level, no formatter, no handler), `loguru` seduces you into implicit global mutable state, and `print()` is a bad habit that must be banned from day one.

Correct logging philosophy rests on three pillars:

1. **Structured events** -- A log entry is not a string; it is a dictionary of key-value pairs. Rendering (converting to text) happens downstream.
2. **Boundary recording** -- Every I/O call crossing a system boundary (HTTP, database, subprocess, message queue) must produce a log event.
3. **Context propagation** -- trace_id, request_id, and user_id must span the entire request lifecycle, not be reconstructed in every function.

## Tool Choice: structlog -- The Only Logging Library You Need

You **must** use [`structlog`](https://www.structlog.org/). It is the only Python logging library that embodies "explicit over implicit" to its core -- created by Hynek Schlawack, inheriting the design philosophy of `attrs`.

```python
import structlog

logger = structlog.get_logger()
```

Core concepts of `structlog`:

| Concept | Explanation |
|---------|-------------|
| **Log events are dicts** | `logger.info("order_placed", order_id="42", amount=100)` produces `{"event": "order_placed", "order_id": "42", "amount": 100}` |
| **Processor chain** | Events pass through a chain of processors before reaching the final renderer. Timestamps, log levels, caller info -- all handled in processors, never polluting business code. |
| **Context binding** | `log = logger.bind(user_id="42")` returns a new logger. All subsequent logs automatically carry `user_id`. Explicit, immutable, zero global state. |
| **Rendering is separate** | Development uses `structlog.dev.ConsoleRenderer` (color, human-readable). Production uses `structlog.processors.JSONRenderer` (machine-parseable). Business code never knows the difference. |

### structlog Configuration (place in `main()` or `app_factory()`)

```python
import structlog
import logging

def configure_logging(*, debug: bool = False) -> None:
    """Called once at application startup. Configures the global log pipeline."""
    level = logging.DEBUG if debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,   # merge contextvars into event
        structlog.processors.add_log_level,        # add "level" key
        structlog.processors.TimeStamper(fmt="iso"), # add "timestamp" key
        structlog.processors.StackInfoRenderer(),   # add stack info on exception
    ]

    if debug:
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            cache_logger_on_first_use=True,
        )
```

## Why You Must Reject loguru

`loguru` is one of the most seductive traps in the Python ecosystem. Its API is concise (`from loguru import logger`), but conciseness comes at the cost of **implicit global mutable state** -- violating the first law of this skill.

See `case-study/loguru-antipattern.md` for the full analysis. One-sentence summary: **you must never use loguru.** If you are using it now, migrate to structlog immediately.

## Why You Must Reject `print()`

`print()` is not logging. See `case-study/print-is-not-logging.md` for details. Core problems:

- No log levels -- you cannot silence DEBUG output in production.
- Writes to stdout, not stderr -- pollutes the normal output stream.
- No structured data -- unparseable by log aggregation systems.
- No context propagation -- trace_id cannot be attached automatically.

**You must never use `print()` in application code.** The sole exception is a CLI tool printing final user-facing output -- and that is not logging.

## Log Output: Always Write to stderr

Your application **must never** open log files, manage log rotation, or connect directly to log aggregation services. These are the responsibilities of the operating system and infrastructure.

```python
# ❌ NEVER -- application manages log files
import logging
logging.basicConfig(
    filename="/var/log/myapp/app.log",
    level=logging.INFO,
)

# ✅ ALWAYS -- write to stderr, let the process manager handle it
import logging
import sys
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(message)s",  # minimal format -- let downstream handle rendering
)
```

At the deployment layer:
- **Development**: Terminal displays stderr directly.
- **Production (systemd)**: `journald` captures stderr automatically → `journalctl -u myapp`.
- **Production (Docker)**: Docker log driver collects stdout/stderr → `docker logs` or ELK/Loki.
- **Production (bare metal / supervisord)**: supervisord redirects stderr to files, paired with `logrotate`.

Core conviction: **applications emit events; the platform transports and stores them.**

## Log Context Must Propagate

An HTTP request passes through auth middleware → business logic → database query → external API call. When it fails, you need the full call chain in the logs. Context must propagate automatically, not be manually threaded through every function call.

```python
import structlog
import uuid

logger = structlog.get_logger()

async def handle_request(request: Request) -> Response:
    """Generate a unique ID per request and bind it to the logging context."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    with structlog.contextvars.bound_contextvars(
        request_id=request_id,
        user_id=getattr(request, "user_id", None),
        path=request.path,
    ):
        logger.info("request_started", method=request.method)
        try:
            result = await process_request(request)
            logger.info("request_completed", status=200)
            return result
        except Exception:
            logger.exception("request_failed")
            raise
```

At any depth inside `process_request` → `query_database` → `call_external_api`, `logger.error("db_timeout")` produces a log event that **automatically** includes `request_id`, `user_id`, and `path` -- no explicit argument threading required.

## Boundary Logging: Every I/O Boundary Must Be Recorded

If you cannot answer "which external systems did this request touch, and how long did each take?" from your logs alone, your logging is insufficient.

```python
import time

async def query_database(query: str, params: tuple) -> list[dict]:
    start = time.perf_counter()
    try:
        rows = await pool.fetch(query, *params)
        elapsed = time.perf_counter() - start
        logger.debug(
            "db_query_success",
            query=query[:100],
            row_count=len(rows),
            duration_ms=round(elapsed * 1000, 2),
        )
        return rows
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception(
            "db_query_failed",
            query=query[:100],
            duration_ms=round(elapsed * 1000, 2),
        )
        raise
```

You **must** record: operation name, duration in milliseconds, success/failure status, and a summary of key parameters (never log secrets or PII).

## Error Logging: Stack Traces Alone Are Not Enough

When an exception occurs, `logger.exception()` alone -- which only captures the stack trace -- is **not enough**. You must simultaneously record the input data and intermediate state that led to the exception.

```python
# ❌ NOT ENOUGH -- stack trace tells you "where" but not "why"
try:
    result = await process_payment(order)
except PaymentError:
    logger.exception("payment_failed")  # no order_id, no amount

# ✅ ALWAYS -- context + stack trace = full diagnosability
try:
    result = await process_payment(order)
except PaymentError:
    logger.exception(
        "payment_failed",
        order_id=order.id,
        amount=order.total,
        payment_method=order.method,
        retry_count=retries,
    )
```

## Log Level Discipline

You **must** strictly follow this level convention:

| Level | When to Use | Must Not Be Used For |
|-------|-------------|---------------------|
| **DEBUG** | Development diagnostics: variable values, intermediate state, detailed SQL | Off by default in production |
| **INFO** | Key business events: request start/end, payment success, user registration | High-frequency polling, heartbeats (use DEBUG) |
| **WARNING** | Recoverable anomalies: retry success, graceful degradation, quota near limit | Routine events requiring no human attention |
| **ERROR** | Unrecoverable but non-fatal errors: single request failure, external API timeout | Application startup failure (use CRITICAL or crash outright) |
| **CRITICAL** | System-level failures: all database connections lost, out of memory | Individual user operation failures |

**You must never** call `logger.debug()` in business code -- DEBUG is for development and troubleshooting only. **You must never** tag every exception as ERROR -- a retryable timeout is WARNING; a user input error is INFO.

## Summary

| Do | How |
|----|-----|
| Logging library | structlog only -- reject loguru, reject bare stdlib logging |
| Log format | Structured dicts -- JSON for machines, ConsoleRenderer for humans |
| Log output | stderr only -- never open files in application code |
| Log context | `structlog.contextvars` for request_id/user_id -- automatic propagation |
| Boundary logging | Every I/O call records: operation name, duration, status, key params |
| Error logging | `logger.exception()` + input data context -- stack traces alone are not enough |
| Log levels | Strict DEBUG/INFO/WARNING/ERROR/CRITICAL discipline |
| print() | Never allowed -- print is not logging |

**Core lesson: Logging is the emission of structured events, not printf debugging. Your application is responsible only for producing events -- the platform handles transport, storage, and rendering.**
