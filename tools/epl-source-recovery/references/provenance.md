# 来源与选型记录

检索时间：2026-07-17。

## 搜索路径

- `search-layer`：Exa、Tavily、Grok 多来源检索易语言工程解析器、精易模块源码和许可证。
- GitHub：使用 `gh repo view`、`gh search code`、Git Data API 核对版本、commit、依赖与许可证。
- Gitee：使用 Git refs、固定 tag clone、源码树检查和本地静态解析核对精易模块。
- 未使用子 agent：候选集中在两个已知上游和一个源码镜像，拆分不会提高证据质量。

## 候选

| 项目 | 基本信息 | 决策 |
|------|----------|------|
| [OpenEpl/EProjectFile](https://github.com/OpenEpl/EProjectFile) | 31 Stars / 10 Forks / C# / Unlicense；latest release `v1.9.4` | 采用，固定 commit 并通过本地安全适配层编译 |
| [OpenEpl/TextECode](https://github.com/OpenEpl/TextECode) | 57 Stars / 20 Forks / C# / MIT；latest release `v0.2.4` | 不进入默认链路；依赖面更大且包含 `OpenEpl.ELibInfo` 恢复能力，本任务只需要无支持库加载的静态提取 |
| [elangec/ec](https://gitee.com/elangec/ec) | 精易模块公开源码镜像 / Apache-2.0 / tag `11.1.6` | 作为只读源码资产归档，不执行、不编译 |

## 本地安全改造

`EProjectFile v1.9.4` 上游通过 `OpenEpl.ELibInfo` 解析支持库名称。本地适配层不引用该包，也不加载 `*.fne`、`*.fnr` 或其他支持库文件：

1. `FormElementInfo.cs` 删除 `OpenEpl.ELibInfo` import。
2. `IDToNameMap.cs` 删除 `ELibInfoLoader`，所有外部支持库名称保留为 `_Lib*` 占位符。
3. 项目不含 `PackageReference`，只使用 portable .NET 10 SDK 自带框架程序集。
4. 提取器只读取输入工程并写出文本、JSON 和原始资源；不调用 `Process.Start`、`LoadLibrary` 或资源执行入口。

## 精易模块取舍

斗罗项目中记录的是 `精易模块 v11.1.5`，且存在旧 ID 断链。根工具不把样本派生副本冒充成通用模块，而是固定公开源码仓的 `11.1.6`；项目专属旧 ID 映射继续保留在项目仓 `analysis/source_repair_map.json`。
