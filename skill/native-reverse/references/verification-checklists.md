# 验证检查清单

## 按需运行前

- 不在任务开始前一次性检查所有工具环境；只勾选本轮实际使用的工具或能力。
- 需要 adb 控制设备、采集日志或运行目标时，已确认 adb 路径和设备状态；必要时 `adb reboot` 后再测。
- 使用任何 Frida 功能前，已用设备侧 `ps`/`pidof` 确认 frida-server 活跃进程；若未启动，已先在 `/data/local/tmp` 查找 `frida-server*` 并用已有文件启动，找不到时已询问用户路径。
- 使用 Frida 时，已确认 frida-server 路径、架构和版本；发现版本不匹配时，仅记录风险并建议用户自行更换，未自行安装、切换、推送或替换任何 Frida/Frida-server 版本。
- 做无 hook 基线运行测试前，已确认本轮基线是否需要 frida-server 参与，并记录“保留 server”或“纯净无 Frida 环境”的基线口径。
- App 进程已清理。
- 使用 Frida JS、runner 或 patch 文件前，已确认当前文件路径。
- 使用 stealth-hook 前，已确认 APatch/KernelPatch、KPM 加载状态、目标设备 arm64/GKI 条件。
- 使用 syscall-filter、MemDumper、eCapture 或 so 注入前，已确认各自所需 root/su、KPM、ABI、eBPF/BTF 等对应前置。
- 实验记录已按详细模板写入，并包含分析思路、所用工具、运行命令、代码改动和检测代码明细字段。

## 加载链

- 主进程是否进入。
- 子进程是否被覆盖。
- 目标早期 so 是否在 constructor 前后被监控。
- 目标主检测 so 是否加载并通过。
- 后续是否有新 so 加载。
- 是否出现匿名 RX 段。

## so 静态分析前

> 硬门禁完整条款见 `workflow-standards.md` §3（syscall-filter）、§4（加密/壳化 dump/fix）、§5（匿名内存）、§7（闪退静态顺序）与 `tooling-and-paths.md`（jadx checksum）。本节只列勾选项。

- 已用 jadx（`-Pdex-input.verify-checksum=no` 或 gui 关闭 checksum）成功加载并反编译目标 dex，所用参数已记录。
- 已判断磁盘 so 是否加密、壳化、自解密或运行时重建；若命中，已 dump/fix 运行期 so 或真实可执行段并校验 ELF/readelf/IDA 导入结果。
- 未把已命中加密/壳化/自解密/运行时重建的磁盘 so 直接用于函数语义、检测链结论、patch 候选或动态验证。
- 闪退/崩溃/退出案例已先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives/JNI bridge，并记录入口函数范围和关键调用。
- 已拉取并落盘 `/proc/<pid>/maps`，确认有/无 `rwx/r-x` 匿名段、`memfd` 或可疑 `[anon:.bss]` 映射。
- 已用 syscall-filter 核对 `mmap/mprotect(PROT_EXEC)`、`memfd_create`，确认匿名 RX/memfd 来源；未覆盖时已停止推进并补采。
- 已比对崩溃/调用 `pc/lr/sp` 落在磁盘 so、系统库、匿名 RX、memfd 还是未知映射。
- 若关键逻辑在匿名内存或 memfd：已 dump 匿名段并 fix，后续分析、函数范围、patch 候选、`pc/lr` 归属均以匿名段为准。
- 已检查 CRC/完整性校验，至少覆盖自身 `.text`、libc/libart/linker、dex/APK/签名等与目标相关的候选，并记录有/无和失配执法路径。
- 已确认崩溃点所在函数范围，并完整分析该函数、上游调用者、下游关键调用、fatal 分支、返回值/状态码和副作用。
- 匿名内存检查结果、命令、证据路径和相关检测代码已写入实验记录；未完成上述硬门禁前未凭磁盘/dump so 的 `.text` 下检测链结论、patch 候选或动态验证。

## 崩溃/终止

- `SIGKILL`：记录 syscall、pid/tid、pc/lr、调用者。
- `SIGSEGV`：记录 fault addr、pc/lr、是否匿名 RX。
- `SIGTRAP/BRK`：记录断点地址、上游分支。
- `exit/exit_group/abort`：记录调用来源。
- 区分 App native 检测终止与系统/framework 生命周期终止。
- 以上任一闪退、崩溃、退出或低地址自毁，均已先用 `xiaojianbang-syscall-filter` 捕获 syscall、pc/lr/sp、线程和 maps 归属；未完成前未继续动态 hook/patch。
- syscall-filter 后的静态闭环已按顺序完成：加密/壳化判断与必要 dump/fix -> `.init`/`.init_array`/`JNI_OnLoad` 入口分析 -> 匿名内存映射 -> CRC/完整性校验 -> 崩溃点函数完整分析；未完成前未继续动态验证。

## 检测类型

逐项确认是否存在证据：

- Frida 检测：maps、memfd、agent、gum、端口、线程名、inline hook。
- Root 检测：`su`、Magisk、`/data/adb`、busybox、特权路径、属性。
- 反调试：`TracerPid`、`ptrace`、JDWP、debugger active。
- 模拟器：build 属性、硬件属性、设备文件、传感器、网络。
- Hook/Xposed：包名、类名、maps、fd、反射、inline patch。
- 完整性：APK、dex、so、资源 hash、签名、代码段字节。
  - 是否存在对 **自身 `.text`、`libc.so`、`libart.so`**（及 `linker`/dex/签名）的 CRC/逐字节校验（识别特征与处置见 `workflow-standards.md` §9.1/§9.2）。
  - 确认有 CRC 时：工具路线按任务类型决策（§9.0），已记录任务类型与工具路线、CRC 函数偏移、校验目标、校验方式、失配自毁形式、所选绕过手段。
- ADB/USB：只有看到明确路径、属性、命令或状态判断才写已确认。
- 设备白名单：只有看到明确 ID/型号/指纹/证书白名单比对才写已确认。

## Patch 验证

- patch 命中日志出现。
- 原始 fatal 分支不再进入。
- 目标函数返回值符合预期。
- stealth-hook 已记录 `pid/so/offset`、hit 次数、X0-X7、返回值或改参/替换返回值结果。
- 下游 so 继续加载。
- App 可交互且无明显 ANR/卡顿。
- 延长测试时间后仍稳定。
- 不因 patch 引入高频日志或性能问题。

## 失败复盘

失败记录必须包含：

- 本轮唯一变量。
- 新日志。
- 与上一轮差异。
- 是否新增 so 或匿名段。
- 是 patch 没命中、命中后仍 fatal、还是引入卡顿。
- 下一轮最小改动。
