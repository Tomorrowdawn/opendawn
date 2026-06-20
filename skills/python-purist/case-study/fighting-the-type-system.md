---
title: "Fighting the Type System: 与类型系统对抗"
category: case-study
tags:
  - type-system
  - metaclass
  - dynamic-type
  - getattr
  - cast
  - introspection
  - anti-pattern
related:
  - ../best-practice/trust-your-types.md
  - ../best-practice/type-safety.md
  - ../best-practice/direct-over-indirect.md
  - ../case-study/type-black-holes.md
summary: "用 type() 动态创建类 + 打属性补丁、用 __class_getitem__ 元类 hack 弥补类型系统缺陷、手动 get_origin/get_args 自建类型反射——这些都是在类型系统之外修补裂痕，而非在类型系统之内解决根本问题。"
---

# Fighting the Type System: 与类型系统对抗

## 场景

你的系统需要从 `msgspec.Struct` 动态生成 Tortoise ORM 模型。你觉得"让类型检查器看到 ORM 模型的属性"不太可行，于是选择用 `type()` 动态创建类，把 schema 元数据作为隐藏属性 (`_yuubot_schema_type`) 打上去，然后通过 `getattr()` 和 `cast()` 在外部访问它们。

同时，你的工具系统需要支持 `Tool[Ctx]` 语法（不指定 `Result` 泛型参数），但 Python 3.12 不支持默认 TypeVar——于是你写了一个 `__class_getitem__` 元类 hack。你的 JSON Schema 生成器手动用 `get_origin()`/`get_args()` 解析类型注解。

这些努力都指向同一个目标:**让类型系统配合你的意愿工作**。但每次修补都在类型系统外部引入新的复杂性，而根本问题从未被解决。

这个模式来自 `model_factory.py`、`_tool.py`、`_schema.py` 的真实代码。

## 坏代码

```python
# ── 模式 1: type() 动态创建类 + 隐藏属性补丁 ──

def resource_model(name: str, schema_type: type[msgspec.Struct], ...) -> type[Model]:
    attrs: dict[str, Any] = {"__module__": module}
    
    for field in msgspec.structs.fields(schema_type):
        attrs[field.name] = _tortoise_field(field, spec)  # ① 动态组装 __init__ 属性
    
    attrs["_yuubot_schema_type"] = schema_type       # ② 隐藏属性 —— 类型检查器看不见
    attrs["_yuubot_schema_fields"] = frozenset(...)   # ③ 又一个隐藏属性
    attrs["_to_builtins"] = _to_builtins              # ④ 动态方法补丁
    
    return type(name, (Model,), attrs)  # ⑤ 运行时创建类

# ── 然后在 protocol.py 里通过 getattr 访问这些隐藏属性 ──

def schema_type_of(orm_type: type[Model]) -> type[msgspec.Struct]:
    return cast(type[msgspec.Struct], getattr(orm_type, "_yuubot_schema_type"))
    # ↑ cast() + getattr() —— 这两个函数的使用说明类型系统完全被绕过了

# ── 模式 2: __class_getitem__ 元类 hack 弥补 TypeVar 默认值 ──

class _DefaultAnyResult:
    @classmethod
    def __class_getitem__(cls, params: Any) -> Any:
        if not isinstance(params, tuple):
            params = (params, Any)  # 自动填充缺失的泛型参数
        return GenericAlias(cls, params)

# ── 模式 3: 手动类型反射 —— 重新实现类型系统 ──

def _unwrap_optional(field_type: object) -> tuple[object, bool]:
    origin = get_origin(field_type)
    if origin not in {Union, UnionType}:
        return field_type, False
    args = get_args(field_type)
    if NoneType not in args:
        return field_type, False
    non_none = tuple(arg for arg in args if arg is not NoneType)
    if len(non_none) != 1:
        return field_type, True
    return non_none[0], True
    # ↑ 15 行代码重新实现了 Optional 展开 ——
    # 对应的库能力: msgspec.structs.fields() 已经告诉你字段是否 required

def type_to_json_schema(tp: Any) -> dict[str, Any]:
    """手动解析 Python 类型生成 JSON Schema —— 80 行 switch-case"""
    origin = get_origin(tp)
    if origin is list:    ...
    elif origin is dict:   ...
    elif origin is tuple:  ...
    elif origin is Union:  ...
    # ↑ 在重新发明 pydantic、msgspec.json.schema_components 已经提供的功能
```

## 为什么坏

1. **`type()` 动态创建类让类型检查器完全失效**。`type(name, (Model,), attrs)` 在运行时创建了一个类，但 mypy/pyright 无法推断这个类的属性。结果是: 调用处无法获得任何 IDE 补全、任何类型检查、任何跳转能力。为了弥补这个缺口，你不得不在 `protocol.py` 中写 5 个 `getattr` + `cast()` wrapper——这是对同一个根本问题的 5 次修补。

2. **隐藏属性 (`_yuubot_*`) 是类型系统之外的旁路**。这些属性的命名约定 (`_yuubot_`) 暗示了它们的不稳定性——它们是"我们私下约定的"，不是"类型系统保证的"。当 reader 看到 `getattr(orm_type, "_yuubot_schema_type")`，她知道这是脆弱代码——改一处可能断三处，而类型检查器不会发出警告。

