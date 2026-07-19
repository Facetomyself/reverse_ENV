# Optional upstreams and evidence

以下数据于 2026-07-18 使用 GitHub CLI 核验。它们是候选 baseline 或方法证据，不是默认安装项。

| 项目 | Stars/Forks | License | 本地结论 |
|---|---:|---|---|
| [j4k0xb/webcrack](https://github.com/j4k0xb/webcrack) | 2798/325 | MIT | 成熟 AST/解包架构可借鉴；2.16.0 仅支持 Node 22/24/26，不进入 Node 20 baseline |
| [ben-sb/javascript-deobfuscator](https://github.com/ben-sb/javascript-deobfuscator) | 1139/153 | Apache-2.0 | 字符串、代理和表达式简化 baseline |
| [HumanSecurity/restringer](https://github.com/HumanSecurity/restringer) | 597/63 | MIT | safe/unsafe passes 分层最值得借鉴；2.1.0 强依赖 `isolated-vm@5.0.4`，不进入主 Node |
| [pljeroen/deobfuscate-js](https://github.com/pljeroen/deobfuscate-js) | 3/0 | MIT | 强依赖 `isolated-vm` 且成熟度不足，不作为默认工具 |
| [notemrovsky/tiktok-reverse-engineering](https://github.com/notemrovsky/tiktok-reverse-engineering) | 149/30 | 未声明 | 只借鉴 opcode map + runtime trace 对齐方法，不复制代码 |
| [authrequest/hermes-dec](https://github.com/authrequest/hermes-dec) | 0/0 | AGPL-3.0 | React Native Hermes 专用，不作为 Web JSVMP 主链 |
| [WebAssembly/instrument-tracing](https://github.com/WebAssembly/instrument-tracing) | 16/6 | Other | 陈旧 proposal，不引入项目 runtime |

## 本地知识库证据

- `article/anti-detection/ruyi-browser-anti-detection-compilation/ruyi-20260424-01.md`：217/256 opcode、11262 条指令、154 个函数，并用真实请求闭环验证。
- `article/anti-detection/ruyi-browser-anti-detection-compilation/ruyi-20260526-01.md`：`TextDecoder`、WASM 调用栈、`getRandomValues` 和 DOM 查询边界。
- `article/anti-detection/ruyi-browser-anti-detection-compilation/ruyi-20260607-01.md`：正向生成、解码和多项离线 parity 闭环。

采用任何上游前必须重新核验版本、license、依赖树和运行方式。复制具体代码时保留来源与 license；未声明 license 的仓库只能作为阅读证据。

## 当前本地决策

2026-07-18 已落地自有 `safe_ast_transform.mjs`，只使用 MIT 的 Babel 7.29.7 parser/traverse/generator/types，锁定在 `tools/web-deobfuscation/package-lock.json`。没有复制上述候选项目代码，也没有引入 `isolated-vm`、native addon 或目标代码执行 pass。
