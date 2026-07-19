---
name: web-env-patcher
description: |
  Web JS Node 补环境工程化 skill。接在 ruyi-reverse / mcp-js-reverse-playbook 的浏览器取证之后，用于 cURL/HAR 输入检查、动态资源保鲜、Trace API 覆盖矩阵、Node 宿主泄露阻断、fixture 对比、浏览器指纹终端 API 回放设计和最终请求 TLS 客户端门禁。所有补环境 runtime 必须独立隔离，禁止切换或污染项目主 Node/MCP 环境。
---

# Web Env Patcher（网页端 Node 补环境工程）

## 定位

本 skill 专门处理网页端 JavaScript 从浏览器取证材料落到 Node.js 补环境工程的中间层。

它不是 Web 逆向入口，也不是协议采集器交付入口：

```text
ruyi-reverse / mcp-js-reverse-playbook
  -> web-deobfuscation（当混淆、JSVMP 或 WASM 边界是核心阻塞）
  -> web-env-patcher（当浏览器环境依赖是核心阻塞）
  -> protocol-recovery
```

- `ruyi-reverse`：负责反检测浏览器、RuyiTrace、网络取证、源码和运行时定位。
- `mcp-js-reverse-playbook`：仅在无强反检测且需要 CDP 断点/单步时使用。
- `web-deobfuscation`：负责 safe AST、可验证 JSVMP 和可观察 JS/WASM 边界的证据门禁。
- `web-env-patcher`：负责把浏览器证据工程化为 Node.js 补环境、fixtures、coverage matrix 和最终请求验证门禁。
- `protocol-recovery`：在 signer / decoder / session chain 已确认后，打包 Python 采集器或协议复现工程。


## 补环境判断矩阵

| 现象 / 阻塞点 | 路由 | 说明 |
|---------------|------|------|
| 页面打不开、需要过风控 / 验证码 / 指纹 / 行为 / RuyiTrace | `ruyi-reverse` | 先拿到可信浏览器证据，不要直接补环境。 |
| 需要 CDP 断点、单步、作用域，且目标无强反检测 | `mcp-js-reverse-playbook` | 先完成 request initiator、断点样本和源码定位。 |
| 已有浏览器取证，但目标 JS 脱离浏览器在 Node 中跑不起来 | `web-env-patcher` | 本 skill 主场：补 WebAPI、Node 泄露阻断和 fixtures。 |
| sign / token / x-s / a_bogus / h5st 依赖 `window/document/navigator/storage/crypto/performance/canvas/webgl` | `web-env-patcher` | 先做 Trace API inventory 和 env coverage matrix。 |
| 需要 Trace API inventory、env coverage matrix、Node 泄露阻断、fixtures 对齐 | `web-env-patcher` | 必须有浏览器真实样本作为对照。 |
| 纯算法签名，无浏览器环境依赖，样本字段已确认 | `protocol-recovery` | 不要为了纯 MD5/AES/HMAC 强行补环境。 |
| Node 输出已与浏览器 fixtures 对齐，需要 Python collector / final request | `protocol-recovery` | 本 skill 到此结束，进入协议交付。 |
| AST 混淆、JSVMP / VM opcode 或 JS/WASM 边界是核心阻塞 | `web-deobfuscation` | 先跑只读 gate；有 opcode/boundary Trace 与 fixture 才允许 L3/partial，否则保持 `triage-only`。 |

## 硬边界

- 只处理网页端 / 浏览器端 JavaScript 的 Node.js 补环境。
- 不处理 Android、iOS、小程序、EXE、DLL、SO、Frida、IDA、JADX、Native patch。
- 不替代 `ruyi-reverse` 做页面打开、反检测、trace 采集和交互取证。
- 不替代 `protocol-recovery` 做最终 Python 采集器交付。
- 默认不主动分析 JSVMP / WASM / VM 字节码；遇到该类目标时记录环境依赖，并切换到 `web-deobfuscation` 做独立证据分级，不在本 skill 内冒充算法恢复。

## 环境隔离硬约束

补环境可能引入 Node ABI 敏感的 `.node` addon、魔改 `isolated-vm`、TLS 指纹客户端、浏览器 profile 和临时依赖。为避免弄坏整个 `D:\reverse_ENV`，必须遵守以下规则：

