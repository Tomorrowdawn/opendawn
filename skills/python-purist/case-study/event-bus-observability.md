---
title: "Event Bus for Observability: Telemetry Without Invasion"
category: case-study
tags:
  - event-bus
  - observability
  - metrics
  - tracing
  - alerting
  - telemetry
  - decoupling
related:
  - ../best-practice/structured-logging.md
  - ../best-practice/explicit-over-implicit.md
  - structlog-pattern.md
  - observer-pattern.md
summary: "A lightweight async event bus dedicated to observability — metrics, traces, and alerts subscribe to domain events without invading core logic. Not structlog, not a logging pipeline — a separate telemetry channel with fault isolation, async dispatch, and per-environment assembly."
---

# Event Bus for Observability: Telemetry Without Invasion

## Scenario

You run a payment processing service. Every time a payment succeeds, you need to: increment a Prometheus counter, record a span in OpenTelemetry, flush a trace annotation to Datadog, and — if the amount exceeds $10,000 — trigger a Slack alert. Today you have four observability calls embedded directly inside `process_payment()`. Tomorrow the infrastructure team adds a fifth: write to an audit log in S3.

## Bad Code: Observability Embedded in Core Logic

```python
from __future__ import annotations

import prometheus_client
from opentelemetry import trace
import structlog

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

payment_counter = prometheus_client.Counter(
    "payment_total", "Total payments", ["status", "currency"],
)

async def process_payment(order_id: str, amount: int, currency: str) -> dict:
    # --- observability starts invading here ---
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("order_id", order_id)
        span.set_attribute("amount", amount)

        try:
            result = await _charge(order_id, amount, currency)

            payment_counter.labels(status="success", currency=currency).inc()
            span.set_attribute("tx_id", result["tx_id"])

            logger.info(
                "payment_success",
                order_id=order_id,
                amount=amount,
                currency=currency,
                tx_id=result["tx_id"],
            )

            # Alert for large payments — another hard-coded side channel
            if amount > 10000:
                await slack_alert(f"Large payment: {order_id} ${amount}")

            return result

        except PaymentError:
            payment_counter.labels(status="failed", currency=currency).inc()
            span.record_exception()
            span.set_status(trace.StatusCode.ERROR)
            logger.exception("payment_failed", order_id=order_id)
            raise
```

## Why It's Bad

1. **Core logic is buried under telemetry**: `process_payment` is 30 lines. Only 3 lines (`_charge` + `return`) are actual business logic. The other 27 lines are observability — metrics, traces, logging, alerting. Reading this function, you cannot find the business intent without scanning past a wall of instrumentation.

2. **Every new telemetry concern modifies core logic**: Adding Datadog APM markers? Edit `process_payment`. Adding S3 audit log? Edit `process_payment`. Adding cost attribution tags? Edit every function that processes money. Each change risks breaking the business logic.

3. **Different concerns share the same failure domain**: If `slack_alert()` hangs because Slack is down, `process_payment` hangs. If the Prometheus pushgateway returns 503, the payment fails. Telemetry outages should never cause business logic outages — but when they share the same call stack, they do.

4. **Not the structlog processor chain either**: You might think: "structlog processors can fan out events — can't I just put metrics/traces/alerts there?" **No.** structlog's processor chain is synchronous, single-threaded, and runs in the logging hot path. A slow metrics push blocks all logging. A crashed subscriber breaks the entire logging pipeline. structlog is for logging, not telemetry routing. (If you need error forwarding to Sentry, use `structlog-sentry` — that is the one legitimate processor-as-subscriber pattern. See `structlog-pattern.md` for details.)

5. **Environment-specific concerns leak into shared code**: Production is the only environment that needs Datadog tracing. Staging uses a different Prometheus instance. Development needs none of this. But the code is identical across environments — you must either pollute dev with unnecessary telemetry or patch functions at runtime.

## Good Code: Dedicated Async Event Bus

