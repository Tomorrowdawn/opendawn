---
title: "Serialization Boundary: Explicit Contracts at the Edge"
category: best-practice
tags:
  - serialization
  - deserialization
  - schema
  - msgspec
  - pydantic
  - boundary
related:
  - ../case-study/serde-schema.md
  - ../case-study/type-black-holes.md
summary: "Untyped raw data (dict, str, bytes) must only exist at system boundaries. Inside the system: only typed objects. Deserialize + validate immediately — never let **data pass through."
---
# Serialization Boundary: Explicit Contracts at the Edge

## 原则

**无类型的原始数据（`dict`、`str`、`bytes`）只存在于系统边界。** 在边界处立即使用 msgspec 或 pydantic 完成反序列化与验证，系统内部永远传递类型化对象。

## 核心理念

Python 的 `dict` 是"万能容器"——它不承诺任何键的存在性、值类型或结构约束。如果在系统深处仍然传递 `dict`，每一次 `data.get("foo")` 都是一次无声的信任：调用者相信键存在、类型正确、结构完整。一旦信任被打破，错误将在距离真正问题源头很远的地方爆炸。

解决方案：定义一道 **serde boundary**。边界之外是 JSON、HTTP body、配置文件等无类型数据；边界之上是 `msgspec.Struct`、`dataclass` 或 pydantic `BaseModel`。数据一跨过边界就完成结构化和验证。

## 推荐的模式

```python
import msgspec

# 定义类型化的边界模型
class IncomingMessage(msgspec.Struct):
    source_id: str
    content: str
    metadata: dict[str, str] = msgspec.field(default_factory=dict)

# ✅ 边界入口：原始 bytes → 立即解码并验证
def handle_raw(raw: bytes) -> IncomingMessage:
    return msgspec.json.decode(raw, type=IncomingMessage)

# ✅ 内部函数只接受类型化对象
def process_message(msg: IncomingMessage) -> str:
    # 无需 isinstance 检查，无需 .get() 防御
    return f"[{msg.source_id}] {msg.content}"

# ❌ 永远不要在内部传递 dict
def bad_process(data: dict) -> str:
    src = data.get("source_id", "unknown")  # 到处都是防御性代码
    content = data.get("content", "")
    return f"[{src}] {content}"
```

## 边界在项目中的位置

在一个典型应用中，serde boundary 位于以下位置：

1. **HTTP 请求入口** —— request body bytes → `msgspec.json.decode()` → 类型化对象
2. **配置文件加载** —— YAML/JSON 文件 → pydantic `model_validate()` → 配置对象
3. **数据库查询结果** —— SQL 行 → ORM 模型 → 领域对象
4. **外部 API 响应** —— HTTP response bytes → 解码 → 领域对象

```python
# ✅ 在边界处一次完成解码 + 验证 + 转换
def load_config(path: str) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text())  # 边界：raw dict
    return AppConfig.model_validate(raw)           # 边界之上：类型化对象

# ❌ 不要把 dict 作为参数传来传去
def setup_app(config: dict) -> App: ...  # 谁知道 config 里有什么？
```

## 总结

无类型数据是脏的，类型化对象是干净的。在系统边界一次性完成"清洗"——解码、验证、结构化——然后让内部代码只和干净的数据打交道。这不仅消除了遍布各处的防御性 `isinstance` 和 `.get()` 调用，也让类型检查器真正发挥作用。
