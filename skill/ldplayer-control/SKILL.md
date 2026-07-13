---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器 RE 实例管理。用于为逆向项目创建独立模拟器实例、启动/停止实例、管理 HTTPS 抓包代理、查看状态和安全清理实例。项目实例按 workspace 项目名隔离，index 0 预留给 MAA，所有写操作拒绝触碰 index 0。
---

# 雷电模拟器 RE 实例管理

`ldplayer-control` 负责管理逆向工程项目使用的 LDPlayer 9 实例。当前采用“模板实例 + 项目实例”的模型：`re-base`、`re-xposed`、`re-stealth` 是长期保留的已验证模板，真实目标 App 使用新的项目实例，从合适模板复制或从备份恢复，不直接污染模板。

## 硬约束

- `Project` 只允许 ASCII 字母、数字、点、下划线、短横线：`^[A-Za-z0-9._-]+$`。
- index 0 是 MAA 保留实例，`re-init.ps1`、`re-proxy.ps1`、`re-destroy.ps1` 和 `ldplayer.ps1` 的写操作都必须拒绝触碰。
- `re-base`、`re-xposed`、`re-stealth` 是模板实例，除升级模块和重新打 verified 备份外，不安装目标 App、不抓目标业务流量。
- 项目实例名必须与 `workspace\<Project>\` 项目名一致；项目实例可以用 `re-init.ps1 -Template <template>` 从模板复制。
- `re-proxy.ps1` 默认端口是 `8080 + instance index`，避免多项目抓包互相抢端口。
- `proxy-off` 只停止当前项目 PID 文件记录的 `mitmdump`，不得全局杀所有 `mitmdump`。
- workspace 产物不随实例删除；`re-destroy.ps1 -Remove` 只删除 LDPlayer VM。
- 备份文件统一放在 `D:\reverse_ENV\storage\ldplayer-backups\`，不纳入 Git。

## 调用链路

新 App 逆向项目的模拟器链路固定如下：

```text
article/INDEX.md 知识库检索
  -> choose template: re-base / re-xposed / re-stealth
  -> re-init.ps1 -Project <Project> -Template <Template>
  -> optional: apk-reverse/scripts/init-ldplayer-re.ps1 -DeviceSerial <ADB>
  -> re-proxy.ps1 -Project <Project> -Action on/off
  -> APK static/dynamic work via apk-reverse / native-reverse
  -> re-backup.ps1 only when the project/template state is worth preserving
  -> re-destroy.ps1 -Project <Project> [-Remove] for disposable project instances
```

职责边界：

| 需求 | 入口 |
|------|------|
| 创建/复制/启动/停止/删除 LDPlayer 实例 | `ldplayer-control` |
| 模板 verified 备份和 `.ldbk` 恢复 | `ldplayer-control` |
| 项目 HTTPS 代理和 flow 文件 | `ldplayer-control` |
| 指定 ADB 设备内 Root / Frida server 重新初始化 | `apk-reverse/scripts/init-ldplayer-re.ps1` |
| APK 解包、静态分析、Frida Hook、重打包 | `apk-reverse` |

## 快速开始

```powershell
# 1. 从已验证模板创建项目实例。默认推荐 re-xposed，强对抗场景用 re-stealth。
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -Template re-xposed

# 2. 开启 HTTPS 抓包，flow 写入 workspace\myapp\mitmproxy_traffic.flow
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

# 3. 查看实例
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1"

# 4. 关闭代理
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off

# 5. 停止实例
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp

# 6. 项目实例坏了就删掉重建，模板坏了才从 verified 备份恢复
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project re-xposed -SourceProject re-xposed -Force
```

## 脚本清单

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `scripts/re-init.ps1` | 创建、复制模板、配置、启动项目实例 | `-Project`, `-Template`, `-Resolution`, `-Cpu`, `-Memory`, `-NoLaunch` |
| `scripts/re-list.ps1` | 查看 LDPlayer 实例并标注 MAA/RE/NONASCII/ORPHAN | `-Project` |
| `scripts/re-proxy.ps1` | 开启或关闭单项目 HTTPS 抓包 | `-Project`, `-Action`, `-ProxyPort` |
| `scripts/re-backup.ps1` | 将模板或项目实例备份为 `.ldbk` | `-Project`, `-Tag`, `-BackupRoot`, `-NoStop` |
| `scripts/re-restore.ps1` | 从 `.ldbk` 恢复到已有实例，按 index 恢复并重命名回目标实例名 | `-Project`, `-SourceProject`, `-BackupFile`, `-BackupRoot`, `-Force` |
| `scripts/re-destroy.ps1` | 停止实例，可选删除 VM | `-Project`, `-Remove`, `-Force` |
| `tools\ldplayer\ldplayer.ps1` | 底层原子操作封装 | `-Action`, `-Index` / `-Name` |

## 实例模型

```text
LDPlayer instances
  [0] MAA reserved instance    -> DO NOT TOUCH
  [1] reverse                  -> seed / legacy RE instance
  [2] re-base                  -> template: root + Frida + CA/proxy readiness
  [3] re-xposed                -> template: re-base + LSPosed + JustTrustMe
  [4] re-stealth               -> template: re-xposed + Hide My Applist + Shamiko
  [5+] myapp                   -> project instance cloned from a template
