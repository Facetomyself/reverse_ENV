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
- CF/hCaptcha → [Anti-Detect] L2 (handle_cloudflare)
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

方式 B — 主动 ([Capture] L2):
  ruyi_break_on_xhr { url: "/api/" }
  → (触发)
  → ruyi_evaluate_script (采样 headers/body)
  + ruyi_get_request_initiator (调用栈)
```

**特征驱动的深度选择：**
- Observe 命中 "encrypt" → [Capture] L2 + 准备 [Debug] L1
- 需要修改请求 → [Capture] L2 (intercept)
- 有 WebSocket → [Capture] L2 (websocket_inject)

---

### Phase 3: Rebuild

**目标：** 整理本地可迭代的复现材料。

**默认模块：[Export](L1-L2)**

```
ruyi_save_script_source { url, filePath }            ← [Observe] L2
ruyi_export_session { outputFile }                   ← [Export] L1
→ (如需 CDP 调试) 切 mcp-js-reverse-playbook         ← [Export] L2 (桥接)
→ (如需补环境) 加载 session.json + target.js          ← [Export] L2
```

---

### Phase 4: Patch

**目标：** 按 first divergence 精准补环境。

**默认模块：[Export](L2) + [Trace](L1-L2)**

```
1. Node.js 加载 session.json + target.js
2. 运行 → first divergence → 补齐 → 验证 → 迭代
3. ruyi_trace_get_results → 查哪些 DOM API 被实际调用  ← [Trace] L1
4. (如需全量 API 列表) ruyitrace CLI → NDJSON          ← [Trace] L2
```

**特征驱动的深度选择：**
- Capture 阶段发现大量 DOM API 调用 → [Trace] L2
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
| WASM/VM 分析 | 标注 L4 triage-only（不假装能完整还原） |

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

每个模块的产出供下游模块消费。`workspace/<project>/ruyi-session.json` 追踪模块执行状态和产出物路径。

> 状态管理详见 `references/state-lifecycle.md`
