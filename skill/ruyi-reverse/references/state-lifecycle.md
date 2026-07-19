# 状态管理参考

> ruyi-reverse 编排器的 session 生命周期、状态文件格式、tier 追踪。

## 会话生命周期

```
                         ruyi_new_page
      IDLE ──────────────────────────────→ ACTIVE
       │                                      │
       │                                      │ ruyi_export_session
       │                                      ├──→ HYBRID (T4 桥接)
       │                                      │      │
       │                                      │      │ 切回 ruyi_new_page
       │                                      │      └──→ ACTIVE
       │                                      │
       │                                      │ ruyi_browser_quit
       │                                      └──→ IDLE
       │                                      │
       │               (超时/异常)             │
       └──────────────────────────────────────┘
```

**状态转换规则：**

| 从 | 到 | 触发条件 |
|------|------|---------|
| IDLE | ACTIVE | `ruyi_new_page` 成功 |
| ACTIVE | HYBRID | `ruyi_export_session` (T4 桥接) |
| HYBRID | ACTIVE | 切回 ruyi-reverse + `ruyi_new_page` |
| ACTIVE | IDLE | `ruyi_browser_quit` 或会话超时 |
| 任意 | IDLE | 异常终止 |

## 状态文件: `"D:\reverse_ENV\workspace\<project>\ruyi-session.json"`

```json
{
  "schema": "ruyi-reverse-session-v2",
  "created_at": "2026-07-02T10:30:00+08:00",
  "updated_at": "2026-07-02T11:15:00+08:00",

  "current_tier": "T1",
  "current_phase": "capture",

  "browser": {
    "active": true,
    "page_count": 2,
    "current_page": 0,
    "pages": [
      {
        "pageIdx": 0,
        "url": "https://target.com",
        "title": "Target App",
        "proxy": "socks5://127.0.0.1:7890",
        "fingerprint_profile": "us-west"
      }
    ]
  },

  "trace": {
    "active": false,
    "enabled_at_new_page": false,
    "started_at": null,
    "stopped_at": null,
    "output_path": null
  },

  "export": {
    "last_export_path": null,
    "last_export_at": null,
    "bridged_to": null,
    "bridge_tool": null
  },

  "escalation_log": [
    {
      "from_tier": "T0",
      "to_tier": "T1",
      "reason": "multi-step workflow: observe → capture → rebuild",
      "signal": "user requested protocol reverse",
      "timestamp": "2026-07-02T10:35:00+08:00"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema` | string | 状态文件版本，用于向前兼容 |
| `current_tier` | T0-T4 | 当前能力层级 |
| `current_phase` | observe/capture/rebuild/patch/deepdive | 当前工作流阶段 |
| `browser.active` | boolean | 是否有活跃浏览器 session |
| `browser.pages` | array | 所有打开页面的状态 |
| `trace.active` | boolean | BiDi trace 是否运行中 |
| `trace.enabled_at_new_page` | boolean | 是否在 `ruyi_new_page { traceEnabled:true }` 时预启用；完整 L1 trace 必须为 true |
| `trace.output_path` | string? | NDJSON 输出路径 (T3) |
| `export.last_export_path` | string? | 最近一次 session 导出路径 |
| `export.bridged_to` | string? | 桥接目标 MCP 服务名（如 "js-reverse-mcp"） |
| `escalation_log` | array | tier 升级记录，用于审计和回溯 |

## Tier 追踪

### 升级记录格式

每次 tier 变更记录一条：

```json
{
  "from_tier": "T0",
  "to_tier": "T1",
  "reason": "多步骤工作流需求",
  "signal": "用户连续调用 ruyi_capture_start + ruyi_capture_wait",
  "timestamp": "2026-07-02T10:35:00+08:00"
}
```

### 升级触发信号速查

