# RuyiPage 上游更新与 ruyi-mcp 兼容审计

审计日期：2026-07-14

## 执行结论

结论为：**建议更新，但必须拆成 Python 包、MCP 适配和 Firefox runtime 三层处理，不能直接在运行环境中原地升级。**

| 层级 | 结论 | 优先级 |
|------|------|--------|
| `ruyiPage` Python 包 `1.2.43 -> 1.2.46` | 建议受控升级；现有公开 API 保持兼容，代理 URL 认证修复直接命中 MCP 主链 | 高 |
| `ruyi-mcp` Bridge | 无上游 breaking change，但审计发现屏幕方向参数和 Trace 语义两个既有缺陷，应随升级一起修 | 高 |
| Firefox `151-proxy` runtime | 只能 side-by-side 验证，禁止覆盖当前 `tools\ruyitrace\firefox` | 高 |
| Prompt MCP tools | 上游已新增 `page.prompts`，当前 MCP 未暴露；属于可选能力扩展 | 低 |

当前运行中的 MCP、Python Bridge 和 Firefox 路径均未改动。

## 本地基线

| 项 | 当前值 |
|----|--------|
| `ruyi-mcp` 子仓 | `Facetomyself/ruyi-mcp`，当前 HEAD `1919c27` |
| Python 依赖 | `ruyiPage==1.2.43` |
| Python | `3.13.12` |
| Node.js | `20.20.2` |
| MCP Firefox 配置 | `D:\reverse_ENV\tools\ruyitrace\firefox\firefox.exe` |
| 项目 Trace Firefox BuildID | `20260504215819` |
| RuyiPage managed cache BuildID | `20260530120704`，release `151-ruyi` |

项目 Trace Firefox 的 `xul.dll` 可见 `MOZ_DOM_TRACE` 和 `httpauth.username`，但未发现 `socksauth.username` / `proxy.rotate.proxy`。本机 managed `151-ruyi` runtime 可见 `MOZ_DOM_TRACE`、`httpauth.username`、`socksauth.username` 和 `proxy.rotate.proxy`。这说明 Python 包与 Firefox 内核能力不能只看同一个 `151.0a1` 版本号，必须按 BuildID 和实际能力验证。

## 检索与取证路径

### 搜索路径

- `search-layer` status/deep：检索近期 release、版本和 Issue/PR 线索。
- `gh repo/release/api/issue/pr/run/search code`：直接核验仓库元数据、release、commit compare、Issue、PR、workflow 和源文件。
- PyPI wheel：下载但不安装 `ruyiPage 1.2.46`，与本机 `1.2.43` 做 API 和 proxy runtime 文件行为对照。
- GitHub release asset：校验 `151-proxy` SHA256、BuildID 和归档内容；临时文件已清理。

### 并行审计

| 子任务 | 覆盖面 | 关键结果 |
|--------|--------|----------|
| release/code audit | release、tag、commit compare、runtime manifest | Python 仅前进 3 commits；installer 仍指向旧 `151-ruyi` |
| Issue/PR audit | 全量 Issue、PR、CI、维护者回复 | 无 PR；#19/#20 未修；CI 因缺 `greenlet` 全红 |
| local compatibility audit | Bridge API、Trace、Firefox marker、测试覆盖 | 上游 API 兼容；发现 orientation 和 Trace 既有缺陷 |

## 上游项目概况

