---
title: "Coroutines vs Threads"
category: best-practice
tags:
  - async
  - asyncio
  - coroutine
  - thread
  - concurrency
  - gil
summary: "I/O-bound → asyncio coroutines. CPU-bound → ProcessPoolExecutor. Never mix threads when the GIL is involved."
---

# Coroutines vs Threads

## 原则

> **I/O 密集 → asyncio 协程，CPU 密集 → multiprocessing，线程是万恶之源。**

Python 的并发模型中有三种机制：线程（threading）、协程（asyncio）、多进程（multiprocessing）。选错一个，你会同时承受性能损失和调试折磨。

## I/O 密集型：asyncio 协程

当你的程序大部分时间在等待——网络请求、数据库查询、文件读写——协程是最优解。单个线程管理数千个并发连接，没有 GIL 竞争，没有上下文切换开销。

```python
import asyncio

async def fetch_all(urls: list[str]) -> list[str]:
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [await r.text() for r in responses]

# 数千个 URL 同时请求，只用一个线程
results = asyncio.run(fetch_all(many_urls))
```

协程的核心优势：
- 协作式调度，没有抢占，代码在 `await` 处显式交出控制权
- 不需要锁（单线程），没有死锁风险
- 堆栈跟踪清晰，每个协程的调用链完整可读

## CPU 密集型：multiprocessing

当你需要真正的并行计算——图像处理、科学计算、大规模数据转换——必须使用多进程绕过 GIL。

```python
from multiprocessing import Pool

def heavy_compute(x: int) -> int:
    return sum(i * i for i in range(x * 1000000))

with Pool() as pool:
    results = pool.map(heavy_compute, [10, 20, 30, 40])
```

## 为什么线程是万恶之源

```python
import threading

# ❌ 线程的三大罪状：
# 1. GIL 让 CPU 密集型线程形同虚设——同一时刻只有一个线程执行 Python 字节码
# 2. 竞态条件——非原子操作导致的间歇性 bug，极难复现
# 3. 死锁——Lock 顺序不当导致线程相互等待

counter = 0
lock = threading.Lock()

def increment():
    global counter
    for _ in range(1000000):
        with lock:
            counter += 1  # 即使加了锁，性能也远逊于协程/多进程
```

线程在 Python 中有且仅有一个合法场景：**调用不提供 async 接口的阻塞 C 库**，此时可以用 `asyncio.to_thread()` 将阻塞调用抛到线程池，但不阻塞事件循环。

```python
# ✅ 线程的唯一合理用法
result = await asyncio.to_thread(some_blocking_c_library_call, arg1, arg2)
```

## 总结

选择口诀：**等得多用协程，算得多用进程，线程能不用就不用。** 当你觉得"这里可能需要线程"的时候，再想一想——十有八九，协程或多进程是更好的答案。
