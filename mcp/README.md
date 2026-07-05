# MCP 服务目录

所有 MCP (Model Context Protocol) 服务统一放在此目录下。每个 MCP 服务一个子目录。

## 约束

1. **MCP 代码必须在 `mcp/` 下** — 不得散落在根目录或 `tools/` 下
2. **新增 MCP 先在此登记** — 更新下方表格 + `.mcp.json`
3. **配置变更同步 CLAUDE.md** — 路径/版本/前缀变更需更新 `CLAUDE.md` 工具速查表
4. **pip 安装的 MCP 标注来源** — 不在本目录下管理的，标注 pip 包名和安装位置

## MCP 服务清单

| MCP 服务 | 目录 | 运行时 | 管理方式 | 状态 |
|----------|------|--------|---------|------|
| `ida-multi-mcp` | `pip: ida_multi_mcp` | `.venv\Scripts\python.exe -m ida_multi_mcp` | pip (venv) | 活跃 |
| `jadx-ai-mcp` | `mcp\jadx-mcp-server\` | `.venv\Scripts\python.exe jadx_mcp_server.py` | 本地源 | 活跃 |
| `js-reverse-mcp` | `mcp\js-reverse-mcp\` | `powershell tools\chromium\start-js-reverse.ps1` | npm | 活跃 |
| `ruyi-mcp` | `mcp\ruyi-mcp\` | `tools\node\node.exe mcp\ruyi-mcp\build\src\index.js` | npm | 活跃 |
| `reqable` | `mcp\reqable-mcp\` (源) | `.venv\Scripts\reqable-mcp.exe mcp` | pip (venv) | 活跃 |
| `first-mcp` | — (远程) | `http://127.0.0.1:4554/sse` | 外部 SSE | 按需 |

## 配置入口

- 项目 MCP: `.mcp.json` (项目根)
- 用户 MCP: `~/.claude.json` (跨项目)

## 新增 MCP 流程

1. 在 `mcp/` 下创建子目录，放入源码
2. 在 `.mcp.json` 的 `mcpServers` 中添加配置段
3. 在 `CLAUDE.md` 的「MCP 工具前缀」表中添加工具前缀
4. 更新 `docs/MCP服务详情.md` 添加新服务说明
5. 更新本文件的「MCP 服务清单」表
