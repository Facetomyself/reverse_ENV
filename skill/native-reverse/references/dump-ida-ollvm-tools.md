# Dump/fix、IDA 导出与 OLLVM 还原工具

## 目录

- MemDumper 工具分流
- Frida + MemDumper 短窗口 dump/fix
- IDA AI 输入导出
- IDA 函数范围修正
- OLLVM_Deobfuscator
- MemDumper

## MemDumper 工具分流

对 so 做静态分析前，先判断磁盘 so 是否加密、壳化、自解密或运行时重建。命中任一特征时，dump/fix 是硬门禁：禁止直接分析磁盘 so 下函数语义、检测链结论、patch 候选或动态验证，必须先 dump/fix 运行期 so 或真实可执行匿名段，并校验产物后再进入 IDA。常见命中特征包括 section/dynamic/string table 异常、IDA/objdump 只识别导入桩或少量函数、运行 pc/lr 不落在磁盘可解释代码、constructor/JNI_OnLoad 解密或重建代码、运行期匿名 RX/memfd、壳 wrapper 类或明显加固入口。

对进程内 so 做 dump/fix 时，按下面规则选工具。这个分流是强约束，用来避免短窗口场景下手工串联过慢，或稳定进程场景下重复写临时脚本。

| 场景 | 必选工具 | 理由 |
|---|---|---|
| 已知 pid 或包名，进程稳定，目标 so 已在 maps 中，dump 时不会立刻死亡 | `scripts/memdump_so.py --pid/--package --name <lib>.so` | 直接封装 MemDumper `-l -n` 库模式，最简单，默认自动 rebuild/fix |
| 目标 so 在 constructor、`dlopen/android_dlopen_ext` 返回后或 `JNI_OnLoad` 前后只有短窗口 | `scripts/frida_memdump_so.py --package ... --name <lib>.so` | Frida Python API 命中 linker constructor 后立即调用 MemDumper，减少 CLI/人工串联延迟 |
| so 较大，复制 pid、轮询 stdout 或分两条命令可能来不及 | `scripts/frida_memdump_so.py` | 宿主收到 `hold_ready` 后同步触发 MemDumper，适合抢时间 |
| 已经由 `frida_memdump_so.py` 成功拉回 fixed ELF，且 `file/readelf` 通过 | 不再重复跑 `memdump_so.py` | 两者底层都是 MemDumper `-l -n` 自动修复，重复 dump 只增加变量 |
| 库模式报 `Can't find Library`、maps 名称不匹配、拆段/匿名 RX | 先保存日志和 maps，再考虑 `memdump_so.py --manual --start --end` | 手动地址模式不是默认 fixed ELF 路径，产物必须重新校验 |

默认命令都不要加 `--manual` 或 `--raw`。`--manual` 是地址范围 dump，`--raw` 会跳过 rebuild/fix；只有库模式失败、失败证据已落盘、并明确需要原始范围时才使用。

稳定 pid 示例：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\memdump_so.py" \
  --pid 12345 \
  --name libtarget.so \
  --out-dir artifacts/dumps/libtarget_mdump \
  --timestamp-device-dir
```

短窗口示例：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\frida_memdump_so.py" \
  --package com.example.target \
  --name libtarget.so \
  --out-dir artifacts/dumps/libtarget_fast \
  --hold-ms 20000 \
  --clear-logcat
```

失败处理：

- `frida_memdump_so.py` 未生成 `hold_ready.json`：先看 `frida.log`、linker64 `call_constructors` 符号/备用偏移、包名和 Frida spawn 状态；不要先切手动地址 dump。
- 已生成 `hold_ready.json` 但 MemDumper 失败：看 `memdumper.log`、`maps.txt`、目标 so 名称和 pid 是否仍存活，再决定是否改用 `memdump_so.py --pid ... --name ...` 重试。
- `memdump_so.py` 库模式失败：保存 stdout/stderr、pid、`/proc/<pid>/maps` 或 wrapper 产物，确认 so 名称、路径、ABI 和进程状态后再考虑 `--manual`。
- 如果失败对象是已判定加密、壳化、自解密或运行时重建的 so，失败后只能补 dump 时机、maps、linker constructor、JNI_OnLoad 前后和匿名段证据；不得因为 dump 失败就回退到直接分析磁盘 so。
- `--force-stop-before` 只在需要干净启动基线时显式使用；已经命中 hold 或准备 dump 时不要 force-stop 目标进程。

## Frida + MemDumper 短窗口 dump/fix

`scripts/tools/frida_memdump_so.py` 用 Frida Python API 和 MemDumper 做短窗口联动：

