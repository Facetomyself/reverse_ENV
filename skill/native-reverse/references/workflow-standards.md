# 工作流标准

> 语言规则（全程中文）见 `SKILL.md` 速查清单第1条。本文件是工具路线（§9.0）、CRC（§9.1/§9.2）、匿名内存检查（§5）、函数范围确认（§6）、静态分析顺序（§7）、混淆处理（§8）、patch 决策（§10）、验证闭环（§11）等强约束的唯一详述出处。

## 目录

- 0. 先读上下文
- 1. 开始本轮记录
- 2. 早期加载监控
- 3. syscall-filter 定位
- 4. 新 so 或匿名 RX 处理
- 5. 匿名内存加载执行检查
- 6. 函数范围确认
- 7. 静态分析推进顺序
- 8. 混淆处理
- 9. 工具路线与 CRC / 完整性校验处理
- 10. Patch 决策
- 11. 验证闭环

## 0. 先读上下文

每次接手先读取：

- `CLAUDE.md` 或项目规则。
- 项目 `README.md`、已有实验记录、分析记录、复现文档。
- `logs/`、`dumps/`、`scripts/`、`third_party/` 的现状。
- 当前稳定 Frida JS、runner、bypass 脚本、patch 表。

不要凭记忆继续。若发现对话、日志、文档不一致，以可复现运行结果和明确的文件证据为准。

不要在接手或任务开始时一次性检查所有工具环境。只在本轮实际要使用 Frida、syscall-filter、MemDumper、stealth-hook、eCapture、jadx、IDA、adb 前，检查对应工具和设备前置；未使用的能力不检查、不阻塞。

只有需要使用 IDA 导出数据时，才探测 IDA 安装目录和现有 `plugins` 目录，并显式复制/安装项目 Skill 内置 `scripts/tools/INP.py` 到 `<IDA目录>/plugins/INP.py` 或项目 `scripts/INP.py`，随后用哈希或文件大小校验。找不到 IDA 或 `plugins` 目录时，在实验记录写明原因；后续拿到路径并需要导出时再补装。

## 1. 开始本轮记录

开始分析前，在实验记录中追加详细记录：

- 记录时间。
- 分析思路。
- 本轮操作。
- 操作目的。
- 所用工具。
- 运行命令。
- 代码变更。
- 检测代码明细。
- 实验结果。
- 下一步计划。

每轮都必须边分析边写，不能等分析结束后凭记忆补。分析思路写清当前假设、证据来源和要验证/排除的判断；所用工具和运行命令写实际工具、路径/版本（已知时）、命令、参数、工作目录和目标。所有已分析出的检测代码都要写入“检测代码明细”，包括 so/函数/offset、伪代码或关键汇编、判断条件、常量/字符串、syscall/API、返回值/状态码、fatal/kill/abort/BRK 分支和上下游调用；不得只写一句“检测 Frida/Root/CRC”。

涉及新 `.so` 工具逆向且用户未明确授权直接分析时，先按 `safety-and-confirmation-rules.md` 走 `.so` 逆向确认流程；已有 IDA 导出可直接分析，并在实验记录中说明。

只有本轮需要使用 `adb`、IDA、`jadx` 等工具且路径未命中时，才检查 `PATH`、项目 `scripts/`、`third_party/`、已有实验记录和常见安装路径。若本轮确实需要 `jadx` 或 IDA 且仍未命中，继续做宿主机全盘搜索，并把搜索命令、范围、命中候选或未命中结果写入实验记录；全盘仍找不到时才询问用户路径。`adb` 等通用工具不要求全盘搜索，按常规路径排查后仍找不到即可询问用户。

工具选择是硬约束：

- Java/Kotlin 层强制使用 `jadx`。只有用户明确表示没有 `jadx` 或无法提供路径后，才允许换用其他 Java 反编译工具，并记录用户答复和替代原因。
  - 调用 `jadx` 必须关闭 dex checksum 校验（完整条款见 `tooling-and-paths.md`）：命令行加 `-Pdex-input.verify-checksum=no`，`jadx-gui` 在设置中关闭；所用参数写入实验记录。
