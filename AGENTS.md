# 逆向工程环境配置与技能仓库（Codex）

本文件与 `CLAUDE.md` 并存，功能对等。Codex 在 `D:\reverse_ENV` 及子目录下工作时自动加载。

> MCP 已在 `~/.codex/config.toml` 中配置，与 `.mcp.json` 对等：ida-multi-mcp、jadx-ai-mcp、jsreverser-mcp、ruyi-mcp、first-mcp、reqable。

## 任务前强制检查

| # | 检查项 | 动作 |
|---|--------|------|
| 1 | **WebFetch 封禁** | 需要取 URL 内容？→ 禁止 WebFetch，走 `search-layer` / `github-solution-research` / 浏览器方案 |
| 2 | **知识库检索** | 新项目/新分析任务？→ 查 `docs/article-index.md` 按主题/技术标签检索现成文章 |
| 3 | **搜索** | 新任务/新问题？→ `search-layer` → `github-solution-research`，确认无现成方案再动手 |
| 4 | **Git 状态** | `git status --short --branch` |
| 5 | **远端同步** | `git remote -v`；涉及 PR/远端时 `git fetch origin && git log --oneline origin/main..HEAD` |

> WebFetch 硬封禁：即使 URL 看起来可访问，也不得直接调用 WebFetch。优先用 `search-layer` (搜索)、`github-solution-research` (GitHub)、浏览器 MCP (需登录/JS 渲染)。**此规则优先于所有其他工具选择逻辑。**

## 核心约束

**所有 skill、MCP、Python venv、工具依赖均安装在 `D:\reverse_ENV\` 内，不得污染系统全局。**

- venv: `.venv\` ｜ JDK: `tools\jdk\` ｜ Node: `tools\node\`
- NDK r29: `tools\android-ndk\` ｜ Rust: `%USERPROFILE%\.cargo\`
- IDA Pro 9.3: `resource\portable_win\` ｜ MCP 配置: `.mcp.json` + `~/.codex/config.toml`
- **所有逆向项目在 `workspace\<项目名>\` 下起新文件夹**。产出物均落地到对应项目目录。
- **待分析二进制文件**（`.dll`, `.so`, `.exe`, `.bin` 等）**必须先放入 `workspace\<项目名>\`**，再打开 IDA/radare2。禁止将二进制文件直接放在 `workspace\` 根目录。
- **IDA 数据库文件**（`.id0`, `.id1`, `.id2`, `.nam`, `.til`, `.i64`）由 IDA 在二进制文件所在目录自动生成。确保二进制文件在项目子目录内，即可避免 IDA 产物污染根目录。
- **抓包流量文件**（`*.flow`, `*.pcap`, `*.har`）统一放在 `workspace\<项目名>\` 下。
- **`storage\` 存放可复用的大文件**（安装包、SDK、ISO 等），内容不纳入 Git。

### AI 协作子约束

> 详见 `docs/AI开发规范.md` 和 `docs/Git与提交规范.md`

**操作纪律：**
1. **不得凭记忆** — 修改文件前 Read 实际内容，不基于摘要操作。
2. **先确认、再动手** — 确认当前目录、文件存在、工具可用。
3. **改动闭环** — 改脚本 → 同步 CLAUDE.md + AGENTS.md；改工具路径 → 同步 skill 文档；加项目 MCP → 同步 `.mcp.json` + `~/.codex/config.toml`。
4. **禁止猜测** — 工具安装、命令执行必须有真实输出为证。

**编码：**
5. UTF-8 + LF 新文件；已有 BOM 保留 BOM；中文文件防乱码。
6. 路径全部绝对化，不依赖 PATH。
7. **禁止滥用 emoji** — 文档、代码注释、CLAUDE.md/AGENTS.md、skill 文件、提交信息中不使用 emoji 作为项目符号或装饰。用纯文本标记（`-`/`*`/`#`）替代。

