---
name: web-deobfuscation
description: Use for evidence-gated Web JavaScript deobfuscation in D:\reverse_ENV after browser or CDP reconnaissance, including safe AST transforms, JSVMP opcode/disassembly recovery, JS/WASM boundary reconstruction, fixture parity, and triage-only classification without executing target code or polluting the project runtime.
---

# Web Deobfuscation

## 定位

本 skill 是 Web JavaScript 反混淆和 VM/WASM 恢复的唯一正式入口。它接收 `ruyi-reverse` 或 `mcp-js-reverse-playbook` 的源码、Trace 和脱敏 fixture，先分类，再按证据合同决定能做到 L2、L3/partial，还是只能 L4/triage-only。

```text
ruyi-reverse / mcp-js-reverse-playbook
  -> web-deobfuscation
  -> web-env-patcher / protocol-recovery
```

典型触发：

- 字符串数组、代理函数、表达式折叠、控制流平坦化等 AST 清理。
- JSVMP / VM opcode、字节码头部、解释器循环、函数边界恢复。
- WASM 内部暂不可读，但 JS/WASM imports、exports、memory、codec、随机数和网络边界可观察。
- 需要判断一个 Web 混淆目标究竟可恢复，还是只能保留 triage。

## 硬边界

1. 默认不执行目标 JavaScript；分类脚本只做 UTF-8 文本扫描和 hash。
2. 不提供“万能反混淆器”，不以代码变好看作为完成标准。
3. 不自动运行 `npm install`、`pip install`、`nvm`，不切换 `tools\node\node.exe`。
4. 第一阶段只接受 safe AST passes；`eval`、`Function`、字符串 timer 和需要执行目标代码的 pass 不得进入验收链。
5. 可选 Node 工具只能在用户确认后锁定到 `tools\web-deobfuscation\` 或 `workspace\<项目名>\.runtime\`；原始源码、Trace、fixture 和报告全部落归属明确的 workspace 项目。
6. WASM 只恢复已观察的边界时，claim scope 必须是 `boundary-only` 或 `partial`，不得外推内部算法。
7. 缺 opcode trace、边界 Trace 或前向 fixture 时保持 `triage-only`，不得声称已反编译或已还原。

## 标准工作流

### 0. 前置证据

开始前至少应有：

- 目标源码快照及 SHA-256。
- `ruyi-reverse` / CDP 保存的目标请求、initiator 或 runtime 证据。
- 涉及 VM/WASM 时的脱敏 Trace；要做完成验收时还需请求、signer 或 wrapper fixture。

没有浏览器证据时先返回上游取证，不要拿静态关键词硬猜 opcode 语义。

### 1. 运行只读分类门禁

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\web-deobfuscation\scripts\web_deobfuscation_gate.py" `
  --source "D:\reverse_ENV\workspace\<project>\samples\target.js" `
  --trace "D:\reverse_ENV\workspace\<project>\captures\runtime.ndjson" `
  --fixture "D:\reverse_ENV\workspace\<project>\fixtures\request.fixture.json" `
  --output "D:\reverse_ENV\workspace\<project>\evidence\web-deobfuscation-gate.json"
```

解释分类前先读 [profiles.md](references/profiles.md)：

| Profile | 深度 | 可做什么 |
|---|---|---|
| `ast-safe` | L2 | parser round-trip + 命名 safe passes + transform report |
| `jsvm-verifiable` | L3 | opcode map、instruction width、反汇编与 runtime trace 对齐、请求对拍 |
| `wasm-boundary` | L3/partial | imports/exports、memory/codec/random/DOM/network 边界与 wrapper 对拍 |
| `triage-only` | L4 | 记录缺口和下一次有界实验，不宣称算法恢复 |
| `plain-js` | L1/L2 | 反混淆不是当前阻塞，回到补环境或协议链 |

分类是路由证据，不是完成证明。正则 marker 只能说明“值得走哪条验收链”，不能替代 AST、opcode 或 runtime 语义验证。

### 2. 按 profile 收集证据

