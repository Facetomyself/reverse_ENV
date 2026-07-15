# MCP 服务详情

项目级 MCP 服务通过 `D:\reverse_ENV\.mcp.json` 声明，Codex 项目级启动配置位于 `D:\reverse_ENV\.codex\config.toml`，stdio 模式由 AI client 按配置拉起。Codex 用户级 `~/.codex/config.toml` 只保留 provider、features、plugins、trust 等个人默认；Claude 全局 MCP 位于 `~/.claude.json`。MCP 源码统一在 `mcp/` 目录下，清单见 `mcp/README.md`；`mcp/ruyi-mcp` 由公开 Git submodule 提供。

## Claude → Codex 正式迁移规则

1. **区分配置层级**
   - `.mcp.json`：项目级可用 MCP 声明
   - `.codex/config.toml`：Codex 项目级启动配置
   - `~/.codex/config.toml`：Codex 用户级个人默认，不放 `D:\reverse_ENV` 专属 MCP
   - `~/.claude.json`：Claude 全局 MCP 配置
   - `search-layer` / `content-extract`：全局搜索/提取分级策略，不写入项目 `.mcp.json`
   - Codex `search-layer`：本地 skill 副本位于 `~/.codex/skills/search-layer`，已通过 `search.py --mode deep --intent resource` 三源 smoke test（Exa + Tavily + Grok）
2. **默认冷启动只放稳定项**
   - 进入项目时必须能立即握手成功、无 GUI/浏览器/外部服务前置条件
   - 当前默认冷启动建议仅保留 `ida-multi-mcp`、`ruyi-mcp`
3. **有前置条件的一律按需启用**
   - `jadx-ai-mcp`：依赖 `jadx-gui` + 已加载 APK
   - `js-reverse-mcp`：依赖浏览器调试端口或包装脚本拉起浏览器
   - `reqable`：依赖 Reqable 桌面端与本地上报链
   - `wechat-miniapp-re-mcp`：stdio 可冷握手；真实 WMPF 动态语义门禁完成前按需启用
   - `first-mcp`：依赖 First GUI 与本地 SSE
4. **规范名统一**
   - Web CDP 调试 MCP 的项目规范名为 `js-reverse-mcp`
   - 不再把 `jsreverser-mcp` 作为项目文档、项目配置、工具前缀表中的正式名称
5. **迁移完成判定**
   - Codex 启动无默认 MCP 握手噪音
   - 至少一个默认冷启动 MCP 完成真实工具调用验证
   - 每个按需 MCP 的前置条件、启用方式、验证方法都已写明

## 服务总览

| 服务 | 版本 | 工具前缀 | 运行时 | 使用前提 |
|------|------|----------|--------|---------|
| `ida-multi-mcp` | 0.1.0 | `survey_binary`, `decompile`, `analyze_function`, `idalib_*` 等 | Python venv | 无需额外操作 |
| `jadx-ai-mcp` | 6.4.0 | `jadx_*` | Python venv | **先启动 jadx-gui 并加载 APK**；按需手动启用，默认不自动初始化 |
| `js-reverse-mcp` | 3.0.0 | `js-reverse_*` | Node.js 便携版 | Chrome 浏览器；按需手动启用，默认不自动初始化 |
| `ruyi-mcp` | 0.1.1 | `ruyi_*` | Node.js 便携版 + Python venv (`ruyiPage==1.2.46`) | 已初始化公开 submodule；Firefox runtime 按 BiDi / DOMTrace 分层 |
| `reqable` | 0.3.2 | `reqable_*` | Python venv (stdio) | Reqable ≥2.20 桌面端；按需手动启用，默认不自动初始化 |
| `wechat-miniapp-re-mcp` | 0.3.0 | `wxmp_*` | Node.js 便携版 + lazy Frida + Gwxapkg adapter | stdio 可冷握手；真实 WMPF 动态语义门禁完成前按需启用 |
| `first-mcp` | 1.0.9 | — | SSE (127.0.0.1:4554) | First GUI 运行中；按需手动启用，默认不自动初始化 |

## ida-multi-mcp

