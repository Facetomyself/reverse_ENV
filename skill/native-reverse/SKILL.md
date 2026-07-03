---
name: native-reverse
description: Android Native 反检测分析与稳定绕过工程（中文工作语言，宿主机 Windows/Linux/macOS）。分析 .so 的反调试、反 Frida、Root、模拟器、完整性/CRC、JNI/constructor/dlopen/匿名 RX 检测链并做 patch 绕过；按任务类型分流 Frida、syscall-filter、内核无痕 HWBP hook、MemDumper dump/fix、IDA(INP.py) 导出、OLLVM 还原、eCapture TLS 抓包，全程中文同步实验记录。
---

# native-reverse

## 职责

Android Native 检测链分析与稳定绕过工程。把动态证据、静态反编译、patch、验证和实验记录形成可复现闭环：分析 `.so` 的 JNI、constructor、dlopen、syscall、反调试、Root、Hook、Frida、模拟器、完整性/CRC 检测链，定位 `SIGKILL`/`SIGSEGV`/`SIGTRAP`/`BRK`/匿名 RX/direct syscall/constructor 早期闪退，给出 patch 候选、最终 patch、风险边界和验证结果。helper 与真实检测链分开记录，不把分析结论只留在对话或临时日志里。

仅用于自有或用户明确许可的样本、研究和调试环境；遇到目标边界不清的场景，先说明边界并停止会造成未授权访问、隐蔽控制或数据外传的操作。

## 按需前置门槛

宿主机支持 Windows/Linux/macOS + Python 3.8+。不要在任务开始前一次性检查所有工具环境；只在本轮确实需要使用某个工具或能力前，检查该工具对应的前置条件。未使用的能力不做环境检查、不阻塞当前任务。

- **MemDumper / syscall-filter / eCapture / so 注入**：仅在准备使用对应能力前确认 root/su；未使用时不检查。
- **syscall-filter / stealth-hook**：仅在准备使用前确认 APatch/KernelPatch、KPM 加载能力和匹配 ABI；KernelPatch superkey 由 `KP_SUPERKEY` 环境变量传入。
- **Frida**：仅在准备使用 `frida-ps`、spawn、attach、runner 或 Frida hook 前确认 frida-server 活跃状态和版本匹配风险；禁止自行更换宿主或设备端 Frida/Frida-server 版本，只能向用户说明风险并建议用户自行更换。
- **stealth-hook / eCapture**：仅在准备使用前确认 GKI 5.4+、eBPF/BTF 等对应内核条件。
- **宿主工具链**：当前项目已预装 frida、capstone、unicorn、keystone-engine、jadx、IDA Pro 9.3、radare2、adb 等工具，路径见 `CLAUDE.md` 工具速查。这不授权代理自行安装、降级、升级或切换 Frida/Frida-server 版本。

## 触发场景

- Android App native 反调试、反 Frida、Root、模拟器、Hook、完整性/CRC 检测分析。
- 定位 `SIGKILL`/`SIGSEGV`/`SIGTRAP`/`BRK`/匿名 RX 崩溃/direct syscall/constructor 早期闪退。
- 验证新加载 `.so`、dump 修复内存 so、分析 IDA 导出、处理 OLLVM/控制流混淆。
- 强反 Frida/强完整性/`.text` 校验环境下用内核无痕 HWBP hook 验证参数、返回值或 patch 候选。
- 编写/维护逆向实验记录、复现文档、检测点汇总、patch 表、验证报告。
- 用户提到 `syscall-filter`、Frida 启动/附加、`dlopen`、`call_constructors`、早期自解密 so、匿名 RX 等工作流。

## 强约束速查清单

每条只给一行速查，完整条款见所列归属文件，不在本文件展开：

