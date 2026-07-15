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

执行重装前先退出正在使用 DBX MCP 的 Codex 会话。脚本会在 `npm ci` 前检测运行中的 DBX server 并直接报出 PID，避免 Windows 锁定 `better_sqlite3.node` 后留下半安装目录。

## 验证

```powershell
& "D:\reverse_ENV\tools\node22\node.exe" "D:\reverse_ENV\mcp\dbx-mcp\smoke-test.mjs"
```

验证包含 MCP `initialize`、`tools/list` 和 `dbx_*` 工具集检查。普通 Windows 安装默认读取 `%APPDATA%\com.dbx.app\dbx.db`；只有便携版 DBX 才设置 `DBX_DATA_DIR`。
