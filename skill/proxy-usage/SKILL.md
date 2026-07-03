---
name: proxy-usage
description: |
  第三方代理统一入口 — 快代理 (HTTP/HTTPS) + Cliproxy (SOCKS5)。
  按使用链路组织: 场景→诊断→提取→验证→注入。供应商细节放在参考区，按需查阅。
  凭证统一走 .env，禁止硬编码。
---

# proxy-usage

逆向工程中代理的**唯一入口**。四个步骤走到底：

```
场景判断 → 诊断/提取 → 验证 → 注入工具链
```

在动手之前:
- **新供应商/新账号** → 先诊断，确认产品可用再提取
- **已有可用代理** → 跳到「RE 工具食谱」选对应工具
- **不知道选哪个** → 看「场景 → 供应商路由」

---

## 走一遍

### 第一步: 判断场景

```
目标网站在国内?  → 快代理 (HTTP 代理，国内 IP)
目标网站在海外?  → Cliproxy (SOCKS5，海外住宅 IP)
需要固定 IP 长期持有? → 快代理 独享 / Cliproxy 静态 ISP
需要每次换 IP (轮换)? → 快代理 隧道 / Cliproxy Rotating
需要同 IP 保持 N 分钟? → Cliproxy Sticky (t-N) / 快代理私密(粘滞)
```

不确定就选 **快代理 私密代理 (dps)**，最通用。

### 第二步: 诊断 + 提取

**快代理** — 先诊断再提取:

```powershell
# 1. 诊断 (必做 — 确认哪些产品可用、余额是否够)
python "D:\reverse_ENV\skill\proxy-usage\scripts\kuaidaili_extract.py" --diagnose

# 2. 提取 (产品确认可用后)
python "D:\reverse_ENV\skill\proxy-usage\scripts\kuaidaili_extract.py" --product dps --count 3 --check
```

输出直接给出可用的 `http://user:pass@ip:port` URL，复制即用。

**Cliproxy** — 拼接用户名 + 直连:

```powershell
# 1. 测试连通性
python "D:\reverse_ENV\skill\proxy-usage\scripts\cliproxy_test.py"

# 2. 按需拼接用户名参数 (见下方「Cliproxy 参考」→「用户名分段参数」)
# Rotating: youruser-region-US-st-California
# Sticky:   youruser-region-US-st-Texas-sid-sess1-t-30
```

**Cliproxy 网络前置 (大陆环境):**
Cliprocy SOCKS5 端口 (`us.cliproxy.io:1080`, `sg.cliproxy.io:1080`) 从大陆直连被阻断。当前用 Clash Verge 将 `*.cliproxy.io` 流量路由到 HK 节点，由 HK 出口连 Cliproxy。拓扑:

```
PC(大陆) → Clash(TUN/系统代理) → HK 节点 → us.cliproxy.io:1080 → 目标
```

> Clash 规则: `DOMAIN-SUFFIX,cliproxy.io,<HK节点名>`。Clash 开启后 Python 脚本直连即可，代码无需改动。

### 第三步: 验证

```powershell
# HTTP 代理
python "D:\reverse_ENV\skill\proxy-usage\scripts\proxy_check.py" `
    --proxy "http://user:pass@ip:port"

# SOCKS5 代理
python "D:\reverse_ENV\skill\proxy-usage\scripts\proxy_check.py" `
    --proxy "socks5h://user:pass@host:port"
```

### 第四步: 注入工具链

按你用的工具对号入座:

| 工具 | 怎么注入 |
|------|---------|
| `ruyi-mcp` 浏览器 | `ruyi_new_page(proxy="http://...")` 或 `proxy="socks5h://..."` |
| Python `requests` | `requests.get(url, proxies={"http": proxy_url, "https": proxy_url})` |
| `curl` | `curl -x "http://..."` 或 `curl -x "socks5h://..."` |
| `mitmproxy` (ldplayer 抓包) | `mitmdump --mode upstream:http://proxy_ip:port` |
| `aiohttp` / `httpx` | `session.get(url, proxy=proxy_url)` / `Client(proxy=proxy_url)` |

> 具体代码见下方「RE 工具食谱」。

### 完整示例: 用快代理给 ruyi-mcp 浏览器挂代理

```powershell
# 1. 诊断
python "D:\reverse_ENV\skill\proxy-usage\scripts\kuaidaili_extract.py" --diagnose

# 2. 提取 1 个 HTTP 代理
python "D:\reverse_ENV\skill\proxy-usage\scripts\kuaidaili_extract.py" --product dps --count 1
# 输出: http://user123:pass456@1.2.3.4:5678

# 3. 在 ruyi-mcp 中使用
# ruyi_new_page(url="https://目标", proxy="http://user123:pass456@1.2.3.4:5678")
```

---

## 供应商参考

### 快代理

**产品线:**