- Frida spawn 目标包。
- hook linker64 `soinfo::call_constructors`。
- 目标 so 映射后用结构化 `hold_ready` 消息通知宿主。
- 宿主立即执行 MemDumper `-l -n <lib>.so` 自动 rebuild/fix。
- 拉回 fixed ELF、Frida 日志、MemDumper 日志、maps 和 hold_ready JSON。

示例：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\frida_memdump_so.py" \
  --package com.example.target \
  --name libtarget.so \
  --out-dir artifacts/dumps/libtarget_fast \
  --timestamp-device-dir \
  --hold-ms 20000 \
  --clear-logcat
```

常用选项：

- `--hold-ms`：命中目标 so 后 constructor 线程 sleep 的时间；默认 20000 ms。不要盲目设置过长，启动阶段长时间阻塞会触发 ANR。
- `--fallback-call-constructors-offset`：找不到 `__dl__ZN6soinfo17call_constructorsEv` 符号时使用的 linker64 偏移；无默认值。符号查找失败且未显式提供该偏移时，agent 不再猜测固定偏移，而是直接报错退出；显式提供时会先校验地址落在 linker 模块范围内、可读且首指令非全零/全一。
- `--keep-device-files`：保留设备端 MemDumper 输出目录。
- `--force-stop-before`：仅在需要干净启动基线时使用；已命中 hold 或正在 dump 时不要 force-stop。
- `--no-force-stop-after`：dump/timeout 后不主动清理目标 App。
- `--raw`/`--fast`：透传 MemDumper `-r`/`-f`；默认不使用，默认是自动 rebuild/fix。

产物校验：

```bash
file artifacts/dumps/libtarget_fast/libtarget.so
readelf -h artifacts/dumps/libtarget_fast/libtarget.so
readelf -d artifacts/dumps/libtarget_fast/libtarget.so
```

若该工具成功并通过 `file/readelf` 校验，进入 IDA 导出、入口函数分析和函数范围确认，不需要再跑 `memdump_so.py`。若失败，先保存 `frida.log`、`memdumper.log`、`maps.txt`、`hold_ready.json` 和 logcat，再决定是否改用 `memdump_so.py --pid ... --name ...` 或手动地址模式。对已判定加密/壳化/运行时重建的目标，失败期间禁止直接分析磁盘 so。

## IDA AI 输入导出

`scripts/tools/INP.py` 是 IDA 插件/批处理脚本，用于导出反编译、反汇编 fallback、字符串、导入导出、xref 和函数调用关系等 AI 分析输入。

导出目录强制使用：

```text
artifacts/inp/<模块名>_ida_export_for_ai/
artifacts/inp/<模块名>_deollvm_export_for_ai/
```

第二种目录只用于已经 OLLVM 还原或导出对象来自还原后 so 的场景。

IDA 批处理示例：

```bash
/path/to/idat64 -A \
  -S"/path/to/project/scripts/INP.py /path/to/project/artifacts/inp/libxxx_ida_export_for_ai" \
  target.i64
```

插件交互模式必须使用 IDA 插件目录中的 `plugins/INP.py`，可在 IDA 内通过 `Export for AI` 或 `Ctrl-Shift-E` 触发；批处理/自动化导出可使用项目副本 `scripts/INP.py`，但仍必须显式指定 `artifacts/inp/` 下的目标目录。

需要使用 IDA 导出数据时再复制/安装 `INP.py`：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py" /path/to/project --with-inp
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py" /path/to/project --install-ida-plugin --ida-root /path/to/ida-pro
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py" /path/to/project --ida-plugin-dir /path/to/ida-pro/plugins
```

分析前先检查现有 `artifacts/inp/`，不要重复导出同一版本；重导出时保留旧目录或使用时间/版本后缀，并在实验记录记录来源 so、偏移口径、`INP.py` 来源、函数范围修正和 OLLVM 状态。

## IDA 函数范围修正

`scripts/tools/ida_fix_function_range.py` 在 IDA/IDAT 内运行，用 JSON 应用已确认的函数起止范围并输出校验报告。它不自动猜范围，只落实人工确认的候选范围，适合执行“函数范围确认”强约束后重新导出。

JSON 示例：

```json
{
  "base": "0x0",
  "functions": [
    {
      "name": "xloader_ctor_dispatch",
      "start": "0x48a38",
      "end": "0x48eb0",
      "must_contain": ["0x48c94", "0x48dc0"],
      "must_not_contain": ["0x49000"],
      "reason": "constructor crash pc/lr/callsite coverage"
    }
  ]
}
```

IDA 批处理示例：

```bash
/path/to/idat64 -A \
  -S"/path/to/scripts/ida_fix_function_range.py --spec ranges.json --out reports/function_ranges.md" \
  target.i64
```

