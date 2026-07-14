# panda-dex-dumper

## 来源与本地资产

- 上游项目：[`P4nda0s/panda-dex-dumper`](https://github.com/P4nda0s/panda-dex-dumper)
- 本地文件：`D:\reverse_ENV\tools\panda-dex-dumper\panda-dex-dumper`
- 仓库登记版本：`1.0.0`
- 文件形态：无扩展名裸二进制；Android ELF64 little-endian，AArch64，ELF type 为 `DYN`
- SHA-256：`BB69815BCEC34A29C410EE7D820962335F5C0CB865FB9CFF38C0DB73377F5E2C`
- License：当前未确认。本地目录没有随二进制保存授权文本，使用或再分发前需单独核对上游授权状态。

## 已验证路线

该工具以 Root 权限读取 `/proc/<pid>/mem`，扫描目标进程中已经加载的标准完整 DEX。当前已验证以下路线可执行：

- LDPlayer 9 主 ABI 为 x86_64，通过 `libnb.so` native bridge 执行本地 AArch64 二进制
- Root、正确目标 PID、真实 DEX 已完成解密和加载时，可以导出 whole-DEX
- Magisk Manager 实测导出 19 个 DEX，共 21,134,420 bytes
- 起点读书 / 360 Jiagu VIP 实测导出 13 个 DEX，共 73,247,772 bytes；能取得大量业务类，但仍有加载和反编译错误，只能标记为部分脱壳

这证明“LDPlayer x86_64 + `libnb.so` + panda”路线可用，也能覆盖部分企业壳样本；不代表所有企业壳都能完整脱壳。多进程目标需要逐 PID 扫描，lazy loading 目标需要在真实 DEX 加载完成后再执行。

优先使用项目封装脚本，它会记录设备 ABI、native bridge、DEX 元数据和 dumper 哈希，并在异常路径尽力恢复目标进程：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\dump-dex.ps1" -Project demo -Package com.example.app -DeviceSerial "127.0.0.1:7555" -Launch
```

## 进程暂停风险

panda 扫描前会向目标进程发送 `SIGSTOP`，结束后再发送 `SIGCONT`。如果工具 panic、被杀或异常退出，恢复步骤可能没有执行，目标进程会保持暂停状态。

- 优先走 `dump-dex.ps1`；其 `finally` 会 best-effort 执行 `kill -CONT <pid>`
- 手工调用后无论成功失败都应执行 `& "D:\reverse_ENV\tools\adb\adb.exe" -s <serial> shell su -c "kill -CONT <pid>"`
- 工具不内置 anti-Root、anti-emulator、anti-ptrace 或 anti-pause 绕过；命中检测时转 `native-reverse` 做定向处理

## 能力边界

| 目标形态 | 结论 |
|----------|------|
| 内存中存在完整标准 DEX | 适用；仍需校验 DEX header、业务类数量、方法体完整性和 jadx 错误数 |
| CDEX / CompactDex | 不支持；不能把 CompactDex 扫描结果当作标准 DEX 产物 |
| 方法抽取、按需回填、缺失 `CodeItem` | whole-DEX dump 不能自动补回缺失方法体或重建 `CodeItem`，结果通常只能标记为 partial / triage-only |
| VMP | 不能通过扫描 DEX 还原 VM opcode 语义，需要单独做解释器、opcode 和运行时分析 |
| Dex2C | Java 方法已迁移到 native，DEX dump 只能保留壳层或调用桩，应转 `native-reverse` / `ida-reverse` |

任何 dump 结果都不能只按“生成了 `.dex` 文件”判定成功。至少检查文件大小与 header 是否一致、类和方法数量、业务包覆盖率、反编译错误，以及关键方法是否仍为空壳或 native stub。
