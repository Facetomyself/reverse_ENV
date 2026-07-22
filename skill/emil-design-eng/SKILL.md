---
name: emil-design-eng
description: 前端设计工程编排器 — 面向非前端工程师的 UI 打磨流程。6 子技能覆盖动画审查/改进/发现/术语/哲学/Apple 设计。自动路由 + 强制审查门 + 速查表。触发：做界面/写动画/审查UI/打磨交互/前端代码审查。
---

# 前端设计工程编排器

## 定位

你不是前端工程师。你对动画缓动、弹簧物理、GPU 合成没有肌肉记忆。这在 AI 时代不是瓶颈 — **只要知道什么时候触发哪个子技能、走过什么流程**，AI 替你执行品味判断。

本 skill 是 **编排器**，不直接提供设计建议。它的职责是：
1. 识别你的前端设计需求属于哪一类
2. 路由到正确的子技能
3. 强制执行审查门（写代码后必须审查）
4. 提供速查表（非前端也能一键修复常见问题）

底层品味规则来自 **Emil Kowalski**（前 Vercel/Linear 工程师，Sonner toast 库作者，npm 周下载 1300 万+），子技能完整保留原始规则。

## 触发短语

以下任一说法自动触发本 skill：

| 你说什么 | 路由到 |
|---------|--------|
| "帮我做个界面" "写个页面" "搭个前端组件" | 写代码 → 审查门 |
| "审查/看看这个动画/交互怎么样" | `review-animations` |
| "改进/优化/审计这个项目的动画" | `improve-animations` |
| "这里能不能加点动画/动效" "加点交互反馈" | `find-animation-opportunities` |
| "这个动画效果叫什么" "怎么描述这个动效" | `animation-vocabulary` |
| "这个缓动/弹簧/手势怎么调" | `emil-design-eng`（主 skill） |
| "怎么做到 iOS 那种感觉" "Apple 风格交互" | `apple-design` |
| "打磨一下这个界面" "让这个交互更流畅" | 先审查 → 再改进 |

## 流程：用户说"帮我做界面"

这是最常见场景。非前端工程师描述需求 → AI 生成代码 → **强制走审查门**。

### 标准流程（3 步）

```
你说"做个登录页" → AI 写代码
    │
    ▼
① 自检（AI 自动，无需你参与）
   □ 有没有 transition: all？→ 改成具体属性
   □ 有没有 ease-in？→ 改成 ease-out
   □ 有没有 scale(0)？→ 改成 scale(0.95) + opacity: 0
   □ 按钮有没有 :active 反馈？→ 加 scale(0.97)
   □ 弹出层 origin 对不对？→ Radix: var(--radix-popover-content-transform-origin)
   □ 动画是否超过 300ms？→ UI 动画控制在 300ms 内
   □ 是否只动了 transform 和 opacity？→ 不动 width/height/margin/padding
   □ 是否加了 prefers-reduced-motion？→ 必须加

② 审查门（必须，自动触发 review-animations）
   如果上面有任何一条不确定 → 对生成代码执行 review-animations 审查
   审查输出：Before/After 表格 + 结论（通过/驳回）

③ 修正（如果审查不通过）
   按审查结果逐条修正 → 再审查 → 直到通过
```

### 增强流程（你说"打磨这个界面"）

在标准流程基础上增加：

```
审查(review-animations) → 发现问题 → 按优先级修正
    │
    ▼
发现机会(find-animation-opportunities) → 找可以加动效的地方
    │
    ▼
实施(improve-animations plan) → 每个发现生成可执行计划
```

## 子技能速查

