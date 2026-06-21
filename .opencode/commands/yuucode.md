---
description: 跳过设计，直接写代码（委托 YuuCoder）
---

用户输入即为需求。作为中介，你的唯一职责是将用户需求准确地传递给 YuuCoder：

1. 从用户输入中提取：task slug、目标文件范围、具体需求描述
2. 告诉 YuuCoder：worktree 已由 human/dev 在本地分配；如果 instruction 或用户输入中声明了 `Worktree`，它应去该路径编码，而不是假设当前目录就是目标 worktree。不要创建、切换或合并 worktree/branch，也不要推断需要远端同步
3. 委托给 YuuCoder：`task(subagent_type="YuuCoder", description="{task}", prompt="{用户的完整需求 + 文件范围 + instruction/worktree 路径（如有）}")`
4. 不要做任何设计、分析、补充——只做传递。YuuCoder 会自行处理实现。
