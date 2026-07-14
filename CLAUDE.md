# CLAUDE.md

逆向工程环境配置与技能仓库。为 Claude Code 提供 skills、MCP 服务、工具脚本。

## 任务前强制检查

| # | 检查项 | 动作 |
|---|--------|------|
| 1 | **WebFetch 封禁** | 需要取 URL 内容？→ 禁止 WebFetch，走 `search-layer` / `content-extract` / `github-solution-research` / 浏览器方案 |
| 2 | **知识库检索** | 新项目/新分析任务？→ 确认 `article` submodule 已初始化，再查 `article/INDEX.md` |
| 3 | **Git 状态** | `git status --short --branch` |
| 4 | **远端同步** | 读取当前 branch/upstream 后 fetch 对应 remote；禁止把 `origin/main` 硬套到子仓 |

> WebFetch 硬封禁：即使 URL 看起来可访问，也不得直接调用 WebFetch。优先用全局 `search-layer` (WebSearch+Exa+Tavily+Grok 并行)、`content-extract` (国内文章/Markdown)、`github-solution-research` (GitHub)、浏览器 MCP (需登录/JS 渲染)。这些搜索/提取能力属于 Claude 全局 MCP 分级策略，不放入项目 `.mcp.json`。**此规则优先于所有其他工具选择逻辑。**

## 核心约束

**所有 skill、MCP、Python venv、工具依赖均安装在 `D:\reverse_ENV\` 内，不得污染系统全局。**

- 项目 skill 源目录: `skill\<name>\`；Codex repo-scope 发现入口: `.agents\skills\<name>\` 薄封装。
- `.agents\skills\` 只保留 frontmatter 与源 skill 路由说明，不复制脚本/参考资料/流程正文；真实维护仍在 `skill\<name>\`。
- `.agents\skills\<name>\SKILL.md` 必须与 `skill\<name>\SKILL.md` 一一对应，只允许指向源 skill；新增/删除/重命名 skill 时两侧同步。
- venv: `.venv\` ｜ JDK: `tools\jdk\` ｜ Node: `tools\node\`
- NDK r29: `tools\android-ndk\` ｜ Rust: `%USERPROFILE%\.cargo\`
- IDA Pro 9.3: `resource\portable_win\` ｜ MCP 配置: `.mcp.json` + `.codex\config.toml`（Codex 项目层）+ `~/.codex/config.toml`（Codex 用户默认）+ `~/.claude.json`（Claude 全局）
- **所有逆向项目在 `workspace\<项目名>\` 下起新文件夹**。产出物均落地到对应项目目录。
- **待分析二进制文件**（`.dll`, `.so`, `.exe`, `.bin` 等）**必须先放入 `workspace\<项目名>\`**，再打开 IDA/radare2。禁止将二进制文件直接放在 `workspace\` 根目录。
- **IDA 数据库文件**（`.id0`, `.id1`, `.id2`, `.nam`, `.til`, `.i64`）由 IDA 在二进制文件所在目录自动生成。确保二进制文件在项目子目录内，即可避免 IDA 产物污染根目录。
- **抓包流量文件**（`*.flow`, `*.pcap`, `*.har`）统一放在 `workspace\<项目名>\` 下。禁止散落在 `workspace\` 根目录。
- **`storage\` 存放可复用的大文件**（安装包、SDK、ISO 等），内容不纳入 Git。
- **用户级 MCP**（`serena`、`deepcon`）为全局辅助工具，详见下方「全局 MCP 使用约束」。

### Workspace 多仓治理

- `workspace\` 是项目容器，不是一个整体 Git 仓库；项目清单以 `docs/workspace-projects.yaml` 为唯一事实源。
- 非空项目默认建立独立 Private GitHub 仓库。正式 spec、公共工具或被其他仓库直接消费的代码可作为 submodule；目标型逆向项目只登记为 `registry`，不得让主仓克隆链自动拉取全部证据。
- 项目仓只跟踪 README、AGENTS、三件套、原创源码、测试、脱敏 fixture 和 evidence manifest。APK/IPA/SO、IDA 数据库、HAR/PCAP/flow、Cookie、凭据、浏览器 profile、解包与反编译全集不得进入 Git。
- 正在运行或存在归属明确脏改动的项目标记为 `deferred-active`；迁移时禁止对其执行 `checkout`、`reset`、`clean`、`stash`、`rebase`、移动目录或 `submodule absorbgitdirs`。
- 新增、删除、重命名、建仓或变更 remote/submodule 状态时，必须同步 `docs/workspace-projects.yaml`，并运行 `tools/workspace-governance/audit_workspace.py`。
- `article/` 是独立 Public 知识库 submodule；canonical index 位于 `article/INDEX.md`，`docs/article-index.md` 只保留主仓兼容入口。

### AI 协作子约束

> 详见 `docs/AI开发规范.md` 和 `docs/Git与提交规范.md`

**操作纪律：**
1. **不得凭记忆** — 修改文件前 Read 实际内容，不基于摘要操作。
2. **先确认、再动手** — 确认当前目录、文件存在、工具可用。
3. **改动闭环** — 改脚本 → 同步 CLAUDE.md + AGENTS.md；改工具路径 → 同步 skill 文档；加项目 MCP → 同步 `.mcp.json` + `.codex/config.toml`；加 Codex 全局 MCP → 同步 `~/.codex/config.toml`；加 Claude 全局 MCP → 同步 `~/.claude.json`。
4. **禁止猜测** — 工具安装、命令执行必须有真实输出为证。

**编码：**
5. UTF-8 + LF 新文件；已有 BOM 保留 BOM；中文文件防乱码。
6. 路径全部绝对化，不依赖 PATH。
7. **禁止滥用 emoji** — 文档、代码注释、CLAUDE.md、skill 文件、提交信息中不使用 emoji 作为项目符号或装饰。用纯文本标记（`-`/`*`/`#`）替代。已有的表格中如 `✅` `❌` `⚠️` 属功能性标记，可保留但不再新增。

