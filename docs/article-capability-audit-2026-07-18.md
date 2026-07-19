# Article 知识库能力审计

> 审计日期：2026-07-18
> 范围：`article/` 全量 Markdown、项目 skill/tool/MCP 文档、`docs/workspace-projects.yaml`、重点 workspace triage，以及公开 GitHub 候选项目。
> 结论边界：本报告做能力与治理审计，不把文章中的个案结论直接当作当前工具链已验证能力。

## 执行摘要

`article/` 的主要问题不是内容不足，而是检索入口、清洁度和能力转化不足；其中知识库自身的 P0 已在本轮落地。

1. 当前 catalog 收录 306 篇文章：20 篇 canonical、286 篇合集子文章。`INDEX.md` 继续维护 canonical/tag 导航，新增 `CATALOG.md` 与 `catalog.json` 暴露全部逐篇记录。
2. 结构门禁已闭合：20/20 canonical 进入索引，286/286 子文章由父合集链接，缺失 H1、重复 H1、重复正文、本地坏链和生成漂移均为 0。
3. 清理已实施：首轮 `sanitize --apply` 修改 143 篇、删除 3789 行；扩充重复培训尾句 marker 后第二轮处理 33 篇、再删 402 行；另对 15 篇剩余候选定点删除 127 行，累计移除 4318 行广告/UI 噪声。
4. 新增零依赖 catalog/linter 与 6 个回归测试；当前 `check` 为 `ok=true`、0 errors，仅保留 Chromium 系列原始日期未统一标注的 1 条 warning。
5. 当前项目最值得继续吸收的四项能力是：Web AST/JSVMP/WASM 分级恢复、Protobuf/gRPC 二进制协议恢复、Unidbg 离线 JNI/SO 模拟、可恢复的 evidence/hypothesis 状态管理。
6. Web 路由 P0 已按审计建议落地：新增反混淆唯一正式入口 `web-deobfuscation`、零执行分类 gate、safe AST transform、evidence manifest validator 与 21 个回归测试，并用 evidence 档位替换不存在的 skill 和 WASM/VM 一刀切 L4 规则。
7. 真实 runtime 验收已补齐：Case 05 通过 Firefox 151 C++ DOMTrace、WASM boundary、两次本地前向 POST 和 8/8 parity；原始 serializer 坏行按 `raw_invalid_lines=1`、`repaired_lines=1`、`unrecoverable_lines=0` 分账，未知坏行由严格门禁拒绝。

## 1. 审计方法与证据

### 1.1 本地检查

- 根仓与 `article` 子模块均在 `main`，审计启动时已 fetch 对应 `origin` 且均为 `0/0` 分叉；本轮收尾再次 fetch 后根仓为 `0/4`。4 个 incoming commits 只改 `docs/MCP服务详情.md`、`mcp/README.md` 和 `mcp/wechat-miniapp-re-mcp` gitlink，唯一与当前 dirty path 精确重叠的是该 submodule，因此未执行 pull/rebase；`article` 仍为 `0/0`。
- 根仓审计前已有用户改动：`AGENTS.md`、`CLAUDE.md`、`mcp/wechat-miniapp-re-mcp`；本轮只在前两者定点追加知识库 catalog/linter 路由，未覆盖其他既有改动。
- 全量读取 `article/INDEX.md`、`README.md`、`AGENTS.md` 和 `article-archiver` 源 skill。
- 对全部 Markdown 做文件规模、目录分布、H1、正文哈希、索引链接、合集子链接、关键主题和清理噪声扫描。
- 对项目正式 skill、tools 清单、工作流和 45 个 workspace registry 条目做能力映射。
- 定向阅读 RuyiTrace、JSVMP、WASM、Unidbg、Protobuf/gRPC、AST 和 VMP trace 文章。

### 1.2 外部检索

先通过 `search-layer` 做 exploratory deep search，再使用项目内 `gh.exe` 直接核验候选仓库元数据、README、Stars、license 和活跃时间。项目规则禁止本任务启用 sub-agent，因此没有并行委派。

主要检索方向：

- evidence-first / resumable reverse engineering workflow；
- Android native/JNI 离线模拟与 MCP；
- Protobuf 无 schema 解码；
- JavaScript AST 反混淆；
- 本地 Markdown 混合检索与知识图谱。

