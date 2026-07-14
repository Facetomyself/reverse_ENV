# Web 逆向工具链架构分析与统合方案

## 核心结论

**当前架构状态：已进入“双 MCP 并行”阶段。** `ruyi-mcp` 已作为 Firefox/BiDi 全链路 MCP 接入并暴露 **56 tools**；`js-reverse-mcp` 保留 Chrome/CDP 的完整断点、单步、作用域优势。二者不是替代关系，而是按能力边界互补。

**执行路由：Web JS 默认走 `ruyi-reverse` / `ruyi-mcp`。** 只有明确需要 CDP 级暂停、单步、作用域枚举，且目标无强反检测需求时，才切 `mcp-js-reverse-playbook` / `js-reverse-mcp`；强反检测、指纹取证、BiDi Trace / DOMTrace、人类行为模拟一律优先 ruyi 工具链。

> 本文早期章节保留了 ruyi-mcp 43-tool 设计草案，用作演进背景和能力对照；实际执行口径以本节、`AGENTS.md`、`CLAUDE.md`、`docs/MCP服务详情.md` 为准。

---

## 0.1 Web 补环境工程层

当前 Web 逆向链路新增 `web-env-patcher` 作为浏览器取证与协议恢复之间的工程化补环境层：

```text
ruyi-reverse / js-reverse-mcp
  -> web-env-patcher
  -> protocol-recovery
```

职责边界：

- `ruyi-reverse` / `ruyi-mcp` 继续作为默认 Web JS 入口，负责反检测、RuyiTrace、网络/脚本/运行时取证。
- `mcp-js-reverse-playbook` 只在无强反检测且需要 CDP 断点/单步时使用。
- `web-env-patcher` 接收已确认的浏览器证据，负责 cURL/HAR 检查、动态资源保鲜、Trace API inventory、Node 泄露阻断、fixtures 对比、最终请求 TLS 门禁。
- `protocol-recovery` 只在 signer / decoder / session chain 已经验证后，负责采集器和协议交付。


补环境判断矩阵：

| 现象 / 阻塞点 | 路由 |
|---------------|------|
| 页面打不开、需要过风控 / 验证码 / 指纹 / 行为 / RuyiTrace | `ruyi-reverse` |
| 需要 CDP 断点、单步、作用域，且目标无强反检测 | `mcp-js-reverse-playbook` / `js-reverse-mcp` |
| 已有浏览器取证，但目标 JS 脱离浏览器在 Node 中跑不起来 | `web-env-patcher` |
| sign / token / x-s / a_bogus / h5st 依赖浏览器 WebAPI 或指纹终端 API | `web-env-patcher` |
| 需要 Trace API inventory、env coverage matrix、Node 泄露阻断、fixtures 对齐 | `web-env-patcher` |
| 纯算法签名，无浏览器环境依赖，样本字段已确认 | 直接 `protocol-recovery` |
| Node 输出已与浏览器 fixtures 对齐，需要 Python collector / final request | `protocol-recovery` |
| WASM / JSVMP / VM opcode 是核心阻塞 | 标 `triage-only`，必要时转 `ast-deobfuscation` / `web-reverse-algorithm` |