| 产品 | 代码 | 协议 | 特点 |
|------|------|------|------|
| 私密代理 | `dps` | HTTP/HTTPS | 独享，手动提取，最通用 |
| 隧道代理 | `tps` | HTTP/HTTPS | 固定隧道地址，自动换 IP |
| 独享代理 | `kps` | HTTP/HTTPS | 独占端口，长期持有 |
| 开放代理 | `ops` | HTTP/HTTPS | 共享池，成本低 |
| 海外动态 | `fps` | HTTP/SOCKS5 | 真实住宅 IP |
| 海外静态 | `sfps` | HTTP | 固定住宅 IP |

**SecretId 类型 (首次必读):**

| 级别 | 用途 | 能调的 API |
|------|------|-----------|
| **账户级** | 管余额、建订单 | `getaccountbalance`, `createorder` |
| **订单级** | 提取代理、管白名单 | `getdps`, `getkps`, `gettps`, `getproxyauthorization` 等 |

新用户典型流程: `注册 → 拿账户级 key → 充值 → 购买套餐 → 拿订单级 key → 提取代理`

错用账户级 key 调 `getdps` → 报 `-123 secret type error`。
充值后未购买套餐 → 报 `-5 余额充值订单不能提取私密代理`。

**认证三方式:**

| 方式 | 何时用 |
|------|--------|
| API 签名 (SecretId + signature) | 调用提取 API (SDK 自动处理) |
| 账密 (`user:pass@ip:port`) | 使用代理时 |
| IP 白名单 | 固定出口 IP 场景，免账密 |

**Python SDK:**

```python
import kdl  # pip install kdl
auth = kdl.Auth("secret_id", "secret_key")
client = kdl.Client(auth)
proxies = client.get_dps(num=1, format='json', pt=1)   # pt: 1=HTTP 2=HTTPS 3=SOCKS5
# → ["1.2.3.4:5678"]
auth_info = client.get_proxy_authorization(plain_text=1)  # 取账密用于拼接
```

**隧道代理:** 不需要提取 IP，用固定隧道地址 + 账密直连:
```python
proxy_url = f"http://{username}:{password}@{tunnel_host}:{tunnel_port}"
# 每次请求自动换 IP
```

