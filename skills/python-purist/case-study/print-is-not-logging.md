---
title: "Print is Not Logging: The Most Common Bad Habit"
category: case-study
tags:
  - logging
  - print
  - anti-pattern
  - stdout
  - stderr
  - observability
related:
  - ../best-practice/structured-logging.md
  - ../best-practice/explicit-over-implicit.md
summary: "print() has no log levels, no structured data, no context propagation, and writes to stdout. It is never acceptable as a logging mechanism in application code."
---

# Print is Not Logging: The Most Common Bad Habit

## Scenario

You are building a backend service. As the processing logic grows complex, you start inserting `print()` statements to understand execution flow. Those print statements remain in the code and ship to production.

## Bad Code: print() as Debugging

```python
async def sync_user_data(user_id: str) -> dict:
    """Sync user data from external API to local database."""
    print(f"Starting sync for user {user_id}")  # ← is this logging?

    try:
        profile = await fetch_profile(user_id)
        print(f"Fetched profile: {profile}")  # ← leaking PII!

        orders = await fetch_orders(user_id)
        print(f"Fetched {len(orders)} orders")

        await save_to_db(user_id, profile, orders)
        print("Sync complete")
        return {"status": "ok", "orders": len(orders)}
    except Exception as e:
        print(f"Sync failed: {e}")  # ← no stack trace, no context
        return {"status": "error", "message": str(e)}
```

## Why It's Bad

1. **No log levels**: `print("syncing user 42")` and `print("database connection pool exhausted, system collapsing")` look identical. You cannot silence DEBUG output in production. You cannot configure alerts on ERROR. Every print statement is treated equally.

2. **Writes to stdout, not stderr**: `print()` writes to `sys.stdout` by default. stdout is your program's **normal output stream** -- if your CLI tool returns JSON to a pipeline downstream, print-logging **corrupts the output format**. Diagnostic information belongs on `sys.stderr`.

3. **No structured data**: `print(f"Fetched {len(orders)} orders")` is an opaque string. You cannot filter by `user_id` in ELK. You cannot aggregate sync durations. You cannot alert on "sync failure rate above 5%." Log aggregation systems see only lines of text.

4. **No context propagation**: `print("Sync complete")` has no trace_id, no user_id, no duration. When 10 concurrent requests all print "Sync complete," you cannot tell them apart.

5. **Leaks sensitive information**: `print(f"Fetched profile: {profile}")` dumps user name, email, and address directly into terminal/container logs. This data must never appear in logs -- GDPR/PCI compliance risk.

6. **Not redirectable or filterable**: stdout is global -- you cannot route `sync_user_data` logs to `sync.log` and `process_payment` logs to `payment.log`. print() offers no such flexibility.

7. **Breaks coroutine/thread safety**: print is not thread-safe -- output from two coroutines can interleave: `Starting sync for user 42Starting sync for user 99Fetched profile...`. The logging module guarantees atomic writes.

## Good Code: structlog + Correct Logging Practice

```python
import structlog

logger = structlog.get_logger(__name__)

async def sync_user_data(user_id: str) -> dict:
    """Sync user data from external API to local database."""
    logger.info("sync_started", user_id=user_id)

    try:
        profile = await fetch_profile(user_id)
        # Log summary, not full data -- privacy protection
        logger.debug(
            "profile_fetched",
            user_id=user_id,
            has_email=bool(profile.get("email")),
            has_address=bool(profile.get("address")),
        )

        orders = await fetch_orders(user_id)
        logger.info(
            "orders_fetched",
            user_id=user_id,
            order_count=len(orders),
            total_amount=sum(o.get("amount", 0) for o in orders),
        )

        await save_to_db(user_id, profile, orders)
        logger.info(
            "sync_completed",
            user_id=user_id,
            order_count=len(orders),
        )
        return {"status": "ok", "orders": len(orders)}

    except Exception:
        logger.exception(
            "sync_failed",
            user_id=user_id,
        )
        raise  # re-raise; let the caller decide how to handle
```

Output (production JSON):
```json
{"event": "sync_started", "user_id": "42", "level": "info", "timestamp": "2026-06-05T14:23:01.045Z", "request_id": "req_abc"}
{"event": "orders_fetched", "user_id": "42", "order_count": 5, "total_amount": 12345, "level": "info", ...}
{"event": "sync_completed", "user_id": "42", "order_count": 5, "level": "info", ...}
```

## Why It's Good / Key Differences

- **Precise log levels**: `logger.info` for key events, `logger.debug` for diagnostic details -- selectively disabled in production.
- **Structured fields are queryable**: In Loki/ELK: `{user_id="42"} |= "sync_completed"` finds every sync log for that user. `sum by(user_id) (count_over_time({event="sync_completed"}[1h]))` counts sync frequency per user.
- **Context propagates automatically**: `request_id` bound by middleware to structlog contextvars -- no manual threading required.
- **Privacy protection**: Log `has_email` boolean instead of the full email address -- satisfies debugging needs without leaking PII.
- **`logger.exception()` includes the stack trace**: Exception info is automatically attached alongside context.
- **Output to stderr**: structlog writes to `sys.stderr` by default; stdout is never polluted.

> Core principle: `print()` is for one-off REPL checks, not application logging. The moment code leaves your local terminal, `print()` is a bug. Never permit `print()` on a production code path.
