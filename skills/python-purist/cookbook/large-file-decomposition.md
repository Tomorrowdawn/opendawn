---
title: "大文件拆散技巧"
category: cookbook
tags:
  - refactoring
  - large-files
  - decomposition
  - composition
  - factory
  - config
  - modularization
  - file-organization
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/explicit-over-implicit.md
  - ../best-practice/fail-fast.md
  - ../case-study/inheritance-vs-composition.md
  - ../case-study/hidden-initialization.md
  - ../case-study/factory-pattern.md
  - ../case-study/template-method-antipattern.md
  - ../case-study/strategy-pattern.md
summary: "大文件拆散三模式：超级大类用组合拆分为子组件；大量启动代码用 config + from_config 工厂方法分散到各自类中；大量子类聚合直接按文件拆分。拆前先消除 anti-pattern 导致的意外复杂性。"
---

# 大文件拆散技巧

> **拆文件不是目的，消除意外复杂性才是。** 在机械拆分之前，先检查大文件的膨胀是否由 anti-pattern 导致——消除 anti-pattern 通常会自然缩小文件。以下技巧按"先治本、后治标"的顺序排列。

---

## 第零步：先消除 Anti-Pattern 导致的意外复杂性

大文件往往不是"代码真的多"，而是**糟糕的设计让简单的事情变复杂了**。在拆分文件之前，先扫描以下 anti-pattern——消除它们之后，文件可能已经缩到合理范围。

| Anti-Pattern | 典型症状 | 消除后效果 | 参考 |
|-------------|----------|-----------|------|
| **深层继承链** | 一个类继承 3+ 层，每层只加一点点行为；读代码时上下跳跃 | 扁平化为组合，每个行为组件独立、可测试 | `case-study/inheritance-vs-composition.md` |
| **Template Method 模式** | 基类定义骨架，子类填空——导致"远距离耦合"，改基类炸所有子类 | 替换为策略模式 + 组合，每个策略独立一个类 | `case-study/template-method-antipattern.md` |
| **隐藏初始化** | `__init__` 里读配置、建连接、调 I/O；`obj = X()` 之后还要 `obj.setup()` | 依赖注入：外部构造依赖，传入 `__init__` | `case-study/hidden-initialization.md` |
| **`__init__` 中的 if/elif 分支** | 根据 `source` 参数在 `__init__` 里做不同初始化逻辑 | `@classmethod` 工厂 + Config schema，每种来源一个工厂方法 | `case-study/factory-pattern.md` |
| **输入修补链** | 数据在多个函数间传递时被逐步"修补"（`dict.get(k, default)`、`if not field: field = x`） | 在边界处用 msgspec.Struct 验证一次，内部直接 `.` 访问 | `best-practice/direct-over-indirect.md` |

**自检命令**：

```bash
# 用 purist check 扫描复杂度和 anti-pattern
scripts/purist check src/

# 搜索你怀疑的 anti-pattern
scripts/purist search "hasattr"
scripts/purist search "super()"
scripts/purist search "__init__"
```

消除 anti-pattern 后，重新评估文件大小。如果仍然超标（>400 行警告，>600 行错误），再进入以下三种机械拆分模式。

---

## 模式一：超级大类 → 组合拆分为子组件

### 识别特征

- 单个类超过 300 行
- 类内部有清晰的分组注释（`# --- HTTP ---`、`# --- Cache ---`、`# --- Retry ---`）
- 多个方法共享一组私有属性（`self._http_client`、`self._http_timeout`、`self._http_headers` 全是一组的）
- 这个类"什么都做"——请求、缓存、重试、日志、序列化全在一个类里

### 拆分策略：组合优于继承

核心类保留为**编排者（orchestrator）**，将职责组提取为独立的**子组件（sub-component）**，通过 `@define` 平摊字段注入。