### 1.3 限制

- 306 篇文章没有逐字人工复核；全量层面使用结构和规则扫描，重点主题及剩余高置信噪声候选才做深读。
- 主题命中文档数是启发式统计，适合判断存量方向，不等于每篇都能直接转成生产能力。
- DOMTrace/WASM 验收使用本地脱敏 fixture，不代表生产站点算法已恢复；Unidbg、Protobuf profile 和生产目标请求仍未实施。

## 2. 知识库现状

### 2.1 规模与分布

| 指标 | 结果 |
|------|------|
| catalog 文章记录 | 306 |
| 根级文档/生成目录 | 4 |
| 仓库 Markdown 总数 | 310 |
| canonical 文章 | 20 |
| 合集子文章 | 286 |
| 文章正文总大小 | 5908464 bytes |
| 文章正文总行数 | 109363 |
| 仓库 Markdown 总大小 | 6045521 bytes |
| 仓库 Markdown 总行数 | 109948 |
| `pending/` | 仅 `.gitkeep` |

| 分类 | 文件数 | 占比约值 | 判断 |
|------|-------:|---------:|------|
| `anti-detection` | 167 | 54.0% | 存量最强，含大量浏览器内核、指纹、Trace 和风控资料 |
| `mobile-app-reverse` | 95 | 30.7% | Android/Frida/Unidbg/Protobuf 存量充足 |
| `web-reverse` | 39 | 12.6% | AST、JSVMP、补环境和协议恢复资料较强 |
| `native-analysis` | 2 | 0.6% | 明显不足 |
| `packing-bypass` | 1 | 0.3% | 明显不足 |
| `protocols` | 1 | 0.3% | 与当前协议项目数量不匹配 |
| `signature-algorithms` | 1 | 0.3% | 与当前签名恢复任务数量不匹配 |

结论：知识库不是均衡型资料库，而是反检测、Android 和 Web 三类合集占绝对多数。Native、协议、签名和桌面二进制的 canonical 文章不足。

### 2.2 结构完整性

| 检查项 | 结果 |
|--------|------|
| canonical 文章进入 `INDEX.md` | 20/20 |
| `INDEX.md` 指向不存在文件 | 0 |
| 合集子文章由父文档链接 | 286/286 |
| 缺失 H1 | 0（本轮补齐 35 篇） |
| 重复正文 SHA-256 | 0 组 |
| 重复 H1 | 0 组 |
| `CATALOG.md` / `catalog.json` 生成漂移 | 0 |

现有两层结构本身没坏：`INDEX.md -> 合集 -> 子文章` 链路完整。问题在于检索粒度太粗，而不是链接丢失。

### 2.3 元数据一致性

以下 6 篇 canonical 项目文章在审计基线中未采用当前模板要求的 blockquote metadata（来源、日期、归档日期、分类）：

- `article/anti-detection/51job-anti-detection-analysis.md`
- `article/native-analysis/qidian-so-analysis.md`
- `article/packing-bypass/jiagu-bypass-analysis.md`
- `article/protocols/mmtls-protocol-analysis.md`
- `article/signature-algorithms/qidian-fock-signature.md`
- `article/web-reverse/51job-webpack-analysis.md`

本轮已统一补齐并通过 linter。`anti-detection/chromium-fingerprint-compilation.md` 是跨日期系列合集，原始日期未统一标注，因此保留 1 条非阻断 warning，不伪造单一日期。

### 2.4 清洁度债务与 P0 实施结果

审计基线曾命中 62 个文件含课程/代理/Token/社群推广，108 个文件含公众号页面 chrome，106 个文件含互动引导候选。当前处理结果：

| 动作/门禁 | 结果 |
|-----------|------|
| 首轮 `sanitize --apply` | 143 篇，删除 3789 行高置信尾部噪声 |
| 培训/付费圈/发群 marker 精修 | 33 篇，再删除 402 行重复推广尾巴 |
| 手工定点复核 | 15 篇，额外删除 127 行开头/尾部推广 |
| `关注该公众号` / `知道了` / `使用小程序` | 0 文件 / 0 次 |
| linter 高置信 tail marker | 0 |
| 保留的正文完整性声明 | 9 条（8 条知识星球截断说明 + 1 条空图文归档缺口） |

