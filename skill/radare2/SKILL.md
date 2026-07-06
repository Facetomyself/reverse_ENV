---
name: radare2
description: |
  Use this skill whenever the user wants to analyze binaries with radare2/r2 from the command line, including reverse engineering, disassembly, function analysis, strings/import inspection, patching, binary diffing, hex inspection, or r2 scripting. Also use it when the user mentions PE/ELF/Mach-O/DEX/WASM files together with CLI analysis, `rabin2`, `rasm2`, `radiff2`, `r2pipe`, or asks for radare2 command help on Windows/Linux/macOS.
---

# radare2

面向 `radare2` CLI 的二进制分析技能。重点是直接用命令行完成侦察、分析、定位、导出和轻量修改，不依赖 GUI。

## 适用范围

当用户有这些意图时应优先使用本 skill：

- 要用 `r2` / `radare2` 分析 `exe`、`dll`、`so`、`elf`、`apk`、`dex`、`wasm` 等文件
- 询问 `rabin2`、`rasm2`、`radiff2`、`rahash2`、`rax2` 怎么用
- 需要命令行反汇编、看函数、看字符串、看导入导出、查交叉引用、做 patch
- 需要写 `radare2` 批处理命令、`-c` 自动化命令、或 `r2pipe` 脚本

如果用户明确要 GUI 逆向、Hex-Rays 风格伪代码、或 IDA 工作流，优先考虑 `ida-reverse`。如果是网页 JS 逆向，默认路由到 `ruyi-reverse`；只有明确需要 Chrome/CDP 级断点、单步、调用栈、作用域调试且没有强反检测要求时，才路由到 `js-reverse-mcp`。

## 本机已安装

radare2 6.1.8 便携版已安装于：
```
D:\reverse_ENV\tools\radare2\bin\
```

所有命令使用绝对路径调用：
```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe
D:\reverse_ENV\tools\radare2\bin\rasm2.exe
D:\reverse_ENV\tools\radare2\bin\radiff2.exe
D:\reverse_ENV\tools\radare2\bin\rahash2.exe
D:\reverse_ENV\tools\radare2\bin\rax2.exe
```

## 先做环境确认

优先使用本机已安装路径。若不可用，检查 `D:\reverse_ENV\tools\radare2\bin\`。

## 内置资源

这个 skill 自带两个资源，优先复用，不要每次临时组织一套重复命令。

### `scripts/recon.ps1`

标准侦察脚本，适合先做第一轮概况分析。会输出：

- 基本信息
- 节区
- 导入
- 导出
- 字符串
- 可选的 `D:\reverse_ENV\tools\radare2\bin\radare2.exe -A` 自动分析摘要
- raw outputs 与 `report.md` / `findings.json` / `triage.md`

调用方式：

```powershell
powershell -File "D:\reverse_ENV\skill\radare2\scripts\recon.ps1" -TargetPath "C:\path\to\sample.exe"
```

默认会落盘到 `D:\reverse_ENV\workspace\<样本名>\radare2-recon\<样本名>-<时间戳>\`。推荐显式指定项目名：

```powershell
powershell -File "D:\reverse_ENV\skill\radare2\scripts\recon.ps1" -TargetPath "C:\path\to\sample.exe" -ProjectName "demo"
```

或指定 workspace 下的输出目录：

```powershell
powershell -File "D:\reverse_ENV\skill\radare2\scripts\recon.ps1" -TargetPath "C:\path\to\sample.exe" -OutputDir "D:\reverse_ENV\workspace\demo\radare2-recon\manual"
```

如果需要附带自动分析，脚本会调用便携版 `D:\reverse_ENV\tools\radare2\bin\radare2.exe`：

```powershell
powershell -File "D:\reverse_ENV\skill\radare2\scripts\recon.ps1" -TargetPath "C:\path\to\sample.exe" -ProjectName "demo" -RunAnalysis
```

### `references/cheatsheet.md`

当需要更多命令细节、常见场景模板、或要快速回忆语法时，读取这个速查表，而不是凭记忆硬猜。

## 已知现象

### Windows 下偶发 `.sdb` 缺失告警

某些 PE 文件在 `rabin2` 侦察时，可能出现类似下面的告警：

```text
ERROR: Cannot find ...\share\format\dll\*.sdb
```

如果主体输出仍然正常返回，通常不影响基础侦察结论，先继续分析即可。不要因为这类附带告警就直接判定分析失败。

## 基本原则

### 1. 先侦察，后深挖

不要一上来就全量自动分析。先用轻量命令确认文件类型、架构、入口点、字符串、导入表，再决定是否做 `aaa`、`aaaa` 或定向分析。

### 2. 优先最小足够命令

`radare2` 命令非常多，用户通常只需要最短路径：

- 看文件信息：`D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I`
- 看字符串：`D:\reverse_ENV\tools\radare2\bin\rabin2.exe -z`
- 看导入导出：`D:\reverse_ENV\tools\radare2\bin\rabin2.exe -i` / `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -E`
- 交互分析：`D:\reverse_ENV\tools\radare2\bin\radare2.exe <file>` 后再执行局部命令

### 3. 修改前保持谨慎

如果用户要 patch 二进制：

- 默认先只读打开：`D:\reverse_ENV\tools\radare2\bin\radare2.exe <file>`
- 只有在明确需要修改时再用写模式：`D:\reverse_ENV\tools\radare2\bin\radare2.exe -w <file>` 或会话中 `oo+`
- 修改前先告知风险，避免无意覆盖原文件

## 常用工作流

## 工作流 1：快速侦察

适合刚拿到一个二进制文件时。

优先直接运行内置脚本：

```powershell
powershell -File "D:\reverse_ENV\skill\radare2\scripts\recon.ps1" -TargetPath "sample.exe"
```

如果只需要手动最小命令，则使用：

```powershell
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -z sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -i sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -E sample.exe
```

关注点：

- 文件格式、位数、架构、平台
- 入口点地址
- 可疑字符串：URL、路径、报错、注册表、命令行参数
- 导入函数：网络、文件、加密、进程注入、注册表操作

## 工作流 2：交互式分析函数

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe sample.exe
```