- `.so` 分析强制使用 IDA。只有用户明确表示没有 IDA 或无法提供路径后，才允许换用 Ghidra/radare2/objdump 等工具，并记录用户答复和替代原因。

## 2. 早期加载监控

Native 早期加载不要只靠轮询模块：

- 优先 hook linker 的 `soinfo::call_constructors` 或等价 constructor 入口。
- 同时 hook `dlopen`、`android_dlopen_ext` 和返回值。
- 需要落盘时，在实验记录中写明 so 名称、关键时机、所用工具、运行命令、检测代码明细和结论。
- 需要 dump 加密、自解密、壳化或运行时重建的 so 时，优先在 `call_constructors` 命中时 dump/fix；无法覆盖该时机时，再选择 `dlopen/android_dlopen_ext` 返回后、JNI_OnLoad 前后或 maps 稳定后的时机，并记录原因。
- **硬门禁：使用 Frida 前先确认 frida-server 已启动**。任何 `frida-ps`、spawn、attach、runner 或 Frida hook 前，必须先用设备侧 `ps`/`pidof` 确认 frida-server 活跃进程；若未启动，先在 `/data/local/tmp` 查找 `frida-server*` 并用已有文件启动；若没有找到 frida-server 文件，停止 Frida 动作并询问用户 frida-server 路径。不能把仅能枚举设备或进程当作 frida-server 已启动证据。
- **硬门禁：禁止自行更换 Frida 版本**。发现宿主 Frida 与设备端 frida-server 版本不匹配时，只能记录风险并建议用户自行更换；禁止自行安装/升级 Python Frida 包、创建/切换 venv、推送替换 frida-server 或改用其它版本。
- **硬门禁：Frida spawn/attach 异常先设备状态闭环**。Frida spawn、spawn-gating、attach、早期注入或 runner 出现长时间卡住、`closed`、server 不可用、启动后立刻断开、目标未起或只剩 server 可见时，必须按顺序先检查设备是否亮屏/解锁，执行唤醒解锁后复测；仍异常时执行 `adb reboot`，等待设备恢复、确认解锁状态、重新启动 frida-server，再用同一最小命令复测。该闭环完成前，禁止优先归因到 frida 版本、端口、脚本问题、目标检测链或继续叠加 hook/patch。复测命令、结果和判断写入实验记录。

## 3. syscall-filter 定位

`xiaojianbang-syscall-filter` 是闪退、崩溃、退出定位的硬门禁，也用于补足 Frida libc hook 看不到的 direct syscall：

- 捕获 `kill/tgkill/exit/exit_group`。
- 捕获 `abort`、低地址自毁、`SIGKILL/SIGSEGV/SIGTRAP/BRK` 的触发上下文。
- 捕获 `faccessat/openat/readlinkat/stat` 等 root/hook/环境路径探测。
- 捕获 `mmap/mprotect(PROT_EXEC)`、`memfd_create`，确认匿名 RX、memfd 或新可执行段来源。
- 记录 pc/lr/sp、线程、pid/tid、syscall 号、参数和返回值；对比 pc/lr 是否落在 App native 段、系统库、匿名 RX、memfd 或未知映射，区分系统生命周期终止与 App 检测 kill。
- 任何闪退、崩溃、退出、低地址自毁或主动终止，必须先用 syscall-filter 明确 syscall 与 pc/lr/sp 归属。若落在 so、匿名 RX 或 memfd，必须 dump/fix 对应 so/内存范围后再进入 IDA 静态分析；未完成前只能补证据，禁止继续 Frida 动态试错、给 patch 候选或下检测链结论。

## 4. 新 so、加密壳 so 或匿名 RX 处理

发现新加载 so 或匿名 RX 崩溃时：

