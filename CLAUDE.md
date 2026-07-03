# CLAUDE.md

逆向工程环境配置与技能仓库。为 Claude Code 提供 skills、MCP 服务、工具脚本。

## 核心约束

**所有 skill、MCP、Python venv、工具依赖均安装在 `D:\reverse_ENV\` 内，不得污染系统全局。**

- venv: `.venv\` ｜ JDK: `tools\jdk\` ｜ Node: `tools\node\`
- NDK r29: `tools\android-ndk\` ｜ Rust: `%USERPROFILE%\.cargo\`
- IDA Pro 9.3: `resource\portable_win\` ｜ MCP 配置: `.mcp.json`
- **所有逆向项目在 `workspace\<项目名>\` 下起新文件夹**。产出物均落地到对应项目目录。
- **待分析二进制文件**（`.dll`, `.so`, `.exe`, `.bin` 等）**必须先放入 `workspace\<项目名>\`**，再打开 IDA/radare2。禁止将二进制文件直接放在 `workspace\` 根目录。
- **IDA 数据库文件**（`.id0`, `.id1`, `.id2`, `.nam`, `.til`, `.i64`）由 IDA 在二进制文件所在目录自动生成。确保二进制文件在项目子目录内，即可避免 IDA 产物污染根目录。
- **抓包流量文件**（`*.flow`, `*.pcap`, `*.har`）统一放在 `workspace\<项目名>\` 下。禁止散落在 `workspace\` 根目录。
- **`storage\` 存放可复用的大文件**（安装包、SDK、ISO 等），内容不纳入 Git。
- **用户级 MCP**（`serena`、`deepcon`）为全局辅助工具，详见下方「全局 MCP 使用约束」。

### AI 协作子约束

> 详见 `docs/AI开发规范.md` 和 `docs/Git与提交规范.md`

**操作纪律：**
1. **不得凭记忆** — 修改文件前 Read 实际内容，不基于摘要操作。
2. **先确认、再动手** — 确认当前目录、文件存在、工具可用。
3. **改动闭环** — 改脚本 → 同步 CLAUDE.md；改工具路径 → 同步 skill 文档；加项目 MCP → 同步 `.mcp.json`；加用户 MCP → 同步 `~/.claude.json`。
4. **禁止猜测** — 工具安装、命令执行必须有真实输出为证。

**编码：**
5. UTF-8 + LF 新文件；已有 BOM 保留 BOM；中文文件防乱码。
6. 路径全部绝对化，不依赖 PATH。

**渐进式披露：**
7. **先侦察、后深挖** — 从轻量 triage 开始，根据 marker 决定深度。不得一上来全量分析/盲目 Hook。
8. **证据优先** — 每个结论必须有可追溯证据。未经证实的标注"待验证"。
9. **能力匹配复杂度** — L1 便携 → L2 上下文 → L3 运行时 → L4 triage-only。不假装能完整还原 WASM/VM。

**产出规范：**
10. 每次分析产出三件套：`report.md` + `findings.json` + `triage.md`（模板: `skill/reverse-coordinator/templates/`）。
11. **审查门** — 产出前自检：claim 有证据？triage 已标注？敏感数据已脱敏？
12. **不得假装** — 不对 L4 目标声称"已完整复现"。

**修改闭环：**
13. 自检：CLAUDE.md 路径一致？`.mcp.json` 合法？临时文件已清理？敏感数据已脱敏？

## 仓库入口

| 想看什么 | 去哪里 |
|----------|--------|
| 完整目录树 | `docs/仓库结构.md`（待建，或 `ls -R` 查看） |
| 工具版本与路径 | `docs/工具与环境.md` |
| MCP 服务配置详情 | `docs/MCP服务详情.md` |
| 工作流与深度等级 | `docs/逆向工作流详解.md` |
| Web 逆向架构分析 | `docs/Web逆向架构分析.md` |
| ruyi-mcp 引导方案 | `docs/ruyi-mcp-引导方案.md` |
| ruyi-mcp DevTools 调试能力分析 | `docs/ruyi-mcp-devtools-调试能力分析.md` |
| 脚本使用说明 | `docs/脚本参考.md` |
| AI 协作开发规范 | `docs/AI开发规范.md` |
| Git 操作规范 | `docs/Git与提交规范.md` |

## Skill 速查

| Skill | 场景 | 何时用 |
|-------|------|--------|
| `reverse-coordinator` | **元 skill** | 未指定工具时优先——分类→路由→编排→交付 |
| `apk-reverse` | Android APK | jadx/apktool/frida/adb |
| `ida-reverse` | PE/ELF/DLL/SO | IDA Pro 深度分析 |
| `mcp-js-reverse-playbook` | Web JS — CDP 调试 | js-reverse-mcp (Chrome/CDP) — 需要完整断点/单步/调用栈时首选 |
| `ruyi-reverse` | Web JS — 统一编排器 | 7 能力模块 (Anti-Detect/Observe/Capture/Trace/Human-Sim/Debug/Export) x 深浅两级，按任务主动组合。**唯一入口** |
| `radare2` | 通用二进制 | CLI 快速侦察/反汇编/patch |
| `reverse-engineering` | 知识库 | CTF 模式参考（自动加载，不直接调用） |
| `native-reverse` | Android Native .so 反检测/绕过 | syscall 定位→dump/fix→IDA→patch→验证 |
| `ldplayer-control` | 雷电模拟器 RE 实例管理 | re-init(创建→配置→启动) / re-proxy(HTTPS代理) / re-list / re-destroy — 项目实例隔离 |
| `protocol-recovery` | Web 协议恢复 | 签名→Python 采集器（接在 mcp-js-reverse-playbook 或 ruyi-reverse 之后） |

**路由**: `.so`/native 反检测/绕过 → `native-reverse`；`.so` 纯静态分析 → `ida-reverse`/`radare2`；APK Java → `apk-reverse`。
**Web JS 路由**: **默认 -> `ruyi-reverse`（统一编排器）** — 7 模块 x 两级深度，按任务主动组合 (Anti-Detect/Observe/Capture/Trace/Human-Sim/Debug/Export)。需 CDP 完整断点调试且无反检测需求 -> `mcp-js-reverse-playbook`。两者**可互补**，通过 Export 桥接。

## 工作流速查

```
多源搜索(全局约束) → 分类(文件类型/平台) → 最小侦察(字符串/导入/manifest)
  → 决策(L1-L4深度) → 定向深挖(仅在确认后) → 产出三件套 → 审查门
