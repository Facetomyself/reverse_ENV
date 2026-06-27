---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器多实例管控（基于 ldconsole.exe CLI）。
  支持完整的实例生命周期：创建、克隆、删除、启停、安装APK、执行ADB命令、修改机型/分辨率/root。
  与 MAA 兼容共存——共用 ldconsole 和 adb，不冲突。
---

# 雷电模拟器多实例管控

## 适用范围

- 创建/克隆/删除模拟器实例
- 启动、关机、重启
- 修改实例配置（分辨率、CPU、内存、机型、IMEI、root 等）
- 安装/卸载/启动应用
- 执行 ADB 命令

如果任务是 APK 分析本身，请用 `apk-reverse`。

## 本机环境

| 项目 | 值 |
|------|-----|
| 版本 | LDPlayer 9 (v9.5.19.0) |
| CLI | `D:\leidian\LDPlayer9\ldconsole.exe` |
| ADB | `D:\leidian\LDPlayer9\adb.exe` |
| ADB 映射 | `leidian{N} ↔ emulator-{5554 + N*2}` |

## CLI

```powershell
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action <动作> [参数...]
```

### 实例管理

| -Action | 参数 | 说明 |
|---------|------|------|
| `list` | — | 列出所有实例（名称、状态、ADB地址、分辨率） |
| `status` | `-Index N` | 单个实例详情（型号、SDK版本） |
| `add` | `-Name <name>` | 创建新实例 |
| `copy` | `-From <idx> -Name <name>` | 克隆实例 |
| `remove` | `-Index N` | 删除实例（禁止删除 index 0） |
| `modify` | `-Index N -Root -Resolution "1920,1080,280"` | 修改实例配置 |

### 运行控制

| -Action | 参数 | 说明 |
|---------|------|------|
| `launch` | `-Index N` | 启动实例 |
| `quit` | `-Index N` | 关闭实例 |
| `reboot` | `-Index N` | 重启实例 |

### 应用管理

| -Action | 参数 | 说明 |
|---------|------|------|
| `install` | `-Index N -ApkPath <path>` | 安装 APK |
| `uninstall` | `-Index N -PackageName <pkg>` | 卸载应用 |
| `runapp` | `-Index N -PackageName <pkg>` | 启动应用 |
| `adb` | `-Index N -Command "..."` | 执行 ADB shell 命令 |

### 示例

```powershell
# 创建逆向专用实例
powershell -File "ldplayer.ps1" -Action add -Name "reverse"
powershell -File "ldplayer.ps1" -Action modify -Index 1 -Root -Resolution "1920,1080,320"

# 启动并安装 APK
powershell -File "ldplayer.ps1" -Action launch -Index 1
powershell -File "ldplayer.ps1" -Action install -Index 1 -ApkPath "D:\app.apk"

# 列出所有实例
powershell -File "ldplayer.ps1" -Action list

# 执行 ADB 命令
powershell -File "ldplayer.ps1" -Action adb -Index 1 -Command "pm list packages"
```

## 典型工作流

```
1. add -Name "re_target"              → 创建逆向专用实例
2. modify -Index 1 -Root              → 开启 root
3. launch -Index 1                    → 启动
4. install -Index 1 -ApkPath xxx.apk  → 安装目标
5. 用 apk-reverse 做静态分析           → jadx + apktool
6. runapp -Index 1 -PackageName xxx   → 启动应用
7. adb -Index 1 -Command "..."        → 运行时调试
8. quit -Index 1                      → 分析完关机
```

## 与 MAA 共存

- 共用 `ldconsole.exe` 和 `adb.exe`，互不干扰
- `list`/`status` 只读，不影响 MAA
- 对 index=0 的写操作会输出 MAA 警告
- `remove` 禁止删除 index 0

## 禁止

- 不要 kill `ldplayerservice` 或 `VBoxSVC`
- 不要在 MAA 执行任务时对 index=0 做 quit/reboot
- 不要 remove index 0