**文档直达:** [API 概览](https://www.kuaidaili.com/doc/api/) | [SDK 样例](https://help.kuaidaili.com/dev/sdk_api_proxy/) | [创建订单 API](https://www.kuaidaili.cn/doc/api/createorder/) | [鉴权信息](https://help.kuaidaili.com/api/getproxyauthorization/)

---

### Cliproxy

SOCKS5 海外代理，按流量计费。

**核心机制: 用户名分段参数**

不走传统 API 提取，把路由参数编码到用户名:

```
<username>-region-<国家>-st-<州>-sid-<会话ID>-t-<分钟>
```

| 参数 | 含义 | 示例 |
|------|------|------|
| `region-XX` | ISO 3166-1 国家 | `region-US`, `region-SG` |
| `st-XXX` | 州/省 (可选) | `st-California` |
| `sid-XXX` | 会话 ID，变了就换 IP | `sid-myapp-sess1` |
| `t-N` | Sticky 分钟 (可选, 最长 120) | `t-30` |

**Rotating (每次换 IP):** 不写 `sid` 和 `t`
```
youruser-region-US-st-California
```

**Sticky (N 分钟不变):** 写 `sid` 和 `t`
```
youruser-region-US-st-Texas-sid-sess1-t-30
```

**连接:**

```python
proxy_url = f"socks5h://{username}:{password}@{host}:{port}"
# host: us.cliproxy.io (美) 或 sg.cliproxy.io (新)
# port: 1080
# socks5h: DNS 走代理 (逆向场景强制，避免 DNS 泄露)
```

**网络前置 (大陆):**
`*.cliproxy.io` TCP 端口从大陆直连被阻断，DNS 正常解析。当前通过 Clash Verge 将 Cliproxy 域名流量路由到 HK 节点:

```
PC(大陆) → Clash → HK 节点 → us.cliproxy.io:1080 → 目标
```

Clash 开启后 Python 脚本无需改动，直连即通。

**白名单模式:** 在后台将出口 IP (此处为 HK 节点的出口 IP) 加入白名单后，可省略账密。

**API 模式 (端口绑定):** 在 Web 面板生成 API URL → GET 请求触发绑定 → 该端口固定 IP。适合需要预先选好 IP 再操作的场景。

**文档直达:** [帮助中心](https://help.cliproxy.com/zh) | [流量包 API](https://help.cliproxy.com/faq/traffic-api) | [账密模式](https://help.cliproxy.com/zh/traffic/using-setup) | [静态 ISP](https://help.cliproxy.com/zh/static/used.md)

---

## RE 工具食谱

### ruyi-mcp 浏览器

```python
# 快代理 HTTP
ruyi_new_page(url="https://目标", proxy="http://user:pass@ip:port")

# Cliproxy SOCKS5
ruyi_new_page(url="https://目标",
    proxy="socks5h://user-region-US-st-CA:pass@us.cliproxy.io:1080")
```

ruyi-mcp 代理在 `ruyi_new_page` 时设置，启动后无法切换。多代理需求用多标签页。

### Python requests

```python
import requests

# 快代理 HTTP
proxies = {"http": "http://user:pass@ip:port", "https": "http://user:pass@ip:port"}
resp = requests.get("https://目标", proxies=proxies, timeout=15)

# Cliproxy SOCKS5 — 需要: pip install 'requests[socks]'
proxies = {
    "http": "socks5h://user-region-US-sid-sess1-t-30:pass@us.cliproxy.io:1080",
    "https": "socks5h://user-region-US-sid-sess1-t-30:pass@us.cliproxy.io:1080",
}
resp = requests.get("https://目标", proxies=proxies, timeout=30)
```

注意: `session.proxies = {...}` 在某些 requests 版本不生效，建议每次 `get()/post()` 显式传 `proxies=`。

### curl

```bash
# HTTP 代理
curl -x "http://user:pass@ip:port" "https://目标"

# SOCKS5 — socks5h 让 DNS 也走代理
curl -x "socks5h://user-region-US:pass@us.cliproxy.io:1080" "https://目标"
```

### aiohttp / httpx

```python
# aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get(url, proxy="http://user:pass@ip:port") as resp:
        data = await resp.json()

# httpx
with httpx.Client(proxy="http://user:pass@ip:port") as client:
    resp = client.get(url)
```

### mitmproxy 上游 (ldplayer 抓包链)

```bash
# 模拟器 → mitmproxy(抓包) → 上游付费代理 → 目标
mitmdump --mode upstream:http://user:pass@proxy_ip:port -w traffic.flow
```

---

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/kuaidaili_extract.py` | 快代理: `--diagnose` 诊断 + `--product dps/tps/kps/ops` 提取 + `--check` 验证 |
| `scripts/cliproxy_test.py` | Cliproxy: `--full` 对比 Rotating vs Sticky, 单次 `--region US --sticky 30` |
| `scripts/proxy_check.py` | 通用: 验证单个/批量代理可用性 (HTTP + SOCKS5) |

**凭证:** 三个脚本都支持 `--env <路径>` 从 `.env` 文件读取。推荐把凭证写在 `skill/proxy-usage/.env`（已 gitignored），一行命令加载:

```powershell
$env_path = "D:\reverse_ENV\skill\proxy-usage\.env"
python "...\kuaidaili_extract.py" --env $env_path --diagnose
python "...\cliproxy_test.py" --env $env_path
```

或设一次系统环境变量 (持久化，重启仍有效):

```powershell
# 快代理
[Environment]::SetEnvironmentVariable("KDL_SECRET_ID", "xxx", "User")
[Environment]::SetEnvironmentVariable("KDL_SECRET_KEY", "yyy", "User")
# Cliproxy
[Environment]::SetEnvironmentVariable("CLIPROXY_USER", "xxx", "User")
[Environment]::SetEnvironmentVariable("CLIPROXY_PASS", "yyy", "User")
```

---

## 规范

### 凭证管理

**禁止硬编码。** 凭证只走三个渠道，优先级从高到低:

1. 环境变量 (`KDL_SECRET_ID`, `CLIPROXY_USER` 等)
2. `.env` 文件 (`skill/proxy-usage/.env` 或 `workspace/<项目>/.env`)
3. 项目凭证文件 (`workspace/<项目>/proxy_creds.json`)

所有凭证文件已加入 `.gitignore`。

### 故障排查

| 症状 | 原因 | 动作 |
|------|------|------|
| 快代理 -123 `secret type error` | 账户级 key 调了订单级 API | 购买套餐后换订单级 key |
| 快代理 -5 `余额充值订单不能...` | 充值了但没买套餐 | 会员中心购买产品套餐 |
| Cliproxy TCP timeout | 大陆直连被阻断 | 开启 Clash (HK 节点) |
| 代理连上但目标返回 403 | IP 被目标封禁 | 换 IP |
| 代理返回 407 | 认证失败 | 检查账密/白名单配置 |
| Sticky 模式 IP 变了 | 会话过期 | 加大 `t-N` 值 |
| SOCKS5 报 `Missing dependencies` | 缺 PySocks | `pip install 'requests[socks]'` |
| ruyi-mcp 代理不生效 | 浏览器已启动 | `ruyi_browser_quit` 后重新 `ruyi_new_page` |

### 禁止事项

- 硬编码凭证到代码/文档
- 代理未验证可用就直接跑逆向 (先跑 `proxy_check.py`)
- 同一 IP 跨项目混用 (封禁连带)
- 同目标高频请求不做 IP 轮换
- 代理流量用于非逆向用途