1. 记录加载时机、base、size、maps 权限和触发日志。
2. **加密/壳化硬门禁**：必须判断磁盘 so 是否加密、壳化、自解密或运行时重建。判断依据包括但不限于 section table 异常、动态段/字符串表异常、IDA/objdump 只能识别导入桩或少量函数、磁盘代码与运行 pc/lr 不一致、constructor 解密/重建代码、运行期 `mprotect(PROT_EXEC)`/匿名 RX/memfd、壳入口或 wrapper 类加载。任一命中时，禁止直接分析磁盘 so 下检测链结论、patch 候选或动态验证；必须先 dump/fix 运行期 so 或真实可执行匿名段，并校验 ELF/readelf/IDA 可导入结果。
3. dump 指定 so 或匿名内存段，dump 时机优先选择 `soinfo::call_constructors`。constructor 短窗口、快速闪退或运行时重建 so 必须优先用 `frida_memdump_so.py` 或等价短窗口联动；稳定进程才用 `memdump_so.py` 库模式。dump/fix 失败时只能补日志、maps、时机和工具证据，不得回退为直接分析磁盘 so。
4. 修复 ELF wrapper 或重建 ELF，并记录产物路径、base/偏移口径、校验命令和结果。产物未校验通过前，不得进入 IDA 结论或 patch 候选。
5. dump/fix 完成后、进入 IDA 静态分析前，必须通过匿名执行硬门禁。不能默认 dump 出的 `.text` 就是真正执行的代码；必须检查运行期映射里是否存在 `rwx`、匿名 `r-x`（无文件名或 `[anon:...]`）、`memfd`、可疑 `[anon:.bss]` 等，并确认该 so 是否通过 `mmap(PROT_EXEC)`+`mprotect`、`memfd_create`、运行时解密把关键函数/检测逻辑搬到匿名内存执行。硬门禁证据：
   - syscall-filter 抓 `mmap/mprotect(PROT_EXEC)`、`memfd_create`；
   - 对比崩溃/调用 `pc/lr` 落在磁盘 so 段还是匿名段；
   - 检查 so 的 `.init_array`/constructor/JNI_OnLoad 是否申请并跳入匿名 RX。
   若关键逻辑在匿名内存或 memfd，必须先 dump 该匿名段并 fix/对齐后以其为准分析，patch 候选与 `pc/lr` 归属必须以匿名段产物为准。maps、syscall 来源、`pc/lr` 归属、跳转证据和记录落盘是继续 IDA 语义分析、patch 候选或动态验证前的必备项；缺项时停止推进并补证据。
6. 生成 IDA 可导入文件；只有用户明确没有 IDA 或无法提供路径时，才准备 Ghidra/radare2/objdump 回退产物。
7. 用 IDA 导出反编译/反汇编文本。
8. 执行“函数范围确认”强约束；范围不正常时修改函数起止范围并重新导出。
9. 若函数存在 OLLVM/CFF、dispatcher 状态机、间接跳转/间接调用、虚假控制流或魔改状态变量，先用项目副本 OLLVM_Deobfuscator 还原，必要时按目标样本修改项目副本工具代码并记录。
10. **闪退静态入口顺序硬门禁**：闪退/崩溃/退出案例进入 IDA 后，必须先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives/JNI bridge；这些入口未完成前，不得跳到崩溃点局部函数、CRC 局部函数或动态验证。
11. 入口分析完成后，必须按顺序检查匿名内存映射与跳转证据、CRC/完整性校验、崩溃点所在函数及其上游调用者/下游关键调用、所有 fatal/返回分支、常量、字符串、系统交互和状态码。该顺序是闪退检测案例的硬门禁，不是建议。
12. 找到明确 patch 位置后，且 §10-§11 已完成并写入实验记录，才允许回到 Frida/stealth-hook 动态验证关键分支、参数和返回值；若 2-3 轮验证仍在同一函数或调度链内迁移崩溃，必须停止继续试 patch，回到完整函数分析。

## 5. 匿名内存加载执行检查

so dump/fix 后、进入静态分析前必须检查有无匿名内存映射。加固壳常把真正的检测/校验逻辑解密到匿名 RX 内存执行，磁盘或 dump 出的 `.text` 可能只是空壳或诱饵；不先检查会增加检测链误判和 patch 失效风险。若磁盘 so 已被判定为加密、壳化、自解密或运行时重建，必须先完成 §4 的 dump/fix 硬门禁，再执行本节；不得用磁盘 so 的 `.text` 代替运行期代码分析。

