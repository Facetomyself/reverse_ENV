# ruyi-mcp DevTools 调试能力分析

## 核心问题

**ruyipage (Firefox 151.0a1 / BiDi) 能否实现 Chrome DevTools 等级的 JS 运行时调试？**
（断点设置、单步执行、调用栈查看、作用域变量检查、暂停/恢复）

## 结论

**不能实现 CDP 等级的完整调试，但可以实现 70-80% 覆盖的增强软断点方案。** 根因不是 ruyipage 的限制，而是 WebDriver BiDi 协议本身的规范缺口 + Firefox CDP 已被移除。

---

## 1. 三层协议能力矩阵

| 调试能力 | CDP (Chrome) | BiDi (W3C Spec) | BiDi (Firefox 实现) | Marionette (Firefox) |
|---------|:---:|:---:|:---:|:---:|
| **断点设置** (`setBreakpoint`) | ✅ | ❌ 规范无此域 | ❌ | ❌ |
| **URL 断点** (`setBreakpointByUrl`) | ✅ | ❌ | ❌ | ❌ |
| **单步跳过** (`stepOver`) | ✅ | ❌ | ❌ | ❌ |
| **单步进入** (`stepInto`) | ✅ | ❌ | ❌ | ❌ |
| **单步跳出** (`stepOut`) | ✅ | ❌ | ❌ | ❌ |
| **暂停/恢复** (`pause`/`resume`) | ✅ | ❌ | ❌ | ❌ |
| **暂停时求值** (`evaluateOnCallFrame`) | ✅ | ❌ | ❌ | ❌ |
| **调用栈** (`getCallStack`) | ✅ | ❌ | ❌ | ❌ |
| **作用域变量** (`getProperties`) | ✅ | ❌ | ❌ | ❌ |
| **异常断点** (`setPauseOnExceptions`) | ✅ | ❌ | ❌ | ❌ |
| **脚本源码** (`getScriptSource`) | ✅ | ❌ | ❌ | ❌ |
| **JS 求值** (`evaluate`/`callFunction`) | ✅ | ✅ `script.evaluate` | ✅ | ✅ |
| **预加载脚本** (`addPreloadScript`) | ✅ | ✅ `script.addPreloadScript` | ✅ | ✅ |
| **预加载脚本移除** (`removePreloadScript`) | ✅ | ✅ | ✅ | ✅ |
| **网络拦截** (`network.addIntercept`) | ✅ | ✅ | ✅ | ✅ |
| **控制台日志** (`log.entryAdded`) | ✅ | ✅ `log.entryAdded` | ✅ | ✅ |

---

## 2. WebDriver BiDi 规范的现状

