# 能力模块详解

> 精简版 + 组合示例见 `ruyi-reverse/SKILL.md`。本文档包含每模块的完整 API 映射、L1/L2 边界、升级触发条件。

## 模块 1: [Anti-Detect] Anti-Detect — 反检测浏览

**职责：** 用指纹浏览器打开目标页面，不被反爬/反自动化检测。

### L1: 基础反检测

```
ruyi_new_page { url, proxy? }
```

**API:** `ruyi_new_page`, `ruyi_navigate_page`

**能做到：** 代理访问、基础指纹差异化
**做不到：** 22维硬件指纹匹配、Cloudflare 自动辅助、hCaptcha/reCAPTCHA/Akamai 自动破解、地理/时区/语言一致性

### L2: 完整反检测

```
ruyi_new_page { url, proxy, fingerprint: { requireCountry: "US" } }
→ ruyi_handle_cloudflare { timeout: 15 }
→ ruyi_set_fingerprint { geolocation, timezone, locale, userAgent, viewport? | windowSize? }
```

**API:** 上述 + `ruyi_handle_cloudflare`, `ruyi_set_fingerprint`

**能做到：** 22维硬件指纹、代理出口 IP 地理匹配、Cloudflare Turnstile / 5s 盾自动辅助、组合仿真、outer/viewport/screen/DPR 同步
**做不到：** hCaptcha/reCAPTCHA/Akamai 自动破解、验证码图片识别（需人工或外部识别能力）

### 升级到 L2 的触发

| 特征 | 动作 |
|------|------|
| 目标域名已知使用 Cloudflare Turnstile / 5s 盾 | 直接 L2 + `ruyi_handle_cloudflare` |
| 目标域名已知使用 hCaptcha / reCAPTCHA / Akamai | 直接 L2 + [Human-Sim]，标注人工/外部能力边界 |
| `ruyi_new_page` 后页面显示 challenge | 升级 L2，并先识别 challenge 类型 |
| console 有 "bot"/"automation" 检测日志 | 升级 L2 + fingerprint |
| 需要多标签独立代理 | → `references/ruyipage-api.md` L3 |

### Python 回退 (T2)

```python
from ruyipage import FirefoxOptions, FirefoxPage
opts = FirefoxOptions()
opts.set_proxy("http://127.0.0.1:7890")
ctx = opts.smart_fingerprint(proxy_host=..., proxy_port=..., require_country="US")
page = FirefoxPage(opts)
ctx.apply_emulation(page)  # geo+tz+locale+viewport+UA 一步
```

> 完整 API 见 `references/ruyipage-api.md`

---

## 模块 2: [Observe] Observe — 侦察页面

**职责：** 列出脚本、搜索关键字、定位目标代码。

### L1: 快速侦察

```
ruyi_list_scripts { filter? }
→ ruyi_list_network_requests { urlFilter? }
→ ruyi_search_in_sources { query: "关键字" }
→ ruyi_get_script_source { url, startLine, endLine }  (小范围)
```

**能做到：** 脚本列表、请求列表、关键字搜索、小范围源码查看
**做不到：** 批量保存全部脚本、大文件全文获取

### L2: 深度侦察

```
ruyi_save_script_source { url, filePath: "D:\reverse_ENV\workspace\<project>\target.js" }  (全部目标脚本)
+ ruyi_search_in_sources { query, isRegex: true }  (正则)
+ ruyi_list_frames → ruyi_select_frame { contextId }  (iframe 内侦察)
```

**能做到：** 批量落盘、正则搜索、iframe 内侦察
**做不到：** CDP 级 script source map 解析；`ruyi_select_frame` 只是把后续操作绑定到指定 context，切回主 frame 需重新选择主 frame 的 `contextId` 或回到 page 级 API

### 升级到 L2 的触发

| 特征 | 动作 |
|------|------|
| 需要离线分析脚本 | 批量 save_script_source |
| 关键字搜索需要正则 | search_in_sources(isRegex) |
| 页面含 iframe | `ruyi_list_frames` + `ruyi_select_frame { contextId }` |

---

## 模块 3: [Capture] Capture — 抓包采样

**职责：** 捕获 HTTP 请求/响应、WebSocket 消息、定位 API 端点。

### L1: 被动抓包

