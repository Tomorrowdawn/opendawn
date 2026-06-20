---
title: "Trust Your Types — 信任你亲手建立的类型体系"
category: best-practice
tags:
  - types
  - trust
  - direct
  - indirect
  - serde
  - serialization
  - to-builtins
  - anti-pattern
related:
  - ../case-study/roundtrip-serialization.md
  - ../case-study/phantom-protocol.md
  - ../case-study/thin-wrapper-epidemic.md
  - ../case-study/fighting-the-type-system.md
  - ../best-practice/direct-over-indirect.md
  - ../best-practice/serde-boundary.md
  - ../best-practice/type-safety.md
summary: "一旦你用了 msgspec.Struct、Protocol、TypeAlias，就信任它们。不要在内部做 to_builtins()、不要 cast 欺骗类型检查器、不要手动重新验证。类型系统是契约——遵守它，而不是绕过它。"
---

# Trust Your Types — 信任你亲手建立的类型体系

## 原则

**类型系统是你和代码之间的契约。你花了时间定义 `User` Struct、声明 `UserRepository` Protocol、写类型注解——现在，遵守它。**

对类型系统的不信任不是一种谨慎，而是一种间接。每一次绕过类型——`to_builtins()`、`cast()`、手动 `get_origin()`——都是在说："我不相信我自己的设计"。这种不信任会渗透到代码的每一层，最终形成一座间接的巴别塔。

## 核心理念

`direct-over-indirect` 讲了"伸手就拿"——信任你的接口契约，不要先摸一圈再访问。`serde-boundary` 讲了"脏数据只存在于边界"——在边界完成清洗，内部永远传递类型化对象。`trust-your-types` 是这两个原则的上层统一：

> **信任是你主动给予的，不是被动等待的。你定义了类型体系，现在用它。**

三个层次的信任：

| 层次 | 信任什么 | 不信任的表现 |
|------|---------|-------------|
| **数据** | `Struct` 成员完整且类型正确 | `to_builtins()` 拆成 dict 再 `msgspec.convert()` 重建 |
| **接口** | Protocol/ABC 的实现者遵守契约 | `@runtime_checkable` + `isinstance()` 反射检查 |
| **类型** | 类型注解表达了真实意图 | `cast()` 欺骗、手动 `get_origin()`/`get_args()` 自省 |

## 规则 1: 类型化数据就地使用，不要拆了重建

`msgspec.Struct` 已经是"干净"数据——字段存在、类型正确、默认值已填充。在内部传递时，它就是最佳形态。不需要 `to_builtins()` 拆成 dict 再拼回去。

```python
# ❌ 信任缺失——Struct → dict → Struct 往返
def to_orm_fields(resource: Resource, row_type: type[Model]) -> dict[str, Any]:
    values = msgspec.to_builtins(resource)  # 拆掉类型
    orm_fields = {name: value for name, value in values.items() if ...}
    return orm_fields

async def from_orm(row: Model, resource_type: type[ResourceT]) -> ResourceT:
    fields = dict(row)                      # Model → dict
    return msgspec.convert(fields, type=resource_type)  # 重建类型

# ✅ 信任类型——Model 内直接映射，类型出口是强类型

class UserModel(Model):
    id = fields.CharField(pk=True, max_length=36)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255)

    @classmethod
    def from_domain(cls, user: User) -> "UserModel":
        """领域 Struct → ORM Model —— 属性直接映射，不经过 dict 中间层。"""
        return cls(id=user.id, name=user.name, email=user.email)

    def to_domain(self) -> User:
        """ORM Model → 领域 Struct —— 一次 msgspec.convert，类型出口是强类型。"""
        return msgspec.convert(
            {"id": self.id, "name": self.name, "email": self.email}, type=User
        )

# 调用处:
model = UserModel.from_domain(user)  # 不经过 to_builtins
await model.save()
return model.to_domain()             # → User, 不是 dict[str, Any]
```

核心区别: 好代码里 `to_builtins()` 消失了——因为 Struct 已经是 builtins 的等价物。`msgspec.convert()` 只在"不可信数据→可信对象"的边界出现一次。

## 规则 2: 接口的信任是编译期的，不是运行时的

`Protocol` 是 type checker 的工具，不是运行时反射的工具。`@runtime_checkable` + `isinstance()` 是对类型系统的迂回——你在用运行时机制验证编译期契约。如果你真的需要在运行时检查，那说明你应该用 ABC 而不是 Protocol。