```python
from __future__ import annotations

import asyncio
import structlog
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = structlog.get_logger(__name__)

# ── Domain Event (immutable, typed) ──────────────────────────────────────

@dataclass(frozen=True)
class PaymentCompleted:
    """A domain event — not a log entry, not a metric. Pure data."""
    order_id: str
    amount: int
    currency: str
    tx_id: str
    duration_ms: float


# ── Subscriber Protocol ──────────────────────────────────────────────────

class TelemetrySubscriber(Protocol):
    """Every observability concern implements this protocol.
       Subscribers receive domain events and export them to their backend.
       They must never mutate the event or raise into the bus."""

    async def on_event(self, event: object) -> None: ...


# ── Event Bus ────────────────────────────────────────────────────────────

@dataclass
class TelemetryEventBus:
    """A lightweight async event bus dedicated to observability.

       This is NOT a logging pipeline. This is NOT a general-purpose pub/sub
       for business coordination (see observer-pattern.md for that). This is
       a telemetry channel: domain events → observability exporters.
    """

    _subscribers: list[TelemetrySubscriber] = field(default_factory=list)

    def subscribe(self, subscriber: TelemetrySubscriber) -> None:
        """Register a subscriber. Call at composition root, never in business code."""
        self._subscribers.append(subscriber)

    async def emit(self, event: object) -> None:
        """Fan out a domain event to all subscribers.

           Guarantees:
           1. Fault isolation — one subscriber's failure does not affect others.
           2. Async dispatch — subscribers can perform I/O (push metrics, flush traces).
           3. Fire-and-forget from the caller's perspective — the bus owns the fan-out.
        """
        results = await asyncio.gather(
            *(self._safe_dispatch(sub, event) for sub in self._subscribers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "telemetry_subscriber_failed",
                    subscriber=type(self._subscribers[i]).__name__,
                    event=type(event).__name__,
                    error=str(result),
                )

    @staticmethod
    async def _safe_dispatch(subscriber: TelemetrySubscriber, event: object) -> None:
        """Dispatch to a single subscriber. The try/except here, combined with
           asyncio.gather(return_exceptions=True), guarantees that a subscriber
           crash never propagates to the caller or to other subscribers."""
        try:
            await subscriber.on_event(event)
        except Exception:
            logger.exception(
                "telemetry_subscriber_error",
                subscriber=type(subscriber).__name__,
                event=type(event).__name__,
            )
            # Intentionally swallowed — telemetry failures must never
            # break the application. The warning log above is sufficient.


# ── Subscriber Implementations ────────────────────────────────────────────

class PrometheusMetricsSubscriber:
    """Exports domain events as Prometheus counters and histograms."""

    def __init__(self) -> None:
        self._counter: Any = None  # prometheus_client.Counter — initialized in setup

    async def on_event(self, event: object) -> None:
        if isinstance(event, PaymentCompleted):
            self._counter.labels(
                status="success",
                currency=event.currency,
            ).inc()


class OpenTelemetryTracingSubscriber:
    """Records domain events as OpenTelemetry span events."""

    async def on_event(self, event: object) -> None:
        if not isinstance(event, PaymentCompleted):
            return
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(
                "payment_completed",
                attributes={
                    "order_id": event.order_id,
                    "amount": event.amount,
                    "tx_id": event.tx_id,
                    "duration_ms": event.duration_ms,
                },
            )


class SlackAlertSubscriber:
    """Sends Slack alerts for high-value events. Configurable threshold."""

    def __init__(self, threshold_cents: int, webhook_url: str) -> None:
        self._threshold = threshold_cents
        self._webhook = webhook_url

    async def on_event(self, event: object) -> None:
        if isinstance(event, PaymentCompleted) and event.amount >= self._threshold:
            await _post_slack(self._webhook, f"Large payment: {event.order_id} ${event.amount}")


class AuditLogSubscriber:
    """Writes structured audit events — environment-aware (dev → no-op)."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled

    async def on_event(self, event: object) -> None:
        if not self._enabled:
            return
        logger.info(
            "audit_event",
            event_type=type(event).__name__,
            event_data=str(event),  # in production: serialize to S3 / Kafka
        )


# ── Assembly at Composition Root (per-environment) ────────────────────────

def build_telemetry_bus(*, env: str) -> TelemetryEventBus:
    """Assemble the telemetry bus for the current environment.

       Dev gets a minimal bus (logging only). Staging gets metrics + audit.
       Production gets everything — metrics, traces, alerts, audit.
       The bus assembly is the ONLY place that knows about the environment."""

    bus = TelemetryEventBus()

    # Always on — structured logging subscriber
    bus.subscribe(AuditLogSubscriber())

    if env in ("staging", "production"):
        bus.subscribe(PrometheusMetricsSubscriber())

    if env == "production":
        bus.subscribe(OpenTelemetryTracingSubscriber())
        bus.subscribe(SlackAlertSubscriber(
            threshold_cents=10_000_00,  # $10,000
            webhook_url="https://hooks.slack.com/...",
        ))

    return bus


# ── Core Logic (clean, no telemetry) ─────────────────────────────────────

async def process_payment(
    order_id: str,
    amount: int,
    currency: str,
    bus: TelemetryEventBus,
) -> dict:
    """Process a payment. Pure business logic — zero observability code."""

    start = asyncio.get_event_loop().time()
    try:
        result = await _charge(order_id, amount, currency)
        elapsed = (asyncio.get_event_loop().time() - start) * 1000

        # Emit domain event — the bus handles everything downstream
        await bus.emit(PaymentCompleted(
            order_id=order_id,
            amount=amount,
            currency=currency,
            tx_id=result["tx_id"],
            duration_ms=elapsed,
        ))

        return result

    except PaymentError:
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        await bus.emit(PaymentFailed(
            order_id=order_id,
            amount=amount,
            currency=currency,
            duration_ms=elapsed,
        ))
        raise
```