清理策略仍保持保守：`扫码`、`留言`、`知识星球` 等词可能属于技术语义或完整性声明，不进入无上下文机械删除规则。`sanitize` 默认 dry-run，`--apply` 只处理固定高置信 marker。

## 3. 文章中可转化的项目能力

### 3.1 主题存量概览

以下为启发式命中文档数，只用于判断知识存量：

| 主题 | 命中文档数 | 当前正式能力状态 |
|------|-----------:|------------------|
| Android/APK | 118 | 已有 `apk-reverse`，主链较成熟 |
| Frida/Hook | 105 | 已有 APK/native skill，覆盖较强 |
| Native/JNI | 94 | 有静态、Hook、dump；缺离线 JNI 模拟主链 |
| Unidbg/离线模拟 | 40 | 正式 skill/tool 路由缺失 |
| Web AST/反混淆 | 36 | 已落 `web-deobfuscation` 门禁与 Babel safe AST transform；更多通用 passes 和生产 target acceptance 待补 |
| WASM/JSVMP | 23 | 已按 Trace/fixture 分 L3/partial 与 L4；Case 05 已完成真实 C++ DOMTrace boundary acceptance |
| Protobuf/gRPC/二进制协议 | 42 | `protocol-recovery` 偏 Web signer，缺通用 profile |
| iOS/IPA | 17 | 仅 IDA/Mach-O 静态入口和泛化参考 |
| Flutter/RN/Unity | 10 | marker 与分流已有，深度工具不完整 |
| 符号执行/污点 | 7 | 仅 generic CTF/reference，非正式主链 |
| Fuzzing | 6 | 无项目级正式主链 |

### 3.2 能力一：Web AST、JSVMP、WASM 分级恢复

#### 文章证据

1. `ruyi-20260424-01.md` 记录了完整 JSVMP 恢复链：
   - 解析 VM 头部、字符串池和 opcode 变换；
   - 建立操作码映射；
   - 生成 11262 条反汇编、识别 154 个函数；
   - 把栈操作转为表达式树和 JavaScript；
   - 手工恢复核心签名函数；
   - 通过真实 API `Status 200` 和业务响应闭环验证。
2. `ruyi-20260526-01.md` 证明即使核心在 Rust WASM，DOMTrace 仍能观察 JS/WASM 边界：
   - `TextDecoder.decode` 暴露最终签名；
   - 调用栈定位 `.wasm`；
   - `Date.now`、`Math.floor`、`Crypto.getRandomValues` 和 DOM 查询可被记录；
   - 可先恢复环境依赖和 I/O 边界，而不是直接宣布“WASM 不可分析”。
3. `ruyi-20260607-01.md` 给出完整 Trace 闭环：浏览器信号 JSON、`deflate-raw`、随机 wrapper、9 字节循环 XOR、最终 POST body，离线验证全部为 true。
4. Web 合集中已有字符串去混淆、数组替换、控制流平坦化、Babel parser/traverse/generator 的可复用实现思路。

#### 实施前缺口

- `skill/web-env-patcher/SKILL.md` 把核心 WASM/JSVMP 阻塞路由到不存在的 `ast-deobfuscation` / `web-reverse-algorithm`。
- `reverse-coordinator`、`ruyi-reverse` 和 `mcp-js-reverse-playbook` 对 WASM/VM 基本按 L4 处理，缺少“可观察边界”和“可验证 VM”两档。
- `mcp-js-reverse-playbook/references/ast-deobfuscation.md` 已存在，但没有正式 skill、脚本合同、fixture 或 acceptance gate。
- `workspace/ruyi-mcp-practical-cases/triage.md` 明确当前案例只验证 BiDi Trace，不是 C++ DOMTrace。

#### 建议落地

建立唯一正式入口 `web-deobfuscation`，替换两个悬空 skill 名称，并与 `ruyi-reverse` 分工：

