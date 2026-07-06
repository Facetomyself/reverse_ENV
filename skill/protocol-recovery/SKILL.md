---
name: protocol-recovery
description: |
  Web 协议恢复——将已定位的签名/加密/编码逻辑打包为脱离浏览器的 Python 采集器。
  前置条件：已通过 mcp-js-reverse-playbook 或 ruyi-reverse 完成签名定位和补环境。
  适用场景：用户说"写采集器"、"这个接口怎么直接调"、"把签名逻辑落成 Python"。
---

# 协议恢复（Protocol Recovery）

## 定位

本 skill 不重复侦察流程。它接在 `mcp-js-reverse-playbook` 之后，解决一个问题：

> **签名已经找到了，怎么把它变成可离线运行、可重复验证的 Python 采集器？**

## 前置条件

使用本 skill 前，必须先通过 `mcp-js-reverse-playbook` 或 `ruyi-reverse` [Export] 模块完成：
- 目标请求和参数已定位
- 签名函数/加密逻辑已确认
- 运行时依赖已识别

如果还没完成这些，先走 `mcp-js-reverse-playbook` 或 `ruyi-reverse`（两者都能导出 session + 签名定位结果）。

## 前置预检

启动协议恢复前必须先做三项预检，并把可复用来源写入 `report.md` 的 evidence/source：
- 检索 `"D:\reverse_ENV\docs\article-index.md"`，按目标厂商、协议、签名、加密、WebSocket、Webpack 等标签查已有文章。
- 需要外部资料时走 `search-layer`，不要直接 WebFetch；搜索结果只作为线索，必须落到本地证据后再下结论。
- 命中 GitHub issue/PR/code/release 线索时走 `github-solution-research` 深挖，并记录仓库、URL、commit/issue 编号和复用点。

如果复用了知识库文章或搜索结果，`report.md` 必须写清来源、复用的字段语义、仍需验证的假设；`findings.json` 的 `evidence.source` 填本地样本/日志路径，不直接把网页摘要当最终证据。

## 工作区边界

所有本 skill 产物必须统一落在 `"D:\reverse_ENV\workspace\<项目名>\"`，不得散落在 `"D:\reverse_ENV\workspace\"` 根目录、`"D:\reverse_ENV\skill\"` 或 `"D:\reverse_ENV\tools\"` 下：
- 采集器源码、最小 JS helper、`.env.local` 示例、复现脚本
- 原始样本、脱敏样本、fixtures、protocol diff 输出
- 日志、抓包文件（`.flow`/`.pcap`/`.har`）、WebSocket 帧导出
- `report.md`、`findings.json`、`triage.md`

真实凭证只允许放在 `.env.local` 或其他未纳入 Git 的私有文件中；提交用 fixture 必须是 scrub 后的样本。

## 目标家族分类

拿到目标后，先判断属于哪一类。不同类的恢复路径不同：

| 家族 | 特征 | 恢复重点 |
|------|------|---------|
| **signer-gated** | 请求带 `sign`/`token` 字段，由本地 JS 计算 | 提取签名算法 → 本地复现 |
| **verifier-gated** | 服务器返回挑战/验证码/动态 Cookie，客户端响应后才放行 | 还原挑战-响应链 |
| **decode-gated** | 请求能通，但响应是加密/乱码/字形映射/二进制 | 还原解码链 |
| **session-gated** | WebSocket 长连接，需 auth→subscribe→heartbeat→ack | 还原会话状态机 |

分类不是互斥的——一个目标可能同时 signer-gated + decode-gated。

## 恢复路径

### L1：简单 signer（纯算法，无环境依赖）

```powershell
# 场景：sign = md5(param1 + param2 + timestamp)
# 手段：用 crypto_fingerprint 识别编码，再用 Python 复现
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\protocol-recovery\crypto_fingerprint.py" "d41d8cd98f00b204e9800998ecf8427e"
# 输出: hex, md5-like length -> 确认是 MD5 hex
```

### L2：有运行时上下文的 signer

签名依赖页面提供的 publicKey/nonce/deviceId 等。恢复步骤：
1. 用 `"D:\reverse_ENV\tools\protocol-recovery\protocol_diff.py"` 对比多次请求，筛出真正的动态字段
2. 用 ruyipage 或 js-reverse-mcp 获取引导值
3. 将引导逻辑 + 签名算法打包为 Python collector

### L3：decode-gated（响应侧解码）

响应体加密/压缩/字形映射。恢复步骤：
1. 冻结一份原始响应样本
2. 在 JS 源码中找到第一个消费原始响应的函数
3. 用 `"D:\reverse_ENV\tools\protocol-recovery\protocol_diff.py"` 对比原始 vs 解码后，确认解码逻辑
4. Python 复现解码链

### L4：session-gated + stateful stream

WebSocket 需要登录→订阅→心跳，或 stateful stream 仍依赖浏览器运行时。当前工具链下未脱离浏览器的步骤必须写入 `triage.md`，标注：
- `triage-only`
- 阻滞点（缺少 auth、subscribe、heartbeat、ack、server challenge、session resume 等哪一段）
- 运行时依赖（Cookie、localStorage、IndexedDB、Service Worker、WebCrypto、浏览器 TLS/指纹、页面 JS 状态机等）
- 下一步验证条件（需要抓几次帧、比较哪些字段、如何证明可以脱离浏览器）

L4 可用 `ruyipage` 辅助采集，但不能把浏览器驱动包装成最终采集器后声称"纯协议交付"。

## 敏感数据处理

默认脱敏以下内容：Cookie、token、Authorization、refresh token、session id、deviceId、userId、IP、手机号、邮箱、身份证号、精确时间戳、精确地理位置、密钥、nonce、验证码、WebSocket auth payload。

