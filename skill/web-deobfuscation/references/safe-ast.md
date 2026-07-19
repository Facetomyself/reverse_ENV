# Safe AST baseline

## 定位

该 baseline 只解决可静态证明的语法清理，不承担字符串解码器执行、JSVMP 解释器恢复、WASM 反编译或补环境。源码位于 `skill/web-deobfuscation/scripts/safe_ast_transform.mjs`，依赖隔离在 `tools/web-deobfuscation/`。

## Runtime

| 项目 | 固定值 |
|---|---|
| Node | `tools/node/node.exe` 20.20.2 |
| Babel parser/traverse/generator/types | 7.29.7 |
| Lockfile | `tools/web-deobfuscation/package-lock.json` |
| 安装脚本 | `npm install --ignore-scripts --no-audit --no-fund` |
| Native addon / isolated-vm | 不使用 |

Babel 8 当前要求 Node 22.18+，与项目主 Node 20 合同不兼容，因此本 baseline 固定 Babel 7.29.7，不切换主 runtime，也不把依赖装到仓库根目录或系统全局。

## Passes

| Pass | 默认 | 边界 |
|---|---|---|
| `normalize-computed-properties` | 是 | 仅把合法 identifier 的静态 string key 改成 dot/property；对象字面量 `__proto__` 明确排除 |
| `fold-static-literals` | 是 | 只折叠 primitive literal 的有限 unary/binary 运算；拒绝 Infinity、NaN、负零和对象 coercion |
| `prune-constant-branches` | 是 | 只处理 boolean literal 的 `if`、conditional、`&&`、`||` |
| `remove-debugger-statements` | 否 | 改变 debugger 行为，必须由调用方显式选择 |

未知 pass、重复 pass、空 pass 列表和输入覆盖都会直接失败。即使源码含 `eval`、`Function` 或字符串 timer，工具也只在 report 中计数，不执行它们。

## Evidence contract

一次成功运行必须生成：

- transform 前后源码快照。
- `parse-before.json` / `parse-after.json`，两者 `passed=true`。
- `transform-report.json`：`applied_passes` 非空、`unsafe_passes=[]`、`target_code_executed=false`、每个 pass 的 change count。

这些文件可直接进入 `ast-safe` case manifest，再由 `validate_web_deobfuscation_case.py` 验证。Parse round-trip 证明语法有效，不自动证明业务语义 parity；目标特定 transform 仍需独立 fixture。

## 安装与验证

```powershell
& "D:\reverse_ENV\tools\node\npm.cmd" `
  --prefix "D:\reverse_ENV\tools\web-deobfuscation" install `
  --cache "D:\reverse_ENV\tools\web-deobfuscation\.npm-cache" `
  --ignore-scripts --no-audit --no-fund

& "D:\reverse_ENV\.venv\Scripts\python.exe" -m unittest `
  "skill.web-deobfuscation.tests.test_safe_ast_transform" -v
```