1. **禁止切换项目主 Node**：`D:\reverse_ENV\tools\node\node.exe` 是 MCP / 项目默认 Node，不得为了补环境 addon 改版本、覆盖目录或替换二进制。
2. **独立 runtime 目录**：需要 Node 25/26、xbs addon、魔改 isolated-vm、CycleTLS、impers、curl-cffi-node 时，只能放在 `D:\reverse_ENV\tools\web-env\runtimes\` 或 `D:\reverse_ENV\workspace\<项目名>\.runtime\`。
3. **显式路径调用**：所有 `node`、`python`、`npm`、浏览器、RuyiTrace、TLS 客户端检测都必须使用绝对路径；不得依赖系统 PATH。
4. **不自动安装依赖**：不得未经用户确认运行 `npm install`、`pip install`、`nvm use`、`nvm install` 或覆盖 runtime。缺依赖时只报告候选命令和隔离落点。
5. **不全局设置环境变量**：只允许在当前进程或 wrapper 脚本内临时设置 `RUYI_TRACE_HOME`、`WEB_JS_ENV_PATCHER_ADDON` 等变量；不得写入系统用户环境变量。
6. **不把外部 skill 直接启用为项目 skill**：`storage\xbsReverseSkill` 仅作为参考/可选脚本来源；项目唯一入口是本 skill 和 `tools\web-env` wrapper。
7. **case 内隔离状态**：浏览器 profile、Cookie jar、HAR、fixtures、日志、临时 JS、TLS 采样结果必须落在 `D:\reverse_ENV\workspace\<项目名>\` 下，不得散落 `workspace\` 根目录或 `tools\`。
8. **ABI 先检后用**：任何 `.node` addon 或 isolated-vm 在使用前必须运行隔离检查；ABI 不匹配时不得 fallback 成“已成功”，只能降级为纯 JS 流程或记录 native capability gap。

## 标准工作流

### 0. 前置门禁

启动前必须已完成至少一种浏览器取证：

- `ruyi-reverse` 产出的请求、脚本、trace、Cookie/Storage、fingerprint baseline；或
- `mcp-js-reverse-playbook` 产出的 request initiator、断点样本、源码片段、运行时参数。

如果还没有这些证据，返回上游 skill，不要直接补环境。

### 1. 输入检查

目标：确认用户提供的 cURL / HAR / HTML / JS / 响应样本是否足以开始补环境。

应检查：

- 目标 URL、方法、Header、Cookie、Body 是否完整。
- sign / token / x-s / a_bogus / h5st / w_rid / captcha 参数位于 query、header、body 还是 cookie。
- 样本中的动态值是否只是历史 fixture，不能硬编码复用。
- 用户样本浏览器族与取证 baseline 是否冲突。
- 敏感字段是否需要 scrub 后进入 evidence。

### 2. 动态资源保鲜

目标：防止固定过期 HTML / JS bundle / challenge JS。

必须记录：

- 资源 URL、hash、采集时间、响应头、cache-control、etag、last-modified。
- 是否运行时刷新资源。
- 最终 `runner.js` / `final.js` 是否仍使用旧快照。

### 3. Trace API inventory

目标：把浏览器/RuyiTrace/Node trace 中出现的 WebAPI 转成补环境待办，而不是等报错才补。

标准产物：

```text
D:\reverse_ENV\workspace\<项目名>\evidence\trace-api-inventory.json
D:\reverse_ENV\workspace\<项目名>\evidence\env-coverage-matrix.md
```

覆盖矩阵至少包含：

| 字段 | 说明 |
|---|---|
| `api` | 被访问的 WebAPI / 属性 / 方法 |
| `source` | RuyiTrace / browser hook / Node trace / manual evidence |
| `count` | 调用次数 |
| `stack` | 脱敏调用栈或脚本位置 |
| `strategy` | implement / fixture-replay / sample-browser / native-gap / ignore |
| `status` | pending / done / blocked / triage-only |
| `evidence` | 本地证据路径 |

### 4. Node 泄露阻断

补环境运行前必须检查宿主 Node 泄露：

- `process`、`Buffer`、`require`、`module`、`global`。
- Node 自带 `navigator`、`localStorage`、`sessionStorage`。
- `performance.nodeTiming`、`eventLoopUtilization`、`timerify`。
- 宿主 `fetch`、`WebSocket`、Streams、Events。
- `crypto`、`URL`、`TextEncoder`、`WebAssembly` 是否与浏览器 baseline 冲突。

### 5. Env 模块实现

按 coverage matrix 补环境，禁止一个巨型 `env.js` 糊到底。推荐结构：

```text
workspace\<项目名>\src\env\
  window.js
  document.js
  navigator.js
  storage.js
  crypto.js
  performance.js
  fingerprint.js