```python
# ❌ 运行时不信任——Protocol 套上 @runtime_checkable
@runtime_checkable
class LlmSession(Protocol):
    async def stream(self, **options) -> StreamResult: ...

# 然后在代码里做运行时 isinstance
if isinstance(factory, SelectableLlmSessionFactory):  # ← 这不信任
    factory = factory.with_selector(selector)

# ✅ 类型系统信任——只有一个实现就不要定义 Protocol
# 直接使用具体类型
class YuuSession:
    async def stream(self, **options) -> StreamResult: ...

# 等真的有第二个实现时，再引入 Protocol
```

核心原则: **"模式出现再抽象"** (`direct-over-indirect` 规则 6)。Protocol 的设计意图是多态——没有多态需求，就不需要 Protocol。

## 规则 3: 类型注解是真相——不要对着它说谎

`cast()` 的本质是告诉类型检查器"相信我，这个东西的类型不是你以为的那样"。但如果你频繁使用 `cast()`，说明你的类型定义和实际数据流之间存在裂痕——你在修补裂缝，而不是修复根本原因。

```python
# ❌ cast 连击——每行都在和类型系统对抗
fields = dict(cast(Iterable[tuple[str, object]], row))
fields = cast(dict[str, object], decrypt_secret_values(fields, secret_codec))
return cast(RecordT, inserted)

# ✅ 修复根本原因——让类型定义匹配实际数据流
# 使用 TypedDict 或 msgspec.Struct 描述真实的 ORM 行结构
class ORMRow(msgspec.Struct):
    id: str
    name: str
    created_at: datetime | None = None

fields = msgspec.structs.asdict(orm_row)  # 类型安全，无需 cast
return msgspec.convert(fields, type=RecordSchema)  # 只在边界验证
```

`cast()` 的合法使用场景只有两种:
1. **类型收窄**——你做了运行时检查，但 type checker 无法推断（如 `isinstance` 分支内）
2. **库签名不完整**——你依赖的第三方库类型 stub 有误，且你无法修复上游

任何其他场景的 `cast()` 都是在掩盖类型设计的缺陷。

## 规则 4: 类型系统是工具，不是障碍——用库，不要绕库

当你发现自己写 `get_origin()`、`get_args()`、`UnionType` 分支来解析类型注解时，停下来。你在重新发明类型系统。msgspec、pydantic、attrs 已经解决了这些问题。

```python
# ❌ 手动重新发明类型反射
def _unwrap_optional(field_type):
    origin = get_origin(field_type)
    if origin not in {Union, UnionType}:
        return field_type, False
    args = get_args(field_type)
    if NoneType not in args:
        return field_type, False
    non_none = tuple(arg for arg in args if arg is not NoneType)
    ...

# ✅ 使用库提供的能力
# msgspec 的 structs.fields() 已经处理了 Optional 展开
for field in msgspec.structs.fields(SchemaType):
    field_type = field.type       # 原始类型注解
    is_optional = field.required is False  # msgspec 已经分析过了
```

核心原则: **你不应该解析类型注解——你应该让类型系统为你工作。** Python 的类型系统不是完美的，但绕过它的人为复杂性远大于它的局限性。

## 反模式速查

| 反模式 | 表现 | root cause |
|--------|------|-----------|
| `to_builtins()` 往返 | Struct → dict → convert → Struct | 不相信 Struct 在内部传递是安全的 |
| `cast()` 连击 | 每行一个 `cast()` 欺骗类型检查器 | 类型定义和数据流之间存在未解决的裂痕 |
| `@runtime_checkable` Protocol | 编译期契约通过运行时 `isinstance` 验证 | 不相信 Protocol 的实现者会遵守契约 |
| 手动 `get_origin`/`get_args` | 重新实现类型反射 | 不了解库已经提供了这些能力 |
| 元类 `__class_getitem__` hack | 为弥补 Python 类型系统缺陷而引入元编程 | 在类型系统外修补，而非在系统内适配 |

## 信任的边界

信任类型系统不等于盲目。信任有边界:

- **边界之外不应信任**——外部输入（HTTP、文件、数据库）在 `serde-boundary` 处验证
- **内部应无条件信任**——越过边界后，代码不应再重复验证
- **类型系统会犯错**——但绕过它引入的人为错误远多于类型系统本身的错误

## 总结

你花时间定义了 `User` Struct、写了类型注解、建立了 Protocol 接口。这些不是装饰——它们是契约。信任你自己的代码。信任类型系统。消掉每一行"以防万一类型不 work"的间接代码。

> **你建立的类型体系是你的盟友，不是你的敌人。停止和它对抗，开始和它合作。**
