---
title: "Naming and Readability"
category: best-practice
tags:
  - naming
  - readability
  - clean-code
  - conventions
  - comments
summary: "Names reveal intent. Functions do one thing at one abstraction level. Comments explain why, not what. Code is read far more than written."
---

# Naming and Readability

## 原则

**命名揭示意图，函数做一件事且只做一件事，注释只解释 why 不解释 what。** 代码是写给人看的，顺便能在机器上运行。

## 核心理念

好的命名像一个微缩的文档：阅读者看到变量名就知道它代表什么，看到函数名就知道它会做什么。低质量的命名——单字母、缩写、泛化动词——强迫阅读者跳转到定义处才能理解代码，每一次跳转都是一次认知中断。

更根本的原则是 **单一抽象层级**：一个函数内部的所有操作应该停留在同一个抽象层级上。如果函数同时包含 SQL 拼接和业务规则判断，那它做了两件事——应该拆成两个函数。

## 意图揭示型命名

```python
# ❌ 命名不揭示意图
d = date.today() - start_date
if d > 30:
    send(u, d)

# ✅ 变量名和函数名自解释
elapsed_days = (date.today() - start_date).days
if elapsed_days > 30:
    notify_user_about_expiry(user, elapsed_days)
```

命名指南：
- **变量名 = 名词短语**：`elapsed_days`、`active_sessions`、`retry_count`
- **函数名 = 动词短语**：`notify_user_about_expiry()`、`decode_incoming_message()`
- **谓词函数以 `is_` / `has_` / `can_` 开头**：`is_expired()`、`has_permission()`

## 单一抽象层级

```python
# ❌ 一个函数混合了三个抽象层级
def handle_request(raw: bytes) -> str:
    data = json.loads(raw)                              # 解析层
    user = db.execute("SELECT * FROM users WHERE id=?",  # 数据库层
                      (data["user_id"],)).fetchone()
    if user["plan"] == "pro":                            # 业务逻辑层
        return "Welcome back, pro user!"
    return "Welcome!"

# ✅ 每层一个函数
def handle_request(raw: bytes) -> str:
    msg = parse_request(raw)
    user = fetch_user(msg.user_id)
    return welcome_message(user)

def parse_request(raw: bytes) -> RequestMsg: ...
def fetch_user(user_id: str) -> User: ...
def welcome_message(user: User) -> str: ...
```

## 注释：只写 why，不写 what

```python
# ❌ 注释复述代码——what
# 将 counter 加 1
counter += 1

# ❌ 无意义的噪声注释
# 检查用户是否存在
if user is None:
    ...

# ✅ 注释解释决策原因——why
# 使用指数退避而非固定间隔，因为 WeChat API
# 在限流时会返回 Retry-After 头，但其值不总是准确
await asyncio.sleep(min(backoff * 2, 60.0))

# ✅ 当"为什么"能在代码中表达时，不需要注释
# 用常量替代魔术数字，本身就是"why"
MAX_RETRY_INTERVAL = 60.0
await asyncio.sleep(min(backoff * 2, MAX_RETRY_INTERVAL))
```

## 总结

三句话记住：如果需要在变量声明旁加注释，改名。如果函数做了两件事，拆成两个函数。如果一段代码需要注释来解释它做了什么，重写它——让它自己说话。
