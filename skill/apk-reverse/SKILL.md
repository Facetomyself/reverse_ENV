---
name: apk-reverse
description: 在 CLI 环境下做 Android APK 逆向时使用。适用于 APK 解包、Java 反编译、smali 修改、重打包、Frida 动态 Hook，以及按需切换到 so/native 分析。优先使用本机已安装的 jadx、apktool、frida、adb、ida-reverse、radare2。
---

# APK 逆向 CLI 作业规范

## 适用范围

当任务属于以下场景时优先使用本 skill：

- 分析 APK 的 Java 业务逻辑
- 定位登录、签名、风控、证书校验、root 检测
- 查看与修改 `AndroidManifest.xml`
- 查看与修改 smali
- 重打包 APK
- 用 Frida 做 Java/native 动态 Hook
- APK 内含 `.so` 时切到 native 分析
- **APK 快速指纹识别** (框架/混淆度/HTTP栈) — Phase 0
- **Kotlin 类名恢复** (R8 混淆 → 真实类名) — Phase 3.5
- **HTTP API 系统性提取** (Retrofit/OkHttp/Ktor/Apollo/Volley + URL分桶 + HMAC检测)

## 当前机器已验证可用的 CLI 工具

- `jadx` `1.5.5`
- `apktool` `3.0.2`
- `frida-ps` `17.9.6`
- `adb`
- `java`
- **`vineflower` `1.11.2`** (optional — 复杂 Java/lambda/泛型输出质量优于 jadx)
- **`dex2jar` `2.4.31`** (optional — Fernflower/Vineflower 反编译 APK 的前置依赖)

## 优先使用脚本的场景

以下流程高频且参数容易出错，优先用 skill 自带脚本：

- **APK 快速指纹识别**: `scripts/fingerprint.sh` — 框架检测/混淆度/HTTP栈/下一步建议
- 一次性完成 `jadx + apktool` 落盘并产出摘要：`scripts/decode.ps1`
- Frida 设备检查、进程列举、spawn/attach 注入：`scripts/frida-run.ps1`
- 重建、对齐、签名、安装 APK：`scripts/rebuild-sign-install.ps1`
- 快速抽取 Manifest 关键组件与权限：`scripts/manifest-summary.ps1`
- **Kotlin 类名恢复** (R8 混淆 → 真实类名): `scripts/recover-kotlin-names.sh` + `scripts/lookup-name.sh`
- **HTTP API 系统性提取**: `scripts/find-api-calls.sh` — Retrofit/OkHttp/Ktor/Apollo/Volley + URL分桶 + HMAC检测

以下一行命令保持直接调用，不单独封装：

- `adb devices`
- `adb logcat`
- `frida-ps -U`
- `jadx --version`
- `apktool --version`

## 自带脚本

### `scripts/fingerprint.sh` — Phase 0 快速指纹

在反编译之前做快速 triage，避免在 Flutter/RN/Cordova/Xamarin 应用上浪费时间反编译 Java。

```bash
bash D:/reverse_ENV/skill/apk-reverse/scripts/fingerprint.sh <file.apk|file.xapk>
```

输出（一屏内）：
- **移动框架** (Flutter / React Native / Cordova / Xamarin / Native Kotlin/Compose)
- **HTTP 栈** (Retrofit / OkHttp / Ktor / Apollo / Volley) — 通过 DEX 字符串扫描
- **DI/序列化** (Hilt / Dagger / Koin / kotlinx.serialization / Moshi / Gson)
- **混淆度** (LOW/MODERATE/HIGH — 基于根级短名包数量)
- **第三方 SDK** (AppsFlyer / Datadog / Sentry / Firebase / Stripe 等)
- **Native libraries** (合并所有 split APK 的 `.so` 列表)
- **推荐下一步** — Flutter 建议 blutter/strings；RN 建议 hbctool；Cordova 建议直接解压；Native 建议继续反编译

### `scripts/recover-kotlin-names.sh` — Phase 3.5 R8 混淆类名恢复

从 Kotlin metadata 注解 (`@DebugMetadata`, `@Metadata.d2`) 中挖掘被 R8 混淆前的原始类名。

```bash
# 构建 obf -> real 映射
bash D:/reverse_ENV/skill/apk-reverse/scripts/recover-kotlin-names.sh output/sources/ output/mapping/

# 产出:
#   output/mapping/mapping.tsv    obf_fqn <TAB> real_fqn <TAB> file
#   output/mapping/mapping.json   { obf_fqn: real_fqn, ... }
#   output/mapping/by_package/    按真实包名索引
```

