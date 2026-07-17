# EPL Source Recovery

易语言 `*.e` / `*.ec` 工程的纯静态源码恢复工具。它不安装易语言，不启动目标工程，不加载支持库，也不执行提取出的资源。

## 组件

| 组件 | 路径 | 边界 |
|------|------|------|
| SafeEplExtractor | `src\SafeEplExtractor\` | 输出文本源码、元数据、调用表和资源清单 |
| EProjectFile v1.9.4 | `upstream\EProjectFile\` | Git submodule，固定 commit `aee36ceea0b63eb5cf83780631dd4d776608cd1e` |
| 安全适配层 | `src\QIQI.EProjectFile.Safe\` | 移除 `OpenEpl.ELibInfo` 和支持库元数据加载，未知名称保留 `_Lib*` 占位符 |
| 精易模块源码 | `assets\jingyi-ec\` | 只读 Git submodule，固定 `11.1.6` commit `73a7c454935541f5fb695a75474471bf8c7057d7` |
| Portable .NET | `D:\reverse_ENV\tools\dotnet\dotnet.exe` | 10.0.302，本地复制并由根仓忽略 |

## 初始化

```powershell
git -C "D:\reverse_ENV" submodule update --init "tools/epl-source-recovery/upstream/EProjectFile" "tools/epl-source-recovery/assets/jingyi-ec"
```

## 使用

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\tools\epl-source-recovery\run.ps1" `
  -InputPath "D:\reverse_ENV\workspace\<project>\sample\target.e" `
  -OutputPath "D:\reverse_ENV\workspace\<project>\extracted"
```

仅构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\tools\epl-source-recovery\run.ps1" -BuildOnly
```

## 精易模块归档

- 归档的是公开源码仓的 `精易模块11.1.6.e`，不是从具体逆向样本中剥离的副本。
- 文件 SHA-256：`2b6ea71d3d56031e266020fbb695b0615839461fcb19a5f3d3389f44c236f8ca`。
- 静态解析：106 类、3556 方法、2621 常量、91 个资源、0 个方法解析错误。
- 资源中未发现 PE/ELF magic 或可执行脚本扩展；Defender `1.455.176.0` 扫描源工程与提取资源均为 no threats。
- submodule 内 6 个历史 `*.e` 文件均完成静态解析和整仓 Defender 扫描：总方法解析错误 0，PE/ELF magic 0，可执行或脚本扩展 0；汇总见 `references\jingyi-archive-audit.json`。
- `.e` 文件仍按不可信第三方源码处理，只允许静态读取；不要在宿主机编译、运行或加载其支持库。

详细来源和取舍见 `references\provenance.md`，整套工具与 portable .NET 的 Defender 结果见 `references\security-audit.json`。
