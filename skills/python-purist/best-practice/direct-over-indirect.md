---
title: "Direct Over Indirect — 伸手就拿，不要绕路"
category: best-practice
tags:
  - direct
  - indirect
  - simplicity
  - defensive-programming
  - guard-code
  - early-return
  - abstraction
  - readability
related:
  - ../case-study/hasattr-abuse.md
  - ../case-study/input-patching-chain.md
  - ../case-study/try-catch-overuse.md
  - ../case-study/hidden-initialization.md
summary: "伸手就拿，不要绕路。如果某个东西必须在，就直接访问它——不要先检查、先兼容、先打补丁。间接的防御性代码不是安全网，是 bug 的藏身之处。"
---

# Direct Over Indirect — 伸手就拿，不要绕路

## 原则

**代码应该伸手就拿，不要先摸一圈确认东西在不在。**

程序员本能地写出防御性代码——检查属性是否存在、包一层 try-catch、给输入打补丁、提前抽象以防未来需求。这些"以防万一"的代码，恰恰是真正 bug 的最佳藏身之处。当一个值必须在时，直接访问它；让不存在的状态以异常的形式暴露，而不是被静默吞掉。

## 核心理念

**防御性代码试图在每一层处理每一种可能的失败模式，结果却是：真正的失败被沉默，代码的意图被淹没在噪声里。**

好的 Python 代码是直接的——属性/键/结果，伸手就拿。精确的类型、边界的验证、清晰的接口，让"防御性检查"变得多余。**当类型系统、边界校验和接口契约已经保证了某个东西存在，你就不需要再去确认它。**

## 规则 1：伸手就拿 — 属性、键、结果，直接访问

如果某个属性必须存在、某个键必须存在、某个调用必须成功——直接访问，不要先检查。

```python
# ❌ 先摸一圈——但 subscription 不存在时程序就是错误的
def get_plan(user: User) -> str:
    if hasattr(user, "subscription"):
        return user.subscription.plan
    return "free"  # 静默掩盖了设计错误

# ✅ 直接拿——subscription 不存在就崩，崩在出错点
def get_plan(user: User) -> str:
    return user.subscription.plan
```

```python
# ❌ dict.get() 默认值——但 key 不存在应该是异常
def get_config(cfg: dict) -> str:
    return cfg.get("api_key", "")  # 空字符串会被下游当合法值传播

# ✅ 直接下标——key 不存在立即 KeyError，定位精准
def get_config(cfg: dict) -> str:
    return cfg["api_key"]
```

```python
# ❌ 先检查再调用——两层认知跳跃
def process(order: Order) -> None:
    if order.is_paid and order.is_shippable:
        ship(order)

# ✅ 直接调用——让 ship() 自己决定能不能发
def process(order: Order) -> None:
    ship(order)  # ship 内部校验，不符合条件 raise ShipError
```

## 规则 2：让错误向上走 — 不层层拦截

不要在每一层包 try-catch。真正能处理错误的只有顶层——业务层知道是重试还是降级，展示层知道是弹窗还是跳转。中间层的 try-catch 只会把丰富的异常信息压缩成 `None`/`False`/默认值。

```python
# ❌ 层层拦截——每层都把异常信息扔掉
async def handle_request(data: bytes) -> dict | None:
    try:
        request = parse(data)
    except Exception:
        return None

    try:
        result = await call_service(request)
    except Exception:
        return None

    return result

# ✅ 只在顶层处理——异常带着完整上下文向上传播
async def handle_request(data: bytes) -> dict:
    request = parse(data)            # 解析失败直接 raise
    result = await call_service(request)  # 调用失败直接 raise
    return result

# 顶层：
try:
    result = await handle_request(data)
except ParseError:
    return Response(status=400, message="Invalid request")
except ServiceTimeoutError:
    return Response(status=504, message="Upstream timeout")
```

## 规则 3：边界验证，内部信任

数据在进入系统时一次性校验、转换、清洗。越过边界之后，所有内部代码无条件信任数据。不在每层重复验证、打补丁、设默认值。

```python
# ❌ 每层打补丁——三层函数，三处 sanitize
def handle(raw: bytes) -> dict:
    data = json.loads(raw)
    data["name"] = (data.get("name") or "").strip()
    return data

def process(data: dict) -> str:
    name = (data.get("name") or "unknown").strip()[:100]
    return f"Hello, {name}"

def render(data: dict) -> str:
    name = data.get("name", "anonymous").strip()
    return f"<p>{name}</p>"

# ✅ 边界一次性验证+转换，内部直接使用
class GreetingRequest(msgspec.Struct):
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")

def handle(raw: bytes) -> str:
    request = msgspec.json.decode(raw, type=GreetingRequest)  # ← 唯一校验点
    return render(process(request))

def process(req: GreetingRequest) -> str:
    return f"Hello, {req.name}"  # 无条件信任

def render(req: GreetingRequest) -> str:
    return f"<p>{req.name}</p>"  # 无条件信任
```

