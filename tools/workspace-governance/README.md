# Workspace Governance

只读审计 `workspace/` 独立仓库、registry、remote、submodule 和禁止入 Git 文件。

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" `
  "D:\reverse_ENV\tools\workspace-governance\audit_workspace.py"
```

只检查单个项目：

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" `
  "D:\reverse_ENV\tools\workspace-governance\audit_workspace.py" `
  --project "qidian"
```

脚本不执行 init、add、commit、push、checkout、clean 或目录移动。`error` 表示 registry/已跟踪内容违反门禁；未建仓项目中的原始证据只报告为 `warning`，供首次提交前清理 staging 边界。

Registry schema 位于 `workspace-projects.schema.json`。审计会先执行 JSON Schema 校验，再核对实际目录和 Git 状态。

普通主仓 clone 不包含 `registry` 项目，默认允许这些本地工作树缺失。对完整逆向环境执行磁盘一致性检查时加 `--require-local`；点名 `--project` 或缺失正式 submodule 仍会失败。
