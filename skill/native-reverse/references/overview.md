# native-reverse 总览

## 目录

- 版本信息
- 功能定位
- 快速安装
- 内置工具
- 宿主机依赖
- 目标设备依赖
- 常用环境变量
- 推荐工作流
- 文档入口

## 版本信息

- 当前版本：v2026.06.24
- 更新日期：2026-06-24
- 版本说明：包含实验记录详细约束、syscall-filter 跨平台 adb/load.ps1、eCapture wrapper 修复，以及 patch 不限制最小化的当前规则。

## 功能定位

`native-reverse` 用于 Android Native 检测链分析与稳定绕过工程。它把动态采集、静态分析、dump/fix、内核 hook、patch 验证和实验记录组织成一套可复现流程。

适用场景：

- 反 Frida、反调试、Root、模拟器、Hook/Xposed、完整性检测分析。
- `SIGKILL`、`SIGSEGV`、`SIGTRAP`、`BRK`、匿名 RX 段、direct syscall、constructor 早期闪退定位。
- 新加载 so 监控、加密 so 内存 dump 修复、IDA 强制导出分析、Ghidra/radare2 回退分析、OLLVM/非标准控制流还原。
- 强检测场景下使用 Android 内核无痕 HWBP hook 验证参数、返回值和 patch 候选。
- 按项目规则同步编写实验记录、检测点汇总、patch 表和验证报告。

## 快速安装

在目标工程根目录执行：

```bash
python D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --with-runner
```

安装脚本默认保留已有工具目录和 runner，且不写入 IDA 插件目录，也不把 `INP.py` 复制到项目 `scripts/`。需要替换时显式加 `--force`，需要保留旧副本时加 `--backup-existing`；需要使用 IDA 导出数据时，再用 `--with-inp` 复制项目批处理副本，或用 `--install-ida-plugin`、`--ida-root`、`--ida-plugin-dir` 复制 `INP.py` 到 IDA `plugins` 目录。

Windows PowerShell：

```powershell
python D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --with-runner
```

安装后常用目录：

```text
third_party/xiaojianbang-syscall-filter/
third_party/OLLVM_Deobfuscator/
third_party/MemDumper-master/
third_party/ecapture-v2.3.0-android-arm64/
third_party/xiaojianbang-stealth-hook-main/
scripts/frida_scfilter_runner.py
scripts/frida_memdump_so.py
scripts/memdump_so.py
scripts/ecapture_android.py
scripts/stealth_hook_android.py
scripts/ida_fix_function_range.py
scripts/INP.py（仅在显式 --with-inp / --install-project-inp 时）
<IDA目录>/plugins/INP.py（仅在显式安装 IDA 插件时）
```

`xiaojianbang-syscall-filter` 的 Unix 入口 `load.sh`、`capture_live.sh`、`capture_test.sh` 和 Windows 入口 `load.ps1` 都支持 `ADB` 覆盖 adb 路径；`load.sh` / `load.ps1` 支持 `KP_SUPERKEY` 覆盖 KernelPatch/APatch superkey。

分发或复制工具前可先运行 `scripts/install_skill_tools.py --self-check` 自检；只想审计目标路径时使用 `--audit`/`--dry-run`。

## 内置工具

| 工具 | 主要用途 | 关键依赖 |
|---|---|---|
| `frida_scfilter_runner.py` | Frida spawn/attach、pre-script、子进程覆盖、logcat 和 syscall-filter 联合采集，自动解析 App uid | Python 3.8+、Frida、adb、设备端 frida-server |
| `frida_memdump_so.py` | constructor/dlopen/JNI_OnLoad 短窗口、快速闪退或大 so 场景；Frida Python API 命中 linker constructor 后立即调用 MemDumper `-l -n` 自动 dump/fix 并拉回 | Python 3.8+、Frida、adb、Android root、匹配 ABI 的 `memdumper` |
| `INP.py` | IDA AI 输入导出插件/批处理脚本，输出反编译、反汇编 fallback、字符串、导入导出、xref 和函数关系到 `artifacts/inp/` | IDA/IDAPython、Hex-Rays 可用时导出伪代码 |
| `xiaojianbang-syscall-filter` | syscall 层定位 kill、exit、SIGSEGV、faccessat/openat、mmap/mprotect、direct syscall | Android root、APatch/KernelPatch、KPM、arm64 设备 |
| `MemDumper-master` + `memdump_so.py` | 稳定 pid/包名场景 dump 已加载 so，默认用 MemDumper `-l -n` 自动 rebuild/fix；manual 只用于失败后的地址范围 dump | Android root、匹配 ABI 的 `memdumper`、adb |
| `OLLVM_Deobfuscator` | OLLVM CFF、dispatcher、间接跳转/调用等控制流还原；混淆函数必须先还原再做语义分析或 patch 候选，项目副本可按样本变种修改 | Python 3.8+、`capstone`、`unicorn`、`keystone-engine` |
| `ecapture_android.py` | Android arm64 eCapture，采集 TLS 明文、pcap/keylog/text 日志 | Android arm64、root、eBPF/BTF 能力、adb |
| `xiaojianbang-stealth-hook` + `stealth_hook_android.py` | 内核无痕 HWBP hook，验证参数、返回值、替换返回值、修改 X0-X7 | Android arm64、GKI 5.4+、APatch/KernelPatch、KPM、root |