- `ast-safe`：保存 transform 前后源码、两次 parse report、完整 applied passes 和空的 unsafe passes。
- `jsvm-verifiable`：记录字节码头、函数边界、opcode 语义来源、instruction width、反汇编、opcode runtime trace 和前向请求 fixture。
- `wasm-boundary`：记录 module hash、imports/exports、memory view、TextEncoder/TextDecoder、随机源、DOM/网络调用和 wrapper 输入输出；若声明 `domtrace_summary`，必须保留 raw/repaired/unrecoverable 计数并让不可恢复行归零；内部不可见部分继续留在 triage。
- `triage-only`：写明缺失证据、失败实验和下一次最小采样，不扩大扫描范围碰运气。

具体 artifact 和 `checks` 名称见 [case-contract.md](references/case-contract.md)。可复制 [case-manifest.example.json](references/case-manifest.example.json) 到 workspace 后按真实路径修改。

#### `ast-safe` 本地 baseline

用户确认安装隔离依赖后，可用锁定的 Babel 7.29.7 runtime 执行纯静态 baseline：

```powershell
& "D:\reverse_ENV\tools\node\node.exe" `
  "D:\reverse_ENV\skill\web-deobfuscation\scripts\safe_ast_transform.mjs" `
  --input "D:\reverse_ENV\workspace\<project>\samples\input.js" `
  --output "D:\reverse_ENV\workspace\<project>\samples\output.js" `
  --parse-before "D:\reverse_ENV\workspace\<project>\evidence\parse-before.json" `
  --parse-after "D:\reverse_ENV\workspace\<project>\evidence\parse-after.json" `
  --report "D:\reverse_ENV\workspace\<project>\evidence\transform-report.json"
```

默认 pass 只包含 computed property 规范化、primitive literal folding 和常量分支裁剪；`remove-debugger-statements` 必须显式传入。工具只读 AST，不 import 目标模块，不调用 `eval` / `Function`，不执行 initializer。精确边界和安装方式见 [safe-ast.md](references/safe-ast.md)。

### 3. 选择实现手段

- 项目自定义 Babel transform 优先处理目标特定 controller、state、opcode 语义。
- 通用工具只作为可选 baseline，不直接接管证据链；引入前查 [upstreams.md](references/upstreams.md) 的 license、成熟度和隔离限制。
- 不复制无 license 项目的代码；需要 `isolated-vm` 或 native addon 时，先停在依赖提案，得到用户确认后再走独立 runtime。
- 每个 transform 必须可命名、可关闭、可定位输入输出；出现 first divergence 就回退最后一个 pass。

### 4. 运行完成门禁

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\web-deobfuscation\scripts\validate_web_deobfuscation_case.py" `
  --manifest "D:\reverse_ENV\workspace\<project>\web-deobfuscation.case.json" `
  --report "D:\reverse_ENV\workspace\<project>\evidence\web-deobfuscation-validation.json"
```

只有 validator exit `0` 且目标 profile 的 parity / parse / trace checks 全部通过，才能使用 manifest 中声明的 claim scope。`plain-js` 不进入该 validator；直接回到上游链路。

### 5. 交付衔接

- AST/VM/WASM wrapper 已对拍，但仍依赖 WebAPI/浏览器状态：切 `web-env-patcher`。
- signer / decoder / session chain 已可稳定前向生成：切 `protocol-recovery`。
- 完整分析仍需三件套：`report.md`、`findings.json`、`triage.md`；manifest 和 validator report 作为 evidence 附件。

## 资源

- [profiles.md](references/profiles.md)：分类规则、证据升级条件和误判边界。
- [case-contract.md](references/case-contract.md)：manifest、artifact、checks 与 claim scope 合同。
- [upstreams.md](references/upstreams.md)：可选上游项目和本地知识库证据。
- [safe-ast.md](references/safe-ast.md)：隔离 Babel baseline、命名 passes、CLI 与证据合同。
- `scripts/web_deobfuscation_gate.py`：零依赖、零执行的只读分类门禁。
- `scripts/validate_web_deobfuscation_case.py`：零依赖 evidence manifest 验证器。
- `scripts/safe_ast_transform.mjs`：使用 `tools/web-deobfuscation` 锁定依赖的纯静态 AST baseline。