```
拆分前（一个文件，一个类）：
  src/service/data_fetcher.py
    └── DataFetcher (400 行)
          - HTTP 请求
          - 缓存逻辑
          - 重试策略
          - 日志记录
          - 响应解析

拆分后（多个文件，组合）：
  src/service/
    data_fetcher.py         ← 编排者，~60 行
    http_client.py          ← HTTP 请求子组件
    cache_manager.py        ← 缓存子组件
    retry_policy.py         ← 重试子组件
    response_parser.py      ← 响应解析子组件
```

### 代码示例：拆分前（反模式）

```python
# src/service/data_fetcher.py — 400 行，什么都做

class DataFetcher:
    def __init__(self, base_url: str, cache_ttl: int = 300, max_retries: int = 3):
        self._base_url = base_url
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._session = aiohttp.ClientSession()
        self._cache: dict[str, tuple[float, str]] = {}  # url -> (expiry, data)

    # --- HTTP 请求 ---
    async def _request(self, path: str) -> str:
        async with self._session.get(f"{self._base_url}{path}") as resp:
            return await resp.text()

    # --- 缓存 ---
    def _cache_get(self, key: str) -> str | None:
        if key in self._cache:
            expiry, data = self._cache[key]
            if time.time() < expiry:
                return data
            del self._cache[key]
        return None

    def _cache_set(self, key: str, data: str) -> None:
        self._cache[key] = (time.time() + self._cache_ttl, data)

    # --- 重试 ---
    async def _retry_request(self, path: str) -> str:
        last_exc = None
        for attempt in range(self._max_retries):
            try:
                return await self._request(path)
            except aiohttp.ClientError as e:
                last_exc = e
                await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    # --- 响应解析 ---
    def _parse_response(self, raw: str) -> dict[str, Any]:
        import json
        data = json.loads(raw)
        # 字段验证 + 修补 + 默认值……又是一大段
        return data

    # --- 公共 API ---
    async def fetch(self, path: str) -> dict[str, Any]:
        cached = self._cache_get(path)
        if cached is not None:
            return json.loads(cached)
        raw = await self._retry_request(path)
        result = self._parse_response(raw)
        self._cache_set(path, raw)
        return result
```

### 代码示例：拆分后（组合）

```python
from attrs import define, field

# src/service/http_client.py
@define
class HttpClient:
    """HTTP 请求——单一职责，可独立测试。session 可注入，便于测试。"""
    base_url: str
    session: aiohttp.ClientSession = field(factory=aiohttp.ClientSession)

    async def get(self, path: str) -> str:
        async with self.session.get(f"{self.base_url}{path}") as resp:
            resp.raise_for_status()
            return await resp.text()


# src/service/cache_manager.py
@define
class CacheManager:
    """缓存——独立于 HTTP，可替换为 RedisCacheManager。"""
    ttl: int = 300
    _store: dict[str, tuple[float, str]] = field(init=False)

    def __attrs_post_init__(self):
        self._store = {}

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, data = entry
        if time.time() >= expiry:
            del self._store[key]
            return None
        return data

    def set(self, key: str, data: str) -> None:
        self._store[key] = (time.time() + self.ttl, data)


# src/service/retry_policy.py
@define
class RetryPolicy:
    """重试——独立于 HTTP，可替换策略。"""
    max_retries: int = 3
    base_delay: float = 1.0

    async def execute(self, fn: Callable[[], Awaitable[str]]) -> str:
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                return await fn()
            except aiohttp.ClientError as e:
                last_exc = e
                await asyncio.sleep(self.base_delay * (2 ** attempt))
        raise last_exc  # type: ignore[misc]


# src/service/response_parser.py
@define
class ResponseParser:
    """解析——无状态，可测试各种响应格式。"""

    def parse(self, raw: str) -> dict[str, Any]:
        return json.loads(raw)


# src/service/data_fetcher.py — 编排者，~30 行
@define
class DataFetcher:
    """数据获取编排者——组合所有子组件，自身不包含任何实现细节。"""
    http: HttpClient
    cache: CacheManager
    retry: RetryPolicy
    parser: ResponseParser

    async def fetch(self, path: str) -> dict[str, Any]:
        cached = self.cache.get(path)
        if cached is not None:
            return self.parser.parse(cached)

        raw = await self.retry.execute(lambda: self.http.get(path))
        result = self.parser.parse(raw)
        self.cache.set(path, raw)
        return result
```

