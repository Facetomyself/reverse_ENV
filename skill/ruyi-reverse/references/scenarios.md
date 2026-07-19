# 场景模板

> 精简索引见 `ruyi-reverse/SKILL.md#场景索引`。本文档包含完整步骤、常见坑点和失败处理。

## 场景 A: 快速过检 — "打开页面看看"

**默认 tier: T0** ｜ **升级: CF 超时 → T2**

### 标准路径 (T0)

```
1. ruyi_new_page { url, proxy?, fingerprint? }
2. ruyi_handle_cloudflare { timeout: 15 }  ← 仅 Cloudflare Turnstile / 5s 盾
3. ruyi_take_screenshot → 确认加载成功
4. (可选) ruyi_list_scripts + ruyi_list_network_requests
5. (可选) ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" } → 保存登录态
```

### 升级: CF 超时 (T2)

```
触发: Cloudflare Turnstile / 5s 盾场景下 `ruyi_handle_cloudflare` 超时 30s+

1. ruyi_dom_select { selector: "tag:iframe" } → 找到 CF iframe
2. ruyi_list_frames → 找到目标 iframe 的 contextId
3. ruyi_select_frame { contextId: "<from step2>" }
4. ruyi_human_move { target: "#checkbox", algorithm: "windmouse" }
5. ruyi_human_click { target: "#checkbox", algorithm: "windmouse" }
6. ruyi_list_frames → 选择主 frame contextId → ruyi_select_frame { contextId: "<main>" } → 等 3-5s → screenshot 验证
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| 代理不可用 | new_page 超时 | 检查代理，或去 proxy |
| CF 版本更新 | ruyi_handle_cloudflare 找不到 checkbox | 升级 T2 手动 |
| 指纹不匹配 | "unsupported browser" | 调整 requireCountry |
| 代理出口不匹配 | CountryMismatchError | 换代理或调整国家 |

---

## 场景 B: 指纹取证 — "分析指纹采集行为"

**默认 tier: T0 → T2 ∼ T3** ｜ **升级: BiDi 缺维度 → T3**

### 标准路径 (T0 → T2)

```
Phase 1 — 侦察 (T0):
1. ruyi_new_page { url, proxy?, fingerprint? }
2. ruyi_list_scripts { filter: "fingerprint" }
3. ruyi_search_in_sources { query: "canvas|webgl|audio|navigator|screen" }

Phase 2 — 动态追踪 (T2):
4. 如页面已打开但未启用 trace: ruyi_browser_quit
5. ruyi_new_page { url, proxy?, fingerprint?, traceEnabled: true }
6. ruyi_trace_start { outputFile: "D:\reverse_ENV\workspace\<project>\trace-bidi.ndjson" }
7. ruyi_navigate_page { type: "reload" }  ← 触发指纹采集
8. ruyi_trace_stop
9. ruyi_trace_get_results { limit: 200 }

Phase 3 — 分析:
10. 按 BiDi 协议事件分类统计 → 交叉引用 scripts 定位可疑函数；不要声称完整 DOM API 覆盖
```

### 升级: BiDi 缺维度 (T3)

```
触发: trace_get_results 缺失 canvas/webgl/audio

1. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\trace-session.json" }
2. 启动 ruyitrace:
   powershell -File "D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1" `
     -Url "https://target.com" -Output "D:\reverse_ENV\workspace\<project>\trace.ndjson"
3. 在 trace 浏览器注入 session.json cookies
4. 刷新 → 操作 → 关闭浏览器
5. "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson"
6. "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\tools\ruyitrace\trace_analyzer.py" "D:\reverse_ENV\workspace\<project>\trace.ndjson" -c canvas
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| trace_start 后无数据 | get_results 空 | 确保 trace_start 在操作之前 |
| NDJSON 空 | 没记录到调用 | 检查 `RUYI_DOMTRACE.txt` 和 `MOZ_DISABLE_LAUNCHER_PROCESS=1`；关闭其他 Firefox |
| 指纹脚本动态加载 | scripts 列表找不到 | 先触发操作再 search |
| 代码混淆 | stack 不清 | T3 C++ stack 更清晰 |

---

## 场景 C: 协议逆向 — "找到加密函数并复现"

**默认 tier: T1** ｜ **升级: 需 CDP 调试 → T4**

### 标准路径 (T1)

```
Phase 1 — Observe:
1. ruyi_new_page { url, proxy?, fingerprint? }
2. ruyi_list_network_requests { urlFilter: "/api/" }
3. ruyi_search_in_sources { query: "encrypt|sign|token|hmac|md5|sha" }
4. 如命中 → ruyi_get_script_source 获取上下文

Phase 2 — Capture:
5a. 被动抓包: ruyi_capture_start → (触发) → ruyi_capture_wait
5b. XHR 断点: ruyi_break_on_xhr → (触发) → ruyi_evaluate_script 采样

Phase 3 — Rebuild:
6. ruyi_save_script_source { url, filePath: "D:\reverse_ENV\workspace\<project>\target.js" }
7. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }
8. Node.js 加载 → 开始补环境

Phase 4 — Patch:
9. first divergence → 补齐 → 验证 → 迭代
10. 如已通过 `ruyi_new_page { traceEnabled:true }` 预启用，可参考 ruyi_trace_get_results 查看 BiDi 协议事件；需要完整环境 API 列表转 T3