## 规则 4：类型消除不确定性

精确的类型让意图可见，防御性代码不再必要。当你用 `msgspec.Struct` 或 `TypedDict` 替代 `dict[str, Any]`，访问属性的每一步都有 IDE 补全和类型检查护航——你不需要"确认字段是否存在"。

```python
# ❌ Any 模糊——每步都要检查、猜测、设默认值
def process(data: dict[str, Any]) -> str:
    user = data.get("user", {})
    name = user.get("name", "unknown")
    age = user.get("age", 0)
    # 没人知道 user 里到底还有什么字段
    return f"{name} ({age})"

# ✅ 类型精确——零防御、零猜测
class User(msgspec.Struct):
    name: str
    age: int

class Request(msgspec.Struct):
    user: User
    action: str

def process(req: Request) -> str:
    # IDE 自动补全 req.user.name, req.user.age
    # 类型检查器保证所有字段存在且类型正确
    return f"{req.user.name} ({req.user.age})"
```

## 规则 5：控制流平铺 — guard clause 在上，主逻辑在下

用 guard clause 把异常路径先处理掉。主逻辑留在顶层缩进，纵向直线阅读，不嵌套。

```python
# ❌ 深层嵌套——主逻辑藏在三层 if 里面
def apply_discount(order: Order) -> float:
    if order is not None:
        if order.user is not None:
            if order.user.is_vip:
                return order.total * 0.8
            else:
                return order.total
        else:
            return 0.0
    else:
        return 0.0

# ✅ guard clause——异常路径先退出，主逻辑平铺
def apply_discount(order: Order) -> float:
    if order is None:
        return 0.0
    if order.user is None:
        return 0.0
    if not order.user.is_vip:
        return order.total

    # 主逻辑——VIP 折扣，只有这一件事
    return order.total * 0.8
```

## 规则 6：模式出现再抽象 — 不预判未来

在同一个模式出现三次之前，不要提取抽象。为"未来可能的需求"提前创建的抽象，往往是"零价值抽象"——它引入了新的概念、新的跳转、新的学习成本，却没有消除任何已有的重复。

```python
# ❌ 提前抽象——只有一个子类，抽象层全是噪音
class Notifier(ABC):
    @abstractmethod
    def notify(self, msg: str) -> None: ...

class EmailNotifier(Notifier):
    def notify(self, msg: str) -> None:
        send_email(msg)

# ✅ 直接写——只有一个实现就不需要抽象层
def notify_user(msg: str) -> None:
    send_email(msg)

# ✅ 等到第三个通知方式出现时，再引入 Protocol
# —— SMSNotifier, PushNotifier 都出现后，提取 HasNotify Protocol
```

## 反模式速查

| 反模式 | 表现 | 为什么是坏的 |
|--------|------|-------------|
| `hasattr()` | 先确认属性存不存在再访问 | 如果属性必须在，hasattr 在运行时掩盖设计错误 |
| 层层 try-catch | 每层函数包一层 try/except | 异常信息被层层压缩，最终变成 `None`/`False` |
| 输入打补丁链 | 每层 strip/default/coerce | 没人知道原始数据长什么样，bug 定位不可能 |
| 深层 if-else 嵌套 | 主逻辑藏在三四层缩进里 | 阅读者需维护心智栈，每个分支增加认知负担 |
| 提前抽象 | 只有一个实现就建基类/Protocol | 增加了零价值的概念层级 |
| `dict.get(key, default)` 掩盖缺键 | 用默认值替代缺失的 key | key 缺失是设计错误，不该被默认值隐藏 |
| `dict[str, Any]` 传播 | 模糊类型全链路流动 | 每步都要猜测和检查字段存在性 |

## 文件与函数尺寸

| 度量 | WARNING | ERROR | 理由 |
|------|---------|-------|------|
| 文件行数 | > 400 行 | > 600 行 | 超过 600 行的文件几乎一定做了两件以上的事 |
| McCabe 圈复杂度 (C901) | — | 按项目 ruff 配置 | 高复杂度函数难以理解和测试 |
| 函数语句数 (PLR0915) | — | 按项目 ruff 配置 | 语句过多的函数应拆分为更小的职责单元 |

## 总结

直接不是粗暴——直接是精确。类型系统、边界验证和清晰的接口已经在代码之外做出了保证，你的代码不需要再去验证它们。**消掉每一行"以防万一"的代码，露出真正的业务逻辑。**