1. **全程中文**回答与记录；仅用户明确要求其他语言才切换并记录答复。（本文件为语言规则唯一出处）
2. **Windows 读取中文文件必须显式 UTF-8**：读本 Skill、`references/*.md`、项目实验记录、中文日志时用 `Get-Content -Encoding UTF8`、`[IO.File]::ReadAllText(path,[Text.Encoding]::UTF8)` 或 Python `encoding='utf-8'`；不要先用 PowerShell 默认编码读再向用户汇报"乱码后重读"。详见 `references/cross-platform.md`。
3. **工具路线按任务类型决策**：过检测类→Frida 干掉检测；硬禁令：当用户目标是"过检测/让 Frida 注入后 App 正常运行/用 Frida 跑起来/注入不被发现"时，禁止把 HWBP/stealth-hook 作为主流程，HWBP 只能作为辅助验证手段；分析算法类→无 Frida 检测用 Frida、有则 HWBP、HWBP 不支持再回 Frida 过检测。详见 `references/workflow-standards.md` §9.0。
4. **注入/patch 前先评估** `.text` CRC / 强反 Frida，再按第3条选路线，不默认 Frida spawn。详见 `references/workflow-standards.md` §9.0。
5. **jadx 关 dex checksum**（`-Pdex-input.verify-checksum=no` 或 gui 关闭）。详见 `references/tooling-and-paths.md`。
6. **加密/壳化 `.so` dump/fix 是硬门禁**：分析 `.so` 前必须判断磁盘 so 是否加密、壳化、自解密或运行时重建；一旦命中，禁止直接分析磁盘 so 下结论或给 patch，必须先 MemDumper/frida_memdump dump/fix 运行期 so 或真实可执行段并校验产物。未确认可分析时只能补证据。分流见 `references/dump-ida-ollvm-tools.md`「MemDumper 工具分流」。
7. **闪退静态分析顺序是硬门禁**：闪退/崩溃/退出案例进入 so 静态分析后，必须先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives，再分析匿名内存映射与跳转证据、CRC/完整性校验、崩溃点所在函数及上下游；未完成前禁止动态验证、patch 候选或继续 Frida 试错。详见 `references/workflow-standards.md` §4/§5/§7。
8. **分析 `.so` 前匿名执行证据是硬门禁**：进入 IDA 结论、函数语义、patch 候选或动态验证前，必须用 maps 与 `syscall-filter` 核对 `mmap/mprotect(PROT_EXEC)`、`memfd_create`、匿名 `rwx/r-x`、`memfd`、可疑 `[anon:.bss]` 等；若关键逻辑落在匿名内存，必须先 dump/fix 匿名段并以其为准分析。未完成则只能补证据，禁止继续下检测链结论或 patch。详见 `references/workflow-standards.md` §5。
9. **静态分析查 CRC/完整性校验**（自身 `.text`/libc/libart），有则优先干掉检测代码。详见 `references/workflow-standards.md` §9.1/§9.2。
10. **分析 so 函数前先确认函数范围；OLLVM 先还原再分析**。详见 `references/workflow-standards.md` §6、§8。
11. **patch 不限制最小化**，只要求基于证据、可解释、可回退并完成验证；详见 `references/workflow-standards.md` §10。
12. **闪退/崩溃/退出必须先走 syscall-filter 硬门禁**：任何 `SIGKILL`/`SIGSEGV`/`SIGTRAP`/`BRK`/`abort`/`exit`/`exit_group`/低地址自毁/进程主动退出，必须先用 `syscall-filter` 捕获 syscall、pc/lr/sp、线程和 maps 归属，再进入 dump/fix、入口函数静态分析、匿名内存检查、IDA 导出、函数范围、CRC、崩溃函数完整分析、patch、验证。未完成前禁止用 Frida 动态试错替代。详见 `references/workflow-standards.md` §3/§7。
13. **连续动态测试硬上限**：同一 so、同一函数、同一检测链或同一调度链内，动态 hook/patch/runner 覆盖等有效测试失败累计 3 次后，禁止继续动态叠加 hook、patch 或 runner 变量；必须转入静态闭环，分析目标 so 和可疑匿名段代码，完成 dump/fix、`.init`/`.init_array`/`JNI_OnLoad`、匿名内存检查、IDA 导出、函数范围确认、CRC 检查和崩溃函数完整分析后，才能基于静态结论恢复动态验证。详见 `references/workflow-standards.md` §7/§11。
14. **动态修改可成组但必须有依据**：可以按静态分析结论成组调整 patch/hook/runner 覆盖；每组调整用实验记录说明依据、分析思路、所用工具、命令、代码改动、检测代码明细和结果，不得用成组调整绕过第13条的三次上限。
15. **使用 Frida 前先确认 frida-server 已启动**：任何 `frida-ps`、spawn、attach、runner 或 Frida hook 前，必须先用设备侧 `ps/pidof` 确认 frida-server 活跃进程；若未启动，先到 `/data/local/tmp` 查找 `frida-server*` 并尝试用已有文件启动；若没有找到，询问用户 frida-server 路径。详见 `references/workflow-standards.md` §11 与 `references/verification-checklists.md`。
16. **禁止自行更换 Frida 版本**：发现宿主 Frida 与设备端 frida-server 版本不匹配时，只能记录风险并建议用户自行更换；禁止自行 `pip install`、创建/切换 venv、推送替换 frida-server 或改用其它版本。详见 `references/workflow-standards.md` §11。
17. **无 hook 基线前先确认 frida-server 口径**：运行 App 做无 hook 基线测试前，先确认设备端 frida-server 是否运行、路径/版本是否与宿主 Frida 匹配，并把结果写入实验记录；若基线口径是纯净无 Frida，需先停止 server。详见 `references/workflow-standards.md` §11 与 `references/verification-checklists.md`。
18. **Frida spawn/attach 异常先设备状态闭环**：Frida spawn、spawn-gating、attach、早期注入出现卡住、`closed`、server 不可用、启动后立刻断开或目标未起时，必须先检查锁屏/亮屏/解锁状态，必要时 `adb reboot` 后重新启动 frida-server 并复测；完成前禁止优先归因到版本、端口、脚本或继续叠加 hook/patch。详见 `references/workflow-standards.md` §2、§11。
19. **jadx/IDA 路径未命中必须全盘搜索**：PATH、项目目录、已有记录和常见安装路径都找不到 `jadx` 或 IDA 时，必须做宿主机全盘搜索并记录命令、范围、候选和结果；全盘仍找不到才询问用户路径或请求确认回退。当前项目 IDA 路径 `D:\reverse_ENV\resource\portable_win\`、jadx 路径 `D:\reverse_ENV\tools\jadx\` 已预配置，优先使用。详见 `references/tooling-and-paths.md`。

补充硬约束：工作前先读项目 `CLAUDE.md`/README/已有实验记录/脚本/日志；不要在任务开始前一次性检查所有工具环境，只有准备使用某个工具或能力时才检查对应前置；分析过程必须边分析边同步写实验记录，详细记录分析思路、实际操作、操作目的、所用工具、运行命令、代码变更、检测代码明细、实验结果和下一步计划；所有已经分析出的检测代码都必须写入记录，不遗漏 so/函数/offset、关键伪代码或汇编、判断条件、常量/字符串、syscall/API、返回值/状态码、fatal/kill/abort/BRK 分支和上下游调用；新 `.so` 工具逆向在用户未明确授权直接分析时，先走 `references/safety-and-confirmation-rules.md` 的确认流程；任何闪退、崩溃或退出必须先用 `syscall-filter` 定位 syscall 与 pc/lr/sp 归属；分析 `.so` 前必须判断加密/壳化/自解密/运行时重建，命中则必须 dump/fix 后分析，禁止直接分析磁盘 so 下结论；闪退静态分析必须先看 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives，再分析匿名 RX/memfd、CRC/完整性校验、崩溃点所在函数和上下游，未完成前禁止动态验证；分析 `.so` 前必须核对 `mmap/mprotect(PROT_EXEC)`、`memfd_create`、匿名 RX/memfd 映射，发现关键匿名代码必须先 dump/fix 后分析；使用任何 Frida 功能前必须先确认设备端 frida-server 活跃进程，未启动时先查 `/data/local/tmp/frida-server*` 并用已有文件启动，找不到才询问用户路径；发现 Frida 版本不匹配时禁止自行更换版本，只能建议用户自行更换并在实验记录中说明；Frida spawn/attach/早期注入异常必须先完成锁屏/亮屏/解锁与必要 reboot 复测闭环，未完成前禁止优先归因到版本、端口、脚本或继续叠加 hook/patch；需要使用 adb/IDA/jadx 且找不到路径时，先查 PATH、项目 `scripts/` 与 `third_party/`、已有实验记录和常见路径；若本轮确实需要 jadx/IDA 且仍未命中，必须做宿主机全盘搜索，并在实验记录中说明结果；Java/Kotlin 层强制 jadx、`.so` 强制 IDA（用户明确没有才回退并记录）；IDA/OLLVM 导出统一用 `INP.py` 输出到 `artifacts/inp/`，且只在需要 IDA 导出时显式复制/安装 `INP.py`（详见 `references/tool-installation.md`、`references/dump-ida-ollvm-tools.md`）；不覆盖旧实验记录。

## 执行步骤

详细流程见 `references/workflow-standards.md`；本节只列骨架，每步的强约束正文见所引章节。

1. **建立上下文**：读项目 `CLAUDE.md`、README、实验记录、日志/脚本目录。整理目标进程、so、稳定命令、失败日志、剩余问题；只有需要使用 IDA 导出数据时，才探测 IDA 目录并显式复制/安装 `INP.py` 到 `<IDA目录>/plugins/INP.py` 或项目 `scripts/INP.py` 并校验。
2. **写入分析计划**：按实验记录详细模板追加本轮记录；没有代码改动写"无"，没有运行命令写"无"，检测代码未确认写"待静态分析"。
3. **动态定位（先定工具路线）**：进入注入前评估 `.text` CRC/强反 Frida、判断任务是"过检测"还是"分析算法"，按速查第3条选路线（详见 `references/workflow-standards.md` §9.0）。选 HWBP 路线时直接跳到第8步，第4-7步按需回看。选 Frida 时优先 hook linker `call_constructors`、同时监控 `dlopen`；spawn/attach/早期注入异常必须先完成锁屏/解锁/必要 reboot 复测闭环，再继续判断检测链或工具链。进入工具动作前做"工具命中检查"映射到内置脚本（先看 `references/bundled-tools.md` 索引）。
4. **syscall 证据**：用 `syscall-filter` 捕获 direct syscall、kill/tgkill、exit/exit_group、abort、faccessat/openat、mmap/mprotect、SIGSEGV/SIGTRAP/BRK、pc/lr/sp。闪退、崩溃、退出必须确认 pc/lr 落在 so/系统库/匿名 RX/memfd/未知映射。详见 `references/workflow-standards.md` §3。
5. **静态分析**：先执行加密/壳化硬门禁；磁盘 so 加密、壳化、自解密或运行时重建时，禁止直接分析磁盘 so，必须 dump/fix 运行期 so 或真实可执行段并校验后再进 IDA。闪退/崩溃/退出案例进入 IDA 后，必须按 `.init`→`.init_array`/constructor→`JNI_OnLoad`/RegisterNatives→匿名 RX/memfd 映射与跳转证据→CRC/完整性校验→崩溃点所在函数及上下游的顺序推进；未完成前禁止动态验证或 patch 候选。匿名执行硬门禁（`references/workflow-standards.md` §5）、函数范围（§6）、OLLVM（§8）、CRC（§9.1/§9.2）和完整 fatal 路径分析必须完成后再提 patch。
6. **检测链整理**：每个 so/函数都要记录分析思路、所用工具、命令、代码改动、完整检测代码明细、关键结论和下一步；不强制维护 per-so、per-function 或 patch 表，但不得遗漏已分析出的检测代码细节。详见 `references/documentation-standards.md`。
7. **patch**：详见 `references/workflow-standards.md` §10。
8. **内核无痕 hook（主力分析或验证）**：分析算法且有 Frida 检测时 HWBP 为首选主力；过检测/Frida 路线下禁止把 HWBP/stealth-hook 作为主流程，只能用 HWBP 无痕验证参数、返回值或 patch 候选。先记录 APatch/KPM/pid/so/offset/回退。详见 `references/tooling-and-paths.md`「stealth-hook 使用要点」。
9. **验证闭环**：固定命令复测，命令、结果和差异写入实验记录。同一 so/函数/检测链/调度链内有效动态测试失败累计 3 次后，禁止继续动态叠加 hook、patch 或 runner 变量，必须回到 so 与匿名段代码的完整静态分析。详见 `references/workflow-standards.md` §11 与 `references/verification-checklists.md`。

## 输出标准

最终或阶段性回复遵循：结果 → 关键证据 → 已修改文件/patch 点 → 验证情况 → 下一步。不贴大段原始日志，只摘决定性行并给文件路径。实验记录使用详细模板，并包含分析思路、所用工具、运行命令、代码改动和完整检测代码明细。

## 文档入口

- `references/overview.md`：版本信息、功能总览、工具依赖和快速安装。
- `references/workflow-standards.md`：完整执行流程与各强约束详述（§5 匿名内存、§6 函数范围、§7 静态分析顺序、§8 混淆、§9 工具路线与 CRC、§10 patch、§11 验证）。
- `references/documentation-standards.md`：实验记录详细标准。
- `references/tooling-and-paths.md`：工具链、路径、命令规范、jadx/IDA/stealth-hook 要点。
- `references/bundled-tools.md`：内置工具索引和按任务读取路由。
- `references/tool-installation.md`：安装复制、`--audit`、`--self-check`、`INP.py` 显式复制/安装规则。
- `references/syscall-frida-tools.md`：syscall-filter、Frida 联合采集、关键证据提取。
- `references/dump-ida-ollvm-tools.md`：MemDumper 分流、dump/fix、IDA 导出、函数范围修正、OLLVM 还原。
- `references/stealth-ecapture-tools.md`：内核无痕 hook、eCapture。
- `references/cross-platform.md`：Windows/Linux/macOS 宿主机使用说明。
- `references/verification-checklists.md`：验证、稳定性和回归检查清单。
- `references/safety-and-confirmation-rules.md`：授权边界、记录边界和 patch 原则。

## 参考文档读取路由

- 建立流程或遇到闪退闭环：读 `references/workflow-standards.md`。
- 不确定工具入口或想按任务分流：读 `references/bundled-tools.md`。
- 需要复制工具、自检、审计、`INP.py` 安装语义：读 `references/tool-installation.md`。
- 需要 syscall-filter、Frida 联合采集或证据提取：读 `references/syscall-frida-tools.md`。
- 需要 MemDumper/INP/IDA/OLLVM：读 `references/dump-ida-ollvm-tools.md`。
- 需要 stealth-hook 或 eCapture：读 `references/stealth-ecapture-tools.md`。
- 需要路径、环境变量、jadx/IDA 规则或跨工具约束：读 `references/tooling-and-paths.md`。
- 要写实验记录：读 `references/documentation-standards.md` 并使用详细模板。
- 要验证稳定性或复盘失败：读 `references/verification-checklists.md`。
- 涉及宿主机差异：读 `references/cross-platform.md`。
- 涉及授权、记录边界或 patch 边界：读 `references/safety-and-confirmation-rules.md`。
- 需要查看版本信息：读 `references/overview.md`。

## 常用脚本入口

- `scripts/install_skill_tools.py`：复制内置工具到工程、审计、自检；`--with-runner` 不复制 `INP.py`，需要 IDA 导出时显式用 `--with-inp`、`--install-ida-plugin`、`--ida-root` 或 `--ida-plugin-dir`。
- `scripts/init_reverse_workspace.py`、`scripts/make_experiment_note.py`、`scripts/collect_key_evidence.py`：初始化工程、写实验记录、提取关键证据。
- `scripts/tools/`：实际工具和 wrapper。按 `references/bundled-tools.md` 的路由读取对应工具文档，不在 `SKILL.md` 展开。

资产模板见 `assets/templates/`。
