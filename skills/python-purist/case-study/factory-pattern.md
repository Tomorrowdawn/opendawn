---
title: "Factory Pattern: @classmethod + Config Schema"
category: case-study
tags:
  - factory
  - classmethod
  - configuration
  - object-creation
  - testing
related:
  - ../best-practice/composition-over-inheritance.md
  - ../best-practice/fail-fast.md
summary: "@classmethod + Config schema makes object creation testable and substitutable, eliminating sprawling if/elif type branching at call sites."
---

# Factory Pattern: @classmethod + Config Schema

## 场景

你的 `AgentConfig` 对象需要从多种数据源创建：YAML 配置文件、数据库查询结果、HTTP API 响应。每个来源的数据结构略有不同，但最终都要转换为统一的 `AgentConfig` 实例。

## 坏代码：`__init__` 中的分支逻辑

```python
class AgentConfig:
    def __init__(self, source: str, data: dict | str):
        if source == "yaml":
            raw = yaml.safe_load(data) if isinstance(data, str) else data
            self.name = raw["name"]
            self.model = raw.get("model", "gpt-4")
            self.temperature = raw.get("temperature", 0.7)
            self.max_tokens = raw.get("max_tokens", 4096)
        elif source == "db_row":
            self.name = data["agent_name"]          # 注意：db 用 agent_name
            self.model = data.get("llm_model", "gpt-4")  # db 用 llm_model
            self.temperature = float(data.get("temp", 0.7))
            self.max_tokens = data.get("tokens", 4096)
        elif source == "api":
            payload = data if isinstance(data, dict) else json.loads(data)
            self.name = payload["agent"]["name"]    # api 嵌套了一层
            self.model = payload["agent"].get("model_name", "gpt-4")
            self.temperature = payload["agent"].get("temperature", 0.7)
            self.max_tokens = payload.get("limits", {}).get("max_tokens", 4096)
        else:
            raise ValueError(f"Unknown source: {source}")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

# 使用
config = AgentConfig("yaml", open("config.yaml").read())
db_config = AgentConfig("db_row", {"agent_name": "helper", "llm_model": "claude-3"})
```

## 为什么坏

1. **`__init__` 成了垃圾场**：构造函数本该是简单的字段赋值，现在充斥着 YAML 解析、字段名映射、类型转换、嵌套提取等逻辑。来源越多，`__init__` 越臃肿。
2. **字段映射规则分散**：`agent_name` → `self.name`（db）、`agent.name` → `self.name`（api）、`name` → `self.name`（yaml）—— 同样的映射逻辑不可能复用。
3. **新增来源 = 修改已有代码**：每加一种数据来源，就要在 `__init__` 里加一个 `elif` 分支，违反开闭原则。
4. **类型不安全**：`data: dict | str` 要求调用方知道什么来源对应什么类型。传错类型（比如 yaml 源传 dict）可能不会立即报错，但语义错误。
5. **测试困难**：测试 yaml 解析和 api 解析的逻辑纠缠在同一个 `__init__` 里，任何一个来源的测试都依赖于整个构造器。

## 好代码：`@classmethod` 工厂 + 独立 Schema

```python
from dataclasses import dataclass
import yaml

@dataclass(frozen=True)
class AgentConfig:
    """统一 Schema —— __init__ 只接受明确的字段"""
    name: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls(
            name=raw["name"],
            model=raw.get("model", "gpt-4"),
            temperature=raw.get("temperature", 0.7),
            max_tokens=raw.get("max_tokens", 4096),
        )

    @classmethod
    def from_db_row(cls, row: dict) -> "AgentConfig":
        return cls(
            name=row["agent_name"],
            model=row.get("llm_model", "gpt-4"),
            temperature=float(row.get("temp", 0.7)),
            max_tokens=row.get("tokens", 4096),
        )

    @classmethod
    def from_api_response(cls, payload: dict) -> "AgentConfig":
        agent = payload["agent"]
        return cls(
            name=agent["name"],
            model=agent.get("model_name", "gpt-4"),
            temperature=agent.get("temperature", 0.7),
            max_tokens=payload.get("limits", {}).get("max_tokens", 4096),
        )

# 使用
config = AgentConfig.from_yaml("config.yaml")
db_config = AgentConfig.from_db_row({"agent_name": "helper", "llm_model": "claude-3"})
api_config = AgentConfig.from_api_response({"agent": {"name": "bot", "model_name": "gemini"}})
```

## 为什么好 / 关键差异

- **`__init__` 回归本质**：构造函数只做字段赋值，不再包含任何解析或映射逻辑。`AgentConfig` 的字段语义由 dataclass 自身定义。
- **每个来源 = 一个独立的 `@classmethod`**：YAML 的字段映射不会污染 DB row 的映射，也不会影响 API response 的映射。新增来源只需增加一个 `@classmethod`，不修改现有代码。
- **类型安全**：每个工厂方法的参数类型都是具体的 —— `from_yaml(path: str)`、`from_db_row(row: dict)` —— 调用者不会传错类型。
- **测试友好**：测试 `from_yaml` 不依赖数据库，测试 `from_db_row` 不需要 YAML 文件。每个工厂方法可以独立测试。
- **自文档化**：看到 `AgentConfig.from_db_row(row)` 就知道它在将数据库行映射为配置对象，意图比 `AgentConfig("db_row", data)` 清晰一百倍。

> 核心原则：`__init__` 只做字段赋值。用 `@classmethod` 工厂方法处理不同来源的数据转换。
