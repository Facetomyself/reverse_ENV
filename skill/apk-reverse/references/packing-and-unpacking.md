# Android 加固识别与脱壳路由

## 目录

1. [先判定保护类型](#先判定保护类型)
2. [轻量识别](#轻量识别)
3. [本地可用路线](#本地可用路线)
4. [产物验证](#产物验证)
5. [失败后的分流](#失败后的分流)
6. [外部候选](#外部候选)

## 先判定保护类型

| 类型 | 运行时表现 | DEX dump 价值 | 路由 |
|------|------------|---------------|------|
| 整体加密 / 类加载型 | 完整标准 DEX 解密后进入内存 | 高 | `dump-dex.ps1` |
| 方法抽取 / 按需回填 | DEX 骨架存在，方法体为空或首次调用时回填 | 只能拿骨架或局部 | FART/dexfix 类方案；当前 active skill 未内置 |
| CompactDex / VDEX / OAT | 目标不一定以标准 DEX 连续存在 | `panda` 覆盖有限 | 专用 ART/OAT/CDEX 工具 |
| VMP | DEX 方法跳入自定义解释器 | DEX 层意义低 | `native-reverse`，分析解释器/调度器 |
| Dex2C / Java2C | 关键方法编译进 `.so` | DEX 只能看到 native 声明 | `native-reverse` / `ida-reverse` |
| Native 壳 / 匿名 RX | `.so` 自解密或代码落入匿名执行段 | 必须先 dump/fix `.so` 或匿名段 | `native-reverse` |

不要用厂商名直接推断代际。同一厂商的免费版、企业版和不同年份可能采用完全不同的组合。

## 轻量识别

先运行：

```powershell
& "C:\Program Files\Git\bin\bash.exe" "D:/reverse_ENV/skill/apk-reverse/scripts/fingerprint.sh" "D:/reverse_ENV/workspace/<project>/app.apk"
```

`fingerprint.sh` 提供框架、DEX 数量、ABI、混淆度和常见保护壳 marker。marker 只是 triage 证据，不是版本或产品等级证明。

继续检查：

- `AndroidManifest.xml` 的 Application 类是否为 Stub/Wrapper。
- APK 中是否只有少量壳类，jadx 业务 Java 文件是否少于 50。
- `lib/**/*.so` 是否包含壳 loader、反调试、完整性或 VM 解释器。
- `assets/` 是否含加密 DEX、sealed DEX、二阶段 payload。
- 目标是否多进程；`pidof <package>` 只覆盖主进程时，要逐进程检查。

如果项目 venv 以后安装了 APKiD，可把它作为补充识别器；当前环境未安装，禁止在任务中自动 `pip install`。

## 本地可用路线

### `dump-dex.ps1`：整体 DEX 内存 dump

入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\apk-reverse\scripts\dump-dex.ps1" `
  -Project <project> -Package <package> -DeviceSerial <serial> -Launch -WaitSeconds 10
```

脚本行为：

1. 校验 ADB、Root、目标 PID、ABI 和 native bridge。
2. 将 `tools\panda-dex-dumper\panda-dex-dumper` 推到独立临时路径。
3. 通过 `/proc/<pid>/mem` 扫描 DEX，并用 `SIGSTOP` / `SIGCONT` 固定窗口。
4. 拉取到 `workspace\<project>\artifacts\dex-dump\<timestamp>\dex\`。
5. 写 `metadata.json`，记录 SHA-256、DEX header、方法/类数量和设备环境。
6. 只有 dumper/pull 成功且至少一个本地 DEX 结构合法时才清理设备 dump；失败或无效结果保留证据。

使用条件：

- 设备必须有 Root 或等价跨 UID 读内存权限。
- LDPlayer 必须能执行 AArch64 dumper；当前 Android 9 x86_64 实例通过 `libnb.so` 已验证。
- 真实 DEX 必须已经解密并保持可读；必要时延长等待、完成首屏交互或逐模块触发 lazy loading。
- 工具没有内置反 Root、反模拟器、反暂停或 anti-dump 绕过。

2026-07-14 本机验证：

- 普通 App：19 个 DEX / 21,134,420 bytes；最大 DEX 生成 2,884 个 Java 文件。
- 起点读书 / 360 Jiagu VIP 线：13 个 DEX / 73,247,772 bytes；最佳 DEX 生成 4,181 个 Java 文件，其中 4,073 个为 `com.qidian`，但存在大量加载和反编译错误，结论为部分脱壳。

### `dex-dump.js`：加载时机观察

`scripts/dex-dump.js` 当前只记录 `DexFile` / `ClassLoader` 路径和 element 数，不读取内存、不写 DEX。它用于判断何时运行 `dump-dex.ps1`，不得作为脱壳后端。

### 多进程与 lazy loading

- 主进程、WebView、push、插件和独立业务进程分别拥有自己的内存映射，按 PID 单独 dump。
- 包名解析到多个 PID 时 wrapper 会拒绝猜测；显式传 `-ProcessId`，且 PID 的 cmdline 必须属于目标包。
- 首屏 dump 不等于完整覆盖。记录触发过的页面、模块和进程。
- 同一 DEX 多次出现时按 SHA-256 去重，不按文件名去重。
- App 被 dump 后退出，先确认是 `SIGSTOP`、`/proc`、Root、模拟器还是工具特征触发，不要连续盲重试。

## 产物验证

`metadata.json` 只证明找到了 DEX 结构，不证明业务代码完整。至少检查：

1. `dex_magic=true`、`header_size=0x70`，实际大小与 header file size 一致。
2. `class_defs` / `method_ids` 是否大于 0。
3. jadx 是否能生成业务包 Java 文件：

```powershell
& "D:\reverse_ENV\tools\jadx.cmd" "-Pdex-input.verify-checksum=no" --no-res -d <jadx-out> <dump.dex>
```

4. 统计业务包类数、空方法/`native` 方法比例、jadx loading/decompile errors。
5. 与静态 APK、不同交互阶段和不同进程的 dump 做 SHA-256 与类集合差异比较。

结果状态：

| 状态 | 判定 |
|------|------|
| `complete-enough` | wrapper 发现的文件均结构合法且工具链退出干净；仍需业务完整性复核 |
| `partial` | 至少一个结构合法 DEX，但存在无效文件、非零退出或拉取异常 |
| `invalid` | 拉到了 `.dex` 文件，但没有任何文件通过结构校验 |
| `no-dex` | 没有 DEX；可能是时机、PID、CDEX/VDEX、VMP 或 anti-dump |

`skeleton-only` 和 `triage-only` 是后续人工分析结论，不是 wrapper 的结构校验状态。

## 失败后的分流

| 现象 | 下一步 |
|------|--------|
| 0 个 DEX | 核对 PID、等待时机、多进程、native bridge、Root、`/proc` 权限 |
| DEX 很多但业务类为 0 | 过滤系统/框架 DEX，检查 lazy loading、壳骨架和假 DEX |
| 类存在但方法体为空 | 方法抽取；转 FART/dexfix 类路线 |
| App 在 dump 时自毁 | 转 `native-reverse`，先做退出 syscall、constructor、匿名 RX 和完整性证据 |
| DEX 只剩 native 声明 | Dex2C/Java2C；转 `.so` 分析 |
| dump 后仍是 VM dispatcher | VMP；转解释器和 opcode 分析，标 L4/triage-only |

## 外部候选

以下项目仅作为方案证据，当前未安装或接入 active skill：

| 项目 | 适合场景 | 边界 |
|------|----------|------|
| `rednaga/APKiD` | 编译器、壳、混淆和 RASP 指纹 | GPL/商业双许可证；当前 venv 未安装 |
| `TheQmaks/clsdumper` | Frida 多策略 DEX/CDEX/OAT dump、反 Frida 初筛 | 需要 Root + frida-server；仍需真实样本验证 ART offset 兼容性 |
| `CodingGay/BlackDex` | Android 5-12 一体化脱壳 | 2023 后维护弱，现代 Android 版本需自行验证 |
| `hanbinglengyue/FART` | 方法抽取、主动调用、CodeItem 重组 | ROM/ART 版本绑定重，不能当通用即插即用工具 |
| `CYRUS-STUDIO/frida_dex_dump` | 活跃 Frida 用户态 DEX dump | 无明确许可证；接入前先审计代码和版本矩阵 |

未经用户确认不得自动安装这些项目，也不得把项目 README 的支持口径当成本机已验证能力。
