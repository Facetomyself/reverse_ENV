# reverse_ENV

逆向工程环境配置与技能仓库。为 AI 辅助逆向分析提供统一工具链、MCP 服务、技能编排和知识库管理。

## 核心能力

| 领域 | 能力 | 工具链 |
|------|------|--------|
| **Android APK** | 脱壳、反编译、签名算法还原、Frida 动态注入、Native .so 反检测 | jadx + apktool + Frida + IDA Pro |
| **iOS IPA** | 静态分析、Mach-O 解析 | radare2 + IDA Pro |
| **Web JS** | 反检测浏览、指纹取证、JS 逆向、签名/Token 提取、补环境 | ruyi-mcp (Firefox/BiDi) + js-reverse-mcp (Chrome/CDP) |
| **Native 二进制** | PE/ELF/DLL/SO 深度静态分析、反汇编、反编译、Patch | IDA Pro + radare2 |
| **网络协议** | 抓包分析、TLS 解密、签名还原、Python 采集器 | Reqable + Frida + mitmproxy |
| **模拟器管理** | LDPlayer 多实例模板、一键 Root+Magisk+LSPosed+CA 证书 | ldconsole + adb + Magisk/Kitsune |
| **代理管理** | 多供应商代理提取、验证、注入浏览器/脚本 | 快代理 + Cliproxy |

## 仓库结构

```
reverse_ENV/
├── skill/              # 技能定义（SKILL.md + scripts + references）
│   ├── reverse-coordinator/   # 元 skill — 分类→路由→编排→交付
│   ├── apk-reverse/           # Android APK 逆向
│   ├── ida-reverse/           # IDA Pro 深度分析
│   ├── ruyi-reverse/         # Web JS 逆向（统一入口）
│   ├── mcp-js-reverse-playbook/  # CDP 断点调试
│   ├── native-reverse/       # Native .so 反检测/绕过
│   ├── radare2/              # radare2 CLI 快速侦察
│   ├── ldplayer-control/     # 雷电模拟器实例管理
│   ├── proxy-usage/          # 代理统一管理
│   ├── web-env-patcher/      # Node.js 补环境
│   ├── protocol-recovery/    # 签名 → Python 采集器
│   ├── article-archiver/     # 文章知识库归档
│   └── reverse-engineering/  # CTF 参考知识库
├── .agents/skills/    # Codex 薄封装入口 → skill/
├── mcp/               # MCP 服务源码
│   ├── ruyi-mcp/             # Public submodule；Firefox/BiDi 增强逆向（56 tools）
│   ├── js-reverse-mcp/       # Chrome/CDP 调试
│   ├── jadx-mcp-server/      # jadx GUI MCP 服务端
│   └── reqable-mcp/          # Reqable 抓包数据查询
├── docs/              # 规范文档
│   ├── 工具与环境.md          # 工具版本、路径、安装说明
│   ├── 逆向工作流详解.md      # 逆向分析工作流与深度等级
│   ├── Web逆向架构分析.md     # Web RE 双 MCP 架构设计
│   ├── App逆向环境规划.md     # 模拟器多实例模板策略
│   ├── MCP服务详情.md         # MCP 架构、配置、工具清单
│   ├── AI开发规范.md          # AI 协作开发规范
│   ├── 脚本参考.md            # 脚本调用规范
│   └── article-index.md      # 独立知识库索引兼容入口
├── article/           # Private 知识库 submodule
│   ├── INDEX.md              # canonical index
│   ├── anti-detection/       # 反检测/指纹对抗
│   ├── protocols/            # 协议分析（MMTLS 等）
│   ├── signature-algorithms/ # 签名算法分析
│   ├── native-analysis/      # Native 层分析
│   ├── packing-bypass/       # 加固绕过
│   ├── web-reverse/          # Web 逆向
│   └── mobile-app-reverse/   # 移动应用逆向
├── tools/             # 便携工具链（不纳入 Git，本地部署）
├── resource/          # 二进制资源（portable_win、kg_patch 等）
├── storage/           # 可复用大文件（安装包、SDK、ISO）
├── workspace/         # 项目工作区（每个逆向项目一个子目录）
└── CLAUDE.md          # Claude Code 项目指令
```

## 前置条件

本仓库设计为 **自包含便携环境**，所有工具安装在仓库内，不污染系统全局。

| 组件 | 路径 | 说明 |
|------|------|------|
| Python venv | `.venv/` | Python 3.x + frida 等工具 |
| JDK 21 | `tools/jdk/` | jadx/apktool 运行依赖 |
| Node.js 20 | `tools/node/` | MCP 服务运行环境 |
| Android NDK r29 | `tools/android-ndk/` | Native 编译（Frida gadget 等） |
| Rust 工具链 | `%USERPROFILE%/.cargo/` | 交叉编译 aarch64/x86_64-android |
| IDA Pro 9.3 | `resource/portable_win/` | 反编译/反汇编核心工具 |