**渐进式披露：**
8. **先侦察、后深挖** — 从轻量 triage 开始，根据 marker 决定深度。不得一上来全量分析/盲目 Hook。
9. **证据优先** — 每个结论必须有可追溯证据。未经证实的标注"待验证"。
10. **能力匹配复杂度** — L1 便携 → L2 上下文 → L3 运行时 → L4 triage-only。不假装能完整还原 WASM/VM。

**产出规范：**
11. 每次分析产出三件套：`report.md` + `findings.json` + `triage.md`（模板: `skill/reverse-coordinator/templates/`）。
12. **审查门** — 产出前自检：claim 有证据？triage 已标注？敏感数据已脱敏？
13. **不得假装** — 不对 L4 目标声称"已完整复现"。

**修改闭环：**
14. 自检：CLAUDE.md/AGENTS.md 路径一致？`.mcp.json` / `.codex/config.toml` / `~/.codex/config.toml` / `~/.claude.json` 合法？临时文件已清理？敏感数据已脱敏？

## 仓库入口

| 想看什么 | 去哪里 |
|----------|--------|
| **完整目录树** | 各目录 README: `skill/README.md`, `tools/README.md`, `mcp/README.md`, `docs/README.md`, `workspace/README.md`, `resource/README.md`, `storage/README.md` |
| 工具版本与路径 | `tools/README.md` + `docs/工具与环境.md` |
| App 逆向环境规划 | `docs/App逆向环境规划.md` |
| MCP 服务配置详情 | `mcp/README.md` + `docs/MCP服务详情.md` |
| Skill 清单 | `skill/README.md` |
| Codex repo-scope skill 入口 | `.agents/skills/README.md` |
| 工作流与深度等级 | `docs/逆向工作流详解.md` |
| Web 逆向架构分析 | `docs/Web逆向架构分析.md` |
| ruyi-mcp 引导方案 | `docs/ruyi-mcp-引导方案.md` |
| ruyi-mcp DevTools 调试能力分析 | `docs/ruyi-mcp-devtools-调试能力分析.md` |
| 脚本使用说明 | `docs/脚本参考.md` |
| AI 协作开发规范 | `docs/AI开发规范.md` |
| Git 操作规范 | `docs/Git与提交规范.md` |
| **逆向知识库索引** | `article/INDEX.md` — 独立知识库 submodule 的 canonical index；`docs/article-index.md` 为兼容入口 |
| 逆向知识库文章 | `article/` — Public submodule，包含协议分析/反检测/签名算法/加固绕过/Native分析/Web逆向 |

## 任务前知识库检索（硬纪律）

**新项目/新分析任务启动时，必须先确认 `article/INDEX.md` 存在；缺失时运行 `git submodule update --init article`，随后按索引检索同主题/同厂商/同技术栈文章。跳过 → 违规。**

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
| `apk-reverse` | Android APK | jadx/apktool/frida/adb + 指纹/脱壳/Kotlin类名恢复/API提取/Vineflower + Frida最佳实践/Unity IL2CPP |
| `ida-reverse` | PE/ELF/DLL/SO | IDA Pro 深度分析 + IDAPython速查/符号恢复/结构体恢复 |
| `mcp-js-reverse-playbook` | Web JS — CDP 调试 | js-reverse-mcp (Chrome/CDP) — 需要完整断点/单步/调用栈时首选 |
| `ruyi-reverse` | Web JS — 统一编排器 | 7 能力模块 (Anti-Detect/Observe/Capture/Trace/Human-Sim/Debug/Export) x 深浅两级，按任务主动组合。**唯一入口** |
| `web-env-patcher` | Web JS Node 补环境 | 接在 ruyi/js-reverse 取证后：隔离 runtime、cURL/HAR 检查、Trace API 覆盖矩阵、fixtures、TLS 门禁 |
| `proxy-usage` | 代理统一管理 | 快代理 + Cliproxy 双供应商 — 选型→提取→验证→注入 (ruyi/requests/curl/mitmproxy) |
| `radare2` | 通用二进制 | CLI 快速侦察/反汇编/patch |
| `reverse-engineering` | 知识库 | CTF 模式参考（自动加载，不直接调用） |
| `native-reverse` | Android Native .so 反检测/绕过 | syscall 定位→dump/fix→IDA→patch→验证 |
| `ldplayer-control` | 雷电模拟器 RE 实例管理 | re-init(-Template 创建/复制) / re-proxy / re-list / re-backup / re-restore / re-destroy — 模板实例 + 项目实例隔离 |
| `protocol-recovery` | Web 协议恢复 | 签名→Python 采集器（接在 mcp-js-reverse-playbook 或 ruyi-reverse 之后） |
| `article-archiver` | 文章知识库归档 | `article/pending` PDF/HTML/Markdown → 清洗 Markdown → 分类归档 → 更新 `article/INDEX.md` |