| 场景 | 建议深度 |
|------|----------|
| 纯 AST 字符串、数组、代理函数、死代码清理 | L2，可静态转换 |
| VM 头部/opcode/函数边界可识别，且有稳定请求 fixture | L3，允许反汇编器和部分反编译 |
| WASM 内部不可读，但 JS/WASM I/O、随机、DOM、压缩和网络边界可 Trace | L3/partial，恢复边界和可复现 wrapper |
| opcode 语义不稳定、无 fixture、Trace 只见 transport 噪声 | L4/triage-only |

工具建议采用“成熟通用 passes + 项目自定义 Babel transform”组合，不要把某个通用 deobfuscator 当万能解：

- `HumanSecurity/restringer`：模块化 safe/unsafe passes，适合作为 baseline；
- `j4k0xb/webcrack`：成熟 AST/解包 baseline，适合处理常见 bundler/obfuscator 外壳；
- `ben-sb/javascript-deobfuscator`：字符串、代理函数和表达式简化 baseline；
- 项目文章中的 Babel 脚本：负责目标特定控制器、state 和 opcode 语义。

Node 依赖必须锁定到 `tools/web-deobfuscation/` 或项目 `.runtime/`，不得污染主 Node。

#### 2026-07-18 实施结果

- 新增 `skill/web-deobfuscation/`，建立 `ast-safe`、`jsvm-verifiable`、`wasm-boundary`、`triage-only`、`plain-js` 五档只读分类。
- `web_deobfuscation_gate.py` 只读取非空 UTF-8 source/Trace/fixture 并计算 SHA-256，不执行目标 JavaScript；WASM/VM 核心 marker 与 runtime marker 分角色统计。
- `validate_web_deobfuscation_case.py` 强制相对路径边界、必需 artifact、parse/opcode/instruction-width/boundary/parity checks 和 claim scope；路径逃逸与伪造非 JSON report 已有回归用例。
- `safe_ast_transform.mjs` 使用锁定的 Babel 7.29.7，在不执行目标代码的前提下完成常量折叠、静态条件裁剪和可审计 transform report；Node 20.20.2 隔离依赖审计为 0 vulnerabilities。
- 已建立 Codex/Claude 薄入口，并同步 `reverse-coordinator`、`ruyi-reverse`、`mcp-js-reverse-playbook`、`web-env-patcher`、根路由与工作流文档；两个悬空 skill 名称已从正式路由移除。
- 验证：21 tests / OK；AST、JSVMP、WASM 三类 gate CLI、safe AST transform 与 manifest validator 均已用 fixture 实际调用；skill `quick_validate.py` 通过。未把 REstringer/webcrack 安装进主 Node。
- `workspace/ruyi-mcp-practical-cases` Case 05 已完成真实 Firefox 151 C++ DOMTrace + WASM boundary + 本地 POST acceptance；claim scope 固定为 `boundary-only`，不冒充 WASM 内部反编译。

#### 验收门槛

- 每个 transform 都有 input/output fixture 和 AST parse round-trip。
- safe passes 不执行目标代码；unsafe passes 必须显式启用并在隔离 runtime 运行。
- VM/WASM 结论至少有一条前向生成或请求 fixture 对拍，不以“代码变好看”作为完成标准。
- 在 `ruyi-mcp-practical-cases` 增加 DOMTrace 离线案例，再调整核心 L1-L4 路由。

### 3.3 能力二：Protobuf/gRPC 通用恢复主链

#### 文章证据

Android 合集已经覆盖完整链路：

- Wire Format、Tag、Varint、ZigZag、嵌套 message；
- `protoc --decode_raw`、递归裸解码；
- 从 `writeTo`、字段常量、descriptor、反编译类恢复 `.proto`；
- `blackboxprotobuf` typedef 修正和重新编码；
- gRPC 5 字节帧头、压缩标志和 HTTP/2；
- `ClientCalls`、Metadata、Protobuf 序列化层、`CodedOutputStream` 字段级 Hook；
- Frida 到 PC 实时解码，typedef 保存和后续复用。

GitHub 直接核验：`nccgroup/blackboxprotobuf` 为 MIT、730 Stars、115 forks，2026-04-13 仍有更新，适合作为可选解码依赖。

#### 当前项目命中

