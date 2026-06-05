---
title: "Serialization Schema: msgspec / Pydantic at the Boundary"
category: case-study
tags:
  - serialization
  - schema
  - msgspec
  - pydantic
  - validation
  - boundary
related:
  - ../best-practice/serde-boundary.md
  - ../best-practice/type-safety.md
summary: "From wild json.loads → unstructured dicts → typed msgspec.Struct schemas. Validate at the boundary, work with typed objects internally."
---

# Serialization Schema: msgspec / Pydantic at the Boundary

## 场景

你的应用需要从磁盘加载 YAML 配置文件。文件来自运维手动编辑或 CI 模板生成，内容可能包含字段缺失、类型错误、多余字段或拼写错误。你需要可靠地将这些"不可信数据"转换为内部强类型对象。

## 坏代码

```python
import yaml

def load_config(path: str) -> dict:
    with open(path) as f:
        config = yaml.safe_load(f)
    # 不验证，不转换，直接传 dict
    return config

def start_server(config: dict) -> None:
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8080)           # 可能是 str "8080"？
    database = config.get("database", {})
    db_host = database.get("host", "localhost")
    db_port = database.get("port", 5432)      # 又重复 .get() 模式
    db_name = database.get("name")            # 没有默认值，可能是 None
    pool_size = config.get("pool", {}).get("size", 10)
    log_level = config.get("logging", {}).get("level", "INFO")

    print(f"Starting server at {host}:{port}")
    print(f"Database: {db_host}:{db_port}/{db_name}, pool={pool_size}")

# 使用
config = load_config("config.yaml")
start_server(config)
```

假设运维在 YAML 中写错了字段名 `por t: 8080` 或把 `port` 写成字符串 `"8080"`——程序在深层嵌套的 `.get()` 调用中静默退化到默认值，用户永远不知道配置没生效。

## 为什么坏

1. **验证缺失**：`yaml.safe_load()` 返回裸 `dict`，不做任何字段存在性、类型正确性校验。`port: "八千零八十"` 只会让 `int("八千零八十")` 在远处炸掉。
2. **默认值散落**：`"0.0.0.0"`, `8080`, `"localhost"`, `5432`, `10`, `"INFO"` 散落在函数各处。改默认值需要全局搜索 `.get()`。
3. **深层 `.get()` 链**：`config.get("database", {}).get("host", "localhost")` 三层嵌套，可读性差，中间任何一层缺失都会静默降级。
4. **类型为 `dict` 毫无信息**：函数签名 `config: dict` 对调用者和阅读者传达零信息 —— 需要哪些字段？什么类型？必须深入实现才知道。
5. **重构脆弱**：字段名改变（`database` → `db`）后，所有 `.get("database")` 静默返回默认值，没有编译错误、没有运行时警告。

## 好代码

```python
import msgspec
import yaml

class DatabaseConfig(msgspec.Struct, frozen=True):
    host: str = "localhost"
    port: int = 5432
    name: str  # 必填，无默认值

class PoolConfig(msgspec.Struct, frozen=True):
    size: int = 10

class LoggingConfig(msgspec.Struct, frozen=True):
    level: str = "INFO"

class AppConfig(msgspec.Struct, frozen=True):
    host: str = "0.0.0.0"
    port: int = 8080
    database: DatabaseConfig
    pool: PoolConfig = msgspec.field(default_factory=PoolConfig)
    logging: LoggingConfig = msgspec.field(default_factory=LoggingConfig)

def load_config(path: str) -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    # 边界处：一次性验证+转换
    return msgspec.convert(raw, type=AppConfig)

def start_server(config: AppConfig) -> None:
    # 属性访问 + 类型安全 + IDE 补全
    print(f"Starting server at {config.host}:{config.port}")
    print(
        f"Database: {config.database.host}:{config.database.port}"
        f"/{config.database.name}, pool={config.pool.size}"
    )
    print(f"Log level: {config.logging.level}")

# 使用
config = load_config("config.yaml")
# 如果 YAML 中 database.name 缺失或 port 是字符串，
# msgspec.convert 在此处抛出 ValidationError，错误信息精确到字段
start_server(config)
```

## 为什么好 / 关键差异

- **单点验证、即时失败**：`msgspec.convert(raw, type=AppConfig)` 在系统边界一次性校验所有字段的存在性、类型和嵌套结构。配置错误在这一行就暴露，附有精确的字段路径和期望类型。
- **默认值集中管理**：所有默认值定义在 `msgspec.Struct` 的字段声明中，单一真相来源，修改默认值不触及业务逻辑。
- **深层嵌套零成本访问**：`config.database.host` 替代三层 `.get()`，IDE 全程补全、mypy/pyright 全程校验，重构字段名时编译器自动追踪所有引用。
- **自文档化的配置结构**：`AppConfig` 及其嵌套的 `DatabaseConfig`、`PoolConfig` 就是活文档，看类定义就知道完整配置结构，不需要维护单独的 schema 文件。
- **`frozen=True` 防止意外修改**：配置对象不可变，任意代码都不可能不小心改掉配置值。

### 替代方案：Pydantic

```python
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str

class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    database: DatabaseConfig
    pool: PoolConfig = PoolConfig()
    logging: LoggingConfig = LoggingConfig()

config = AppConfig.model_validate(raw)
```

选择 `msgspec` 或 `pydantic` 取决于项目依赖——核心思想一致：**在系统边界处用 schema 验证，内部全链路强类型。**

> 核心原则：不可信数据（文件、网络、环境变量）进入系统的第一行就做 schema 验证。内部代码只操作验证后的强类型对象。
