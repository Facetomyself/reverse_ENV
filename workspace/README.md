# 逆向项目工作区

`workspace/` 是独立项目工作树容器，不是一个整体 Git 仓库。项目状态、remote、可见性、Git 根和接入方式只认 [`docs/workspace-projects.yaml`](../docs/workspace-projects.yaml)，不在本文件维护易过期的手工清单。

## 固定规则

1. 新项目建立在 `workspace/<项目名>/`，待分析二进制、抓包和运行产物不得散落在 `workspace/` 根目录。
2. 非空正式项目默认建立独立 Private GitHub 仓库；现有 Public 仓保持实际可见性，不自动改权。
3. `submodule` 仅用于正式 spec、公共工具或真实代码依赖；目标型逆向项目使用 `registry`，不进入主仓默认克隆链。
4. 项目仓只提交 README、AGENTS、三件套、原创源码、测试、脱敏 fixture 和 evidence manifest。
5. APK/IPA/SO、IDA 数据库、HAR/PCAP/flow、Cookie、凭据、浏览器 profile、解包与反编译全集只留本地，不使用 Git LFS 绕过门禁。
6. `deferred-active` 项目只读审计，禁止 checkout/reset/clean/stash/rebase、移动目录、修改 remote 或吸收 Git 目录。

## 生命周期

- `planned`：已登记但尚未建仓。
- `active`：独立仓正常维护。
- `deferred-active`：正在运行或存在受保护改动，迁移延期。
- `archived`：保留远端历史，不再日常开发。
- `excluded`：空目录、一次性测试或外部上游工作树，不创建自有仓库。

建仓就绪度由 registry 的 `readiness` 表示：`ready`、`existing`、`deferred`、`curation-required`、`incomplete`、`excluded`。

## 审计

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" `
  "D:\reverse_ENV\tools\workspace-governance\audit_workspace.py"
```

新增、删除、重命名、建仓或变更 remote/submodule 后必须同步 registry 并重新审计。项目完成后，将可复用知识提炼到 `article/` 子仓；项目本身继续由独立仓维护，不移动到未纳入 Git 的 `storage/` 代替归档。