这是静态分析前的硬门禁。进入 IDA 结论、函数语义归纳、patch 候选或动态验证前，必须完成以下证据；无法完成时停止推进并补采，不得用“证据不足”继续下结论或 patch：

1. **运行期映射检查**：必须检查目标进程运行期映射中是否存在 `rwx`、匿名 `r-x`（无文件名或 `[anon:...]`）、`memfd`、可疑 `[anon:.bss]` 段；必须拉取 `/proc/<pid>/maps` 并保留到项目 `artifacts/` 或 `logs/`，标明 pid、进程名、采集时机。
2. **syscall 来源证据**：必须用 syscall-filter 抓或检索 `mmap(PROT_EXEC)`、`mprotect(... PROT_EXEC)`、`memfd_create`、`memfd` 访问；如果当前日志没覆盖这些 syscall，本轮只能补采，不能直接假定没有匿名 RX，也不能继续 patch。
3. **pc/lr 归属证据**：必须把 syscall-filter、tombstone、Frida、logcat 中关键 `pc/lr/callsite` 与 maps 比对，逐项写明落在目标 so、系统库、匿名 RX、memfd 还是未知映射。闪退/kill/自毁的 `pc/lr` 未归属时，禁止继续 patch。
4. **跳入匿名段证据**：必须检查目标 so 的 `.init_array`、constructor、JNI_OnLoad、dlopen 后回调、直接 syscall wrapper 附近是否申请匿名内存并 `BR/BLR`/间接调用到匿名段；记录已检查入口和结果。动态证据能先判定时仍要在 IDA 后补静态交叉验证。
5. **匿名段 dump/fix 证据**：若关键逻辑、崩溃 pc/lr、检测调用或间接跳转落在匿名 RX/memfd，必须 dump 该匿名段，按基址/对齐 fix 后再进入函数范围确认；后续分析、patch 候选、`pc/lr` 归属均以匿名段产物为准。
6. **实验记录证据**：必须在实验记录追加“匿名内存加载执行检查”结论，写明有/无匿名 RX、段地址范围与权限、来源 syscall、对应 so/函数、关键 `pc/lr` 归属、dump/fix 产物、结论和回退点。

硬门禁处理：

- 若关键 `pc/lr` 均落在磁盘/内存 dump 的目标 so 或系统库，且 maps、syscall-filter 与跳转检查均未发现关键逻辑跳入匿名 RX，可以继续以该 so dump 进入 IDA；实验记录必须写“未见关键检测逻辑落在匿名 RX，后续以 `<so>` dump 偏移为准”。
- 若发现关键逻辑在匿名 RX 或 `memfd`：必须 dump 该匿名段，按基址/对齐 fix 后再交给 IDA；后续函数范围、检测链、patch 候选、`pc/lr` 归属必须以匿名段产物为准。
- 若只看过磁盘 so 或 dump so、尚未检查运行期映射、未落盘 maps、未比对关键 `pc/lr`、或 syscall-filter 没覆盖 `mmap/mprotect/memfd_create`，停止分析并补证据；禁止标记风险后继续下检测链结论或 patch。

## 6. 函数范围确认

分析任何 so 函数前必须先确认函数范围，这是强约束：

- 检查 IDA 识别的函数起始地址、结束地址和基本块边界是否合理。
- 确认 syscall-filter、tombstone、Frida、logcat 中的已知 `pc/lr/callsite` 都落在正确函数范围内。
- 确认入口、跳转表、dispatcher、真实 basic block、尾部 `ret/br`、异常/fatal 分支没有被截断。
- 确认相邻函数、thunk、异常处理块、OLLVM dispatcher 没有被误合并到当前函数。
- 范围异常时，先在 IDA 中修正函数起止范围、重建函数并重新导出，再进入检测链分析。
- 实验记录必须写明函数范围、结束地址；若 IDA 初始识别错误，记录人工判断依据。
- 未确认函数范围前，禁止给出伪代码结论、patch 候选或继续动态验证。

## 7. 静态分析推进顺序

普通检测链推荐顺序：

