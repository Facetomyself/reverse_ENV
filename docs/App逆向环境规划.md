# App 逆向环境规划

> 本文记录 `D:\reverse_ENV` 当前 App 逆向环境的本地落地方案。背景知识参考 `article/mobile-app-reverse/app-reverse-environment-setup.md`，但实际操作以本文和 `skill/ldplayer-control/SKILL.md` 为准。

## 核心模型

LDPlayer 是多实例模拟器，不能按真机那套“长期维护一台设备”的逻辑使用。当前环境采用模板实例 + 项目实例：

```text
template instance -> copy/restore -> project instance -> install target App -> analyze -> destroy/rebuild
```

模板只做环境基座和 verified 备份，不直接安装目标 App，不长期保留目标登录态，不混入业务抓包流量。

## 当前实例分层

| 实例 | ADB | 定位 | 已验证能力 |
|------|-----|------|------------|
| `re-base` | `emulator-5558` | 基础动态调试模板 | Android 9 / Root / Kitsune Mask v27.0 / Frida 17.15.3 / mitmproxy CA |
| `re-xposed` | `emulator-5560` | 日常逆向默认模板 | `re-base` + LSPosed v1.9.2 + JustTrustMe v2 |
| `re-stealth` | `emulator-5562` | 强检测目标模板 | `re-xposed` + Hide My Applist V3.6.1 + Shamiko v0.7.5 |

`reverse` 是早期 seed / legacy RE 实例，不作为新项目默认入口。index 0 是 MAA 保留实例，任何写操作都不能触碰。

## 模板选择

| 目标情况 | 首选模板 | 原因 |
|----------|----------|------|
| 普通抓包、Frida Hook、基础 Java/Native 动态观察 | `re-base` | 干扰最小，便于判断 App 原始行为 |
| HTTPS Pinning 明显、需要 Xposed 模块快速验证 | `re-xposed` | JustTrustMe 已就位，日常效率最高 |
| App 检测 Root、Xposed、安装列表或 Magisk 痕迹 | `re-stealth` | 已加入 HMA + Shamiko，适合强检测初筛 |
| 明确检测模拟器硬件、ABI、传感器、GPU、基带 | 真机 | 模拟器层能力有限，不要硬装能过 |

## 新项目启动

先查知识库，再按目标风险创建项目实例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -Template re-xposed
```

基础项目可用 `re-base`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -Template re-base
```

强检测项目可用 `re-stealth`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project myapp -Template re-stealth
```

创建后再做目标 App 安装、LSPosed scope、代理、Frida Hook。项目实例脏了就删除重建，不回写模板。

## LSPosed 与反检测模块

当前模板内模块状态：

| 模板 | LSPosed | JustTrustMe | Hide My Applist | Shamiko |
|------|---------|-------------|-----------------|---------|
| `re-base` | 无 | 无 | 无 | 无 |
| `re-xposed` | 已安装 | 已安装并启用模块本体 | 无 | 无 |
| `re-stealth` | 已安装 | 已安装并启用模块本体 | 已安装并启用模块本体 | v0.7.5 已安装 |

LSPosed scope 不在模板中预设。项目实例里按目标包名设置：

```text
/data/adb/lspd/config/modules_config.db
modules(mid, module_pkg_name, apk_path, enabled)
scope(mid, app_pkg_name, user_id)
```

原则：

- JustTrustMe 只给需要 SSL Pinning 绕过的目标包加 scope。
- Hide My Applist 只给强检测目标加 scope，并为目标配置隐藏列表。
- 不建议在模板里启用全局 scope；除非目标验证明确需要，且必须记录到项目 `triage.md`。

## 备份与恢复

verified 备份已落地：

```text
D:\reverse_ENV\storage\ldplayer-backups\re-base.verified.20260707_104718.ldbk
D:\reverse_ENV\storage\ldplayer-backups\re-xposed.verified.20260707_104718.ldbk
D:\reverse_ENV\storage\ldplayer-backups\re-stealth.verified.20260707_104718.ldbk
```

重新备份模板：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-backup.ps1" -Project re-xposed -Tag verified
```