**路由**: `.so`/native 反检测/绕过 → `native-reverse`；`.so` 纯静态分析 → `ida-reverse`/`radare2`；APK Java → `apk-reverse`。
**APK 逆向主链**: `fingerprint.sh`（框架/加固/ABI）→ `decode.ps1` + `manifest-summary.ps1` → Java/smali/native 主战场决策 → 按需 `dump-dex.ps1` / `frida-run.ps1` / 代理抓包 → patch/重建/API 提取 → 三件套。
**APK 加固分流**: 整体加密、完整 DEX 已回填 → `dump-dex.ps1`（panda）；方法抽取/按需回填 → 标 `partial/triage-only`，转 FART/dexfix 类方案；VMP/Dex2C/壳化 `.so` → `native-reverse`，不得继续把 DEX dump 当完整脱壳。
**APK framework 约束**: Flutter/RN/Unity/壳 marker 可并存；单一 runtime `.so` 不得触发“停止 Java/DEX 分析”，以业务类、bundle、metadata、壳和运行时证据决定 hybrid 主战场。
**微信小程序路由**: PC 微信 WMPF、`.wxapkg`、小程序/小游戏运行时调试 → `wechat-miniapp-re-mcp`（`wxmp_*`）；小程序内嵌 H5 或普通网页 JS 仍按 Web JS 路由处理。
**Web JS 路由**: **默认 -> `ruyi-reverse`（统一编排器）** — 7 模块 x 两级深度，按任务主动组合 (Anti-Detect/Observe/Capture/Trace/Human-Sim/Debug/Export)。需 CDP 完整断点调试且无反检测需求 -> `mcp-js-reverse-playbook`。两者**可互补**，通过 Export 桥接。
**Web 补环境路由**: 浏览器取证完成后，需要把原始网页 JS 放到 Node.js 中运行、补 `window/document/navigator/storage/crypto`、生成 sign/token 或对齐 fixtures 时，切到 `web-env-patcher`；协议采集器交付再切 `protocol-recovery`。

**Web 补环境判断矩阵**:

| 现象 / 阻塞点 | 路由 |
|---------------|------|
| 页面打不开、需要过风控 / 验证码 / 指纹 / 行为 / RuyiTrace | `ruyi-reverse` |
| 需要 CDP 断点、单步、作用域，且目标无强反检测 | `mcp-js-reverse-playbook` / `js-reverse-mcp` |
| 已有浏览器取证，但目标 JS 脱离浏览器在 Node 中跑不起来 | `web-env-patcher` |
| sign / token / x-s / a_bogus / h5st 依赖 `window/document/navigator/storage/crypto/performance/canvas/webgl` | `web-env-patcher` |
| 需要 Trace API inventory、env coverage matrix、Node 泄露阻断、fixtures 对齐 | `web-env-patcher` |
| 纯算法签名，无浏览器环境依赖，样本字段已确认 | 直接 `protocol-recovery` |
| Node 输出已与浏览器 fixtures 对齐，需要 Python collector / final request | `protocol-recovery` |
| WASM / JSVMP / VM opcode 是核心阻塞，补环境只能继续执行但不能解释算法 | 标 `triage-only`，必要时转 `ast-deobfuscation` / `web-reverse-algorithm` |


## 临时邮箱 skill/CLI 使用约束