```

模板分层：

| 模板 | 用途 | 已验证能力 |
|------|------|------------|
| `re-base` | 低干扰快速动态调试 | Android 9 / Root / Kitsune Mask v27.0 / Frida 17.15.3 / mitmproxy CA |
| `re-xposed` | 日常 App 逆向默认环境 | `re-base` + LSPosed v1.9.2 + JustTrustMe v2 |
| `re-stealth` | 需要 Root/模块隐藏的强检测目标 | `re-xposed` + Hide My Applist V3.6.1 + Shamiko v0.7.5 |

模板不要直接用于目标项目。新任务按风险选择模板后复制：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project target-demo -Template re-base
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project target-demo -Template re-xposed
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project target-demo -Template re-stealth
```

`re-list.ps1` 分类规则：

| Type | 含义 | 处理策略 |
|------|------|----------|
| `MAA` | index 0，MAA 保留实例 | 只读查看，不做写操作 |
| `RE` | 名称符合项目命名规则 | 可由本 skill 管理 |
| `NONASCII` | 名称存在但不符合 ASCII 项目名规则 | 不作为托管 RE 项目 |
| `ORPHAN` | 空名或异常实例 | 人工确认后再清理 |

## `re-init.ps1`

创建或复用项目实例，并配置 root、分辨率、CPU 和内存。传 `-Template` 时会复制模板实例；未显式传 `-Resolution`、`-Cpu`、`-Memory` 时保留模板配置。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" `
  -Project myapp -Resolution "1280,720,240" -Cpu 2 -Memory 2048

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" `
  -Project myapp -Template re-xposed

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -NoLaunch
```

执行链路：

```text
validate project name
  -> ldconsole list2
  -> if project exists: reject index 0, launch if stopped
  -> if missing and -Template: ldconsole copy --name <project> --from <template>
  -> if missing without -Template: ldconsole add
  -> ldconsole modify --root 1 --resolution --cpu --memory when creating from scratch or explicit overrides exist
  -> launch unless -NoLaunch
  -> wait for ADB ready
```

## 模块与 LSPosed Scope

模块资产统一放在 `D:\reverse_ENV\tools\android-modules\`，该目录只跟踪 `README.md`，APK/ZIP 本体不进 Git。

| 模块 | 当前用途 |
|------|----------|
| Kitsune Mask v27.0 | 模拟器 Root 管理，当前模板基座 |
| LSPosed v1.9.2 | Zygisk Xposed 框架 |
| JustTrustMe v2 | SSL Pinning 快速绕过模块，`re-xposed` / `re-stealth` 已安装并启用模块本体 |
| Hide My Applist V3.6.1 | App 列表隐藏，`re-stealth` 已安装并启用模块本体 |
| Shamiko v0.7.5 | 当前 Kitsune/Magisk 27001 上已验证可用的 Root 隐藏模块 |
| Shamiko v1.2.5 | 已归档但未用于模板；要求 Magisk Canary > 27005，当前环境安装会失败 |

模板内 LSPosed 模块只启用模块本体，不预设目标 App scope。每个项目复制实例后再按目标包名设置 scope，避免模板全局污染导致定位问题。

## 备份与恢复

verified 模板备份位于 `D:\reverse_ENV\storage\ldplayer-backups\`：

```text
re-base.verified.20260707_104718.ldbk
re-xposed.verified.20260707_104718.ldbk
re-stealth.verified.20260707_104718.ldbk
```

备份模板：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-backup.ps1" -Project re-xposed -Tag verified
```

恢复到同名模板：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project re-xposed -SourceProject re-xposed -Force
```

恢复到临时测试实例时，先创建目标实例，再指定来源：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project restore-test -Template re-base -NoLaunch
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project restore-test -SourceProject re-xposed -Force
```