处理规则：
- 报告和 `findings.json` 只保留 hash、前后缀截断或占位符，例如 `<TOKEN_SHA256:...>`、`abc...xyz`、`<REDACTED_COOKIE>`。
- 真实凭证只放 `.env.local` 或未纳入 Git 的私有文件，且在报告里只写保存位置和访问限制，不写原值。
- diff、fixture、日志、抓包进入 evidence chain 前必须 scrub；不能把含真实 Cookie/token 的样本直接放进 `report.md` 或 `findings.json`。
- `findings.json` 每条 finding 必须沿用 reverse-coordinator 模板的 `redaction.redacted`、`redaction.redaction_method`、`redaction.raw_value_stored` 语义。
- 如果需要证明字段稳定性，使用脱敏映射表记录原字段类别、脱敏方式、hash/截断值和存放路径；映射表本身也放在项目工作区，敏感原值不入 Git。

## 证据链粒度

`protocol_diff.py` 的输出只是 evidence 的一部分，不能替代完整证据链。每个关键 claim 至少记录：
- 原始样本路径：例如 `"D:\reverse_ENV\workspace\<项目名>\samples\raw\req-001.json"`
- 脱敏样本路径与脱敏映射：例如 `"D:\reverse_ENV\workspace\<项目名>\samples\scrubbed\req-001.json"`、`"D:\reverse_ENV\workspace\<项目名>\evidence\redaction-map.json"`
- 本地复现命令：必须使用 `"D:\reverse_ENV\.venv\Scripts\python.exe"` 和绝对脚本路径
- 期望输出 hash：对响应体、解码结果、签名串或关键 JSON canonical form 取 SHA-256
- 验证次数：至少写明通过次数、样本数量和覆盖的时间/账号/会话维度
- 失败条件：什么输出、状态码、字段变化或 hash mismatch 代表复现失败
- `confidence`：沿用 `high` / `medium` / `low`
- `rebuild_status`：沿用 `extracted` / `partial` / `not_applicable`

## 交付标准

通过本 skill 完成的任务，最终产出：
- 所有采集器、样本、日志、抓包、报告统一落在 `"D:\reverse_ENV\workspace\<项目名>\"`
- Python 采集器（可通过 `"D:\reverse_ENV\.venv\Scripts\python.exe"` 独立运行）
- 固定输入验证样本、脱敏 fixture、复现命令、期望输出 hash、验证次数和失败条件
- 最终三件套：`report.md`、`findings.json`、`triage.md`
- 三件套沿用 `"D:\reverse_ENV\skill\reverse-coordinator\templates\"` 的字段语义：`report.md` 写结论与 evidence/source，`findings.json` 写结构化 claim、redaction、confidence、rebuild_status，`triage.md` 写未完成项、阻滞点、环境缺口、待验证假设
- 如果 Python 复现不完整，保留一个极小 JS helper（不依赖浏览器 DOM），并在 `triage.md` 写明为什么仍是 `partial`

**不是合格交付**：
- Playwright/Selenium/CDP 驱动浏览器作为最终采集器
- 只跑通一次就不再验证的"幸运重放"
- 把动态 token 硬编码进代码

## CLI 工具

| 工具 | 用途 |
|------|------|
| `"D:\reverse_ENV\tools\protocol-recovery\crypto_fingerprint.py" <value>` | 识别 hash/Base64/自定义编码 |
| `"D:\reverse_ENV\tools\protocol-recovery\protocol_diff.py" <left> <right>` | 对比两请求/响应，筛动态字段 |
| `"D:\reverse_ENV\tools\protocol-recovery\scaffold_reverse_project.py" <name> --profile generic` | 生成采集器项目骨架 |

### 使用示例

```powershell
# 识别可疑字符串
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\protocol-recovery\crypto_fingerprint.py" "e99a18c428cb38d5f260853678922e03"

# 对比两次请求找 sign 字段
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\protocol-recovery\protocol_diff.py" "D:\reverse_ENV\workspace\<项目名>\samples\scrubbed\req1.json" "D:\reverse_ENV\workspace\<项目名>\samples\scrubbed\req2.json" --max-diffs 20

# 生成 Python 采集器项目
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\protocol-recovery\scaffold_reverse_project.py" "target_com" --profile public-envelope --output "D:\reverse_ENV\workspace\target_com"
```

```text
推荐目录：
D:\reverse_ENV\workspace\<项目名>\collector\
D:\reverse_ENV\workspace\<项目名>\samples\raw\
D:\reverse_ENV\workspace\<项目名>\samples\scrubbed\
D:\reverse_ENV\workspace\<项目名>\logs\
D:\reverse_ENV\workspace\<项目名>\captures\
D:\reverse_ENV\workspace\<项目名>\evidence\
D:\reverse_ENV\workspace\<项目名>\report.md
D:\reverse_ENV\workspace\<项目名>\findings.json
D:\reverse_ENV\workspace\<项目名>\triage.md
```

## 禁止事项

- 不要在尚未定位签名函数时就跑 scaffold（骨架里填不了真逻辑）
- 不要跳过 `"D:\reverse_ENV\tools\protocol-recovery\protocol_diff.py"` 直接猜动态字段
- 不要把未 scrub 的 diff、fixture、日志、抓包放入证据链
- 不要把动态 token、Cookie、Authorization、deviceId、userId 或真实账号信息硬编码进代码、报告或 `findings.json`
- 不要对 L4（WebSocket 会话状态机）声称"纯协议交付"——必须在 `triage.md` 标注 `triage-only`
