# 跨平台宿主机支持

## 目录

- 支持范围
- 推荐入口
- adb 路径
- Frida
- `.sh` 脚本边界
- Windows 编码
- 路径写法
- 工具覆盖变量
- IDA / INP.py
- xiaojianbang-stealth-hook
- OLLVM_Deobfuscator

## 支持范围

宿主机支持：

- Windows 10/11 + Python 3.8+
- Linux + Python 3.8+
- macOS + Python 3.8+

目标侧仍是 Android。只在准备使用对应工具时检查其 Android 设备能力；未使用的工具不做环境检查、不阻塞当前任务：

- Frida：设备端需运行匹配架构的 `frida-server`。
- syscall-filter：设备需 root、APatch/KernelPatch 和 KPM 加载环境。
- stealth-hook：设备需 root、arm64、GKI 5.4+、APatch/KernelPatch 和 KPM 加载环境。
- MemDumper：设备需 root，目标进程 ABI 要匹配 `arm64-v8a` 或 `armeabi-v7a`。
- eCapture：Android arm64，root，内核通常需要 aarch64 5.5+ 和 eBPF/BTF 能力。

## 推荐入口

跨平台优先使用 Python wrapper：

```text
scripts/frida_scfilter_runner.py
scripts/frida_memdump_so.py
scripts/memdump_so.py
scripts/ecapture_android.py
scripts/stealth_hook_android.py
scripts/install_skill_tools.py
scripts/init_reverse_workspace.py
scripts/make_experiment_note.py
scripts/collect_key_evidence.py
```

这些脚本避免依赖宿主机 shell 特性，Windows/Linux/macOS 都可运行。

## Windows 编码

Windows PowerShell 读取中文 Markdown、实验记录和中文日志时必须显式 UTF-8，避免先输出乱码再重读：

