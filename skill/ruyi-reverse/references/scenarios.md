# 场景模板

> 精简索引见 `ruyi-reverse/SKILL.md#场景索引`。本文档包含完整步骤、常见坑点和失败处理。

## 场景 A: 快速过检 — "打开页面看看"

**默认 tier: T0** ｜ **升级: CF 超时 → T2**

### 标准路径 (T0)

```
1. ruyi_new_page { url, proxy?, fingerprint? }
2. ruyi_handle_cloudflare { timeout: 15 }
3. ruyi_take_screenshot → 确认加载成功
4. (可选) ruyi_list_scripts + ruyi_list_network_requests
5. (可选) ruyi_export_session → 保存登录态
```

### 升级: CF 超时 (T2)

```
触发: ruyi_handle_cloudflare 超时 30s+

1. ruyi_dom_select { selector: "tag:iframe" } → 找到 CF iframe
2. ruyi_select_frame { contextId: "<from step1>" }
3. ruyi_human_move { target: "#checkbox", algorithm: "windmouse" }
4. ruyi_human_click { target: "#checkbox", algorithm: "windmouse" }
5. ruyi_select_frame → 切回主 frame → 等 3-5s → screenshot 验证
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| 代理不可用 | new_page 超时 | 检查代理，或去 proxy |
| CF 版本更新 | handle_cloudflare 找不到 checkbox | 升级 T2 手动 |
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
4. ruyi_trace_start
5. ruyi_navigate_page { type: "reload" }  ← 触发指纹采集
6. ruyi_trace_stop
7. ruyi_trace_get_results { limit: 200 }

Phase 3 — 分析:
8. 按 API 分类统计 → 交叉引用 stack 和 scripts 定位具体函数
```

### 升级: BiDi 缺维度 (T3)

```
触发: trace_get_results 缺失 canvas/webgl/audio

1. ruyi_export_session → workspace/<project>/trace-session.json
2. 启动 ruyitrace:
   powershell -File "D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1" `
     -Url "https://target.com" -Output "workspace/<project>/trace.ndjson"
3. 在 trace 浏览器注入 session.json cookies
4. 刷新 → 操作 → 关闭浏览器
5. python tools\ruyitrace\trace_analyzer.py workspace/<project>/trace.ndjson
6. python trace_analyzer.py trace.ndjson -c canvas/webgl/audio
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| trace_start 后无数据 | get_results 空 | 确保 trace_start 在操作之前 |
| NDJSON 空 | 没记录到调用 | 检查 RUYI_DOMTRACE.txt; 关其他 Firefox |
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
6. ruyi_save_script_source → workspace/<project>/target.js
7. ruyi_export_session → workspace/<project>/session.json
8. Node.js 加载 → 开始补环境

Phase 4 — Patch:
9. first divergence → 补齐 → 验证 → 迭代
10. 参考 ruyi_trace_get_results 确认调用哪些 API

Phase 5 — DeepDive (可选):
11. ruyi_trace_start → 触发加密 → ruyi_trace_stop → 确认底层 API
```

### 升级: 需 CDP 调试 (T4)

```
触发: 需要单步进入加密函数内部

1. ruyi_export_session → workspace/<project>/session.json
2. 切 mcp-js-reverse-playbook skill
3. js-reverse_new_page { url }
4. js-reverse_evaluate_script: 注入 cookies + localStorage
5. js-reverse_set_breakpoint_on_text { text: "encrypt" }
6. (触发) → js-reverse_get_paused_info { includeScopes: true }
7. js-reverse_step { direction: "into" }
8. js-reverse_evaluate_script: 读取中间变量
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| 签名在 WASM | JS 找不到 | 标注 L4 triage-only |
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
2. ruyi_handle_cloudflare { timeout: 15 }

Phase 2 — 手动人类模拟 (T2, CF 超时):
3. ruyi_dom_select { selector: "tag:iframe" }
4. ruyi_select_frame → 进入 iframe
5. 识别类型: CF checkbox / hCaptcha / reCAPTCHA
6. ruyi_human_move { target: "<checkbox>", algorithm: "windmouse" }
7. ruyi_human_click { target: "<checkbox>", algorithm: "windmouse" }

Phase 3 — 验证:
8. ruyi_select_frame → 切回主 frame
9. ruyi_take_screenshot → 确认通过
10. ruyi_list_console_messages → 检查无 "blocked"
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
2. ruyi_handle_cloudflare
3. (登录) ruyi_dom_input → ruyi_dom_click
4. ruyi_take_screenshot → 确认已登录

Phase 2 — 导出 (T0):
5. ruyi_export_session {
     outputFile: "workspace/<project>/session.json",
     include: ["cookies", "localStorage", "sessionStorage"]
   }

Phase 3 — 桥接 CDP (T4):
6. 切 mcp-js-reverse-playbook skill
7. js-reverse_new_page { url }
8. js-reverse_evaluate_script {
     function: "async ({ localFile }) => {
       const s = JSON.parse(localFile.text);
       s.cookies.forEach(c => document.cookie = `${c.name}=${c.value}; domain=${c.domain}; path=${c.path}`);
       Object.entries(s.localStorage||{}).forEach(([k,v]) => localStorage.setItem(k,v));
     }",
     localFilePath: "workspace/<project>/session.json"
   }
9. js-reverse_navigate_page { type: "reload" } → 刷新使 cookie 生效

Phase 4 — CDP 调试:
10. js-reverse_set_breakpoint_on_text { text: "目标函数" }
11. (触发) → js-reverse_get_paused_info { includeScopes: true }
12. js-reverse_step { direction: "into" }
13. js-reverse_evaluate_script: 查看变量值

Phase 5 — 返回 ruyi (可选):
14. 切回 ruyi-reverse → ruyi_new_page 重新过检
```

### 坑点

| 坑点 | 现象 | 解决 |
|------|------|------|
| Cookie domain 不匹配 | 注入后仍跳登录 | 检查 domain/path/sameSite |
| HttpOnly cookies 丢失 | 登录态不完整 | js-reverse 直接设浏览器 cookie |
| Chrome 被检测 | 页面行为不同 | 回到 ruyi；T4 不适合 |
| session.json 太大 | evaluate_script 超时 | 分批注入或只注入关键 cookies |
