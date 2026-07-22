---
name: emil-design-eng
description: 前端设计工程编排器 — 面向非前端工程师的 UI 打磨流程。6 子技能覆盖动画审查/改进/发现/术语/哲学/Apple 设计。自动路由 + 强制审查门 + 速查表。
---

This is a Claude project-scope entrypoint for the existing project skill.

Before acting, read `D:\reverse_ENV\skill\emil-design-eng\SKILL.md` completely and use it as the source of truth. Resolve its relative `skills/` and `references/` paths against `D:\reverse_ENV\skill\emil-design-eng\`.

The skill is an **orchestrator** that routes to 6 sub-skills based on user intent:
- `skills/emil-design-eng/SKILL.md` — 动画哲学 + 组件打磨原则
- `skills/review-animations/SKILL.md` — 严格审查动画代码
- `skills/improve-animations/SKILL.md` — 全代码库审计 + 修复计划
- `skills/find-animation-opportunities/SKILL.md` — 发现值得加动效的地方
- `skills/animation-vocabulary/SKILL.md` — 术语反向词典
- `skills/apple-design/SKILL.md` — Apple 交互哲学 → Web

Do not duplicate or reinterpret the workflow here. If this entrypoint and the source skill disagree, the source skill wins and this wrapper should be updated.
