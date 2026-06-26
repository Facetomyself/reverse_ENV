# CLAUDE.md

逆向工程环境配置与技能仓库。为 Claude Code 提供 skills、MCP 服务、工具脚本。

## 核心约束

**所有 skill、MCP、Python venv、工具依赖均安装在 `D:\reverse_ENV\` 内，不得污染系统全局。**

- venv: `.venv\` ｜ JDK: `tools\jdk\` ｜ Node: `tools\node\`
- IDA Pro 9.3: `resource\portable_win\` ｜ MCP 配置: `.mcp.json`
- **所有逆向项目在 `workspace\<项目名>\` 下起新文件夹**。产出物（report/findings/triage/脚本）均落地到对应项目目录。

### AI 协作子约束

> 详见 `docs/AI开发规范.md` 和 `docs/Git与提交规范.md`

**操作纪律：**
1. **不得凭记忆** — 修改文件前 Read 实际内容，不基于摘要操作。
2. **先确认、再动手** — 确认当前目录、文件存在、工具可用。
3. **改动闭环** — 改脚本 → 同步 CLAUDE.md；改工具路径 → 同步 skill 文档；加 MCP → 同步 `.mcp.json`。
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
13. 自检：旧用户名 `25286`？旧路径 `D:\APP\IDA`？CLAUDE.md 路径一致？`.mcp.json` 合法？临时文件已清理？敏感数据已脱敏？

## 仓库入口

| 想看什么 | 去哪里 |
|----------|--------|
| 完整目录树 | `docs/仓库结构.md`（待建，或 `ls -R` 查看） |
| 工具版本与路径 | `docs/工具与环境.md` |
| MCP 服务配置详情 | `docs/MCP服务详情.md` |
| 工作流与深度等级 | `docs/逆向工作流详解.md` |
| 脚本使用说明 | `docs/脚本参考.md` |
| AI 协作开发规范 | `docs/AI开发规范.md` |
| Git 操作规范 | `docs/Git与提交规范.md` |

## Skill 速查

| Skill | 场景 | 何时用 |
|-------|------|--------|
| `reverse-coordinator` | **元 skill** | 未指定工具时优先——分类→路由→编排→交付 |
| `apk-reverse` | Android APK | jadx/apktool/frida/adb |
| `ida-reverse` | PE/ELF/DLL/SO | IDA Pro 深度分析 |
| `mcp-js-reverse-playbook` | Web JS | js-reverse-mcp 浏览器取证 |
| `radare2` | 通用二进制 | CLI 快速侦察/反汇编/patch |
| `reverse-engineering` | 知识库 | CTF 模式参考（自动加载，不直接调用） |

**路由**: `.so`/native → `ida-reverse`/`radare2`；APK Java → `apk-reverse`；Web JS → `mcp-js-reverse-playbook`。

## 工作流速查

```
分类(文件类型/平台) → 最小侦察(字符串/导入/manifest) → 决策(L1-L4深度)
  → 定向深挖(仅在确认后) → 产出三件套 → 审查门
```

**不得跳阶段。L4 目标不声称完整还原。**

## MCP 工具前缀

| 前缀 | 服务 | 用途 |
|------|------|------|
| `idapro_*` | ida-multi-mcp | 反编译/反汇编/xref/patch/类型/栈帧 (~72 tools) |
| `idalib_*` | ida-multi-mcp | headless 会话管理 (open/close/list) |
| `jadx_*` | jadx-ai-mcp | APK 类/方法搜索/反编译/xref |
| `js-reverse_*` | js-reverse-mcp | 浏览器操控/断点/Hook/网络分析 (~17 tools) |

> MCP 服务详情见 `docs/MCP服务详情.md`

## 已知坑点

1. **idalib 孤儿进程** → `start.ps1` 用 `taskkill /F /T` 杀进程树。
2. **System32 文件无权限** → `open.ps1` 自动复制到 `%TEMP%\opencode\`。
3. **IDA 许可单实例** → GUI 和 headless 互斥，跑 headless 前关 GUI。
4. **jadx-ai-mcp 需先开 GUI** → `tools\jadx-gui.cmd` 启动并加载 APK 后 MCP 才可用。
5. **Plugin 命名冲突** → `plugins/ida_multi_mcp.py` 若报 "is not a package"，改名为 `mcp_multi_loader.py` 并注入 venv 路径。

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
| JDK 21 | `tools\jdk\` |
| Node.js 20.20.2 | `tools\node\node.exe` |

> 完整清单见 `docs/工具与环境.md`