**渐进式披露：**
8. **先侦察、后深挖** — 从轻量 triage 开始，根据 marker 决定深度。不得一上来全量分析/盲目 Hook。
9. **证据优先** — 每个结论必须有可追溯证据。未经证实的标注"待验证"。
10. **能力匹配复杂度** — L1 便携 → L2 上下文 → L3 运行时 → L4 triage-only。不假装能完整还原 WASM/VM。

**产出规范：**
11. 每次分析产出三件套：`report.md` + `findings.json` + `triage.md`（模板: `skill/reverse-coordinator/templates/`）。
12. **审查门** — 产出前自检：claim 有证据？triage 已标注？敏感数据已脱敏？
13. **不得假装** — 不对 L4 目标声称"已完整复现"。

**修改闭环：**
14. 自检：CLAUDE.md/AGENTS.md 路径一致？`.mcp.json` + `config.toml` 合法？临时文件已清理？敏感数据已脱敏？

## 仓库入口

| 想看什么 | 去哪里 |
|----------|--------|
| **完整目录树** | 各目录 README: `skill/README.md`, `tools/README.md`, `mcp/README.md`, `docs/README.md`, `workspace/README.md`, `resource/README.md`, `storage/README.md` |
| 工具版本与路径 | `tools/README.md` + `docs/工具与环境.md` |
| MCP 服务配置详情 | `mcp/README.md` + `docs/MCP服务详情.md` |
| Skill 清单 | `skill/README.md` |
| 工作流与深度等级 | `docs/逆向工作流详解.md` |
| Web 逆向架构分析 | `docs/Web逆向架构分析.md` |
| ruyi-mcp 引导方案 | `docs/ruyi-mcp-引导方案.md` |
| 脚本使用说明 | `docs/脚本参考.md` |
| AI 协作开发规范 | `docs/AI开发规范.md` |
| Git 操作规范 | `docs/Git与提交规范.md` |
| **逆向知识库索引** | `docs/article-index.md` — 按主题/技术标签检索跨项目可复用分析文章 |
| 逆向知识库文章 | `article/` — 协议分析/反检测/签名算法/加固绕过/Native分析/Web逆向 |

## 任务前知识库检索（硬纪律）

**新项目/新分析任务启动时，必须先查 `docs/article-index.md`**，确认是否有现成的同主题/同厂商/同技术栈分析文章可复用。跳过 → 违规。

| 场景 | 检索方向 |
|------|---------|
| 遇到新协议 | 查 `article/protocols/` + 标签「协议」 |
| 遇到签名/加密 | 查 `article/signature-algorithms/` + 标签「密码学」 |
| 遇到反调试/加固 | 查 `article/packing-bypass/` + 标签「反检测/对抗」 |
| 遇到 Web 框架/打包 | 查 `article/web-reverse/` + 标签「Webpack」 |
| 遇到风控/验证码 | 查 `article/anti-detection/` + 标签「WAF」「设备指纹」 |

## Skill 速查

| Skill | 场景 | 何时用 |
|-------|------|--------|
| `reverse-coordinator` | **元 skill** | 未指定工具时优先——分类→路由→编排→交付 |
| `apk-reverse` | Android APK | jadx/apktool/frida/adb + 指纹/脱壳/Kotlin类名恢复/API提取 |
| `ida-reverse` | PE/ELF/DLL/SO | IDA Pro 深度分析 + IDAPython速查/符号恢复/结构体恢复 |
| `ruyi-reverse` | Web JS — 统一编排器 | 7 能力模块 x 深浅两级，按任务主动组合。**唯一入口** |
| `proxy-usage` | 代理统一管理 | 快代理 + Cliproxy 双供应商 — 选型→提取→验证→注入 |
| `radare2` | 通用二进制 | CLI 快速侦察/反汇编/patch |
| `native-reverse` | Android Native .so 反检测/绕过 | syscall 定位→dump/fix→IDA→patch→验证 |
| `ldplayer-control` | 雷电模拟器 RE 实例管理 | re-init/re-proxy/re-list/re-destroy — 项目实例隔离 |
| `protocol-recovery` | Web 协议恢复 | 签名→Python 采集器 |
| `github-solution-research` | GitHub 方案搜索 | 问题→证据→方案 |
| `project-agents-governance` | 项目规范治理 | 生成/维护 CLAUDE.md + AGENTS.md |
| `prompt` | 提示词优化 | 诊断+优化 |
| `drawio` | 流程图/架构图 | .drawio 文件生成与导出 |
| `docx-thesis-formatter` | DOCX 格式化 | 论文/报告模板 |

