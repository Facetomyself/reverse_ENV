---
name: protocol-recovery
description: |
  Web 协议恢复——将已定位的签名/加密/编码逻辑打包为脱离浏览器的 Python 采集器。
  前置条件：已通过 mcp-js-reverse-playbook 完成签名定位和补环境。
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

```python
# 场景：sign = md5(param1 + param2 + timestamp)
# 手段：用 crypto_fingerprint 识别编码 → Python 复现
python tools\protocol-recovery\crypto_fingerprint.py "d41d8cd98f00b204e9800998ecf8427e"
# 输出: hex, md5-like length → 确认是 MD5 hex
```

### L2：有运行时上下文的 signer

签名依赖页面提供的 publicKey/nonce/deviceId 等。恢复步骤：
1. `protocol_diff.py` 对比多次请求，筛出真正的动态字段
2. 用 ruyipage 或 js-reverse-mcp 获取引导值
3. 将引导逻辑 + 签名算法打包为 Python collector

### L3：decode-gated（响应侧解码）

响应体加密/压缩/字形映射。恢复步骤：
1. 冻结一份原始响应样本
2. 在 JS 源码中找到第一个消费原始响应的函数
3. `protocol_diff.py` 对比原始 vs 解码后，确认解码逻辑
4. Python 复现解码链

### L4：session-gated + stateful stream

WebSocket 需要登录→订阅→心跳。当前工具链下标注为 triage，建议用 `ruyipage` 做浏览器辅助采集。

## 交付标准

通过本 skill 完成的任务，最终产出：
- Python 采集器（可在 `.venv` 中独立运行）
- 固定输入验证样本（`protocol_diff.py` 的输出作为证据）
- 如果 Python 复现不完整，保留一个极小 JS helper（不依赖浏览器 DOM）

**不是合格交付**：
- Playwright/Selenium/CDP 驱动浏览器作为最终采集器
- 只跑通一次就不再验证的"幸运重放"
- 把动态 token 硬编码进代码

## CLI 工具

| 工具 | 用途 |
|------|------|
| `tools\protocol-recovery\crypto_fingerprint.py <value>` | 识别 hash/Base64/自定义编码 |
| `tools\protocol-recovery\protocol_diff.py <left> <right>` | 对比两请求/响应，筛动态字段 |
| `tools\protocol-recovery\scaffold_reverse_project.py <name> --profile generic` | 生成采集器项目骨架 |

### 使用示例

```bash
# 识别可疑字符串
python tools\protocol-recovery\crypto_fingerprint.py "e99a18c428cb38d5f260853678922e03"

# 对比两次请求找 sign 字段
python tools\protocol-recovery\protocol_diff.py req1.json req2.json --max-diffs 20

# 生成 Python 采集器项目
python tools\protocol-recovery\scaffold_reverse_project.py target_com --profile public-envelope
```

## 禁止事项

- 不要在尚未定位签名函数时就跑 scaffold（骨架里填不了真逻辑）
- 不要跳过 `protocol_diff` 直接猜动态字段
- 不要对 L4（WebSocket 会话状态机）声称"纯协议交付"——标注为 triage