| 信号 | 从 | 到 | 自动/手动 |
|------|:---:|:---:|:---:|
| 连续 3+ 次不同 ruyi_* 调用 | T0 | T1 | 自动检测 |
| MCP 工具报 unknown parameter | T0/T1 | T2 | 手动确认 |
| `ruyi_trace_get_results` 缺关键维度 | T1/T2 | T3 | 手动确认 |
| 用户要求单步/作用域/调用栈 | 任意 | T4 | 手动确认 |
| CF 过检超时 30s+ | T0/T1 | T2 | 自动检测 |

### 降级记录格式

```json
{
  "from_tier": "T4",
  "to_tier": "T0",
  "reason": "CDP 调试完成，返回 ruyi 做 trace",
  "timestamp": "2026-07-02T11:10:00+08:00"
}
```

## 多页面追踪

当打开多标签页时的状态管理：

```
ruyi_new_page → browser.pages[0]
ruyi_new_page → browser.pages[1]  (新标签)
ruyi_select_page { pageIdx: 0 }   → browser.current_page = 0
ruyi_select_page { pageIdx: 1 }   → browser.current_page = 1
ruyi_close_page { pageIdx: 1 }    → browser.pages 移除 [1]
```

**注意：** MCP 的 proxy 是 launch-time browser 级配置，未暴露 per-tab proxy；切换代理须 quit/relaunch，只有 T2 直接调用 ruyipage 才能使用 `set_per_tab_proxies`。fingerprint tab 先创建 `about:blank`：普通 tab 首跳前重放 context-scoped overlay 并保留共享 userContext screen，container 首跳前重放完整 emulation；container 创建失败不得降级为普通 tab。

## Trace 生命周期

```
IDLE ──ruyi_new_page { traceEnabled:true }──→ TRACE_READY
                                            │
                              ruyi_trace_start
                                            │
                                            ▼
                                         TRACING
                              │
                     (触发操作/等待)
                              │
                     ruyi_trace_stop
                              │
                              ▼
                           COMPLETE ──ruyi_trace_get_results──→ 分析
                              │
                     (超时/异常)
                              │
                              ▼
                           IDLE
```

**Trace L1 规则：** 完整路径必须从 `ruyi_new_page { traceEnabled:true }` 开始；页面已经打开但未启用 trace 时，先 `ruyi_browser_quit`，再用同 URL、代理、fingerprint 重开。`ruyi_trace_start` 只能记录追加的 BiDi 协议事件，不能补齐旧页面生命周期里的完整 DOM/API 行为。

**Trace 期间不可：** 关闭浏览器、切换代理、修改指纹设置。

## 跨 Session 状态迁移

### ruyi → js-reverse (T4 桥接)

```
1. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }
2. 记录: export.last_export_path, export.bridged_to = "js-reverse-mcp"
3. Gate: 目标无强反检测、Cookie/Storage 可迁移、Chrome/CDP 行为差异不会影响结论
4. 切到 js-reverse-mcp 相关 playbook
5. js-reverse_new_page → 注入 `"D:\reverse_ENV\workspace\<project>\session.json"`
```

### ruyi → ruyitrace (T3 升级)

```
1. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\trace-session.json" }
2. 记录: escalation_log 添加 T2→T3
3. 启动独立 ruyitrace Firefox
4. 在 trace 浏览器中通过 preload script 注入 session
```

### 返回 ruyi (降级)

```
1. 记录 escalation_log 中的降级记录
2. ruyi_new_page 重新打开（需要重新过检）
3. 如有需要，从之前的 session.json 恢复状态
```

## 清理

会话结束时的清理清单：

- [ ] `ruyi_browser_quit` 确保浏览器进程终止
- [ ] 删除临时 trace NDJSON（如已分析完毕）
- [ ] `ruyi-session.json` 存档到 `"D:\reverse_ENV\workspace\<project>\"`
- [ ] escalation_log 完整记录所有 tier 变更
- [ ] `triage.md` 中标注当前 tier 和未完成原因