典型恢复率：~100% 的 `*Repository` / `*ViewModel` / `*UseCase` / `*Impl`，~80% 的 DTO。

### `scripts/lookup-name.sh` — 查询类名映射

```bash
# 按真实类名搜索
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh output/mapping/ LoginRepository

# 混淆 -> 真实
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh output/mapping/ -o a.b.c

# 按包名列出
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh output/mapping/ -p com.example.feature

# 在源码中 grep 并标注真实类名
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh output/mapping/ --grep '/api/' output/sources/
```

### `scripts/find-api-calls.sh` — Phase 5 HTTP API 系统性提取

7 种 HTTP 库全覆盖 + URL 去噪分桶 + HMAC 签名检测。

```bash
# 全扫描
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/

# 定向扫描
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --retrofit
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --ktor
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --apollo
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --urls     # 去噪 + 分桶
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --paths    # 混淆后仍可提取的路径字面量
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/ --auth     # Bearer/HMAC/API Key
```

`--urls` 模式通过 `third_party_hosts.txt` (120+ 域名) 自动将 URL 分为 first-party 和 third-party，按频次排序输出。

### `scripts/decode.ps1`

用途：

- 统一跑 `jadx` 和 `apktool`
- 默认在原 APK 同目录创建任务输出目录
- 输出 `package`、`java_files`、`smali_dirs`、`so_files` 等摘要
- 兼容 `jadx` 部分反编译错误但仍然有可用产物的情况

示例：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\decode.ps1" -ApkPath "D:\DOWNLOAD\app.apk" -Clean
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\decode.ps1" -ApkPath "D:\DOWNLOAD\app.apk" -Name demo -SkipJadx
```

### `scripts/frida-run.ps1`

用途：

- 统一 Frida 的设备、进程、spawn/attach 入口
- 避免手写参数时混淆 `-f`、`-n`、`-U`

示例：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\frida-run.ps1" -ListDevices
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\frida-run.ps1" -Usb -ListProcesses
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\frida-run.ps1" -Usb -Spawn -Package com.example.app -ScriptPath "D:\hooks\test.js"
```

### `scripts/rebuild-sign-install.ps1`

用途：

- `apktool b` 重建 APK
- `zipalign` 对齐
- `apksigner` 签名与验签
- 可选直接 `adb install`

示例：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "C:\work\apktool_out" -Clean
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "C:\work\apktool_out" -Install -Reinstall -DeviceSerial "127.0.0.1:7555"
```

说明：

- 默认生成并复用调试 keystore
- 默认输出到 `ProjectDir` 同目录，便于和原始包、解包目录放在一起

### `scripts/manifest-summary.ps1`

用途：

- 抽取包名
- 列权限
- 列 activity/service/receiver/provider
- 标出主启动 activity

示例：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\manifest-summary.ps1" -ManifestPath "C:\work\apktool_out\AndroidManifest.xml"
```

如果要分析 `.so`、`lib/arm64-v8a/*.so`、`lib/armeabi-v7a/*.so`，再结合：

- `ida-reverse`
- `radare2`

## 工具分工

### `jadx`

用于：

- Java 反编译阅读
- 包名、类名、方法名搜索
- 先从高层逻辑理解 APK

常用命令：

```bash
jadx -d jadx_out app.apk
jadx --single-class com.example.LoginActivity -d jadx_out app.apk
jadx --deobf -d jadx_out app.apk
```

### `apktool`

用于：

- 解包 APK
- 查看和修改 `AndroidManifest.xml`
- 查看和修改 smali
- 重建 APK

常用命令：

```bash
apktool d app.apk -o apktool_out
apktool b apktool_out -o rebuilt.apk
```

### `frida`

用于：

- 动态观察 Java 方法调用
- Hook native 导出函数
- 绕过 root 检测、证书校验、调试检测

常用命令：

```bash
frida-ps -U
frida -U -f com.example.app -l hook.js
frida-trace -U -f com.example.app -j '*!*certificate*'
```

### `adb`

用于：

- 设备连接
- 安装 APK
- 查看日志
- 拉取文件

常用命令：

```bash
adb devices
adb install -r app.apk
adb shell pm list packages
adb logcat
adb pull /data/local/tmp/file .
```