进入后常用：

```text
aaa          # 常规自动分析
afl          # 列出函数
iz           # 列出字符串
iS           # 列节区
is           # 列符号
s entry0     # 跳到入口点
pdf          # 反汇编当前函数
VV           # 进入可视化模式（如果终端适合）
q            # 退出
```

说明：

- 默认优先 `aaa`，不要一开始就用更重的 `aaaa`
- 如果样本很大或分析很慢，可以只分析入口附近，再手动扩展

## 工作流 3：定位 main / 关键逻辑

```text
afl~main
afl~sym.
iz~http
iz~error
axt <addr>
```

思路：

- 先从 `main`、入口点、字符串引用入手
- 用 `axt` 查谁引用了某个字符串或地址
- 找到引用点后再 `s <addr>`、`pdf`

## 工作流 4：十六进制与内存查看

```text
px 64        # 当前地址起 64 字节十六进制
pd 20        # 反汇编 20 条指令
psz          # 读取当前地址字符串
pxa          # 更友好的十六进制视图
```

## 工作流 5：二进制 patch

仅当用户明确要求修改文件时使用：

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe -w sample.exe
```

进入后例如：

```text
s 0x401000
wa nop
wa jmp 0x401050
wq
```

常见写操作：

- `wa <asm>`：写汇编
- `wx <hex>`：写原始字节
- `wq`：写入并退出

修改前最好先备份原文件。如果用户没提备份，至少提醒一次。

## 工作流 6：非交互自动化

适合一次性输出结果：

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe -A -q -c "afl;iz;ii;q" sample.exe
```

常用参数：

- `-A`：启动时自动分析
- `-q`：安静模式
- `-c`：执行命令串

如果命令很多，优先整理成易读顺序，不要塞入难以维护的超长串。

更推荐先用内置侦察脚本打底，再决定要不要补定制命令。

## 常用子工具

### `rabin2`

适合静态信息提取：

```powershell
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I sample.exe   # 基本信息
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -S sample.exe   # 节区
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -s sample.exe   # 符号
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -i sample.exe   # 导入
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -E sample.exe   # 导出
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -z sample.exe   # 字符串
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -zz sample.exe  # 更详细字符串
```

### `rasm2`

适合快速汇编/反汇编：

```powershell
D:\reverse_ENV\tools\radare2\bin\rasm2.exe -d "9090"
D:\reverse_ENV\tools\radare2\bin\rasm2.exe -a x86 -b 64 "xor eax, eax"
```

### `radiff2`

适合对比两个二进制：

```powershell
D:\reverse_ENV\tools\radare2\bin\radiff2.exe old.exe new.exe
D:\reverse_ENV\tools\radare2\bin\radiff2.exe -C old.exe new.exe
```

### `rahash2`

适合算哈希：

