---
title: "Process Isolation"
category: best-practice
tags:
  - process
  - isolation
  - subprocess
  - context-manager
  - resource-management
summary: "External resources — subprocesses, DB connections, temp files, sockets — must live behind process boundaries managed by context managers."
---

# Process Isolation

## 原则

**外部资源通过进程边界隔离访问，生命周期由 context manager 管理。** 子进程、数据库连接、临时文件、网络套接字——任何拥有独立生命周期的外部资源，都不应与业务逻辑对象耦合在一起。

## 核心理念

外部资源的特点是：打开、使用、关闭。三者必须成对出现，且关闭必须可靠执行——即使在使用过程中发生异常。Python 的 `with` 语句（context manager）正是为此设计：它将资源获取和释放绑定在同一个语法结构中，杜绝"忘记关闭"的隐患。

更重要的是，**资源的创建和资源的注入应该是分离的**。`__init__` 中不打开连接，只接收已配置好的资源，让调用者（通常是工厂函数或依赖容器）决定何时创建和销毁。

## 推荐的模式

```python
from dataclasses import dataclass
from contextlib import asynccontextmanager
import asyncio

@dataclass
class DatabaseClient:
    """不持有连接，只描述如何连接。"""
    conn_string: str

    async def execute(self, sql: str) -> list[dict]:
        """每次执行自行管理连接生命周期。"""
        # 实际项目中应使用连接池，这里仅为示例
        ...

# ✅ context manager 管理子进程
@asynccontextmanager
async def run_worker(binary: str, args: list[str]):
    proc = await asyncio.create_subprocess_exec(
        binary, *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        yield proc
    finally:
        proc.terminate()
        await proc.wait()

# ✅ 临时文件通过 with 管理
from tempfile import NamedTemporaryFile

def process_batch(data: bytes) -> bytes:
    with NamedTemporaryFile(suffix=".csv", delete=True) as f:
        f.write(data)
        f.flush()
        return transform_file(f.name)
```

## 禁止的行为

```python
# ❌ 在 __init__ 中打开子进程或连接
class Worker:
    def __init__(self):
        self.proc = subprocess.Popen(...)   # 谁负责关闭？不知道
        self.db = sqlite3.connect(":memory:") # 生命周期混乱

# ❌ 手动管理资源——可能因异常跳过关闭
def bad_worker():
    proc = subprocess.Popen(["python", "script.py"])
    proc.wait()
    proc.terminate()  # 如果 wait() 抛异常，这行永远不会执行

# ✅ 使用 context manager
async def good_worker():
    async with run_worker("python", ["script.py"]) as proc:
        await proc.wait()
```

## 总结

进程边界是一道防火墙。外部资源在边界内创建、使用、销毁，业务逻辑只通过注入的抽象接口与资源交互。`with` 语句和 context manager 是 Python 表达"这个资源的生命周期由我负责"最清晰的方式。
