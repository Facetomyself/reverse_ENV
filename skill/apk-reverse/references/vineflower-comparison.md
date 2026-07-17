# Vineflower 对照反编译

Vineflower 是补充证据，不替代 jadx/apktool 主链。只在下面两类场景使用：

- 输入是 JAR、AAR 或单个 CLASS，jadx/apktool 不适合作为主入口；
- jadx 对关键类出现 malformed control flow、lambda/generic 还原异常或明显的 `JADX WARNING`，需要第二视角复核。

## 调用

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\vineflower-decompile.ps1" `
  -InputPath "D:\reverse_ENV\workspace\<project>\input.jar" `
  -OutputDir "D:\reverse_ENV\workspace\<project>\vineflower" -Clean
```

支持 APK、DEX、JAR、AAR、CLASS。APK/DEX 先经项目固定版本 dex2jar 转换；AAR 只提取并反编译 `classes.jar` 与 `libs/*.jar`。

## 解释边界

- APK/DEX 的 Vineflower 输出只用于关键方法对照；Android resources、smali、运行时类名和重建仍以 apktool/jadx 为准。
- 默认不启用成员重命名，避免静态可读名与 Frida/JNI/runtime 名字脱节。只有纯静态阅读时才考虑 `-RenameMembers`。
- Java/Kotlin 文件数量只能说明产物存在，不能证明控制流、异常边、泛型或 Kotlin 语义完全恢复。
- `vineflower-summary.json` 记录输入 SHA-256、工具路径、阶段退出码、产物数量与限制；结论引用具体类/方法时同时保留 jadx 对照。

## 不采用的做法

- 不自动下载或安装 JDK、Vineflower、dex2jar；只使用 `D:\reverse_ENV\tools\` 下的固定版本。
- 不把 AAR 整体丢给 dex2jar；AAR 是 ZIP 容器，应直接处理内部 JAR。
- 不使用已废弃的 Vineflower `-mpm` 参数，也不假设输出一定是可再次解压的 JAR。
