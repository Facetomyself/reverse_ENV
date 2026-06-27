---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器多实例管控——列表、状态、ADB、关机、重启、安装APK。
  支持多实例（-Index 参数），与 MAA 兼容共存。
---

# 雷电模拟器多实例管控

## 适用范围

- 查看所有模拟器实例及运行状态
- ADB 连接指定实例
- 关机 / 重启
- 安装 APK

如果任务是 APK 分析本身（反编译、Hook），请用 `apk-reverse`。
创建/删除/克隆实例通过 LDPlayer 多开器 GUI（`dnmultiplayer.exe`），本脚本不管。

## 本机环境

| 项目 | 值 |
|------|-----|
| 版本 | LDPlayer 9 |
| 安装路径 | `D:\leidian\LDPlayer9\` |
| 后端 | VirtualBox 6.1.50 |
| ADB | `D:\leidian\LDPlayer9\adb.exe`（雷电自带） |

## 实例与 ADB 映射

```
leidian0  →  emulator-5554   ← MAA 正在使用，写操作需确认
leidian1  →  emulator-5556
leidian2  →  emulator-5558
leidianN  →  emulator-{5554 + N*2}
```

## CLI

```powershell
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action <动作> [-Index N] [-ApkPath ...]
```

### 动作

| -Action | 说明 | 影响 MAA? |
|---------|------|-----------|
| `list` | 列出所有实例（名称、ADB地址、运行状态、机型） | 只读 |
| `status` | 指定实例详情（Index/ADB/Model/DPI/SDK） | 只读 |
| `adb` | ADB devices 列表 | 只读 |
| `stop` | 通过 ADB 关机 | 若 Index=0 会警告 |
| `reboot` | 通过 ADB 重启 | 若 Index=0 会警告 |
| `install` | 安装 APK 到指定实例 | 若 Index=0 会警告 |

### 示例

```powershell
# 列出所有实例
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action list

# 查看 index 0 详情
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action status

# 查看 index 1（如果有）
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action status -Index 1

# 安装 APK 到 index 1
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action install -Index 1 -ApkPath "D:\app.apk"

# 重启 index 1
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action reboot -Index 1
```

## 典型工作流

```
1. list → 确认目标实例 index
2. status -Index N → 确认在线
3. install -Index N -ApkPath xxx → 安装目标 APK
4. 用 apk-reverse skill 做分析
5. stop -Index N → 分析完关机
```

## 与 MAA 共存

- 本脚本和 MAA 共用 `D:\leidian\LDPlayer9\adb.exe`，互不干扰
- `list` 和 `status` 只读，不影响 MAA 运行
- 对 index=0 的写操作（stop/reboot/install）会输出警告
- MAA 独占 `emulator-5554`，不建议在 MAA 运行时对其 stop/reboot

## 禁止

- 不要杀 `ldplayerservice` 或 `VBoxSVC` 进程
- 不要在 MAA 执行任务时对 index=0 做 stop/reboot
