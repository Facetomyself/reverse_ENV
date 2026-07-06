---
name: ida-reverse
description: |
  IDA Pro 逆向分析辅助技能。用于分析 PE/ELF/Mach-O、exe/dll/sys/so/elf/macho/bin、firmware 固件、APK 中的 native .so，以及需要 IDA/Hex-Rays/IDALib 的二进制目标。

  不作为普通 APK 入口；APK Java/Kotlin、Manifest、smali、jadx/apktool 流程先走 apk-reverse，只有发现 native .so 或明确需要 IDA 分析时再切入本 skill。

  Primary path: use ida-multi-mcp stdio tools. scripts/start.ps1 verifies the environment. scripts/open.ps1 is only a non-destructive path-preparation helper.
---

# IDA Pro 逆向分析技能

## 当前调用链

ida-multi-mcp 由 `.mcp.json` / `~/.codex/config.toml` 以 stdio 模式自动拉起：

```text
Codex / Claude MCP client
  -> D:\reverse_ENV\.venv\Scripts\python.exe -m ida_multi_mcp
  -> idalib_open(input_path=...)
  -> 返回 instance_id
  -> survey_binary(instance_id=..., detail_level="minimal")
  -> analyze_function / decompile / xrefs_to / callgraph / trace_data_flow
```

主路径只走 MCP 工具。无需手动启动独立 HTTP server；worker HTTP / registry 是 ida-multi-mcp 内部实现细节。

## 工作流原则

| 步骤 | 做什么 | 用什么 |
|------|--------|--------|
| 1 | 验证 IDA 环境、venv、idapro 可用 | `scripts/start.ps1` |
| 2 | 必要时做路径预处理 | `scripts/open.ps1`，只输出安全路径 |
| 3 | 打开目标二进制 | `idalib_open(input_path=...)` |
| 4 | 保存返回的 `instance_id` | 后续所有 proxied IDA tools 必须显式传入 |
| 5 | 先做最小侦察 | `survey_binary(instance_id=..., detail_level="minimal")` |
| 6 | 定向深入分析 | `analyze_function` / `decompile` / `xrefs_to` / `callgraph` |
| 7 | 记录与交付 | `report.md` + `findings.json` + `triage.md` |

## 脚本边界

### `scripts/start.ps1` — 环境验证

用途：

- 检查 `.venv\Scripts\python.exe`
- 检查 `IDADIR=D:\reverse_ENV\resource\portable_win`
- 检查 `ida_multi_mcp` 与 `idapro` 是否可 import
- 清理当前 venv 下的旧 `idalib_worker` 孤儿进程
- 成功输出 `READY:ida-multi-mcp environment verified`

调用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ida-reverse\scripts\start.ps1"
```

### `scripts/open.ps1` — 非破坏性路径预处理辅助

用途：

- 自动检测 System32 路径并复制到 `%TEMP%\opencode\`
- 检测同名旧 IDA 数据库文件（`.id0` / `.id1` / `.id2` / `.nam` / `.til` / `.i64`）
- 默认不删除任何 IDA 数据库；发现旧库时复制 binary 到 temp GUID 副本
- 只有显式传 `-CleanOldDb` 才清理旧数据库文件
- 输出可传给 MCP `idalib_open` 的最终路径

边界：

- 不打开数据库
- 不绑定当前 MCP session
- 不替代 `idalib_open`
- 默认不会删除 `.i64` / `.id*` 等已有分析产物

调用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ida-reverse\scripts\open.ps1" -Path "C:\path\to\file.exe"
```

输出：

```text
READY_FOR_IDALIB_OPEN:C:\path\to\file.exe
NEXT:call MCP idalib_open/input_path with the READY_FOR_IDALIB_OPEN path
```

如果出现 `WARN:old_db_exists:*`，默认会同时输出 `INFO:old_db_temp_copy:*`，并以后面的 `READY_FOR_IDALIB_OPEN` 路径为准。

## 真实 MCP 工具名

当前 `ida_multi_mcp` 版本：`0.1.0`。静态 schema 文件：`.venv\Lib\site-packages\ida_multi_mcp\ida_tool_schemas.json`，当前包含 44 个 proxied IDA tools。Codex 工具 namespace 通常显示为 `mcp__ida_multi_mcp.<tool>`，Claude 工具名常见为 `mcp__ida-multi-mcp__<tool>`；文档中统一使用短名。

