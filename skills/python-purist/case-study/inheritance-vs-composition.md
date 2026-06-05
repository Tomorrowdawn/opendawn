---
title: "Inheritance vs LEGO-Style Composition"
category: case-study
tags:
  - inheritance
  - composition
  - decorator-chain
  - anti-pattern
  - dependency-injection
related:
  - ../best-practice/composition-over-inheritance.md
summary: "Deep inheritance chains for code sharing cause tight coupling, welded ordering, and combinatorial explosion — composition with inner: Protocol is the escape hatch."
---

# Inheritance vs LEGO-Style Composition

> 对应 best-practice 中的 **类型 1（代码共享）**：当你用继承来复用方法行为而非表达"子是父加更多"的层次关系时，属于这一类反模式。

## 场景

你需要一个数据获取器，功能包括：HTTP 请求、日志记录、缓存、重试。每项功能都可能有不同实现（本地缓存 vs Redis 缓存），且顺序可调。

## 坏代码：深层继承链

```python
class HttpFetcher:
    def fetch(self, url: str) -> str:
        # 发送 HTTP GET，返回响应体
        ...

class LoggerFetcher(HttpFetcher):
    def fetch(self, url: str) -> str:
        print(f"[LOG] fetching {url}")
        return super().fetch(url)

class RetryFetcher(LoggerFetcher):  # 继承自 LoggerFetcher
    def fetch(self, url: str) -> str:
        for i in range(3):
            try:
                return super().fetch(url)
            except Exception:
                if i == 2:
                    raise

class CachedRetryLoggerFetcher(RetryFetcher):
    _cache: dict[str, str] = {}

    def fetch(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        result = super().fetch(url)
        self._cache[url] = result
        return result

# 使用
fetcher = CachedRetryLoggerFetcher()
data = fetcher.fetch("https://api.example.com/data")
```

## 为什么坏

1. **顺序焊死**：继承链决定了功能叠加顺序 —— `Cache` → `Retry` → `Logger` → `HTTP`。想改成"先重试再缓存"或"只缓存不重试"？必须重新设计整个类层次。
2. **组合爆炸**：每增加一个功能维度，就要产生新的子类。比如想在前面加 `AuthFetcher`，就得在 `HttpFetcher` 之上插入一层。N 个功能维度 = 2^N 个潜在子类。
3. **测试噩梦**：测试 `CachedRetryLoggerFetcher` 时，`super().fetch()` 穿透了 4 层调用，mock 任何一层都需要侵入继承链。
4. **违反单一职责**：`CachedRetryLoggerFetcher` 同时负责缓存、重试、日志和 HTTP——4 个完全不相关的职责塞进一个类。
5. **复用困难**：如果另一个模块只需要 `Logger` + `HTTP`（不需要重试和缓存），你没法从中间截取，必须再写一个 `LoggerHttpFetcher(HttpFetcher)`。

## 好代码：LEGO 式组合 + 依赖注入

```python
from dataclasses import dataclass
from typing import Protocol

class Fetcher(Protocol):
    def fetch(self, url: str) -> str: ...

@dataclass
class HttpFetcher:
    def fetch(self, url: str) -> str:
        ...  # 实际 HTTP 请求

@dataclass
class LoggingFetcher:
    inner: Fetcher

    def fetch(self, url: str) -> str:
        print(f"[LOG] fetching {url}")
        return self.inner.fetch(url)

@dataclass
class RetryFetcher:
    inner: Fetcher
    max_retries: int = 3

    def fetch(self, url: str) -> str:
        for i in range(self.max_retries):
            try:
                return self.inner.fetch(url)
            except Exception:
                if i == self.max_retries - 1:
                    raise

@dataclass
class CachingFetcher:
    inner: Fetcher
    _cache: dict[str, str] = field(default_factory=dict)

    def fetch(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        result = self.inner.fetch(url)
        self._cache[url] = result
        return result

# 使用：自由组合，顺序任意
fetcher = CachingFetcher(
    inner=RetryFetcher(
        inner=LoggingFetcher(
            inner=HttpFetcher()
        ),
        max_retries=5,
    )
)
data = fetcher.fetch("https://api.example.com/data")

# 只做日志+HTTP，不需要重试和缓存
simple_fetcher = LoggingFetcher(inner=HttpFetcher())
```

## 为什么好 / 关键差异

- **无限组合性**：每个装饰器只持有 `inner: Fetcher` 依赖，任何实现了 `Fetcher` 协议的对象都可以插入。顺序由 `__init__` 的嵌套决定，而非继承链。
- **独立测试**：测试 `RetryFetcher` 时，传入一个 mock `Fetcher` 即可，不依赖任何具体实现。
- **按需选用**：生产环境用 `Cache → Retry → Log → HTTP`，测试环境用 `Log → MockHttp`，零重复代码。
- **单一职责**：每个类只做一件事 —— `CachingFetcher` 只管缓存，`RetryFetcher` 只管重试。
- **可替换实现**：想把 Redis 缓存替代内存缓存？写一个 `RedisCachingFetcher`，替换 `CachingFetcher` 即可，其余链不变。

> 核心原则：组合优于继承。用 `inner` 依赖注入构建装饰器链，而非用 `class A(B(C(D)))` 焊死层次结构。
> 
> 这是继承类型 1（代码共享）的反模式。切记不要与类型 3（特化）混为一谈——详见 [composition-over-inheritance.md](../best-practice/composition-over-inheritance.md)。