## 推荐工作流

### 0. Phase 0 — 快速指纹 (必须第一步)

**在反编译之前跑 `fingerprint.sh`，确定 APK 类型和下一步方向。**

```bash
bash D:/reverse_ENV/skill/apk-reverse/scripts/fingerprint.sh app.apk
```

根据输出决定：
- **Flutter** → 停止。Dart 代码在 `libapp.so` 中，用 blutter / reFlutter / `strings libapp.so`
- **React Native** → 停止。JS 代码在 `assets/index.android.bundle`，用 hbctool (Hermes) 或直接 grep
- **Cordova/Capacitor** → 停止。代码在 `assets/www/`，直接解压看 HTML/JS
- **Xamarin/.NET MAUI** → 停止。代码在 `assemblies/` (.NET DLL)，用 ILSpy/dotPeek
- **Native Android (Java/Kotlin)** → 继续 Phase 1

### 1. Triage

先确定 APK 大致构成，不急着改包或 Hook。

建议动作：

1. 用 `jadx -d jadx_out app.apk` 导出 Java 代码
2. 用 `apktool d app.apk -o apktool_out` 导出 smali 和资源
3. 先看：
   - `AndroidManifest.xml`
   - 主 `package`
   - `application`、`activity`、`service`、`receiver`
   - `lib/` 目录里是否有 `.so`
   - **所有 `BuildConfig.java`** — 几乎不被混淆，常泄露 base URL、API key、feature flag

### 2. Java 逻辑观察

优先从 `jadx_out` 读：

- `MainActivity`
- `Application`
- 登录、网络、加密、风控相关类
- 第三方 SDK 初始化类

常见关键词：

- `login`
- `sign`
- `encrypt`
- `cipher`
- `token`
- `root`
- `certificate`
- `trust`
- `okhttp`
- `retrofit`
- `webview`

如果 Java 代码可读，先在这里定位业务逻辑。

### 2.5 Phase 3.5 — Kotlin 类名恢复 (混淆 Kotlin 应用必做)

如果 Phase 0 报告混淆度为 MODERATE/HIGH 且应用为 Kotlin/Compose：

```bash
# 构建映射
bash D:/reverse_ENV/skill/apk-reverse/scripts/recover-kotlin-names.sh output/sources/ output/mapping/

# 用 lookup 替代 plain grep
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh output/mapping/ --grep '"/api/' output/sources/
```

典型恢复 ~100% 的 `*Repository` / `*ViewModel` / `*Impl`。详见 `references/kotlin-name-recovery.md`。

### 3. Smali 与资源层确认

当 `jadx` 结果不完整、混淆重、或需要实际 patch 时，切到 `apktool_out`：

- 看 `smali*/`
- 看 `res/values/strings.xml`
- 看 `AndroidManifest.xml`

优先 patch：

- `android:exported`
- 调试标记
- root 检测返回值
- 登录验证逻辑
- 证书校验分支

### 4. 重建与安装

修改后：

```bash
apktool b apktool_out -o rebuilt.apk
```

或者直接用脚本闭环：

```powershell
powershell -File "D:\reverse_ENV\skill\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "apktool_out" -Install -Reinstall -DeviceSerial "127.0.0.1:7555"
```

说明：

- 本 skill 只保证 `apktool` 重建链路
- 若后续需要正式安装到设备，通常还需要签名流程
- 如果任务进入签名/对齐，补充 `apksigner` / `zipalign`

### 5. 动态 Hook

静态分析不足时，用 Frida：

- Hook 登录函数
- Hook `OkHttp` / `Retrofit` / `WebView` 关键点
- Hook `javax.crypto`、`MessageDigest`
- Hook root 检测函数
- Hook SSL pinning 逻辑

原则：

- 先 Hook Java 层，再看是否需要 native Hook
- 先打印参数与返回值，再决定是否主动修改返回值

建议：

- 简单一次性命令直接用 `frida-*`
- 需要稳定复用的注入流程优先走 `scripts/frida-run.ps1`

### 5.5 Phase 5 — API 系统性提取

```bash
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh output/sources/
```

产出 Tier 1（全量端点表）+ Tier 2（auth/payment 等重点端点深度文档）。详见 `references/api-extraction-patterns.md` 和 `references/call-flow-analysis.md`。

### 6. Native `.so` 分流

如果 APK 中包含关键 `.so`：

