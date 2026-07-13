# Workspace 与知识库多仓治理

## 目标拓扑

`reverse_ENV` 是工具链和治理主仓，不是所有逆向项目的 monorepo。`workspace/` 只承载本地工作树，项目关系通过以下两种方式表达：

- `submodule`：正式 spec、公共工具或被主仓/其他仓库直接消费的代码，主仓固定其 commit。
- `registry`：目标型逆向、数据研究和证据型项目，仅在 `docs/workspace-projects.yaml` 登记，不进入主仓克隆链。

知识库 `article/` 使用独立 Private 仓库并以 submodule 接回原路径。文章 canonical index 位于 `article/INDEX.md`，主仓 `docs/article-index.md` 仅提供兼容入口。

## 项目仓跟踪边界

允许进入 Git：

- README、AGENTS、许可证和项目元数据
- `report.md`、`findings.json`、`triage.md`
- 原创源码、脚本、测试和脱敏 fixture
- evidence manifest：只保存哈希、类型、尺寸和本地相对引用

禁止进入 Git：

- APK、IPA、SO、DLL、EXE、DEX、IDA 数据库和内存 dump
- HAR、PCAP、flow、浏览器 profile、Cookie、token、凭据和代理配置
- jadx/apktool/webpack 解包及反编译全集
- 第三方仓库副本、依赖目录、缓存、构建和运行产物

Git LFS 不用于绕过上述禁入规则。确需版本化的自有大文件必须单独评审。

## 生命周期

| 状态 | 含义 | 允许动作 |
|------|------|----------|
| `planned` | 已登记，尚未建仓 | 只读审计、补治理文件 |
| `active` | 独立仓正常维护 | 常规提交、推送、审计 |
| `deferred-active` | 正有任务或存在受保护脏改动 | 只读审计，不改 Git 元数据和工作树 |
| `archived` | 停止开发但保留历史 | 只读维护、安全修订 |
| `excluded` | 空目录、一次性测试或外部上游工作树 | 不创建自有仓库 |

Registry 的 `readiness` 独立描述建仓门禁：`ready` 可立即整理首提，`existing` 已有仓库，`deferred` 受活动任务保护，`curation-required` 必须先隔离原始证据，`incomplete` 需先补齐项目交付，`excluded` 不建仓。

## 迁移门禁

1. 记录目录、branch、HEAD、remote 和 dirty 状态。
2. 运行 `tools/workspace-governance/audit_workspace.py`，确认禁止文件和大文件风险。
3. 为项目补项目级 `.gitignore`、README/AGENTS 和 evidence manifest；不得移动或删除原始证据来制造“干净”。
4. 创建 Private GitHub 仓库，新仓默认分支使用 `main`；已有仓库保留当前默认分支。
5. 只提交允许跟踪的内容，推送后更新 registry。
6. 重新运行审计并验证 remote、visibility、HEAD 和主仓状态。

`deferred-active` 项目不执行第 3–5 步，直到活动任务结束并单独复核。

## Submodule 规则

- 首批正式依赖为 `article/` 和 `workspace/novel-rank-scout-spec/`。
- `workspace/fanqie-auto-publisher-spec/` 当前为 `deferred-active`，本轮只登记，空闲后再接入。
- 禁止对活动或脏项目执行 `git submodule absorbgitdirs`。
- 普通 clone 不应下载 registry 项目；需要正式依赖时使用 `git submodule update --init --recursive`。
