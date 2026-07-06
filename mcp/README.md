# MCP 服务目录

所有 MCP (Model Context Protocol) 服务统一放在此目录下。每个 MCP 服务一个子目录。

## 约束

1. **MCP 代码必须在 `mcp/` 下** — 不得散落在根目录或 `tools/` 下
2. **新增 MCP 先在此登记** — 更新下方表格 + `.mcp.json`
3. **配置变更同步规范文档** — 路径/版本/前缀变更需更新 `AGENTS.md` / `CLAUDE.md` 工具速查表、`docs/MCP服务详情.md`
4. **pip 安装的 MCP 标注来源** — 不在本目录下管理的，标注 pip 包名和安装位置

## MCP 服务清单

| MCP 服务 | 目录 | 运行时 | 管理方式 | 状态 |
|----------|------|--------|---------|------|
| `ida-multi-mcp` | `pip: ida_multi_mcp` | `.venv\Scripts\python.exe -m ida_multi_mcp` | pip (venv) | 活跃 |
| `jadx-ai-mcp` | `mcp\jadx-mcp-server\` | `.venv\Scripts\python.exe jadx_mcp_server.py` | 本地源 | 按需，默认不自动初始化 |
| `js-reverse-mcp` | `mcp\js-reverse-mcp\` | `powershell tools\chromium\start-js-reverse.ps1` | npm | 按需，默认不自动初始化 |
| `ruyi-mcp` | `mcp\ruyi-mcp\` | `tools\node\node.exe mcp\ruyi-mcp\build\src\index.js` | npm | 活跃 |
| `reqable` | `mcp\reqable-mcp\` (源) | `.venv\Scripts\reqable-mcp.exe mcp` | pip (venv) | 按需，默认不自动初始化 |
| `first-mcp` | — (远程) | `http://127.0.0.1:4554/sse` | 外部 SSE | 按需，默认不自动初始化 |

## 配置入口

- 项目 MCP: `.mcp.json` (项目根，项目级可用声明)
- Claude 全局 MCP / skill: `~/.claude.json` + `~/.claude/skills/` (跨项目，含 `search-layer` / `content-extract` 等全局分层)
- Codex 用户 MCP: `~/.codex/config.toml` (默认冷启动配置)

`jadx-ai-mcp`、`js-reverse-mcp`、`reqable`、`first-mcp` 都依赖额外前置条件，默认不放进自动初始化清单；需要时再临时加入配置。

`search-layer` 是全局搜索分级策略（client-native search + Exa + Tavily + Grok 并行），不属于本仓库 `mcp/` 目录，也不写入项目 `.mcp.json`。Claude 全局环境已配置；Codex 侧已迁移本地 skill 副本到 `~/.codex/skills/search-layer`，并完成 `search.py --mode fast` smoke test。

## Claude → Codex 迁移约束

1. `.mcp.json` 维护项目级可用 MCP；`~/.codex/config.toml` 维护 Codex 用户级默认启动 MCP。迁移时禁止简单镜像复制。
2. 默认启动清单只放“冷启动稳定项”；依赖 GUI、浏览器端口、本地 SSE、桌面客户端上报链的服务统一降级为按需配置。
3. 规范名以项目实现为准：`js-reverse-mcp` 是仓库规范名，文档与配置示例统一使用这一名字。
4. 迁移后至少做两类验证：默认 MCP 的真实工具调用验证、按需 MCP 的前置条件验证。

## 新增 MCP 流程

1. 在 `mcp/` 下创建子目录，放入源码
2. 判断该服务属于“默认冷启动”还是“按需启用”
3. 在 `.mcp.json` 的 `mcpServers` 中添加项目级配置段
4. 如需 Codex 默认启用，再同步 `~/.codex/config.toml`
5. 在 `CLAUDE.md` / `AGENTS.md` 的 MCP 前缀表中添加工具前缀
6. 更新 `docs/MCP服务详情.md` 添加服务说明、前置条件、验证方式
7. 更新本文件的「MCP 服务清单」表