- **入口**: `.venv\Scripts\python.exe -m ida_multi_mcp`
- **IDADIR**: `D:\reverse_ENV\resource\portable_win`
- **模式**: stdio
- **核心工具**: `survey_binary`, `decompile`, `analyze_function`, `xrefs_to`, `rename` 等 44 个 proxied IDA tools
- **管理工具**: `idalib_open`, `idalib_close`, `idalib_list`, `idalib_status`, `list_instances`, `refresh_tools`, `compare_binaries`, `decompile_to_file`

### 工作流

```
MCP client 拉起 ida-multi-mcp (stdio)
  → idalib_open 打开二进制（headless 分析）
  → 记录 instance_id
  → survey_binary / analyze_function / decompile 等工具分析
```

无需手动启动独立 HTTP 服务器。`start.ps1` 用作环境验证；worker HTTP/registry 是 ida-multi-mcp 内部实现细节。

## jadx-ai-mcp

- **架构**: JADX GUI 插件 (Java, 端口 8650) + Python MCP 服务端 (stdio)
- **插件 JAR**: `tools\jadx\plugins\jadx-ai-mcp-6.4.0.jar`
- **服务端**: `mcp\jadx-mcp-server\jadx_mcp_server.py`
- **依赖**: fastmcp, httpx, requests（已安装在 venv）

### 工作流

```
1. tools\jadx-gui.cmd 启动 jadx-gui（自动加载插件，监听 8650）
2. 在 GUI 中打开目标 APK
3. Claude Code 拉起 jadx_mcp_server.py (stdio)
4. 服务端通过 HTTP ↔ JADX 插件通信
5. jadx_* 工具可用
```

⚠️ 必须先启动 jadx-gui 并加载 APK，否则健康检查报 `Connection refused`。

## js-reverse-mcp

- **入口**: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\chromium\start-js-reverse.ps1`
- **默认模式**: 包装脚本启动系统 Chrome / bundled Chromium，并通过 `--browserUrl http://127.0.0.1:9222` 连接 js-reverse-mcp
- **强反检测模式**: 手动传 `-Cloak`，包装脚本改用 js-reverse-mcp `--cloak` 启动 CloakBrowser
- **关键选项**:
  - `--browserUrl http://127.0.0.1:9222` — 默认路径，连接已运行的 Chromium/Chrome
  - `--cloak` — CloakBrowser 反检测 Chromium（源码级指纹补丁: canvas/WebGL/audio/GPU），仅在 `start-js-reverse.ps1 -Cloak` 时启用
  - `--isolated` — 临时隔离浏览器配置文件

### 核心工具

`js-reverse_new_page`, `js-reverse_list_scripts`, `js-reverse_search_in_sources`, `js-reverse_break_on_xhr`, `js-reverse_evaluate_script`, `js-reverse_get_paused_info`, `js-reverse_set_breakpoint_on_text`, `js-reverse_list_network_requests`, `js-reverse_get_request_initiator`, `js-reverse_take_screenshot` 等约 22 个。

> **适用场景：弱检测站点。** 无反检测、无 CF/hCaptcha 等 JS 挑战的站点。

## ruyi-mcp

