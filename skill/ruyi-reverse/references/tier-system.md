# Tier 系统

> ruyi-reverse 的 T0-T4 能力层级、升级触发和交付要求。模块边界见 `capability-modules.md`，场景路径见 `scenarios.md`。

## 层级定义

| Tier | 用途 | 典型工具 | 边界 |
|------|------|----------|------|
| T0 | 轻量打开、截图、脚本/请求列表 | `ruyi_new_page`, `ruyi_take_screenshot`, `ruyi_list_scripts`, `ruyi_list_network_requests` | 不做深度断点、不做完整 trace |
| T1 | 抓包采样与复现材料整理 | `ruyi_capture_start`, `ruyi_capture_wait`, `ruyi_save_script_source`, `ruyi_export_session` | 输出必须落 `"D:\reverse_ENV\workspace\<project>\"` |
| T2 | 反检测、人类行为、拦截队列消费 | `ruyi_set_fingerprint`, `ruyi_handle_cloudflare`, `ruyi_human_*`, `ruyi_intercept_wait` | `ruyi_handle_cloudflare` 仅覆盖 Cloudflare Turnstile / 5s 盾；hCaptcha/reCAPTCHA/Akamai 需标注人工/外部能力 |
| T3 | C++ trace 深度指纹取证 | `"D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1"`, `"D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py"` | 独立 Firefox；不与 ruyipage profile 混用 |
| T4 | CDP 真断点桥接 | `js-reverse-mcp` | 仅在无强反检测、Cookie/Storage 可迁移、行为差异可接受时使用 |

## 升级触发

| 信号 | 升级 | 动作 |
|------|------|------|
| 需要连续 observe → capture → rebuild | T0 → T1 | 建立 `"D:\reverse_ENV\workspace\<project>\ruyi-session.json"` |
| 出现 Cloudflare Turnstile / 5s 盾 | T0/T1 → T2 | `ruyi_handle_cloudflare` + 必要的人类轨迹 |
| 出现 hCaptcha / reCAPTCHA / Akamai | T0/T1 → T2 | 使用 fingerprint + human-sim 辅助，并在 triage 标注能力边界 |
| 需要 BiDi trace | T0/T1 → T2 | 先 `ruyi_browser_quit`，再 `ruyi_new_page { traceEnabled:true }` 重开 |
| BiDi trace 缺 canvas/webgl/audio 或需完整 API 序列 | T2 → T3 | 导出 session 后跑 ruyitrace CLI |
| 需要单步、作用域、结构化调用栈 | 任意 → T4 | 先通过 js-reverse gate，再桥接 |
| WASM/VM/重混淆目标 | 任意 → L4 triage-only | 不声称完整还原，只交付证据和下一步 |

## Trace Gate

Trace L1 不能在已打开页面上“补开完整追踪”。标准路径：

```text
ruyi_browser_quit  # 仅当旧页面未启用 trace 时
ruyi_new_page { url, proxy?, fingerprint?, traceEnabled: true }
ruyi_trace_start { outputFile: "D:\reverse_ENV\workspace\<project>\trace-bidi.ndjson" }
触发目标行为
ruyi_trace_stop
ruyi_trace_get_results { limit: 200 }
```

BiDi trace 记录的是协议事件和有限辅助信息，不等同于完整 DOM API 追踪。需要 canvas/webgl/audio、C++ 调用栈或页面无感知取证时，直接升 T3。

## js-reverse Gate

桥接 `js-reverse-mcp` 前必须同时满足：

- 目标没有强反检测，或已经确认 Chrome/CDP 不会改变目标行为
- `ruyi_export_session` 导出的 Cookie/Storage 足以恢复状态
- 调试结论不依赖 Firefox/ruyipage 的指纹一致性
- `triage.md` 记录从 ruyi 到 js-reverse 的行为差异风险

不满足时留在 ruyi-reverse，使用软断点、采样和 trace 辅助，不硬切 CDP。

## 交付门禁

三件套必须写入项目目录：

- `"D:\reverse_ENV\workspace\<project>\report.md"`
- `"D:\reverse_ENV\workspace\<project>\findings.json"`
- `"D:\reverse_ENV\workspace\<project>\triage.md"`

`findings.json` 每条记录至少包含：

```json
{
  "id": "finding-001",
  "source": "ruyi_capture_wait",
  "request_id": "req-123",
  "evidence": {
    "path": "D:\\reverse_ENV\\workspace\\<project>\\captures\\req-123.json",
    "summary": "POST /api/sign 命中 X-Sign header"
  },
  "redaction": {
    "status": "redacted",
    "fields": ["cookie", "authorization", "token"]
  }
}
```

`report.md` 禁止写明文 token/cookie/authorization；必要时只写脱敏前后缀、字段名和证据文件路径。`triage.md` 必须标注当前 Tier、升级原因、未完成能力边界；WASM/VM/重混淆目标必须标注 L4 triage-only。