隔离约束：补环境可能依赖 Node ABI 敏感的 `.node` addon、魔改 isolated-vm 或 TLS 指纹客户端。`tools\node\node.exe` 是项目主 Node 和 MCP 运行时，不得替换或切换。Node 25/26、addon、xbs isolated-vm、CycleTLS、impers、curl_cffi 等只能进入 `tools\web-env\runtimes\` 或 `workspace\<项目名>\.runtime\`，并且必须先通过 `tools\web-env\check-isolation.ps1`。


## 1. js-reverse-mcp 完整工具集（基线参考）

js-reverse-mcp 共 **22 个工具**，按工作流阶段分 7 类：

### 1.1 页面管理 (Page Lifecycle) — 3 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 1 | `new_page` | `url`(必填), `timeout` | 打开新标签页并导航 |
| 2 | `navigate_page` | `type`(url/back/forward/reload), `url`, `timeout` | 导航/刷新/前进后退 |
| 3 | `select_page` | `pageIdx` | 切换活跃标签页 |

### 1.2 脚本分析 (Script Analysis) — 3 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 4 | `list_scripts` | `filter`(URL 片段) | 列出页面加载的所有 JS |
| 5 | `get_script_source` | `url`/`scriptId`, `startLine`/`endLine`/`offset`/`length` | 读取脚本片段（预览） |
| 6 | `save_script_source` | `url`/`scriptId`, `filePath`(必填), `format` | 保存完整脚本到本地（自动 beautify） |

### 1.3 源码搜索 (Source Search) — 1 tool

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 7 | `search_in_sources` | `query`(必填), `caseSensitive`, `isRegex`, `excludeMinified`, `urlFilter` | 在所有已加载 JS 中搜索 |

### 1.4 网络取证 (Network Forensics) — 3 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 8 | `list_network_requests` | `reqid`, `pageSize`, `resourceTypes`, `urlFilter`, `outputFile`/`outputPart` | 列出/导出网络请求 |
| 9 | `get_request_initiator` | `requestId`(必填) | 获取请求的 JS 调用栈来源 |
| 10 | `get_websocket_messages` | `wsid`, `analyze`, `direction`, `show_content`, `urlFilter` | 列出/分析 WebSocket 消息 |

### 1.5 调试与断点 (Debugging) — 7 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 11 | `set_breakpoint_on_text` | `text`(必填), `urlFilter`, `occurrence`, `condition` | 按代码文本设断点 |
| 12 | `break_on_xhr` | `url`(必填) | URL 匹配时断点触发 |
| 13 | `get_paused_info` | `includeScopes`, `maxScopeDepth`, `frameIndex` | 暂停时查看调用栈/作用域变量 |
| 14 | `pause_or_resume` | — | 暂停/恢复 JS 执行 |
| 15 | `step` | `direction`(over/into/out, 必填) | 单步执行 |
| 16 | `list_breakpoints` | — | 列出活跃断点 |
| 17 | `remove_breakpoint` | `breakpointId`/`url` | 移除断点 |

### 1.6 运行时求值 (Runtime Evaluation) — 2 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 18 | `evaluate_script` | `function`(必填), `mainWorld`, `frameIndex`, `outputFile`, `localFilePath` | 在页面中执行 JS 并返回结果 |
| 19 | `list_console_messages` | `types`, `pageSize`, `includePreservedMessages` | 读取控制台日志 |

### 1.7 辅助 (Utilities) — 3 tools

| # | 工具 | 关键参数 | 用途 |
|---|------|---------|------|
| 20 | `take_screenshot` | `format`, `fullPage`, `filePath` | 截图 |
| 21 | `select_frame` | `frameIdx` | 切换 iframe 上下文 |
| 22 | `clear_site_data` | — | 清除浏览器状态（Cookie/缓存/存储） |

### 1.8 js-reverse-mcp 工作流（五阶段）

```
Observe ──→ Capture ──→ Rebuild ──→ Patch ──→ DeepDive
  │            │            │           │           │
  │ new_page   │ break_on   │ save_     │ evaluate  │ search_in
  │ list_net.. │ _xhr       │ script_   │ _script   │ _sources
  │ get_req..  │ get_paused │ source    │ (补环境)   │ (去混淆)
  │ list_scr.. │ _info      │ (落盘)     │           │
  │ search_..  │ step       │           │           │
  └────────────┴────────────┴───────────┴───────────┘
