# APK 逆向验证与交付清单

## 输入与工作区

- APK/XAPK/APKS 位于 `workspace\<project>\`，不是 `workspace\` 根目录。
- 记录输入绝对路径、SHA-256、文件大小和来源。
- `docs/workspace-projects.yaml` 中已有项目登记；新建/重命名项目后运行 workspace audit。
- 不对存在归属不明脏改动的项目执行 `clean/reset/stash`。

## Phase 0：指纹

- `fingerprint.sh` 成功识别 APK 数量、DEX 数量、ABI 和框架。
- 保护壳 marker 标为证据，不直接推断厂商版本/企业版。
- Flutter/RN/Unity/Cordova/Xamarin marker 已记录；hybrid 目标没有因单一 framework marker 跳过 DEX/Manifest 取证。
- XAPK/APKS 的所有 split 均参与 native library 和 marker 汇总。

## Phase 1：静态解包

- `decode.ps1` 没有删除源 APK、report、findings、triage 或其他项目文件。
- `decode-summary.json` 存在，包含输入 SHA-256、退出码和产物计数。
- `manifest-summary.txt` 存在，包含 SDK、Application、网络配置、权限、组件和 launcher。
- jadx 非零退出时确认是否仍有可用源码；apktool 非零退出时确认 partial smali/resources。
- Java 文件少于 50 时进入加固判断，不直接声称“无业务逻辑”。

## Phase 2：主战场决策

- Java/Kotlin、smali、动态 DEX、`.so`、Flutter/RN/Unity 主战场已明确。
- `System.loadLibrary()`、JNI wrapper、关键 native 方法已列出。
- 反调试/反 Frida/完整性/壳化 `.so` 已转 `native-reverse`。
- 纯静态算法 `.so` 才直接转 `ida-reverse` / `radare2`。

## Phase 3：动态验证

- LDPlayer 项目实例来自合适模板，未直接污染 `re-base/re-xposed/re-stealth`。
- 多设备时所有 ADB/Frida 命令显式指定 serial/device id。
- Host Frida 与 device frida-server 版本一致，且 host-to-device 进程枚举 handshake 成功；Frida 17 命令不含 `--no-pause`。
- Hook 前有无 Hook 基线，Hook 结论包含类/方法/签名/进程/时间和日志证据。
- 抓包 flow、Frida 日志和 dump 产物位于项目目录并已脱敏。

## DEX dump

- 使用 `dump-dex.ps1`，设备端临时文件默认已清理。
- `metadata.json` 中 PID cmdline、dumper exit、DEX 数量、有效数量、SHA-256、magic、`header_size`、file size 和 `class_defs` 完整。
- wrapper 状态已区分 `complete-enough`、`partial`、`invalid`、`no-dex`；`skeleton-only` / `triage-only` 作为人工分析结论另行记录。
- `invalid` / `no-dex` / dumper 非零退出时设备端证据未被删除，目标进程已 best-effort `SIGCONT`。
- jadx 使用 `-Pdex-input.verify-checksum=no` 后仍记录 loading/decompile errors。
- 企业壳结论只覆盖已验证样本和触发范围，不写“通杀”。

## Patch / 重建

- patch 点有文件、类/方法或 smali 路径和原始/修改逻辑。
- `rebuild-sign-install.ps1` 的 keystore 仅用于调试，未提交到 Git。
- `apktool b`、`zipalign`、`apksigner verify` 均成功。
- 含 `.so` 的 APK 已用 build-tools 35 `zipalign -P 16` 写入并校验；`llvm-readelf` 的 `PT_LOAD` 16 KB 风险已记录。
- 安装明确指定 `DeviceSerial`，并记录原包/修改包签名差异造成的影响。
- 完整性/签名校验目标在 patch 前已评估，失败不得归因成“重建工具问题”。

## API / 协议

- `find-api-calls.sh` 输出只作为候选；最终端点表经调用点/运行时复核后再填写 Host、Method、Path、Auth、Source、Confidence。
- 第三方 SDK URL 与一方业务 URL 已分桶。
- 签名/加密字段有调用链、输入、输出和运行时样本证据。
- 协议复现需要 Python collector 时转 `protocol-recovery`。

## 三件套审查门

- `report.md`：结论、范围、证据、限制、验证和下一步齐全。
- `findings.json`：严格使用 `reverse-coordinator-findings-v1`；每条 finding 有 `id/category/claim/location/evidence/confidence/redaction/rebuild_status`。
- `triage.md`：L0-L4、已做动作、失败原因、未验证项和建议齐全。
- `workspace.json.artifacts` 指向三件套真实路径。
- 所有 claim 可追溯到文件、行号、函数、命令输出或运行时日志。
- token、Cookie、账号、私钥、代理凭据和完整正文均已脱敏。
- L4/企业壳/VM 目标没有“完整还原”或“完整绕过”的虚假表述。