| 子技能 | 一句话 | 输入 | 输出 |
|--------|--------|------|------|
| `emil-design-eng` | 动画哲学 + 组件打磨法则 | 具体问题 | 设计建议 + Before/After 表格 |
| `review-animations` | 严格审查动画代码 | 代码 diff / 文件 | 问题表 + 通过/驳回 |
| `improve-animations` | 全代码库审计 + 修复计划 | 项目目录 | 优先级表格 + plans/*.md |
| `find-animation-opportunities` | 发现值得加动效的地方 | 页面/组件 | 机会表 + 拒绝表 |
| `animation-vocabulary` | 描述 → 术语 | 模糊描述 | 精确术语 + 近义词辨析 |
| `apple-design` | Apple 交互哲学 → Web | 交互需求 | 弹簧参数 + 手势方案 + 材质 |

## 非前端工程师速查表

如果你只想快速修一个已知问题，直接查这里：

### 动效修复速查

| 问题 | 修复 | 代码 |
|------|------|------|
| 动画卡顿/掉帧 | 只动 transform 和 opacity | `transition: transform 200ms ease-out, opacity 200ms ease-out` |
| 下拉菜单感觉慢 | ease-out 替代 ease-in | `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` |
| 弹窗从奇怪的地方出来 | 对齐触发器的 origin | `transform-origin: var(--radix-popover-content-transform-origin)` |
| 按钮点了没反应 | 加 :active 反馈 | `.button:active { transform: scale(0.97) }` |
| 列表出现太突兀 | 加 stagger | 每项延迟 30-80ms，从 scale(0.95)+opacity:0 进入 |
| 元素出现像"凭空变出来" | 不从 scale(0) 开始 | 从 `scale(0.95); opacity: 0` 开始 |
| Framer Motion 动画掉帧 | 用完整 transform 字符串 | `<motion.div animate={{ transform: "translateX(100px)" }} />` |
| 忘了无障碍 | 加 reduced-motion | `@media (prefers-reduced-motion: reduce) { ... }` |
| Toast/通知动画不连贯 | 用 transition 不用 keyframes | `transition: transform 400ms ease` |
| 键盘快捷键弹窗动画拖沓 | 删掉动画 | 高频操作不加动画，学 Raycast |

### 缓动曲线预设

```css
/* 直接复制到你的 CSS 变量里 */
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* UI 进入/退出，最常用 */
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* 屏幕内移动/变形 */
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);     /* iOS 风格抽屉 */
```

### 动画时长预设

| 元素 | 时长 |
|------|------|
| 按钮按下反馈 | 100-160ms |
| Tooltip/小弹出层 | 125-200ms |
| 下拉菜单/选择器 | 150-250ms |
| Modal/抽屉 | 200-500ms |
| 规则：UI 动画不超过 300ms |

### Spring 预设

```js
// 一般 UI（无回弹，推荐默认）
{ type: "spring", duration: 0.4, bounce: 0 }

// 拖拽/动量交互（有轻微回弹）
{ type: "spring", duration: 0.4, bounce: 0.2 }
```

## 禁区（绝对不能做的事）

1. 键盘快捷键触发的动作 → **不加动画**（学 Raycast）
2. 每天操作 100+ 次的动作 → **不加动画**
3. 动画 `width`/`height`/`margin`/`padding` → **绝对禁止**
4. `transition: all` → **绝对禁止**，必须列出具体属性
5. `ease-in` 做 UI 动画 → **绝对禁止**，用 ease-out
6. `scale(0)` 做入场 → **绝对禁止**，从 scale(0.95) 开始
7. 弹出层 `transform-origin: center` → **禁止**（Modal 除外）
8. 忘记 `prefers-reduced-motion` → **禁止**

## 决策树

```
你需要什么？
├─ "做个界面/写个组件" → [标准流程] 写代码 → 自检 → 审查门 → 修正
├─ "审查/检查现有动画" → review-animations
├─ "改进/审计项目所有动画" → improve-animations
├─ "这里能不能加动效" → find-animation-opportunities
├─ "这个动效叫什么名字" → animation-vocabulary
├─ "怎么调缓动/弹簧/手势" → emil-design-eng（主 skill）
├─ "Apple 风格怎么做" → apple-design
└─ "打磨界面/让交互更流畅" → [增强流程] 审查 → 发现机会 → 实施
```

## 子技能位置

所有子技能源码在 `skill/emil-design-eng/skills/<name>/SKILL.md`。

- 主哲学：`skills/emil-design-eng/SKILL.md`
- 审查标准参考：`skills/review-animations/STANDARDS.md`
- 审计手册：`skills/improve-animations/AUDIT.md`
- 计划模板：`skills/improve-animations/PLAN-TEMPLATE.md`
