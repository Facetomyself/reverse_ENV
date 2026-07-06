---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器 RE 实例管理。用于为逆向项目创建独立模拟器实例、启动/停止实例、管理 HTTPS 抓包代理、查看状态和安全清理实例。项目实例按 workspace 项目名隔离，index 0 预留给 MAA，所有写操作拒绝触碰 index 0。
---

# 雷电模拟器 RE 实例管理

`ldplayer-control` 负责管理逆向工程项目使用的 LDPlayer 9 实例。每个项目一个模拟器实例，实例名必须与 `workspace\<Project>\` 的项目名一致。

## 硬约束

- `Project` 只允许 ASCII 字母、数字、点、下划线、短横线：`^[A-Za-z0-9._-]+$`。
- index 0 是 MAA 保留实例，`re-init.ps1`、`re-proxy.ps1`、`re-destroy.ps1` 和 `ldplayer.ps1` 的写操作都必须拒绝触碰。
- `re-proxy.ps1` 默认端口是 `8080 + instance index`，避免多项目抓包互相抢端口。
- `proxy-off` 只停止当前项目 PID 文件记录的 `mitmdump`，不得全局杀所有 `mitmdump`。
- workspace 产物不随实例删除；`re-destroy.ps1 -Remove` 只删除 LDPlayer VM。

## 快速开始

```powershell
# 1. 创建或启动项目实例
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

# 2. 开启 HTTPS 抓包，flow 写入 workspace\myapp\mitmproxy_traffic.flow
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

# 3. 查看实例
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1"

# 4. 关闭代理
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off

# 5. 停止实例
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp
```

## 脚本清单

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `scripts/re-init.ps1` | 创建、配置、启动项目实例 | `-Project`, `-Resolution`, `-Cpu`, `-Memory`, `-NoLaunch` |
| `scripts/re-list.ps1` | 查看 LDPlayer 实例并标注 MAA/RE/NONASCII/ORPHAN | `-Project` |
| `scripts/re-proxy.ps1` | 开启或关闭单项目 HTTPS 抓包 | `-Project`, `-Action`, `-ProxyPort` |
| `scripts/re-destroy.ps1` | 停止实例，可选删除 VM | `-Project`, `-Remove`, `-Force` |
| `tools\ldplayer\ldplayer.ps1` | 底层原子操作封装 | `-Action`, `-Index` / `-Name` |

## 实例模型

```text
LDPlayer instances
  [0] MAA reserved instance    -> DO NOT TOUCH
  [1] myapp                    -> workspace\myapp\
  [2] book-dmm                 -> workspace\book-dmm\
  [3] weidian                  -> workspace\weidian\
```

`re-list.ps1` 分类规则：

| Type | 含义 | 处理策略 |
|------|------|----------|
| `MAA` | index 0，MAA 保留实例 | 只读查看，不做写操作 |
| `RE` | 名称符合项目命名规则 | 可由本 skill 管理 |
| `NONASCII` | 名称存在但不符合 ASCII 项目名规则 | 不作为托管 RE 项目 |
| `ORPHAN` | 空名或异常实例 | 人工确认后再清理 |

## `re-init.ps1`

创建或复用项目实例，并配置 root、分辨率、CPU 和内存。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" `
  -Project myapp -Resolution "1280,720,240" -Cpu 2 -Memory 2048

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -NoLaunch
```

执行链路：

```text
validate project name
  -> ldconsole list2
  -> if project exists: reject index 0, launch if stopped
  -> if missing: ldconsole add
  -> ldconsole modify --root 1 --resolution --cpu --memory
  -> launch unless -NoLaunch
  -> wait for ADB ready
```

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
| workspace | `D:\reverse_ENV\workspace\` |

## 故障排查

| 症状 | 排查 |
|------|------|
| `ERR:invalid_project_name` | 项目名只能用 ASCII 字母、数字、点、下划线、短横线 |
| `ERR:project_resolves_to_index_0_MAA` | 项目名匹配到了 index 0，必须换项目名 |
| `ERR:instance_not_running` | 先执行 `re-init.ps1 -Project <name>` |
| `ERR:mitmproxy_ca_not_found` | 确认 `D:\reverse_ENV\tools\c8750f0d.0` 存在 |
| 端口冲突 | 显式传 `-ProxyPort`，或检查旧项目的 `mitmdump.pid` |
| 没有抓到 HTTPS | 检查 CA bind mount、App 是否证书固定、代理是否被 App 绕过 |
