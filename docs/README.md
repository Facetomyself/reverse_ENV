# 项目文档

逆向工程环境配置与技能仓库的规范文档、参考指南、分析文章索引。

## 文档索引

| 文档 | 内容 |
|------|------|
| `article-index.md` | 独立知识库 `article/INDEX.md` 的兼容入口与初始化说明 |
| `workspace-projects.yaml` | Workspace 独立仓库 registry（路径、remote、接入方式、生命周期） |
| `workspace-repository-governance.md` | Workspace/Article 多仓边界、迁移与审计规则 |
| `AI开发规范.md` | AI 协作开发规范（仓库架构、MCP 主线、编码、Git） |
| `Git与提交规范.md` | Git 操作与提交信息规范 |
| `工具与环境.md` | 完整工具版本、路径、安装说明 |
| `App逆向环境规划.md` | LDPlayer 多实例模板、LSPosed/JustTrustMe/HMA/Shamiko 分层与备份恢复策略 |
| `MCP服务详情.md` | 6 个 MCP 服务的架构、配置、工具清单 |
| `脚本参考.md` | PS/Bash/Python 脚本的调用规范和功能说明 |
| `逆向工作流详解.md` | 逆向分析工作流与深度等级（L1-L4）说明 |
| `Web逆向架构分析.md` | Web RE 工具架构设计（js-reverse-mcp vs ruyi-mcp） |
| `搜索编排规范.md` | 多源搜索（search-layer/github-solution-research）的编排规范 |
| `ruyi-mcp-引导方案.md` | ruyi-mcp 引导与部署方案 |
| `ruyi-mcp-devtools-调试能力分析.md` | ruyi-mcp 软断点调试能力 vs js-reverse-mcp CDP 对比 |
| `ruyipage-upstream-update-audit-2026-07-14.md` | RuyiPage 1.2.46、151-proxy、Issue/CI 与 ruyi-mcp 兼容审计 |

## 维护规则

- 文档变更后检查 CLAUDE.md 中的交叉引用是否仍然准确
- 每个文档只写硬规则/事实，不写解释性废话
- 新增文档后在本 README 索引表中添加一行