1. `JNI_OnLoad` / `RegisterNatives` / JNI bridge。
2. `.init_array` / constructor。
3. `dlopen` 和动态解析函数。
4. 直接 syscall wrapper 和异常终止函数。
5. 字符串初始化、常量表、路径表、属性表。
6. 中心 dispatcher、状态码汇总函数、watchdog。
7. 真实检测函数。
8. helper、日志、加密/字符串解码、容器类。

如果需要反编译 Java/Kotlin 层，强制使用 `jadx`；找不到时询问用户路径，只有用户明确表示没有 `jadx` 或无法提供路径后，才允许换用其他工具，并记录用户答复和替代原因。

闪退/崩溃/退出案例使用更严格的硬门禁顺序：

1. syscall-filter 定位 syscall 与 pc/lr/sp，并确认 so、系统库、匿名 RX、memfd 或未知映射落点。
2. 判断目标 so 是否加密、壳化、自解密或运行时重建；命中时必须 dump/fix 运行期 so 或真实可执行段，禁止直接分析磁盘 so。
3. IDA 导出 dump/fix 产物，先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives/JNI bridge，记录入口函数范围和关键调用。
4. 完成匿名内存加载执行检查：maps 落盘、`mmap/mprotect(PROT_EXEC)`/`memfd_create` 来源、关键 pc/lr 归属、入口是否跳入匿名段；关键逻辑在匿名段时必须 dump/fix 匿名段。
5. 检查 CRC/完整性校验，包括自身 `.text`、libc/libart/linker、dex/APK/签名等可能目标，并确认失配执法路径。
6. 确认崩溃点所在函数范围，完整分析该函数、上游调用者、下游关键调用、fatal 分支、返回值/状态码和副作用。
7. 只有以上步骤完成并写入实验记录后，才允许提出 patch 候选或恢复动态验证。

未完成上述顺序时，只能补采证据、dump/fix、IDA 导出、函数范围修正、OLLVM 还原或写实验记录；禁止用 Frida hook、inline patch、返回值替换或 runner 变量继续动态验证。必须分析代码，不要只做动态 patch 验证。同一 so、同一函数、同一检测链或同一调度链内，动态 hook/patch/runner 覆盖等有效动态测试失败累计 3 次后，必须暂停动态验证并回到目标 so 与可疑匿名段代码的完整静态分析。

## 8. 混淆处理

遇到 OLLVM 或非标准控制流时：

- 先执行“函数范围确认”强约束，确认函数范围和结束地址。
- 在语义分析、检测链归纳、patch 候选和动态验证之前，必须先做还原；不得只看混淆伪代码局部结论就继续 patch。
- 优先使用项目目录 `third_party/OLLVM_Deobfuscator/ollvm_deobfuscator.py`。项目没有副本时，先运行 `scripts/install_skill_tools.py --with-runner` 或从项目 Skill `scripts/tools/ollvm_deobfuscator/` 复制到项目目录。
- 只修改项目副本工具代码来适配目标样本的 OLLVM 变种；不要直接修改 Skill 原始工具，除非用户明确要求更新 Skill。
- 标记 basic block、dispatcher、状态变量、真实调用点和返回点。
- 对关键偏移做 reachability slice。
- 用常量折叠、块重排、条件分支还原、伪代码手工整理。
- 现有工具不适配时，必须记录工具改动、算法假设、输入/输出 so、函数范围、还原前后关键跳转变化和失败边界。
- 还原结果必须重新导入 IDA 或重新导出关键函数文本，与 syscall-filter/Frida/日志中的 pc/lr/callsite 交叉验证。

## 9. 工具路线与 CRC / 完整性校验处理

### 9.0 工具路线按任务类型决策（先定路线）

强约束：进入 hook/patch 前，先按任务类型选工具路线，并把答复和路线记入实验记录。

Frida 路线下若 spawn/attach/早期注入异常，必须先执行 §2 的“Frida spawn/attach 异常先设备状态闭环”。未完成锁屏/解锁/必要 reboot 复测前，不得把异常作为版本、端口、脚本或检测链结论，也不得继续扩大 hook 面。

