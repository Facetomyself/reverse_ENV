---
name: ida-reverse
description: |
  IDA Pro 逆向分析辅助技能。当用户提到逆向、反编译、分析二进制/PE/ELF/APK/DLL/SO、破解、找密码、漏洞分析、病毒分析、firmware 固件分析，或需要分析 exe/dll/so/elf/macho/sys 等文件时，务必使用此技能。

  Ensure to use this skill when the user wants to analyze any binary file, regardless of whether they explicitly mention "IDA" or "reverse engineering". This includes requests like "看看这个exe", "分析这个dll", "帮我破解", "找一下密码", "这个软件怎么注册", etc.

  Primary path: use ida-multi-mcp stdio tools (idalib_* / idapro_*). scripts/start.ps1 verifies the environment. scripts/open.ps1 is only a path-preparation compatibility helper.
---

# IDA Pro 逆向分析技能

## 当前调用链

ida-multi-mcp 已迁移为 stdio 模式，由 `.mcp.json` / `~/.codex/config.toml` 自动拉起：

```
Codex / Claude MCP client
  -> D:\reverse_ENV\.venv\Scripts\python.exe -m ida_multi_mcp
  -> idalib_open 打开二进制
  -> idapro_survey_binary / idapro_analyze_function / idapro_* 分析
```

**主路径只走 MCP 工具。** 不再启动 HTTP 服务器，也不再通过脚本“绑定”数据库会话。

## 工作流程原则

| 步骤 | 做什么 | 用什么 |
|------|--------|--------|
| 1 | 验证 IDA 环境、venv、idalib 可用 | `scripts/start.ps1`（环境检查，不启动服务器） |
| 2 | 打开目标二进制 | `idalib_open` / `idapro_idalib_open` MCP 工具 |
| 3 | 先做最小侦察 | `idapro_survey_binary(detail_level="minimal")` |
| 4 | 定向深入分析 | `idapro_analyze_function` / `idapro_decompile` / `idapro_xrefs_to` |
| 5 | 记录与交付 | `report.md` + `findings.json` + `triage.md` |

## 脚本边界

### `scripts/start.ps1` — 验证 ida-multi-mcp stdio 环境

用途：

- 检查 `.venv\Scripts\python.exe`
- 检查 `IDADIR=D:\reverse_ENV\resource\portable_win`
- 检查 `ida_multi_mcp` 与 `idapro` 是否可 import
- 清理旧 `idalib_worker` 孤儿进程
- 成功输出 `READY:ida-multi-mcp environment verified`

调用：

```powershell
powershell -File "D:\reverse_ENV\skill\ida-reverse\scripts\start.ps1"
```

### `scripts/open.ps1` — 路径预处理辅助（非主打开路径）

用途：

- 自动检测 System32 路径并复制到临时目录
- 自动清理同名旧数据库文件（`.id0` / `.id1` / `.id2` / `.nam` / `.til` / `.i64`）
- 旧库被锁时自动降级：复制到 Temp 加 GUID 前缀
- 输出可传给 MCP `idalib_open` 的最终路径

边界：

- 不打开数据库
- 不写 `~/.ida-mcp/instances.json`
- 不承诺绑定当前 MCP session
- 不替代 `idalib_open`

调用：

```powershell
powershell -File "D:\reverse_ENV\skill\ida-reverse\scripts\open.ps1" -Path "C:\path\to\file.exe"
```

输出：

```text
READY_FOR_IDALIB_OPEN:C:\path\to\file.exe
NEXT:call MCP idalib_open/input_path with the READY_FOR_IDALIB_OPEN path
```

如果出现 `INFO:copied_from_system32:*` 或 `INFO:locked_db_fallback:*`，以后面的 `READY_FOR_IDALIB_OPEN` 路径为准。

## 核心工具列表

### 概况分析（第一步）

- `idapro_survey_binary(detail_level="minimal")` — 快速概况：函数数、字符串、段、入口点、导入分类（加密/网络/文件IO）
- `idapro_list_funcs(queries)` — 列出函数（分页、按名称过滤）
- `idapro_list_globals(queries)` — 列出全局变量
- `idapro_entity_query(kind, filter)` — 统一查询：functions/globals/imports/strings/names

