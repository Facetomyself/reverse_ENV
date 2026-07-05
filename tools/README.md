# 便携工具链

所有 CLI 工具安装在 `tools/` 下，不依赖系统 PATH。MCP 服务源码已迁移至 `mcp/`。

## 工具清单

| 工具 | 版本 | 路径 | 用途 |
|------|------|------|------|
| jadx | 1.5.5 | `jadx\bin\jadx.bat` | APK/Java 反编译 |
| apktool | 3.0.2 | `apktool\apktool.bat` | APK 解包/重打包 |
| JDK | 21 | `jdk\` | Java 运行时 |
| radare2 | 6.1.8 | `radare2\bin\radare2.exe` | 通用二进制快速分析 |
| Node.js | 20.20.2 | `node\node.exe` | JS 运行时（MCP 服务） |
| adb | 1.0.41 | `adb\adb.exe` | Android 调试桥 |
| zipalign | — | `adb\zipalign.exe` | APK 对齐 |
| apksigner | 0.9 | `adb\apksigner.bat` | APK 签名 |
| Android NDK | r29 | `android-ndk\` | C/C++ 交叉编译 |
| MinGW-w64 | 14.2.0 | `mingw64\mingw64\bin\gcc.exe` | Windows C 编译 |
| QuickJS | — | `quickjs\qjs_min.exe` | 轻量 JS 引擎 |
| LDPlayer | 9 | `ldplayer\ldplayer.ps1` | 雷电模拟器管控 |
| Chromium | 152 | `chromium\chrome-win\chrome.exe` | 备用浏览器 |
| Vineflower | 1.11.2 | `vineflower\vineflower-1.11.2.jar` | Java 反编译备选引擎 |
| dex2jar | 2.4.31 | `dex2jar\dex-tools-2.4.31\` | DEX→JAR 转换 |
| First | — | `First\` | 微信小程序调试 |
| Frida gadget | 17.15.3 | `frida-gadget-*.so` | Frida gadget 注入库 |
| frida-server | — | `frida-server\` | Android frida-server 二进制 |
| hide-soinfo | — | `hide-soinfo\` | 内存隐藏 C 库 |
| stealth-hook-engine | — | `stealth-hook-engine\` | 隐身 Hook 引擎 |
| protocol-recovery | — | `protocol-recovery\` | 协议恢复 CLI 工具 |
| gh | — | `gh\` | GitHub CLI |
| go | — | `go\` | Go 工具链 |

## 约束

- **所有工具不依赖系统 PATH**，通过绝对路径调用
- 大文件不纳入 Git（`jadx/`, `jdk/`, `node/`, `android-ndk/`, `mingw64/`, `chromium/` 等已在 `.gitignore`）
- 新增工具后同步更新本 README + `CLAUDE.md` 工具速查表 + `docs/工具与环境.md`
- MCP 服务源码不放在此目录，统一在 `mcp/` 下
