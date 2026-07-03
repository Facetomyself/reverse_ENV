---
name: reverse-coordinator
description: |
  逆向工程元技能——编排多 skill 协作，渐进式披露分析深度，产出结构化交付物。
  当用户提出"分析这个文件"、"看看这个APK"、"帮我逆向"等未指定具体工具的任务时优先使用。
  负责目标分类 → skill 路由 → 分阶段取证 → 产出汇总。
  不替代任何具体 skill，而是作为协调层决定"先做什么、用什么做、做到什么深度"。
---

# 逆向协调器（Reverse Coordinator）

## 适用范围

当任务满足以下任一条件时优先使用本 skill：

- 目标是**混合类型**（APK 内含 .so、网页 + 小程序、多层嵌套）
- 用户**未指定具体工具**，只说"帮我看看这个"
- 需要**系统性分析报告**而非单点查询
- 需要判断"做到什么程度算够了"

如果用户已明确指定工具（"用 IDA 分析这个 dll"），直接使用对应 skill，不需要经过本协调器。

## 核心原则

### 渐进式披露（Progressive Disclosure）

**永远从最轻的手段开始，逐层深入。**

```
文件类型 marker
  ↓ 确认格式/架构/平台
轻量侦察（字符串、导入表、manifest、脚本列表）
  ↓ 确认复杂度
分类决策（portable / context-aware / runtime-assisted / triage-only）
  ↓ 匹配分析深度
定向深挖（反编译、Hook、补环境）
  ↓ 仅在必要时
全量分析（全函数反编译、完整调用图、符号执行）
```

**不得跳阶段**。不要一上来就跑 IDA 全量分析或盲目 Hook 所有函数。

### 多 Agent 编排

本 skill 不直接做逆向，而是**委托给专业 skill**：

| 角色 | 对应 skill | 职责 |
|------|-----------|------|
| **Router** | 本 skill 内建 | 读取目标特征，决定走哪个 playbook |
| **Recon** | 对应 skill 的侦察阶段 | 最小化取证——字符串、导入、manifest、脚本列表 |
| **Analysis** | 对应 skill 的深挖阶段 | 定向反编译、xref 追踪、Hook 验证 |
| **Rebuild** | 对应 skill 的复现阶段 | 补环境、patch、重建 |
| **Review** | 本 skill 内建 | 汇总产出、检查证据链、标注 triage |

委托规则：
- 每个阶段只调用一个 skill，完成后再决定是否进入下一阶段
- 子 skill 返回"结构化摘要 + 文件路径"（大材料写文件）
- 全局 todo 由本 skill 管理，子 skill 不修改全局计划
- **Web RE 路由**：默认走 `ruyi-reverse`（统一编排器 T0→T4）；需 CDP 完整调试时通过 T4 桥接到 `mcp-js-reverse-playbook`

### 交付产物

每次完整分析流程必须产出**三件套**：

| 产物 | 内容 | 模板 |
|------|------|------|
| `report.md` | 人类可读分析报告 | `templates/report.md` |
| `findings.json` | 结构化发现列表 | `templates/findings.json` |
| `triage.md` | 未完成项 + 原因 + 下一步 | `templates/triage.md` |

辅助产物：
- `workspace.json` — 会话状态：目标信息、当前阶段、已完成/待完成项

## 四个分析深度等级

| 等级 | 名称 | 何时使用 | 典型产出 |
|------|------|---------|---------|
| **L1** | 便携提取 | 纯算法、无环境依赖、无混淆 | 完整 Python/JS 复现脚本 |
| **L2** | 上下文感知 | 需要部分运行时值（nonce、时间戳、设备信息） | 带桩函数的复现脚本 + 环境缺口说明 |
| **L3** | 运行时辅助 | 强依赖运行时（JNI 调用、native bridge、动态代码加载） | Hook 脚本 + 调用链文档 + 无法离线的部分清单 |
| **L4** | Triage-only | WASM、VM 混淆、重度反调试、硬件绑定 | 分析阻滞点清单 + Hook 候选 + 建议的工具链 |

**不得假装**：如果 L1 可达就不要标 L3；如果确实是 L4（WASM/VM/重混淆），不要声称能完整还原。

## 工作流

### 阶段 0：目标分类

读取目标文件/URL/包名，判断类型：

| 特征 | 判定 | 主 skill |
|------|------|---------|
| `.apk` / `.aab` / Android 包名 | Android APK | `apk-reverse` |
| `.exe` / `.dll` / `.sys` | Windows PE | `ida-reverse` |
| `.so` / `.elf`（反调试/反Frida/壳化/闪退） | Android/Linux Native 检测 | `native-reverse` |
| `.so` / `.elf` / `.macho`（纯算法/无保护） | Linux/macOS 二进制 | `ida-reverse` 或 `radare2` |
| `.js` / 网页 URL / 小程序 | Web JS | `ruyi-reverse`（默认）/ `mcp-js-reverse-playbook`（需 CDP 调试时） |
| 任意二进制（仅需快速侦察） | 通用二进制 | `radare2` |
| Android Native 反检测/完整性/Root | Native 安全分析 | `native-reverse` |

