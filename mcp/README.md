# MCP 服务目录

所有 MCP (Model Context Protocol) 服务统一放在此目录下。每个 MCP 服务一个子目录。

## 约束

1. **MCP 代码必须在 `mcp/` 下** — 不得散落在根目录或 `tools/` 下
2. **新增 MCP 先在此登记** — 更新下方表格 + `.mcp.json`
3. **配置变更同步规范文档** — 路径/版本/前缀变更需更新 `AGENTS.md` / `CLAUDE.md` 工具速查表、`docs/MCP服务详情.md`
4. **pip 安装的 MCP 标注来源** — 不在本目录下管理的，标注 pip 包名和安装位置
5. **独立 MCP 仓库使用 submodule** — 主仓只固定 gitlink，源码提交、Issue 和发布在对应公开/私有仓库维护

## MCP 服务清单

| MCP 服务 | 目录 | 运行时 | 管理方式 | 状态 |
|----------|------|--------|---------|------|
| `ida-multi-mcp` | `pip: ida_multi_mcp` | `.venv\Scripts\python.exe -m ida_multi_mcp` | pip (venv) | 活跃 |
| `jadx-ai-mcp` | `mcp\jadx-mcp-server\` | `.venv\Scripts\python.exe jadx_mcp_server.py` | 本地源 | 按需，默认不自动初始化 |
| `js-reverse-mcp` | `mcp\js-reverse-mcp\` | `powershell tools\chromium\start-js-reverse.ps1` | npm | 按需，默认不自动初始化 |
| `ruyi-mcp` | `mcp\ruyi-mcp\` | `tools\node\node.exe mcp\ruyi-mcp\build\src\index.js` | [公开 Git submodule](https://github.com/Facetomyself/ruyi-mcp) + npm | 活跃 |
| `dbx` | `mcp\dbx-mcp\` | `tools\node22\node.exe mcp\dbx-mcp\node_modules\@dbx-app\mcp-server\dist\index.js` | npm lock + 隔离 Node.js 22 | 活跃；默认冷启动 |
| `reqable` | `mcp\reqable-mcp\` (源) | `.venv\Scripts\reqable-mcp.exe mcp` | pip (venv) | 按需，默认不自动初始化 |
| `wechat-miniapp-re-mcp` | `mcp\wechat-miniapp-re-mcp\` | `tools\node\node.exe mcp\wechat-miniapp-re-mcp\build\src\index.js` | [Public Git submodule](https://github.com/Facetomyself/wechat-miniapp-re-mcp) + npm | v0.3.1；PR #14/#15/#16 已合入 runner、Review P0 修复与 post-fix live record；99 tests；按需启用 |
| `first-mcp` | — (远程) | `http://127.0.0.1:4554/sse` | 外部 SSE | 按需，默认不自动初始化 |

## 配置入口

- 项目 MCP: `.mcp.json` (项目根，项目级可用声明)
- Claude 全局 MCP / skill: `~/.claude.json` + `~/.claude/skills/` (跨项目，含 `search-layer` / `content-extract` 等全局分层)
- Codex 项目 MCP: `.codex/config.toml` (reverse_ENV 项目启动配置)
- Codex 用户配置: `~/.codex/config.toml` (provider、features、plugins、trust 等个人默认；不放 `D:\reverse_ENV` 专属 MCP)

`jadx-ai-mcp`、`js-reverse-mcp`、`reqable`、`wechat-miniapp-re-mcp`、`first-mcp` 默认不放进自动初始化清单；需要时再临时启用。`wechat-miniapp-re-mcp` 本身可冷握手，WMPF v19977 的完整真实 CDP/semantic gate 已通过，WMPF v20079 的 profile/AOB/hash-binding 与生产 hook attach/detach 也已闭环；动态能力仍依赖目标 runtime，因此继续按需管理。

当前 Codex 项目默认冷启动为 `ida-multi-mcp`、`ruyi-mcp`、`dbx`。

