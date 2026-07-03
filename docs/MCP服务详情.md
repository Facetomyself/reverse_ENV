# MCP 服务详情

所有 MCP 服务通过 `D:\reverse_ENV\.mcp.json` 注册，stdio 模式由 Claude Code 自动管理。

## 服务总览

| 服务 | 版本 | 工具前缀 | 运行时 | 使用前提 |
|------|------|----------|--------|---------|
| `ida-multi-mcp` | 0.1.0 | `idapro_*`, `idalib_*` | Python venv | 无需额外操作 |
| `jadx-ai-mcp` | 6.4.0 | `jadx_*` | Python venv | **先启动 jadx-gui 并加载 APK** |
| `js-reverse-mcp` | 3.0.0 | `js-reverse_*` | Node.js 便携版 | Chrome 浏览器 |
| `ruyi-mcp` | 0.1.0 | `ruyi_*` | Node.js 便携版 + Python venv | ruyipage Firefox 151.0a1 |
| `reqable` | 0.3.2 | `reqable_*` | Python venv (stdio) | Reqable ≥2.20 桌面端 |
| `first-mcp` | 1.0.9 | — | SSE (127.0.0.1:4554) | First GUI 运行中 |

## ida-multi-mcp

- **入口**: `.venv\Scripts\python.exe -m ida_multi_mcp`
- **IDADIR**: `D:\reverse_ENV\resource\portable_win`
- **模式**: stdio
- **核心工具**: `idapro_decompile`, `idapro_analyze_function`, `idapro_xrefs_to`, `idapro_survey_binary`, `idapro_rename` 等约 72 个
- **管理工具**: `idalib_open`, `idalib_close`, `idalib_list`, `list_instances`, `refresh_tools`, `compare_binaries`

### 工作流

```
Claude Code 拉起 ida-multi-mcp (stdio)
  → idalib_open 打开二进制（headless 分析）
  → idapro_* 工具分析
```

无需手动启动 HTTP 服务器。`start.ps1` 用作环境验证。

## jadx-ai-mcp

- **架构**: JADX GUI 插件 (Java, 端口 8650) + Python MCP 服务端 (stdio)
- **插件 JAR**: `tools\jadx\plugins\jadx-ai-mcp-6.4.0.jar`
- **服务端**: `tools\jadx-mcp-server\jadx_mcp_server.py`
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

- **入口**: `tools\node\node.exe js-reverse-mcp\node_modules\js-reverse-mcp\build\src\index.js --cloak`
- **依赖**: CloakBrowser（反检测 Chromium，首次自动下载 ~200MB，已缓存）
- **备选**: 手动 Chromium 152 (`tools\chromium\chrome-win\chrome.exe`) + `--browserUrl http://127.0.0.1:9222`
- **关键选项**:
  - `--cloak` — 反检测 Chromium（源码级指纹补丁: canvas/WebGL/audio/GPU），**默认启用**
  - `--browserUrl http://127.0.0.1:9222` — 连接已运行的 Chromium
  - `--isolated` — 临时隔离浏览器配置文件

### 核心工具

`js-reverse_new_page`, `js-reverse_list_scripts`, `js-reverse_search_in_sources`, `js-reverse_break_on_xhr`, `js-reverse_evaluate_script`, `js-reverse_get_paused_info`, `js-reverse_set_breakpoint_on_text`, `js-reverse_list_network_requests`, `js-reverse_get_request_initiator`, `js-reverse_take_screenshot` 等约 22 个。

> **适用场景：弱检测站点。** 无反检测、无 CF/hCaptcha 等 JS 挑战的站点。

## ruyi-mcp