```

---

## 2. ruyipage + ruyitrace 现有能力盘点

### 2.1 ruyipage 能力（Python 包，WebDriver BiDi）

| 类别 | API | 说明 |
|------|-----|------|
| **页面导航** | `FirefoxPage()`, `page.get()`, `page.quit()` | 启动/导航/关闭 |
| **元素定位** | `page.ele("#id")`, `ele("css:.cls")`, `ele("xpath://div")`, `ele("tag:input")`, `ele("text:登录")` | 5 种定位方式 |
| **元素读** | `.text`, `.html`, `.value`, `.attr("href")` | 读取元素内容 |
| **元素写** | `.input("text")`, `.clear()`, `.input("file.txt")` | 输入/清空/上传 |
| **元素交互** | `.click_self()`, `.hover()`, `.drag_to()` | 点击/悬停/拖拽 |
| **人类模拟** | `actions.human_move()`, `actions.human_click()` | bezier/windmouse 算法 |
| **触摸模拟** | `touch.tap()`, `touch.long_press()` | 移动端触摸 |
| **网络抓包** | `page.capture.start/stop/wait()` | 按 URL 模式抓包 |
| **请求拦截** | `page.intercept.start_requests(handler)` | 修改请求头/阻断/mock |
| **响应拦截** | `page.intercept.start_responses(handler)` | 读取/修改响应体 |
| **全局 Headers** | `page.network.set_extra_headers()` | 附加请求头 |
| **缓存控制** | `page.network.set_cache_behavior()` | 跳过缓存 |
| **Cookie** | `get_cookies()`, `set_cookies()`, `delete_cookies()` | CRUD |
| **多标签代理** | `set_per_tab_proxies()`, `new_container_tabs()` | 每标签独立 SOCKS5 |
| **指纹伪装** | `smart_fingerprint()`, `apply_emulation()` | 22 维指纹 + 国家校验 |
| **隐私模式** | `private_mode(True)` | 无痕模式 |
| **可视化调试** | `enable_action_visual()`, `enable_xpath_picker()` | 鼠标轨迹可视化 + XPath 拾取 |

### 2.2 ruyitrace 能力（C++ 内核 Hook，PowerShell CLI）

| 类别 | 功能 | 说明 |
|------|------|------|
| **DOM API Hook** | `MOZ_DOM_TRACE=1` | C++ 层 Hook 所有 DOM API |
| **覆盖维度** | canvas, webgl, audio, webrtc, navigator, screen, crypto, storage, font, time, webgpu | 11 个指纹类别 |
| **输出格式** | NDJSON | 每行 `{api, args, stack}` |
| **分析工具** | `trace_analyzer.py` | 分类统计/筛选 |
| **无头模式** | `-Headless` | 后台运行 |

### 2.3 能力缺口对照表

| js-reverse-mcp 能力 | ruyipage 现有 | ruyitrace 现有 | 缺口 |
|---------------------|:---:|:---:|------|
| 页面导航 | ✅ `page.get()` | ❌ | — |
| 多标签管理 | ✅ container tabs | ❌ | — |
| 脚本列表 | ❌ | ❌ | **需要** |
| 脚本源码获取 | ❌ | ❌ | **需要** |
| 脚本保存落盘 | ❌ | ❌ | **需要** |
| 源码搜索 | ❌ | ❌ | **需要** |
| 网络请求列表 | ✅ capture | ❌ | 需结构化暴露 |
| 请求 initiator 调用栈 | ❌ | ❌ | **需要** |
| WebSocket 消息 | ❌ | ❌ | **需要** |
| XHR 断点 | ❌ | ❌ | **需要** (BiDi 可行) |
| 代码文本断点 | ❌ | ❌ | **需要** (BiDi 可行) |
| 暂停信息/调用栈 | ❌ | ❌ | **需要** (BiDi 有限) |
| 单步执行 | ❌ | ❌ | **需要** (BiDi 有限) |
| JS 运行时求值 | ❌ | ❌ | **需要** (BiDi `script.evaluate`) |
| 控制台消息 | ❌ | ❌ | **需要** |
| 截图 | ❌ (需验证) | ❌ | **需要** |
| iframe 选择 | ❌ | ❌ | **需要** |
| 清除浏览器状态 | ❌ | ❌ | **需要** |
| **反检测指纹伪装** | ✅ 22 维 | ❌ | ruyi 独有 ✅ |
| **代理池** | ✅ per-tab SOCKS5 | ❌ | ruyi 独有 ✅ |
| **人类行为模拟** | ✅ bezier/windmouse | ❌ | ruyi 独有 ✅ |
| **元素交互** | ✅ 5 种定位 | ❌ | ruyi 独有 ✅ |
| **请求/响应拦截修改** | ✅ | ❌ | ruyi 独有 ✅ |
| **DOM 指纹追踪** | ❌ | ✅ 11 维 | ruyi 独有 ✅ |
| **Session 导出桥接** | ❌ | ❌ | **需要** (ruyi 独有) |

---

## 3. 当前架构：双 MCP 全链路

```
                    Web RE 目标
                         │
              ┌──────────┴──────────┐
              │  reverse-coordinator │
              │  判定能力需求         │
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    默认 Web JS      CDP 完整调试      APK 内嵌 H5
          │              │              │
          ▼              ▼              ▼
   ruyi-mcp       js-reverse-mcp     apk-reverse
   (Firefox/BiDi   (Chrome/CDP      + ruyi-mcp
    56 tools)       22 tools)       辅助
          │              │
          │     ┌────────┴────────┐
          │     │                 │
          │  ruyipage 能力     ruyitrace 能力
          │  (反检测+自动化)    (DOM追踪)
          │     │                 │
          │     └────────┬────────┘
          │              │
          ▼              ▼
    protocol-recovery (共享下游)
