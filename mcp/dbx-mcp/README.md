# DBX MCP 本地运行目录

此目录固定安装官方 `@dbx-app/mcp-server@0.4.29`，使用 `tools\node22\node.exe` 运行，与项目现有 Node.js 20 runtime 隔离。

## 安装

```powershell
Push-Location "D:\reverse_ENV\mcp\dbx-mcp"
& "D:\reverse_ENV\tools\node22\npm.cmd" install --package-lock-only --ignore-scripts
Pop-Location
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\mcp\dbx-mcp\install.ps1"
```

`install.ps1` 会依据 `package-lock.json` 预取 `better-sqlite3` 与 `keytar` 的 Windows x64 原生资产，写入本目录的 `.npm-cache\_prebuilds\`，随后执行锁定安装与 native addon 加载检查。

执行重装前先退出正在使用 DBX MCP 的 Claude / Codex 会话。脚本会在 `npm ci` 前检测运行中的 DBX server 并直接报出 PID，避免 Windows 锁定 `better_sqlite3.node` 后留下半安装目录。

## 项目使用约束

- Claude 从项目 `.mcp.json` 启动，Codex 从 `.codex/config.toml` 启动；二者统一使用本目录依赖和 `tools\node22\node.exe`。
- 固定查询连接 `nas-re-db-postgres`，默认数据库 `re_db`；连接参数和凭据由 NAS / DBX 本地连接存储维护。
- 两端设置 `DBX_MCP_ALLOW_WRITES=1` 和 `DBX_MCP_ALLOW_DANGEROUS_SQL=0`，允许常规 `INSERT`、带明确 `WHERE` 的 `UPDATE` / `DELETE`，继续拦截危险 SQL。
- Claude 项目权限拒绝 `dbx_add_connection`、`dbx_remove_connection`、`dbx_execute_redis_command`；连接变更不经 MCP 完成。
- SQL 执行前先确认连接与 schema；写入前查询目标范围，执行后复核影响结果；明细查询使用明确列名和 `LIMIT`，UI 工具只在用户要求时调用。

## 验证

```powershell
& "D:\reverse_ENV\tools\node22\node.exe" "D:\reverse_ENV\mcp\dbx-mcp\smoke-test.mjs"
```

验证包含 MCP `initialize`、`tools/list` 和 `dbx_*` 工具集检查。普通 Windows 安装默认读取 `%APPDATA%\com.dbx.app\dbx.db`；只有便携版 DBX 才设置 `DBX_DATA_DIR`。