详细命令先看 `references/bundled-tools.md` 索引，再按任务读取 `tool-installation.md`、`syscall-frida-tools.md`、`dump-ida-ollvm-tools.md`、`stealth-ecapture-tools.md`。

## 宿主机依赖

宿主机支持：

- Windows 10/11 + Python 3.8+
- Linux + Python 3.8+
- macOS + Python 3.8+

通用依赖：

```bash
python -m pip install frida-tools frida
python -m pip install capstone unicorn keystone-engine
```

`adb` 路径查找顺序：

1. `ADB`
2. 工程内 `third_party/aosp/platform-tools/adb` 或 `adb.exe`
3. 工程内 `third_party/platform-tools/adb` 或 `adb.exe`
4. `PATH` 中的 `adb`

## 目标设备依赖

按工具不同，目标 Android 设备可能需要：

- root/su。
- arm64 或匹配目标进程 ABI。
- APatch/KernelPatch 和 KPM 加载环境。
- frida-server，版本需与宿主机 Frida 匹配。
- eBPF/BTF 能力，用于 eCapture。
- GKI 5.4+，用于 stealth hook。

## 常用环境变量

| 变量 | 用途 |
|---|---|
| `ADB` | 覆盖 adb 路径 |
| `SYSCALL_FILTER_ROOT` | 覆盖 syscall-filter 根目录 |
| `MEMDUMPER_ROOT` | 覆盖 MemDumper 根目录 |
| `ECAPTURE_ROOT` | 覆盖 eCapture 根目录 |
| `STEALTH_HOOK_ROOT` | 覆盖 stealth-hook 根目录 |
| `KP_SUPERKEY` | 覆盖 KernelPatch superkey，由用户设定，通过 KP_SUPERKEY 传入 |

## 推荐工作流

> 强约束速查（全程中文、工具路线、jadx checksum、匿名内存检查、CRC、函数范围、OLLVM、MemDumper 分流等）见 `SKILL.md` 速查清单；完整条款见 `workflow-standards.md` 对应章节。本节只给概览顺序。

1. 读取项目规则、已有实验记录、脚本、日志、dump 目录。
2. 在实验记录中写入详细记录：记录时间、分析思路、本轮操作、操作目的、所用工具、运行命令、代码变更、检测代码明细、实验结果、下一步计划。
3. 进入注入前先按任务类型定工具路线（`workflow-standards.md` §9.0），不默认 Frida spawn。
4. Frida 路线下监控 constructor、`dlopen/android_dlopen_ext`、JNI、关键返回值；syscall-filter 捕获 direct syscall、kill、SIGSEGV、路径探测和匿名 RX。
5. 分析 so 前必须判断是否加密、壳化、自解密或运行时重建；命中时 dump/fix 是硬门禁，禁止直接分析磁盘 so，下工具按 `dump-ida-ollvm-tools.md`「MemDumper 工具分流」选 `memdump_so.py` 或 `frida_memdump_so.py`。
6. dump/fix 后、IDA 分析前先做匿名内存加载执行检查（§5）。
7. 在已授权目标范围内用 IDA 分析 `.so`（jadx 分析 Java 层时关 dex checksum）；已有导出优先直接分析，需要导出数据时再复制/安装 `INP.py`。
8. 闪退案例按硬门禁闭环（§7）：syscall-filter 定位 pc/lr→加密/壳化判断与必要 dump/fix→先分析 `.init`/`.init_array`/`JNI_OnLoad`→匿名内存检查→CRC 检查→崩溃函数及上下游完整分析→patch→验证；未完成前禁止动态验证。
9. 遇 OLLVM/非标准控制流先确认函数范围（§6）再用项目副本 OLLVM_Deobfuscator 还原（§8）。
10. Frida/inline hook 不稳定或触发检测时，用 stealth-hook 做无痕参数/返回值验证。
11. 按证据选择 patch（§10），固定命令延长验证（§11），结果、命令和检测代码明细仍按详细模板记录。

## 文档入口

- `SKILL.md`：Skill 职责、触发场景、执行步骤和输出标准。
- `references/workflow-standards.md`：完整分析流程。
- `references/documentation-standards.md`：实验记录详细标准。
- `references/tooling-and-paths.md`：工具链、路径和环境变量规范。
- `references/bundled-tools.md`：内置工具索引和按任务读取路由。
- `references/tool-installation.md`：工具复制、自检、审计、`INP.py` 显式复制/安装。
- `references/syscall-frida-tools.md`：syscall-filter、Frida 联合采集、关键证据提取。
- `references/dump-ida-ollvm-tools.md`：MemDumper、IDA 导出、函数范围修正、OLLVM。
- `references/stealth-ecapture-tools.md`：stealth-hook、eCapture。
- `references/cross-platform.md`：Windows/Linux/macOS 使用说明。
- `references/verification-checklists.md`：运行前、加载链、崩溃、patch 和失败复盘检查项。
- `references/safety-and-confirmation-rules.md`：授权边界、记录边界和 patch 边界。