```

**关键原则：**
- js-reverse-mcp 和 ruyi-mcp **不是替代关系**，是**场景互补**
- ruyi-mcp 必须是**全链路方案**，不是"过验证码的工具"
- ruyi-mcp 工具接口**对齐 js-reverse-mcp**，使 skill 流程可复用
- ruyi-mcp 额外具备 js-reverse-mcp **没有**的能力（反检测、指纹、trace、人类模拟）

---

## 4. ruyi-mcp 统一工具集设计规范（历史基线）

### 4.1 工具总数与分类

早期设计基线为 **43 个工具**：核心 22 个对齐 js-reverse-mcp，21 个为 ruyi 独有增强。当前实现已扩展为 **56 tools**，新增 frame、cookie、请求/响应拦截、WebSocket、request initiator、preload scripts 等能力；实际清单以 `mcp/ruyi-mcp/src/tools/` 和 `docs/MCP服务详情.md` 为准。

```
ruyi-mcp = js-reverse-mcp 等价工具 (22)
         + 反检测/指纹 (4)
         + 人类模拟 (3)
         + DOM 元素交互 (4)
         + 指纹追踪 (4)
         + 网络增强 (4)
         + Session 导出 (1)
         ─────────────────
         = 43 tools (+ 21 独有，历史基线)
