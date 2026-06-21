---
description: 跳过设计，直接写代码（委托 YuuCoder）
---

用户输入即为需求。作为中介，你的唯一职责是将用户需求准确地传递给 YuuCoder：

1. 从用户输入中提取：task slug、目标文件范围、具体需求描述
2. 告诉 YuuCoder：当前 checkout/worktree 已由 human/dev 在本地分配；它只需要确认当前位置是干净 worktree，不要创建、切换或合并 worktree/branch，也不要推断需要远端同步
3. 委托给 YuuCoder：`task(subagent_type="YuuCoder", description="{task}", prompt="{用户的完整需求 + 文件范围 + 当前 worktree 已分配}")`
4. 不要做任何设计、分析、补充——只做传递。YuuCoder 会自行处理实现。
