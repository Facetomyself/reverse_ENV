# HeroSMS API 参考与方案取舍

## 结论

HeroSMS 官方提供两套与本 skill 相关的接口：

1. SMS-Activate 兼容层：`https://hero-sms.com/stubs/handler_api.php`
2. REST v1：`https://hero-sms.com/api/v1`

激活购买、状态轮询和生命周期管理优先使用兼容层，因为官方文档列出的 action 完整，且现有 TypeScript/Python 客户端都以它为主。REST v1 当前用于结构化查询 `/activations/offers`。

## 认证

### SMS-Activate 兼容层

认证放在 query 参数：

```text
api_key=<key>&action=<action>
```

### REST v1

activation offers 使用 header：

```text
Authorization: ApiKey <key>
```

CLI 的 key 来源优先级：

1. 当前进程 `HEROSMS_API_KEY`
2. Windows 用户环境变量 `HEROSMS_API_KEY`（`HKCU\Environment`）
3. `%USERPROFILE%\.herosms\credentials.json`

真实 key 只保存在 Windows 用户环境变量，不写入 Codex/Claude 配置、skill、项目文件或日志。Codex 和 Claude 的用户级 skill 都只是指向 `D:\reverse_ENV\skill\herosms-api\SKILL.md` 的薄入口。

## 核心 action

| CLI | HeroSMS action/endpoint | 说明 |
|-----|-------------------------|------|
| `account balance` | `getBalance` | 查询余额 |
| `catalog countries` | `getCountries` | 国家 ID 列表 |
| `catalog services` | `getServicesList` | 服务 code 列表 |
| `catalog operators` | `getOperators` | 运营商列表 |
| `catalog prices` | `getPrices` | 价格和可用量 |
| `catalog top-countries` | `getTopCountriesByService` / `getTopCountriesByServiceRank` | 服务的推荐国家 |
| `catalog offers` | `GET /activations/offers` | REST v1 activation offers |
| `activation buy` | `getNumberV2`，可选 `getNumber` | 购买号码 |
| `activation status` | `getStatus` / `getStatusV2` | 查询短信状态 |
| `activation ready/resend/complete/cancel` | `setStatus` | 更新生命周期 |
| `activation active` | `getActiveActivations` | 当前激活 |
| `activation history` | `getHistory` | 历史记录 |
| `activation sms` | `getAllSms` | 全部短信 |

官方文档还列出 `reactivate`、`reactivationPrice`、`serviceCountRent`、`getRentServicesAndCountries`、`getRentNumber`、`finishActivation` 和 `cancelActivation`。当前 CLI 未暴露这些低频操作，避免在没有真实账户回归的情况下扩大未验证面。

## 生命周期状态

### `setStatus` 请求值

| 值 | 含义 |
|----|------|
| `1` | 已提交号码，准备接收短信 |
| `3` | 请求再次发送短信 |
| `6` | 激活完成 |
| `8` | 取消激活 |

### `getStatus` 常见响应

| 响应 | 含义 |
|------|------|
| `STATUS_WAIT_CODE` | 等待第一条短信 |
| `STATUS_WAIT_RETRY:<old_code>` | 等待替换短信 |
| `STATUS_WAIT_RESEND` | 等待请求重发 |
| `STATUS_OK:<code>` | 已收到验证码 |
| `STATUS_CANCEL` | 激活已取消 |

## 常见错误

| 错误 | 处理 |
|------|------|
| `BAD_KEY` / `BAD_API_KEY` / `NO_KEY` | 检查 key 来源，不要在日志中打印 key |
| `NO_BALANCE` | 充值后重试，不要自动循环购买 |
| `NO_NUMBERS` | 换国家/运营商或稍后查询库存 |
| `WRONG_MAX_PRICE:<min>` | 重新确认价格上限，禁止静默提高 |
| `EARLY_CANCEL_DENIED` | 等待平台允许取消，不要反复高频请求 |
| `NO_ACTIVATION` / `WRONG_ACTIVATION_ID` | 校验 activation ID |
| `BANNED:<time>` | 到期后再试，检查请求频率 |
| HTTP `400` / `1020` / `429` | 检查是否触发频率限制 |

官方规则写明每个账户分配 40 RPS；超限会先短暂封禁。单 activation 轮询保持 5 秒间隔即可，没必要往限额上怼。

## 多来源方案对比

| 方案 | 现状 | 取舍 |
|------|------|------|
| 官方 API 文档 | 完整列出兼容层 actions、REST offers 和 webhook | 协议事实源；页面动态加载，检索时需搜索层或浏览器 |
| `osyduck/Hero-SMS` / npm `hero-sms` | TypeScript，MIT，0 Stars；覆盖主要 action | 可供 Node 项目直接采用，但引入 axios/npm 依赖 |
| `xxspell/herosms` / PyPI `herosms` 0.1.1 | Python async/sync，0 Stars；覆盖 activation、rent、webhook | 功能较全，但 GitHub 仓库未声明 license，不适合直接复制源码 |
| `netcookies/MaDao` | Rust/Tauri，多供应商，18 Stars，AGPL-3.0 | 适合桌面聚合管理，作为单一 HeroSMS CLI 太重 |
| `kompui/fastapi-sms-receiver` | HeroSMS webhook 示例，9 Stars，无 license | 可参考 webhook 架构，不作为基础客户端依赖 |

GitHub 未检索到可直接复用的 Codex/Claude `SKILL.md`。因此本仓库新增 dependency-free CLI，只复用公开协议，不复制无 license 客户端源码。

## 证据来源

- HeroSMS 官方 API：<https://hero-sms.com/api>
- HeroSMS 官方规则：<https://hero-sms.com/rules>
- HeroSMS 官方 GitHub 指南：<https://github.com/HeroSMS-com/virtual-numbers-guide>
- TypeScript 客户端：<https://github.com/osyduck/Hero-SMS>
- Python 客户端：<https://github.com/xxspell/herosms>
- PyPI：<https://pypi.org/project/herosms/>
- 多供应商桌面方案：<https://github.com/netcookies/MaDao>

## 当前验证边界

- 已验证：本地 mock 覆盖认证、余额、目录、价格、V1/V2 购买响应、状态轮询、REST offers、错误映射、密钥脱敏和购买确认门。
- 已验证：官方 legacy endpoint 对假 key 的真实认证错误路径，不产生购买。
- 待验证：真实账户余额、真实库存、实际扣费、真实短信到达、取消退款和 webhook 投递。