```

### 4.2 完整工具列表

#### 4.2.1 页面管理 (Page Lifecycle) — 4 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R01 | `ruyi_new_page` | 对齐 | `url`, `timeout`, `proxy`, `fingerprint_profile` | 新标签页；可选代理+指纹 profile |
| R02 | `ruyi_navigate_page` | 对齐 | `type`, `url`, `timeout` | 导航/刷新/前进后退 |
| R03 | `ruyi_select_page` | 对齐 | `pageIdx` | 切换活跃标签 |
| R04 | `ruyi_close_page` | 对齐+ | `pageIdx` | 关闭标签（js-reverse 无此工具） |

**增强点 (vs js-reverse)：**
- `new_page` 直接支持 `proxy` 和 `fingerprint_profile`，一步完成"过检页面"创建

#### 4.2.2 脚本分析 (Script Analysis) — 3 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R05 | `ruyi_list_scripts` | 对齐 | `filter`, `pageIdx` | 列出已加载 JS 脚本 |
| R06 | `ruyi_get_script_source` | 对齐 | `url`/`scriptId`, `startLine`, `endLine`, `offset`, `length` | 读取脚本片段 |
| R07 | `ruyi_save_script_source` | 对齐 | `url`/`scriptId`, `filePath`, `format` | 保存完整脚本到本地 |

**实现要点：**
- Firefox 通过 BiDi `script.getSource` 或内部调试 API 获取源码
- `save_script_source` 的 beautify 复用 prettier（与 js-reverse-mcp 一致）

#### 4.2.3 源码搜索 (Source Search) — 1 tool

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R08 | `ruyi_search_in_sources` | 对齐 | `query`, `caseSensitive`, `isRegex`, `excludeMinified`, `urlFilter` | 搜索已加载 JS 源码 |

#### 4.2.4 网络取证 (Network Forensics) — 3 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R09 | `ruyi_list_network_requests` | 对齐 | `reqid`, `pageSize`, `resourceTypes`, `urlFilter`, `outputFile` | 列出/导出网络请求 |
| R10 | `ruyi_get_request_initiator` | 对齐 | `requestId` | 请求的 JS 调用栈 |
| R11 | `ruyi_get_websocket_messages` | 对齐 | `wsid`, `analyze`, `direction`, `show_content`, `urlFilter` | WS 消息列表/分析 |

**实现要点：**
- 基于 ruyipage `page.capture` 能力，加上调用栈回溯
- `get_request_initiator` 需要在 Firefox 网络监听中注入 stack trace 收集

#### 4.2.5 调试与断点 (Debugging) — 7 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R12 | `ruyi_set_breakpoint_on_text` | 对齐 | `text`, `urlFilter`, `occurrence`, `condition` | 代码文本断点 |
| R13 | `ruyi_break_on_xhr` | 对齐 | `url` | XHR/Fetch URL 断点 |
| R14 | `ruyi_get_paused_info` | 对齐 | `includeScopes`, `maxScopeDepth`, `frameIndex` | 暂停时调用栈/作用域 |
| R15 | `ruyi_pause_or_resume` | 对齐 | — | 暂停/恢复执行 |
| R16 | `ruyi_step` | 对齐 | `direction`(over/into/out) | 单步执行 |
| R17 | `ruyi_list_breakpoints` | 对齐 | — | 活跃断点列表 |
| R18 | `ruyi_remove_breakpoint` | 对齐 | `breakpointId`/`url` | 移除断点 |

**实现要点（技术风险）：**
- BiDi 协议的 `script` 域支持 `script.addPreloadScript`（注入）、`script.evaluate`（求值）
- **断点/单步/调用栈**在 BiDi 中的支持取决于 Firefox 151 定制版的内核版本
- 如果 BiDi 调试能力不足，替代方案：
  - 用 `debugger;` 语句 + `script.addPreloadScript` 注入实现"软断点"
  - 用 Proxy/wrap 模式做函数级 Hook 替代行级断点
  - 或用 Firefox 内部 DevTools 协议（非标准）桥接

#### 4.2.6 运行时求值 (Runtime Evaluation) — 2 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R19 | `ruyi_evaluate_script` | 对齐 | `function`, `mainWorld`, `frameIndex`, `outputFile`, `localFilePath` | 页面中执行 JS |
| R20 | `ruyi_list_console_messages` | 对齐 | `types`, `pageSize`, `includePreservedMessages` | 控制台消息 |

**实现要点：**
- BiDi `script.evaluate` 原生支持，这是 ruyipage 当前缺失但 BiDi 标准支持的能力
- `mainWorld` 映射到 BiDi 的 `realm` 概念

#### 4.2.7 辅助 (Utilities) — 3 tools

| # | 工具 | 类型 | 关键参数 | 说明 |
|---|------|------|---------|------|
| R21 | `ruyi_take_screenshot` | 对齐 | `format`, `fullPage`, `filePath` | 截图 |
| R22 | `ruyi_select_frame` | 对齐 | `frameIdx` | 切换 iframe 上下文 |
| R23 | `ruyi_clear_site_data` | 对齐 | — | 清除浏览器状态 |

---

#### 4.2.8 反检测与指纹 (Anti-Detection) — 4 tools（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R24 | `ruyi_set_proxy` | `pageIdx`, `proxy_url`(socks5://host:port:user:pass) | 为标签设置代理 |
| R25 | `ruyi_set_fingerprint` | `pageIdx`, `profile`{ `country`, `timezone`, `language`, `screen`, `canvas_noise`, `webgl_vendor`, `fonts`, `platform`, `hardware_concurrency`, ... } | 设置 22 维指纹 |
| R26 | `ruyi_emulate_geolocation` | `pageIdx`, `latitude`, `longitude`, `accuracy` | 模拟地理位置 |
| R27 | `ruyi_emulate_timezone` | `pageIdx`, `timezone_id`, `locale` | 模拟时区/语言 |

**实现基础：** ruyipage `smart_fingerprint()` + `apply_emulation()`，封装为独立可调工具。

---

#### 4.2.9 人类行为模拟 (Human Simulation) — 3 tools（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R28 | `ruyi_human_move` | `pageIdx`, `target`(selector), `algorithm`(bezier/windmouse), `style`(arc/linear) | 人类鼠标移动 |
| R29 | `ruyi_human_click` | `pageIdx`, `target`, `algorithm` | 人类点击 |
| R30 | `ruyi_human_input` | `pageIdx`, `target`, `text`, `delay_ms` | 人类打字输入 |

**实现基础：** ruyipage `page.actions.human_move/human_click` + `page.ele().input()`。

---

#### 4.2.10 DOM 元素交互 (DOM Interaction) — 4 tools（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R31 | `ruyi_dom_select` | `pageIdx`, `selector`, `timeout` | 选择元素（返回元素 ID） |
| R32 | `ruyi_dom_get_info` | `pageIdx`, `elementId` | 获取元素的 text/html/value/attrs |
| R33 | `ruyi_dom_input` | `pageIdx`, `elementId`/`selector`, `text`, `clear` | 输入文本/文件 |
| R34 | `ruyi_dom_click` | `pageIdx`, `elementId`/`selector` | 点击元素 |

**设计说明：**
将这些从 ruyipage 的元素 API 提升为独立的 MCP 工具，使 Claude Code 可以直接操控页面元素（js-reverse-mcp 通过 `evaluate_script` 间接做到，但不如专用工具语义清晰）。

---

#### 4.2.11 BiDi 追踪 (BiDi Trace) — 3 tools（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R35 | `ruyi_trace_start` | `pageIdx`, `outputFile` | 启动 RuyiPage/WebDriver BiDi JSON Trace |
| R36 | `ruyi_trace_stop` | `pageIdx` | 停止记录，可将 JSON dump 保存到 `outputFile` |
| R37 | `ruyi_trace_get_results` | `pageIdx`, `limit` | 读取内存中最近的结构化 BiDi 事件 |

**实现要点：**
- `trace_start/stop` 通过 RuyiPage `Settings.trace_enabled` 和 `page.trace` 控制 BiDi 事件记录
- launch 时启用可保留初始导航证据；运行时首次 start 会建立新 trace 段
- C++ DOMTrace 是独立 T3 能力，由 `tools\ruyitrace\ruyitrace.ps1` 启动专用 Firefox，不伪装成 MCP `ruyi_trace_*`

---

#### 4.2.12 网络增强 (Network Enhancement) — 4 tools（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R39 | `ruyi_intercept_requests` | `pageIdx`, `pattern`, `action`(block/modify/continue), `modifications`{headers, body} | 请求拦截修改 |
| R40 | `ruyi_intercept_responses` | `pageIdx`, `pattern`, `action`, `modifications` | 响应拦截修改 |
| R41 | `ruyi_set_extra_headers` | `pageIdx`, `headers`{key:value} | 全局附加请求头 |
| R42 | `ruyi_set_cache_behavior` | `pageIdx`, `mode`(default/bypass/force_cache) | 缓存策略 |

**实现基础：** ruyipage `page.intercept` + `page.network` API。

---

#### 4.2.13 Session 导出 (Session Export) — 1 tool（ruyi 独有）

| # | 工具 | 关键参数 | 说明 |
|---|------|---------|------|
| R43 | `ruyi_export_session` | `pageIdx`, `outputFile`, `include`([cookies,localStorage,sessionStorage,indexedDB]) | 导出浏览器状态 |

**用途：**
- ruyi → js-reverse-mcp Cookie 桥接（弱检测场景回退需要）
- 保存登录态供后续分析复用
- 跨工具 session 迁移的自动化基础

---

### 4.3 工具分类统计

| 分类 | 工具数 | 对齐 js-reverse | ruyi 独有 |
|------|:---:|:---:|:---:|
| 页面管理 | 4 | 3 + 1 增强 | 1 |
| 脚本分析 | 3 | 3 | 0 |
| 源码搜索 | 1 | 1 | 0 |
| 网络取证 | 3 | 3 | 0 |
| 调试与断点 | 7 | 7 | 0 |
| 运行时求值 | 2 | 2 | 0 |
| 辅助 | 3 | 3 | 0 |
| **反检测/指纹** | **4** | — | **4** |
| **人类模拟** | **3** | — | **3** |
| **DOM 交互** | **4** | — | **4** |
| **指纹追踪** | **4** | — | **4** |
| **网络增强** | **4** | — | **4** |
| **Session 导出** | **1** | — | **1** |
| **总计** | **43** | **22** | **21** |

---

## 5. ruyi-mcp 五阶段工作流（与 js-reverse-mcp 对齐）

```
Observe ──────→ Capture ──────→ Rebuild ──────→ Patch ──────→ DeepDive
    │                │               │               │               │
    │ ruyi_new_page  │ ruyi_break    │ ruyi_save     │ ruyi_eval     │ ruyi_search
    │ +proxy+finger  │ _on_xhr       │ _script       │ uate_script   │ _in_sources
    │ print          │ ruyi_get_     │ _source       │ (补环境)       │ (去混淆)
    │ ruyi_list_net  │ paused_info   │ (本地落盘)     │ ruyi_trace_   │
    │ work_requests  │ ruyi_step     │               │ analyze       │
    │ ruyi_get_req   │               │               │ (指纹取证)     │
    │ _initiator     │               │               │               │
    │ ruyi_list_scri │               │               │               │
    │ pts            │               │               │               │
    │ ruyi_search..  │               │               │               │
    │                │               │               │               │
    │ 【ruyi独有】    │               │               │               │
    │ ruyi_dom_*     │               │               │               │
    │ ruyi_human_*   │               │               │               │
    │ ruyi_intercept │               │               │               │
    │ ruyi_trace_st* │               │               │               │
    └────────────────┴───────────────┴───────────────┴───────────────┘
