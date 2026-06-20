---
title: "Input Patching Chain — 数据补丁链"
category: case-study
tags:
  - validation
  - defensive-programming
  - data-pipeline
  - boundary
  - fail-fast
  - msgspec
  - indirect
  - anti-pattern
related:
  - ../best-practice/direct-over-indirect.md
  - ../best-practice/fail-fast.md
  - ../best-practice/serde-boundary.md
  - ../best-practice/type-safety.md
summary: "当数据途经多层函数、每层都在 strip/default/coerce —— 没人知道原始数据长什么样。边界一次性验证转换，内部无条件信任。"
---

# Input Patching Chain — 数据补丁链

## 场景

你有一个后台任务管线：API Gateway 接收请求 → 业务函数处理 → 格式化函数渲染 → 返回客户端。数据以 `dict` 形态流转，每层函数都在"清洗"输入——去除空白、设置默认值、类型转换。线上偶尔出现"名字丢失"的 bug——用户明明填了名字，页面却显示 "anonymous"。

## 坏代码

```python
import json
from typing import Any

def receive_from_gateway(raw: bytes) -> dict[str, Any]:
    """接收 API Gateway 的原始请求。"""
    data = json.loads(raw)
    # 第一层：Gateway 可能传了空值，先给默认值
    data.setdefault("name", "unknown")
    data.setdefault("age", 0)
    return data


def process_user(data: dict[str, Any]) -> dict[str, Any]:
    """业务层处理用户数据。"""
    # 第二层：再次清洗——万一上游没处理好
    name = (data.get("name") or "").strip()
    if len(name) > 100:
        name = name[:100]  # 截断
    if not name:
        name = "anonymous"  # 再次兜底

    age = data.get("age", 0)
    if not isinstance(age, int):
        try:
            age = int(age)
        except (ValueError, TypeError):
            age = 0  # 转换失败，再来一个兜底

    return {"name": name, "age": age}


def render_response(data: dict[str, Any]) -> str:
    """渲染层：格式化为 HTML。"""
    # 第三层：不敢相信上游，再来一遍
    name = data.get("name", "anonymous").strip() or "anonymous"
    age = data.get("age", 0)
    if not isinstance(age, int):
        age = 0

    return f"<div>{name}, {age} years old</div>"


def handle_request(raw: bytes) -> str:
    """主入口。"""
    data = receive_from_gateway(raw)
    processed = process_user(data)
    return render_response(processed)
```

## 为什么坏

1. **同一件事做了三遍**：`name` 的默认值逻辑散落在三个函数中。如果产品要求把 "unknown" 改成 "visitor"，需要找到并修改三处。漏掉一处就出现不一致。

2. **原始错误被层层掩盖**：上游传了 `{"age": "twenty"}`（字符串而非整数）。`receive_from_gateway` 不改它（只设默认值），`process_user` 尝试 `int("twenty")` 失败后设为 0，`render_response` 再做一次检查——最终用户看到 0 岁，没有任何错误日志。原始问题（API 传了非法的 age 值）永远没人发现。

3. **类型不确定导致防御性链条**：因为函数签名是 `dict[str, Any]`，每一层都不敢信任上游。"万一 age 不是 int 呢？万一 name 是 None 呢？"——每一层都在重复相同的猜测。

4. **bug 定位不可能**：生产环境突然出现一批用户名字变成 "anonymous"。你需要排查——数据是 Gateway 就没传？是 `process_user` 的 strip 把名字洗空了？还是 `render_response` 的兜底逻辑触发了？三个函数各有一段补丁逻辑，谁也不知道原始数据长什么样。

5. **"以防万一"的滑坡效应**：第一个开发者给 `render_response` 加了兜底，第二个开发者觉得"我也不信任上游"于是给 `process_user` 也加了，第三个开发者看到前两层都有补丁，在 `receive_from_gateway` 又加了一套。每一层都合理（"我加个默认值又不费事"），合在一起就是灾难。

## 好代码

```python
import msgspec

class UserRequest(msgspec.Struct):
    """数据契约——字段和类型就是文档。"""
    name: str
    age: int

    def __post_init__(self) -> None:
        """边界处一次性验证全部规则。"""
        stripped = self.name.strip()
        if not stripped:
            raise ValueError("name must not be empty after strip")
        if len(stripped) > 100:
            raise ValueError(f"name too long: {len(stripped)} chars")
        self.name = stripped

        if self.age < 0 or self.age > 150:
            raise ValueError(f"age out of range: {self.age}")


# ── 处理管线：每层无条件信任数据 ──

def receive_from_gateway(raw: bytes) -> UserRequest:
    """边界：解析 + 验证 + 转换 —— 唯一的校验点。"""
    return msgspec.json.decode(raw, type=UserRequest)


def process_user(req: UserRequest) -> UserRequest:
    """业务层：直接使用数据。不需要任何清洗。"""
    # req.name 一定是干净的非空字符串，req.age 一定是合法的 int
    # 业务逻辑直接写——比如检查年龄门槛、名字合法性
    return req


def render_response(req: UserRequest) -> str:
    """渲染层：无条件信任。"""
    return f"<div>{req.name}, {req.age} years old</div>"


def handle_request(raw: bytes) -> str:
    """主入口。"""
    req = receive_from_gateway(raw)  # 唯一校验点
    processed = process_user(req)
    return render_response(processed)
```

## 为什么好 / 关键差异

- **单点验证**：`receive_from_gateway` 是唯一的校验点。校验规则在 `UserRequest.__post_init__` 中集中定义，修改一处即全局生效。越过边界后，所有下游代码无条件信任数据结构。

- **类型携带信息**：`UserRequest` 替代了 `dict[str, Any]`。下游函数看到 `req.name` 就知道它是 `str`，IDE 补全、类型检查、重构跳转全部可用。不需要任何防御性检查。

- **错误即时暴露**：`msgspec.json.decode(raw, type=UserRequest)` 在数据进入系统的第一行就校验类型和字段。`{"age": "twenty"}` 在此处立即抛出明确异常，包含文件路径和行号。不会传播到下游。

- **补丁链消失**：`process_user` 和 `render_response` 不再有任何清洗逻辑。函数从 15 行缩减到 3 行，意图一目了然。

- **原始错误可追溯**：任何数据问题都在 `receive_from_gateway` 处暴露。排查 bug 只需看异常堆栈的第一帧——不需要翻遍调用链。

> 核心原则：**只在边界验证一次，内部全链路信任。不要给数据打补丁——修好数据源。**
