---
title: "Document Your Tests: Intent Over Mechanics"
category: case-study
tags:
  - testing
  - tdd
  - documentation
  - readability
  - regression
related:
  - ../best-practice/red-green-tdd.md
  - ../best-practice/naming-and-readability.md
summary: "A test name describes what is being tested. The docstring explains why it matters. Without documentation, future maintainers cannot distinguish a bug fix from intentional behavior."
---

# Document Your Tests: Intent Over Mechanics

## Scenario

You maintain a library used by hundreds of projects. A contributor submits a bug fix with a new test. The test verifies some specific edge case behavior. A year later, another contributor refactors the internals and that test starts failing. Is the test a regression guard that must be preserved, or an accidental side effect of the old implementation that can be safely deleted?

## Bad Code: Undocumented Tests

```python
def test_hash_eq_false():
    @attr.s(eq=False)
    class C:
        pass

    c1 = C()
    c2 = C()

    assert hash(c1) != hash(c2)


def test_empty_string_returns_none():
    result = parse_input("")
    assert result is None


def test_zero_division():
    with pytest.raises(ZeroDivisionError):
        compute_ratio(10, 0)
```

## Why It's Bad

1. **What is visible, why is invisible**: `test_hash_eq_false` tells you "we're testing hashes when eq=False." But **why**? Is this testing that eq=False makes the class unhashable? Or that eq=False makes it hashable by object identity? The test body proves the hashes differ, but the reason is lost.
2. **Regression tests lose their origin**: `test_empty_string_returns_none` -- was empty string always returning None? Or was this added after a bug report where empty input crashed the parser? Without a link to the issue or a docstring explaining the bug, you cannot know.
3. **Refactoring safety lost**: When `test_zero_division` fails after an internal refactor, the contributor sees `ZeroDivisionError` is no longer raised. Should they preserve the old behavior ("division by zero must raise"), or update the test ("we now return `math.inf`")? The test name says what happens; it does not say whether the behavior is intentional or accidental.
4. **Code review friction**: A reviewer sees `test_hash_eq_false` and must deduce the purpose by reading the test body and mentally reverse-engineering the requirement. This wastes reviewer time and causes misunderstandings.

## Good Code: Documented Tests

```python
def test_eq_false_makes_hashable_by_id():
    """Setting eq=False makes the class hashable by object identity.

    When eq=False, attrs does not generate __eq__ or __hash__, so Python
    falls back to the default object.__hash__ which uses the object's id().
    This means two distinct instances must have different hashes.

    Regression test for: https://github.com/org/repo/issues/142
    """
    @attr.s(eq=False)
    class C:
        pass

    c1 = C()
    c2 = C()

    assert hash(c1) != hash(c2)


def test_empty_string_returns_none():
    """Empty input must return None, not raise ParseError.

    Bug report: users passing empty query strings from unset form fields
    were getting 500 errors because the parser raised ParseError instead
    of treating empty input as "no query."

    See: https://sentry.io/org/project/issues/5821
    """
    result = parse_input("")
    assert result is None


def test_zero_division_returns_inf():
    """Division by zero must return math.inf, not raise ZeroDivisionError.

    Design decision (2024-03): the ratio function is used in dashboard
    widgets where infinity is a valid display value ("∞"). Raising an
    exception would require every caller to wrap in try/except.

    See ADR: docs/adr/004-ratio-division-by-zero.md
    """
    result = compute_ratio(10, 0)
    assert result == math.inf
```

## Why It's Good / Key Differences

1. **Intent documented**: The docstring answers *why this test exists* and *what design decision it encodes*. A maintainer encountering a failing test two years later can decide whether to fix the code or update the test.
2. **Regression traceability**: Links to issue trackers, Sentry issues, or ADRs (Architecture Decision Records) let you trace the test back to its origin. Was this a user-reported bug? A deliberate design choice? The provenance is preserved.
3. **Reviewer clarity**: The reviewer reads the docstring and immediately understands what correctness means -- without deducing it from assertions.
4. **Tool enforcement**: Use [`interrogate`](https://interrogate.readthedocs.io/) to enforce that every test function has a docstring: `interrogate -vv --fail-under 100 --whitelist-regex "test_.*" tests/`

> Core principle: A test name says *what* is being tested. A test docstring says *why*. Without the why, future maintainers cannot distinguish a regression guard from accidental behavior. Every test must have a docstring.