```

**Observe 阶段 ruyi-mcp 的额外能力：**
- `ruyi_set_proxy` + `ruyi_set_fingerprint` 在打开页面前配置反检测环境
- `ruyi_dom_select` + `ruyi_dom_get_info` 直接检查页面 DOM 状态
- `ruyi_intercept_requests` 在请求发出前就拦截
- `ruyi_trace_start` 一边观察一边记录结构化 BiDi 命令与事件

**Rebuild 阶段 ruyi-mcp 的额外能力：**
- `ruyi_export_session` 导出完整浏览器状态供 Node 补环境参考
- BiDi Trace 用于定位导航、网络与运行时时序；需要 DOM API 维度时再用 `ruyitrace.ps1` + `trace_analyzer.py`

---

## 6. 技术实现路线

### 6.1 架构选型

```
┌────────────────────────────────────────────┐
│              ruyi-mcp (Node.js)             │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │     MCP Server (stdio transport)     │   │
│  │     → 56 tools exposed to AI clients │   │
│  └──────────────┬──────────────────────┘   │
│                 │                            │
│  ┌──────────────┴──────────────────────┐   │
│  │        Ruyi Bridge Layer             │   │
│  │  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │ BiDi      │  │ Trace Controller │  │   │
│  │  │ Client    │  │ (子进程管理)      │  │   │
│  │  └─────┬─────┘  └────────┬─────────┘  │   │
│  └────────┼─────────────────┼────────────┘   │
│           │                 │                 │
│  ┌────────┴────────┐ ┌──────┴──────────┐    │
│  │ Firefox 151.0a1 │ │ Firefox 151     │    │
│  │ (ruyipage 定制)  │ │ Trace Kernel    │    │
│  │ WebDriver BiDi   │ │ MOZ_DOM_TRACE=1 │    │
│  └─────────────────┘ └─────────────────┘    │
└────────────────────────────────────────────┘
```

**关键决策：**
- **MCP 层用 Node.js**（复用 js-reverse-mcp 的 MCP server 框架 + 工具注册模式）
- **BiDi 客户端**通过 WebSocket 连接 Firefox（ruyipage 的 Python 包里已有实现，需要移植或用 Node.js 重写 BiDi 客户端）
- **实际落地分层**：MCP Bridge 只管理 RuyiPage BiDi JSON Trace；C++ DOMTrace Firefox 由独立 CLI 管理，不经 MCP 子进程伪装

### 6.2 分阶段实现

#### Phase 1：核心 22 工具对齐（MCP + BiDi）

**目标：** ruyi-mcp 具备 js-reverse-mcp 的全部等价功能。

| 步骤 | 内容 | 风险 |
|------|------|------|
| 1.1 | Node.js BiDi 客户端封装（WebSocket → Firefox） | 低 — BiDi 是开放标准 |
| 1.2 | 页面管理工具 (R01-R04) | 低 — BiDi `browsingContext` 域 |
| 1.3 | 脚本分析工具 (R05-R07) | 中 — Firefox 脚本获取 API 需验证 |
| 1.4 | 网络取证工具 (R09-R11) | 低 — BiDi `network` 域 |
| 1.5 | 运行时求值工具 (R19-R20) | 低 — BiDi `script.evaluate` |
| 1.6 | 辅助工具 (R21-R23) | 低 |
| 1.7 | 调试工具 (R12-R18) | **高** — BiDi 断点/单步能力需验证 |

**调试工具备选方案（如果 BiDi 不支持完整断点）：**

```javascript
// 方案 A: debugger; 软断点注入
await script.addPreloadScript({
  functionDeclaration: `
    (() => {
      const original = window.targetFunction;
      window.targetFunction = function(...args) {
        debugger; // 触发 BiDi 暂停
        return original.apply(this, args);
      };
    })()
  `
});