| 项 | 状态 |
|----|------|
| 仓库 | [LoseNine/ruyipage](https://github.com/LoseNine/ruyipage) |
| Stars / Forks | 1644 / 200（审计时） |
| License | BSD-3-Clause |
| 主语言 | Python |
| 最近 push | 2026-07-12 |
| PR | 历史总数 0；修复均由维护者直接 push |
| Discussions | 未启用 |

Python 包的 semver tag 停留在 `v1.2.37`；`1.2.44` 到 `1.2.46` 只发布到 PyPI，没有对应 GitHub version tag/release。GitHub 最新 release `151-proxy` 是 Firefox binary release，不等于 Python package release。

## 1.2.43 到 1.2.46 的精确变化

完整 compare：<https://github.com/LoseNine/ruyipage/compare/20dbcad2eb4bd7baa1cbf98fe01accb8beb7e8ee...7f23562ae71560e18c5c402ae6232d0886af8474>

| 版本 | Commit | 变化 | 对当前 MCP 的影响 |
|------|--------|------|--------------------|
| 1.2.44 | [`cda3395e`](https://github.com/LoseNine/ruyipage/commit/cda3395e064424510fbc5cf5a955ff236d390543) | 新增 `page.prompts` manager；prompt action 非 `accept/dismiss/ignore` 时抛 `ValueError` | 当前 MCP 未暴露 prompt，现有调用不受影响；可选新增工具 |
| 1.2.45 | [`57f705a0`](https://github.com/LoseNine/ruyipage/commit/57f705a0e574f7167fbf11f1ce5cdf9609930c85) | 规范化 iframe URL 的默认 `:80/:443` 端口 | 当前 MCP 主要通过 `contextId` 调用 `get_frame()`，收益有限 |
| 1.2.46 | [`7f23562a`](https://github.com/LoseNine/ruyipage/commit/7f23562ae71560e18c5c402ae6232d0886af8474) | 从 HTTP/SOCKS proxy URL 提取并 percent-decode 用户名密码，生成 `httpauth` / `socksauth` runtime fpfile | 直接命中 `ruyi_new_page(proxy=...) -> opts.set_proxy()`，是本次升级的主要理由 |

未发现被删除、重命名或改签名的 MCP 已调用公开 API。把 `1.2.46` wheel 临时置于 `sys.path` 后，当前 Bridge 可正常 import，52 个 Python handler 可注册，使用 FakePage 的 launch contract 也可完成。

## 代理修复的本地实证

使用同一组测试 URL：

- `http://user:pa%24%24@proxy.example.com:1000`
- `socks5://user:pa%24%24@proxy.example.com:1000`

结果：

| 版本 | HTTP URL auth | SOCKS5 URL auth |
|------|---------------|-----------------|
| 本机 1.2.43 | 不生成 runtime fpfile，credentials 为 `None` | 不生成 runtime fpfile，credentials 为 `None` |
| 解压态 1.2.46 | 生成 `httpauth.username/password`，密码正确解码为 `pa$$` | 生成 `socksauth.username/password`，密码正确解码为 `pa$$` |

项目的 `proxy-usage` 工作流明确使用 `http://user:pass@host:port`，因此 1.2.46 不是无关紧要的功能更新。

## Firefox binary release

最新 binary release：[`151-proxy`](https://github.com/LoseNine/ruyipage/releases/tag/151-proxy)

| 项 | 值 |
|----|----|
| 发布日期 | 2026-07-12 |
| Release body | `修复了代理bug` |
| Windows asset | `firefox-151.0a1.en-US.win64.zip` |
| SHA256 | `f82151f9f197b528b36fb461cf106bc6825c0f752efb5c5d762c34f7529055f6` |
| BuildID | `20260702113527` |
| Linux asset | 无对应 `151-proxy` 更新 |

关键问题：[`ruyipage/_runtime/manifest.py`](https://github.com/LoseNine/ruyipage/blob/7f23562ae71560e18c5c402ae6232d0886af8474/ruyipage/_runtime/manifest.py) 在 `1.2.46` 中仍固定 `RELEASE_TAG = "151-ruyi"`。因此：

- `pip install -U ruyiPage` 不会更新 Firefox binary。
- `python -m ruyipage install` 仍会下载旧 `151-ruyi`，不会取得 `151-proxy`。
- `151-proxy` 必须单独下载并放到隔离目录验证。

`151-proxy` 归档没有当前 `ruyitrace.ps1` 强制检查的 `RUYI_DOMTRACE.txt` marker。即便二进制仍包含 `MOZ_DOM_TRACE` 字符串，也不能直接覆盖当前目录，否则现有 CLI 会立即拒绝启动。正确做法是 side-by-side 部署并分别验证普通 MCP、BiDi Trace 和 DOMTrace。

## Issue、PR 与 CI

| 证据 | 状态 | 本地适用性 |
|------|------|------------|
| [Issue #17](https://github.com/LoseNine/ruyipage/issues/17) | 仍为 Open，但维护者称新版已修；对应 1.2.45 commit | 低到中；当前 MCP 不按 locator URL 选 Frame |
| [Issue #19](https://github.com/LoseNine/ruyipage/issues/19) | Firefox 128 下 BiDi 对象序列化截断；维护者仅表示尝试修复 | 默认 Firefox 151 不受影响；自定义 `browserPath` 指向 Firefox 128 时有风险 |
| [Issue #20](https://github.com/LoseNine/ruyipage/issues/20) | 1/22 fpfile 自动最大化导致坐标偏移；暂无维护者回复 | 高；直接命中 `smart_fingerprint` 与 human move/click，1.2.46 未修 |
| PR | 无任何 PR | 没有独立 review 证据 |
| [1.2.46 CI](https://github.com/LoseNine/ruyipage/actions/runs/29102043186) | Python 3.9-3.13 全失败 | 测试在收集 `async_smoke` 时因缺少 optional `greenlet` 失败，后续 browser/feature/release gate 未运行 |

1.2.43 对应 CI 也因同一配置问题失败，因此 CI 红灯不是 1.2.46 新回归；但上游目前也没有一条完整绿灯证明最新版通过浏览器回归。

## ruyi-mcp 本地兼容矩阵

| MCP 面 | 结论 | 建议 |
|--------|------|------|
| `FirefoxPage` / `FirefoxOptions` import 与构造 | 1.2.46 兼容 | 无需为升级改接口 |
| `set_proxy(proxyUrl)` | 1.2.46 明确修复 credentialed URL | 升级并补 HTTP/SOCKS contract tests |
| `get_all_frames()` / `get_frame(context_id=...)` | 签名兼容；1.2.45 locator 修复不是主路径 | 保持现实现 |
| prompt | 新增能力，当前未使用 | 后续可新增 accept/dismiss/input/wait tools，不与依赖升级绑死 |
| fingerprint / human actions | 上游 diff 未改核心 fingerprint，但 #20 未修 | 增加 viewport、element rect、click point 回归 |
| Trace | 本次上游无变化，但当前 MCP 的 runtime start/stop 语义不准确 | 升级时一并修复并增加 entries 增长/停止断言 |
| screen orientation | Bridge 使用错误关键字 `orientation=`，实际签名一直是 `orientation_type` | 必须修复，属于既有缺陷 |

### 本地发现的既有缺陷

1. `bridge/ruyi_bridge.py` 调用：

   ```python
   page.set_screen_orientation(orientation=..., angle=...)
   ```

   上游实际签名为：

   ```python
   set_screen_orientation(self, orientation_type, angle=0)
   ```

   当前路径一旦触发就会因未知关键字失败，与 1.2.46 无关。

2. `trace.start` 在浏览器已经启动后只调用 `self.opts.enable_trace(True)`。该方法只修改 options，不能为已经构造的 Driver 补建 Tracer；返回的 `partialTrace: true` 容易造成“已开始记录”的假象。

3. `trace.stop` 当前只读取和 dump trace，没有真正禁用或 clear tracer，语义与工具名不一致。

4. `ruyi-mcp` CI 只做 Python 语法检查和 56 tools list，未安装 `requirements.txt`，也未验证 RuyiPage import、Bridge contract 或真实 Python 子进程。

## 建议升级方案

### Phase A：先更新 Python 层与 MCP 门禁

在 `ruyi-mcp` 子仓独立分支中：

1. 将 `requirements.txt` 更新为 `ruyiPage==1.2.46`，同步 README。
2. 修正 `set_screen_orientation(orientation_type=...)`。
3. 收紧 Trace 语义：完整 Trace 只允许 launch 时启用；运行时 start 不再谎报成功，stop 明确 dump/clear/disable 行为。
4. CI 安装 `requirements.txt`，增加 Python import/version 和 Bridge `browser.status` contract test。
5. 保持 MCP tool count 不变；Prompt tools 另开能力变更，不混入依赖升级。

### Phase B：隔离验证 Firefox runtime

1. 将 `151-proxy` 解压到新的 project-local runtime 目录，例如 `tools\ruyipage\runtimes\151-proxy\`。
2. 不修改正在使用的 `tools\ruyitrace\firefox`。
3. 仅在测试进程中临时覆盖 `RUYI_FIREFOX_PATH`。
4. 分别验证 managed `151-ruyi`、project Trace Firefox、`151-proxy` 的能力矩阵。

### Phase C：真实回归门

- 56 tools list 和 Node/Python Bridge 启停。
- `browser.status`、连续 launch/quit、随机端口和孤儿进程清理。
- HTTP / SOCKS5：无认证、URL 认证、percent-encoded 凭据。
- fingerprint：UA、viewport、timezone、locale、窗口尺寸与元素点击坐标。
- Frame list/select；增加默认端口 fixture。
- Trace：launch 后 entries 增长、dump 非空、stop 后不再增长。
- DOMTrace：`MOZ_DOM_TRACE` 生成非空 NDJSON，CLI marker 规则仍成立。

全部通过后，再更新 `.mcp.json` / `.codex/config.toml`、主仓文档和固定 runtime 路径。

## 最终决策

- **Python 包：建议升级到 1.2.46。** 兼容性证据充分，代理修复与现有工作流高度相关。
- **MCP 代码：需要小幅修复和补测试。** 不是因 breaking change，而是升级审计暴露了 orientation 与 Trace 的既有问题。
- **Firefox binary：暂不直接替换。** `151-proxy` 值得测试，但 installer 不会自动取得它，且当前 DOMTrace 路径有 marker 与能力边界。
- **执行时机：安排独立维护窗口。** 当前已有多组 ruyi-mcp 进程从原路径运行，升级应通过新进程和隔离 runtime 验证后再切换。

置信度：Python package 升级建议为高；Firefox runtime 切换建议为中，受上游 CI、#20 和 runtime 分层影响。

## 实施进展（2026-07-14）

### 已落地

- `ruyi-mcp` 版本已更新为 `0.1.1`，依赖固定为 `ruyiPage==1.2.46`；Bridge 的 orientation、Trace 状态和 contract/CI 门禁已进入本轮维护改动。
- `151-proxy` 已 side-by-side 部署到 `D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`，没有覆盖当前 `tools\ruyitrace\firefox`。
- Windows release asset SHA256 为 `f82151f9f197b528b36fb461cf106bc6825c0f752efb5c5d762c34f7529055f6`，Firefox BuildID 为 `20260702113527`。
- `tools\ruyipage\runtimes\` 已按本地 runtime 目录治理，浏览器二进制不进入 Git。

### 真实回归结果

| 门禁 | 结果 |
|------|------|
| `151-proxy` BiDi launch/quit | 通过；headless 会话可正常启动、访问与退出，无本轮测试残留进程 |
| 指纹与窗口状态 | UA、viewport、timezone、locale、orientation 均通过 |
| DOM 交互 | 元素 rect 与 click point 回归通过，DOM click 生效 |
| Issue #20 风险 | 3 个 headed fingerprint profile 均未复现自动最大化导致的坐标偏移；仍保留上游未关闭风险 |
| launch-enabled Trace | entries 可增长，初始导航证据保留 |
| runtime Trace | 首次 start 后 entries 增长；stop 后冻结；结果可继续读取 |
| HTTP 认证代理 | 真实出口通过，percent-encoded 凭据通过 |
| SOCKS5 认证代理 | 当前供应商无对应产品，真实出口门禁跳过；offline contract 已覆盖 URL 与凭据生成 |
| `151-proxy` DOMTrace | 不通过能力判定：无 `RUYI_DOMTRACE.txt` marker，实际不产出 DOMTrace |
| 旧 trace runtime DOMTrace | 通过；设置 `MOZ_DISABLE_LAUNCHER_PROCESS=1` 后可产出 `<output>_<PID>.ndjson` 分片 |

`tools\ruyitrace\ruyitrace.ps1` 现会设置 `MOZ_DISABLE_LAUNCHER_PROCESS=1`，等待各进程分片稳定后合并到 `-Output`；`-Limit` 为可选的每进程行数上限。该 CLI 的 C++ DOMTrace NDJSON 与 MCP `ruyi_trace_*` 的 RuyiPage/WebDriver BiDi JSON Trace 是两套独立能力，文档和验证不得混写。

### 切换结果与剩余风险

- 共享 venv 已升级到 `ruyiPage 1.2.46`。
- `.mcp.json` 与 `.codex/config.toml` 的 `RUYI_FIREFOX_PATH` 已切到 `D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`。
- `D:\reverse_ENV\tools\ruyitrace\firefox\firefox.exe` 不再承担项目 MCP 普通 BiDi 启动，仅保留给 `ruyitrace.ps1` 的 C++ DOMTrace CLI。
- 剩余验证缺口只有真实 SOCKS5 出口门禁：当前供应商没有对应产品，待获得可用供应商后补测；现有 offline contract 已覆盖 1.2.46 的 SOCKS5 credential fpfile 行为。
- Issue #20 在 3 个 headed profile 中未复现，但上游 Issue 仍未关闭，不能据此宣称根因已修复。
