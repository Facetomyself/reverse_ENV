# Web deobfuscation profiles

## 判定原则

`web_deobfuscation_gate.py` 只做启发式路由，不解析或执行目标 JavaScript：

- WASM / VM 核心 marker 只从 `--source` 计入，避免 Trace 文本反向污染目标分类。
- VM 可验证档要求 `--trace` 中出现 opcode event，并同时提供非空 `--fixture`。
- WASM 边界档要求 `--trace` 至少命中两类 boundary marker；fixture 仍由完成 validator 强制。
- 所有输入必须是非空 UTF-8 文本，每个文件默认不超过 8 MiB，并在报告中记录 SHA-256。

正则命中不是语义证明。压缩 bundle、生成器状态机和普通 parser switch 可能像 VM；业务使用 `WebAssembly` API 也不等于核心算法在 WASM。

## Profile 合同

### `ast-safe`

- 适用：字符串数组、`_0x*` 标识符、computed property、代理函数、debugger trap、控制流 dispatch 等静态形态。
- 深度：L2 / `transform-only`。
- 升级条件：transform 前后均可 parse；每个 pass 可命名；unsafe passes 为空；目标特定变换有 input/output fixture。
- 降级条件：pass 依赖 `eval`、`Function` 或执行目标 initializer；变换后 first divergence 无法定位。

### `jsvm-verifiable`

- 适用：源码同时出现 typed bytecode container、dispatch switch，以及 opcode/bytecode/interpreter loop/instruction pointer marker。
- 深度：L3 / `partial`；只有 opcode map、instruction widths、trace alignment、request parity 全部过门禁才可声明 `algorithm-recovered`。
- 升级条件：runtime Trace 至少有 opcode event，且存在脱敏 request/signer fixture。
- 降级条件：opcode 语义随会话漂移、instruction width 不稳定、只有静态 switch、缺前向对拍。

### `wasm-boundary`

- 适用：源码包含 `WebAssembly.instantiate`、`Module` 或 `.wasm`，Trace 可观察至少两类 imports/exports、TextEncoder/TextDecoder、linear memory、typed memory view、randomness 等边界。
- 深度：L3/partial / `boundary-only`。
- 升级条件：module inventory、boundary Trace、wrapper fixture 与 parity report 齐全。
- 降级条件：Trace 只有加载事件或 transport 噪声；没有稳定 I/O；把 wrapper 结果外推为 WASM 内部算法。

### `triage-only`

- 适用：看见 VM/WASM 形态但缺 runtime Trace、fixture 或稳定语义。
- 深度：L4 / `triage-only`。
- 交付：输入快照、限制清单、失败证据、下一次有界实验。不得写“已完整反编译”。

### `plain-js`

- 适用：没有足够反混淆 marker。
- 动作：返回 `ruyi-reverse`、`web-env-patcher` 或 `protocol-recovery`；不要为了使用本 skill 强造 case manifest。

## Hybrid 目标

同时命中 WASM 和 VM 时，先以最外层可观察边界分类：

1. 先固定 source、module 和 Trace hash。
2. JS/WASM boundary 可对拍时先交付 `wasm-boundary`。
3. WASM 内部还嵌 VM，但无内部 opcode Trace时保持未解释边界，不升级 claim。
4. 后续获得 opcode Trace 与 request fixture 后，再建立独立 `jsvm-verifiable` case，禁止两个 profile 共用一份模糊结论。
