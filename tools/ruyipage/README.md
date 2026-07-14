# ruyipage Firefox 运行时

本目录用于管理 ruyipage 定制 Firefox 的本地 runtime。这里只跟踪治理说明；`runtimes/` 下的浏览器二进制由 `.gitignore` 排除，不进入 Git。

## 并行运行时

| 项 | 值 |
|----|----|
| Release | `151-proxy` |
| 可执行文件 | `D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe` |
| Windows release asset SHA256 | `f82151f9f197b528b36fb461cf106bc6825c0f752efb5c5d762c34f7529055f6` |
| Firefox BuildID | `20260702113527` |
| 配套依赖 | `ruyiPage==1.2.46`、`ruyi-mcp 0.1.1` |
| 当前状态 | 已完成回归并作为项目 MCP 的 BiDi runtime 启用 |

该 runtime 已通过 BiDi launch/quit、UA/viewport/timezone/locale/orientation、DOM click、launch/runtime Trace entries 增长和 stop 后冻结，以及真实 HTTP 认证代理与 percent-encoded 凭据验证。3 个 headed fingerprint profile 均未复现 Issue #20 的窗口最大化/坐标偏移；SOCKS5 因当前供应商没有对应产品，只完成 offline contract，待有可用供应商时补真实出口门禁。

它没有 `RUYI_DOMTRACE.txt` marker，实际验证也未生成 C++ DOMTrace 输出，因此不能替换 DOMTrace 专用内核。

## Trace 能力边界

- `ruyi_trace_start`、`ruyi_trace_stop`、`ruyi_trace_get_results` 使用 RuyiPage/WebDriver BiDi JSON Trace，不是 C++ DOMTrace。
- `D:\reverse_ENV\tools\ruyitrace\firefox\firefox.exe` 继续作为 DOMTrace 专用 runtime，由 `tools\ruyitrace\ruyitrace.ps1` 启动。
- DOMTrace CLI 会设置 `MOZ_DOM_TRACE=1` 与 `MOZ_DISABLE_LAUNCHER_PROCESS=1`。Firefox 生成的 `<output>_<PID>.ndjson` 分片会在退出后合并到 `-Output`；`-Limit` 是可选的每进程行数上限。
- `.mcp.json` 与 `.codex/config.toml` 的 `RUYI_FIREFOX_PATH` 已指向本 runtime；`tools\ruyitrace\firefox\` 不再承担 MCP 普通 BiDi 启动，只保留 DOMTrace CLI。

## 维护规则

1. 新 runtime 必须放入 `tools\ruyipage\runtimes\<release>\`，不得覆盖既有目录。
2. 记录 release、asset SHA256、BuildID 和能力验证结果；不能只凭 Firefox 版本号判断兼容性。
3. 普通 BiDi runtime 与 DOMTrace runtime 分开验证、分开切换。
4. 浏览器二进制、profile、Trace 输出和代理凭据不得提交到 Git。