从 [W3C WebDriver BiDi 规范](https://w3c.github.io/webdriver-bidi/)（2025-01-08 草案）来看：

### BiDi 现有的 10 个模块

| 模块 | 含调试能力？ |
|------|:---:|
| `session` — 会话管理 | ❌ |
| `browser` — 浏览器级操作 | ❌ |
| `browsingContext` — 页面上下文 | ❌ |
| `emulation` — 模拟（地理/时区/UA/视口） | ❌ |
| `network` — 网络拦截/请求修改 | ❌ |
| **`script`** — 脚本执行 | ⚠️ **求值+预加载，无断点** |
| `storage` — Cookie 管理 | ❌ |
| `log` — 日志事件 | ❌ |
| `input` — 输入操作 | ❌ |
| `webExtension` — 扩展管理 | ❌ |

### `script` 模块详细内容

**命令（6 个）：**
- `script.addPreloadScript` — 注入预加载脚本（每次导航前执行）
- `script.removePreloadScript` — 移除预加载脚本
- `script.evaluate` — 执行 JS 表达式
- `script.callFunction` — 调用 JS 函数
- `script.disown` — 释放句柄
- `script.getRealms` — 获取执行上下文列表

**事件（3 个）：**
- `script.realmCreated` — 执行上下文创建
- `script.realmDestroyed` — 执行上下文销毁
- `script.message` — 脚本消息（`sendMessage` 回调通道）

**全规范中不存在 "breakpoint"、"debugger"、"pause"、"step" 等词汇。**

BiDi 规范目前明确**不包含调试域**。调试相关提案在 W3C WebDriver WG 中有讨论但未进入草案阶段，时间线不可预期（可能是年为单位）。

---

## 3. Firefox CDP — 已彻底移除

Firefox 曾有一个**实验性 CDP 实现**（`remote.active-protocols=2`），支持 `Debugger` 域的大部分命令：

- `Debugger.setBreakpoint` / `Debugger.setBreakpointByUrl`
- `Debugger.stepOver` / `Debugger.stepInto` / `Debugger.stepOut`
- `Debugger.pause` / `Debugger.resume`
- `Debugger.evaluateOnCallFrame`
- `Debugger.getScriptSource`
- `Runtime.getProperties`

**但已被移除：**

| 里程碑 | Firefox 版本 | CDP 状态 |
|--------|:---:|------|
| 2024-05 宣布弃用 | — | Deprecation announced |
| 2024-07 | Firefox 129 | CDP disabled by default (`remote.active-protocols`=1) |
| 2024-11 | Firefox Nightly 141 | **CDP 代码从源码树完全删除** |
| 2025 中期 | Firefox ESR 128 EOL | 最后的 CDP 余留版本终止 |

**ruyipage 使用 Firefox 151.0a1 → 远在 CDP 删除之后。CDP 在 ruyipage 的 Firefox 中不存在。**

唯一可能性：降级到 Firefox ESR 128 作为浏览器引擎 → 失去 ruyipage 的 22 维指纹 + 定制反检测补丁，不可行。

---

## 4. 可实现的增强方案：三级软断点

虽然 CDP 调试不可能，但可以通过 `script.addPreloadScript` + Proxy 包装实现**三级增强软断点**，覆盖大部分 RE 需求。

### 4.1 当前已实现 (Level 1)

```
ruyi_set_breakpoint_on_text / ruyi_break_on_xhr
  → script.addPreloadScript
    → 注入 XHR/Fetch Proxy 包装
    → 匹配 URL 时插入 debugger; 语句
```

**能力：** URL 匹配时暂停（`debugger;` 触发 BiDi 暂停）
**缺陷：** 无调用栈、无作用域、无法单步、无法条件断点

### 4.2 短期可实现 (Level 2) — 无需协议支持

利用 `Error().stack` + Promise 通信通道：

```
script.addPreloadScript(() => {
  // 1. 建立 MCP<->页面通信通道
  const channel = new BroadcastChannel('__ruyi_debug__');
  let pauseResolve = null;

  // 2. 监听 MCP 命令
  channel.onmessage = (e) => {
    if (e.data === 'resume') pauseResolve?.();
  };

  // 3. 包装目标函数
  const _orig = window.targetFunction;
  window.targetFunction = async function(...args) {
    // 捕获调用栈
    const stack = new Error().stack;

    // 通知 MCP：函数被调用
    channel.postMessage({
      type: 'breakpoint',
      name: 'targetFunction',
      args: JSON.parse(JSON.stringify(args)),
      stack: stack,
      timestamp: Date.now()
    });

    // 暂停等待 MCP 命令
    await new Promise(r => { pauseResolve = r; });

    // 执行原函数
    return _orig.apply(this, args);
  };
});
```

**可新增能力：**

| 能力 | 实现方式 | 可靠性 |
|------|---------|:---:|
| **调用栈字符串** | `new Error().stack` | ✅ 高 |
| **入参捕获** | `JSON.stringify(args)` | ✅ 高 |
| **返回值捕获** | 在 `return` 后 `postMessage` | ✅ 高 |
| **条件断点** | `if (condition) { await pause; }` | ✅ 高 |
| **MCP 远程控制暂停/恢复** | `BroadcastChannel` + Promise | ✅ 高 |
| **函数级"单步"** | 递归包装所有被调用函数 | ⚠️ 中（需预先知道调用图） |
| **console 拦截** | 包装 `console.log/warn/error` | ✅ 高 |
| **DOM 事件断点** | `addEventListener` + `postMessage` | ✅ 高 |

**仍无法实现：**

| 能力 | 原因 |
|------|------|
| 源码任意行断点 | 无 VM 级断点支持 |
| 逐行单步 | 无 VM 级执行控制 |
| 作用域变量枚举 | 无 `scope.getProperties` API |
| 异常断点（全局） | 无 `setPauseOnExceptions` |
| WASM 内断点 | 完全超出 BiDi 能力范围 |
| Blackbox 脚本 | 无脚本忽略机制 |

### 4.3 长期可探索 (Level 3) — 需 Firefox 定制

ruyipage 已经是定制版 Firefox（22 维指纹补丁 + BiDi 增强），理论上可以在**定制版内核**中加入调试能力：

**方案 A：在内核中嵌入调试 WebSocket**
- 在 Firefox 151 定制版中保留/恢复 CDP `Debugger` 域
- 通过独立的 WebSocket 端口暴露（类似 Chrome `--remote-debugging-port`）
- ruyi-mcp 同时连接 BiDi（自动化）和 CDP（调试）
- 实现难度：🔴 高（需修改 Firefox 源码 C++/JS 层）

**方案 B：扩展 BiDi 定制命令**
- 在 ruyipage Firefox 的 BiDi 实现中加入非标准扩展命令
- `ruyi.debugger.setBreakpoint`、`ruyi.debugger.stepOver` 等
- 底层复用 Firefox 的 SpiderMonkey 调试 API（`Debugger` 对象，这是 SpiderMonkey 的 JS 级调试 API，不是 CDP）
- 实现难度：🟡 中（SpiderMonkey `Debugger` API 已存在，只需 BiDi 桥接）

**方案 C：SpiderMonkey Debugger API 桥接**
- Firefox 的 JS 引擎 SpiderMonkey 有内置的 [`Debugger` API](https://firefox-source-docs.mozilla.org/js/Debugger.html)
- 这个 API 可以设置断点、单步执行、查看调用栈、枚举作用域——功能上等价于 CDP Debugger 域
- 但它暴露给**浏览器内部 chrome 代码**（`chrome://` 特权上下文），不是 WebDriver 协议
- 如果 ruyipage Firefox 能暴露一个特权 JS 上下文 via BiDi，理论上可以从一个 chrome-privileged 脚本中使用 SpiderMonkey `Debugger` API
- 实现难度：🟡 中（需要 ruyipage 内核配合 + BiDi 特权上下文）

---

## 5. 实战建议：分三阶段推进

### Phase A 立即可做（Level 2 软断点增强）

在 ruyi-mcp 中实现：

```
ruyi_set_breakpoint({
  target: "window.encrypt",       // 目标函数路径
  captureArgs: true,               // 捕获入参
  captureReturn: true,             // 捕获返回值
  captureStack: true,              // 捕获 new Error().stack
  condition: "args[0] > 100",     // 条件断点
  pauseOnHit: true                 // 是否暂停等待 resume
})

ruyi_resume_breakpoint({ breakpointId: "bp_1" })
ruyi_get_breakpoint_hits({ breakpointId: "bp_1" })
```

**这个方案无需 ruyipage 内核改动，纯粹在 MCP + BiDi 协议层实现。**

### Phase B 需要 ruyipage 定制（SpiderMonkey Debugger 桥接）

与 ruyipage 开发者协调，在内核中加入：
1. 一个 `chrome://` 特权 JS 上下文暴露给 BiDi
2. 在此上下文中加载 SpiderMonkey `Debugger` API 桥接脚本
3. MCP 通过 BiDi 向特权上下文发命令

这可以实现**接近 CDP 的完整调试能力**。

### Phase C 长期（BiDi 规范演进）

跟踪 [W3C WebDriver BiDi](https://github.com/w3c/webdriver-bidi) 仓库的 debugger 提案进展。一旦规范定稿，Chrome 和 Firefox 都会实现。

---

## 6. 能力对比总表

| 调试能力 | js-reverse-mcp (Chrome/CDP) | ruyi-mcp 当前 (BiDi) | ruyi-mcp Phase A (软断点增强) | ruyi-mcp Phase B (SM Debugger) |
|---------|:---:|:---:|:---:|:---:|
| URL XHR 断点 | ✅ | ✅ | ✅ | ✅ |
| 函数级断点 | ✅ | ❌ | ✅ Proxy 包装 | ✅ |
| 条件断点 | ✅ | ❌ | ✅ | ✅ |
| 调用栈（结构化） | ✅ `getCallStack` | ❌ | ⚠️ `Error().stack` 字符串 | ✅ |
| 入参捕获 | ✅ | ❌ | ✅ JSON | ✅ |
| 返回值捕获 | ✅ | ❌ | ✅ JSON | ✅ |
| 单步跳过 | ✅ | ❌ | ❌ | ✅ |
| 单步进入 | ✅ | ❌ | ❌ | ✅ |
| 单步跳出 | ✅ | ❌ | ❌ | ✅ |
| 作用域变量 | ✅ `getProperties` | ❌ | ❌ | ✅ |
| 源码任意行断点 | ✅ | ❌ | ❌ | ✅ |
| 异常断点 | ✅ | ❌ | ❌ | ✅ |
| WASM 断点 | ✅ | ❌ | ❌ | ❌ |
| 反检测浏览 | ❌ 基础 `--cloak` | ✅ 22 维指纹 | ✅ | ✅ |
| 人类行为模拟 | ❌ | ✅ | ✅ | ✅ |
| DOM 指纹追踪 | ❌ | ✅ | ✅ | ✅ |
| 代理池 | ❌ | ✅ | ✅ | ✅ |
| Session 桥接 | ❌ | ✅ | ✅ | ✅ |

---

## 7. 当前最佳实践

**鉴于 CDP 调试在 ruyipage Firefox 中不可用（协议限制 + CDP 已移除），推荐策略：**

1. **能用 js-reverse-mcp 调试就用它** — Chrome CDP 有完整调试能力
2. **需要反检测/指纹/trace 时用 ruyi-mcp** — 立即实施 Phase A 软断点增强
3. **两者跨工具桥接** — `ruyi_export_session` → js-reverse-mcp 继续 CDP 调试
4. **Phase B (SpiderMonkey Debugger) 作为中期目标** — 一旦实现，ruyi-mcp 将成为真正的全能方案

### 一句话总结

> **BiDi 协议本身不具备调试域，Firefox CDP 已被移除。在 ruyipage Firefox 中实现 CDP 级 DevTools 调试的唯一可行路径是：利用 SpiderMonkey 内置 `Debugger` API，通过 ruyipage 定制内核暴露给 BiDi 特权上下文。在此之前，Level 2 软断点（Proxy 包装 + Error.stack + MCP 通信）可覆盖约 70% 的 RE 调试需求。**