常用选项：

- `--dry-run`：只校验并输出报告，不修改 IDA 数据库。
- `--undefine-items`：在指定范围内先 undefine items，再重新创建指令和函数。
- `--base 0x...`：给 JSON 中所有地址统一加基址。

报告必须回写实验记录。若报告出现 `FAIL`，先修正范围或证据地址，不进入检测链分析、patch 候选或动态验证。

## OLLVM_Deobfuscator

用途：

- OLLVM 控制流平坦化、间接跳转、间接调用、虚假控制流的辅助还原。
- 对 IDA 无法正确识别的状态机函数做自动 patch 后再导入分析；Ghidra/radare2 仅在用户明确没有 IDA 或需要交叉验证时使用。
- 遇到 OLLVM/CFF、dispatcher 状态机、间接跳转/间接调用、虚假控制流或魔改状态变量时，必须在语义分析和 patch 候选前先还原。

项目使用规则：

- 优先使用项目副本 `third_party/OLLVM_Deobfuscator/ollvm_deobfuscator.py`，不要直接在 Skill 原始目录改工具。
- 项目没有副本时，先运行 `"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py" . --with-runner`，或从项目 Skill `scripts/tools/ollvm_deobfuscator/` 复制到项目 `third_party/OLLVM_Deobfuscator/`。
- 目标样本存在魔改 OLLVM、状态变量宽度变化、寄存器预加载、异常跳转表或模拟执行失败时，可以修改项目副本工具代码适配；必须记录改动文件、算法假设、输入/输出 so、函数范围和失败边界。
- 还原输出不能单独作为结论，必须重新导入 IDA 或重新导出关键函数文本，并与 Frida/syscall-filter/logcat 的 pc/lr/callsite 交叉验证。

基本命令：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\third_party\OLLVM_Deobfuscator\ollvm_deobfuscator.py" \
  <input.so> <start_hex> <end_hex> \
  --type auto \
  -o <output.so>
```

支持的 `--type` 参数：

```text
auto
cff
indirect
```

使用要求：

- Python 3.8+。
- `capstone`、`unicorn`、`keystone-engine`。
- 使用前先执行 `workflow-standards.md` 的“函数范围确认”强约束。
- 新 `.so` 反汇编/反编译仍需遵守授权边界和记录规则。

## MemDumper

用途：

- 从目标进程内存 dump 已加载 so。
- 支持按包名或 pid dump。
- 支持 `-l` library 模式自动按 maps 查找 so 范围。
- 默认对 so 做 ELF rebuild/fix；加 `--raw` 时只拉原始内存镜像。
- 适合新 so 加载后做 dump -> fix ELF -> IDA 导出 -> 静态分析；只有用户明确没有 IDA 或无法提供路径时，才切换到 Ghidra/radare2/objdump 回退。

Wrapper 示例：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\memdump_so.py" \
  --package com.example.target \
  --name libtarget.so \
  --abi arm64-v8a \
  --out-dir dumps/memdumper/libtarget
```

按 pid dump：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\memdump_so.py" \
  --pid 12345 \
  --name libtarget.so \
  --out-dir dumps/memdumper/libtarget_by_pid
```

手动地址范围 dump：

```powershell
"D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\workspace\<项目名>\scripts\memdump_so.py" \
  --pid 12345 \
  --manual \
  --name anon_rx_0x70000000_0x70100000.bin \
  --start 70000000 \
  --end 70100000 \
  --out-dir dumps/memdumper/anon
```

注意：

- 需要设备 root，wrapper 会把对应 ABI 的 `memdumper` push 到 `/data/local/tmp/xjb_memdump/`。
- 默认会清理 `--device-dir` 后再 push；需要保留旧设备文件时用 `--no-clean-device-dir`，需要避免复用目录时用 `--timestamp-device-dir`。
- Windows/Linux/macOS 宿主机都支持；`ADB=/path/to/adb` 或 `ADB=C:\path\adb.exe` 可覆盖 adb。
- `MEMDUMPER_ROOT=/path/to/MemDumper-master` 可覆盖 MemDumper 根目录。
- 64 位目标进程用 `--abi arm64-v8a`；32 位目标进程用 `--abi armeabi-v7a`。
- `memdump_so.py` 适合 dump 已经加载到 maps 且进程稳定的 so；constructor 短窗口、快速闪退或大 so 优先使用 `frida_memdump_so.py`。
- 匿名 RX 或拆段映射仍需结合 maps、Frida dump 或 wrapper 的 manual 模式；manual 产物必须用 `file/readelf` 或 IDA 重新确认可分析性。
