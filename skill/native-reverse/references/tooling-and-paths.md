# 工具链与路径规范

## 目录

- 常用工具
- 宿主机平台
- 目录建议
- Frida 监控要点
- syscall-filter 使用要点
- stealth-hook 使用要点
- Dump/fix/IDA export 要点
- 动态验证上限

## 常用工具

环境检查按需触发：不要在任务开始前统一检查所有工具。只有准备运行对应工具、脚本或能力时，才检查它的路径、版本、设备权限和内核/ABI 条件；未使用的工具不检查、不阻塞。

- Frida：启动、附加、constructor hook、dlopen 监控、runtime patch、参数/返回值验证。
- frida-server：目标设备上的 server，例如 `/data/local/tmp/fsarm64`。
- xiaojianbang-syscall-filter：定位 direct syscall、kill、SIGSEGV、faccessat、匿名 RX。
- xiaojianbang-stealth-hook：Android 内核无痕 HWBP hook，用于强反 Frida/强完整性场景下验证参数、返回值和 patch 候选。
- jadx：Java/Kotlin 层反编译强制使用。PATH、项目目录、已有记录和常见安装路径找不到时，必须先做宿主机全盘搜索；全盘仍找不到才询问用户路径。只有用户明确表示没有或无法提供路径后，才允许换用其他 Java 反编译工具，并在实验记录中说明原因。**强约束：调用 jadx 必须关闭 dex checksum 校验**，命令行加 `-Pdex-input.verify-checksum=no`（如 `jadx -Pdex-input.verify-checksum=no app.apk`），`jadx-gui` 在设置中关闭 checksum 校验。
- IDA：`.so` 反编译/反汇编强制使用。PATH、项目目录、已有记录和常见安装路径找不到时，必须先做宿主机全盘搜索；全盘仍找不到才询问用户路径。只有用户明确表示没有或无法提供路径后，才允许换用 Ghidra/radare2/objdump 等工具，并在实验记录中说明原因。
- Ghidra/radare2/objdump：仅作为用户确认没有 IDA 或无法提供 IDA 路径后的回退，或在 IDA 结果之外补充交叉验证。
- OLLVM_Deobfuscator：处理 OLLVM 或非标准控制流；混淆函数必须在语义分析和 patch 候选前先还原，优先使用并按需修改项目副本 `scripts/tools/ollvm_deobfuscator/`。
- adb/logcat：进程控制、日志采集、重启设备、清理状态。

只有本轮需要使用 `adb`、IDA、`jadx` 等工具且找不到位置时，才检查 `PATH`、项目 `scripts/`、`third_party/`、已有实验记录和常见安装路径；若本轮确实需要 `jadx` 或 IDA 且仍未命中，必须继续做宿主机全盘搜索，不要凭空假设路径。全盘搜索命令、范围、候选和结果写入实验记录；全盘仍找不到时才询问用户路径。用户明确说没有 `jadx` 或 IDA 后，才能切换对应回退工具。

`jadx`/IDA 全盘搜索建议：
- Windows：枚举本机文件系统盘，搜索 `jadx.bat`、`jadx-gui*.exe`、`jadx*.bat`、`ida64.exe`、`ida.exe`、`idat64.exe`、`idat.exe`；可跳过回收站、系统卷信息、网络盘和无权限目录。
- Linux/macOS：用 `find` 或 `mdfind/locate` 搜索 `jadx`、`jadx-gui`、`ida64`、`ida`、`idat64`、`idat`；可跳过 `/proc`、`/sys`、`/dev`、网络挂载和无权限目录。

当前项目已知路径：JDK 21 在 `tools/jdk/`，Node.js 20.20.2 在 `tools/node/`，jadx 1.5.5 在 `tools/jadx/`，IDA Pro 9.3 在 `resource/portable_win/`，adb 在 `tools/adb/`。`scripts/tools/` 下已内置 `xiaojianbang-syscall-filter`、`xiaojianbang-stealth-hook-main`、`MemDumper`、`ollvm_deobfuscator` 等工具。全盘搜索时优先跳过上述已知路径；在目标工具确实不在已知路径时才启动全盘搜索。

只有需要使用 IDA 导出数据时，才探测 Windows/Linux/macOS 常见 IDA `plugins` 目录并复制/安装 `INP.py`。执行 `scripts/install_skill_tools.py` 默认不写入 IDA 目录，也不复制项目 `scripts/INP.py`；需要项目批处理副本时显式用 `--with-inp` 或 `--install-project-inp`，需要安装插件时显式使用 `--install-ida-plugin`、`--ida-root` 或 `--ida-plugin-dir`。可用 `IDA_PLUGIN_DIR`、`IDA_PLUGINS_DIR`、`IDA_ROOT`、`IDAPRO_ROOT` 覆盖；发现多个候选时记录候选列表和最终选择。

## 宿主机平台

宿主机支持 Windows、Linux 和 macOS。跨平台优先使用本 Skill 的 Python wrapper；`.sh` 脚本只作为 Linux/macOS/WSL/Git Bash 入口。

## 目录建议

通用工程建议：

```text
docs/
logs/
dumps/
scripts/
third_party/
so/
```