```
ruyi_capture_start { pattern: "/api/", method? }
→ (触发操作: dom_click / navigate)
→ ruyi_capture_wait { timeout, count }
```

**能做到：** 按 URL 模式捕获请求/响应 (headers + body)
**做不到：** 流式实时推送、JS 调用栈定位、自定义拦截/修改

### L2: 拦截观察与队列消费

```
ruyi_break_on_xhr { url: "/api/" }            ← XHR 断点
+ ruyi_intercept_wait { timeout, pageIdx? }     ← 消费拦截队列中的请求/响应
+ ruyi_evaluate_script { function: "() => ({ stack: new Error().stack })" }  ← 调用栈字符串采样
+ ruyi_websocket_inject → ruyi_get_websocket_messages
```

**能做到：** XHR 断点采样、拦截队列观察/消费、WebSocket 消息捕获、调用栈字符串采样
**做不到：** 当前 MCP 文档不承诺请求/响应改写；需要结构化调用栈转 Debug L2，需要自定义改写逻辑转 ruyipage Python 回退

### 升级到 L2 的触发

| 特征 | 动作 |
|------|------|
| 需要观察拦截命中的请求/响应 | `ruyi_intercept_wait` |
| 需要捕获 WebSocket | websocket_inject |
| 需要确认哪个 JS 发起的请求 | `ruyi_evaluate_script` 采样 `Error().stack` 或业务 wrapper |
| 需要自定义拦截逻辑 (Python 闭包) | → `references/ruyipage-api.md` L3 |

---

## 模块 4: [Trace] Trace — 指纹/API 追踪

**职责：** 用 BiDi 协议事件做有限辅助追踪；需要完整 DOM/Canvas/WebGL/Audio 等 API 追踪时转 C++ trace。

### L1: BiDi Trace

```
ruyi_new_page { url, traceEnabled: true }
→ (如果页面已打开: ruyi_browser_quit 后重开，不能在旧页补完整 trace)
→ ruyi_trace_start { outputFile?: "D:\reverse_ENV\workspace\<project>\trace-bidi.ndjson" }
→ (触发操作)
→ ruyi_trace_stop
→ ruyi_trace_get_results { limit }
```

**能做到：** BiDi 协议事件记录、有限辅助定位导航/网络/运行时事件
**做不到：** 完整 DOM API 追踪、canvas/webgl/audio 维度、C++ 级调用栈、页面无感知隐身

### L2: C++ 内核 Trace

```
ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\trace-session.json" }
→ ruyitrace CLI (独立 Firefox 进程)
→ "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson"
```

**API:** `"D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1"`, `"D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py"`

**能做到：** 全 11 维 (canvas/webgl/audio/webrtc/navigator/screen/crypto/storage/font/time/webgpu)、C++ 调用栈、页面完全无感知
**做不到：** 与 ruyipage 同进程并发（需独立 Firefox）

### 什么时候用 L2（主动推荐，不等 BiDi 失败）

| 任务特征 | 直接用 L2 的理由 |
|----------|----------------|
| 目标明确做指纹采集 (搜索命中 "fingerprint") | BiDi 大概率缺维度，直接用 C++ |
| 需要 canvas/webgl/audio 维度 | BiDi 不覆盖这些 API |
| 需要完整 C++ 调用栈 | BiDi 只有 JS 级 |
| 需要离线 NDJSON 深度分析 | BiDi 输出为结构化 JSON，NDJSON 更灵活 |

> 完整 CLI 参考见 `references/ruyitrace-cli.md`

---

## 模块 5: [Human-Sim] Human-Sim — 人类行为模拟

**职责：** 模拟人类鼠标/键盘操作，过行为检测。

### L1: 基础模拟

```
ruyi_human_click { target }
```

**能做到：** 人类化点击（含基础轨迹）
**做不到：** 自定义轨迹算法、逐字输入、触摸

### L2: 深度模拟

```
ruyi_human_move { target, algorithm: "bezier"|"windmouse", style: "arc"|"linear" }
→ ruyi_human_click { target, algorithm: "windmouse" }
→ ruyi_human_drag { source, target, algorithm: "windmouse", holdMs: 120, releaseMs: 80 }
→ ruyi_human_input { target, text, delayMs }
```

**能做到：** bezier/windmouse 轨迹、单次 BiDi action 原子拖拽、逐字输入、触摸模拟、轨迹可视化调试
**做不到：** 验证码图片识别

