---
title: "hasattr() – A Dangerous Misnomer"
category: case-study
tags:
  - hasattr
  - getattr
  - implicit
  - attribute-error
  - explicit-over-implicit
  - property
related:
  - ../best-practice/explicit-over-implicit.md
summary: "hasattr() silently swallows AttributeErrors in properties on Python 2 and behaves inconsistently across versions. Use try/except AttributeError or getattr() with a sentinel instead."
---

# hasattr() -- A Dangerous Misnomer

## Scenario

You are writing a function that accepts objects from third-party libraries. You need to check whether an attribute exists before accessing it. `hasattr()` looks like the obvious tool.

## Bad Code: hasattr() Abuse

```python
class UserProfile:
    def __init__(self, data: dict):
        self._data = data

    @property
    def subscription(self) -> str:
        # This property performs a database query!
        return self._fetch_subscription_from_db()

    def _fetch_subscription_from_db(self) -> str:
        # If the DB is down, this raises DatabaseError
        ...


def send_notification(user: UserProfile) -> None:
    if hasattr(user, "subscription"):      # ← executes the property getter!
        plan = user.subscription           # ← executes it AGAIN
        print(f"Sending to {plan} user")
    else:
        print("No subscription -- skipping")
```

## Why It's Bad

1. **`hasattr()` executes the property getter**: `hasattr(user, "subscription")` does not check whether the attribute "exists" -- it calls `getattr(user, "subscription")` internally and catches **all** exceptions. If the property raises `DatabaseError`, `hasattr()` returns `False` -- silently swallowing the real error.

2. **Python 2 vs Python 3 behavior divergence**: On Python 2, `hasattr()` catches `except:` (bare except -- swallows even `KeyboardInterrupt`). A property that raises **any** exception causes `hasattr()` to return `False`. On Python 3, `hasattr()` only catches `AttributeError` -- but a property that crashes with `ZeroDivisionError` still returns `False` on Python 2 and propagates the error on Python 3. Hybrid codebases get inconsistent behavior.

3. **Double lookup**: If `hasattr()` returns `True`, you then access the attribute a second time. The property getter runs twice -- doubling any side effects (database queries, network calls).

4. **Code reader deception**: `if hasattr(obj, "x")` looks like a cheap existence check. The reader does not expect it to trigger arbitrary code execution. This is the definition of implicit behavior.

5. **`hasattr()` is not faster than `getattr()`**: Both go through the same attribute lookup machinery in CPython. `hasattr()` simply discards the result. There is zero performance justification.

## Good Code: try/except or getattr() with Sentinel

```python
class UserProfile:
    def __init__(self, data: dict):
        self._data = data
        self._cached_subscription: str | None = None

    @property
    def subscription(self) -> str | None:
        if self._cached_subscription is None:
            self._cached_subscription = self._fetch_from_db()
        return self._cached_subscription

    def _fetch_from_db(self) -> str | None:
        ...


# Approach 1: try/except AttributeError -- explicit and safe
def send_notification(user: UserProfile) -> None:
    try:
        plan = user.subscription  # single lookup
    except AttributeError:
        print("No subscription -- skipping")
        return

    print(f"Sending to {plan} user")


# Approach 2: getattr() with sentinel -- when None is a valid value
_MISSING = object()

def send_notification(user: UserProfile) -> None:
    plan = getattr(user, "subscription", _MISSING)
    if plan is _MISSING:
        print("No subscription -- skipping")
        return

    print(f"Sending to {plan} user")
```

## Why It's Good / Key Differences

- **Single attribute lookup**: `try/except` and `getattr()` each access the attribute once. No double execution of property getters.
- **Only catches `AttributeError`**: `try: ... except AttributeError:` catches exactly what it says. A `DatabaseError` propagates up to the caller -- where it belongs. No silent swallowing.
- **Consistent across Python versions**: `try/except AttributeError` behaves identically on Python 2 and 3. No version-specific surprises.
- **Explicit intent**: `try/except AttributeError` tells the reader: "I expect this attribute might not exist, and here's what I'll do." `getattr(obj, "x", default)` tells the reader: "Give me x if it exists; otherwise use this default."

> Core principle: `hasattr()` lies about what it does. It does not check for the *existence* of an attribute -- it tries to *get* it and swallows exceptions. In your own code, use `try/except AttributeError`. For third-party objects, **especially** use `try/except AttributeError`. Never use `hasattr()`.
