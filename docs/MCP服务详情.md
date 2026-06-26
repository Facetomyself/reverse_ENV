# MCP 服务详情

所有 MCP 服务通过 `D:\reverse_ENV\.mcp.json` 注册，stdio 模式由 Claude Code 自动管理。

## 服务总览

| 服务 | 版本 | 工具前缀 | 运行时 | 使用前提 |
|------|------|----------|--------|---------|
| `ida-multi-mcp` | 0.1.0 | `idapro_*`, `idalib_*` | Python venv | 无需额外操作 |
| `jadx-ai-mcp` | 6.4.0 | `jadx_*` | Python venv | **先启动 jadx-gui 并加载 APK** |
| `js-reverse-mcp` | 3.0.0 | `js-reverse_*` | Node.js 便携版 | Chrome 浏览器 |

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

- **入口**: `tools\node\node.exe js-reverse-mcp\node_modules\js-reverse-mcp\build\src\index.js`
- **依赖**: Chrome 浏览器
- **关键选项**:
  - `--browserUrl http://127.0.0.1:9222` — 连接已运行的 Chrome
  - `--isolated` — 临时隔离浏览器配置文件
  - `--cloak` — 反检测 Chromium（首次下载 ~200MB）

### 核心工具

`js-reverse_new_page`, `js-reverse_list_scripts`, `js-reverse_search_in_sources`, `js-reverse_break_on_xhr`, `js-reverse_evaluate_script`, `js-reverse_get_paused_info`, `js-reverse_set_breakpoint_on_text`, `js-reverse_list_network_requests`, `js-reverse_get_request_initiator`, `js-reverse_take_screenshot` 等约 17 个。

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
      "args": ["D:\\reverse_ENV\\js-reverse-mcp\\node_modules\\js-reverse-mcp\\build\\src\\index.js"]
    }
  }
}
```

## 新增 MCP 服务时

必须同步：
1. 更新 `.mcp.json`
2. 更新本文档
3. 更新 `CLAUDE.md` 的 MCP 前缀速查表
