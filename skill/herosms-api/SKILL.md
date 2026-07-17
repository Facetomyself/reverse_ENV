---
name: herosms-api
description: Use for HeroSMS virtual-number API operations in D:\reverse_ENV, including API-key setup, balance checks, country/service/price lookup, activation offers, buying a number with a price ceiling, polling an OTP, reading SMS history, and completing or cancelling an activation. Trigger for HeroSMS、hero-sms、接码 API、购买号码、收验证码、查询接码库存或迁移 SMS-Activate API.
---

# herosms-api

通过无第三方依赖的 CLI 使用 HeroSMS。默认走官方 SMS-Activate 兼容端点完成激活生命周期，并用 REST v1 查询 activation offers。

## 入口

```powershell
$py = "D:\reverse_ENV\.venv\Scripts\python.exe"
$cli = "D:\reverse_ENV\skill\herosms-api\scripts\herosms.py"
```

所有业务结果输出 JSON。`--pretty` 必须放在命令组之前，例如：

```powershell
& $py $cli --pretty account balance
```

## 配置凭据

真实凭据统一使用 Windows 用户环境变量 `HEROSMS_API_KEY`。新启动的 Codex、Claude 和终端会直接继承；CLI 还会只读 `HKCU\Environment`，因此当前已启动会话也能立即使用。先检查，不输出 key：

```powershell
& $py $cli --pretty config show
```

凭据优先级：

1. 当前进程 `HEROSMS_API_KEY`
2. Windows 用户环境变量 `HEROSMS_API_KEY`
3. `%USERPROFILE%\.herosms\credentials.json` 兼容回退

只有环境变量无法使用时，才交互式写入兼容凭据文件：

```powershell
& $py $cli config set
```

禁止把 key 放进命令参数、仓库文件、`.codex/config.toml`、`.claude/settings*.json`、skill 文件、日志或回复正文。

## 标准流程

### 1. 验证账户

```powershell
& $py $cli --pretty health
& $py $cli --pretty account balance
```

### 2. 查服务、国家、价格和库存

不要凭记忆写 service/country ID，先查目录：

```powershell
& $py $cli --pretty catalog countries
& $py $cli --pretty catalog services --country 6
& $py $cli --pretty catalog prices --service tg --country 6
& $py $cli --pretty catalog offers --services tg --countries 6
```

`catalog offers` 使用 REST v1；其他目录命令使用 SMS-Activate 兼容 API。两路结果冲突时，以购买前最新一次 `catalog prices/offers` 和 `getNumberV2` 返回为准。

### 3. 购买号码

购买会扣费，必须同时给出价格上限和显式确认：

```powershell
& $py $cli --pretty activation buy `
  --service tg `
  --country 6 `
  --max-price 0.30 `
  --yes
```

默认调用 `getNumberV2`。仅在旧集成明确需要文本响应时加 `--v1`。不要在用户没有确认 service、country、`max-price` 时代买号码。

### 4. 接收验证码

目标站点接受号码并触发短信后，将 activation 标记为 ready，再轮询：

```powershell
& $py $cli --pretty activation ready --id 123456 --yes
& $py $cli --pretty activation poll --id 123456 --poll-timeout 120 --interval 5
```

只查一次状态：

```powershell
& $py $cli --pretty activation status --id 123456
& $py $cli --pretty activation status --id 123456 --v2
```

读取该 activation 的全部短信：

```powershell
& $py $cli --pretty activation sms --id 123456
```

### 5. 收尾

收到并确认验证码后完成 activation：

```powershell
& $py $cli --pretty activation complete --id 123456 --yes
```

不再使用且符合平台取消条件时取消：

```powershell
& $py $cli --pretty activation cancel --id 123456 --yes
```

需要重发时：

```powershell
& $py $cli --pretty activation resend --id 123456 --yes
```

CLI 不会在 poll 超时后自动 complete 或 cancel，避免错误结算。

## 查询已有记录

```powershell
& $py $cli --pretty activation active --limit 20
& $py $cli --pretty activation history --size 20
```

## 执行约束

- 购买前先查价格/库存，并始终设置可接受的 `--max-price`。
- `buy/ready/resend/complete/cancel/config clear` 都要求 `--yes`，不得绕过。
- 轮询默认 5 秒一次；不要为了抢码把间隔压到 1 秒以下。官方账户限额为 40 RPS，超限可能短暂封禁。
- `BAD_KEY`、`NO_NUMBERS`、`NO_BALANCE`、`WRONG_MAX_PRICE` 等会输出结构化错误并返回非零 exit code。
- Codex 用户入口为 `%USERPROFILE%\.codex\skills\herosms-api\SKILL.md`，Claude 用户入口为 `%USERPROFILE%\.claude\skills\herosms-api\SKILL.md`；两者只路由到本项目 source skill，不复制脚本或凭据。
- 真实 `health` 未通过时，只能运行本地测试和认证门禁，不能声称购买、收码或退款已实测。
- 需要接口、状态码、现成库对比或证据来源时，读取 [references/api.md](references/api.md)。

## 验证

```powershell
& $py -m unittest discover `
  -s "D:\reverse_ENV\skill\herosms-api\tests" `
  -p "test_*.py" `
  -v
```
