---
title: "Mutable Hash Keys: The Hash Contract Violation"
category: case-study
tags:
  - hash
  - equality
  - dict
  - set
  - mutable
  - type-safety
related:
  - ../best-practice/type-safety.md
  - ../best-practice/fail-fast.md
summary: "Using mutable objects as dict keys or set elements violates Python's hash contract. The object disappears from the collection after mutation, creating silent data loss. Use frozen/immutable objects or hash only an immutable subset of fields."
---

# Mutable Hash Keys: The Hash Contract Violation

## Scenario

You define a class representing a point in 2D space. You make it hashable so it can be used as a dict key. You later mutate the point's coordinates. The dict silently loses track of the entry.

## Bad Code: Mutable Object as Dict Key

```python
@dataclass
class Point:
    x: int
    y: int

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y


# Construction and insertion -- works fine
points: dict[Point, str] = {}
p = Point(x=1, y=2)
points[p] = "originally (1,2)"

assert p in points          # True
assert points[p] == "originally (1,2)"  # True

# Mutation -- the contract is violated
p.x = 999

# The object is now in a ghost state:
assert p in points          # False -- Python claims it was never there!
assert points  # {Point(x=999, y=2): "originally (1,2)"} -- but it IS there!
```

## Why It's Bad

1. **Violates Python's hash contract**: The language specification requires that **the hash of an object must never change during its lifetime.** Dict and set lookups use the hash to locate the bucket. After mutation, `hash(p)` returns a new value. Python looks in a different bucket, finds nothing, and reports the key is absent -- even though the entry still exists in the old bucket.

2. **Silent data loss with no error**: No exception is raised. No warning is emitted. The entry becomes a ghost -- present in the dict's internal storage but unreachable through normal key lookup. Over time, these ghost entries accumulate, leaking memory and silently corrupting application state.

3. **`__contains__` lies**: `p in points` returns `False` for an object that is visually present in the dict's `__repr__`. Any code relying on `in` checks for deduplication or caching will produce incorrect results.

4. **Re-insertion creates duplicates**: If you insert the mutated `p` again, the dict now contains **two** entries with logically equal keys -- one in the old hash bucket, one in the new. `len(points)` increases. Iteration yields duplicates.

## Good Code: Immutable Objects (Preferred)

```python
@dataclass(frozen=True)  # frozen=True makes it immutable AND generates correct __hash__
class Point:
    x: int
    y: int

# Every modification creates a new instance
p = Point(x=1, y=2)
points: dict[Point, str] = {p: "first"}

# "Mutation" creates a new object -- the original dict entry is unaffected
p2 = Point(x=999, y=p.y)
points[p2] = "second"

assert len(points) == 2
assert points[Point(x=1, y=2)] == "first"
assert points[Point(x=999, y=2)] == "second"
```

## Good Code: Hash on Immutable Subset (When Immutability Is Impractical)

```python
@dataclass
class UserSession:
    """A session that tracks mutable state but is keyed by immutable ID."""
    session_id: str       # immutable -- never changes
    last_active: float    # mutable -- changes on every request
    data: dict            # mutable

    def __hash__(self) -> int:
        # Hash only the immutable primary key
        return hash(self.session_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserSession):
            return NotImplemented
        # Equality also based only on the primary key
        return self.session_id == other.session_id


# Mutation is safe -- session_id never changes
sessions: dict[UserSession, str] = {}
session = UserSession(session_id="abc123", last_active=0.0, data={})
sessions[session] = "active"

session.last_active = 999.0  # mutable field changes
session.data["key"] = "val"  # mutable field changes

# Lookup still works -- hash depends only on session_id
assert session in sessions  # True
assert sessions[session] == "active"  # True
```

## Why It's Good / Key Differences

- **`frozen=True` enforces immutability at the language level**: `dataclass(frozen=True)` prevents field assignment after construction. The hash is computed once and never changes. The contract is mechanically enforced.
- **Hash-on-ID is explicit and bounded**: `UserSession.__hash__` uses only `session_id` -- a field that never changes. The docstring and type annotations make it clear which fields participate in hashing and which don't.
- **`__eq__` matches `__hash__`**: If `hash(x) == hash(y)` but `x != y`, dict/set fall back to equality check. By basing both on `session_id`, the contract `x == y ⇒ hash(x) == hash(y)` holds.
- **No silent data loss**: In both approaches, once an object is inserted into a dict/set, it remains reachable. No ghost entries. No memory leaks.

> Core principle: Python's dict and set rely on a contract: hash must not change, and `x == y` must imply `hash(x) == hash(y)`. Use `frozen=True` dataclasses whenever possible. When mutability is required, hash only on an immutable subset of fields and ensure equality matches.