3. **`__class_getitem__` hack 在解决一个即将消失的问题**。Python 3.13 引入了 `TypeVar(default=...)`。这个 hack 的存在时间窗口不到一年。为短期问题引入元编程的长期复杂性，是不划算的。`try: TypeVar("Result", default=Any) except TypeError: TypeVar("Result")` 这一段 try/except 说明你已经知道这是版本敏感的——但你还是选择了运行时 workaround 而不是直接适配。

4. **手动类型反射代码的 bug 密度极高**。`_unwrap_optional` 的 15 行代码需要正确处理: `str | None`、`Union[str, None]`、`Optional[str]`、`Union[str, int, None]`（非法 Optional——多个非 None 类型）。每一种边缘情况都可能被遗漏。而 `msgspec.structs.fields()` 已经处理了所有这些——它是经过数千个项目验证的实现。

5. **每一种 hack 都增加了"理解的债务"**。新加入的开发者看到 `type(name, (Model,), attrs)` 时需要理解: 这个类来自哪里？它的属性在什么时候定义？`_to_builtins` 方法的实现在哪里？为什么用 `getattr` 访问而不是直接调用？这些问题的答案散布在 `model_factory.py`、`protocol.py`、`orm.py` 三个文件中——每一个都是理解的障碍。

## 好代码

```python
# ── 方案 1: 接受 Python 类型系统的限制，使用显式的静态类定义 ──

class UserResource(msgspec.Struct, frozen=True):
    """领域模型 —— 类型安全、IDE 友好"""
    id: str
    name: str
    email: str
    created_at: datetime = msgspec.field(default_factory=datetime.now)

class UserModel(Model):
    """ORM 模型 —— 显式定义，静态类型"""
    id = fields.CharField(pk=True, max_length=36)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "users"
    
    # 显式转换方法 —— 类型安全的桥梁
    def to_resource(self) -> UserResource:
        return UserResource(
            id=self.id,
            name=self.name,
            email=self.email,
            created_at=self.created_at,
        )
    
    @classmethod
    def from_resource(cls, resource: UserResource) -> "UserModel":
        return cls(
            id=resource.id,
            name=resource.name,
            email=resource.email,
        )

# ── 方案 2: 如果确实需要动态生成，使用 Protocol 描述生成的类 ──

from typing import Protocol

class HasSchemaType(Protocol):
    """描述动态生成的 ORM 类必须满足的接口。"""
    _yuubot_schema_type: type[msgspec.Struct]
    
    def to_resource(self) -> msgspec.Struct: ...

# 生成时使用 Protocol 验证:
def resource_model(name: str, schema_type: type[msgspec.Struct], ...) -> HasSchemaType:
    ...
    return cast(HasSchemaType, type(name, (Model,), attrs))

# ── 方案 3: 使用 msgspec 内置能力替代手动类型反射 ──

# ❌ 旧的 80 行: 手动 get_origin/get_args/UnionType 分支
def type_to_json_schema(tp: Any) -> dict[str, Any]: ...

# ✅ 新的 3 行: 使用 msgspec 内置能力
def struct_to_json_schema(schema_type: type[msgspec.Struct]) -> dict[str, Any]:
    """基于 msgspec Struct 生成 JSON Schema"""
    from msgspec.json import schema_components
    schemas, _ = schema_components([schema_type])
    return schemas[0]

# ── 对于泛型默认值: 直接适配 Python 版本 ──

# Python 3.13+: 使用正式语法的 default TypeVar
# Python 3.12-: 接受用户在 Tool 调用时必须指定两个泛型参数
# 不要为 3.12 写 __class_getitem__ hack —— 
# 等 3.13 普及后这个 hack 就是需要清理的技术债务
```

## 为什么好 / 关键差异

1. **类型检查器全程有效**。静态定义的 `UserModel` 类让 mypy/pyright 看得到所有属性——IDE 补全、跳转、重构全部可用。不需要 `getattr` 和 `cast`。

2. **转换逻辑收拢在模型类内**。`to_resource()` 和 `from_resource()` 是显式的方法，调用处看到 `user_model.to_resource()` —— 一步跳转就能看到转换逻辑。不经过 `protocol.py` → `getattr` → `_to_builtins` → `msgspec.convert` 的四层间接。

3. **利用库能力而非重新实现**。`msgspec.json.schema_components()` 替代了 80 行手动类型反射。`msgspec.structs.fields()` 替代了手动 `_unwrap_optional`。使用库能力意味着: 更少的代码、更少的 bug、自动跟随库升级获得改进。

4. **技术债务有明确生命周期**。如果你确实需要 `__class_getitem__` hack 来支持老版本 Python，在 hack 旁边加上 `# TODO: Remove when min Python is 3.13`。这样你知道这块代码是临时的，不是永久的。

### 核心原则

> 不要和类型系统对抗。如果你发现自己写了 `type()` 动态创建类、`getattr` 访问隐藏属性、`cast` 欺骗类型检查器、手动 `get_origin`/`get_args` 重新实现类型反射——停下来。回到类型系统内部，找到真正能协作的方式。每次你用元编程绕过类型系统，你都在为你的未来创造理解成本。