- **源码**: 公开 submodule [`Facetomyself/ruyi-mcp`](https://github.com/Facetomyself/ruyi-mcp)，本地路径 `mcp\ruyi-mcp`
- **初始化**: `git submodule update --init mcp/ruyi-mcp`，随后执行 `tools\node\npm.cmd --prefix mcp\ruyi-mcp ci`
- **入口**: `tools\node\node.exe mcp\ruyi-mcp\build\src\index.js`
- **Python**: 项目配置注入 `RUYI_MCP_PYTHON=D:\reverse_ENV\.venv\Scripts\python.exe`
- **版本**: `ruyi-mcp 0.1.1`，依赖固定为 `ruyiPage==1.2.46`
- **当前 Firefox 配置**: `RUYI_FIREFOX_PATH=D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`
- **Firefox BuildID**: `20260702113527`；`tools\ruyitrace\firefox\` 仅保留给 DOMTrace CLI
- **架构**: Node.js MCP Server → Python 子进程 (JSON-RPC over stdio) → ruyipage (WebDriver BiDi)
- **浏览器**: Firefox 151.0a1 定制版（22 维指纹伪装 + 人类行为模拟）；C++ DOMTrace 由独立 runtime 和 CLI 提供

### 核心工具（56 tools，分 15 类）

| 分类 | 工具 | 说明 |
|------|------|------|
| 页面管理 | `ruyi_new_page`, `ruyi_navigate_page`, `ruyi_close_page`, `ruyi_select_page`, `ruyi_list_pages`, `ruyi_list_frames`, `ruyi_select_frame` | 反检测浏览器页面/iframe 操作，`new_page` 支持 proxy+fingerprint |
| 脚本分析 | `ruyi_list_scripts`, `ruyi_get_script_source`, `ruyi_save_script_source`, `ruyi_search_in_sources` | JS 脚本枚举/源码获取/搜索 |
| 运行时求值 | `ruyi_evaluate_script`, `ruyi_list_console_messages` | 页面 JS 执行 + 控制台日志 |
| 反检测/指纹 | `ruyi_set_fingerprint`, `ruyi_emulate_geolocation`, `ruyi_emulate_timezone`, `ruyi_emulate_locale`, `ruyi_emulate_useragent`, `ruyi_set_proxy`, `ruyi_handle_cloudflare` | 22 维指纹伪装 + CF 自动过检；proxy 必须在 `new_page` 时设置 |
| DOM 交互 | `ruyi_dom_select`, `ruyi_dom_get_info`, `ruyi_dom_input`, `ruyi_dom_click` | 元素定位/读写/交互 |
| Session 导出 | `ruyi_export_session` | Cookie+Storage 导出（跨工具桥接） |
| Cookie 管理 | `ruyi_get_cookies`, `ruyi_set_cookies`, `ruyi_delete_cookies` | Cookie 读取/写入/删除 |
| 网络取证 | `ruyi_list_network_requests`, `ruyi_capture_start`, `ruyi_capture_stop`, `ruyi_capture_wait`, `ruyi_get_request_initiator` | 网络请求列表、被动抓包、fetch/XHR 调用栈采样 |
| 请求/响应拦截 | `ruyi_intercept_requests`, `ruyi_intercept_responses`, `ruyi_intercept_wait`, `ruyi_intercept_stop` | BiDi network intercept 队列式消费 |
| WebSocket | `ruyi_websocket_inject`, `ruyi_get_websocket_messages` | 注入 WebSocket Proxy 并采集 send/receive 消息 |
| 软断点调试 | `ruyi_set_breakpoint_on_text`, `ruyi_break_on_xhr`, `ruyi_list_breakpoints`, `ruyi_remove_breakpoint`, `ruyi_list_preload_scripts` | preload script + Proxy 软断点 |
| 人类模拟 | `ruyi_human_move`, `ruyi_human_click`, `ruyi_human_input` | bezier/windmouse 算法鼠标操作 |
| 指纹追踪 | `ruyi_trace_start`, `ruyi_trace_stop`, `ruyi_trace_get_results` | RuyiPage/WebDriver BiDi JSON Trace；不是 C++ DOMTrace |
| 网络增强 | `ruyi_set_extra_headers`, `ruyi_set_cache_behavior` | 全局 Headers + 缓存策略 |
| 辅助 | `ruyi_take_screenshot`, `ruyi_clear_site_data`, `ruyi_browser_status`, `ruyi_browser_quit` | 截图/清除状态/状态查询 |

> **所有站点通用。** 反检测、指纹分析、BiDi Trace、人类模拟等增强能力无论目标站点反检测强度如何都可用。CF/hCaptcha 等强反检测站点必须使用。

### BiDi Trace 与 DOMTrace 边界

- `ruyi_trace_*` 操作 RuyiPage Tracer，结果和 `outputFile` 都是 JSON；launch/runtime Trace entries 增长、stop 后冻结已通过回归。
- `tools\ruyitrace\ruyitrace.ps1` 操作 Firefox C++ DOM Hook，输出 NDJSON，和 MCP 的 `ruyi_trace_*` 不是同一条链路。
- DOMTrace CLI 设置 `MOZ_DOM_TRACE=1`、`MOZ_DISABLE_LAUNCHER_PROCESS=1`。Firefox 生成的 `<output>_<PID>.ndjson` 会在退出后合并到 `-Output`；`-Limit` 为可选的每进程行数上限。
- `151-proxy` 没有 `RUYI_DOMTRACE.txt` marker，实际验证也不生成 DOMTrace。`tools\ruyitrace\firefox\` 因此继续作为 DOMTrace 专用 runtime。
- 真实 HTTP 认证代理与 percent-encoded 凭据已通过；SOCKS5 因当前供应商无产品只完成 offline contract，待有可用供应商时补真实出口门禁。

### 与 js-reverse-mcp 的关系

```
Web RE 目标 → 按需求能力选择
  ├── 需要 CDP 完整断点调试 → js-reverse-mcp (Chrome/CDP, ~22 tools)
  ├── 需要反检测/指纹/BiDi Trace/人类模拟 → ruyi-mcp (Firefox/BiDi, 56 tools)
  └── 两者都需要 → ruyi 过检 + export_session → js-reverse 调试
```

两者**工具接口对齐、工作流对等**（Observe → Capture → Rebuild → Patch → DeepDive），但底层浏览器/协议不同。**同一任务中不得混用两个前缀的工具**，除非通过 `ruyi_export_session` 显式桥接。

## reqable (reqable-mcp)

- **入口**: `.venv\Scripts\reqable-mcp.exe mcp`
- **架构**: FastMCP (Python stdio) + 内嵌 ingest HTTP server (127.0.0.1:18765)
- **依赖**: `mcp>=1.2.0`, `pydantic>=2.0.0`（已装在 venv）
- **前提**: 安装 Reqable ≥2.20 桌面端，配置上报服务器

### Reqable 配置

1. Reqable 菜单 → **工具** → **上报服务器** → 添加配置
2. 填写：
   - 名称: `reqable-mcp-local`
   - 匹配规则: `*`
   - 服务器 URL: `http://127.0.0.1:18765/report`
   - 压缩: `无`

### 工作流

```
Reqable 抓包 → HAR 推送 18765/report → reqable-mcp ingest → SQLite 存储
                                                              ↓
Claude Code ← stdio ← FastMCP ← reqable_* 工具查询
```

### 核心工具（17 tools）

| 类别 | 工具 | 说明 |
|------|------|------|
| 状态 | `ingest_status`, `health_report` | 服务状态 / 数据质量报告 |
| HTTP | `list_requests`, `get_request`, `search_requests` | 请求列表/详情/关键字搜索 |
| 分析 | `get_domains`, `analyze_api`, `generate_code` | 域名统计/API 结构推断/代码生成 |
| WebSocket | `list_websocket_sessions`, `list_active_websocket_sessions`, `get_websocket_session`, `tail_websocket_messages`, `search_websocket_messages`, `analyze_websocket_session`, `export_websocket_session_raw`, `repair_websocket_messages` | WS 会话管理/消息搜索/分析与导出 |
| 导入 | `import_har` | HAR 文件手动导入（实时推送的兜底方案） |

### 数据位置

- 数据库: `%APPDATA%\reqable-mcp\requests.db`（SQLite）
- 保留期: 默认 7 天（`REQABLE_RETENTION_DAYS`）

## wechat-miniapp-re-mcp

- **源码**: Private submodule `mcp\wechat-miniapp-re-mcp\`
- **入口**: `tools\node\node.exe mcp\wechat-miniapp-re-mcp\build\src\index.js`
- **模式**: stdio；目标发现、Frida、WMPF bridge 和 Gwxapkg 均按调用懒加载
- **工具前缀**: `wxmp_*`（53 tools）
- **Workspace**: `workspace\<项目名>\wechat-miniapp\`
- **静态后端**: `tools\Gwxapkg-runtime\gwxapkg.exe`
- **Profile**: clean-room schema；generated candidate 必须匹配目标 WMPF version/module hash，并通过 `wxmp_profile_promote` 记录 review evidence 后才可注入；本地兼容测试可通过 `WXMP_LEGACY_PROFILE_DIR` 读取外部 profile，不复制进子仓
- **状态**: PR #6 已合入且 Node 20/22 CI 绿色；cold-start / 53-tool contract / mock bridge / WMPF 19977 Frida attach 与 runtime CDP/reconnect 证据已验证；v0.3.0 已补 capability 语义探测、context probe、context-scoped request/script、XHR hook、clean-room profile/AOB 默认接入、evidence 事件/字节容量治理和 schema validation，breakpoint hit、非零 trace/hook event、replay 与第二版本 profile 仍待真实门禁

按需 Codex 配置见 `.codex/config.toml` 注释段。完整 Plan 与完成度见子仓 `docs/plan.md`、`docs/progress.md`。

## first-mcp（Legacy）

- **模式**: 远程 SSE (`http://127.0.0.1:4554/sse`)
- **前提**: 先启动 `First GUI`，并确认本地 SSE 服务已监听 `127.0.0.1:4554`
- **启用策略**: 按需手动启用，默认不加入 Codex / Claude 的自动初始化清单

### 原因

`first-mcp` 依赖外部 GUI 与本地 SSE 服务。若在工作区启动时直接初始化，而 `First GUI` 尚未运行，MCP client 会在握手阶段报连接失败。为了避免启动噪音，默认从自动初始化配置中移除；只有在需要微信小程序调试时再临时加入配置。

新工作流优先使用 `wechat-miniapp-re-mcp`；First 仅保留人工 GUI fallback 和外部 profile 兼容测试参考。

## .mcp.json 配置

```json
{
  "mcpServers": {
    "ida-multi-mcp": {
      "command": "D:\\reverse_ENV\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ida_multi_mcp"],
      "env": { "IDADIR": "D:\\reverse_ENV\\resource\\portable_win" }
    },
    "ruyi-mcp": {
      "command": "D:\\reverse_ENV\\tools\\node\\node.exe",
      "args": ["D:\\reverse_ENV\\mcp\\ruyi-mcp\\build\\src\\index.js"],
      "env": {
        "RUYI_MCP_PYTHON": "D:\\reverse_ENV\\.venv\\Scripts\\python.exe",
        "RUYI_FIREFOX_PATH": "D:\\reverse_ENV\\tools\\ruyipage\\runtimes\\151-proxy\\firefox\\firefox.exe"
      }
    }
  }
}
```

## Codex 项目启动配置

```toml
[mcp_servers.ida-multi-mcp]
command = "D:\\reverse_ENV\\.venv\\Scripts\\python.exe"
args = ["-m", "ida_multi_mcp"]

[mcp_servers.ida-multi-mcp.env]
IDADIR = "D:\\reverse_ENV\\resource\\portable_win"

[mcp_servers.ruyi-mcp]
command = "D:\\reverse_ENV\\tools\\node\\node.exe"
args = ["D:\\reverse_ENV\\mcp\\ruyi-mcp\\build\\src\\index.js"]

[mcp_servers.ruyi-mcp.env]
RUYI_MCP_PYTHON = "D:\\reverse_ENV\\.venv\\Scripts\\python.exe"
RUYI_FIREFOX_PATH = "D:\\reverse_ENV\\tools\\ruyipage\\runtimes\\151-proxy\\firefox\\firefox.exe"

# On-demand examples:
# [mcp_servers.jadx-ai-mcp]
# command = "D:\\reverse_ENV\\.venv\\Scripts\\python.exe"
# args = ["D:\\reverse_ENV\\mcp\\jadx-mcp-server\\jadx_mcp_server.py"]
#
# [mcp_servers.js-reverse-mcp]
# command = "powershell"
# args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "D:\\reverse_ENV\\tools\\chromium\\start-js-reverse.ps1"]
```

## 迁移后验证

1. 在 `D:\reverse_ENV` 启动 Codex，确认项目 MCP 无握手报错。
2. 验证项目冷启动 MCP：
   - `ida-multi-mcp`：至少完成一次 `idalib_open` + `survey_binary` 或同等级真实调用
   - `ruyi-mcp`：至少完成一次 `ruyi_new_page` 或同等级真实调用
3. 验证按需 MCP：
   - 先满足前置条件，再临时加入配置并单独测试
4. 若只做到“启动不报错”，不能算迁移完成。

## 新增 MCP 服务时

必须同步：
1. 更新 `.mcp.json`
2. 如需 Codex 在 reverse_ENV 项目冷启动，更新 `.codex/config.toml`
3. 如属 Claude 全局 MCP，更新 `~/.claude.json` 并在项目文档标明“全局分层，不进项目 `.mcp.json`”
4. 更新 `mcp/README.md` 服务清单
5. 更新本文档，写清前置条件、启用方式、验证方式
6. 更新 `AGENTS.md` / `CLAUDE.md` 的 MCP 前缀速查表 + 工具速查表
