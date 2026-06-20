---
title: "回归测试自证：改错一行，测试必须抓"
category: best-practice
tags:
  - testing
  - e2e
  - regression
  - verification
  - self-check
  - subprocess
  - integration
related:
  - red-green-tdd.md
  - ../case-study/test-documentation.md
summary: "写完回归测试后，在关键路径故意改错一行。测试必须挂。不挂就证明测试没碰到真实代码路径——你测了个幻影。重写。"
---

# 回归测试自证：改错一行，测试必须抓

## 规则

**不要写单元测试。** 单元测试耦合实现细节，每次改代码都要改测试——起不到回归保护作用，只是维护负担。回归保护只写一种测试：从真实入口进入、走完整用户流程、验证可观测结果的 E2E 测试。

## 场景匹配

- **问题**: 回归测试全绿，但你怀疑它是否真的覆盖了关键路径。不需要 agent 判断什么是真正的 E2E——用事实说话。
- **上下游**: 适用于任何有可触发行为变更的代码路径（CLI 服务、HTTP API、SDK 库）。

## 动作

回归测试写完且全绿后，必须执行以下自证：

```bash
# Step 1: 确认测试全绿
pytest tests/ -v -k "test_<your_regression_test>"
# 1 passed

# Step 2: 找到关键路径上的一行代码，故意改错
#     → 反向断言（assert result == wrong_value）
#     → 返回 None
#     → 删掉必须执行的语句
#     → 改硬编码值
# 例：src/service.py line 42
#   user = create_user(name=name)        # 原始
#   user = create_user(name="<BROKEN>")  # 故意改错

# Step 3: 重跑测试 → 必须 FAIL
pytest tests/ -v -k "test_<your_regression_test>"
# FAILED  ← 正确。测试真的碰到了改错的那行。

# Step 4: 恢复源码
git checkout -- src/
```

## 测试没挂的情况 → 测试无效

```bash
# 你故意改错了关键路径上的一行代码，但测试仍然 PASSED
pytest tests/ -v -k "test_create_user"
# 1 passed  ← 错误。测试没碰到这行代码。

# 根本原因（常见）：
#   - import 服务内部模块自己组装 App 实例，没走 CLI/HTTP 入口
#   - mock 了 config、mock 了数据库、mock 了外部依赖
#   - 测试唯一的 assert 是"启动不抛异常"，没走完整用户操作流程
#
# 解决：删除重写。从 CLI/HTTP 入口启动真实进程，走完整用户操作。
```

## Agent 执行清单

- [ ] 回归测试从真实入口（CLI 或 HTTP）进入？禁止 import 内部模块组装 app。
- [ ] 测试走了完整用户操作流程（CRUD / 请求-响应 / 副作用验证）？不是仅"启动不抛异常"。
- [ ] 测试全绿后，在关键路径故意改错一行 → 测试 FAILED？
- [ ] 如果改错后测试仍然 PASSED → 测试无效 → 删除重写。
