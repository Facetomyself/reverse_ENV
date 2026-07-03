---
name: ldplayer-control
description: |
  LDPlayer 9 雷电模拟器 — 逆向工程实例管理。
  为每个项目创建专属的隔离实例，一键初始化(root+分辨率)、HTTPS 代理抓包、实例销毁。
  与 MAA 安全共存。
---

# 雷电模拟器 RE 实例管理

为逆向项目提供隔离的 Android 模拟器实例。每个项目一个实例，命名一致，互不干扰。

## 快速开始

```powershell
# 1. 初始化项目实例（创建→配置 root→启动→等待 ADB 就绪）
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

# 2. 开启 HTTPS 代理抓包（flow 自动写入 workspace\myapp\）
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

# 3. 查看所有实例
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1"

# 4. 完成后清理
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp
```

## 脚本

| 脚本 | 用途 | 必填参数 |
|------|------|---------|
| `scripts/re-init.ps1` | 创建→配置→启动，一键就绪 | `-Project` |
| `scripts/re-list.ps1` | 实例总览（MAA/RE/orphan） | — |
| `scripts/re-proxy.ps1` | HTTPS 代理 on/off | `-Project` `-Action` |
| `scripts/re-destroy.ps1` | 停止 + 可选删除 | `-Project` |

## 实例隔离模型

```
┌─────────────────────────────────────────────────────┐
│ LDPlayer 实例列表                                    │
│                                                     │
│ [0] leidian0     ← MAA 专用，永不触碰               │
│ [1] myapp        ← RE 项目 myapp                    │
│ [2] book-dmm     ← RE 项目 book-dmm                 │
│ [3] weidian      ← RE 项目 weidian                  │
│ ...                                                 │
└─────────────────────────────────────────────────────┘
```

- **实例名 = 项目名** — 和 `workspace\<项目名>\` 命名一致
- **MAA 保护** — index 0 的所有写操作被拒绝
- **各项目隔离** — 不共享实例、不互相影响

## re-init.ps1 — 项目实例初始化

创建专属实例，一键配置完成。已存在的实例直接复用不重建。

```powershell
# 基础用法（默认 1920x1080@320dpi, 4核, 4GB）
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

# 自定义配置
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" `
    -Project myapp -Resolution "1280,720,240" -Cpu 2 -Memory 2048

# 只创建不启动
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -NoLaunch
```

**执行流程**: 检查是否存在 → 创建新实例(如需要) → root + 分辨率 + CPU/RAM 配置 → 启动 → 等待 ADB 就绪(最长 90s)

## re-list.ps1 — 实例状态一览

```powershell
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1"
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1" -Project myapp
```

输出按 Type 分类: `[MAA]` MAA 实例 / `[RE]` 逆向项目 / `[ORPHAN]` 无名孤例

## re-proxy.ps1 — HTTPS 代理管理

```powershell
# 开启代理（CA 证书 + adb reverse + mitmdump）
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

# 关闭代理
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off
```

**前置条件**: 实例必须已运行(`re-init.ps1`)。自动解析项目名→实例 index，flow 写入 `workspace\<Project>\mitmproxy_traffic.flow`。

**proxy-on 做了什么**: CA 证书推入 → bind mount cacerts(需 root) → adb reverse 端口 → Android 全局代理 → 启动 mitmdump
**proxy-off**: 清除代理 → 移除 adb reverse → 停止 mitmdump

## re-destroy.ps1 — 清理

```powershell
# 仅停止
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp

# 停止 + 删除实例（确认交互）
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp -Remove

# 停止 + 删除 + 跳过确认
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp -Remove -Force
```

**安全防护**: 拒绝操作 index 0。`-Remove` 需输入项目名确认。workspace 下的分析产出不会被删除。

## 典型工作流

### 新项目从零开始

```powershell
# 1. 创建 workspace 目录（按 CLAUDE.md 约束）
mkdir D:\reverse_ENV\workspace\myapp

# 2. 初始化 RE 实例
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp

# 3. 如有 APK 需要安装
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action install -Name myapp -ApkPath "D:\app.apk"

# 4. 开启抓包
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on

# 5. 启动目标 APP（触发流量）
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action runapp -Name myapp -PackageName "com.example.app"

# 6. 分析结束 — 关闭代理
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off

# 7. 清理
powershell -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-destroy.ps1" -Project myapp
```

### 多项目并行

```powershell
# 两个项目同时跑在不同实例上
powershell -File "...\re-init.ps1" -Project myapp
powershell -File "...\re-init.ps1" -Project weidian

# 各自独立抓包
powershell -File "...\re-proxy.ps1" -Project myapp -Action on
powershell -File "...\re-proxy.ps1" -Project weidian -Action on
```

## 本机环境

| 项目 | 值 |
|------|-----|
| 模拟器 | LDPlayer 9 (v9.5.19.0) |
| CLI | `D:\leidian\LDPlayer9\ldconsole.exe` |
| ADB | `D:\leidian\LDPlayer9\adb.exe` |
| ADB 映射 | `leidian{N} ↔ emulator-{5554 + N*2}` |
| mitmproxy CA | `D:\reverse_ENV\tools\c8750f0d.0` |

## 底层工具

RE 管理脚本基于 `ldplayer.ps1` 封装。如需原子操作（add/copy/install/uninstall/runapp/adb 等），直接调用：

```powershell
# 底层工具路径
powershell -File "D:\reverse_ENV\tools\ldplayer\ldplayer.ps1" -Action <动作> [参数...]
```

| -Action | 说明 |
|---------|------|
| `list` | 列出实例 |
| `status` | 单实例详情 |
| `launch` / `quit` / `reboot` | 启停控制 |
| `install` / `uninstall` / `runapp` | 应用管理 |
| `adb` | shell 命令 |
| `proxy-on` / `proxy-off` | 代理（含 -Project 必填） |

## 与 MAA 共存

- 共用 `ldconsole.exe` 和 `adb.exe`
- 所有 RE 管理脚本**拒绝操作 index 0**
- `re-list.ps1` 明确标记 MAA 实例
- `re-destroy.ps1` 内置 index=0 检查

## 故障排查

| 症状 | 排查 |
|------|------|
| `re-init.ps1` 找不到 ADB | 等待实例完全启动，手动验证: `adb -s emulator-5556 shell echo ready` |
| `re-proxy.ps1` CA 证书错误 | 确认 `D:\reverse_ENV\tools\c8750f0d.0` 存在，hash 匹配 |
| mitmdump 端口冲突 | 改端口: `ldplayer.ps1 -Action proxy-on -Index N -Project X -ProxyPort 8081` |
| 实例名冲突 | 一个项目一个实例，名=项目名。如需多实例，手动 `ldplayer.ps1 -Action add -Name xxx` |
| 孤儿实例清理 | `re-list.ps1` 查看 ORPHAN 实例 → `ldplayer.ps1 -Action remove -Index N` |