Phase 5 — DeepDive (可选):
11. Trace L1: ruyi_new_page { traceEnabled:true } → ruyi_trace_start → 触发加密 → ruyi_trace_stop → 只做协议事件辅助
```

### 升级: 需 CDP 调试 (T4)

```
触发: 需要单步进入加密函数内部

1. ruyi_export_session { outputFile: "D:\reverse_ENV\workspace\<project>\session.json" }
2. Gate: 无强反检测、Cookie/Storage 可迁移、Chrome/CDP 行为差异不会影响结论
3. 切 js-reverse-mcp 相关 playbook
4. js-reverse_new_page { url }
5. js-reverse_evaluate_script: 注入 cookies + localStorage
6. js-reverse_set_breakpoint_on_text { text: "encrypt" }
7. (触发) → js-reverse_get_paused_info { includeScopes: true }
8. js-reverse_step { direction: "into" }
9. js-reverse_evaluate_script: 读取中间变量
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| 签名在 WASM | JS 找不到 | 固化 boundary Trace、wrapper fixture 和源码后切 `web-deobfuscation`；证据不足才标 L4/triage-only |
| 捕获无 body | POST body 空 | 改用 break_on_xhr |
| session 桥接后仍需登录 | cookie domain 不匹配 | 检查 domain/path/sameSite |
| 补环境无限循环 | 补一个触发新 API | trace 获取完整列表一次性补齐 |

---

## 场景 D: 验证码突破 — "过掉验证码"

**默认 tier: T0 → T2** ｜ **升级: 图片挑战 → 人工/AI**

### 标准路径

```
Phase 1 — 自动 (T0):
1. ruyi_new_page { url, proxy, fingerprint: { requireCountry: "US" } }
2. ruyi_handle_cloudflare { timeout: 15 }  ← 仅 Cloudflare Turnstile / 5s 盾

Phase 2 — 手动人类模拟 (T2, CF 超时):
3. ruyi_dom_select { selector: "tag:iframe" }
4. ruyi_list_frames → 找到目标 iframe contextId
5. ruyi_select_frame { contextId: "<challenge-frame>" } → 进入 iframe
6. 识别类型: Cloudflare Turnstile / hCaptcha / reCAPTCHA / Akamai
7. Cloudflare Turnstile 可继续 human_move/human_click；hCaptcha/reCAPTCHA/Akamai 只做人工/外部能力辅助，不承诺自动破解
8. ruyi_human_move { target: "<checkbox>", algorithm: "windmouse" }
9. ruyi_human_click { target: "<checkbox>", algorithm: "windmouse" }

Phase 3 — 验证:
10. ruyi_list_frames → 选择主 frame contextId → ruyi_select_frame { contextId: "<main>" }
11. ruyi_take_screenshot → 确认通过
12. ruyi_evaluate_script { function: "() => ({ url: location.href, title: document.title, blocked: document.body?.innerText?.includes('blocked') })" }
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| 代理被标记 | 反复 challenge | 换代理 IP |
| 轨迹太机械 | 反复要求验证 | windmouse + 随机延迟 |
| 指纹缺陷 | 通过 checkbox 仍 block | 检查 22 维指纹 |
| 图片挑战 | 无法自动 | 截图供人工或接 AI 识别 |

---

## 场景 E: 跨工具协作 — "过检后 CDP 调试"

**默认 tier: T4**

### 标准路径

```
Phase 1 — ruyi 过检 (T0):
1. ruyi_new_page { url, proxy, fingerprint }
2. ruyi_handle_cloudflare  ← 仅 Cloudflare Turnstile / 5s 盾
3. (登录) ruyi_dom_input → ruyi_dom_click
4. ruyi_take_screenshot → 确认已登录

Phase 2 — 导出 (T0):
5. ruyi_export_session {
     outputFile: "D:\reverse_ENV\workspace\<project>\session.json",
     include: ["cookies", "localStorage", "sessionStorage"]
   }

Phase 3 — 桥接 CDP (T4):
6. Gate: 无强反检测、Cookie/Storage 可迁移、Chrome/CDP 行为差异不会影响结论
7. 切 js-reverse-mcp 相关 playbook
8. js-reverse_new_page { url }
9. js-reverse_evaluate_script {
     function: "async ({ localFile }) => {
       const s = JSON.parse(localFile.text);
       s.cookies.forEach(c => document.cookie = `${c.name}=${c.value}; domain=${c.domain}; path=${c.path}`);
       Object.entries(s.localStorage||{}).forEach(([k,v]) => localStorage.setItem(k,v));
     }",
     localFilePath: "D:\reverse_ENV\workspace\<project>\session.json"
   }
10. js-reverse_navigate_page { type: "reload" } → 刷新使 cookie 生效

Phase 4 — CDP 调试:
11. js-reverse_set_breakpoint_on_text { text: "目标函数" }
12. (触发) → js-reverse_get_paused_info { includeScopes: true }
13. js-reverse_step { direction: "into" }
14. js-reverse_evaluate_script: 查看变量值

Phase 5 — 返回 ruyi (可选):
15. 切回 ruyi-reverse → ruyi_new_page 重新过检
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| Cookie domain 不匹配 | 注入后仍跳登录 | 检查 domain/path/sameSite |
| HttpOnly cookies 丢失 | 登录态不完整 | js-reverse 直接设浏览器 cookie |
| Chrome 被检测 | 页面行为不同 | 回到 ruyi；T4 不适合 |
| session.json 太大 | evaluate_script 超时 | 分批注入或只注入关键 cookies |