```powershell
D:\reverse_ENV\tools\radare2\bin\rahash2.exe -a md5 sample.exe
D:\reverse_ENV\tools\radare2\bin\rahash2.exe -a sha256 sample.exe
```

### `rax2`

适合进制和编码转换：

```powershell
D:\reverse_ENV\tools\radare2\bin\rax2.exe 0x401000
D:\reverse_ENV\tools\radare2\bin\rax2.exe 4198400
D:\reverse_ENV\tools\radare2\bin\rax2.exe -s hello
```

## 渐进式披露阶段

本 skill 的推荐分析顺序已按 `reverse-coordinator` 的四个深度等级对齐：

| 阶段 | 深度 | 操作 | 工具 |
|------|------|------|------|
| 分类 | L0 | 确认文件格式、架构、位数、入口点 | `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I` |
| 侦察 | L1 | 字符串、导入/导出、节区 | `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -z/-i/-E/-S` |
| 决策 | — | 判断复杂度：有混淆标记？异常段？ | 基于 marker 判定 |
| 深挖 | L2 | 交互式分析入口和关键函数 | `D:\reverse_ENV\tools\radare2\bin\radare2.exe` → `aaa` → `afl` → `pdf` |
| 深挖+ | L3 | 交叉引用、patch、对比 | `axt` / `D:\reverse_ENV\tools\radare2\bin\radare2.exe -w` / `D:\reverse_ENV\tools\radare2\bin\radiff2.exe` |

> 遵循 `reverse-coordinator` 约定：先 `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I/-z/-i` 做无风险侦察，再决定是否进入交互式 `D:\reverse_ENV\tools\radare2\bin\radare2.exe`。不要在未侦察前直接 `D:\reverse_ENV\tools\radare2\bin\radare2.exe -A` 全量分析大文件。

## 推荐分析顺序

遇到未知样本时，按这个顺序做：

1. `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I` 看格式、架构、入口点
2. `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -z` 看字符串
3. `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -i` 看导入函数
4. 如需交互分析，再进 `D:\reverse_ENV\tools\radare2\bin\radare2.exe`
5. 先 `aaa`，再 `afl` / `iz` / `pdf`
6. 通过字符串引用、导入调用、入口流程逐步定位关键函数

这个顺序的好处是噪音低，能尽快建立方向感。

## Windows 注意事项

- 路径里有空格时，命令必须正确加引号
- 默认使用 `D:\reverse_ENV\tools\radare2\bin\*.exe` 绝对路径；只有用户明确要求验证 PATH 时，才把 PATH 当作显式 fallback
- 有些样本需要管理员权限读取，但默认不要主动提升权限，除非用户明确需要
- 对可疑样本做动态调试前，要先确认用户意图，避免误操作

## 输出风格

当用户不是只要命令，而是要你实际分析文件时：

- 先给出侦察结果摘要
- 再列出关键证据：字符串、导入、函数、地址
- 最后给出下一步建议或继续深入分析

不要只罗列命令而不解释为什么这么做。

## 典型请求示例

### 示例 1：分析一个 exe

用户：`帮我看看这个 exe 干了什么，用 radare2 就行`

处理方式：

1. 先用 `D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I/-z/-i`
2. 判断是否需要进入 `D:\reverse_ENV\tools\radare2\bin\radare2.exe`
3. 用 `aaa`、`afl`、`pdf` 深挖入口和关键字符串引用

### 示例 2：找字符串在哪被调用

用户：`这个报错字符串在哪个函数里触发的`

处理方式：

1. 用 `iz~关键字` 找字符串地址
2. 用 `axt <addr>` 找引用
3. 跳到引用点 `s <addr>` 后 `pdf`

### 示例 3：改掉跳转

用户：`把这个 jne 改成 je`

处理方式：

1. 先确认目标地址
2. 明确告知要进入写模式
3. 用 `wa je <target>` 或直接 `wx`
4. 修改后再次反汇编验证

## 避免的做法

- 不要把 `radare2` 当成只有 `aaa` 一个命令的工具
- 不要在未说明风险时直接写模式打开用户文件
- 不要在还没做基础侦察前就下结论
- 不要把网页 JS 逆向误导到这个 skill；默认用 `ruyi-reverse`，只有明确需要 Chrome/CDP 级断点调试且无强反检测要求时才用 `js-reverse-mcp`

## 参考资料

- 命令速查：`references/cheatsheet.md`
- 标准侦察脚本：`scripts/recon.ps1`