- **入口**: `tools\node\node.exe ruyi-mcp\build\src\index.js`
- **依赖**: ruyipage Firefox 151.0a1（`C:\Users\mengma\AppData\Local\ruyipage\browsers\`）
- **架构**: Node.js MCP Server → Python 子进程 (JSON-RPC over stdio) → ruyipage (WebDriver BiDi)
- **浏览器**: Firefox 151.0a1 定制版（22 维指纹伪装 + 人类行为模拟 + C++ DOM Trace）

### 核心工具（41 tools，分 12 类）

| 分类 | 工具 | 说明 |
|------|------|------|
| 页面管理 | `ruyi_new_page`, `ruyi_navigate_page`, `ruyi_close_page`, `ruyi_select_page`, `ruyi_list_pages` | 反检测浏览器页面操作，`new_page` 支持 proxy+fingerprint |
| 脚本分析 | `ruyi_list_scripts`, `ruyi_get_script_source`, `ruyi_save_script_source`, `ruyi_search_in_sources` | JS 脚本枚举/源码获取/搜索 |
| 运行时求值 | `ruyi_evaluate_script`, `ruyi_list_console_messages` | 页面 JS 执行 + 控制台日志 |
| 反检测/指纹 | `ruyi_set_fingerprint`, `ruyi_emulate_geolocation`, `ruyi_emulate_timezone`, `ruyi_emulate_locale`, `ruyi_handle_cloudflare` | 22 维指纹伪装 + CF 自动过检 |
| DOM 交互 | `ruyi_dom_select`, `ruyi_dom_get_info`, `ruyi_dom_input`, `ruyi_dom_click` | 元素定位/读写/交互 |
| Session 导出 | `ruyi_export_session` | Cookie+Storage 导出（跨工具桥接） |
| 网络取证 | `ruyi_list_network_requests`, `ruyi_capture_start`, `ruyi_capture_stop`, `ruyi_capture_wait` | 网络请求列表 + 被动抓包 |
| 软断点调试 | `ruyi_set_breakpoint_on_text`, `ruyi_break_on_xhr`, `ruyi_list_breakpoints`, `ruyi_remove_breakpoint` | preload script 注入 debugger |
| 人类模拟 | `ruyi_human_move`, `ruyi_human_click`, `ruyi_human_input` | bezier/windmouse 算法鼠标操作 |
| 指纹追踪 | `ruyi_trace_start`, `ruyi_trace_stop`, `ruyi_trace_get_results` | BiDi 事件 + ruyitrace DOM Hook |
| 网络增强 | `ruyi_set_extra_headers`, `ruyi_set_cache_behavior` | 全局 Headers + 缓存策略 |
| 辅助 | `ruyi_take_screenshot`, `ruyi_clear_site_data`, `ruyi_browser_status`, `ruyi_browser_quit` | 截图/清除状态/状态查询 |

> **所有站点通用。** 反检测/指纹分析/DOM trace/人类模拟等增强能力，无论目标站点反检测强度如何都可用。CF/hCaptcha 等强反检测站点必须使用。

### 与 js-reverse-mcp 的关系

```
Web RE 目标 → 按需求能力选择
  ├── 需要 CDP 完整断点调试 → js-reverse-mcp (Chrome/CDP, ~22 tools)
  ├── 需要反检测/指纹/trace/人类模拟 → ruyi-mcp (Firefox/BiDi, ~41 tools)
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

## .mcp.json 配置

```json
{
  "mcpServers": {
    "ida-multi-mcp": {
      "command": "D:\\reverse_ENV\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ida_multi_mcp"],
      "env": { "IDADIR": "D:\\reverse_ENV\\resource\\portable_win" }
    },
    "jadx-ai-mcp": {
      "command": "D:\\reverse_ENV\\.venv\\Scripts\\python.exe",
      "args": ["D:\\reverse_ENV\\tools\\jadx-mcp-server\\jadx_mcp_server.py"],
      "env": { "JAVA_HOME": "D:\\reverse_ENV\\tools\\jdk" }
    },
    "js-reverse-mcp": {
      "command": "D:\\reverse_ENV\\tools\\node\\node.exe",
      "args": ["D:\\reverse_ENV\\js-reverse-mcp\\node_modules\\js-reverse-mcp\\build\\src\\index.js", "--cloak"]
    },
    "ruyi-mcp": {
      "command": "D:\\reverse_ENV\\tools\\node\\node.exe",
      "args": ["D:\\reverse_ENV\\ruyi-mcp\\build\\src\\index.js"]
    }
  }
}
```

## 新增 MCP 服务时

必须同步：
1. 更新 `.mcp.json`
2. 更新本文档
3. 更新 `CLAUDE.md` 的 MCP 前缀速查表
