---
title: "Don't Mock What You Don't Own"
category: case-study
tags:
  - testing
  - mock
  - tdd
  - facade
  - dependency-injection
  - stub
related:
  - ../best-practice/red-green-tdd.md
  - ../best-practice/explicit-over-implicit.md
summary: "Mocking third-party APIs directly leads to brittle, unreadable tests with nested mock hierarchies. Wrap third-party dependencies in thin facades that you own and mock those instead."
---

# Don't Mock What You Don't Own

## Scenario

You are writing a business function that fetches data from a Docker registry API using the `httpx` HTTP client. You need to test that an empty repository list produces an empty result.

## Bad Code: Mocking the Third-Party Client Directly

```python
from unittest.mock import Mock
import httpx


def get_repos_with_tags(client: httpx.Client) -> dict[str, list[str]]:
    """Fetch all repositories and their tags from a Docker registry."""
    rv: dict[str, list[str]] = {}
    repos = client.get(
        "https://docker.example.com/v2/_catalog"
    ).json()["repositories"]

    for repo in repos:
        rv[repo] = client.get(
            f"https://docker.example.com/v2/{repo}/tags/list"
        ).json()["tags"]

    return rv


def test_empty():
    """Test that an empty repository list produces an empty dict."""
    client = Mock(
        spec_set=httpx.Client,
        get=Mock(
            return_value=Mock(
                spec_set=httpx.Response,
                json=lambda: {"repositories": []},
            ),
        ),
    )

    assert {} == get_repos_with_tags(client)
```

## Why It's Bad

1. **Three layers of nested mocks**: To test that an empty key produces an empty dict, you need `Mock(Client)` → `Mock(get)` → `Mock(Response)` → `lambda` for `json()`. The test intent ("empty repos → empty result") is buried under mock plumbing.

2. **Brittle against upstream API changes**: If `httpx` renames `Client` or changes the method signature, **every test** that mocks `httpx.Client` must be updated -- even though your business logic didn't change.

3. **The test verifies mock behavior, not business logic**: You are testing that your mock objects return the values you told them to. The real business logic -- "iterate repos, fetch tags for each" -- is barely visible.

4. **Multi-call responses are painful**: If `client.get()` must return different values for the `_catalog` call vs the per-repo calls, you need `side_effect` with a call counter. This quickly turns into an unreadable state machine.

5. **Mock Hell**: As complexity grows, you end up in a maze of nested mocks where you can no longer be sure what you are actually testing. The test becomes a mirror of the mock setup, not the business logic.

## Good Code: Wrap Third-Party APIs in Facades You Own

```python
from typing import Protocol


# Step 1: Define the facade interface
class DockerRegistryClient:
    """Thin facade over the Docker Registry HTTP API.

    This is the layer we own. It has exactly two methods.
    """
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def get_repos(self) -> list[str]:
        return self._client.get(
            "https://docker.example.com/v2/_catalog"
        ).json()["repositories"]

    def get_repo_tags(self, repo: str) -> list[str]:
        return self._client.get(
            f"https://docker.example.com/v2/{repo}/tags/list"
        ).json()["tags"]


# Step 2: Business logic depends on the facade, not httpx
def get_repos_with_tags(drc: DockerRegistryClient) -> dict[str, list[str]]:
    rv: dict[str, list[str]] = {}
    for repo in drc.get_repos():
        rv[repo] = drc.get_repo_tags(repo)
    return rv


# Step 3: Test against the facade -- one mock, clear intent
def test_empty():
    drc = Mock(
        spec_set=DockerRegistryClient,
        get_repos=lambda: [],
    )
    assert {} == get_repos_with_tags(drc)


def test_with_repos():
    drc = Mock(
        spec_set=DockerRegistryClient,
        get_repos=lambda: ["web-svc", "worker-svc"],
        get_repo_tags=lambda repo: {
            "web-svc": ["1", "5", "7"],
            "worker-svc": ["8", "10"],
        }[repo],
    )
    assert {
        "web-svc": ["1", "5", "7"],
        "worker-svc": ["8", "10"],
    } == get_repos_with_tags(drc)
```

## Why It's Good / Key Differences

1. **One mock, clear intent**: `Mock(spec_set=DockerRegistryClient, get_repos=lambda: [])` -- the test reader immediately understands: "No repos → empty result."
2. **Upstream changes isolated to the facade**: If `httpx` changes its API, only `DockerRegistryClient` needs updating. Business logic tests are unaffected.
3. **Business logic is more idiomatic**: `for repo in drc.get_repos()` is cleaner than `for repo in client.get(...).json()["repositories"]`. The facade reveals the domain language.
4. **Facade is itself thin and simple**: `DockerRegistryClient` has minimal cyclomatic complexity -- no branches, no loops, just delegation. The hard-to-test layer is kept so simple that testing it is optional (defer to integration tests).
5. **Replaceable without touching business logic**: Swap `httpx` for `aiohttp` or `requests`? Only the facade changes. Business code and its tests never know.

> Core principle: Never let third-party APIs leak into your business logic or your tests. Wrap them in a thin facade that you own. Mock the facade, not the library. This is "Don't Mock What You Don't Own."