`search-layer` 是全局搜索分级策略（client-native search + Exa + Tavily + Grok 并行），不属于本仓库 `mcp/` 目录，也不写入项目 `.mcp.json`。Claude 全局环境已配置；Codex 侧已迁移本地 skill 副本到 `~/.codex/skills/search-layer`，并完成 `search.py --mode fast` smoke test。

## dbx MCP

- 官方包：`@dbx-app/mcp-server@0.4.29`
- 本地目录：`mcp\dbx-mcp\`
- 运行时：`tools\node22\node.exe` (Node.js 22.23.1 / ABI 127)
- 锁定安装：`package.json` + `package-lock.json`
- 原生依赖：`better-sqlite3 12.11.1`、`keytar 7.9.0`
- 默认数据：`%APPDATA%\com.dbx.app\dbx.db`；便携版才设置 `DBX_DATA_DIR`
- 项目连接：`nas-re-db-postgres`、`nas-re-db-redis`、`nas-re-db-mongodb`、`nas-re-db-mariadb`、`nas-re-db-elasticsearch`；凭据由 NAS / DBX 本地连接存储维护
- 运行边界：`.mcp.json` 与 `.codex/config.toml` 均设置 `DBX_MCP_ALLOW_WRITES=1`、`DBX_MCP_ALLOW_DANGEROUS_SQL=0`
- Claude 权限：`.claude/settings.json` 只拒绝增删连接；Redis 命令、schema、查询、常规写 SQL 与按需 UI 展示正常开放

安装与验证：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\mcp\dbx-mcp\install.ps1"
& "D:\reverse_ENV\tools\node22\node.exe" "D:\reverse_ENV\mcp\dbx-mcp\smoke-test.mjs"
```