### 反编译与反汇编

- `idapro_decompile(addr)` — 反编译为伪代码
- `idapro_disasm(addr, max_instructions=N)` — 反汇编
- `idapro_analyze_function(addr, include_asm=false)` — 综合分析（伪代码+字符串+常量+调用者+被调用者+块）
- `idapro_func_profile(queries)` — 函数概要指标

### 交叉引用与数据流

- `idapro_xrefs_to(addrs)` — 查谁引用目标地址
- `idapro_xref_query(addr, direction)` — 高级 xref 查询（方向/类型过滤）
- `idapro_callees(addrs)` — 子函数列表
- `idapro_callgraph(roots, max_depth)` — 调用图
- `idapro_trace_data_flow(addr, direction, max_depth)` — 数据流追踪（forward/backward）

### 搜索

- `idapro_find_regex(pattern, limit)` — 正则搜字符串
- `idapro_search_text(pattern)` — 在反汇编列表中搜文本
- `idapro_find_bytes(patterns, limit)` — 字节模式搜索（支持 `??` 通配符）
- `idapro_find(type, targets)` — 高级搜索（立即数/字符串/引用）

### 内存与数据

- `idapro_get_bytes(addrs)` — 读原始字节
- `idapro_get_string(addrs)` — 读字符串
- `idapro_get_int(queries)` — 读整数值
- `idapro_get_global_value(queries)` — 读全局变量值
- `idapro_read_struct(queries)` — 读结构体字段值
- `idapro_search_structs(filter)` — 搜索结构体

### 修改操作

- `idapro_set_comments(items)` — 添加注释（反汇编+反编译双向同步）
- `idapro_append_comments(items)` — 追加注释
- `idapro_rename(batch)` — 批量重命名（函数/全局/局部/栈变量）
- `idapro_patch_asm(items)` — Patch 汇编指令
- `idapro_patch(patches)` — Patch 字节
- `idapro_define_func(items)` — 定义函数
- `idapro_undefine(items)` — 取消定义
- `idapro_define_code(items)` — 将字节转为代码

### 类型系统

- `idapro_declare_type(decls)` — 声明 C 结构体/枚举/联合体
- `idapro_set_type(edits)` — 应用类型到函数/全局/局部
- `idapro_infer_types(addrs)` — 推断类型
- `idapro_type_query(queries)` — 查询已声明类型
- `idapro_type_inspect(queries)` — 查看类型详情

### 栈帧

- `idapro_stack_frame(addrs)` — 查看栈帧变量
- `idapro_declare_stack(items)` — 声明栈变量
- `idapro_delete_stack(items)` — 删除栈变量

### 会话管理

- `idalib_open` / `idapro_idalib_open(input_path)` — 主打开路径
- `idalib_list` / `idapro_idalib_list()` — 列出所有 session
- `idapro_idalib_current()` — 当前上下文绑定的 session
- `idapro_idalib_switch(session_id)` — 切换到其他 session
- `idalib_close` / `idapro_idalib_close(session_id)` — 关闭 session
- `idapro_idalib_save(path)` — 保存数据库
- `idapro_idalib_health(session_id)` — 检查 worker 健康状态

### 其他

- `idapro_int_convert(inputs)` — 进制转换（需要转换数字时优先用这个）
- `idapro_export_funcs(addrs, format)` — 导出函数（json/c_header/prototypes）
- `idapro_py_eval(code)` — 在 IDA 上下文执行 Python
- `idapro_server_health()` — 服务器健康检查
- `idapro_server_warmup()` — 预热子系统（字符串缓存、Hex-Rays 等）

## 渐进式披露阶段

