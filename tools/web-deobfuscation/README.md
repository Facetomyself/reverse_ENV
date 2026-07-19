# Safe AST runtime

该目录只承载 `web-deobfuscation` 的锁定 Babel 依赖，不是项目主 Node 环境，也不执行目标 JavaScript。

## 固定版本

- Node：`D:\reverse_ENV\tools\node\node.exe` (`20.20.2`)
- `@babel/parser` / `traverse` / `generator` / `types`：`7.29.7`
- 依赖锁：`package-lock.json`

## 安装

```powershell
& "D:\reverse_ENV\tools\node\npm.cmd" `
  --prefix "D:\reverse_ENV\tools\web-deobfuscation" install `
  --cache "D:\reverse_ENV\tools\web-deobfuscation\.npm-cache" `
  --ignore-scripts --no-audit --no-fund
```

`node_modules/` 与 `.npm-cache/` 不进入 Git。CLI 源码位于 `skill/web-deobfuscation/scripts/safe_ast_transform.mjs`，通过本目录的 `package.json` 建立隔离的 module resolution，不向根目录或系统全局安装包。