- 用 `apktool` 或 `jadx` 找到 `lib/**/*.so`
- 若只是导出符号、字符串、快速 triage，可用 `radare2`
- 若要长期深入分析、反编译、改名、类型恢复，用 `ida-reverse`

遇到这些信号要尽快切 native：

- Java 层只是 JNI 包装
- 核心签名逻辑不在 Java
- `System.loadLibrary()` 后关键逻辑消失
- 证书校验/风控在 `.so` 中

## 输出要求

最终至少说明：

- 入口组件与关键类
- 关键逻辑在 Java、smali 还是 `.so`
- 已确认的敏感点：登录、签名、root、SSL、WebView、JNI
- 如果做了 patch，说明改了什么
- 如果做了 Hook，说明 Hook 了哪个类/方法/导出函数
- **如果做了 API 提取**：Tier 1 全量表 (Host/Method/Path/Auth/Source) + 重点端点 Tier 2 详情
- **如果做了类名恢复**：恢复率统计 + mapping 文件路径

## 参考文档

| 文档 | 内容 |
|------|------|
| `references/api-extraction-patterns.md` | Retrofit/OkHttp/Ktor/Apollo/Volley grep 模式库 + 端点文档模板 (Tier1/Tier2) |
| `references/call-flow-analysis.md` | Activity→ViewModel→Repository→HTTP 调用链追踪技术 + 混淆对抗策略 |
| `references/kotlin-name-recovery.md` | R8/Kotlin metadata 类名恢复原理 + 局限性 + 阅读流 |
| `references/third_party_hosts.txt` | URL 分桶用第三方域名 denylist (120+ 域名: Firebase/AppsFlyer/Stripe/...)

## 渐进式披露阶段

本 skill 的工作流已按 `reverse-coordinator` 的四个深度等级对齐：

| 阶段 | 深度 | 对应本 skill 步骤 | 产出 |
|------|------|-------------------|------|
| 分类 | L0 | 步骤 0 Phase 0 指纹 | 框架识别、混淆度、HTTP栈、下一步建议 |
| 侦察 | L1 | 步骤 1-2 Triage + Java 观察 | manifest 摘要、package、so 列表、关键类/方法 |
| 决策 | — | 步骤 3 判断主战场 | 确定为 Java/smali/native 主线 |
| 深挖 | L2-L3 | 步骤 2.5-5 | 类名恢复映射、smali patch、Frida Hook、API 提取、native 分流 |
| 产出 | — | 步骤 5.5 Phase 5 + 步骤 6 | 报告 + Hook 脚本 + API 端点表 (Tier1/Tier2) |

> 遵循 `reverse-coordinator` 约定：不得跳过 L0 分类直接做 L3 深挖。

## 禁止事项

- 不要一开始就盲目改 smali
- 不要在没看 manifest 和主入口前就写 Hook
- 不要把 Java 反编译不完整直接等同于”逻辑不可分析”
- 不要在 `.so` 明显承载核心逻辑时继续死磕 Java 层

## 快速命令备忘

```bash
# === Phase 0: 指纹 ===
bash D:/reverse_ENV/skill/apk-reverse/scripts/fingerprint.sh app.apk

# === 反编译 Java ===
jadx -d jadx_out app.apk

# === 解包 APK ===
apktool d app.apk -o apktool_out

# === 重建 APK ===
apktool b apktool_out -o rebuilt.apk

# === Phase 3.5: Kotlin 类名恢复 ===
bash D:/reverse_ENV/skill/apk-reverse/scripts/recover-kotlin-names.sh jadx_out/sources/ jadx_out/mapping/
bash D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh jadx_out/mapping/ --grep '/api/' jadx_out/sources/

# === Phase 5: API 提取 ===
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh jadx_out/sources/        # 全扫描
bash D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh jadx_out/sources/ --urls # URL分桶

# === Fernflower/Vineflower (高级) ===
# APK → dex2jar → Fernflower (对复杂 lambda/泛型输出质量更优)
java -jar D:/reverse_ENV/tools/dex2jar/dex-tools-2.4.31/lib/dex-tools-2.4.31.jar -f -o app.jar app.apk
java -jar D:/reverse_ENV/tools/vineflower/vineflower-1.11.2.jar -dgs=1 -mpm=60 app.jar vineflower_out/

# === 设备与进程 ===
adb devices
frida-ps -U

# === 启动并注入 ===
frida -U -f com.example.app -l hook.js
```