**路由**: `.so`/native 反检测/绕过 → `native-reverse`；`.so` 纯静态分析 → `ida-reverse`/`radare2`；APK Java → `apk-reverse`。
**Web JS 路由**: **默认 -> `ruyi-reverse`（统一编排器）** — 7 模块 x 两级深度，按任务主动组合。需 CDP 完整断点调试且无反检测需求 -> jsreverser-mcp。

## 工作流速查

```
知识库检索(article-index) → 多源搜索(search-layer + github-solution-research) → APK指纹(fingerprint.sh, 非Native则停止)
  → 分类(文件类型/平台) → 最小侦察(字符串/导入/manifest) → 决策(L1-L4深度) → 定向深挖(仅在确认后)
  → 产出三件套 → 审查门 → 知识库回填(有跨项目价值的分析)
```

> 多源搜索约束见全局 `~/.codex/AGENTS.md`。详细规范: `docs/搜索编排规范.md`。

**不得跳阶段。L4 目标不声称完整还原。**

## MCP 工具前缀

| 前缀 | 服务 | 用途 |
|------|------|------|
| `idapro_*` | ida-multi-mcp | 反编译/反汇编/xref/patch/类型/栈帧 (~72 tools) |
| `idalib_*` | ida-multi-mcp | headless 会话管理 (open/close/list) |
| `jadx_*` | jadx-ai-mcp | APK 类/方法搜索/反编译/xref |
| `jsreverser_*` | jsreverser-mcp | JS 逆向调试 — 断点/脚本/网络/运行时 (~73 tools) |
| `ruyi_*` | ruyi-mcp | Firefox/BiDi 全链路增强 — 反检测/指纹/人类模拟/trace/JS逆向 (~41 tools) |
| `reqable_*` | reqable-mcp | Reqable 抓包数据查询 — HTTP/WebSocket 流量搜索/分析/代码生成 (~17 tools) |

> **Web RE 双 MCP**: jsreverser-mcp (npx/CDP) 调试优先；`ruyi-mcp` (Firefox/BiDi) 增强全能 — 反检测/指纹/trace/人类模拟。按需求能力选择，可互补协作。详见 `docs/Web逆向架构分析.md`。

> MCP 服务详情见 `docs/MCP服务详情.md`

### MCP 服务组织约束

**所有 MCP 服务代码统一在 `mcp/` 目录下管理。**

| 规则 | 说明 |
|------|------|
| 源码归属 | MCP 源码/项目必须在 `mcp/` 下，不得散落根目录或 `tools/` |
| 配置同步 | 新增/变更 MCP 时，同步更新 `.mcp.json` + `~/.codex/config.toml` + `CLAUDE.md` + `AGENTS.md` + `mcp/README.md` + `docs/MCP服务详情.md` |
| pip 管理标注 | pip 安装的 MCP 在 `mcp/README.md` 中标注包名和 venv 位置 |
| 硬编码路径 | MCP 启动脚本中的路径必须使用 `mcp/` 前缀 |

### Web RE 双 MCP 约束

jsreverser-mcp 和 ruyi-mcp 是两个**互补**的 Web RE MCP 服务，按需求能力选择，可协作：

| MCP 服务 | 浏览器/协议 | 核心优势 | 适用场景 |
|---------|-------------|---------|---------|
| jsreverser-mcp | Chrome / CDP | **完整 JS 断点调试**（断点/单步/调用栈/作用域） | 需要 CDP 级运行时调试、无强反检测要求 |
| ruyi-mcp | Firefox / BiDi | **反检测 + 指纹分析 + trace + 人类模拟** | 需要过验证码、指纹取证、DOM trace、人类行为模拟（**所有站点通用**） |

