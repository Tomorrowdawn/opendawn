---
title: "Builder Pattern: Taming Complex Constructors"
category: case-study
tags:
  - builder
  - constructor
  - dependency-injection
  - chaining
  - factory
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/fail-fast.md
summary: "From 12-parameter constructors to chainable Build pattern — progressive evolution toward testable, self-documenting object creation."
---

# Builder Pattern: Taming Complex Constructors

## 场景

HTTP 客户端需要构造请求对象，包含 15 个可配置字段：method、url、headers、body、timeout、retry 策略、代理、TLS 证书、压缩算法、认证 token 等。大多数请求只需 3-4 个字段，其余使用默认值。

## 坏代码

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str] | None = None
    body: bytes | None = None
    timeout: float = 30.0
    retry_count: int = 0
    retry_backoff: float = 1.0
    proxy: str | None = None
    tls_cert: str | None = None
    tls_key: str | None = None
    compression: str | None = None
    auth_token: str | None = None
    user_agent: str = "yuubot/2.0"
    follow_redirects: bool = True
    max_redirects: int = 5

# 调用端——参数爆炸
req = HttpRequest(
    method="POST",
    url="https://api.example.com/v2/orders",
    headers={"Content-Type": "application/json"},
    body=b'{"amount": 100}',
    timeout=10.0,
    retry_count=3,
    auth_token="sk-xxx",
)
```

## 为什么坏

1. **参数爆炸**：15 个参数让构造函数难以阅读——调用者需要数到第 7 个位置才知道 `auth_token` 是什么。
2. **默认值陷阱**：如果未来增加 `http_version` 参数且必须插在 `timeout` 和 `retry_count` 之间，所有仅用位置参数的调用端都会静默地传错值。
3. **不同场景无法自描述**：`GET /health` 只需 `method` + `url` + `timeout(1s)`，`POST /orders` 需要 8 个字段。构造函数无法区分"我没设这个值"和"我主动设它为默认值"。
4. **验证逻辑无处安放**：`retry_count > 0` 时 `retry_backoff` 必须 > 0、`tls_cert` 和 `tls_key` 必须同时提供或同时为空——这些约束落在构造器里会导致大量无结构的 `if` 块。

## 好代码

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HttpRequest:
    """不可变请求对象——由 Builder 构造，外部只能读不能改。"""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 30.0
    retry_count: int = 0
    retry_backoff: float = 1.0
    proxy: str | None = None
    tls_cert: str | None = None
    tls_key: str | None = None
    compression: str | None = None
    auth_token: str | None = None
    user_agent: str = "yuubot/2.0"
    follow_redirects: bool = True
    max_redirects: int = 5


class HttpRequestBuilder:
    """流畅 API 构造器——每一步都返回值允许链式调用，build() 时统一验证。"""

    def __init__(self) -> None:
        self._method: str = "GET"
        self._url: str = ""
        self._headers: dict[str, str] = {}
        self._body: bytes | None = None
        self._timeout: float = 30.0
        self._retry_count: int = 0
        self._retry_backoff: float = 1.0
        self._proxy: str | None = None
        self._tls_cert: str | None = None
        self._tls_key: str | None = None
        self._compression: str | None = None
        self._auth_token: str | None = None
        self._user_agent: str = "yuubot/2.0"
        self._follow_redirects: bool = True
        self._max_redirects: int = 5

    def get(self, url: str, /) -> HttpRequestBuilder:
        self._method = "GET"
        self._url = url
        return self

    def post(self, url: str, /) -> HttpRequestBuilder:
        self._method = "POST"
        self._url = url
        return self

    def header(self, key: str, value: str, /) -> HttpRequestBuilder:
        self._headers[key] = value
        return self

    def body(self, data: bytes, /) -> HttpRequestBuilder:
        self._body = data
        return self

    def timeout(self, seconds: float, /) -> HttpRequestBuilder:
        self._timeout = seconds
        return self

    def retry(self, count: int, backoff: float = 1.0, /) -> HttpRequestBuilder:
        self._retry_count = count
        self._retry_backoff = backoff
        return self

    def auth(self, token: str, /) -> HttpRequestBuilder:
        self._auth_token = token
        return self

    def build(self) -> HttpRequest:
        """统一验证——确保构造出的对象始终合法。"""
        if self._retry_count > 0 and self._retry_backoff <= 0:
            raise ValueError("retry_backoff must be positive when retry_count > 0")
        if bool(self._tls_cert) != bool(self._tls_key):
            raise ValueError("tls_cert and tls_key must be provided together")
        return HttpRequest(
            method=self._method, url=self._url,
            headers=self._headers, body=self._body,
            timeout=self._timeout,
            retry_count=self._retry_count, retry_backoff=self._retry_backoff,
            proxy=self._proxy, tls_cert=self._tls_cert, tls_key=self._tls_key,
            compression=self._compression, auth_token=self._auth_token,
            user_agent=self._user_agent,
            follow_redirects=self._follow_redirects, max_redirects=self._max_redirects,
        )


# --- 调用端：自解释的流畅 API ---
req: HttpRequest = (
    HttpRequestBuilder()
    .post("https://api.example.com/v2/orders")
    .header("Content-Type", "application/json")
    .body(b'{"amount": 100}')
    .timeout(10.0)
    .retry(3, backoff=2.0)
    .auth("sk-xxx")
    .build()
)
```

## 为什么好 / 关键差异

1. **流畅 API 自解释**：`.post(url).body(data).timeout(10).retry(3).build()` ——读代码的顺序就是构造数据的顺序，无需数第 7 个参数是什么。
2. **按需设值**：不需要的字段完全不出现——`GET /health` 就是 `.get(url).timeout(1.0).build()`，简洁明了。
3. **build() 守住验证**：所有跨字段约束集中在 `build()` 中，构造出的 `HttpRequest` 永远合法——调用者无需事后调用 `validate()`。
4. **不可变产物**：`HttpRequest` 是 `frozen=True` dataclass，一旦 `build()` 完成便不可修改——线程安全、可哈希缓存、无意外篡改。