### 升级到 L2 的触发

| 特征 | 动作 |
|------|------|
| 目标有行为检测 (鼠标轨迹分析) | windmouse + 随机延迟 |
| 需要输入长文本不被检测 | human_input 逐字 |
| 需要滑块/排序/drag-and-drop | `ruyi_human_drag`，优先 selector，必要时 viewport 坐标 |
| 需要触摸事件 | → `references/ruyipage-api.md` L4 |
| CF checkbox 需要自然轨迹 | human_move + human_click |

---

## 模块 6: [Debug] Debug — JS 断点调试

**职责：** 在 JS 执行中设断点、采样参数、追踪调用栈。

### L1: 软断点 (MCP)

```
ruyi_break_on_xhr { url }                         ← URL XHR 断点
+ ruyi_set_breakpoint_on_text { text }             ← 代码文本匹配软断点
+ ruyi_evaluate_script { function: "() => ({ stack: new Error().stack })" }  ← 调用栈字符串采样
```

**能做到：** URL/函数名匹配断点、`Error().stack` 调用栈字符串、入参/返回值 JSON 采样
**做不到：** 结构化调用栈 (call frames)、单步执行、作用域变量、任意行断点、异常断点

### L2: CDP 真断点 (桥接 js-reverse-mcp)

```
ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }
→ 仅在无强反检测、session 可迁移、Chrome 行为差异可接受时切 js-reverse-mcp
→ js-reverse_set_breakpoint_on_text
→ js-reverse_get_paused_info { includeScopes: true }   ← 结构化调用栈 + 作用域
→ js-reverse_step { direction: "into"|"over"|"out" }   ← 单步
→ js-reverse_evaluate_script                           ← 在暂停帧求值
```

**能做到：** 结构化调用栈、单步执行、作用域变量枚举、任意行断点、异常断点
**做不到：** 指纹伪装（Chrome 无反检测）；遇强反检测、行为一致性要求高或 Cloudflare 过检态不可迁移时不要桥接

### 什么时候用 L2（主动推荐）

| 任务特征 | 直接用 L2 的理由 |
|----------|----------------|
| 需要理解加密函数的内部逻辑 | L1 软断点看不到中间变量 |
| 搜索命中 "decrypt\|encrypt\|cipher" + 代码混淆 | 软断点的 Error().stack 在混淆代码中不可读 |
| 需要追踪多层调用链 | 单步 + 结构化调用栈是必须的 |
| 需要在任意行设断点 | L1 只能 URL/函数名匹配 |

---

## 模块 7: [Export] Export — 产出与桥接

**职责：** 导出 session、保存脚本、桥接其他工具。

### L1: 基础导出

```
ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json", include: ["cookies","localStorage"] }
```

**能做到：** 导出 cookies + storage → JSON 文件
**做不到：** 脚本落盘、补环境辅助、跨工具注入

### L2: 完整产出

```
ruyi_save_script_source { url, filePath: "D:\reverse_ENV\workspace\<project>\target.js" }  ← 脚本落盘
+ ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }    ← session 导出
+ (切 protocol-recovery)                              ← 补环境 → Python 采集器
+ (切 js-reverse-mcp，需通过反检测/行为一致性 gate)       ← CDP 调试
+ ruyi_trace_get_results → 补环境 API 列表            ← Trace 辅助补环境
```

**能做到：** 完整本地复现材料、跨工具 session 迁移、trace 指导补环境
**做不到：** 自动补环境（需手动按 first divergence 迭代）

---

## 模块组合矩阵

| 任务类型 | [Anti-Detect] | [Observe] | [Capture] | [Trace] | [Human-Sim] | [Debug] | [Export] |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 轻量侦察 | L1 | L1 | — | — | — | — | — |
| 过验证码 | L2 | — | — | — | L2 | — | L1 |
| 协议逆向 | L2 | L1 | L2 | L1 | — | L2 | L2 |
| 指纹取证 | L2 | L1 | — | **L2** | — | — | L1 |
| 补环境 | — | — | — | L1 | — | — | L2 |
| 批量爬取 | L2 | — | L1 | — | L2 | — | L1 |
| 深度调试 | L2 | L1 | L2 | — | — | **L2** | L2 |

> **L2** = 主动推荐深度，不等待浅层失败
