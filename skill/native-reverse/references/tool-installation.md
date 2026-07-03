# 工具安装、自检与复制

## 目录

- 安装到工程
- 默认行为
- IDA / INP.py 复制规则
- 自检与分发清洁

## 安装到工程

在目标工程根目录执行：

```bash
python D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --with-runner
```

Windows PowerShell：

```powershell
python D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --with-runner
```

默认复制结果：

```text
third_party/xiaojianbang-syscall-filter/
third_party/OLLVM_Deobfuscator/
third_party/MemDumper-master/
third_party/ecapture-v2.3.0-android-arm64/
third_party/xiaojianbang-stealth-hook-main/
scripts/frida_scfilter_runner.py
scripts/frida_memdump_so.py
scripts/ida_fix_function_range.py
scripts/memdump_so.py
scripts/ecapture_android.py
scripts/stealth_hook_android.py
```

注意：`--with-runner` 不复制 `INP.py`。只有需要 IDA 导出数据时，才显式复制项目批处理副本或安装 IDA 插件。

## 默认行为

- 已存在的工具目录和 runner 脚本会保留，不覆盖。
- 使用 `--force` 才直接替换已有副本。
- 使用 `--backup-existing` 会先把已有副本移动为 `.bak`/`.bak1` 后再复制。
- 使用 `--audit`/`--dry-run` 只打印将要复制或安装的路径，不写入文件。
- 使用 `--self-check` 检查内置资源、Python 语法、frontmatter 基本结构、缓存清洁度和代表性 wrapper `--help` 入口。

## IDA / INP.py 复制规则

`INP.py` 只在需要 IDA 导出数据时复制/安装：

- 项目批处理副本：显式传 `--with-inp` 或 `--install-project-inp`，复制到 `scripts/INP.py`。
- IDA 交互插件：显式传 `--install-ida-plugin`、`--ida-root` 或 `--ida-plugin-dir`，复制到 `<IDA目录>/plugins/INP.py`。

示例：

```bash
python3 D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --with-inp
python3 D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --install-ida-plugin --ida-root /path/to/ida-pro
python3 D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py . --ida-plugin-dir /path/to/ida-pro/plugins
```

IDA 插件安装触发后，目录自动探测覆盖：

- 环境变量：`IDA_PLUGIN_DIR`、`IDA_PLUGINS_DIR`、`IDA_ROOT`、`IDAPRO_ROOT`。
- `PATH` 中的 `ida`、`ida64`、`idat`、`idat64` 所在目录。
- Linux/macOS 常见目录：`~/bin`、`~/tools`、`~/Applications`、`/opt`、`/Applications`、`/usr/local` 下的 `ida-pro-*`、`IDA Pro *`、`IDA Professional *`。
- Windows 常见目录：`%ProgramFiles%`、`%ProgramFiles(x86)%`、`%LOCALAPPDATA%`，以及 `C:\Program Files`、`D:\Program Files` 等目录下的 `IDA Pro *`、`IDA Professional *`。

找不到 IDA `plugins` 目录时只提示，不中断普通工具安装；可用 `--ida-root` 或 `--ida-plugin-dir` 指定。发现多个候选时记录候选列表和最终选择。

## 自检与分发清洁

分发或复制前建议运行：

```bash
python3 D:\reverse_ENV\skill\native-reverse\scripts\install_skill_tools.py --self-check
```

Skill 内不应包含历史采集日志、`.git`、`__pycache__`、`.pyc`、编译中间文件、测试 APK 和非必需样本 so。`--self-check` 会把缓存和样本 so 视为失败项。