### 关键原则

1. **子组件不持有编排者的引用**——单向依赖，子组件不知道谁在使用它。
2. **每个子组件可通过构造参数替换**——测试时注入 mock，生产时注入真实实现。
3. **编排者不应包含任何"怎么做"的逻辑**——它只描述"先做什么、再做什么"的流程。
4. **拆分粒度：如果子组件还需要分组注释，说明还可以继续拆。**

---

## 模式二：大量启动组装 → config + from_config 工厂方法

### 识别特征

- `__init__` 或模块顶层有大量 `key=value` 初始化代码
- 创建对象需要 10+ 个参数，每个都有默认值
- 同一种对象的初始化代码在多处重复（测试、生产、不同环境各写一套）
- 启动代码像一个"购物清单"——30 行创建对象，10 行业务逻辑

### 解法

> **完整方案已提取至 `cookbook/initialization-patterns.md`**（本文件的核心内容），包含：
> - 模式 3：配置驱动 → `@define` + `from_config` 递归组装
> - 模式 4：多来源构建 → `from_*` classmethods
> - 反模式对比：为什么不是 `__init__(self, config)` + 简单转发

核心要点：
1. 类自身是平摊字段（`@define` / `msgspec.Struct`），不手写 `__init__`。
2. `from_config` 做真正的创建——递归创建子对象、组装平摊字段。不是 `return cls(config)`。
3. 对象创建后立即可用——无二次初始化，无 `connect()` 调用，无延迟创建。
4. 默认值放在 Config schema 中，不要散落在各处。
5. 启动文件退化为一行 `App.from_config(config)`——超过 3 行说明有组件的创建逻辑泄漏。

---

## 模式三：大量子类聚合 → 文件夹拆分

### 识别特征

- 一个文件里定义了一个基类和 5+ 个子类
- 每个子类 30-80 行，全部放在同一个文件中
- 文件头部有一长串 `from .models import ...` 或者子类之间互相引用
- 新增一个子类就要在同一个文件里追加

### 典型场景

策略模式、命令模式、插件系统、枚举对应的处理器——这些场景天然会产生大量小类。

```
拆分前：
  src/llm/backends.py  (300 行)
    ├── class LLMBackend(Protocol): ...
    ├── class OpenAIBackend: ...
    ├── class AnthropicBackend: ...
    ├── class OllamaBackend: ...
    ├── class GeminiBackend: ...
    └── class GrokBackend: ...

拆分后：
  src/llm/
    backends/
      __init__.py          ← 重新导出 + 注册表（可选）
      protocol.py          ← LLMBackend Protocol
      openai.py            ← OpenAIBackend
      anthropic.py         ← AnthropicBackend
      ollama.py            ← OllamaBackend
      gemini.py            ← GeminiBackend
      grok.py              ← GrokBackend
```

### 代码示例：拆分前

```python
# src/llm/backends.py — 5 个子类挤在一起

from typing import Protocol
from attrs import define, field

class LLMBackend(Protocol):
    """后端接口。"""
    async def generate(self, prompt: str) -> str: ...


@define
class OpenAIBackend:
    api_key: str
    model: str = "gpt-4"
    _client: openai.AsyncOpenAI = field(init=False)

    def __attrs_post_init__(self):
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


@define
class AnthropicBackend:
    api_key: str
    model: str = "claude-3-opus"
    _client: anthropic.AsyncAnthropic = field(init=False)

    def __attrs_post_init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return response.content[0].text


@define
class OllamaBackend:
    base_url: str = "http://localhost:11434"
    model: str = "llama3"

    async def generate(self, prompt: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            ) as resp:
                data = await resp.json()
                return data["response"]

# ... 还有 GeminiBackend, GrokBackend ... 文件继续膨胀
```