**选择规则：**
1. 需要 CDP 完整断点调试（`get_paused_info`、`step`、调用栈查看）→ 用 jsreverser
2. 需要指纹分析、DOM trace、过 Cloudflare/hCaptcha、反检测浏览 → 用 ruyi（**无论目标站点反检测强度如何**）
3. 两者可互补：`ruyi_export_session` → 导出 Cookie/Storage → jsreverser 继续 CDP 调试

### 反检测能力边界（指纹伪装）

| 伪装维度 | ruyipage (Firefox/fpfile) | CloakBrowser (Chromium/C++) | 说明 |
|---------|--------------------------|---------------------------|------|
| navigator.webdriver | ✅ fpfile webdriver:0 | ✅ C++ 层清除 | |
| Canvas 指纹 | ✅ 随机种子 | ✅ C++ patched | |
| WebGL (12字段) | ✅ 22 个真实 GPU profile | ✅ C++ patched | |
| AudioContext | ❌ 不覆盖 | ✅ C++ patched | |
| 字体枚举 | ✅ font_system | ✅ C++ 层控制 | |
| 硬件并发 | ✅ 22 个真实值 | ✅ C++ 层控制 | |
| WebRTC IP | ✅ public/private IP | ✅ C++ 层阻止泄露 | |
| 时区/语言 | ✅ fpfile + BiDi 双层 | ✅ geoip 自动匹配 | |
| TLS 指纹 | ❌ Firefox 原生 TLS | ✅ 对齐真实 Chrome | **ruyi 碰不到** |
| CDP 协议痕迹 | ❌ 不适用(BiDi无CDP) | ✅ C++ 层清除 | |

**路由决策（按检测深度）：**

```
页面 → 查 navigator/canvas/webgl? (JS 层检测)
  ├─ 是 → ruyipage 22 profile 够了
  ├─ 查 TLS / CDP / 网络时序? (协议层检测)
  │   └─ 是 → CloakBrowser
  └─ 查 AudioContext / 自动化标记?
      └─ 是 → CloakBrowser
```

## WebFetch 使用约束

**禁止直接使用 WebFetch。** WebFetch 有结构性限制，项目内已有成熟替代：

| 场景 | 走哪个 |
|------|--------|
| 搜索/查事实/找资料 | `search-layer`（四源并行 + 去重打分） |
| GitHub 代码/Issue/PR 深挖 | `github-solution-research` |
| 需登录/Cookie/JS 渲染的页面 | `ruyi_*` / `jsreverser_*` 浏览器方案 |

## 已知坑点

