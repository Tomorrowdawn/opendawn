---
title: "Red-Green-Refactor TDD"
category: best-practice
tags:
  - tdd
  - testing
  - pytest
  - red-green
  - test-first
summary: "Simon Willison's agentic TDD pattern adapted to Python. Write test → watch it FAIL → write minimal code → watch it PASS → refactor. Never skip the red step."
---
# Red-Green-Refactor TDD

## 起源

Simon Willison 在其 [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/) 指南中提出：**"Use red/green TDD"** 是一个极其高效的 coding agent 提示词模式。它不仅是测试方法论，更是约束 agent 行为、确保交付质量的工程实践。

## 为什么 TDD 特别适合 Coding Agent

Coding agent 面临两个核心风险：(1) 写出不能运行的代码；(2) 写出不需要的代码。测试先行同时防御这两个问题——测试定义了"正确"的边界，测试失败证明实现还不存在，测试通过证明实现已完成。此外，积累的测试套件是防止未来回归的最有效手段。

## Red/Green 四步流程

### 第一步：Red —— 先写测试，确认失败

写测试函数，运行它，亲眼看到它 **FAIL**。跳过这一步是致命的：你可能写了一个本来就能通过的测试，它根本没有验证新功能。

```python
# test_calculator.py
def test_add():
    calc = Calculator()
    assert calc.add(2, 3) == 5
```

```bash
$ pytest test_calculator.py -k test_add
# FAILED - NameError: name 'Calculator' is not defined  ← 这是正确的失败
```

### 第二步：Green —— 最小实现

只写让测试通过的最少代码。不要预测未来需求，不要过度设计。

```python
# calculator.py
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
```

```bash
$ pytest test_calculator.py -k test_add
# 1 passed  ← 绿色！
```

### 第三步：Refactor —— 重构

测试通过后，安全地重构实现。提取重复代码、改善命名、优化结构。测试套件是你的安全网。

### 第四步：重复

添加下一个测试用例，重走红→绿→重构循环。

## 核心要点

> **"写测试 → 确认失败 → 实现 → 确认通过 → 重构"** 这十二个字是对 coding agent 最有效的约束。每个优秀的模型都能理解 "red/green TDD" 这个缩写所代表的完整流程。

这不仅是写代码的技巧，更是工程纪律。它强制你在写实现之前先定义"什么是正确的"，从而杜绝模糊需求和过度实现。
