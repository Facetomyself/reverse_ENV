---
name: ruyi-reverse
description: |
  ruyi 工具链统一编排器 — Web JS 逆向唯一入口。
  7 个能力模块 × 深浅两级，按任务主动组合。
  深度内容在 references/。
---

# ruyi-reverse

## 定位

Web JS 逆向的**唯一编排入口**。不按"够不够用"线性升级，而是**按任务需求主动组合能力模块**。

```
任务需求 → 匹配能力模块 → 选择深浅等级 → 组合执行
```

每个模块有**两级深度**——从轻量开始，需要时加深——但**不等待失败**：如果任务特征匹配，直接推荐合适深度。

## 能力模块

7 个可组合模块，按任务需求选取：

| # | 模块 | 做什么 | 轻量 (L1) | 深度 (L2) |
|:---:|------|------|------|------|
| 1 | **[Anti-Detect] Anti-Detect** | 反检测浏览 | `ruyi_new_page` + proxy | + `smart_fingerprint` 22维 + `handle_cloudflare` |
| 2 | **[Observe] Observe** | 侦察页面 | `list_scripts` + `search_in_sources` | + `save_script_source` 全部落盘 |
| 3 | **[Capture] Capture** | 抓包采样 | `capture_start/wait` (被动) | + `break_on_xhr` + `intercept_*` (主动拦截) |
| 4 | **[Trace] Trace** | 指纹/API追踪 | `ruyi_trace_*` (BiDi) | + `ruyitrace` CLI (C++内核, 全11维) |
| 5 | **[Human-Sim] Human-Sim** | 人类行为模拟 | `ruyi_human_click` | + `human_move` bezier/windmouse + `human_input` 逐字 |
| 6 | **[Debug] Debug** | JS 断点调试 | `break_on_xhr` + `set_breakpoint_on_text` (软断点) | + `js-reverse_*` CDP桥接 (真断点/单步/作用域) |
| 7 | **[Export] Export** | 产出与桥接 | `export_session` → session.json | + `save_script_source` + 补环境 → `protocol-recovery` |

### 模块深度决策

**不等待失败——根据任务特征主动选择深度：**

| 任务特征 | 推荐深度 |
|----------|---------|
| 目标有 Cloudflare / hCaptcha / akamai | [Anti-Detect] L2 |
| 目标普通站点，无验证码 | [Anti-Detect] L1 |
| 搜索 "encrypt\|sign\|token\|hmac" 命中 | [Capture] L2 + [Debug] L2 |
| 搜索 "canvas\|webgl\|fingerprint" 命中 | [Trace] L2 |
| 需要完整调用栈 / 单步 / 看变量 | [Debug] L2 |
| 只需确认请求参数 | [Capture] L1 |
| 需要爬取/批量操作 | [Human-Sim] L2 |
| 只需一次性过检 | [Anti-Detect] L2 + [Human-Sim] L1 |

## 快速决策

```
任务是什么?
├─ "打开页面看看"                    → [Anti-Detect](L1-L2) + [Observe](L1)
├─ "抓 API 请求/响应"                → [Anti-Detect] + [Capture](L1) + [Export](L1)
├─ "过验证码/Cloudflare"             → [Anti-Detect](L2) + [Human-Sim](L1-L2)
├─ "分析指纹采集行为"                 → [Anti-Detect](L2) + [Observe](L1) + [Trace](L2)   ← 主动推荐深度 Trace
├─ "找到加密函数 → 复现算法"          → [Anti-Detect] + [Capture](L2) + [Debug](L2) + [Export](L2)
├─ "补环境 / 验证签名逻辑"            → [Export](L2) + [Trace](L1)               ← Trace 辅助补环境
├─ "批量爬取/自动化操作"              → [Anti-Detect](L2) + [Human-Sim](L2) + [Capture](L1)
├─ "去混淆后需要单步调试"             → [Anti-Detect](L2) + [Debug](L2) + [Export](L2)    ← CDP 桥接
└─ "不确定"                          → [Anti-Detect](L1) + [Observe](L1) → 按发现的特征升级
```

## 典型组合

### 组合 1: 协议逆向全套
`[Anti-Detect](L2) + [Observe](L1) + [Capture](L2) + [Debug](L2) + [Export](L2)`

