# ruyitrace CLI 参考（T3 回退）

> **这不是独立 skill。** 仅在 ruyi-mcp 的 `ruyi_trace_*` (BiDi trace) 不足时回退使用。
> 升级决策见 `references/tier-system.md` 的 T3 升级触发信号。

## 本机环境

| 项目 | 值 |
|------|-----|
| 内核路径 | `"D:\reverse_ENV\tools\ruyitrace\firefox\firefox.exe"` |
| 追踪机制 | `MOZ_DOM_TRACE=1` → C++ 层 Hook |
| Windows 启动约束 | `MOZ_DISABLE_LAUNCHER_PROCESS=1`，避免 launcher 提前退出 |
| 输出格式 | NDJSON（每行一条 API 调用） |
| 标记文件 | `"D:\reverse_ENV\tools\ruyitrace\firefox\RUYI_DOMTRACE.txt"` (**禁止删除**) |

## T2 vs T3 对比

| 维度 | T2: ruyi_trace_* (BiDi) | T3: ruyitrace CLI (C++) |
|------|------------------------|------------------------|
| Hook 层级 | BiDi 事件层 | Firefox C++ 内核层 |
| 覆盖维度 | 取决于 BiDi 事件覆盖 | **全部 11 维** |
| 调用栈 | JS 级，可能截断 | C++ Hook 记录的 JS frame 列表（不是 native C++ backtrace） |
| 可检测性 | 页面可能感知 | 无页面级 monkey patch；仍可能有性能侧效应，不声称绝对不可检测 |
| 输出 | 结构化 JSON (MCP) | 原始 NDJSON |
| 并发 | 同进程 | **独立 Firefox** (需 profile 隔离) |

## CLI

```powershell
powershell -File "D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1" `
  -Url "https://target.com" `
  -Output "D:\reverse_ENV\workspace\<project>\trace.ndjson" `
  [-Limit 200000] `
  [-KeepProcessFiles] `
  [-ProcessTypes "parent,tab"] `
  [-DurationSeconds 10 -Headless]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-Url` | 目标 URL (必填) | — |
| `-Output` | NDJSON 输出路径，必须传 quoted absolute 路径 | `"D:\reverse_ENV\workspace\<project>\trace.ndjson"` |
| `-Profile` | Firefox profile 目录 | 临时 |
| `-Headless` | 无头模式 | 否 |
| `-Limit` | 每个 Firefox 进程的最大 NDJSON 行数；`0` 使用内核默认 | `0` |
| `-KeepProcessFiles` | 保留内核生成的 `<output>_<PID>.ndjson` 分片 | 否 |
| `-ProcessTypes` | 传给 `MOZ_DOM_TRACE_PTYPE` 的进程类型 | `parent,tab` |
| `-DurationSeconds` | 非交互采集时长；要求 `-Headless` | `0`（交互） |
| `-RemoteDebuggingPort` | 定时采集 Remote Agent 端口；`0` 自动选 loopback 空闲端口 | `0` |

Firefox 内核会在 `MOZ_DOM_TRACE_FILE` 的文件名后追加 PID。包装脚本会等待本轮分片稳定，再合并到 `-Output` 指定的单一 NDJSON；默认删除已合并的 PID 分片。

定时模式不是 `Start-Sleep + terminate()`：Firefox 先按命令行打开 URL，Remote Agent session 就绪后执行 `browsingContext.reload`，到时通过 `browser.close` 优雅退出。这样既避开当前 HTTP `browsingContext.navigate` 的 `NS_ERROR_NOT_IMPLEMENTED`，又让页面关键调用发生在 Trace 初始化后，并给 parent/tab 分片留出 flush 时间。生命周期 helper 为 `tools\ruyitrace\bidi_close.py`。

## NDJSON 格式

当前 Firefox 151 schema：

```json
{"type":"call","interface":"CanvasRenderingContext2D","member":"fillText","args":[],"stack":[]}
```

分析器同时兼容旧 `{ "api": "CanvasRenderingContext2D.fillText" }` schema。Custom serializer 对个别长 Function source 可能多写一个 closing-quote 反斜杠；分析器只在边界唯一、parser 停点一致、修复后结构为 `typeof` + `Function` 时做内存修复。`raw_invalid_lines` 保留原始缺陷，`repaired_lines` 记录行号与原因，`unrecoverable_lines` / 兼容字段 `invalid_lines` 记录仍不可恢复的行，禁止把原始坏行静默写成零。

## 分析

```bash
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson"           # 全维度
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson" -c canvas  # 仅 Canvas
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson" -c webgl   # 仅 WebGL
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson" --json     # 机器可读摘要
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson" --json --strict  # 有不可恢复行时 exit 2
```

**覆盖维度：** canvas, webgl, audio, webrtc, navigator, screen, crypto, storage, font, time, webgpu

## T3 工作流

```
1. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\trace-session.json" }
   (在 ruyipage 中过检并导出登录态)

2. 启动 ruyitrace:
   powershell -File "D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1" `
     -Url "https://target.com" -Output "D:\reverse_ENV\workspace\<project>\trace.ndjson"

3. 在 trace 浏览器中注入 session.json 的 cookies
   (通过浏览器控制台或 preload script)

4. 刷新页面 → 执行目标操作 → 关闭浏览器

5. "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson"
```

## 升级触发信号

| 信号 | 说明 |
|------|------|
| `ruyi_trace_get_results` 缺失 canvas/webgl/audio | BiDi 不覆盖 |
| trace 堆栈截断 | 只有 JS 无 native |
| 页面检测到自动化 | console 有反调试日志 |
| 需要离线 NDJSON | 自定义统计维度 |
| 需要精确调用时序 | BiDi 时间戳精度不够 |

## 禁止

- **不删除** `"D:\reverse_ENV\tools\ruyitrace\firefox\RUYI_DOMTRACE.txt"`
- **不与 ruyipage 共享 profile** — 独立 Firefox 进程
- **不在 T2 足够时用 T3** — C++ trace 开销更大
- **不得用 taskkill / 宽泛 Stop-Process 关闭全部 Firefox** — 定时 wrapper 只管理本次 profile/PID 树