### 会话与管理

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `idalib_open` | 打开 binary/IDB，创建 headless session | `input_path`, `timeout`, `unsafe` |
| `idalib_list` | 列出 headless idalib sessions | 无 |
| `idalib_status` | 检查 worker 是否存活 | `instance_id` |
| `idalib_close` | 关闭 headless session | `instance_id` |
| `list_instances` | 列出 GUI + headless 注册实例 | 无 |
| `refresh_tools` | 刷新动态工具缓存 | 无 |
| `compare_binaries` | 比较两个 instance 的 survey 摘要 | `instance_id_a`, `instance_id_b` |
| `decompile_to_file` | 批量反编译到磁盘文件 | `instance_id`, `output_dir`, `addrs`/`all` |
| `list_cached_outputs` / `get_cached_output` | 读取被截断的大输出 | `cache_id`, `offset`, `size` |

### 侦察与查询

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `survey_binary` | 第一步全局概览 | `instance_id`, `detail_level` |
| `list_funcs` / `lookup_funcs` | 函数分页/名称查询 | `instance_id`, `queries` |
| `list_globals` | 全局变量分页/查询 | `instance_id`, `queries` |
| `imports` | 导入表分页 | `instance_id`, `offset`, `count` |
| `find_regex` | 字符串正则搜索 | `instance_id`, `pattern`, `limit` |
| `find` | 搜字符串/立即数/data_ref/code_ref | `instance_id`, `type`, `targets` |
| `find_bytes` | 字节模式搜索，支持 `??` | `instance_id`, `patterns` |
| `basic_blocks` | 基本块信息 | `instance_id`, `addr` |

### 函数与关系分析

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `analyze_function` | 单函数综合摘要 | `instance_id`, `addr`, `include_asm` |
| `analyze_component` | 多函数组件级摘要 | `instance_id`, `addrs` |
| `decompile` | Hex-Rays 反编译 | `instance_id`, `addr` |
| `disasm` | 反汇编 | `instance_id`, `addr` |
| `xrefs_to` / `xrefs_to_field` | 交叉引用 | `instance_id`, `addrs` |
| `callees` | 被调函数列表 | `instance_id`, `addrs` |
| `callgraph` | 调用图 | `instance_id`, `roots`, `max_depth` |
| `trace_data_flow` | xref 多跳数据流 | `instance_id`, `addr`, `direction`, `max_depth` |

### 内存、类型与修改

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `get_bytes` / `get_int` / `get_string` | 读取字节、整数、字符串 | `instance_id`, `regions`/`queries` |
| `get_global_value` | 读取全局变量值 | `instance_id`, `queries` |
| `read_struct` / `search_structs` | 结构体读取/搜索 | `instance_id`, `queries`/`filter` |
| `declare_type` / `set_type` / `infer_types` | 类型声明、应用、推断 | `instance_id`, `decls`/`edits`/`addrs` |
| `stack_frame` / `declare_stack` / `delete_stack` | 栈帧变量 | `instance_id`, `addrs`/`items` |
| `rename` | 函数、全局、局部、栈变量重命名 | `instance_id`, `batch` |
| `set_comments` / `append_comments` | 覆盖/追加注释 | `instance_id`, `items` |
| `patch` / `patch_asm` / `put_int` | Patch 字节、汇编、整数 | `instance_id`, `patches`/`items` |
| `define_func` / `define_code` / `undefine` | 定义/取消定义 | `instance_id`, `items` |
| `diff_before_after` | 修改前后反编译对比 | `instance_id`, `addr`, `action` |
| `refresh_caches` | 批量修改后刷新缓存 | `instance_id` |
| `int_convert` | 数字转换 | `instance_id`, `inputs` |
| `export_funcs` | 导出函数 JSON/header/prototypes | `instance_id`, `addrs`, `format` |
| `py_eval` | 在 IDA 上下文执行 Python | `instance_id`, `code` |

## 渐进式披露阶段