## Why It's Good / Key Differences

1. **Core logic is pure**: `process_payment` contains business logic and one line: `await bus.emit(PaymentCompleted(...))`. The event is a typed dataclass — the compiler verifies its shape. All telemetry concerns live in subscribers, not in business functions.

2. **Each subscriber is independently owned and tested**: `PrometheusMetricsSubscriber` can be tested with a fake Prometheus registry. `SlackAlertSubscriber` can be tested with a fake HTTP endpoint. No subscriber test requires the payment processing logic to run.

3. **Fault isolation is architectural, not aspirational**: `_safe_dispatch` wraps every subscriber in try/except. `asyncio.gather(return_exceptions=True)` collects failures without propagating them. If Slack is down, Prometheus still records. If Prometheus is slow, OpenTelemetry still traces. A subscriber crash is logged as a warning and never reaches the business caller.

4. **Per-environment assembly, zero code branches**: `build_telemetry_bus(env="dev")` returns a bus with only the audit logger. `build_telemetry_bus(env="production")` returns the full stack. The subscribers themselves contain no `if env == "production"` checks. The assembly function is the single source of truth.

5. **Not structlog, not a logging pipeline**: This is a deliberate distinction. structlog handles **structured log events** — what happened, when, with what context. The telemetry event bus handles **domain events routed to observability infrastructure** — metrics, traces, alerts. They serve different purposes:
   - structlog → stderr → log aggregator (ELK, Loki)
   - TelemetryEventBus → Prometheus pushgateway, OTLP collector, Slack webhook

   Confusing the two pipelines — e.g., routing Prometheus metrics through structlog processors — creates a fragile architecture where logging latency blocks metrics collection and a logging crash silences your dashboards.

6. **Composable with the existing `observer-pattern.md`**: The business event bus in `observer-pattern.md` handles inter-module communication (cache invalidation, audit logging as a business concern). The telemetry event bus handles infrastructure-facing telemetry. A single domain event can be emitted on both buses — but the buses themselves serve different audiences and have different failure semantics.

> Core principle: Observability is a first-class architectural concern with its own failure domain, its own performance budget, and its own environment-specific assembly. Embedding telemetry calls in business logic conflates two concerns that must fail independently. Use a dedicated async event bus — not structlog processors, not inline SDK calls — to route domain events to observability infrastructure.