安装脚本优先通过 GitHub CLI 拉取 Windows x64 prebuild，写入本地 `.npm-cache\_prebuilds\` 后执行 `npm ci`，避免 GitHub Release 断流触发 `node-gyp` 回退。

SQL 固定按 `dbx_list_connections` → schema/table 描述 → `dbx_execute_query` 执行。写入前先查询目标范围，`UPDATE` / `DELETE` 使用明确 `WHERE` 并在执行后复核；明细查询使用明确列名与 `LIMIT`。不得把 NAS 连接凭据写入提示词、日志或仓库。

## ruyi-mcp submodule

当前公开子仓版本为 `0.1.4`，Python 依赖固定为 `ruyiPage==1.2.54`。
本版保持 57 tools：`windowSize` 仅设置 outer window，`viewport` 独立设置 viewport / DPR，`screenSize` 独立设置 `screen.*` 并回报实际应用结果；`ruyi_select_frame.selector` 可精确区分 `srcdoc` 与同 URL frame。
新标签页统一从 `about:blank` 创建并在首跳前重放 fingerprint，container 创建失败不降级，导航失败会清理未登记 tab；`ruyi_capture_wait` 将单个 `CapturePacket`、`None` 或多包 list 统一为 MCP `packets` 数组。上游取舍与验证证据见 [`ruyi-mcp/docs/upstream-audit-2026-07-18.md`](ruyi-mcp/docs/upstream-audit-2026-07-18.md)。

首次克隆或 submodule 未初始化时：

```powershell
git -C "D:\reverse_ENV" submodule update --init "mcp/ruyi-mcp"
& "D:\reverse_ENV\tools\node\npm.cmd" --prefix "D:\reverse_ENV\mcp\ruyi-mcp" ci
```

主仓日常使用固定在 gitlink 指向的版本；维护者需要跟进公开仓 `main` 时执行：

```powershell
git -C "D:\reverse_ENV" submodule update --remote --merge "mcp/ruyi-mcp"
git -C "D:\reverse_ENV" diff --submodule=log -- "mcp/ruyi-mcp"
```

确认构建和 MCP 调用正常后，再在主仓提交更新后的 gitlink。项目配置显式注入 `RUYI_MCP_PYTHON` 与 `RUYI_FIREFOX_PATH`，入口仍为 `mcp/ruyi-mcp/build/src/index.js`。

Firefox runtime 分层如下：

- 当前 `.mcp.json` / `.codex/config.toml` 已指向 `tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`，作为项目 BiDi runtime。
- 真实 HTTP 认证代理和 percent-encoded 凭据门禁已通过；SOCKS5 因当前供应商无对应产品只完成 offline contract，待有可用供应商时补真实出口门禁。
- `ruyi_trace_start` / `ruyi_trace_stop` / `ruyi_trace_get_results` 是 RuyiPage BiDi JSON Trace，不是 C++ DOMTrace。
- 2026-07-18 上游审计确认 Ruyi Trace 最新可信公开版仍为 `v1.2`；内部 JSCALL / JSVMP / WASM / HTTP / WS 能力已回滚，本轮不替换 trace kernel。
- C++ DOMTrace 继续使用 `tools\ruyitrace\ruyitrace.ps1` 和专用 `tools\ruyitrace\firefox\`。脚本设置 `MOZ_DISABLE_LAUNCHER_PROCESS=1`，将 `<output>_<PID>.ndjson` 分片合并到 `-Output`；`-Limit` 可选。

## wechat-miniapp-re-mcp submodule

Public 子仓提供 `wxmp_*` 工具，用于 PC 微信 WMPF 与 wxapkg 专用逆向。服务采用 stdio + lazy attach，启动时不要求微信、Frida target、GUI 或 SSE。

首次初始化与验证：

```powershell
git -C "D:\reverse_ENV" submodule update --init "mcp/wechat-miniapp-re-mcp" "tools/Gwxapkg"
& "D:\reverse_ENV\tools\node\npm.cmd" --prefix "D:\reverse_ENV\mcp\wechat-miniapp-re-mcp" ci
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\tools\build-gwxapkg.ps1"
& "D:\reverse_ENV\tools\node\npm.cmd" --prefix "D:\reverse_ENV\mcp\wechat-miniapp-re-mcp" run check
```

当前仍按需启用。v0.3.1 已在 v19977 通过 AppService 选择、evaluate、真实 breakpoint、727 trace wrappers、`wx.request`/fetch/XHR hook、Network body/replay、同 session reconnect、detach 与 evidence export；PR #10/#11 分别闭环静态 subprocess workflow 和 v20079 profile/AOB/hash-binding/生产 hook 交叉验证。PR #14 新增可重复 acceptance contract 与 live runner，PR #15 修复当前 xwechat 默认包发现、CDP capability 误报及 Frida/DevTools proxy 异常清理，Node 20/22 CI 均为 99 tests。PR #16 已将 fresh v19977 lifecycle 的 post-fix full-semantic repeat 写入机器可读 acceptance record：所有 required gates 通过、runner 无 errors、lifecycle findings 在 export 前 resolved。第二版本完整 mini-program semantic gate 仍待补齐，详见 `mcp\wechat-miniapp-re-mcp\docs\progress.md`。

## Claude → Codex 迁移约束

1. `.mcp.json` 维护项目级可用 MCP；`.codex/config.toml` 维护 Codex 项目级启动 MCP；`~/.codex/config.toml` 维护 Codex 用户级个人默认。迁移时禁止简单镜像复制到全局层。
2. 项目启动清单只放“冷启动稳定项”；依赖 GUI、浏览器端口、本地 SSE、桌面客户端上报链的服务统一降级为按需配置。
3. 规范名以项目实现为准：`js-reverse-mcp` 是仓库规范名，文档与配置示例统一使用这一名字。
4. 迁移后至少做两类验证：默认 MCP 的真实工具调用验证、按需 MCP 的前置条件验证。

## 新增 MCP 流程

1. 在 `mcp/` 下创建子目录，放入源码
2. 判断该服务属于“默认冷启动”还是“按需启用”
3. 在 `.mcp.json` 的 `mcpServers` 中添加项目级配置段
4. 如需 Codex 在本项目启用，同步 `.codex/config.toml`；只有全局 MCP 才同步 `~/.codex/config.toml`
5. 在 `CLAUDE.md` / `AGENTS.md` 的 MCP 前缀表中添加工具前缀
6. 更新 `docs/MCP服务详情.md` 添加服务说明、前置条件、验证方式
7. 更新本文件的「MCP 服务清单」表
