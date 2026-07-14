# AI 开发规范

> 适配本逆向工作台仓库的 AI 协作开发规范。

---

## 阅读顺序要求

涉及代码、skill、MCP 配置、脚本、工具安装等任务前，必须阅读或重新核对：

1. `AGENTS.md` / `CLAUDE.md`（Codex / Claude 仓库总纲）
2. 当前文件
3. 相关 `skill/*/SKILL.md`
4. 相关 `skill/*/references/*.md`

**禁止仅凭历史记忆、会话摘要或"看起来知道项目"直接操作。**

---

## 0. AI 协作执行协议

### 0.1 操作前必须确认仓库现状

开始任何改动前，至少检查当前工作目录结构和文件状态：

```bash
ls -la
git status --short --branch   # 若已初始化 git
```

要求：
- 不得在未知晓当前目录状态时开始写文件
- 若工作区有归属不明的文件或改动，须先停下说明
- MCP 工具调用前须先确认对应服务可用

### 0.2 分析与执行不能脱节

- 先读现有 skill 定义和脚本，再修改
- 分析确认"不应存在"的旧路径、旧 fallback、旧用户名引用，修改时一并清理
- 所有工具和依赖必须安装在 `D:\reverse_ENV\` 内，不得污染系统全局环境
- 新增或修改 skill 时，同步更新 `AGENTS.md` / `CLAUDE.md` 中的架构说明

### 0.3 执行方案要求

用户要求写方案时，方案须包含：
1. 需求理解与目标
2. 现有文件/配置链路分析
3. 是否符合本仓库架构和命名约定
4. 方案自身的缺陷、边界遗漏
5. 关联文件检查（脚本、CLAUDE.md、skill、.mcp.json）
6. 分阶段执行清单
7. 每阶段完成后的自检项

进入执行后须按清单逐阶段完成，阶段自检未通过则不得进入下一阶段。

---

## 1. 仓库架构原则

本仓库为**逆向工程环境配置与技能仓库**，核心目录：

- `skill/`：AI 协作 skill 定义
- `tools/`：便携工具链（JDK, jadx, apktool, radare2, adb, node, vineflower, dex2jar 等）
- `mcp/`：MCP 服务源码（js-reverse-mcp, ruyi-mcp, jadx-mcp-server, reqable-mcp），清单见 `mcp/README.md`
- `resource/`：资源文件（IDA Pro 便携版 + 汉化 + 许可补丁）
- `.venv/`：Python 虚拟环境（所有 MCP 服务和 Python 包）
- `workspace/`：独立项目工作树容器；项目 Git 边界由 `docs/workspace-projects.yaml` 管理
- `article/`：独立 Public 知识库 submodule，索引由子仓维护
- `.mcp.json`：项目级 MCP 服务声明
- `~/.codex/config.toml`：Codex 用户级默认启动配置
- `AGENTS.md` / `CLAUDE.md`：Codex / Claude 仓库总纲

### 1.1 MCP 主线 / 脚本兜底

- **MCP 工具（stdio）是主线**：ida-multi-mcp / jadx-ai-mcp / js-reverse-mcp / ruyi-mcp / reqable
- **PowerShell/Bash 脚本是兜底**：当 MCP 有 schema bug 或需要特殊绕过时才走脚本
- **MCP 源码统一在 `mcp/` 下**，不得散落根目录或 `tools/`
- 新增 MCP 服务时，同步更新 `.mcp.json` + `~/.codex/config.toml`（如需 Codex 默认启用）+ `mcp/README.md` + `docs/MCP服务详情.md` + `AGENTS.md` + `CLAUDE.md`
- 新增 skill 时，同步更新 `AGENTS.md` / `CLAUDE.md` 的 skill 表

### 1.2 模块边界

| 目录 | 职责 | 禁止 |
|------|------|------|
| `skill/*/SKILL.md` | skill 定义、工作流、适用范围 | 不写具体配置值，不硬编码路径 |
| `skill/*/scripts/` | 可执行的 .ps1 脚本 | 不跨 skill 互相调用 |
| `skill/*/references/` | 参考资料、速查表 | 不包含可执行逻辑 |
| `tools/` | 便携工具二进制/jar/脚本 | 不安装到系统目录 |
| `.mcp.json` | MCP 服务注册 | 不注册非本仓库安装的服务 |
| `AGENTS.md` / `CLAUDE.md` | 架构概述、约束、依赖清单 | 不重复 skill 内的细节 |

### 1.3 平台扩展边界

当前覆盖 Web / Android / 二进制 三大逆向领域，各自独立：
- Web → 默认 `ruyi-reverse` + ruyi-mcp；仅需 CDP 完整断点且无反检测需求时走 `mcp-js-reverse-playbook` + js-reverse-mcp
- Android → `apk-reverse` + jadx-ai-mcp + frida + adb
- 二进制 → `ida-reverse` + `radare2` + ida-multi-mcp
- 知识参考 → `reverse-engineering`（CTF 向，只读）

不将某一平台的工具或流程强加给另一平台。

### 1.4 多仓边界

- `reverse_ENV` 只版本化环境、skill、MCP、治理规则、项目 registry 和少量真实依赖，不承载全部逆向证据。
- Workspace 项目默认独立 Private 仓库；`submodule` 只用于正式 spec、公共工具或主仓真实依赖，普通目标逆向仓使用 `registry`。
- 项目仓不得提交第三方二进制、抓包、Cookie、凭据、浏览器 profile、IDA 数据库或反编译全集；这些内容只允许保留在本地工作树，并用 evidence manifest 记录哈希和相对引用。
- 对 `deferred-active` 项目只能只读审计，禁止任何会改变 HEAD、index、remote、Git 目录或运行文件的迁移动作。
- 新建或迁移项目仓前后都要运行 `tools/workspace-governance/audit_workspace.py`，并同步 `docs/workspace-projects.yaml`。

---

## 2. 新增 Skill 规范

新增 skill 须同步检查：

1. `SKILL.md` 是否包含正确的 YAML frontmatter（name, description）
2. skill 是否与已有 skill 职能边界清晰
3. 脚本路径是否使用绝对路径（`D:\reverse_ENV\...`）
4. 工具引用是否指向 `tools\` 内的便携版本
5. MCP 依赖是否已在 `.mcp.json` 中注册
6. `AGENTS.md` / `CLAUDE.md` 是否已同步更新

### 2.1 用户层全局协作 Skill

`grill-with-docs` / `grilling` / `domain-modeling` 属于用户层全局协作 skill，不属于本仓库 `skill/` 项目技能体系。

使用约束：
- 不写入 `.mcp.json` / `.codex/config.toml`
- 不在 `.agents/skills/` 下创建薄封装
- 只用于重大计划、架构设计、术语边界和 ADR 决策拷问
- 不替代 `reverse-coordinator`、`apk-reverse`、`native-reverse`、`ruyi-reverse` 等逆向任务路由
- 在本仓库内不得自动创建根目录 `CONTEXT.md` 或 `docs/adr/`；确需新增决策文档时，先说明必要性，并同步 `AGENTS.md` / `CLAUDE.md` / 当前文件

---

## 3. 新增 MCP 服务规范

新增 MCP 服务须同步检查：

1. 服务是否安装在 `D:\reverse_ENV\` 内（venv 或 tools 子目录）
2. `.mcp.json` 是否已添加对应条目
3. `command` 和 `args` 是否使用绝对路径
4. 环境变量（`IDADIR`, `JAVA_HOME` 等）是否正确设置
5. `AGENTS.md` / `CLAUDE.md` 的 MCP 架构章节是否已更新

---

## 4. 新增工具规范

新增便携工具须同步检查：

1. 工具是否安装在 `tools\` 子目录
2. 包装脚本（`.bat` / `.cmd`）是否自动设置所需环境变量
3. 已有 skill 脚本中的 fallback 路径是否已更新
4. `AGENTS.md` / `CLAUDE.md` 的工具依赖章节是否已更新

---

## 5. 测试与验证

本仓库没有统一业务测试套件。每次改动后最低验证：

1. 新增/修改的脚本能否独立运行（PowerShell 语法无误）
2. 新增/修改的 MCP 服务能否启动（`--help` 或 `--version` 不报错）
3. 新增的 CLI 工具能否输出预期版本号
4. `AGENTS.md` / `CLAUDE.md` 中引用的所有路径是否真实存在
5. Workspace registry 与本地目录、Git remote、submodule 状态是否一致
6. 新建项目仓是否通过禁止文件、敏感文件和大文件门禁

---

## 6. 编码与文件规范

- 文件默认 UTF-8，LF 换行
- 已有 UTF-8 with BOM 文件须保留 BOM
- 修改已有文件时优先保持原换行风格
- 修改含中文的文件时须检查是否出现乱码
- 不得在未确认编码的情况下批量重写中文文件

---

## 7. AI 操作自检清单

每次修改后自问：

1. 操作前是否重新核对了 `AGENTS.md` / `CLAUDE.md` 和相关 skill 文件？
2. 是否先看了真实文件内容而非靠记忆？
3. 新增/修改的路径是否都在 `D:\reverse_ENV\` 内？
4. 是否将工具、MCP、skill 的路径引用都更新了？
5. `AGENTS.md` / `CLAUDE.md` 是否与已安装的工具/MCP 版本一致？
6. 是否有残留的旧用户名（`25286`）、旧路径（`D:\APP\IDA`）引用？
7. 新增文件是否有中文乱码？
8. 是否误将临时下载文件、缓存、`__pycache__/` 留在仓库？
9. diff 中是否混入了 token、密码、cookie 等敏感信息？
10. 若修改了 `.mcp.json` / `~/.codex/config.toml`，配置是否合法、路径是否存在？

---

## 8. 完成标准

合格操作完成的条件：

- 改动边界清晰，不跨模块污染
- 所有路径引用指向 `D:\reverse_ENV\` 内的真实文件
- 无旧用户名、旧路径残留
- `AGENTS.md` / `CLAUDE.md` 与实际情况一致
- 无中文乱码、BOM 丢失、换行异常
- 无临时文件、缓存文件残留