**Web JS 子路由**（统一入口 + 能力模块组合）：
- **所有 Web JS 逆向** → `ruyi-reverse` (7 模块 × 两级深度，按任务主动组合)
  - Anti-Detect / Observe / Capture / Trace / Human-Sim / Debug / Export
  - 每个模块有 L1 (轻量) 和 L2 (深度)，根据任务特征主动推荐——不等失败再升级
  - 需 Python API → ruyi-reverse 内部回退 (`references/ruyipage-api.md`)
  - 需 C++ trace → ruyi-reverse 内部回退 (`references/ruyitrace-cli.md`)
  - 需 CDP 断点调试 -> ruyi-reverse Export 桥接：`ruyi_export_session` -> js-reverse-mcp
- **已知需要 CDP 完整断点调试**（且无反检测需求）→ `mcp-js-reverse-playbook` (js-reverse-mcp)
- **需要 HTTP/WebSocket 抓包数据分析** → `reqable_*` (reqable-mcp)：先确认 Reqable ≥2.20 已配置上报到 `127.0.0.1:18765/report`，再 `ingest_status` → `list_requests`/`search_requests`/`analyze_api`/`generate_code` 等 17 tools

> ruyipage 和 ruyitrace 不再是独立 skill — 它们是 `ruyi-reverse` 内部能力模块的 L2 回退参考。

混合目标（如 APK 含多个 .so）：先走主 skill 的侦察阶段，发现 native 层信号后切 `ida-reverse`。

### 阶段 1：最小侦察

委托给对应 skill 的侦察阶段：

- **APK**: `decode.ps1`（不跳过 jadx+apktool） → 产出 package/java_files/smali_dirs/so_files
- **二进制**: 字符串 + 导入表 + 段信息（`rabin2 -I/-z/-i` 或 `idapro_survey_binary`）
- **Web JS**: `ruyi_new_page`（默认）+ `ruyi_list_scripts` + `ruyi_list_network_requests` + `ruyi_search_in_sources`；需 CDP 调试时 `js-reverse_new_page`（T4 桥接）
- **网络抓包分析**: `reqable_ingest_status` → `reqable_list_requests` / `reqable_search_requests` / `reqable_get_domains`（前提：Reqable 桌面端已抓包并推送到 18765）

**产出**: `workspace.json` 中记录目标类型、架构、关键字符串/类/函数名列表、复杂度 marker。

### 阶段 2：分类决策

根据侦察结果判定分析深度：

| Marker | 深度等级 |
|--------|---------|
| 纯 Java/Kotlin 逻辑，无 native 调用 | L1 或 L2 |
| 有 `System.loadLibrary()`，.so 占比 < 30% | L2，native 部分 L3 |
| 核心签名/加密在 .so 中 | L2（Java 层）+ L3（native 层） |
| `.wasm` / `WebAssembly.instantiate` / VM 解释器 / 控制流平坦化 | L4 |
| 反调试、反 Hook、反模拟器 | L3（需先中和保护） |

**Web JS 工具选择：** 路由到 ruyi-reverse（统一编排器），按任务组合能力模块：

| 任务需求 | 模块组合 | 说明 |
|---------|---------|------|
| 过检/侦察（默认路径） | Anti-Detect + Observe | ruyi-mcp |
| 协议逆向（加密定位->复现） | Anti-Detect(L2) + Capture(L2) + Debug(L2) + Export(L2) | ruyi -> js-reverse 桥接 |
| 指纹取证 | Anti-Detect(L2) + Observe(L1) + Trace(L2) | 主动推荐 C++ trace |
| 验证码突破 | Anti-Detect(L2) + Human-Sim(L2) | ruyi 人类模拟 |
| CDP 完整断点调试（无反检测） | `mcp-js-reverse-playbook` | 直接 CDP |
| 抓包流量分析 | `reqable_*` | Reqable + reqable-mcp |

### 阶段 3：定向深挖

按 L1→L4 等级匹配分析深度：

- **L1**: 全量反编译目标类/函数 → 提取算法 → 用 Python/JS 复现
- **L2**: 反编译 + 定向 Hook 获取运行时值 → 带桩复现 → 标注环境缺口
- **L3**: Hook 关键 JNI 调用 + IDA 分析 .so 导出函数 → 文档化调用链
- **L4**: 记录阻滞点 → 列出 Hook 候选 → 不声称完整还原 → 给下一步建议

### 阶段 4：产出汇总

1. 汇总各阶段发现 → 写入 `report.md`
2. 提取结构化数据 → 写入 `findings.json`（每条有 address/evidence/confidence）
3. 标注未完成项 → 写入 `triage.md`（原因 + 建议）
4. 自检审查门：
   - 所有 claim 有 evidence 支撑？
   - triage 遗留项已标注原因？
   - 产出文件路径正确？
   - 敏感数据已脱敏？

## 禁止事项

- 不要跳过分类直接深挖
- 不要因为"看起来简单"就不做侦察
- 不要对 L4 目标声称"已完成分析"
- 不要在不读文件内容的情况下猜结论
- 不要跨 skill 混用工具（IDA 工具不应用于 Web JS 分析）

## 快速入口

```bash
# 创建分析工作目录
mkdir D:\reverse_ENV\workspace\<target_name>

# 从目标分类开始
# → 对应 skill 的最小侦察
# → 分类决策 → 定向深挖 → 产出汇总
```
