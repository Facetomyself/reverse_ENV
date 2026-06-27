---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器管控——状态、ADB 连接、关机、重启。
  当用户需要"模拟器连adb"、"关掉雷电"、"重启模拟器"时使用。
  注意：启动需通过 LDPlayer GUI，脚本无法绕过服务锁。
---

# 雷电模拟器管控

## 适用范围

- 查看模拟器运行状态
- ADB 连接管理
- 关机（ADB 优雅关机 / 强制断电）
- 重启（ADB reboot）

启动模拟器需要通过 LDPlayer GUI（桌面快捷方式），因为 LDPlayer 9 的 Windows 服务持有 VM 会话锁，VBoxManage 无法绕过。

如果任务是 APK 分析本身，请用 `apk-reverse`。

## 本机环境

| 项目 | 值 |
|------|-----|
| 版本 | LDPlayer 9 |
| 安装路径 | `C:\Program Files\ldplayer9box\` |
| VM 名称 | `leidian0` |
| ADB 地址 | `emulator-5554`（LDPlayer index 0 固定地址） |
| ADB 路径 | `D:\leidian\LDPlayer9\adb.exe`（雷电自带，与 MAA 共用） |

## 架构说明

LDPlayer 9 使用 `emulator-5554` 作为 ADB 地址（非 `127.0.0.1:5555`）。与 MAA 兼容共存——MAA 使用同一 ADB 路径和地址。本脚本只做只读状态查询和通过 ADB 操作 Android，不碰 VBoxManage，不影响 MAA 运行。

## CLI 管控脚本

统一入口：`tools\ldplayer\ldplayer.ps1`

```powershell
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action <动作>
```

### 支持的动作

| -Action | 说明 |
|---------|------|
| `status` | 查看 VM 是否运行 + ADB 是否在线 |
| `adb` | 执行 `adb connect 127.0.0.1:5555` |
| `stop` | 关机（优先 ADB reboot -p，兜底 poweroff） |
| `restart` | ADB reboot 软重启 Android |

### 示例

```powershell
# 查看状态
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action status

# 连接 ADB
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action adb

# 关机
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action stop

# 重启 Android
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action restart
```

## 典型工作流

```
1. 双击桌面 LDPlayer 图标启动模拟器
2. 等 Android 启动完毕
3. powershell -File "ldplayer.ps1" -Action adb      → 连接
4. 安装/运行 APK，Frida Hook                        → 走 apk-reverse
5. powershell -File "ldplayer.ps1" -Action stop     → 关机
```

## 禁止事项

- 不要杀 `ldplayerservice` 或 `VBoxSVC` 进程（会导致 VM 注册丢失）
- 不要在 ADB 离线时用 `restart`（需先确认 ADB 在线）