- 27 个 active workspace 中有 6 个 APK/Android 相关项目、2 个协议/API 逆向项目；另有 2 个 planned `apk-native-reverse` 项目。
- `workspace/bilibili/triage.md` 已明确写出“先动态捕获 header，再决定是否恢复 protobuf schema”。
- `jd-command-longlink-research`、`qidian`、`yyb` 等项目都可能遇到二进制帧、signer 或 native 序列化链。

#### 当前缺口

- `protocol-recovery` 当前模型主要是 Web signer/verifier/decode/session gated，缺 Android/Native 二进制协议 profile。
- 项目没有固定的 gRPC frame parser、protobuf heuristic、typedef 持久化和 round-trip 验证工具。
- eCapture、Reqable、Frida 和 APK 静态证据分散在不同 skill，缺统一编排。

#### 建议落地

在 `protocol-recovery` 增加 `protobuf-grpc` profile，而不是新建另一套孤立 skill：

```text
capture
  -> detect protobuf/grpc
  -> strip grpc frame / decompress
  -> decode_raw + blackbox typedef
  -> static class/writeTo/descriptor correlation
  -> field naming and schema confidence
  -> re-encode round-trip
  -> collector / fixture / report
```

建议产物：

- `samples/raw/*.bin`
- `samples/scrubbed/*.bin`
- `schema/typedef.json`
- `schema/recovered.proto`
- `decoded/*.json`
- `evidence/roundtrip.json`

`blackboxprotobuf` 仅作为项目 venv 的可选依赖；安装前仍需用户确认，不得写系统 Python。

#### 验收门槛

- 正确处理 gRPC 5 字节帧头和压缩标志。
- 无 schema 时输出 field number、wire type、多候选类型和置信度，不猜字段名。
- typedef/recovered proto 能重新编码，结果与原始 payload 字节级一致，或明确记录允许差异。
- 所有抓包和 message 内容先脱敏，再进入三件套。

### 3.4 能力三：Unidbg 离线 JNI/SO 模拟

#### 文章证据

知识库有约 20 篇连续 Unidbg 专题，已经形成成熟方法论：

- 四层补环境模型：JNI、syscall、文件、库函数；
- 最小干预，不以“能继续跑”替代正确性；
- 指令级、函数级、内存级三层 Trace；
- 分析期 Unicorn2、生产期 Dynarmic/KVM 的分层；
- Trace diff、算法常量、Hook dump、标准实现对比、高级语言重写；
- 100 个随机输入和真机交叉验证；
- 对象池、预热、健康检查、超时、native RSS 和错误实例销毁。

本地还存在 `workspace/tmp-unidbg-analysis`：

- 配置了 `origin=LunFengChen/unidbg` 和 `upstream=zhkl0228/unidbg`；
- 当前 commit 为 2026-06-11；
- README 已包含 MCP debugger、trace、custom tools；
- 工作树含用户修改的 IPA 资源，按 registry 必须保持 excluded/protected，不能直接升格为项目工具。

GitHub 直接核验：`zhkl0228/unidbg` 为 Apache-2.0、5079 Stars、1163 forks，2026-06-28 仍更新，且已原生支持 MCP、JNI、syscall、Unicorn/Dynarmic、Android/iOS 实验能力。

#### 当前缺口

- 正式 `apk-reverse` / `native-reverse` 没有 Unidbg 路由、wrapper、fixture 和验收合同。
- 当前主要依赖真机/LDPlayer + Frida，遇到反调试、批量签名和确定性对拍时成本较高。
- 现有 dirty external worktree 不适合作为可复现 runtime。

#### 建议落地

新增 `unidbg-emulation` skill，作为 `apk-reverse` / `native-reverse` 的按需子路由：

- 只在目标函数、JNI 入口和输入输出已经定位后启用；
- 使用 clean、固定 commit 的 canonical upstream，建议放 `tools/unidbg/` 并作为独立 submodule 或固定源码资产；
- MCP 属于交互式 SSE/on-demand 能力，不进入 cold-start `.mcp.json`；
- dirty 的 `workspace/tmp-unidbg-analysis` 保持原状，只作为历史研究 worktree；
- 默认先生成项目级 harness，再按需要补 JNI/syscall/file/library 四层环境。

优先 pilot：

1. 选择已有真实输入输出、算法入口明确的 `.so`；
2. 用 Unicorn2 做 trace 和对拍；
3. 用高层语言重写或保留 repeatable custom MCP tool；
4. 再评估 Dynarmic 与池化，不一上来做生产服务。