- **过检测/绕过运行类任务**（用户要"过 frida 检测""用 frida 跑起来""注入不被发现"）：即使存在 `.text` CRC 校验，也用 frida 推进。目标是让 frida 与目标共存——用 frida 定位并干掉 CRC 校验函数和反 frida 检测（让校验返回 clean、执法分支不执行、隐藏 frida 自身痕迹：端口/agent 名/线程名/maps/gadget），按"先接管 CRC 校验再注入其余 hook"的顺序，必要时用改版 frida/gadget 降低特征。
- **硬禁令**：当用户目标是"过检测""让 frida 注入后 App 正常运行""用 frida 跑起来"或"注入不被发现"时，禁止把 HWBP/`xiaojianbang-stealth-hook` 作为主流程；HWBP 在该场景只能作为辅助验证手段，用于确认参数、返回值、patch 候选或 syscall 证据，不能替代 frida 过检测路线。
- **分析算法/还原逻辑类任务**（抓参数、返回值、中间值、还原加密/签名算法）：按以下顺序选工具——
  1. 目标**没有 frida 检测**：直接用 frida（脚本灵活、开发快）。
  2. 目标**有 frida 检测**：用内核无痕 HWBP（`xiaojianbang-stealth-hook`），不改用户态内存、不触发反 frida/CRC，读寄存器/内存、dump 中间数据。
  3. HWBP **功能上不支持**所需操作（复杂脚本逻辑、主动调用函数、replace 大段逻辑、读取 HWBP 拿不到的上下文）：回到 frida，并先过掉 frida 检测（同"过检测类任务"做法），再做算法分析。
- 任务类型不明确时，先问用户目标是"过检测让 app 跑起来"还是"分析算法"；分析算法时还要确认目标是否存在 frida 检测，再选路线。

### 9.1 CRC / 完整性校验识别

强约束：静态分析时必须主动检查是否存在 CRC/完整性校验；有则优先干掉检测代码来绕过。

加固/反作弊 so 普遍对 **自身 `.text`、`libc.so`、`libart.so`**（有时含 `linker`/`linker64`、dex、apk 签名）做 CRC/hash/逐字节比对。

识别特征：
- 读 `/proc/self/maps`、`/proc/%d/maps` 定位目标库的 r-x 段。
- `openat` 目标 `.so` 文件 + `read`/`mmap`，再与内存内容做逐字节比对（文件 vs 内存）。
- 内存内容与保存的校验常量做 `memcmp`/CRC/adler/hash 循环（内存 vs 常量）。
- 校验失配后跳异常控制流：`__stack_chk_fail`、零值函数指针表间接调用、`MOV SP,#0; BR Xn` 清栈跳非法地址、`rt_tgsigqueueinfo` 自发 SIGSEGV。
- 字符串里出现 `libc.so`、`libart.so`、自身 so 名、`/proc/self/maps`、`/proc/%d/maps`、`linker` 等。

### 9.2 确认存在 CRC 校验后的处置
1. 正确做法是干掉检测代码本身：定位 CRC 校验函数与中央执法/kill 出口，让校验函数直接返回"未篡改"或让执法分支不执行。
2. 工具路线按 9.0 选择：过 frida 检测类任务用 frida 接管 CRC 校验函数；分析算法类任务无 frida 检测用 frida、有 frida 检测用 HWBP、HWBP 不支持再回 frida 过检测。可选的不改被校验 `.text` 的手段：
   - 内核无痕 HWBP（`xiaojianbang-stealth-hook`），在校验函数入口 replace-ret 让函数体不执行；
   - 改全局开关/状态变量（数据段，不在 CRC 覆盖范围内）；
   - 内核拦截 `kill/tgkill/exit_group` syscall；
   - 双映射/影子页（mremap/userfaultfd），让校验读到原始字节而执行流走 patch 后的副本。
3. 实验记录写明：任务类型与所选工具路线、检测了哪几个目标（自身/libc/libart/linker/dex/签名）、CRC 函数偏移、校验方式（文件vs内存 / 内存vs常量）、失配自毁形式、采用的绕过手段。
4. 环境注意：ART 被全局插桩的环境（如 root 设备对 `libart` 做 `RegisterNative` hook）下，对 `libart`/`libc` 的 CRC 会因系统侧改动而失配，导致未注入任何工具也崩溃；此时崩溃与 frida 无关，必须先干掉对应 CRC 检测函数，而不是归因于注入工具。