```

原则：

- 先补实际命中的 API，再补推断 API。
- 指纹终端 API 优先真实浏览器采样回放，不瞎模拟渲染结果。
- `document.all`、prototype chain、descriptor、getter/setter、`Function.prototype.toString`、`Symbol.toStringTag` 必须作为高强度检测项单独记录。
- addon / isolated-vm 不可用时，明确记录 JS fallback 风险。

### 6. Fixtures 验证

必须用浏览器真实样本对比 Node 输出。

标准产物：

```text
workspace\<项目名>\fixtures\browser-output.fixture.json
workspace\<项目名>\fixtures\node-output.fixture.json
workspace\<项目名>\fixtures\fingerprint.fixture.json
workspace\<项目名>\notes\fixture-validation.md
```

至少记录：

- 样本数量、通过数量、失败数量。
- 是否固定时间、随机数、Cookie、Storage、UA、语言、时区、代理。
- 失败字段、first divergence、下一步补环境策略。

### 7. 最终请求 TLS 门禁

如果需要发送真实请求或交付可请求 `final.js` / `final.py`，必须先选择最终请求客户端：

- Node.js：CycleTLS / impers / curl-cffi-node / 不发真实请求。
- Python：curl_cffi / cffi_curl / cyCronet / 不发真实请求。

规则：

- 最终请求必须 Session 模式。
- UA、Client Hints、Accept-Language、Header 顺序、Cookie jar、代理、TLS / JA3 / JA4 / HTTP2 指纹必须来自同一取证 baseline。
- Firefox baseline 不得混用 Chrome `sec-ch-ua`。
- 普通 `fetch` / `requests` 失败后临时切 TLS 客户端不合格；客户端选择必须前置记录。

## 工作区推荐结构

```text
D:\reverse_ENV\workspace\<项目名>\
  captures\
    request.har
    request.curl
    ruyitrace.ndjson
  samples\
    raw\
    scrubbed\
  fixtures\
    request.fixture.json
    browser-output.fixture.json
    node-output.fixture.json
    fingerprint.fixture.json
  src\
    env\
    signer\
    runner.js
  evidence\
    trace-api-inventory.json
    env-coverage-matrix.md
    redaction-map.json
  notes\
    runtime-precheck.md
    node-leakage.md
    final-request-validation.md
    code-change-memory.md
  report.md
  findings.json
  triage.md
```

## 工具入口

项目封装脚本位于 `D:\reverse_ENV\tools\web-env\`：

| 脚本 | 用途 |
|---|---|
| `check-isolation.ps1` | 检查主 Node、可选 xbs clone、RuyiTrace 路径、addon ABI 状态，确认补环境隔离边界。 |
| `invoke-xbs-script.ps1` | 只读调用 `storage\xbsReverseSkill\web-js-env-patcher\scripts\*.js` 中的纯 JS 检查器，强制绝对路径和临时环境变量。 |

调用示例：

```powershell
powershell -File "D:\reverse_ENV\tools\web-env\check-isolation.ps1"
powershell -File "D:\reverse_ENV\tools\web-env\invoke-xbs-script.ps1" -Script "check_tls_clients.js" -ScriptArgs "--markdown"
```

## 借鉴来源

本 skill 吸收了 `D:\reverse_ENV\storage\xbsReverseSkill\web-js-env-patcher` 的补环境流程思想，但不直接启用其外部 skill，也不默认加载其 native addon / isolated-vm 二进制。该仓库为 MIT License；若后续复制具体实现代码到 Git 管理范围，应保留来源说明并做路径、编码、隔离改造。

## 交付标准

一次合格的 web-env-patcher 任务最终必须提供：

- `report.md`：结论、证据路径、复用来源、环境隔离状态。
- `findings.json`：结构化 claim、evidence、redaction、confidence、rebuild_status。
- `triage.md`：未补 API、native capability gap、TLS/指纹差异、JS fallback 风险。
- `evidence/env-coverage-matrix.md`：Trace 命中 API 的处理状态。
- `notes/final-request-validation.md`：如果发送真实请求，记录 TLS/session/client baseline；如果不发送，明确说明。

不得声称“补环境完成”，除非 fixtures 已对齐、coverage matrix 无未解释关键 API、最终请求门禁已通过或明确标注不发真实请求。
