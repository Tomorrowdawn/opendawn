---
title: "Round-Trip Serialization: Struct → dict → Struct"
category: case-study
tags:
  - serialization
  - round-trip
  - to-builtins
  - msgspec
  - orm
  - type-safety
  - anti-pattern
related:
  - ../best-practice/trust-your-types.md
  - ../best-practice/serde-boundary.md
  - ../best-practice/type-safety.md
  - ../case-study/type-black-holes.md
summary: "类型化数据在内部传递时被拆成 dict，然后又用 msgspec.convert 重建为 Struct。同一个调用链内，类型信息被丢弃再恢复——这是一种对类型系统的不信任，不是防御性编程。"
---

# Round-Trip Serialization: Struct → dict → Struct

## 场景

你的系统使用 `msgspec.Struct` 定义了领域模型 `Resource`。数据在写入数据库时需要转换为 ORM 字段，读取时又需要从 ORM 行重建 `Resource` 对象。你在每一层都调用了 `msgspec.to_builtins()` 和 `msgspec.convert()`——同一个对象在这条链路上被序列化了两次、反序列化了两次。

这个模式来自 `yuubot-v2/resources/orm.py` 的真实代码。

## 坏代码

```python
import msgspec
from typing import Any, TypeVar, cast
from tortoise import Model

ResourceT = TypeVar("ResourceT")

# ── 写路径: Struct → to_builtins → dict → ORM ──

def to_orm_fields(resource: object, row_type: type[Model]) -> dict[str, Any]:
    values = msgspec.to_builtins(resource)            # ① Struct → dict
    if not isinstance(values, dict):
        raise TypeError(...)
    orm_fields = {
        name: value for name, value in values.items() # ② dict → 字段筛选
        if name not in generated_fields
    }
    return _replace_references_with_ids(orm_fields, row_type)  # ③ dict → dict

# ── 读路径: ORM → dict → msgspec.convert → Struct ──

async def from_orm(
    row: Model,
    resource_type: type[ResourceT],
) -> ResourceT:
    fields = dict(cast(Iterable[tuple[str, object]], row))  # ④ Model → dict
    for name, reference in _references(type(row)).items():
        fields.pop(f"{name}_id", None)
        fields[name] = await _referenced_resource(row, name, reference)
    return msgspec.convert(fields, type=resource_type, strict=False)  # ⑤ dict → Struct

# ── 调用链 ──
# insert:  Struct ─→ ① msgspec.to_builtins ─→ ② dict ─→ ORM.create
# select:  ORM ─→ ④ dict(fields) ─→ ⑤ msgspec.convert ─→ Struct
# 总操作: Struct → dict → ORM → dict → Struct  ← 一次完整的往返
```

## 为什么坏

1. **类型信息被故意丢弃**。`resource` 作为 `msgspec.Struct` 已经有完整的类型信息——字段名、类型、默认值都已经过验证。`msgspec.to_builtins(resource)` 把它拆成一个裸 `dict`，所有类型保证荡然无存。

2. **往返不产生新信息**。`Struct → dict → ORM → dict → Struct` 这条链路上，最后得到的 `Struct` 和最初的 `Struct` 在类型层面是同样的东西。中间的两次 `to_builtins`/`convert` 是纯粹的开销——没有任何边界被跨越，没有任何验证产生新价值。

3. **错误位置漂移**。如果 `msgspec.to_builtins(resource)` 返回的 dict 缺少某个字段（因为 Struct 定义中的 `omit_defaults` 等选项），错误不会在这里暴露——它会在下游的 `msgspec.convert(fields, type=resource_type)` 处爆炸。但此时数据已经经过了 ORM 往返，原始上下文已丢失。

4. **维护成本指数级**。Struct 新增一个字段 → 需要在 `to_orm_fields` 中确认字段筛选逻辑 → 需要在 `from_orm` 中确认字段恢复逻辑 → 需要在 `model_factory` 中确认 ORM 列映射。一个字段的变更需要在 4 个位置同步。

5. **`to_builtins` 的语义被误用**。`msgspec.to_builtins` 是为 JSON 序列化设计的——它将 Struct 转为可 JSON 序列化的 Python 原语。但在 ORM 场景中，你根本不需要 JSON 兼容性——你只是要把字段值传给 ORM 的 `create(**fields)`。Struct 的字段值已经是 ORM 可接受的 Python 原语。

## 好代码

```python
import msgspec
from typing import Any
from tortoise import Model

# ── 直接字段映射 —— 不需要 to_builtins ──

def struct_to_orm_kwargs(struct: msgspec.Struct) -> dict[str, Any]:
    """将 Struct 字段直接映射为 ORM create/update 的 kwargs。
    
    不做序列化——Struct 的字段值已经是 Python 原语。
    """
    return {
        field.encode_name: getattr(struct, field.encode_name)
        for field in msgspec.structs.fields(struct)
    }

# ── 只在不可信数据边界做一次 convert ──

async def orm_row_to_struct(
    row: Model,
    schema_type: type[msgspec.Struct],
) -> msgspec.Struct:
    """从 ORM 行转回 Struct —— 只在这一处调用 msgspec.convert。
    
    这是从"不可信数据"(ORM 查询结果)到"可信对象"(Struct)的边界。
    在此之前的代码不对 ORM 行的字段做任何假设。
    """
    raw: dict[str, object] = {}
    for field_name, column in row._meta.fields_map.items():
        raw[field_name] = getattr(row, field_name)
    return msgspec.convert(raw, type=schema_type)

# ── 调用链 ──
# write: Struct ─→ struct_to_orm_kwargs ─→ ORM.create(**kwargs)
# read:  ORM ─→ orm_row_to_struct ─→ Struct
# 总操作: 零往返，只有一次边界验证
```

## 为什么好 / 关键差异

1. **零往返**。写路径：`Struct` 的字段值直接作为 ORM 的 `create(**kwargs)` 参数——没有中间 dict 序列化。读路径：`msgspec.convert` 只在从 ORM 读到数据的边界处调用一次——因为 ORM 查询结果是"不可信数据"，需要在这里完成验证。

2. **使用库能力，而非重新造轮子**。`msgspec.structs.fields()` 提供了 Struct 的所有字段元信息——名称、类型、默认值、encode_name。不需要 `to_builtins()` 把整个 Struct 拆成 dict 再去筛选字段。

3. **修改点收敛**。Struct 新增字段后：`msgspec.structs.fields()` 自动包含新字段 → `struct_to_orm_kwargs` 自动映射 → ORM 列定义由 `model_factory` 一次配置。字段变更不再需要在 4 个位置手动同步。

4. **`to_builtins` 不再出现**。`to_builtins` 的唯一合法场景是：你确实需要一个 JSON 兼容的表示来调用第三方 API 或写入网络。在内部 ORM 映射中，它没有存在的理由。

### 核心原则

> `to_builtins()` 不应该出现在内部数据传递中。类型化对象 (`Struct`) 在内部传递时就是最佳形态。`msgspec.convert()` 只在"不可信数据 → 可信对象"的边界调用一次。中间层不需要，也不应该做序列化。