```powershell
Get-Content -LiteralPath .\docs\experiment_record.md -Encoding UTF8 -Raw
Get-Content -LiteralPath .\logs\some_log.txt -Encoding UTF8 -Tail 80
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

读取 Skill 自身或 `references/*.md` 时也使用 `-Encoding UTF8`。需要用脚本处理时优先用 Python 显式编码：

```python
from pathlib import Path
text = Path("docs/experiment_record.md").read_text(encoding="utf-8", errors="replace")
```

不要先用 PowerShell 默认编码读取中文文件，再向用户汇报“第一次输出编码错乱，我先用 UTF-8 重读”。首次读取就应指定 UTF-8。

## adb 路径

路径选择顺序：

1. `ADB`
2. 当前工程 `third_party/aosp/platform-tools/adb` 或 `adb.exe`
3. 当前工程 `third_party/platform-tools/adb` 或 `adb.exe`
4. `PATH` 中的 `adb`

Windows 示例。稳定进程选 `memdump_so.py`，constructor 短窗口、快速闪退或大 so 选 `frida_memdump_so.py`，二者不要无理由重复执行：

```powershell
$env:ADB = "C:\Android\platform-tools\adb.exe"
# 稳定 pid/包名场景
python scripts\memdump_so.py --package com.example.target --name libtarget.so --out-dir dumps\memdump
# 短窗口场景
python scripts\frida_memdump_so.py --package com.example.target --name libtarget.so --out-dir dumps\frida_memdump
```

Linux/macOS 示例。稳定进程选 `memdump_so.py`，constructor 短窗口、快速闪退或大 so 选 `frida_memdump_so.py`，二者不要无理由重复执行：

```bash
export ADB=/path/to/platform-tools/adb
# 稳定 pid/包名场景
python3 scripts/memdump_so.py --package com.example.target --name libtarget.so --out-dir dumps/memdump
# 短窗口场景
python3 scripts/frida_memdump_so.py --package com.example.target --name libtarget.so --out-dir dumps/frida_memdump
```

## Frida

宿主机安装：

```bash
python -m pip install frida-tools frida
```

Windows PowerShell 示例：

```powershell
python scripts\frida_scfilter_runner.py `
  --package com.example.target `
  --script scripts\agent_main.js `
  --duration 120
```

`--uid` 通常可省略，runner 会自动解析目标包 uid；解析失败时再手动传入。

Linux/macOS 示例：

```bash
python3 scripts/frida_scfilter_runner.py \
  --package com.example.target \
  --script scripts/agent_main.js \
  --duration 120
```

## `.sh` 脚本边界

`xiaojianbang-syscall-filter` 自带跨平台入口：

- Linux/macOS：直接运行 `load.sh`、`capture_live.sh`、`capture_test.sh`。
- Windows PowerShell：使用 `load.ps1` 执行 KPM 加载、卸载、状态和 `ctl` 控制；采集建议继续用 Python wrapper 或 WSL/Git Bash 运行 `capture_*.sh`。
- `load.sh`、`capture_live.sh`、`capture_test.sh`、`resolve.py` 都按 `ADB` -> PATH 中 `adb` 的顺序选 adb，不再写死宿主机路径。
- `load.sh` 和 `load.ps1` 用 `KP_SUPERKEY` 传入 KernelPatch/APatch superkey。

跨平台优先用：

- `frida_scfilter_runner.py` 采集 scfilter dmesg 和 Frida/logcat。
- `adb shell su -c "<kpatch ctl 命令>"` 直接控制设备端 KPM。

Windows PowerShell 示例：

```powershell
$env:ADB = "D:\reverse_ENV\tools\adb\adb.exe"
$env:KP_SUPERKEY = "your-superkey"
.\load.ps1 push
.\load.ps1 load
.\load.ps1 ctl resolve=on
.\load.ps1 status
```

## 路径写法

- 文档中命令用 `/` 表示通用路径；Windows 可用 `\` 或 `/`。
- Python wrapper 接受 `Path` 参数，Windows 路径含空格时使用引号。
- 输出目录会自动创建。

## 工具覆盖变量

- `ADB`：adb 路径。
- `SYSCALL_FILTER_ROOT`：syscall-filter 根目录。
- `MEMDUMPER_ROOT`：MemDumper 根目录。
- `ECAPTURE_ROOT`：eCapture 根目录。
- `STEALTH_HOOK_ROOT`：xiaojianbang-stealth-hook 根目录。
- `KP_SUPERKEY`：传入 `load.sh` / `load.ps1` 使用的 KernelPatch superkey。
- `IDA_PLUGIN_DIR` / `IDA_PLUGINS_DIR`：IDA 插件目录；仅在需要 IDA 导出并显式安装 `INP.py` 时使用。
- `IDA_ROOT` / `IDAPRO_ROOT`：IDA 安装根目录；仅在需要 IDA 导出并显式安装 `INP.py` 时使用其下的 `plugins/`。

## IDA / INP.py

`scripts/install_skill_tools.py` 默认不写入 IDA 目录，也不把 `INP.py` 复制到项目 `scripts/`。需要使用 IDA 导出数据时，再显式复制项目批处理副本或安装 `INP.py` 到 IDA `plugins` 目录；自动探测覆盖环境变量、`PATH` 中的 `ida/ida64/idat/idat64`，以及常见安装目录。

显式复制项目批处理副本：

```bash
python scripts/install_skill_tools.py . --with-inp
```

显式指定 IDA 根目录：

```bash
python scripts/install_skill_tools.py . --install-ida-plugin --ida-root /path/to/ida-pro
```

显式指定插件目录：

```bash
python scripts/install_skill_tools.py . --ida-plugin-dir /path/to/ida-pro/plugins
```

Windows PowerShell 示例：

```powershell
python scripts\install_skill_tools.py . --install-ida-plugin --ida-root "C:\Program Files\IDA Pro 9.3"
```

macOS 示例：

```bash
python3 scripts/install_skill_tools.py . --install-ida-plugin --ida-root "/Applications/IDA Pro 9.3"
```

只审计将要复制的工具和 IDA 插件目标、不实际写入时：

```bash
python scripts/install_skill_tools.py . --with-runner --audit
```

交互导出优先使用 IDA `plugins/INP.py`；批处理导出可使用项目副本 `scripts/INP.py`，输出目录仍统一为 `artifacts/inp/`。两种副本都只在需要 IDA 导出时显式复制/安装。

## xiaojianbang-stealth-hook

宿主机 Windows/Linux/macOS 都可用 Python wrapper 推送和调用目标侧 arm64 工具：

```bash
python scripts/stealth_hook_android.py --push-only
python scripts/stealth_hook_android.py --kpm-hello
python scripts/stealth_hook_android.py --load-kpm
python scripts/stealth_hook_android.py --sh-status
```

trace 示例：

```bash
python scripts/stealth_hook_android.py \
  --package com.example.target \
  --so libtarget.so \
  --offset 0x4161c \
  --dump-size 96 \
  --duration 30
```

Windows PowerShell 也使用同一个 wrapper：

```powershell
python scripts\stealth_hook_android.py --package com.example.target --so libtarget.so --offset 0x4161c --once
```

注意：

- `xiaojianbang_hook`、`kpm_loader`、`sh_control` 是 Android arm64 目标侧程序，不在 Windows/Linux/macOS 宿主机本地直接运行。
- `--load-kpm`/`--reload-kpm` 依赖设备 KernelPatch supercall 和项目内置 superkey 匹配；不匹配时用 APatch App 手动加载 `/sdcard/xiaojianbang-stealth-hook.kpm`。
- wrapper 会优先使用工程内 `third_party/xiaojianbang-stealth-hook-main`，可用 `STEALTH_HOOK_ROOT` 覆盖。

## OLLVM_Deobfuscator

跨平台依赖 Python 包：

```bash
python -m pip install capstone unicorn keystone-engine
```

macOS/Windows 上如果 keystone/unicorn 安装失败，优先使用 Linux/WSL 环境执行还原脚本，再把输出 so 带回 IDA 分析；只有用户明确没有 IDA 或无法提供路径时，才使用 Ghidra/radare2/objdump 回退。

遇到 OLLVM/CFF、dispatcher 状态机、间接跳转/调用或虚假控制流时，函数范围确认后必须先还原再分析。优先运行项目副本；项目没有副本时先用安装脚本复制 Skill 内置工具。样本变种需要改代码时，只改项目副本并记录原因。

当前 Skill 内置目录是 `scripts/tools/ollvm_deobfuscator/`，安装到工程后目录为 `third_party/OLLVM_Deobfuscator/`。主命令为：

```bash
python third_party/OLLVM_Deobfuscator/ollvm_deobfuscator.py input.so 0x1000 0x2000 --type auto -o output.so
```