#### 验收门槛

- 同一输入在 Unidbg 中确定性复现。
- 至少 100 组随机输入与重写实现一致。
- 至少一组真机/LDPlayer 结果交叉验证，防止 anti-emulator 假路径。
- 每个补环境值有来源：静态推理、真机采样、fixture 或明确的无关分支证明。
- TEE/Keystore、冷门 syscall、重度 VM 等边界进入 `triage.md`，不硬补到“看起来能跑”。

`VortexDBG` 提供 DEX/Java + native 双向 JNI 和大量 MCP tools，但当前只有 5 Stars、0 forks，适合作为 watchlist，不应替代 Unidbg 成为首选依赖。

### 3.5 能力四：持久 evidence 与 hypothesis 状态

#### 文章与外部证据

`ai-assisted-vmp-trace-recovery.md` 的核心不是某个 AES/HMAC 结论，而是：

- 大规模 trace 进入 fixed-width 数据库和索引；
- AI 只做小查询，不吞整份 trace；
- 从输出回溯 producer、PC count、跨 run 稳定性和 I/O boundary；
- 每条结论都落成 Python assertion；
- `KEY16`、HKDF、五段 SHA、自定义 VM 等错误路线被保留并明确淘汰原因。

公开项目也给出相同工程模式：

- `mrphrazer/agentic-malware-analysis`：per-sample case directory、13 个固定 artifact、hypothesis、component inventory、`CURRENT_STATE.json`；GPL-2.0，279 Stars。
- `Dryxio/auto-re-agent`：reverser/checker、build/test/parity gate、`knowledge-graph.json`、per-function progress；MIT，1087 Stars。

#### 当前缺口

当前三件套和 `workspace.json` 已经比普通项目强，但还缺：

- 原始 evidence 的统一 ID、hash、collector、时间和 redaction manifest；
- 假设的 `active/rejected/confirmed` 生命周期；
- finding 到 evidence/hypothesis 的稳定引用；
- 大 trace/多阶段任务在 context compaction 后的可恢复查询计划。

#### 建议落地

保持三件套合同不变，增加两个可选辅助产物：

- `evidence/manifest.json`
- `hypotheses.json`

最小字段建议：

```json
{
  "evidence": {
    "id": "EV-001",
    "path": "evidence/trace-window-001.json",
    "sha256": "...",
    "collector": "ruyitrace|frida|ida|unidbg|manual",
    "redacted": true,
    "supports": ["F-001", "H-003"]
  },
  "hypothesis": {
    "id": "H-003",
    "status": "rejected",
    "claim": "output is HKDF expansion",
    "evidence_ids": ["EV-001", "EV-004"],
    "disproof": "standard-library forward reproduction failed",
    "next_test": null
  }
}
```

这类增强应先在 VMP/大 trace 项目试点，确认不会变成文档负担，再决定是否写入 coordinator 模板。

### 3.6 能力五：浏览器指纹回归矩阵

反检测文章占知识库 54%，但当前项目验证仍偏“工具能调用”和单站结果。文章存量覆盖：

- AudioContext、Canvas、WebGL/WebGPU、字体、WebRTC；
- CSS/HTML-only 指纹、CPU timing、传感器和行为特征；
- session linkability、住宅代理检测、TLS/JA3/JA4；
- CDP/BiDi/自动化检测和 DOMTrace。

当前已知边界：

- `ruyi-mcp-practical-cases` Case 01–04 主要验证 BiDi Trace，Case 05 已单独完成 C++ DOMTrace；两类证据仍不得混用；
- Firefox TLS 未伪装成指定 Chrome 指纹；
- 项目能力矩阵中 AudioContext 仍是缺口；
- BrowserScan 100% 只代表单次公开检测页。

建议把文章中的检测维度转为离线/自有站点 regression fixtures，而不是继续堆第三方检测站截图：

- JS-visible fingerprint fixture；
- DOM/CSS/layout fixture；
- Audio/WebGPU fixture；
- session consistency fixture；
- human input trusted-event fixture；
- BiDi Trace 与 DOMTrace 分层 fixture；
- TLS/HTTP2 只做网络层独立门禁。