`cloudflare-tmail` 是用户层 Codex skill + CLI，不属于 `D:\reverse_ENV\skill\` 项目 skill，也不写入 `.mcp.json` / `.codex/config.toml`。Codex 触发 `cloudflare-tmail` skill；Claude 按同一 CLI 和约束直接调用。

| 项 | 约束 |
|----|------|
| CLI 入口 | `python "%USERPROFILE%\.codex\skills\cloudflare-tmail\scripts\tmail.py" <group> <command>` |
| 本地凭据 | `%USERPROFILE%\.cf-tmail\credentials.json`，只存本机，不纳入 Git，不复制到项目目录 |
| JWT 缓存 | `%USERPROFILE%\.cf-tmail\mailboxes.json`，仅保存 CLI 创建/恢复的 Address JWT；临时测试结束必须删除测试邮箱并清空对应缓存 |
| 命令分组 | 只使用 `health`、`smtp-test`、`config`、`mailbox`、`mail`、`cf`；旧顶层别名已移除，不再使用 `create/list/get/poll/cf-check` |
| 邮箱管理 | 地址创建/查询/删除走 `mailbox create/list/show-jwt/delete/clear-inbox/clear-sent`；读信/轮询/删信走 `mail inbox/get/admin-list/delete/poll` |
| API 边界 | Address JWT 用 `Authorization: Bearer <jwt>` 访问 `/api/*`；User JWT 用 `x-user-token`，不得混用 |
| 私有站点 | 私有站点密码走 `x-custom-auth`；管理 API 走 `x-admin-auth`；不得把这些值写进回复、日志或仓库文件 |
| 收信接口 | 当前部署 `/api/parsed_mails` 返回 404 时必须 fallback 到 `/api/mails`，不要误判为收信失败 |
| Cloudflare 审计 | `cf check/zone/dns/email-rules/inventory` 可读 zone、DNS、Email Routing rules；Worker/D1/KV/Pages 当前 token 可能返回 `401/403 Authentication error`，按权限边界记录 |
| 真实 SMTP | 只有用户明确要求端到端收信测试时才运行 `smtp-test`；严格 SPF/DMARC 发件域可能被 Cloudflare DATA 阶段拒收，需如实记录 |
| 清理纪律 | 测试创建的邮箱必须 `mailbox delete --address <addr>`；复查 `mailboxes.json` 不保留测试 JWT；不得在 `workspace\` 留临时源码/解压目录 |

常用命令：

```powershell
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" health
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" config show
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" mailbox create --name codexdemo
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" mail poll --address codexdemo@zhangxuemin.work --timeout 120 --match "code|verify|验证码"
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" mailbox delete --address codexdemo@zhangxuemin.work
python "$env:USERPROFILE\.codex\skills\cloudflare-tmail\scripts\tmail.py" cf inventory
```

## 全局设计拷问 skill 使用约束

`grill-with-docs` / `grilling` / `domain-modeling` 是用户层全局协作 skill，不属于 `D:\reverse_ENV\skill\` 项目 skill，也不写入 `.mcp.json` / `.codex/config.toml`。Codex 与 Claude 均可全局触发。

| 项 | 约束 |
|----|------|
| 定位 | 只用于重大设计、工作流变更、术语边界、ADR 决策拷问；不是逆向 triage 入口 |
| 触发 | 用户明确要求 `grill` / `grill-with-docs` / “问透方案” / “拷问设计”，或任务涉及难逆转架构与跨模块工作流 |
| 禁用 | 新样本分析、APK/native/Web JS 常规侦察、已明确执行的修复、简单配置改动 |
| 提问 | 一次只问一个决策问题；事实能从仓库、代码、文档查到就先查，不反问用户 |
| 执行边界 | 达成共同理解前不得实施方案；不得跳过知识库检索、搜索、最小侦察、三件套产出 |
| 文档落点 | 不自动创建根目录 `CONTEXT.md` 或 `docs/adr/`；如需新增 ADR/术语文档，先说明必要性并同步 `AGENTS.md` / `CLAUDE.md` / `docs/AI开发规范.md` |

## 工作流速查

```
知识库检索(article-index) → 多源搜索(全局约束) → APK指纹(fingerprint.sh, 非Native则停止) → 分类(文件类型/平台)
  → 最小侦察(字符串/导入/manifest) → 决策(L1-L4深度) → 定向深挖(仅在确认后)
  → 产出三件套 → 审查门 → 知识库回填(有跨项目价值的分析)
```

> 多源搜索约束见全局 `~/.claude/CLAUDE.md` 与 `docs/搜索编排规范.md`。`search-layer` / `content-extract` 属全局分级能力；Claude/Codex 两份 `search-layer` 保持同步，Grok 采用 grounded Responses API（`grok-4.3` 主检索、`grok-4.5` fallback），streaming、structured outputs 与 `x_search` 均为 opt-in。

**不得跳阶段。L4 目标不声称完整还原。**

## MCP 工具前缀

| 前缀 | 服务 | 用途 |
|------|------|------|
| `survey_binary` 等 | ida-multi-mcp | IDA proxied tools：反编译/反汇编/xref/patch/类型/栈帧 (44 tools，均需 `instance_id`) |
| `idalib_*` | ida-multi-mcp | headless 会话管理 (open/close/list/status) |
| `jadx_*` | jadx-ai-mcp | APK 类/方法搜索/反编译/xref |
| `js-reverse_*` | js-reverse-mcp | Chrome/CDP 调试优先 — 断点/脚本/网络/运行时 (~22 tools) |
| `ruyi_*` | ruyi-mcp | Firefox/BiDi 全链路增强 — 反检测/指纹/人类模拟/BiDi JSON Trace/JS逆向 (56 tools) |
| `reqable_*` | reqable-mcp | Reqable 抓包数据查询 — HTTP/WebSocket 流量搜索/分析/代码生成 (~17 tools) |
| `wxmp_*` | wechat-miniapp-re-mcp | PC 微信 WMPF / wxapkg 专用逆向 — 会话、CDP、Hook、网络、静态还原、Profile 与证据导出 |
| `serena_*` | serena (user) | 代码符号搜索/引用追踪/语义搜索/项目导航 |
| `deepcon_*` | deepcon (user) | 包文档语义搜索/API 参考/代码示例检索 |

> **Web RE 双 MCP**: `js-reverse-mcp` (Chrome/CDP) 调试优先；`ruyi-mcp` (Firefox/BiDi) 增强全能 — 反检测/指纹/trace/人类模拟。按需求能力选择，可互补协作。详见 `docs/Web逆向架构分析.md`。

> MCP 服务详情见 `docs/MCP服务详情.md`

### Claude → Codex MCP 迁移规则

1. `.mcp.json` 是**项目级可用声明**，`.codex/config.toml` 是 **Codex 项目级启动配置**，`~/.codex/config.toml` 是 **Codex 用户级个人默认**。迁移时不得把项目级可用清单直接提升为 Codex 全局冷启动清单。
2. 项目冷启动只保留无额外前置条件、可在进入项目时立即握手成功的 MCP；依赖 GUI、浏览器调试端口、本地 SSE、桌面客户端上报链的 MCP 一律改为按需启用。
3. 项目规范名优先。Web CDP 调试 MCP 的规范名统一为 `js-reverse-mcp`；如 Codex 侧实验过其他包名，也不得反向污染项目文档与项目配置。
4. 迁移完成的判定标准不是“配置能被加载”，而是“默认冷启动无噪音 + 至少一个默认 MCP 能真实调用成功 + 按需 MCP 的前置条件和验证步骤已写清楚”。

### MCP 服务组织约束

**所有 MCP 服务代码统一在 `mcp/` 目录下管理。** pip 安装的 MCP（ida-multi-mcp、reqable-mcp 运行时）标注来源即可，不移动 venv 文件。

| 规则 | 说明 |
|------|------|
| 源码归属 | MCP 源码/项目必须在 `mcp/` 下，不得散落根目录或 `tools/` |
| 独立子仓 | `mcp/ruyi-mcp/` 是 Public Git submodule，`mcp/wechat-miniapp-re-mcp/` 是 Private Git submodule；修改时先在子仓验证、commit、push，再更新主仓 gitlink。fresh clone 必须先初始化对应 submodule 并安装锁定依赖 |
| 配置同步 | 新增/变更项目 MCP 路径时，同步更新 `.mcp.json` + `.codex/config.toml` + `CLAUDE.md` + `AGENTS.md` + `mcp/README.md` + `docs/MCP服务详情.md`；只有全局 MCP 才同步 `~/.codex/config.toml` |
| pip 管理标注 | pip 安装的 MCP 在 `mcp/README.md` 中标注包名和 venv 位置 |
| 硬编码路径 | MCP 启动脚本（如 `start-js-reverse.ps1`）中的路径必须使用 `mcp/` 前缀 |

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
| `ruyi-mcp` | Firefox / BiDi | **反检测 + 指纹分析 + BiDi JSON Trace + 人类模拟** | 需要过验证码、指纹取证、运行时 Trace、人类行为模拟（**所有站点通用**） |

**选择规则：**
1. 需要 CDP 完整断点调试（`get_paused_info`、`step`、调用栈查看）→ 用 `js-reverse_*`
2. 需要指纹分析、BiDi Trace、过 Cloudflare/hCaptcha、反检测浏览 → 用 `ruyi_*`（**无论目标站点反检测强度如何**）
3. ruyi-mcp 功能更全面（56 tools vs 22），指纹分析和 trace 能力在弱检测站点同样实用
4. 两者可互补：`ruyi_export_session` → 导出 Cookie/Storage → js-reverse-mcp 继续 CDP 调试
5. **禁止** 在强反检测站点上单独用 js-reverse-mcp（Chrome 无指纹伪装，会被封）— 需先经 ruyi-mcp 过检

**工具前缀隔离：** 同一浏览器 session 内不混用两个前缀的工具。跨工具协作通过 `ruyi_export_session` 显式桥接。

### ruyi Trace 与 Firefox runtime 分层

- `ruyi-mcp 0.1.1` 固定 `ruyiPage==1.2.46`；`ruyi_trace_*` 产出 RuyiPage/WebDriver BiDi JSON Trace，不是 C++ DOMTrace。
- 项目 BiDi runtime 放在 `tools\ruyipage\runtimes\`，浏览器二进制不进 Git；当前 `151-proxy` 固定在 `tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`。
- `tools\ruyitrace\firefox\` 只用于 C++ DOMTrace。`ruyitrace.ps1` 设置 `MOZ_DISABLE_LAUNCHER_PROCESS=1`，将 `<output>_<PID>.ndjson` 分片合并到 `-Output`；`-Limit` 可选。
- `.mcp.json` / `.codex/config.toml` 已切到 `151-proxy`；真实 HTTP 与 percent-encoded 凭据已通过。SOCKS5 只完成 offline contract，待有可用供应商时补真实出口门禁。

### js-reverse-mcp 双模式约束

默认使用 **`--browserUrl` 模式**（PS 脚本自动启动系统 Chrome + debug port）。`--cloak` 模式（CloakBrowser 57 维指纹补丁）仅限以下场景手动启用：

| 模式 | 何时用 | 如何启用 |
|------|--------|---------|
| 默认 `--browserUrl` | 一般调试、无强反检测站点 | `.mcp.json` 不传 `-Cloak`（当前默认） |
| `--cloak` | 强反检测站点（Cloudflare/验证码/51job 类） | `.mcp.json` args 加 `"-Cloak"` |

**cloakbrowser 已安装**于 `js-reverse-mcp/node_modules/cloakbrowser/`，首次使用自动下载 ~200MB 二进制到缓存，后续即时启动。

> 51job 等强反检测站点：先用 `ruyi-mcp` (Firefox/BiDi) 过检，必要时切 js-reverse-mcp `--cloak`。两者可通过 `ruyi_export_session` 桥接。

### Web 补环境隔离约束

`web-env-patcher` 吸收 `storage\xbsReverseSkill` 的补环境流程，但不得直接启用外部 skill 或替换项目主运行时。

| 项 | 约束 |
|----|------|
| 主 Node | `tools\node\node.exe` 是 MCP / 项目默认 Node，不得为 addon / isolated-vm 切换或覆盖 |
| 独立 runtime | Node 25/26、xbs addon、魔改 isolated-vm、TLS 指纹客户端只允许放 `tools\web-env\runtimes\` 或 `workspace\<项目名>\.runtime\` |
| 外部仓库 | `storage\xbsReverseSkill` 只作为参考和可选脚本来源；项目入口是 `skill\web-env-patcher` + `tools\web-env` wrapper |
| 自动安装 | 未经用户确认不得 `npm install` / `pip install` / `nvm use` / `nvm install`；不得写系统 PATH 或用户级环境变量 |
| ABI 检查 | `.node` addon / xbs isolated-vm 使用前必须跑 `tools\web-env\check-isolation.ps1`；不匹配只能记录 native gap 或走纯 JS fallback |
| 产物落点 | captures、fixtures、trace、runtime profile、TLS 采样全部落 `workspace\<项目名>\`，不得污染 `tools\` 或 `workspace\` 根目录 |

### 反检测能力边界（指纹伪装）

**注意区分：MCP 的 `ruyi_trace_*` 是 BiDi JSON Trace；`tools\ruyitrace\ruyitrace.ps1` 才是 C++ DOMTrace CLI。二者都属于监控取证，不做伪装。** 反检测伪装由 `ruyipage smart_fingerprint` 和 `CloakBrowser` 承担。

| 伪装维度 | ruyipage (Firefox/fpfile) | CloakBrowser (Chromium/C++) | 说明 |
|---------|--------------------------|---------------------------|------|
| navigator.webdriver | ✅ fpfile webdriver:0 | ✅ C++ 层清除 | |
| Canvas 指纹 | ✅ 随机种子 | ✅ C++ patched | |
| WebGL (12字段) | ✅ 22 个真实 GPU profile | ✅ C++ patched | RTX 4090→3050 / RX / Arc / UHD |
| AudioContext | ❌ 不覆盖 | ✅ C++ patched | |
| 字体枚举 | ✅ font_system | ✅ C++ 层控制 | |
| 硬件并发 | ✅ 22 个真实值 | ✅ C++ 层控制 | |
| 屏幕/窗口 | ✅ width/height + emulation | ✅ C++ 层控制 | |
| WebRTC IP | ✅ public/private IP | ✅ C++ 层阻止泄露 | ruyi 防真实 IP 泄露 |
| 时区/语言 | ✅ fpfile + BiDi 双层 | ✅ geoip 自动匹配 | |
| 地理位置 | ✅ BiDi emulation | ✅ 代理 IP 匹配 | |
| TLS 指纹 | ❌ Firefox 原生 TLS | ✅ 对齐真实 Chrome | **ruyi 碰不到** |
| CDP 协议痕迹 | ❌ 不适用(BiDi无CDP) | ✅ C++ 层清除 | |
| 网络时序 | ❌ 不覆盖 | ✅ C++ 层标准化 | |
| 自动化标记 | ❌ 不覆盖 | ✅ 消除 Playwright 信号 | |
| 语音合成 | ✅ speech.voices | ❌ 不覆盖 | |

**路由决策（按检测深度）：**

```
页面 → 查 navigator/canvas/webgl? (JS 层检测)
  ├─ 是 → ruyipage 22 profile 够了，无需 cloak
  ├─ 查 TLS / CDP / 网络时序? (协议层检测)
  │   └─ 是 → 必须 CloakBrowser --cloak
  └─ 查 AudioContext / 自动化标记?
      └─ 是 → 必须 CloakBrowser --cloak
```

> **经验规则**：90% 的国内站点（含 51job）检测在 JS 层，ruyipage 够用。遇到 ruyi 反复被拦时，分析 trace 判断是否协议层检测，再决定切 cloak。

## WebFetch 使用约束

**禁止直接使用 WebFetch。** WebFetch 有结构性限制——不跟随跨域重定向、HTTP 强制升级 HTTPS、不支持认证/Cookie、国内站点常被封锁——项目内已有成熟替代：

| 场景 | 走哪个 |
|------|--------|
| 搜索/查事实/找资料 | 全局 `search-layer`（client-native search + Exa + Tavily + Grok 并行 + 去重打分） |
| 微信公众号/国内文章/需解析的 URL | 全局 `content-extract`（MinerU API） |
| GitHub 代码/Issue/PR 深挖 | `github-solution-research` |
| 需登录/Cookie/JS 渲染的页面 | `ruyi_*` / `js-reverse_*` 浏览器方案 |

本项目不使用 WebFetch fallback。若全局文档允许 WebFetch 兜底，以本项目 `AGENTS.md` / `CLAUDE.md` 的硬封禁为准；搜索能力不可用时，应先迁移/修复 `search-layer` 或改走 GitHub / 浏览器方案，并在结论中标注能力缺口。

## 已知坑点

1. **idalib 孤儿进程** → `start.ps1` 只清理当前 venv 下的旧 `idalib_worker` 进程树。
2. **System32 文件无权限 / 同名旧 IDA 库** → `open.ps1` 自动复制到 `%TEMP%\opencode\`；默认不删除 `.i64` / `.id*`。
3. **IDA 许可单实例** → GUI 和 headless 互斥，跑 headless 前关 GUI。
4. **jadx-ai-mcp 需先开 GUI** → `tools\jadx-gui.cmd` 启动并加载 APK 后 MCP 才可用。
5. **Plugin 命名冲突** → `plugins/ida_multi_mcp.py` 若报 "is not a package"，改名为 `mcp_multi_loader.py` 并注入 venv 路径。
7. **ruyi-mcp 断点为软断点** → BiDi 协议无调试域，Firefox CDP 已于 v141 移除。`ruyi_set_breakpoint_on_text` 通过 preload script + Proxy 包装实现。可获取 `Error().stack` 调用栈字符串，但无法单步/作用域枚举。完整分析见 `docs/ruyi-mcp-devtools-调试能力分析.md`。短期可通过 Proxy 通信通道增强到 Level 2 软断点（覆盖 ~70% 需求），中期需 ruyipage 内核暴露 SpiderMonkey `Debugger` API。
8. **ruyi-mcp proxy 需在 launch 时设置** → `ruyi_new_page` 的 `proxy` 参数在启动浏览器时生效，启动后无法切换代理。多代理用多标签 container tab（后续版本支持）。Cliproxy 用户名以 `-` 分段，Sticky `sid` 只使用 ASCII 字母、数字、下划线；含 `-` 的 SID 可能被截断并碰撞，批量任务必须同时验证 SID 内复用和 SID 间换 IP。
9. **First 微信小程序调试 — WMPF 版本偏移量** → 开源版仅覆盖至 19823，新版 WMPF 需从编译版 v1.1.3（存档于 `storage\First-release\`）提取配置。方法：`pyinstxtractor-ng First.exe` → `find . -name "addresses.*.json"` → 复制到 `tools\First\frida\config\win\`。
10. **NDK 交叉编译** → NDK r29 安装在 `tools\android-ndk\`，未纳入 Git。编译前确认 `tools\android-ndk\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android33-clang.cmd` 存在。
11. **LDPlayer RE 模拟器** → 多实例模板：`re-base`(Root+Frida+CA)、`re-xposed`(+LSPosed+JustTrustMe)、`re-stealth`(+Hide My Applist+Shamiko v0.7.5)。项目实例从模板复制；模板 verified 备份在 `storage\ldplayer-backups\`。`ldconsole restore` 会恢复备份内部实例名，必须通过 `re-restore.ps1` 按 index 恢复并重命名。`Shamiko v1.2.5` 需 Magisk Canary > 27005，当前 Kitsune/Magisk 27001 使用已验证的 v0.7.5。
12. **Rust 交叉编译** → 需 `rustup target add aarch64-linux-android x86_64-linux-android`。`.cargo/config.toml` 的 NDK 路径已通过 `tools\android-ndk\` 重定位。
13. **Shadow Hook Frida JS agent 能力边界** → 仅做公开 API 过滤（dl_iterate_phdr / maps read），无法从 linker 内部 solist 摘除 soinfo。如需完整摘除，编译 `tools\hide-soinfo\`。
14. **ruyi Trace 不是 DOMTrace** → `151-proxy` 无 `RUYI_DOMTRACE.txt` 且不产出 DOMTrace；C++ DOMTrace 必须继续使用 `tools\ruyitrace\firefox\`。

## Git约束

- **仓库已初始化 Git** — `docs/Git与提交规范.md` 中的规则已生效。提交前须检查 diff、提交信息须描述真实改动。
- **大文件未纳入 Git** — `resource/portable_win/`、`tools/jdk/`、`tools/node/` 等大文件在 `.gitignore` 中排除，通过磁盘路径直接引用。

## 脚本速查

PS 脚本绝对路径调用：`powershell -File "D:\reverse_ENV\skill\<name>\scripts\<script>.ps1"`；bash 脚本用 `bash D:/reverse_ENV/skill/<name>/scripts/<script>.sh`。

| 领域 | 脚本 | 一行用途 |
|------|------|---------|
| APK | `fingerprint.sh` | Phase 0 快速指纹（框架/混淆度/HTTP栈/下一步） |
| APK | `decode.ps1` | jadx+apktool 落盘 |
| APK | `frida-run.ps1` | Frida 注入 |
| APK | `rebuild-sign-install.ps1` | 重建→签名→安装 |
| APK | `manifest-summary.ps1` | Manifest 摘要 |
| APK | `recover-kotlin-names.sh` | Kotlin 高置信类名恢复 + 低置信 d2 候选分离 |
| APK | `lookup-name.sh` | 查询类名映射 (obf->real/搜索/标注grep) |
| APK | `find-api-calls.sh` | HTTP/API/URL/auth/sign 候选扫描，结果需证据复核 |
| APK | `init-ldplayer-re.ps1` | 指定 LDPlayer ADB 设备 Root/ABI/Frida 版本与 handshake 验证 |
| APK | `dump-dex.ps1` | panda whole-DEX wrapper；ABI/PID/超时/结构校验/失败留证 |
| APK | `dex-dump.js` | Frida DEX 加载观察（triage-only，不写出 DEX） |
| IDA | `start.ps1` | 环境验证 |
| IDA | `open.ps1` | idalib 路径预处理（不打开数据库） |
| r2 | `recon.ps1` | 一站式侦察 |
| LDPlayer | `re-init.ps1` | RE 实例初始化（创建/从模板复制→启动） |
| Article | `pdf_to_markdown.py` | pending PDF → Markdown 草稿（需人工清洗、分类、索引） |
| LDPlayer | `re-proxy.ps1` | HTTPS 代理 on/off |
| LDPlayer | `re-list.ps1` | 实例状态一览 |
| LDPlayer | `re-backup.ps1` | 模板/项目实例备份到 `storage\ldplayer-backups\` |
| LDPlayer | `re-restore.ps1` | 从 `.ldbk` 按 index 恢复到已有实例，恢复后重命名回 `-Project`，支持 `-SourceProject` |
| LDPlayer | `re-destroy.ps1` | 停止/删除实例 |
| Proxy | `proxy_check.py` | 代理可用性验证 (HTTP/SOCKS5) |
| Proxy | `kuaidaili_extract.py` | 快代理 API 提取 + 验证 |
| Proxy | `cliproxy_test.py` | Cliproxy SOCKS5 测试 (Rotating/Sticky) |
| Web Env | `check-isolation.ps1` / `invoke-xbs-script.ps1` | Web 补环境隔离检查与 xbs 纯 JS 检查器封装 |

> `.py` 脚本用 `python "D:\reverse_ENV\skill\<name>\scripts\<script>.py"` 调用。
> 脚本详情见 `docs/脚本参考.md`

## 工具速查

| 工具 | 路径 |
|------|------|
| jadx 1.5.5 | `tools\jadx\bin\jadx.bat` |
| apktool 3.0.2 | `tools\apktool\apktool.bat` |
| Vineflower 1.11.2 (备选) | `tools\vineflower\vineflower-1.11.2.jar` — Fernflower 社区分支，复杂 Java/lambda/泛型输出质量优于 jadx。用法: `java -jar ...vineflower.jar -dgs=1 -mpm=60 input.jar output/` |
| dex2jar 2.4.31 (备选) | `tools\dex2jar\dex-tools-2.4.31\` — DEX→JAR 转换，Vineflower 反编译 APK 的前置依赖。用法: `d2j-dex2jar.sh -f -o app.jar app.apk` |
| Kitsune Mask v27.0 | `tools\Kitsune-Mask-27.0.apk` — Magisk Delta 模拟器版 (支持「直接安装到系统分区」)，LDPlayer RE 实例 Magisk 安装用 |
| Android 模块资产 | `tools\android-modules\` — Kitsune/LSPosed/JustTrustMe/Hide My Applist/Shamiko 本地资产清单，APK/ZIP 本体不进 Git |
| jadx-mcp-server | `mcp\jadx-mcp-server\jadx_mcp_server.py`（jadx-ai-mcp MCP 服务端） |
| radare2 6.1.8 | `tools\radare2\bin\radare2.exe` |
| frida 17.15.3 | `.venv\Scripts\frida.exe` |
| adb 1.0.41 | `tools\adb\adb.exe` |
| zipalign (build-tools 33) | `tools\adb\zipalign.exe` |
| apksigner 0.9 | `tools\adb\apksigner.bat` |
| LDPlayer 9 底层管控 | `tools\ldplayer\ldplayer.ps1` （RE 管理用 `skill\ldplayer-control\scripts\`） |
| Chromium 152 (备用浏览器) | `tools\chromium\chrome-win\chrome.exe`（系统 Chrome 不可用时 fallback） |
| js-reverse-mcp 包装脚本 | `powershell -File tools\chromium\start-js-reverse.ps1` |
| ruyipage 1.2.46 / 151-proxy | `.venv\Scripts\python.exe -m ruyipage`；项目 runtime: `tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe` |
| ruyiTrace DOMTrace | `tools\ruyitrace\ruyitrace.ps1`（专用 `tools\ruyitrace\firefox\`） |
| ruyi-mcp 0.1.1 (Web 增强 MCP) | `tools\node\node.exe D:\reverse_ENV\mcp\ruyi-mcp\build\src\index.js` |
| reqable-mcp (抓包数据查询) | `.venv\Scripts\reqable-mcp.exe mcp`（源: `mcp\reqable-mcp\`） |
| wechat-miniapp-re-mcp | `tools\node\node.exe mcp\wechat-miniapp-re-mcp\build\src\index.js`（stdio 冷启动，真实 WMPF v19977 CDP 门禁已通过。环境变量: `WXMP_LEGACY_PROFILE_DIR`, `WXMP_WORKSPACE_ROOT`, `WXMP_GWXAPKG`, `REVERSE_ENV_ROOT`） |
| Gwxapkg 2.7.4 | `tools\Gwxapkg-runtime\gwxapkg.exe`（源码 submodule: `tools\Gwxapkg\`） |
| JDK 21 | `tools\jdk\` |
| Node.js 20.20.2 | `tools\node\node.exe` |
| Web Env | `tools\web-env\` |
| MinGW-w64 14.2.0 (C/GCC) | `tools\mingw64\mingw64\bin\gcc.exe` |
| QuickJS (qjs_min) | `tools\quickjs\qjs_min.exe` |
| First (微信小程序调试 Legacy) | `powershell -File tools\First\first-gui.ps1` |
| First CLI (无头模式) | `powershell -File tools\First\first-cli.ps1` |
| Shadow Hook 隐身工具 | `python skill\native-reverse\scripts\tools\shadow-hook\stealth-runner.py` |
| hide-soinfo C 库 | `tools\hide-soinfo\` (需 NDK 编译) |
| stealth-hook-engine | `tools\stealth-hook-engine\` (需 NDK 编译) |
| Android NDK r29 | `tools\android-ndk\` |
| Rust 工具链 | `%USERPROFILE%\.cargo\bin\rustc.exe` |
| Serena (user MCP) | `tools\serena\` (uv run) |
| Deepcon (user MCP) | `tools\node\npx.cmd -y deepcon-mcp` |

> 完整清单见 `docs/工具与环境.md`

## 提交前自检（硬门禁）

```powershell
git status --short
git diff --stat
git diff --check
```

- 提交信息须描述真实改动，不写 "update" / "fix"
- 确认无临时文件、敏感数据、调试日志混入 diff
- 涉及脚本/工具路径变更 → 同步 CLAUDE.md + AGENTS.md + skill 文档
- 涉及项目 MCP 配置变更 → 同步 `.mcp.json` + `.codex/config.toml`；涉及 Codex 全局 MCP 再同步 `~/.codex/config.toml`
- 涉及 Claude 全局 MCP 变更 → 同步 `~/.claude.json`

## 大任务自动刷新

满足以下任一条件时，**先更新本文件和相关规范，再写代码**：

- 新增/移除 skill、MCP、工具
- 任务跨 3 个及以上 `skill/` / `tools/` / `docs/` 顶层目录
- 涉及工作流变更（如新增逆向阶段、新增平台支持）

## 本文件维护规则

- 路径变更必须同步更新；工具版本号变更必须同步更新
- 目录不存在或命令不可用时，标注 `（待建）` 或 `（待验证）`，不得保留过期路径
- 规范与真实仓库冲突时，以真实仓库为准，并立即更新本文件
- 全局约束（搜索、治理、编码）在 `~/.claude/CLAUDE.md`，本文件引用而不重复

## Novel Rank Scout 开篇采样接入

- 需求与主实现仓库：`workspace/novel-rank-scout-spec/`
- 逆向证据工作区：`workspace/novel-rank-scout-opening-reverse/`，仅保存取证、原始 fixture 和外部 Adapter 原型，不作为主仓库运行时依赖
- 番茄与起点最终采集均走匿名公开 SSR；浏览器只用于首次取证，生产链路不得依赖 ruyipage、Cookie、登录态或动态签名
- 正式实现只能进入 `novel_rank_scout/adapters/`、开篇采样 Provider/Parser/Store 层，不得把逆向细节写入 analyzer、report 或创作判断层
- 章节全文只能通过受控 `body_ref` 进入本地 RawSnapshot/OpeningSampleStore；跨项目 Envelope、stdout、EvidenceDigest 和 canon 禁止内嵌全文
