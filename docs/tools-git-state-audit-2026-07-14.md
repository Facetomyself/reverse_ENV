# `tools/` Git 状态审计（2026-07-14）

## 结论

- 不新增 submodule：`tools/` 中不存在自有、独立演进且已有远端的 Git 项目。
- 不迁移到 `storage/`：当前外部克隆均仍被使用或带有脏改动；移动会改变既有路径或工作树状态。
- 新增 `tools/tmp/` 忽略规则：该目录是空 scratch 容器，未被 README 或项目配置引用。

## Git 仓库

| 路径 | 上游 | 状态 | 决策 |
|---|---|---|---|
| `tools/Gwxapkg` | `25smoking/Gwxapkg` | 干净；已是 gitlink | 保持 Public submodule；由微信小程序 MCP 依赖。 |
| `tools/First` | `Spade-sec/First` | 11 条本地变更 | 保持原地、整体忽略；它是已废弃但仍供行为参考的外部工具，禁止移动、清理或重置。 |
| `tools/serena` | `oraios/serena` | `uv.lock` 本地镜像源改动 | 保持原地、整体忽略；不纳入主仓或升格为 submodule。 |
| `tools/codex-session-patcher` | `ryfineZ/codex-session-patcher` | 干净 | 保持本地外部克隆并整体忽略；未发现项目内调用。 |

## 主仓维护的工具代码

`protocol-recovery`、`web-env`、`workspace-governance`、`ldplayer`、`panda-dex-dumper` 与构建包装脚本均由主仓历史持续维护，并与项目 skill、文档或工作流耦合。它们应继续作为主仓跟踪文件，不拆分成 submodule。

## 已有忽略分层

- 可复现工具脚本与 README 被跟踪；JDK、Node、NDK、SDK、浏览器、运行时及构建产物按目录或文件精确忽略。
- `tools/chromium/`、`tools/ruyipage/`、`tools/ruyitrace/`、`tools/android-modules/` 采用“保留包装脚本/README、忽略运行资产”的白名单结构，保持不变。
- `tools/First/`、`tools/serena/`、`tools/codex-session-patcher/` 都已整体忽略，Git 脏状态不会污染主仓。

## 后续门槛

只有工具具备独立 README、版本/测试、明确自有远端和跨仓复用者时，才创建独立仓并以 submodule 接入。外部上游克隆先保留 upstream remote，不能转换为自有 submodule。