实测 `ldconsole restore` 会恢复备份内部实例名。`re-restore.ps1` 必须按目标 index 恢复，并在恢复后执行 `rename --index <index> --title <Project>`，否则把 `re-xposed` 备份恢复到临时实例时会产生第二个同名 `re-xposed`。

## `re-proxy.ps1`

对指定项目实例开启或关闭 HTTPS 抓包。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off

# 如需手动指定端口
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on -ProxyPort 8091
```

执行链路：

```text
validate project name
  -> resolve project name to instance index
  -> reject index 0
  -> require instance running
  -> delegate to tools\ldplayer\ldplayer.ps1 proxy-on/proxy-off
```

`proxy-on` 行为：

- 推送 `D:\reverse_ENV\tools\c8750f0d.0` 到模拟器。
- root 后 bind mount CA 到 `/system/etc/security/cacerts`。
- 建立 `adb reverse tcp:<port> tcp:<port>`。
- 设置 Android 全局代理 `127.0.0.1:<port>`。
- 启动项目专属 `mitmdump`，PID 写入 `workspace\<Project>\mitmdump.pid`。
- flow 写入 `workspace\<Project>\mitmproxy_traffic.flow`。

`proxy-off` 行为：

- 清理 Android 全局代理。
- 移除当前端口的 adb reverse。
- 只停止 `workspace\<Project>\mitmdump.pid` 指向的进程。

## `re-destroy.ps1`

停止项目实例，可选删除 LDPlayer VM。

```powershell
# 只停止
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp

# 停止并删除，需要输入项目名确认
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp -Remove

# 非交互删除
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp -Remove -Force
```

安全边界：

- 拒绝 index 0。
- `-Remove` 删除的是 LDPlayer 实例，不删除 `workspace\<Project>\`。
- 非 `-Force` 模式必须输入项目名确认。

## 底层工具

底层封装路径：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action list
```

常用 action：

| Action | 用途 | 关键参数 |
|--------|------|----------|
| `list` | 列出实例 | 无 |
| `status` | 查看实例状态 | `-Index` 或 `-Name` |
| `launch` / `quit` / `reboot` | 启停和重启 | `-Index` 或 `-Name` |
| `copy` | 从模板或源实例复制 | `-Name`, `-From` |
| `install` / `uninstall` / `runapp` | APK 和 App 管理 | `-ApkPath`, `-PackageName` |
| `adb` | 执行 ldconsole adb command | `-Command` |
| `proxy-on` / `proxy-off` | 抓包代理 | `-Index`, `-Project`, `-ProxyPort` |

除 `list/status/add/copy` 外，底层写操作会解析目标实例并拒绝 index 0。

## 本机环境

| 项目 | 值 |
|------|----|
| LDPlayer CLI | `D:\leidian\LDPlayer9\ldconsole.exe` |
| LDPlayer ADB | `D:\leidian\LDPlayer9\adb.exe` |
| 控制脚本 | `D:\reverse_ENV\tools\ldplayer\ldplayer.ps1` |
| mitmdump | `D:\reverse_ENV\.venv\Scripts\mitmdump.exe` |
| mitmproxy CA | `D:\reverse_ENV\tools\c8750f0d.0` |
| Android 模块资产 | `D:\reverse_ENV\tools\android-modules\` |
| LDPlayer 备份 | `D:\reverse_ENV\storage\ldplayer-backups\` |
| workspace | `D:\reverse_ENV\workspace\` |

## 故障排查

| 症状 | 排查 |
|------|------|
| `ERR:invalid_project_name` | 项目名只能用 ASCII 字母、数字、点、下划线、短横线 |
| `ERR:project_resolves_to_index_0_MAA` | 项目名匹配到了 index 0，必须换项目名 |
| `ERR:instance_not_running` | 先执行 `re-init.ps1 -Project <name>` |
| `ERR:template_instance_not_found` | 先确认 `re-base` / `re-xposed` / `re-stealth` 是否存在 |
| `ERR:mitmproxy_ca_not_found` | 确认 `D:\reverse_ENV\tools\c8750f0d.0` 存在 |
| 端口冲突 | 显式传 `-ProxyPort`，或检查旧项目的 `mitmdump.pid` |
| 没有抓到 HTTPS | 检查 CA bind mount、App 是否证书固定、代理是否被 App 绕过 |
| Shamiko 1.2.5 安装失败 | 当前 Kitsune/Magisk 27001 不满足 Magisk Canary > 27005 要求；使用已验证的 Shamiko v0.7.5 |