| 阶段 | 深度 | 操作 | 工具 |
|------|------|------|------|
| 分类 | L0 | 确认文件格式/架构/入口点 | `rabin2 -I` 或文件头 |
| 侦察 | L1 | 全局概览：字符串、导入、热门函数 | `idapro_survey_binary(minimal)` |
| 决策 | — | 判断复杂度：有无混淆/反调试/VM | 基于 marker 判定 L1-L4 |
| 深挖 | L2 | 定向分析关键函数 | `idapro_analyze_function` / `idapro_decompile` |
| 深挖+ | L3 | 数据流追踪、调用图、交叉引用 | `idapro_xrefs_to` / `idapro_callgraph` / `idapro_trace_data_flow` |
| 记录 | — | 重命名、加注释、产出报告 | `idapro_rename` / `idapro_set_comments` |

遵循 `reverse-coordinator` 约定：不得跳过 L0 survey 直接做 L3 全量分析。对重混淆/VM 样本标注为 L4 triage。

## 完整工作流

### Step 1: 验证环境

```powershell
powershell -File "D:\reverse_ENV\skill\ida-reverse\scripts\start.ps1"
```

### Step 2: 必要时预处理路径

```powershell
powershell -File "D:\reverse_ENV\skill\ida-reverse\scripts\open.ps1" -Path "C:\目标.exe"
```

普通 workspace 文件可跳过本步，直接把原始路径传给 MCP `idalib_open`。

### Step 3: MCP 打开文件

```text
idalib_open(input_path="D:\reverse_ENV\workspace\<project>\<target>")
```

打开后先确认当前 session，再进入 survey。

### Step 4: 全局概览

```text
idapro_survey_binary(detail_level="minimal")
```

关注：

- 架构（x86/x64/ARM）
- 入口点（main/WinMain/DllMain）
- 有趣字符串（URL、路径、错误消息）
- 导入分类（加密函数、网络 API、文件操作）
- 热门函数（高 xref 计数的函数通常是关键逻辑）

### Step 5: 深入关键函数

```text
idapro_analyze_function(addr="关键函数名")
idapro_decompile(addr="函数名")
idapro_disasm(addr="函数名", max_instructions=50)
```

### Step 6: 数据流和交叉引用

```text
idapro_xrefs_to(addrs="关键地址/字符串")
idapro_callgraph(roots=["关键函数"], max_depth=3)
idapro_trace_data_flow(addr="关键地址", direction="backward", max_depth=5)
```

### Step 7: 记录和优化

```text
idapro_set_comments(items=[{"addr": "0x140001000", "comment": "你的理解"}])
idapro_rename(batch={"func": [{"addr": "函数地址", "name": "有意义的名字"}]})
```

### Step 8: 输出报告

分析完成后，使用 `reverse-coordinator` 模板产出 `report.md` + `findings.json` + `triage.md`。

## Prompt 工程准则

1. **不要手动算进制** — 任何时候需要转换数字，用 `idapro_int_convert`
2. **先 survey 后深入** — 先看概况再针对性分析
3. **持续加注释和重命名** — 分析过程中不断更新函数名和变量名，提升后续分析准确性
4. **跟踪交叉引用** — 发现有趣的数据/字符串，用 `xrefs_to` 看谁引用了它
5. **遇到混淆代码** — 先做字符串解密、导入哈希去除、控制流平坦化去除等预处理
6. **C++ STL 代码** — 用 FLIRT/Lumina 识别库函数后，再分析业务逻辑
7. **不要暴力破解** — 分析应从反汇编中推导解决方案，用简单 Python 辅助计算
8. **遇到 `No database bound`** — 还没有通过 MCP 打开任何二进制文件，先调用 `idalib_open`
9. **遇到 `Failed to open database`** — 可能是旧数据库文件被锁，可先用 `open.ps1` 预处理路径，再把 `READY_FOR_IDALIB_OPEN` 路径传给 `idalib_open`

## 参考文档

| 文档 | 来源 | 内容 |
|------|------|------|
| `references/idapython-reference.md` | rev-idapython | IDAPython/IDALib API 速查 (~170 snippets) |
| `references/symbol-recovery.md` | rev-symbol | 符号恢复方法论 (magic number/配对模式/xref) |
| `references/structure-recovery.md` | rev-struct | 结构体恢复 (内存访问聚合→类型推断) |