// 方案 B: Proxy 函数级 Hook
await script.addPreloadScript({
  functionDeclaration: `
    (() => {
      // 用 Proxy 包装目标对象的方法
      // 在每个方法调用时收集 args/return/stack
      // 通过 BiDi script.evaluate 同步读取
    })()
  `
});
```

#### Phase 2：反检测 + 网络增强（ruyipage 封装）

**目标：** ruyi-mcp 具备完整的反检测和网络操控能力。

| 步骤 | 内容 | 基础 |
|------|------|------|
| 2.1 | 指纹设置工具 (R24-R27) | ruyipage `smart_fingerprint` |
| 2.2 | 网络增强工具 (R39-R42) | ruyipage `intercept` + `network` |
| 2.3 | DOM 交互工具 (R31-R34) | ruyipage `page.ele` |

**需要：** 把 ruyipage Python 包的关键逻辑移植到 Node.js BiDi 客户端，或通过子进程调用 Python CLI 桥接。

#### Phase 3：Trace 分层落地

**目标：** ruyi-mcp 提供 BiDi JSON Trace，DOM API 内核取证保持独立 CLI。

| 步骤 | 内容 | 基础 |
|------|------|------|
| 3.1 | BiDi Trace 启动/停止 (R35-R36) | RuyiPage `Settings` + `page.trace` |
| 3.2 | BiDi Trace 结果读取 (R37) | 内存 JSON entries / dump |
| 3.3 | C++ DOMTrace | `tools\ruyitrace\ruyitrace.ps1` + PID 分片 NDJSON |

**关键边界：** `ruyi_trace_start` 不启动独立 DOMTrace 浏览器。需要 T3 内核取证时，先用 `ruyi_export_session` 保存状态，再交给 DOMTrace 专用 Firefox。

#### Phase 4：人类模拟 + Session 导出

| 步骤 | 内容 | 基础 |
|------|------|------|
| 4.1 | 人类行为工具 (R28-R30) | ruyipage `actions` |
| 4.2 | Session 导出 (R43) | Cookie + Storage API |

### 6.3 技术风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:---:|:---:|------|
| BiDi 不支持完整断点/单步 | 中 | 高 | 降级为函数 Hook + Proxy 模式 |
| Firefox 151 源码获取 API 不可用 | 中 | 中 | 通过 `evaluate_script` + `fetch` 间接获取 |
| ruyitrace 无法与 ruyipage 共享进程 | 高 | 中 | 双进程 + Cookie 桥接自动化 |
| 定制 Firefox 版本升级后 API 变化 | 低 | 高 | 版本锁定 + 兼容层 |

---

## 7. Skill 层改造（与 MCP 同步）

### 7.1 新建 `ruyi-reverse` skill

```
skill/ruyi-reverse/
├── SKILL.md              # 主 skill（参考 mcp-js-reverse-playbook 结构）
├── references/
│   ├── tool-defaults.md  # ruyi_* 工具默认值
│   ├── workflow.md       # 强检测五阶段工作流
│   ├── anti-detection.md # 反检测配置指南
│   ├── trace-usage.md    # 指纹追踪使用指南
│   └── session-bridge.md # Cookie 桥接操作
```

### 7.2 `reverse-coordinator` 路由（当前口径）

```
Web JS 路由决策树：
  ├── 默认 → ruyi-reverse (ruyi-mcp)
  │     ├── 需要 BiDi 时序取证 → ruyi_trace_* 子流程
  │     ├── 需要 C++ DOM API 取证 → 导出 session 后运行 tools\ruyitrace\ruyitrace.ps1
  │     ├── 需要过验证码 / 人类行为 → ruyi_fingerprint_* + ruyi_human_*
  │     └── 需要导出会话 → ruyi_export_session
  ├── 明确需要 CDP 暂停 / 单步 / 作用域枚举，且无强反检测 → mcp-js-reverse-playbook (js-reverse-mcp)
  └── 两者协作 → ruyi_export_session → js-reverse-mcp 继续 CDP 调试
