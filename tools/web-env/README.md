# web-env 工具封装

`tools\web-env` 是网页端 Node 补环境的项目级隔离封装层。它可以调用 `storage\xbsReverseSkill\web-js-env-patcher` 中的参考脚本，但不会把外部 skill 直接安装为项目 skill，也不会替换项目主 Node。

## 硬规则

- 项目主 Node 固定为 `D:\reverse_ENV\tools\node\node.exe`，只服务 MCP 和默认 JS 工具链，不得为了补环境 addon 替换。
- 需要 Node 25/26、native addon、魔改 isolated-vm、TLS 指纹客户端时，放入 `D:\reverse_ENV\tools\web-env\runtimes\` 或 `D:\reverse_ENV\workspace\<项目名>\.runtime\`。
- 本目录脚本只做检测、封装和显式调用；不自动安装 npm/pip 依赖，不写系统 PATH，不写用户级环境变量。
- `storage\xbsReverseSkill` 属于可复用外部参考仓库，默认不纳入 Git；复制其实现代码到本仓库前必须保留 MIT 来源说明并完成路径隔离改造。

## 脚本

| 脚本 | 用途 |
|---|---|
| `check-isolation.ps1` | 检查主 Node、RuyiTrace、xbs clone、addon / isolated-vm ABI 是否匹配，输出 Markdown 或 JSON。 |
| `invoke-xbs-script.ps1` | 用绝对路径调用 xbs `web-js-env-patcher/scripts` 下的纯 JS 检查器，并临时注入 `RUYI_TRACE_HOME`。 |

## 示例

```powershell
powershell -File "D:\reverse_ENV\tools\web-env\check-isolation.ps1"
powershell -File "D:\reverse_ENV\tools\web-env\check-isolation.ps1" -Json
powershell -File "D:\reverse_ENV\tools\web-env\invoke-xbs-script.ps1" -Script "check_tls_clients.js" -ScriptArgs "--markdown"
powershell -File "D:\reverse_ENV\tools\web-env\invoke-xbs-script.ps1" -Script "parse_curl.js" -ScriptArgs "--input", "D:\reverse_ENV\workspace\demo\captures\request.curl", "--markdown"
```

## 当前已知状态

- `xbsReverseSkill` 的 `addon.node` 预编译 ABI 需要 Node 25.x，不能直接在当前 Node 20.20.2 主链路使用。
- `xbs-isolated-vm` 预编译 ABI 需要 Node 26.x，不能直接在当前 Node 20.20.2 主链路使用。
- 因此默认只调用纯 JS 检查器；native 能力必须显式走隔离 runtime，并先运行 `check-isolation.ps1`。
