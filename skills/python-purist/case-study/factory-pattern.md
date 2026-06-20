---
title: "Factory Pattern: @classmethod + Config Schema"
category: case-study
tags:
  - factory
  - classmethod
  - configuration
  - object-creation
  - initialization
  - constructor
  - testing
  - design-pattern
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

## 正确做法

> **完整方案见 `cookbook/initialization-patterns.md`**（模式 4：多来源构建 → `from_*` classmethods）。
>
> 核心原则：`__init__` 只做字段赋值。每个来源 = 一个独立的 `@classmethod`（`from_yaml`、`from_db_row`、`from_api_response`），各自负责自己的字段映射，然后委托给 `cls(name=..., model=...)`。新增来源只增方法，不改现有代码。类型安全、测试友好、自文档化。