```

### 7.3 更新 `CLAUDE.md` — Skill 速查表

```markdown
| `ruyi-reverse` | Web JS 强检测 | ruyi-mcp (Firefox/BiDi) 全链路 — 反检测+JS逆向+指纹追踪 |
```

MCP 前缀表新增：
```markdown
| `ruyi_*` | ruyi-mcp | Firefox/BiDi 全链路增强 — 反检测/指纹/人类模拟/trace/JS逆向 (56 tools) |
```

---

## 8. 与现状对比总结

| 维度 | 现状 | 目标 |
|------|------|------|
| **强检测场景覆盖** | ruyipage 只用来过验证码，然后手动切 Chrome | ruyi-mcp 全链路覆盖，从反检测→JS调试→补环境→协议恢复 |
| **MCP 集成** | 两个一等 MCP 服务已并存：ruyi-mcp 默认、js-reverse-mcp 专注 CDP | 继续补齐验证与文档同步 |
| **反检测+调试共存** | 做不到（跨浏览器 Cookie 手动搬） | 同一 Firefox session 内完成 |
| **指纹追踪** | 独立 CLI，手动分析 | MCP 工具实时追踪+分析，嵌入工作流 |
| **工具对齐** | ruyi-mcp 当前 56 tools，核心能力覆盖并扩展 js-reverse-mcp 工作流 | 继续维护能力边界和桥接规范 |
| **工作流复用** | 每个 skill 独立工作流 | Observe→Capture→Rebuild→Patch→DeepDive 五阶段统一 |
| **Session 桥接** | 手动 | `ruyi_export_session` 自动化 |