## 4. 优先级路线图

| 优先级 | 工作项 | 影响 | 改动规模 | 推荐先做 |
|--------|--------|------|----------|----------|
| P0 | 清理推广/UI 噪声，生成细粒度 catalog 和 linter | 所有新任务检索、知识可信度 | M | 已实施（2026-07-18） |
| P0 | 修复 AST skill 悬空路由，增加 Web VM/WASM 分级门 | Web 项目、RuyiTrace、补环境 | M | 已实施（2026-07-18） |
| P0 | 为 `protocol-recovery` 增加 Protobuf/gRPC profile | Bilibili、JD、后续 APK/API | M | 是 |
| P1 | 建立 Unidbg on-demand skill + clean pinned runtime pilot | 6 个 active APK、2 个 planned native APK | L | 是，先 pilot |
| P1 | 增加 evidence manifest / hypothesis lifecycle 试点 | VMP、大 trace、长周期项目 | M | 先单项目 |
| P1 | 增加 DOMTrace/指纹回归案例 | ruyi-mcp 与 web-env | M | 已完成 WASM boundary Case 05；完整指纹矩阵待后续 |
| P2 | iOS/Flutter/Swift 独立能力 | 当前 Windows 环境限制明显 | L | 暂缓，只补静态路由 |
| P2 | 符号执行、污点、fuzzing 正式 skill | 文章证据和当前需求都偏弱 | L | 暂缓 |
| P2 | 向量/知识图谱检索 | 300+ 篇后开始有价值 | L | catalog/FTS 基线后再评估 |

## 5. 知识库自身的改造状态与后续

### 5.1 生成式 catalog

已保留 `INDEX.md` 作为人工维护的 canonical/tag 导航，并新增机器生成：

- `article/CATALOG.md`：306 篇逐篇标题、路径、日期、分类、父合集和关键 heading；
- `article/catalog.json`：供 skill 和脚本读取；
- `article/scripts/kb_catalog.py`：标准库零依赖，输出排序固定，运行两次无 diff。

第一阶段不急着上 embeddings。中文知识库先做：

1. 标题、heading、metadata、路径和人工关键词索引；
2. `rg`/substring 检索；
3. SQLite FTS5 若使用，优先验证 trigram 对中文的实际效果；
4. 只有关键词召回确实不足时再加向量检索。

`ceaksan/dnomia-knowledge` 的 FTS5 + sqlite-vec + RRF + heading chunk 思路值得参考，但项目只有 1 Star，不建议直接引入；先复用架构，不复用依赖栈。

### 5.2 知识库 linter

`article-archiver` 已接入 `kb_catalog.py generate/check/sanitize`，当前只读检查覆盖：

- canonical metadata 是否齐全；
- `INDEX.md` canonical 覆盖；
- 合集子文章覆盖；
- 本地 Markdown 链接；
- duplicate H1/content；
- 固定公众号 chrome 和推广段；
- 生成文件漂移。

脚本读取 UTF-8，并在 `sanitize` 写回时保持既有 BOM/换行；本轮另做字节级编码/换行复核。清理规则保持高置信 marker + dry-run，避免误删技术正文中的“扫码”“留言”等词。

### 5.3 从当前项目回填知识库

当前项目已有、但知识库 canonical 覆盖不足的主题：

1. WMPF `flue.dll` 偏移提取、跨版本 AOB 和 runtime acceptance；
2. wxapkg / PC 微信小程序动态与静态证据链；
3. 易语言工程安全静态恢复；
4. WSH/PE polyglot 和桌面二进制分析；
5. 通用 evidence/redaction/triage 方法；
6. Protobuf/gRPC 恢复的项目级实证文章。

分类建议：

- 小程序/WMPF 至少形成 2 到 3 篇 canonical 后，再建立 `mini-program-reverse/`，避免为单篇文章开空分类。
- 桌面 PE/WSH、固件、iOS 暂不急着建分类；先看是否能形成持续产出。

## 6. 外部候选项目评估

Stars 和活跃时间为 2026-07-18 使用 GitHub CLI 实测。

