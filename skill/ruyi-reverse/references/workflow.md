# 五阶段工作流 + 模块组合

> 入口和模块选择见 `ruyi-reverse/SKILL.md`。本文档将五阶段工作流与能力模块交叉映射。

## 阶段 → 模块映射

每个阶段默认参与的模块，以及可选深度的模块：

| 阶段 | 目标 | 必选模块 | 可选加深 |
|------|------|---------|---------|
| **Observe** | 打开页面，确认请求和脚本 | [Anti-Detect] + [Observe] | [Anti-Detect] 遇 CF → L2 |
| **Capture** | 运行时采样 | [Capture] | [Debug] 需断点 → L1/L2; [Capture] 需拦截 → L2 |
| **Rebuild** | 整理复现材料 | [Export] | [Observe] 需批量落盘 → L2; [Export] 需桥接 → L2 |
| **Patch** | 补环境 | [Export] + [Trace] | [Trace] 需全API列表 → L2 |
| **DeepDive** | 去混淆/指纹取证/深度调试 | [Trace] 或 [Debug] | [Trace] 需C++ trace → L2; [Debug] 需CDP → L2 |

## 阶段详解

### Phase 1: Observe

**目标：** 打开页面，确认请求和脚本。不深挖。

**默认模块：[Anti-Detect](L1-L2) + [Observe](L1)**

```
ruyi_new_page { url, proxy?, fingerprint? }         ← [Anti-Detect]
→ ruyi_list_network_requests                         ← [Observe] L1
→ ruyi_list_scripts                                  ← [Observe] L1
→ ruyi_search_in_sources { query: "关键字" }          ← [Observe] L1
```

**特征驱动的深度选择：**
- Cloudflare Turnstile / 5s 盾 → [Anti-Detect] L2 (`ruyi_handle_cloudflare`)
- hCaptcha / reCAPTCHA / Akamai → [Anti-Detect] L2 + [Human-Sim]，标注人工/外部能力边界
- 搜索命中 "encrypt\|sign" → 标记：后续需 [Capture] L2 + [Debug] L2
- 搜索命中 "fingerprint\|canvas\|webgl" → 标记：后续需 [Trace] L2
- 脚本数量 > 20 → 考虑 [Observe] L2 批量落盘

**不要做：** 一上来全量保存脚本、设断点、深度代码分析

---

### Phase 2: Capture

**目标：** 对目标请求/函数做运行时采样。

**默认模块：[Capture](L1) ；按 Observe 特征加深**

```
方式 A — 被动 ([Capture] L1):
  ruyi_capture_start { pattern: "/api/" }
  → (触发操作)
  → ruyi_capture_wait

方式 B — 拦截观察 ([Capture] L2):
  ruyi_break_on_xhr { url: "/api/" }
  → (触发)
  → ruyi_evaluate_script (采样 headers/body)
  + ruyi_intercept_wait { timeout: 10 } (消费拦截队列)
  + ruyi_evaluate_script { function: "() => ({ stack: new Error().stack })" } (调用栈字符串)
```

**特征驱动的深度选择：**
- Observe 命中 "encrypt" → [Capture] L2 + 准备 [Debug] L1
- 需要观察命中的请求/响应 → [Capture] L2 (`ruyi_intercept_wait`)
- 需要修改请求/响应 → ruyipage Python 回退，不在当前 MCP 能力中承诺
- 有 WebSocket → [Capture] L2 (websocket_inject)

---

### Phase 3: Rebuild

**目标：** 整理本地可迭代的复现材料。

**默认模块：[Export](L1-L2)**

```
ruyi_save_script_source { url, filePath: "D:\reverse_ENV\workspace\<project>\target.js" }   ← [Observe] L2
ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }       ← [Export] L1
→ (如需 CDP 调试且通过 gate) 切 js-reverse-mcp       ← [Export] L2 (桥接)
→ (如需补环境) 加载 session.json + target.js          ← [Export] L2
```

---

### Phase 4: Patch

**目标：** 按 first divergence 精准补环境。

**默认模块：[Export](L2) + [Trace](L1-L2)**

```
1. Node.js 加载 session.json + target.js
2. 运行 → first divergence → 补齐 → 验证 → 迭代
3. Trace L1 前置: `ruyi_new_page { traceEnabled:true }`；已打开页面需 `ruyi_browser_quit` 后重开
4. ruyi_trace_get_results → 查 BiDi 协议事件，作为补环境有限辅助  ← [Trace] L1
5. (如需全量 API 列表) ruyitrace CLI → NDJSON          ← [Trace] L2
```

**特征驱动的深度选择：**
- Capture 阶段发现大量指纹/环境 API 调用 → [Trace] L2
- 补环境循环超过 5 轮 → [Trace] L2 获取全量 API 列表一次性补齐

---

### Phase 5: DeepDive

**目标：** 去混淆、控制流还原、指纹取证。

**根据任务特征选模块：**

| DeepDive 子类型 | 模块组合 |
|----------------|---------|
| 指纹取证 | [Trace](L2) C++ trace → `trace_analyzer.py` |
| 去混淆 + 验证 | [Debug](L2) CDP 断点 → 单步验证去混淆结果 |
| 控制流还原 | [Debug](L1) 软断点采样 → 追踪执行路径 |
| AST/JSVMP/WASM 分析 | [Capture]/[Trace]/[Export] 固化证据后切 `web-deobfuscation`；门禁不通过才标 L4 triage-only |

---

## 模块间数据流

```
[Anti-Detect] (session)
  ↓
[Observe] (scripts, api_endpoints)
  ↓
[Capture] (captured_requests, breakpoint_samples)
  ↓
[Export] (saved_scripts, session.json)
  ↓
[Trace] (trace_results) → 指导 [Export] (补环境)
  ↓
[Debug] (debug_samples) → 验证 [Export] (补环境正确性)
```

每个模块的产出供下游模块消费。`"D:\reverse_ENV\workspace\<project>\ruyi-session.json"` 追踪模块执行状态和产出物路径。

## 交付落点

三件套必须落在项目 workspace：`"D:\reverse_ENV\workspace\<project>\report.md"`、`"D:\reverse_ENV\workspace\<project>\findings.json"`、`"D:\reverse_ENV\workspace\<project>\triage.md"`。`findings.json` 每条记录必须带 `evidence`、`source`、`request_id`、`redaction`；`report.md` 禁止明文 token/cookie；WASM/VM 目标须记录 `web-deobfuscation` profile，缺 opcode/boundary Trace、fixture 或稳定语义时在 `triage.md` 标注 L4/triage-only。

> 状态管理详见 `references/state-lifecycle.md`
