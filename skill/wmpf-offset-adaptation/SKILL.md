---
name: wmpf-offset-adaptation
description: |
  Use for WMPF flue.dll Frida offset adaptation in D:\reverse_ENV, including generating and validating addresses.{version}.json fields LoadStartHookOffset, CDPFilterHookOffset, and SceneOffsets for X Debugger or WMPFDebugger. Trigger on WMPF version config 404, missing upstream addresses, flue.dll offset extraction, 偏移适配, or adding a new WMPF version. General WMPF runtime debugging remains under wechat-miniapp-re-mcp; escalate failed static extraction to ida-reverse.
---

# WMPF 偏移适配

## 定位与边界

本 Skill 只处理 WMPF `flue.dll` 的 Frida 配置偏移，输出 `addresses.{version}.json`：

- `LoadStartHookOffset`
- `CDPFilterHookOffset`
- `SceneOffsets`

默认先用 `.pdata` + Capstone 自动提取；自动化失配或证据不足时，切到 `ida-reverse` 使用 `ida-multi-mcp` 定向复核。WMPF 运行时 Hook、网络、CDP 会话、小程序包和动态证据仍走 `wechat-miniapp-re-mcp`。

## 强制约束

| 项 | 约束 |
|----|------|
| 唯一源码 | `D:\reverse_ENV\skill\wmpf-offset-adaptation\`；Codex/Claude 项目入口只做路由，不复制正文 |
| Python | 只用 `D:\reverse_ENV\.venv\Scripts\python.exe`，不得调用系统 Python 或全局 `pip` |
| 输入归档 | 目标 `flue.dll` 先复制到 `D:\reverse_ENV\workspace\<project>\`；记录来源版本与 SHA-256 |
| 输出落点 | 默认写入对应 workspace；只有用户明确指定调试器项目时才写其 `frida/config/` |
| 偏移语义 | 两个 Hook offset 都是 RVA，不是 VA；不得额外加 ImageBase |
| SceneOffsets | 必须从目标 DLL 的指针链证据提取；历史版本只能做 sanity check，禁止直接照搬 |
| 完成门槛 | 静态提取成功不等于运行时适配完成；缺少 `script loaded` 与 DevTools 连接证据时标记 `runtime-pending` |
| 分析深度 | 脚本成功且结构证据完整时停止；不得为了“更保险”直接全量 IDA 分析 |

## 依赖检查

项目 venv 当前依赖记录在 `requirements.txt`。先检查，不要重复安装：

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" -c "import pefile, capstone; print(pefile.__version__, capstone.__version__)"
```

缺失时只安装到项目 venv：

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" -m pip install -r "D:\reverse_ENV\skill\wmpf-offset-adaptation\requirements.txt"
```

## 标准流程

### 1. 建立项目落点

如果当前没有归属明确的 workspace，先创建 `D:\reverse_ENV\workspace\<project>\`。把目标 `flue.dll` 复制进去，再计算哈希：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath "D:\reverse_ENV\workspace\<project>\flue.dll"
```

WMPF 常见原始位置仅用于定位，不作为分析落点：

```text
%APPDATA%\Tencent\xwechat\xplugin\Plugins\RadiumWMPF\<version>\extracted\runtime\flue.dll
```

### 2. 运行自动提取

始终显式传 `--dll` 和 workspace 输出路径：

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" `
  "D:\reverse_ENV\skill\wmpf-offset-adaptation\scripts\extract_wmpf_offsets.py" `
  --version 25047 `
  --dll "D:\reverse_ENV\workspace\<project>\flue.dll" `
  --output "D:\reverse_ENV\workspace\<project>\addresses.25047.json"
```

输出结构：

```json
{
  "Version": 25047,
  "LoadStartHookOffset": "0x29ef320",
  "CDPFilterHookOffset": "0x3859ae0",
  "SceneOffsets": [64, 1488, 8, 1424, 16, 456]
}
```

### 3. 静态审查门

脚本返回成功后仍要核对：