1. **idalib 孤儿进程** → `start.ps1` 用 `taskkill /F /T` 杀进程树。
2. **System32 文件无权限** → `open.ps1` 自动复制到 `%TEMP%\opencode\`。
3. **IDA 许可单实例** → GUI 和 headless 互斥，跑 headless 前关 GUI。
4. **jadx-ai-mcp 需先开 GUI** → `tools\jadx-gui.cmd` 启动并加载 APK 后 MCP 才可用。
5. **ruyi-mcp proxy 需在 launch 时设置** → 启动后无法切换代理。
6. **NDK 交叉编译** → `tools\android-ndk\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android33-clang.cmd`
7. **LDPlayer RE 模拟器** → RE 实例（emulator-5556），Root + Frida 17.15.3 + Kitsune Mask v27.0
8. **Rust 交叉编译** → 需 `rustup target add aarch64-linux-android x86_64-linux-android`
9. **PowerShell UTF-8 BOM** → SKILL.md 必须无 BOM，否则 frontmatter 识别失败

## 脚本速查

PS 脚本绝对路径调用：`powershell -File "D:\reverse_ENV\skill\<name>\scripts\<script>.ps1"`；bash 脚本用 `bash D:/reverse_ENV/skill/<name>/scripts/<script>.sh`。

| 领域 | 脚本 | 一行用途 |
|------|------|---------|
| APK | `fingerprint.sh` | Phase 0 快速指纹（框架/混淆度/HTTP栈/下一步） |
| APK | `decode.ps1` | jadx+apktool 落盘 |
| APK | `frida-run.ps1` | Frida 注入 |
| APK | `rebuild-sign-install.ps1` | 重建→签名→安装 |
| APK | `manifest-summary.ps1` | Manifest 摘要 |
| APK | `recover-kotlin-names.sh` | Phase 3.5 R8 混淆类名恢复 |
| APK | `lookup-name.sh` | 查询类名映射 (obf->real/搜索/标注grep) |
| APK | `find-api-calls.sh` | Phase 5 HTTP API 提取 (7库+URL分桶+HMAC) |
| APK | `init-ldplayer-re.ps1` | LDPlayer RE 模拟器环境一键初始化 |
| APK | `dex-dump.js` | Frida DEX 内存 Dump (三种策略抗加固壳) |
| APK | `backup-ldplayer-re.ps1` | 雷电 RE 实例备份/还原 |
| IDA | `start.ps1` / `open.ps1` | 环境验证 / idalib 打开文件 |
| r2 | `recon.ps1` | 一站式侦察 |
| LDPlayer | `re-init.ps1` / `re-proxy.ps1` / `re-list.ps1` / `re-destroy.ps1` | 实例管理 |
| Proxy | `proxy_check.py` / `kuaidaili_extract.py` / `cliproxy_test.py` | 代理验证/提取 |

## 工具速查

| 工具 | 路径 |
|------|------|
| jadx 1.5.5 | `tools\jadx\bin\jadx.bat` |
| apktool 3.0.2 | `tools\apktool\apktool.bat` |
| Vineflower 1.11.2 | `tools\vineflower\vineflower-1.11.2.jar` |
| radare2 6.1.8 | `tools\radare2\bin\radare2.exe` |
| frida 17.15.3 | `.venv\Scripts\frida.exe` |
| adb 1.0.41 | `tools\adb\adb.exe` |
| zipalign / apksigner | `tools\adb\` |
| LDPlayer 9 | `tools\ldplayer\ldplayer.ps1` |
| Node.js | `tools\node\node.exe` |
| JDK 21 | `tools\jdk\` |
| MinGW-w64 14.2.0 | `tools\mingw64\mingw64\bin\gcc.exe` |
| NDK r29 | `tools\android-ndk\` |
| Rust | `%USERPROFILE%\.cargo\` |
| uv | `.venv\Scripts\uv.exe` |
| Python | `.venv\Scripts\python.exe` |
| jsreverser-mcp | `tools\node\npx.cmd jsreverser-mcp` |
| ruyi-mcp | `tools\node\node.exe mcp\ruyi-mcp\build\src\index.js` |
| reqable-mcp | `.venv\Scripts\reqable-mcp.exe mcp` |
| First (微信小程序) | `powershell -File tools\First\first-gui.ps1` |
| Google Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` |

## 提交前自检（硬门禁）

```powershell
git status --short
git diff --stat
git diff --check
```

- 提交信息须描述真实改动
- 确认无临时文件、敏感数据、调试日志混入
- 涉及脚本/工具路径变更 → 同步 CLAUDE.md + AGENTS.md + skill 文档
- 涉及 MCP 配置变更 → 同步 `.mcp.json` + `~/.codex/config.toml`

## 大任务自动刷新

满足以下条件时，**先更新 CLAUDE.md + AGENTS.md，再写代码**：

- 新增/移除 skill、MCP、工具
- 任务跨 3 个及以上 `skill/` / `tools/` / `docs/` 顶层目录
- 涉及工作流变更（如新增逆向阶段、新增平台支持）

## 本文件维护规则

- 路径变更必须同步更新 CLAUDE.md + AGENTS.md；工具版本号变更必须同步更新
- 目录不存在或命令不可用时，标注（待建）或（待验证），不得保留过期路径
- 规范与真实仓库冲突时，以真实仓库为准，并立即更新本文件
