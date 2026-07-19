# Web deobfuscation case contract

## Manifest 顶层字段

| 字段 | 规则 |
|---|---|
| `schema_version` | 当前固定为整数 `1` |
| `case_id` | 1–80 位小写字母、数字、`.`、`_`、`-`，首位必须是字母或数字 |
| `profile` | `ast-safe`、`jsvm-verifiable`、`wasm-boundary`、`triage-only` |
| `claim_scope` | 必须属于 profile 允许范围 |
| `artifacts` | key 到 case root 内相对路径的映射；禁止绝对路径和 `..` 越界 |
| `checks` | 每项必须显式 `passed: true`，并列出支撑该 check 的 artifact key |
| `limitations` | `triage-only` 必填且非空 |

所有 artifact 必须存在、非空。Validator 对 artifact 流式计算 bytes 和 SHA-256；UTF-8 JSON evidence 默认限制为 8 MiB，可用 `--max-json-bytes` 显式调整。它不修改 manifest 或已声明 artifact，也不执行目标代码；只有显式传入 `--report` 时才写独立验证报告。

## Profile artifact

### `ast-safe`

允许 claim scope：`transform-only`、`algorithm-only`。

必需 artifact：

- `input_snapshot`、`output_snapshot`
- `parse_before.json`、`parse_after.json`：对象且包含 `"passed": true`
- `transform_report.json`：包含非空字符串数组 `applied_passes` 和空字符串数组 `unsafe_passes`

必需 checks：

- `parse_roundtrip` -> `parse_before`, `parse_after`
- `safe_passes_only` -> `transform_report`

### `jsvm-verifiable`

允许 claim scope：`partial`、`algorithm-recovered`。

必需 artifact：`input_snapshot`、`opcode_map`、`disassembly`、`runtime_trace`、`request_fixture`、`parity_report`。

- `opcode_map.json` 必须同时有非空 `opcodes` 和 `instruction_widths`。
- `parity_report.json` 必须包含 `"passed": true`。
- checks：`opcode_map_coverage`、`trace_alignment`、`request_parity`。

### `wasm-boundary`

允许 claim scope：`boundary-only`、`partial`。

必需 artifact：`input_snapshot`、`imports_exports`、`boundary_trace`、`wrapper_fixture`、`parity_report`。

- `imports_exports.json` 必须包含数组 `imports` 和 `exports`，空数组也要显式记录。
- `parity_report.json` 必须包含 `"passed": true`。
- 可选 `domtrace_summary.json` 一旦声明，必须使用 schema `2`，满足 `raw_invalid_lines == repaired_lines + unrecoverable_lines`、`invalid_lines == unrecoverable_lines`、repair 明细数与计数一致，并且 `unrecoverable_lines == 0`；否则 validator 拒绝。
- checks：`boundary_inventory`、`boundary_trace`、`wrapper_parity`。

### `triage-only`

只允许 claim scope `triage-only`。

- 必需 artifact：`input_snapshot`、`triage`。
- 必需 check：`limitations_recorded`。
- 顶层 `limitations` 必须列出当前缺失证据或稳定性问题。

## Check 示例

```json
"checks": {
  "parse_roundtrip": {
    "passed": true,
    "evidence": ["parse_before", "parse_after"]
  }
}
```

`evidence` 只能引用 manifest 已声明的 artifact key。文件缺失、JSON 无效、report 未通过、unsafe pass、opcode map 为空或路径逃逸都会使 validator 非零退出。