| 项目 | Stars/Forks | License | 活跃时间 | 本地用途 | 结论 |
|------|-------------|---------|----------|----------|------|
| [zhkl0228/unidbg](https://github.com/zhkl0228/unidbg) | 5079/1163 | Apache-2.0 | 2026-06-28 | Android JNI/SO 模拟、Trace、MCP | 首选 pilot |
| [ben-sb/javascript-deobfuscator](https://github.com/ben-sb/javascript-deobfuscator) | 1139/153 | Apache-2.0 | 2025-07-15 | 通用 JS deobfuscation baseline | 可选依赖，需 fixture |
| [Dryxio/auto-re-agent](https://github.com/Dryxio/auto-re-agent) | 1087/137 | MIT | 2026-07-15 | checker/parity/evidence graph 模式 | 借鉴架构，不直接接管 IDA 主链 |
| [nccgroup/blackboxprotobuf](https://github.com/nccgroup/blackboxprotobuf) | 730/115 | MIT | 2026-04-13 | 无 schema Protobuf decode/encode | 推荐可选依赖 |
| [HumanSecurity/restringer](https://github.com/HumanSecurity/restringer) | 597/63 | MIT | 2025-12-07 | safe/unsafe 模块化 AST passes | 推荐 baseline |
| [llnl/OGhidra](https://github.com/llnl/OGhidra) | 289/31 | Other | 2026-07-15 | Ghidra + LLM | 与现有 IDA MCP 重叠，暂不引入 |
| [mrphrazer/agentic-malware-analysis](https://github.com/mrphrazer/agentic-malware-analysis) | 279/43 | GPL-2.0 | 2026-03-22 | case directory/hypothesis/state | 只借鉴模式，注意 GPL |
| [incogbyte/android-reverse-engineering-claude-skill](https://github.com/incogbyte/android-reverse-engineering-claude-skill) | 88/18 | Unlicense | 2026-06-20 | Android 自动化 RE skill | 与现有 `apk-reverse` 高度重叠 |
| [carlosadrianosj/VortexDBG](https://github.com/carlosadrianosj/VortexDBG) | 5/0 | Apache-2.0 | 2026-07-16 | DEX/Java/native 一体 MCP | 观察名单，成熟度不足 |
| [ceaksan/dnomia-knowledge](https://github.com/ceaksan/dnomia-knowledge) | 1/0 | MIT | 2026-04-29 | Markdown hybrid search | 只参考架构 |

## 7. 建议的第一批实施顺序

1. 已完成 article cleanup + catalog/linter，306 篇资料已具备逐篇目录和结构门禁。
2. 已完成 Web AST 悬空路由修复；已用现有文章和离线 fixture 建立 `web-deobfuscation` 零依赖最小闭环。
3. 已在 `ruyi-mcp-practical-cases` 增加 Case 05 DOMTrace closed-loop 案例，并以 `boundary-only` 证据验证 WASM 分级规则。
4. 给 `protocol-recovery` 加 Protobuf/gRPC profile，优先命中 Bilibili 的现有 triage。
5. 使用 clean pinned Unidbg 做一个单函数 pilot；成功后再决定是否新增正式 skill 和 on-demand MCP wrapper。
6. 在一个大 trace 项目试点 evidence manifest/hypothesis lifecycle，确认收益后再更新全局模板。

## 8. 本轮实施边界与剩余事项

- 知识库 P0 已实施；中置信互动词仍不做无上下文批量删除，后续归档按 linter + 人工复核持续收敛。
- Web 路由 P0、safe AST 和 Case 05 真实 DOMTrace + 本地前向请求 acceptance 已完成；该案例只支持 `boundary-only`，不冒充生产目标或 WASM 内部算法恢复。
- Unidbg、Protobuf profile 和 coordinator artifact 仍属于后续跨 skill/runtime 改动，需要独立 fixture、依赖门禁和真实 acceptance。
- 根仓已有用户维护中的治理文件和 MCP submodule 改动均保留；当前 `HEAD` 是 `origin/main` 的祖先但落后 4 个提交，唯一 incoming/dirty 重叠为 `mcp/wechat-miniapp-re-mcp` gitlink。submodule 当前干净地停在 `fix/project-review-p0@6de6b79`，incoming gitlink 为其后继 `32e1e3f`；未在脏主仓中强行同步。