```

> 多源搜索约束见全局 `~/.claude/CLAUDE.md`。详细规范: `docs/搜索编排规范.md`。

**不得跳阶段。L4 目标不声称完整还原。**

## MCP 工具前缀

| 前缀 | 服务 | 用途 |
|------|------|------|
| `idapro_*` | ida-multi-mcp | 反编译/反汇编/xref/patch/类型/栈帧 (~72 tools) |
| `idalib_*` | ida-multi-mcp | headless 会话管理 (open/close/list) |
| `jadx_*` | jadx-ai-mcp | APK 类/方法搜索/反编译/xref |
| `js-reverse_*` | js-reverse-mcp | Chrome/CDP 调试优先 — 断点/脚本/网络/运行时 (~22 tools) |
| `ruyi_*` | ruyi-mcp | Firefox/BiDi 全链路增强 — 反检测/指纹/人类模拟/trace/JS逆向 (~41 tools) |
| `reqable_*` | reqable-mcp | Reqable 抓包数据查询 — HTTP/WebSocket 流量搜索/分析/代码生成 (~17 tools) |
| `serena_*` | serena (user) | 代码符号搜索/引用追踪/语义搜索/项目导航 |
| `deepcon_*` | deepcon (user) | 包文档语义搜索/API 参考/代码示例检索 |

> **Web RE 双 MCP**: `js-reverse-mcp` (Chrome/CDP) 调试优先；`ruyi-mcp` (Firefox/BiDi) 增强全能 — 反检测/指纹/trace/人类模拟。按需求能力选择，可互补协作。详见 `docs/Web逆向架构分析.md`。

> MCP 服务详情见 `docs/MCP服务详情.md`

### 全局 MCP 使用约束

`serena` 和 `deepcon` 是**用户级**（`~/.claude.json`）MCP，跨所有项目可用。需遵守以下约束：

**定位：**
- 二者是**通用辅助工具**，不是逆向工程核心工具链的一部分
- 核心 RE 流程（IDA → jadx → js-reverse/ruyi → Frida）优先级始终更高
- 不得因全局工具可用而跳过项目级 RE 工具的配置和使用

**Serena（代码上下文引擎）：**
1. 适用场景：跨多文件代码理解、符号定位、调用链追踪、大型陌生代码库导航
2. **不得替代** `Read`/`Grep`/`Glob` — 已知文件内容读取仍用原生工具
3. **不得替代** IDA 反编译 — `.so`/`.dll` 二进制分析仍走 `ida-reverse`
4. 仅当代码库规模大（>50 文件）或结构不明确时启用 Serena
5. Serena 的分析结论需交叉验证，不可作为唯一证据

**Deepcon（包文档搜索）：**
1. 适用场景：查询第三方库/框架/SDK 的 API 文档和用法示例
2. **需 API Key** — 在 [deepcon.ai](https://deepcon.ai) 注册获取 `DEEPCON_API_KEY`，填入 `~/.claude.json`
3. 免费层：100 请求/月，超出则限流
4. **不得替代** 官方文档阅读 — Deepcon 结果为摘要，关键 API 仍应查阅原始文档
5. 逆向分析中仅在需要理解第三方库内部行为时使用

**通用纪律：**
- 每次使用前自问：「这个操作用项目 RE 工具能否完成？」能则不用全局工具
- 全局工具的输出不作为最终产出的唯一来源 — 必须有项目工具链的独立验证

### Web RE 双 MCP 约束

`js-reverse-mcp` 和 `ruyi-mcp` 是两个**互补**的 Web RE MCP 服务，按需求能力选择，可协作：

| MCP 服务 | 浏览器/协议 | 核心优势 | 适用场景 |
|---------|-------------|---------|---------|
| `js-reverse-mcp` | Chrome / CDP | **完整 JS 断点调试**（断点/单步/调用栈/作用域） | 需要 CDP 级运行时调试、无强反检测要求 |
| `ruyi-mcp` | Firefox / BiDi | **反检测 + 指纹分析 + trace + 人类模拟** | 需要过验证码、指纹取证、DOM trace、人类行为模拟（**所有站点通用**） |

**选择规则：**
1. 需要 CDP 完整断点调试（`get_paused_info`、`step`、调用栈查看）→ 用 `js-reverse_*`
2. 需要指纹分析、DOM trace、过 Cloudflare/hCaptcha、反检测浏览 → 用 `ruyi_*`（**无论目标站点反检测强度如何**）
3. ruyi-mcp 功能更全面（41 tools vs 22），指纹分析和 trace 能力在弱检测站点同样实用
4. 两者可互补：`ruyi_export_session` → 导出 Cookie/Storage → js-reverse-mcp 继续 CDP 调试
5. **禁止** 在强反检测站点上单独用 js-reverse-mcp（Chrome 无指纹伪装，会被封）— 需先经 ruyi-mcp 过检

**工具前缀隔离：** 同一浏览器 session 内不混用两个前缀的工具。跨工具协作通过 `ruyi_export_session` 显式桥接。

## 已知坑点

1. **idalib 孤儿进程** → `start.ps1` 用 `taskkill /F /T` 杀进程树。
2. **System32 文件无权限** → `open.ps1` 自动复制到 `%TEMP%\opencode\`。
3. **IDA 许可单实例** → GUI 和 headless 互斥，跑 headless 前关 GUI。
4. **jadx-ai-mcp 需先开 GUI** → `tools\jadx-gui.cmd` 启动并加载 APK 后 MCP 才可用。
5. **Plugin 命名冲突** → `plugins/ida_multi_mcp.py` 若报 "is not a package"，改名为 `mcp_multi_loader.py` 并注入 venv 路径。
6. **阅文 Fock SDK 魔改 QuickJS** → 字节码版本号 `0x46` ('F')，标准 qjs 无法反编译。fockrt JS 逻辑通过 `evaluate2(byte[])` 加载，字节码缓存在 `com.yuewen.fockrt.files.xml` 的 Base64 `d` 字段中。
7. **ruyi-mcp 断点为软断点** → BiDi 协议无调试域，Firefox CDP 已于 v141 移除。`ruyi_set_breakpoint_on_text` 通过 preload script + Proxy 包装实现。可获取 `Error().stack` 调用栈字符串，但无法单步/作用域枚举。完整分析见 `docs/ruyi-mcp-devtools-调试能力分析.md`。短期可通过 Proxy 通信通道增强到 Level 2 软断点（覆盖 ~70% 需求），中期需 ruyipage 内核暴露 SpiderMonkey `Debugger` API。
8. **ruyi-mcp proxy 需在 launch 时设置** → `ruyi_new_page` 的 `proxy` 参数在启动浏览器时生效，启动后无法切换代理。多代理用多标签 container tab（后续版本支持）。
9. **First 微信小程序调试 — WMPF 版本偏移量** → 开源版仅覆盖至 19823，新版 WMPF 需从编译版 v1.1.3（存档于 `storage\First-release\`）提取配置。方法：`pyinstxtractor-ng First.exe` → `find . -name "addresses.*.json"` → 复制到 `tools\First\frida\config\win\`。
10. **NDK 交叉编译** → NDK r29 安装在 `tools\android-ndk\`，未纳入 Git。编译前确认 `tools\android-ndk\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android33-clang.cmd` 存在。
11. **Rust 交叉编译** → 需 `rustup target add aarch64-linux-android x86_64-linux-android`。`.cargo/config.toml` 的 NDK 路径已通过 `tools\android-ndk\` 重定位。
12. **Shadow Hook Frida JS agent 能力边界** → 仅做公开 API 过滤（dl_iterate_phdr / maps read），无法从 linker 内部 solist 摘除 soinfo。如需完整摘除，编译 `tools\hide-soinfo\`。

## 已知缺漏

- **仓库已初始化 Git** — `docs/Git与提交规范.md` 中的规则已生效。提交前须检查 diff、提交信息须描述真实改动。
- **大文件未纳入 Git** — `resource/portable_win/`、`tools/jdk/`、`tools/node/` 等大文件在 `.gitignore` 中排除，通过磁盘路径直接引用。

## 脚本速查

所有脚本为 `.ps1`，绝对路径调用：`powershell -File "D:\reverse_ENV\skill\<name>\scripts\<script>.ps1"`

| 领域 | 脚本 | 一行用途 |
|------|------|---------|
| APK | `decode.ps1` | jadx+apktool 落盘 |
| APK | `frida-run.ps1` | Frida 注入 |
| APK | `rebuild-sign-install.ps1` | 重建→签名→安装 |
| APK | `manifest-summary.ps1` | Manifest 摘要 |
| IDA | `start.ps1` | 环境验证 |
| IDA | `open.ps1` | idalib 打开文件 |
| r2 | `recon.ps1` | 一站式侦察 |
| LDPlayer | `re-init.ps1` | RE 实例初始化（创建→配置→启动） |
| LDPlayer | `re-proxy.ps1` | HTTPS 代理 on/off |
| LDPlayer | `re-list.ps1` | 实例状态一览 |
| LDPlayer | `re-destroy.ps1` | 停止/删除实例 |

> 脚本详情见 `docs/脚本参考.md`

## 工具速查

| 工具 | 路径 |
|------|------|
| jadx 1.5.5 | `tools\jadx\bin\jadx.bat` |
| apktool 3.0.2 | `tools\apktool\apktool.bat` |
| radare2 6.1.8 | `tools\radare2\bin\radare2.exe` |
| frida 17.15.3 | `.venv\Scripts\frida.exe` |
| adb 1.0.41 | `tools\adb\adb.exe` |
| zipalign (build-tools 33) | `tools\adb\zipalign.exe` |
| apksigner 0.9 | `tools\adb\apksigner.bat` |
| LDPlayer 9 底层管控 | `tools\ldplayer\ldplayer.ps1` （RE 管理用 `skill\ldplayer-control\scripts\`） |
| Chromium 152 (手动调试) | `tools\chromium\chrome-win\chrome.exe` (9222 headless) |
| js-reverse-mcp 包装脚本 | `powershell -File tools\chromium\start-js-reverse.ps1` |
| ruyipage 指纹浏览器 | `.venv\Scripts\python.exe -m ruyipage` |
| ruyiTrace DOM 追踪 | `tools\ruyitrace\ruyitrace.ps1` |
| ruyi-mcp (Web 增强 MCP) | `tools\node\node.exe ruyi-mcp\build\src\index.js` |
| reqable-mcp (抓包数据查询) | `.venv\Scripts\reqable-mcp.exe mcp` |
| JDK 21 | `tools\jdk\` |
| Node.js 20.20.2 | `tools\node\node.exe` |
| MinGW-w64 14.2.0 (C/GCC) | `tools\mingw64\mingw64\bin\gcc.exe` |
| QuickJS (qjs_min) | `tools\quickjs\qjs_min.exe` |
| First (微信小程序调试) | `powershell -File tools\First\first-gui.ps1` |
| First CLI (无头模式) | `powershell -File tools\First\first-cli.ps1` |
| Shadow Hook 隐身工具 | `python skill\native-reverse\scripts\tools\shadow-hook\stealth-runner.py` |
| hide-soinfo C 库 | `tools\hide-soinfo\` (需 NDK 编译) |
| stealth-hook-engine | `tools\stealth-hook-engine\` (需 NDK 编译) |
| Android NDK r29 | `tools\android-ndk\` |
| Rust 工具链 | `%USERPROFILE%\.cargo\bin\rustc.exe` |
| Serena (user MCP) | `tools\serena\` (uv run) |
| Deepcon (user MCP) | `tools\node\npx.cmd -y deepcon-mcp` |

> 完整清单见 `docs/工具与环境.md`