| 阶段 | 深度 | 操作 | 工具 |
|------|------|------|------|
| 分类 | L0 | 确认文件格式/架构/入口点 | `rabin2 -I` 或文件头 |
| 侦察 | L1 | 全局概览：字符串、导入、热门函数 | `survey_binary(detail_level="minimal")` |
| 决策 | — | 判断复杂度：有无混淆/反调试/VM | 基于 marker 判定 L1-L4 |
| 深挖 | L2 | 定向分析关键函数 | `analyze_function` / `decompile` |
| 深挖+ | L3 | 数据流追踪、调用图、交叉引用 | `xrefs_to` / `callgraph` / `trace_data_flow` |
| 记录 | — | 重命名、加注释、产出报告 | `rename` / `set_comments` / `append_comments` |

不得跳过 L0 survey 直接做 L3 全量分析。对重混淆/VM 样本标注为 L4 triage，不声称完整还原。

## 完整工作流

### Step 1: 验证环境

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ida-reverse\scripts\start.ps1"
```

### Step 2: 必要时预处理路径

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ida-reverse\scripts\open.ps1" -Path "C:\目标.exe"
```

普通 workspace 文件可跳过本步，直接把原始路径传给 MCP `idalib_open`。

### Step 3: MCP 打开文件并记录 `instance_id`

```text
idalib_open(input_path="D:\reverse_ENV\workspace\<project>\<target>", timeout=120)
```

从返回结果中记录 `instance_id`。如果打开耗时长，先不要重试；确认 worker 状态：

```text
idalib_status(instance_id="<instance_id>")
```

### Step 4: 全局概览

```text
survey_binary(instance_id="<instance_id>", detail_level="minimal")
```

关注：

- 架构（x86/x64/ARM）
- 入口点（main/WinMain/DllMain）
- 有趣字符串（URL、路径、错误消息）
- 导入分类（加密函数、网络 API、文件操作）
- 热门函数（高 xref 计数的函数通常是关键逻辑）

### Step 5: 深入关键函数

```text
analyze_function(instance_id="<instance_id>", addr="关键函数名")
decompile(instance_id="<instance_id>", addr="函数名")
disasm(instance_id="<instance_id>", addr="函数名")
```

### Step 6: 数据流和交叉引用

```text
xrefs_to(instance_id="<instance_id>", addrs="关键地址/字符串")
callgraph(instance_id="<instance_id>", roots=["关键函数"], max_depth=3)
trace_data_flow(instance_id="<instance_id>", addr="关键地址", direction="backward", max_depth=5)
```

### Step 7: 记录和优化

```text
set_comments(instance_id="<instance_id>", items=[{"addr": "0x140001000", "comment": "你的理解"}])
rename(instance_id="<instance_id>", batch={"func": [{"addr": "函数地址", "name": "有意义的名字"}]})
```

### Step 8: 输出报告

分析完成后，使用 `reverse-coordinator` 模板产出 `report.md` + `findings.json` + `triage.md`。

## Prompt 工程准则

1. 需要转换数字时优先用 `int_convert`，不要手算后直接下结论。
2. 先 `survey_binary` 后深入，不要一上来全量反编译或跑重型循环。
3. 批量反编译用 `decompile_to_file`，不要在 `py_eval` 里遍历所有函数。
4. 所有 proxied IDA tools 都显式传同一个 `instance_id`。
5. 分析过程中持续用 `rename`、`set_comments`、`append_comments` 固化证据。
6. 发现有趣数据/字符串后，用 `xrefs_to` / `find` / `trace_data_flow` 追调用链。
7. 遇到 `No database bound` 或缺 `instance_id`，回到 `idalib_open` 返回结果，不要猜当前 session。
8. 遇到 `Failed to open database`，先用 `open.ps1` 预处理路径；不要删除 `.i64` / `.id*`，除非用户明确要求清理旧库。

## 参考文档

| 文档 | 来源 | 内容 |
|------|------|------|
| `references/idapython-reference.md` | rev-idapython | IDAPython/IDALib API 速查 |
| `references/symbol-recovery.md` | rev-symbol | 符号恢复方法论 |
| `references/structure-recovery.md` | rev-struct | 结构体恢复 |
