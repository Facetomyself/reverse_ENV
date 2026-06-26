---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器管控——启停、状态、ADB 连接、快照。
  当用户需要"启动模拟器"、"关掉雷电"、"模拟器连 adb"、"给模拟器做快照"时使用。
---

# 雷电模拟器管控

## 适用范围

- 启动/停止/重启雷电模拟器
- 查看模拟器运行状态
- ADB 连接管理
- 快照保存与恢复

如果任务是 APK 分析本身（反编译、Hook），请用 `apk-reverse`。

## 本机环境

| 项目 | 值 |
|------|-----|
| 版本 | LDPlayer 9 |
| 安装路径 | `C:\Program Files\ldplayer9box\` |
| VM 名称 | `leidian0` |
| ADB 地址 | `127.0.0.1:5555` |
| 后端 | VirtualBox 6.1.50 |

## CLI 管控脚本

统一入口：`tools\ldplayer\ldplayer.ps1`

```powershell
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action <动作>
```

### 支持的动作

| -Action | 说明 |
|---------|------|
| `start` | 无 GUI 后台启动 |
| `start-gui` | 带窗口启动 |
| `stop` | 优雅关机（acpi） |
| `stop-force` | 强制断电 |
| `restart` | 优雅重启 |
| `status` | 查看是否运行中 |
| `adb` | 执行 `adb connect 127.0.0.1:5555` |
| `snapshot` | 创建快照（需 `-Name`） |
| `restore` | 恢复到快照（需 `-Name`） |

### 示例

```powershell
# 后台启动
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action start

# 查看状态
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action status

# 连接 ADB
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action adb

# 创建分析前快照
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action snapshot -Name "before-hook"

# 优雅关机
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action stop
```

## 典型工作流

```
1. 启动模拟器           → start
2. ADB 连接             → adb
3. 安装/运行目标 APK     → adb install（或走 apk-reverse 的 rebuild-sign-install.ps1）
4. Frida Hook / 分析    → 走 apk-reverse
5. 分析完毕、关机        → stop
```

> 如果要做破坏性测试，先 `snapshot` 保存当前状态，事后 `restore` 恢复。

## 禁止事项

- 不要在 `stop-force` 前不尝试 `stop`（优先优雅关机）
- 不要在生产/敏感环境中使用快照恢复（会丢弃所有增量数据）