恢复模板：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project re-xposed -SourceProject re-xposed -Force
```

恢复脚本要求目标实例已存在；这是有意设计，避免误把备份恢复成一个意外新实例。测试恢复时先创建临时实例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-init.ps1" -Project restore-test -Template re-base -NoLaunch
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project restore-test -SourceProject re-xposed -Force
```

实测注意：`ldconsole restore` 会把备份内部实例名一并恢复出来。脚本现在按目标 index 恢复，并在恢复后重命名回 `-Project`，避免跨来源恢复时出现两个同名模板实例。

## 抓包与 Frida

开启项目代理：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action on
```

关闭项目代理：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-proxy.ps1" -Project myapp -Action off
```

flow 文件写入：

```text
D:\reverse_ENV\workspace\myapp\mitmproxy_traffic.flow
```

Frida server 由 `init-ldplayer-re.ps1` 初始化；模板已验证可用。项目实例复制后如 Frida 不通，重新对目标 serial 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-list.ps1" -Project myapp
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\apk-reverse\scripts\init-ldplayer-re.ps1" -DeviceSerial <ADB from re-list>
```

脚本成功门不是“frida-server 有 PID”，而是 ADB/Root/ABI、host/device Frida 版本和 host-to-device 进程枚举 handshake 全部通过。

## 模拟器 whole-DEX 脱壳路线

当前 `tools\panda-dex-dumper\panda-dex-dumper` 是 AArch64 ELF。LDPlayer 9 模板主 ABI 为 x86_64，但 Android 9 实例通过 `libnb.so` native bridge 已验证可以执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\dump-dex.ps1" `
  -Project myapp -Package com.example.app -DeviceSerial <ADB> -Launch
```

已验证范围：

- 普通 App：19 个 DEX / 21,134,420 bytes，最大 DEX 经 jadx 生成 2,884 个 Java 文件。
- 起点读书 / 360 Jiagu VIP 样本：13 个 DEX / 73,247,772 bytes，最佳 DEX 生成 4,181 个 Java 文件，其中 4,073 个为 `com.qidian`；仍有大量 loading/decompile errors，只能称部分脱壳。

因此这条模拟器路线标记为**可用**，适用于真实代码加载后以内存标准 whole DEX 存在的目标，也覆盖部分企业壳样本。它不是企业壳通杀：方法抽取、CompactDex、VMP、Dex2C、强 anti-dump、多进程和 lazy loading 必须按样本另行验证或转 `native-reverse`。

`dump-dex.ps1` 会校验 AArch64 执行条件、PID 归属、超时、DEX magic/header/class_defs，并在失败时保留设备端证据、best-effort 恢复被 panda 暂停的目标进程。详见 `skill\apk-reverse\references\packing-and-unpacking.md`。

## 真机边界

模拟器适合快速验证、批量重置、抓包和 Hook，但不是强检测最终答案。出现以下信号时切真机：

| 信号 | 说明 |
|------|------|
| 明确检测 `ro.kernel.qemu`、模拟器硬件、传感器、基带、GPU | LSPosed/Frida 不一定能补齐硬件真实性 |
| 只在 x86_64 模拟器崩溃，ARM64 真机正常 | ABI/JIT/native 兼容问题，不应在模拟器硬耗 |
| 风控绑定 SafetyNet/Play Integrity/TEE/硬件密钥 | 模拟器很难提供可信硬件证明 |
| 目标存在强 Frida/Xposed/Root 对抗 | 先用 `re-stealth` triage，最终仍需真机复核 |

## 维护规则

- 模板升级必须先记录模块版本，再跑 Root、Frida、代理、LSPosed 基础验证。
- 模板升级后重新打 `verified` 备份，并更新 `tools/android-modules/README.md`。
- 项目实例不得回灌为模板；需要沉淀能力时，在干净模板上重复安装并验证。
- `Shamiko-v1.2.5-414-release.zip` 当前只归档，不用于模板；当前 Kitsune/Magisk 27001 verified 版本是 `Shamiko-v0.7.5-194-release.zip`。