1. `Version` 与目标 WMPF 目录版本一致。
2. 两个 Hook offset 是十六进制 RVA，且落在 PE 映像范围内。
3. `SceneOffsets` 恰好包含 6 个非负整数。
4. `CDPFilterHookOffset` 来自 `SendToClientFilter` 父函数的首个 `E8` 目标。
5. `LoadStartHookOffset` 所在函数同时引用 `applet_index_container.cc` 与 `AppletIndexContainer::OnLoadStart(bool`。
6. `SceneOffsets` 最终字段指向与 scene `1101`（`0x44D`）比较相关的链路。

只要第 4–6 项任一项无法由脚本行为或人工证据确认，就不得把结果标为已验证。

### 4. 脚本失败时升级到 IDA

先完整读取 `D:\reverse_ENV\skill\ida-reverse\SKILL.md`，再按以下最小路径取证：

1. `idalib_open(input_path="D:\reverse_ENV\workspace\<project>\flue.dll")`
2. `survey_binary(instance_id=..., detail_level="minimal")`
3. `find_regex` 搜索 `SendToClientFilter`、`applet_index_container.cc`、`AppletIndexContainer::OnLoadStart`
4. `xrefs_to` / `analyze_function` / `disasm` 只分析命中的父函数和尾部 callee
5. 用 `.pdata` 函数边界与目标指令交叉确认 RVA

不要同时让 IDA GUI 和 headless IDALib 打开同一数据库。若目标出现 VM、强混淆或结构完全漂移，标记 `triage-only`，不要猜偏移。

### 5. 写入调试器配置

只有目标调试器项目路径已经明确时，才使用 `--write`：

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" `
  "D:\reverse_ENV\skill\wmpf-offset-adaptation\scripts\extract_wmpf_offsets.py" `
  --version 25047 `
  --dll "D:\reverse_ENV\workspace\<project>\flue.dll" `
  --write `
  --config-dir "D:\reverse_ENV\workspace\<debugger-project>\frida\config"
```

写入前确认目标文件不存在或已被纳入本次变更范围；不得覆盖来源不明的手工配置。

### 6. 运行时验收

运行时验证转 `wechat-miniapp-re-mcp` 或目标调试器原生流程，至少记录：

- Frida 日志出现 `script loaded`
- 打开小程序后 Hook 未报 `unable to intercept`
- DevTools 能连接 `ws://127.0.0.1:62000`
- scene 改写功能按目标调试器预期生效

缺少运行时环境时，交付状态必须写成 `static-verified / runtime-pending`。

## 交付与证据

独立适配任务仍遵循逆向三件套，落到同一 workspace：

- `report.md`：版本、输入 SHA-256、提取方法、偏移结果、运行时状态
- `findings.json`：每个字段的证据位置、RVA、置信度和验证状态
- `triage.md`：自动脚本是否命中、是否升级 IDA、剩余阻塞

最终配置文件与三件套中的值必须一致。不得只给一份 JSON 就声称完整适配。

## 常见失败

| 现象 | 处理 |
|------|------|
| 上游 `addresses.{version}.json` 404 | 对目标 DLL 本地提取，不从邻近版本复制 |
| `SendToClientFilter string not found` | 确认 DLL/版本；升级 IDA 搜索宽松字符串与调用链 |
| `OnLoadStart pdata function not found` | 检查是否选错模块；用两个字符串的共同函数交叉确认 |
| `Could not parse OnLoadStart tail call pattern` | 结构发生漂移；IDA 定向分析尾部 callee，不做默认值回退 |
| `unable to intercept` | 复核 RVA、模块基址和目标函数入口；不要把 VA 写入配置 |
| scene 不生效 | 单独重算 `SceneOffsets`，不要推翻已验证的两个 Hook offset |

## 参考资料

- 项目适配算法：`references/algorithm.md`
- 上游原始算法快照：`references/upstream-algorithm.md`
- 上游原始 README 快照：`references/upstream-README.md`
- 25047 示例：`references/examples/addresses.25047.json`
- 上游来源与更新规则：`references/upstream.md`