> 完整工具清单与安装说明见 `docs/工具与环境.md`。

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Facetomyself/reverse_ENV.git
cd reverse_ENV
git submodule update --init --recursive
```

其中 `mcp/ruyi-mcp` 来自公开仓库 [`Facetomyself/ruyi-mcp`](https://github.com/Facetomyself/ruyi-mcp)，主仓通过 gitlink 固定已验证版本。

### 2. 部署本地工具

本仓库 `.gitignore` 排除了大型二进制文件。需手动部署以下组件：

- `resource/portable_win/` — IDA Pro 9.3 便携版
- `tools/jdk/` — JDK 21
- `tools/node/` — Node.js 20
- `tools/jadx/` — jadx 1.5.5
- `tools/radare2/` — radare2 6.1.8
- `tools/android-ndk/` — Android NDK r29
- `tools/chromium/` — Chromium 152（备选浏览器）

详见 `docs/工具与环境.md`。

### 3. 初始化 Python 环境

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt  # 如有
```

### 4. 验证环境

```powershell
# 验证 IDA 环境
powershell -File "skill/ida-reverse/scripts/start.ps1"

# 验证 MCP 服务
.venv\Scripts\python.exe -m ida_multi_mcp --help
```

## 典型工作流

### Android APK 逆向

```
Phase 0 指纹 → Phase 1 静态解包(jadx+apktool) → Phase 2 动态分析(Frida)
  → Phase 3 深度分析(IDA/Kotlin恢复) → Phase 4 算法还原 → Phase 5 产出
```

### Web JS 逆向

```
ruyi-reverse（反检测浏览 + Hook + Trace 取证）
  → web-env-patcher（Node 补环境，签名/Token 生成）
  → protocol-recovery（Python 采集器）
```

### Native .so 反检测

```
native-reverse（syscall 定位 → dump/fix → IDA 分析 → Patch → 验证）
```

> 详见 `docs/逆向工作流详解.md`。

## MCP 服务

本仓库提供 4 个项目级 MCP 服务：

| 服务 | 传输 | 核心能力 |
|------|------|---------|
| `ida-multi-mcp` | stdio | IDA Pro 反编译/反汇编/xref/patch/类型/栈帧（44 tools） |
| `ruyi-mcp` | stdio | Firefox/BiDi 反检测/指纹/trace/人类模拟/软断点（56 tools） |
| `js-reverse-mcp` | stdio | Chrome/CDP 完整断点调试/脚本/网络/运行时（22 tools） |
| `jadx-mcp-server` | stdio | jadx GUI APK 类/方法搜索/反编译/xref |

> 详见 `docs/MCP服务详情.md`。

## 技能（Skills）

所有逆向工作通过 Skill 编排执行。核心路由：

- **未指定工具** → `reverse-coordinator`（自动分类→路由→编排→交付）
- **Android APK** → `apk-reverse`
- **IDA 二进制分析** → `ida-reverse`
- **Web JS** → `ruyi-reverse`（默认首选）+ `mcp-js-reverse-playbook`（需 CDP 调试时）
- **Native 反检测** → `native-reverse`
- **Web 补环境** → `web-env-patcher` → `protocol-recovery`

> 完整 Skill 清单与使用场景见 `skill/README.md`。

## 贡献指南

1. 所有产出物落地到 `workspace/<项目名>/`
2. 分析完成后按模板交付：`report.md` + `findings.json` + `triage.md`
3. 有跨项目复用价值的分析文章归档到 `article/` 并更新 `article/INDEX.md`，随后在主仓更新 gitlink
4. 新增/修改 Skill 时同步更新 `skill/README.md` 和 `.agents/skills/`
5. 提交前执行自检：`git diff --stat` + `git diff --check`
6. 提交信息描述真实改动，不写 "update" / "fix"

> 详见 `docs/AI开发规范.md` 和 `docs/Git与提交规范.md`。

## 免责声明

本仓库提供的工具、技能和知识库**仅用于安全研究、教育目的和授权的安全测试**。

- 未经授权对第三方应用/服务进行逆向工程可能违反相关服务条款和法律法规
- 使用者应遵守所在地法律法规，在合法授权范围内使用本仓库工具
- 本仓库作者不对任何滥用、非法使用或因此产生的法律后果承担责任
- 仓库中不包含任何第三方应用的原始代码、二进制文件、API 密钥或用户数据

## License

MIT