## 10. Patch 决策

patch 不限制必须最小化；可以根据静态分析和动态证据选择返回值、状态码、fatal 分支、JNI bridge、syscall wrapper、整函数禁用或成组 patch。要求是证据闭环明确、修改语义可解释、回退方法清楚，并通过固定命令验证。

每个 patch 必须记录原始行为、修改行为、命中证据、patch 范围、风险边界、回退方法和验证结果。整函数禁用或成组 patch 时，额外记录选择原因、覆盖范围、已确认不会破坏目标正常功能的依据，以及失败时的回退点。

## 11. 验证闭环

使用任何 Frida 功能前必须先确认设备端 frida-server 状态：用设备侧 `adb shell ps -A | grep frida`、`adb shell pidof <frida-server进程名>`、`adb shell su -c 'ps -A | grep -i frida'` 或等价命令确认活跃进程、路径/进程名、设备端版本与宿主 Frida 是否匹配，并写入实验记录。若未启动，先在 `/data/local/tmp` 查找 `frida-server*` 并用已有文件启动；若没有找到，询问用户 frida-server 路径。无 hook 基线运行测试前也必须执行该检查；若本轮基线目标是“无 hook 但保留 frida-server”，必须明确标注；若目标是“纯净无 Frida 环境”，发现 frida-server 正在运行时先停止或重启设备后再测。

发现宿主 Frida 与设备端 frida-server 版本不匹配时，只能把风险和建议写入实验记录并提示用户自行更换；禁止自行安装、降级、升级或切换 Frida/Frida-server 版本，也禁止自行推送替换设备端 frida-server。

Frida spawn、spawn-gating、attach、早期注入或 runner 出现卡住、`closed`、server 不可用、启动后断开、目标未起等异常时，验证闭环必须先记录并执行 §2 的设备状态闭环：亮屏/解锁检查、唤醒解锁复测、必要时 `adb reboot`、重启 frida-server、同一最小命令复测。该步骤完成前，不得把失败结论写成版本不匹配、端口暴露、脚本错误或目标检测已确认。

动态验证上限是硬门禁：

- **有效动态测试**包括新增/修改 Frida hook、inline patch、返回值替换、syscall/libc hook、spawn/child-gating/runner 覆盖策略、fork/线程/端口/maps 隐藏策略等会改变运行行为的验证轮次。
- 同一 so、同一函数、同一检测链或同一调度链内，有效动态测试失败累计 **3 次** 后，禁止继续新增或扩大动态 hook、patch、runner 覆盖、fork/线程处理、maps/端口隐藏等变量。
- 触发上限后必须转入静态闭环：先用 syscall-filter 整理 syscall 与 pc/lr/sp，再判断目标 so 是否加密、壳化、自解密或运行时重建；命中时必须 dump/fix 运行期 so 或真实可执行段，禁止直接分析磁盘 so。进入 IDA 后必须先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives，再做 maps 归属、匿名内存检查与可疑匿名段 dump/fix，核对 `mmap/mprotect(PROT_EXEC)`、`memfd_create`、匿名 `rwx/r-x`、`memfd`、`[anon:.bss]`，确认函数范围，检查 CRC/完整性校验，完整分析崩溃点函数上下游、fatal 分支和状态码。
- 未完成上述静态闭环前，只允许做不改变目标行为的证据采集，或做 dump/fix、IDA/OLLVM、日志归属整理；禁止继续用动态试错替代代码分析。
- 完成静态闭环后，可以按静态结论成组调整 patch/hook/runner 覆盖；每组调整都要在实验记录中说明分析依据、所用工具、运行命令、代码改动、检测代码明细、结果和下一步。

每轮验证都按详细模板记录；命令、日志路径、关键 offset、动态失败次数、静态分析目标、已确认检测代码和下一步，分别写进“运行命令 / 实验结果 / 检测代码明细 / 下一步计划”等对应字段。