```
ruyi_new_page(proxy, fingerprint)              ← [Anti-Detect] L2
→ search_in_sources("encrypt|sign")             ← [Observe] L1
→ break_on_xhr + capture_start                  ← [Capture] L2
→ (定位后) export_session → js-reverse CDP      ← [Debug] L2
→ save_script + 补环境                          ← [Export] L2
```

### 组合 2: 指纹取证
`[Anti-Detect](L2) + [Observe](L1) + [Trace](L2)`

```
ruyi_new_page(proxy, fingerprint)              ← [Anti-Detect] L2
→ list_scripts + search("canvas|webgl")         ← [Observe] L1
→ ruyitrace CLI (C++ 全维度)                    ← [Trace] L2 (主动推荐,不等 BiDi 失败)
→ python trace_analyzer.py trace.ndjson
```

### 组合 3: 验证码突破
`[Anti-Detect](L2) + [Human-Sim](L2)`

```
ruyi_new_page(proxy, fingerprint)              ← [Anti-Detect] L2
→ handle_cloudflare                             ← [Anti-Detect] L2
→ (如需手动) human_move + human_click           ← [Human-Sim] L2
```

### 组合 4: 轻量侦察
`[Anti-Detect](L1) + [Observe](L1) + [Capture](L1)`

```
ruyi_new_page                                  ← [Anti-Detect] L1
→ list_scripts + list_network_requests          ← [Observe] L1
→ capture_start → wait                          ← [Capture] L1
```

## 模块能力边界

每个模块深浅两级的精确边界——知道什么能做、什么不能做。

| 模块 | L1 能做到 | L1 做不到 (→ L2 解决) |
|------|----------|---------------------|
| [Anti-Detect] Anti-Detect | 代理、基础指纹 | 22维硬件指纹、CF自动过检 |
| [Observe] Observe | 列出脚本/请求、关键字搜索 | 批量保存全部脚本 |
| [Capture] Capture | 被动抓包 (batch) | 流式监听、XHR调用栈、自定义拦截逻辑 |
| [Trace] Trace | BiDi 事件追踪 (部分维度) | canvas/webgl/audio 维度、C++调用栈、页面无感知 |
| [Human-Sim] Human-Sim | 单次点击 | bezier/windmouse 轨迹、逐字输入、触摸模拟 |
| [Debug] Debug | URL XHR 断点、Error().stack | 结构化调用栈、单步、作用域变量、任意行断点 |
| [Export] Export | 导出 cookies+storage | 完整 session 桥接、补环境辅助 |

## 执行要求

- **按特征主动推荐深度**——搜索命中 "encrypt" 就直接建议 Capture L2 + Debug L2，不等失败
- **模块可任意组合**——不是线性升级，一个任务可以同时用 [Anti-Detect](L2) + [Trace](L2) + [Observe](L1)
- **`ruyi_new_page` 先调**——proxy/fingerprint 启动时配置
- **遇反检测站点不得单独用 js-reverse_***——先经 [Anti-Detect] 模块过检
- **产出三件套**——`report.md` + `findings.json` + `triage.md`
- **不假装**——L4 目标 (WASM/VM/重混淆) 标注 triage-only

## 参考文档索引

| 文档 | 何时读 |
|------|--------|
| `references/capability-modules.md` | 需要了解每模块的完整 API 映射 + 边界条件 |
| `references/workflow.md` | 五阶段工作流 × 模块组合 |
| `references/scenarios.md` | 完整场景步骤 + 坑点 + 失败处理 |
| `references/state-lifecycle.md` | session 生命周期 + 跨模块状态追踪 |
| `references/ruyipage-api.md` | [Anti-Detect]/[Human-Sim]/[Capture] 模块 L2 — Python API 参考 |
| `references/ruyitrace-cli.md` | [Trace] 模块 L2 — C++ CLI 参考 |

## 交付衔接

- [Export] Export + 补环境完成 → `protocol-recovery`
- [Debug] Debug L2 → `mcp-js-reverse-playbook`
- Native 反检测 → `native-reverse`
- `triage.md` 标注使用了哪些模块及深度
