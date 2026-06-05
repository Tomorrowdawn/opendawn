---
title: "Composition Over Inheritance"
category: best-practice
tags:
  - composition
  - inheritance
  - dependency-injection
  - protocol
  - specialization
  - lsp
related:
  - ../case-study/inheritance-vs-composition.md
  - ../case-study/template-method-antipattern.md
  - ../case-study/hidden-initialization.md
  - ../case-study/dependency-injection.md
summary: "Three inheritance types must not be mixed. Code sharing → composition. Interfaces → Protocol. Data hierarchy → specialization with LSP."
---

# Composition Over Inheritance

## 原则

**乐高式组装：对象声明子组件为成员，通过 `__init__` 注入；`__init__` 或 `__attrs_post_init__` 中不应创建本库的其他复杂对象。**

更重要的是：**先分清你面对的是哪种继承，混用三种继承是一切问题的根源**（Hynek Schlawack, [Subclassing in Python Redux](https://hynek.me/articles/python-subclassing-redux/)）。

## 继承的三种类型

| 类型 | 名称 | 用途 | 结论 |
|------|------|------|------|
| 类型 1 | 代码共享 | 通过父类复用方法 | ❌ 总是坏的——用组合替代 |
| 类型 2 | 接口定义（ABC/Protocol） | 约束调用契约 | ⚠️ 可选但有用——Protocol 优于 ABC |
| 类型 3 | 特化（Specialization） | "子类是父类加更多" | ✅ 必要且正确——Python 无法回避 |

大多数继承的灾难源于**把三种类型混在一个继承链里**——比如 ABC 既定义接口又塞代码共享，或者特化父类被当代码共享池用。

---

## 类型 1：代码共享 —— 用组合替代

这是"继承有害论"的主要靶子。三个核心问题：

1. **多轴变化导致子类爆炸**。如果你希望一个类在 N 个维度上独立变化，用继承就是 `2^N` 个子类。
2. **命名空间混乱**。`self.x` 来自哪个父类？阅读者需要上下跳跃才能找到——调试时更是噩梦。两个互不知晓的父类可能碰巧定义了同名属性。
3. **控制流间接**。基类调用子类方法，子类再 `super()` 回基类——理解调用链需要掌握 MRO 和 `super()` 的微妙语义。

### 代码共享的正确做法：组合 + 依赖注入

```python
from dataclasses import dataclass

@dataclass
class LLMService:
    """LLM 调用服务——通过组合拥有 client 和 cost_tracker。"""
    client: LLMClient            # 注入，不创建
    cost_tracker: CostTracker    # 注入，不创建

    async def generate(self, prompt: str) -> str:
        response = await self.client.complete(prompt)
        self.cost_tracker.record(prompt, response)  # 委托给组件
        return response.content

# ✅ 组装在外部完成
def build_llm_service(api_key: str) -> LLMService:
    client = OpenAIClient(api_key=api_key, model="gpt-4")
    tracker = CostTracker(budget_limit=10.0)
    return LLMService(client=client, cost_tracker=tracker)
```

### 禁止的行为

```python
# ❌ 在 __init__ 中创建复杂对象——隐藏依赖，难以测试
@dataclass
class BadService:
    api_key: str
    def __post_init__(self):
        self.client = OpenAIClient(self.api_key)       # 硬编码依赖
        self.tracker = CostTracker(budget_limit=10.0)   # 无法替换

# ❌ 模板方法模式——基类写控制流，子类填空
class AbstractRepository(abc.ABC):
    def add(self, item):
        self._add(item)         # ← 调子类方法
        self.seen.add(item)     # ← 基类自己的逻辑

    @abc.abstractmethod
    def _add(self, item): ...   # ← 子类填空

# ✅ 用装饰器模式（wrapper）替代模板方法
class TrackingRepository:
    def __init__(self, repo: Repository):
        self._repo = repo
        self.seen: set[Product] = set()

    def add(self, item):
        self._repo.add(item)
        self.seen.add(item)
```

---

## 类型 2：接口定义 —— Protocol 优于 ABC

接口的目的是收紧调用契约。Python 有两种方式：

| 方式 | 子类型关系 | 需要显式继承？ | 运行时检查？ |
|------|-----------|--------------|------------|
| ABC（名义子类型） | 必须显式声明或 `register()` | 是 | `isinstance()` 可用 |
| Protocol（结构子类型） | 满足协议即子类型 | **否** | 需 `@runtime_checkable` |

**优先使用 Protocol**：被检查的类不需要知道 Protocol 存在。一个类可以从来自不同包的 10 个 Protocol 中自动获得类型安全，零耦合。

```python
from typing import Protocol, runtime_checkable

# 定义接口——Protocol 可以定义在消费者旁边
class Reader(Protocol):
    def read(self) -> str: ...

# 实现者无需知道 Reader 协议
class FileSource:
    def read(self) -> str:
        return self._file.read()

class HttpSource:
    def read(self) -> str:
        return self._client.get(...)

# 消费者声明自己需要的契约
def printer(r: Reader) -> None:
    print(r.read())

printer(FileSource())   # ✅ 类型检查器自动识别
printer(HttpSource())   # ✅
```

**ABC 仅在一种场景下更有优势**：当你需要利用鸭子方法（dunder methods）实现共享逻辑时。例如 `collections.UserDict` 的场景——但即便如此，也是与"代码共享"混杂，接近危险区域。保持 ABC 轻量、只含抽象方法，切勿往里塞具体实现。

```python
# ✅ ABC 的合理用法：只定义抽象方法，不塞代码
import abc

class Repository(abc.ABC):
    @abc.abstractmethod
    def get(self, id: str) -> object | None: ...

    @abc.abstractmethod
    def save(self, obj: object) -> None: ...

# ❌ ABC 的错误用法：接口定义 + 代码共享 混在一起
class BadRepository(abc.ABC):
    @abc.abstractmethod
    def _get(self, id: str): ...        # 抽象

    def get(self, id: str):              # 具体实现——这是代码共享！
        return self._cache.get(id) or self._get(id)
```

---

## 类型 3：特化（Specialization） —— 可以且应该继承

这是唯一无法回避的继承。特化的定义：**子类 B 是父类 A 加更多的属性/行为**。一只狗是动物加更多。一个 A350 是客机加更多。

**关键测试：里氏替换原则（LSP）**——凡是父类出现的地方，子类必须能无缝替换。如果不能满足 LSP，就不是特化关系。

经典反例：正方形是矩形的特化？几何上是，代码上不是——矩形可以独立改宽高，正方形不行。这不是特化。

### 特化的正确用法：层次化数据

```python
# ✅ 特化：子类严格是父类加更多
class EmailAddr:
    id: UUID
    addr: str

class Mailbox(EmailAddr):         # Mailbox 是 EmailAddr + 密码
    pwd: str

class Forwarder(EmailAddr):       # Forwarder 是 EmailAddr + 转发目标
    targets: list[str]
```

当你拥有一个 `Mailbox`，你**知道**一定有 `pwd` 字段——类型检查器也知道。类型信息编码在类本身中。

### 错误做法对比

```python
# ❌ 方法一：把所有字段揉进一个类，用 Optional 区分
class AddrType(enum.Enum):
    MAILBOX = "mailbox"
    FORWARDER = "forwarder"

class EmailAddr:
    type: AddrType
    id: UUID
    addr: str
    pwd: str | None          # 仅 MAILBOX 有用
    targets: list[str] | None  # 仅 FORWARDER 有用

# → Optional 泛滥 + if/elif 分支爆炸 + 类型检查器无法区分变体
```

**判断信号**：当你写的字段需要注释来解释"何时使用"时——这就是特化在敲门。让非法状态不可表示（make illegal state unrepresentable）。

```python
# ❌ 方法四（组合）对此场景过于笨重
class EmailAddr:
    id: UUID
    addr: str

class Mailbox:
    email: EmailAddr
    pwd: str
# → mailbox.email.id 而非 mailbox.id，不 Pythonic
```

特化要求你遵守 LSP、避免跨层次方法交互。但只要做到，它就是最自然、最符合 Python 习惯的设计。

> 判断原则：如果你的场景在 Go 中会用 embedding，在 Python 中就适合用特化继承。

---

## 决策流程

```
需要复用代码？
 └─ 类型 1：用组合+依赖注入，坚决不继承

需要约束接口？
 └─ 类型 2：用 Protocol（首选）或纯抽象 ABC（不含代码）

需要表达"子类是父类加更多"的层次化数据？
 └─ 类型 3：用特化继承——遵守 LSP，保持层级浅（≤2 层）
```

## 其他派生原则

- **有时一个函数就够了**。不要看到一个名词就创建一个类——尤其是协调两个类之间工作的场景，答案往往是一个普通函数。
- **重复比错误的抽象便宜得多**（Sandi Metz）。先让两个类独立存在并看到完整的字段全景，再判断是否值得合并。
- **组合设计是从地基开始不同的**——不能简单地把继承树逐个节点替换成组合。需要从接口和职责的角度重新思考。

## 总结

| 做什么 | 怎么做 |
|--------|--------|
| 共享代码 | 组合 + 依赖注入 |
| 定义接口 | Protocol（结构子类型），ABC 仅用于纯抽象 |
| 层次化数据 | 特化继承（LSP + ≤2层）+ 先考虑组合方式（方法一/三）是否更简单 |
| 横切行为 | 装饰器模式（wrapper）而非模板方法 |
| 什么都不是 | 用一个函数 |

**核心教训：三种继承不混用。代码共享用组合，接口约束用 Protocol，数据层次用特化。**