### 代码示例：拆分后

```python
# src/llm/backends/protocol.py
from typing import Protocol

class LLMBackend(Protocol):
    """后端接口——所有后端必须实现 generate(prompt) -> str。"""
    async def generate(self, prompt: str) -> str: ...


# src/llm/backends/openai.py
import openai
from attrs import define, field

@define
class OpenAIBackend:
    api_key: str
    model: str = "gpt-4"
    _client: openai.AsyncOpenAI = field(init=False)

    def __attrs_post_init__(self):
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


# src/llm/backends/anthropic.py  ← 只包含 Anthropic 相关代码
# src/llm/backends/ollama.py     ← 只包含 Ollama 相关代码


# src/llm/backends/__init__.py
from .protocol import LLMBackend
from .openai import OpenAIBackend
from .anthropic import AnthropicBackend
from .ollama import OllamaBackend

__all__ = ["LLMBackend", "OpenAIBackend", "AnthropicBackend", "OllamaBackend"]

# 可选：方便的注册表
_REGISTRY: dict[str, type] = {
    "openai": OpenAIBackend,
    "anthropic": AnthropicBackend,
    "ollama": OllamaBackend,
}

def get_backend(name: str) -> type:
    """按名称获取后端类。"""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]
```

### 注意事项

1. **Protocol / ABC 单独一个文件**（如 `protocol.py`），不要和任何实现混在一起。
2. **`__init__.py` 做两件事**：重新导出（方便外部 `from backends import OpenAIBackend`）+ 可选的注册表。
3. **每个子类文件只包含一个类及其紧耦合的辅助类型**（如该后端专用的 Config schema、异常类）。
4. **如果某个子类又膨胀了，重复模式一**——对其内部用组合拆分。
5. **不要过早建文件夹**——只有当子类 ≥ 5 个或文件 > 400 行时才需要。2-3 个子类放在同一个文件里完全合理。

---

## 文件拆分决策树

```
大文件（>400 行）
 │
 ├─ 是否有第零步列出的 anti-pattern？
 │   └─ 有 → 先消除 anti-pattern → 重新评估 → 可能已不需要拆分
 │
 ├─ 是否是一个超级大类（300+ 行，内含清晰分组）？
 │   └─ 是 → 模式一：组合拆分为子组件
 │
 ├─ 是否有大量 key=value 初始化代码（创建对象 10+ 参数）？
 │   └─ 是 → 模式二：Config + from_config 工厂方法
 │
 ├─ 是否有 5+ 个同类子类挤在一个文件中？
 │   └─ 是 → 模式三：文件夹拆分，每个子类独立文件
 │
 └─ 都不匹配？
     └─ 检查是否一个文件承担了多个不相关的职责 → 按职责拆分
```

---

## 相关文档

- `best-practice/composition-over-inheritance.md` — 模式一的理论基础：三种继承类型 + 组合替代代码共享
- `best-practice/explicit-over-implicit.md` — 显式注入优于隐式创建
- `best-practice/fail-fast.md` — 对象应在 `__init__` 后立即可用
- `case-study/inheritance-vs-composition.md` — LEGO 式组合 vs 深层继承链的完整对比
- `case-study/hidden-initialization.md` — `__init__` 中创建依赖是反模式
- `case-study/factory-pattern.md` — `@classmethod` + Config schema 标准解法
- `case-study/template-method-antipattern.md` — 当"大文件"的根源是 Template Method 时
- `case-study/strategy-pattern.md` — 模式三的典型场景：可替换策略的自然拆分