当前案例中已验证过的依赖放置方式：

```text
scripts/tools/xiaojianbang-syscall-filter/
scripts/tools/ollvm_deobfuscator/
scripts/tools/xiaojianbang-stealth-hook-main/
```

外部依赖进入项目时应复制到工程内，而不是只引用绝对路径。文档中保留原路径和复制后路径。

## Frida 监控要点

- 早期 so：hook constructor，不只轮询模块名。
- 加密、自解密、壳化或运行时重建 so：优先在 `soinfo::call_constructors` 或等价 constructor 入口命中时 dump/fix。
- 后续 so：同时 hook `dlopen/android_dlopen_ext`。
- 对会早期自解密或 mmap 匿名 RX 的目标 so，必须监控 `mmap/mprotect` 和 maps。
- Frida spawn 长时间卡住或无法启动时，先检查设备是否锁屏；尝试唤醒、解锁，必要时 `adb reboot` 后重测。

## syscall-filter 使用要点

采集时记录：

- 启动命令。
- 目标包名和进程名。
- filter 配置。
- 输出日志路径。
- 关键 syscall 摘录。
- 与 Frida/logcat 的时间线对应关系。

如果 syscall-filter 证明 direct syscall 命中，而 Frida libc hook 没看到调用，应在文档中明确说明这是绕过 libc hook 的 direct syscall。

检测输出里的 `libcapture` 和 `libtrace` 字符串通常是无 hook 基线运行的背景流量，不作为目标 App 检测结论；只有和目标调用栈、pc/lr、文件访问或崩溃时间线相互印证时才升级为有效证据。

## stealth-hook 使用要点

`xiaojianbang-stealth-hook` 适合 Frida/inline hook 影响目标行为时使用：

- 仅在准备使用 stealth-hook 前确认 APatch/KernelPatch、KPM 加载状态和目标设备 arm64/GKI 条件。
- 记录 `pid`、`so`、`offset`、`dump-size`、是否 `replace-ret`、是否 `modify-arg`。
- 只 hook 低频目标函数或基本块入口；不要 hook 高频 libc 通用函数。
- 每轮验证结束后执行 `--unhook` 或确认 Ctrl+C 已自动清理。
- 通过 `scripts/stealth_hook_android.py` 运行时，工具优先使用工程内 `scripts/tools/xiaojianbang-stealth-hook-main`。

## Dump/fix/IDA export 要点

dump、fix、IDA export 的产物路径、运行命令、检测代码明细和关键结论必须写入实验记录；不要求为每个 dump 维护额外长字段表，但不得遗漏已分析出的检测代码。新增或重导出时，只有确实需要导出才显式复制/安装 `INP.py` 到 IDA 插件目录或项目 `scripts/INP.py`。交互导出优先使用 IDA 插件目录中的 `plugins/INP.py`，批处理/自动化可使用项目副本 `scripts/INP.py`，输出到 `artifacts/inp/<模块名>_ida_export_for_ai/` 或 `artifacts/inp/<模块名>_deollvm_export_for_ai/`。

强约束：dump/fix 完成后、IDA 分析前先做"匿名内存加载执行检查"（完整条款见 `workflow-standards.md` §5）；检查结果、命令、证据路径和相关检测代码写入实验记录，未完成前禁止凭磁盘/dump so 的 `.text` 下检测链结论或 patch。
- IDA 导出后先执行 `workflow-standards.md` §6 的"函数范围确认"；范围不正常时修改 IDA 识别的函数范围并重新导出，再进入检测链分析。
- 函数范围确认后若发现 OLLVM/CFF、dispatcher 状态机、间接跳转/调用、虚假控制流或魔改状态变量，先用项目副本 OLLVM_Deobfuscator 还原（详见 `workflow-standards.md` §8）；项目没有副本时先复制/安装 Skill 内置工具到项目目录，工具不适配时修改项目副本代码并记录，不直接改 Skill 原始工具。

崩溃定位闭环必须包含 syscall-filter 定位、确认 so/匿名内存落点、加密/壳化/自解密/运行时重建判断、必要的 MemDumper dump/fix 运行期 so 或真实可执行段、IDA 静态代码分析和 patch 验证。闪退/崩溃/退出案例进入 IDA 后，必须先分析 `.init`、`.init_array`/constructor、`JNI_OnLoad`/RegisterNatives，再分析匿名内存映射、CRC/完整性校验、崩溃点所在函数及上下游；未完成前禁止动态验证。同一 so、同一函数、同一检测链或同一调度链内，动态验证失败累计 3 次后，必须暂停验证并回到目标 so 与可疑匿名段代码的完整函数分析。

## 动态验证上限

可以按静态分析结论成组调整 patch、hook、runner 覆盖和隐藏策略；调整依据、所用工具、运行命令、代码改动、检测代码明细、结果和下一步都要写入实验记录。

同一 so、同一函数、同一检测链或同一调度链内，动态 hook/patch/runner 覆盖等有效测试失败累计 3 次后，禁止继续新增或扩大动态变量；必须先完成 so 和可疑匿名段的 dump/fix、匿名内存检查、IDA 导出、函数范围确认、CRC 检查和完整函数分析。
