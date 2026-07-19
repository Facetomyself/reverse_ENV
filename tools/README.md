# 便携工具链

所有 CLI 工具安装在 `tools/` 下，不依赖系统 PATH。MCP 服务源码已迁移至 `mcp/`。

## 工具清单

| 工具 | 版本 | 路径 | 用途 |
|------|------|------|------|
| jadx | 1.5.5 | `jadx\bin\jadx.bat` | APK/Java 反编译 |
| apktool | 3.0.2 | `apktool\apktool.bat` | APK 解包/重打包 |
| JDK | 21 | `jdk\` | Java 运行时 |
| radare2 | 6.1.8 | `radare2\bin\radare2.exe` | 通用二进制快速分析 |
| Node.js | 20.20.2 | `node\node.exe` | 现有 MCP 主运行时 |
| Node.js | 22.23.1 | `node22\node.exe` | DBX MCP 隔离运行时（ABI 127） |
| .NET SDK | 10.0.302 | `dotnet\dotnet.exe` | C# 工具 portable runtime，不依赖系统安装 |
| adb | 1.0.41 | `adb\adb.exe` | Android 调试桥 |
| zipalign | — | `adb\zipalign.exe` | APK 对齐 |
| apksigner | 0.9 | `adb\apksigner.bat` | APK 签名 |
| Android NDK | r29 | `android-ndk\` | C/C++ 交叉编译 |
| panda-dex-dumper | 1.0.0 | `panda-dex-dumper\panda-dex-dumper` | P4nda0s AArch64 whole-DEX 内存 dump；LDPlayer x86_64 + `libnb.so` 路线已验证，详见 [README](panda-dex-dumper/README.md) |
| MinGW-w64 | 14.2.0 | `mingw64\mingw64\bin\gcc.exe` | Windows C 编译 |
| QuickJS | — | `quickjs\qjs_min.exe` | 轻量 JS 引擎 |
| LDPlayer | 9 | `ldplayer\ldplayer.ps1` | 雷电模拟器管控 |
| Android modules | — | `android-modules\` | LDPlayer 模板用 Kitsune/LSPosed/JustTrustMe/HMA/Shamiko 资产清单 |
| Chromium | 152 | `chromium\chrome-win\chrome.exe` | 备用浏览器 |
| Vineflower | 1.11.2 | `vineflower\vineflower-1.11.2.jar` | Java 反编译备选引擎 |
| dex2jar | 2.4.31 | `dex2jar\dex-tools-2.4.31\` | DEX→JAR 转换 |
| First | — | `First\` | 微信小程序调试 |
| Gwxapkg | 2.7.4 | `Gwxapkg\` + `Gwxapkg-runtime\gwxapkg.exe` | 微信小程序/小游戏 wxapkg 解密、解包、还原与 repack；源码为 Public submodule，运行产物忽略 |
| Frida gadget | 17.15.3 | `frida-gadget-*.so` | Frida gadget 注入库 |
| frida-server | — | `frida-server` | Android frida-server 单文件二进制 |
| hide-soinfo | — | `hide-soinfo\` | 内存隐藏 C 库 |
| stealth-hook-engine | — | `stealth-hook-engine\` | 隐身 Hook 引擎 |
| protocol-recovery | — | `protocol-recovery\` | 协议恢复 CLI 工具 |
| web-env | — | `web-env\` | Web JS Node 补环境隔离检查与 xbs 纯 JS 检查器封装 |
| ruyipage Firefox runtime | 151-proxy | `ruyipage\runtimes\151-proxy\firefox\firefox.exe` | ruyiPage 1.2.54 / ruyi-mcp 0.1.5 项目 BiDi runtime |
| ruyiTrace | v1.2 | `ruyitrace\ruyitrace.ps1` | C++ DOMTrace NDJSON 采集；使用独立 Firefox trace kernel |
| gh | — | `gh\` | GitHub CLI |
| go | — | `go\` | Go 工具链 |
| workspace-governance | — | `workspace-governance\audit_workspace.py` | Workspace registry、remote、submodule 与 Git 禁入文件只读审计 |
| EPL Source Recovery | 1.9.4-safe.1 | `epl-source-recovery\run.ps1` | 易语言 `*.e` / `*.ec` 纯静态源码恢复；含固定版 EProjectFile 与只读精易模块源码资产 |

## 约束

- **所有工具不依赖系统 PATH**，通过绝对路径调用
- **补环境 runtime 隔离**：`tools\node\node.exe` 是项目主 Node，不得为 addon / isolated-vm 切换或覆盖；`tools\node22\node.exe` 仅供 DBX MCP；Node 25/26、xbs addon、TLS 指纹客户端只能放 `tools\web-env\runtimes\` 或 `workspace\<项目名>\.runtime\`
- **ruyipage runtime 隔离**：浏览器二进制放入 `tools\ruyipage\runtimes\` 并排除 Git；`tools\ruyitrace\firefox\` 继续作为 DOMTrace 专用 runtime，不得被普通 BiDi runtime 覆盖
- 大文件不纳入 Git（`jadx/`, `jdk/`, `node/`, `node22/`, `dotnet/`, `android-ndk/`, `mingw64/`, `chromium/` 等已在 `.gitignore`）
- 新增工具后同步更新本 README + `CLAUDE.md` 工具速查表 + `docs/工具与环境.md`
- MCP 服务源码不放在此目录，统一在 `mcp/` 下
- Gwxapkg 构建：`powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\tools\build-gwxapkg.ps1"`
- EPL 子模块初始化：`git -C "D:\reverse_ENV" submodule update --init "tools/epl-source-recovery/upstream/EProjectFile" "tools/epl-source-recovery/assets/jingyi-ec"`
