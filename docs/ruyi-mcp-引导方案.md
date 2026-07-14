# ruyi-mcp 引导方案

## 0. 前置确认

| 项目 | 值 | 状态 |
|------|-----|:---:|
| Node.js | v20.20.2（`tools\node\node.exe`） | ✅ >= 20.19.0 |
| ruyipage | 1.2.46（`.venv\Lib\site-packages\ruyipage\`） | ✅ |
| ruyipage BiDi Firefox | `tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe` | ✅ |
| ruyitrace DOMTrace Firefox | `tools\ruyitrace\firefox\firefox.exe` | ✅（独立 CLI） |
| Python venv | `.venv\Scripts\python.exe` | ✅ |
| MCP SDK | `@modelcontextprotocol/sdk` 1.21.1（js-reverse-mcp 已安装） | ✅ |

## 1. 总架构：Node.js MCP Server → Python 子进程桥接 → ruyipage

```
┌────────────────────────────────────────────────┐
│            ruyi-mcp (Node.js MCP Server)         │
│                                                  │
│  src/                                            │
│  ├── index.ts          # MCP entry point         │
│  ├── server.ts         # MCP server setup         │
│  ├── tools/            # 56 tool definitions     │
│  │   ├── page.ts       # R01-R04                 │
│  │   ├── script.ts     # R05-R07                 │
│  │   ├── search.ts     # R08                     │
│  │   ├── network.ts    # R09-R11                 │
│  │   ├── debug.ts      # R12-R18                 │
│  │   ├── runtime.ts    # R19-R20                 │
│  │   ├── util.ts       # R21-R23                 │
│  │   ├── antidetect.ts # R24-R27  (ruyi 独有)    │
│  │   ├── human.ts      # R28-R30  (ruyi 独有)    │
│  │   ├── dom.ts        # R31-R34  (ruyi 独有)    │
│  │   ├── trace.ts      # 3 BiDi Trace tools       │
│  │   ├── netenhance.ts # R39-R42  (ruyi 独有)    │
│  │   └── session.ts    # Session 导出              │
│  │                                                │
│  ├── bridge/           # Python 桥接层            │
│  │   ├── python.ts     # 子进程管理 + JSON-RPC   │
│  │   ├── page.ts       # 页面操作桥接             │
│  │   ├── script.ts     # 脚本操作桥接             │
│  │   ├── network.ts    # 网络操作桥接             │
│  │   └── ...                                      │
│  │                                                │
│  └── ruyi-context.ts   # 浏览器会话状态管理        │
│                                                  │
│  ┌────────────────────┐                          │
│  │  Python Bridge      │  child_process.spawn    │
│  │  (ruyi_bridge.py)   │  ← JSON-RPC over stdin  │
│  │                     │  → JSON-RPC over stdout │
│  └────────┬───────────┘                          │
│           │                                       │
│  ┌────────┴───────────┐                          │
│  │  ruyipage Python    │  WebDriver BiDi         │
│  │  FirefoxPage        │ ←──────────→ Firefox    │
│  └────────────────────┘                          │
└────────────────────────────────────────────────┘
```

**为什么用 Python 子进程桥接而不是纯 Node.js：**
- ruyipage 1.2.46 是成熟的 Python 包，直接重写成本高、风险大
- BiDi WebSocket 协议虽然标准，但 ruyipage 的 `smart_fingerprint`、`handle_cloudflare_challenge` 等高级功能是 Python 实现的业务逻辑
- 子进程桥接让我们**立即获得全部 ruyipage 能力**，同时保留未来逐步移植到 Node.js 的路径
- 桥接协议用 JSON-RPC（stdin/stdout），零网络开销，简单可靠

## 2. Python Bridge 设计

### 2.1 桥接协议：JSON-RPC over stdio

```
Node.js                              Python (ruyi_bridge.py)
  │                                       │
  │── {"id":1, "method":"page.navigate",  │
  │     "params": {"url":"https://..."}} ─→│
  │                                       │── page.get(url)
  │                                       │── return {"title":"..."}
  │←─ {"id":1, "result": {"title":"..."}} │
  │                                       │
```

### 2.2 `ruyi_bridge.py` 骨架

```python
#!/usr/bin/env python3
"""ruyi-mcp Python bridge — JSON-RPC over stdio."""

import sys
import json
import traceback
from ruyipage import FirefoxPage, FirefoxOptions

class RuyiBridge:
    def __init__(self):
        self.page: FirefoxPage | None = None
        self.opts: FirefoxOptions | None = None
        self.pages: dict[int, FirefoxPage] = {}  # pageIdx → page
        self._handlers = {
            "browser.launch": self._launch,
            "browser.quit": self._quit,
            "page.navigate": self._navigate,
            "page.new": self._new_page,
            "page.close": self._close_page,
            "page.select": self._select_page,
            "page.screenshot": self._screenshot,
            "script.evaluate": self._evaluate,
            "script.add_preload": self._add_preload,
            "network.list": self._list_network,
            "network.intercept": self._intercept,
            "cookie.get": self._get_cookies,
            "cookie.set": self._set_cookies,
            "cookie.delete": self._delete_cookies,
            "fingerprint.set": self._set_fingerprint,
            "proxy.set": self._set_proxy,
            "console.get": self._get_console,
            "dom.select": self._dom_select,
            "dom.info": self._dom_get_info,
            "dom.input": self._dom_input,
            "dom.click": self._dom_click,
            "human.move": self._human_move,
            "human.click": self._human_click,
            "human.input": self._human_input,
            "session.export": self._export_session,
            "cf.handle": self._handle_cf,
        }

    def _launch(self, params):
        opts = FirefoxOptions()
        opts.set_browser_path(params.get("browser_path") or
            r"C:\Users\mengma\AppData\Local\ruyipage\browsers\firefox-151.0a1-151-ruyi-win64\firefox\firefox.exe")
        if params.get("proxy"):
            opts.set_proxy(params["proxy"])
        if params.get("headless"):
            opts.headless(True)
        if params.get("fingerprint"):
            fp = params["fingerprint"]
            ctx = opts.smart_fingerprint(
                proxy_host=fp.get("proxy_host"),
                proxy_port=fp.get("proxy_port"),
                require_country=fp.get("require_country"),
            )
        self.opts = opts
        self.page = FirefoxPage(opts)
        if params.get("fingerprint"):
            ctx.apply_emulation(self.page)
        self.pages[0] = self.page
        return {"pageIdx": 0, "url": self.page.url, "title": self.page.title}

    def _navigate(self, params):
        page = self._get_page(params.get("pageIdx", 0))
        page.get(params["url"], timeout=params.get("timeout", 30))
        return {"url": page.url, "title": page.title}

    def _evaluate(self, params):
        page = self._get_page(params.get("pageIdx", 0))
        result = page.run_js(params["script"], timeout=params.get("timeout", 10))
        return {"result": self._serialize(result)}

    def _add_preload(self, params):
        page = self._get_page(params.get("pageIdx", 0))
        script_id = page.add_preload_script(params["script"])
        return {"scriptId": str(script_id)}

    # ... (其余 handler 实现)

    def _get_page(self, page_idx):
        if page_idx not in self.pages:
            raise ValueError(f"Invalid pageIdx: {page_idx}")
        return self.pages[page_idx]

    def _serialize(self, obj):
        """将 Python 对象序列化为 JSON-safe 格式"""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._serialize(x) for x in obj]
        if isinstance(obj, dict):
            return {str(k): self._serialize(v) for k, v in obj.items()}
        return str(obj)

    def handle(self, request):
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        handler = self._handlers.get(method)
        if not handler:
            return {"id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

        try:
            result = handler(params)
            return {"id": req_id, "result": result}
        except Exception as e:
            return {"id": req_id, "error": {"code": -32000, "message": str(e), "data": traceback.format_exc()}}

    def run(self):
        """主循环 — 逐行读取 JSON-RPC 请求，写回响应。"""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle(request)
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                sys.stdout.write(json.dumps({"error": str(e)}) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    bridge = RuyiBridge()
    bridge.run()
```

### 2.3 Node.js 桥接层 (`src/bridge/python.ts`)

```typescript
import { spawn, ChildProcess } from 'node:child_process';
import { createInterface } from 'node:readline';

interface JsonRpcRequest {
  id: number;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: string };
}

export class PythonBridge {
  private proc: ChildProcess;
  private requestId = 0;
  private pending = new Map<number, { resolve: Function; reject: Function }>();
  private rl: ReturnType<typeof createInterface>;

  constructor() {
    const pythonPath = 'D:\\reverse_ENV\\.venv\\Scripts\\python.exe';
    const scriptPath = 'D:\\reverse_ENV\\mcp\\ruyi-mcp\\bridge\\ruyi_bridge.py';

    this.proc = spawn(pythonPath, [scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    this.rl = createInterface({ input: this.proc.stdout! });
    this.rl.on('line', (line: string) => {
      const response: JsonRpcResponse = JSON.parse(line);
      const pending = this.pending.get(response.id);
      if (pending) {
        this.pending.delete(response.id);
        if (response.error) {
          pending.reject(new Error(response.error.message));
        } else {
          pending.resolve(response.result);
        }
      }
    });

    this.proc.stderr!.on('data', (data: Buffer) => {
      console.error('[ruyi-bridge stderr]', data.toString());
    });
  }

  async call(method: string, params?: Record<string, unknown>): Promise<unknown> {
    const id = ++this.requestId;
    const request: JsonRpcRequest = { id, method, params };
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc.stdin!.write(JSON.stringify(request) + '\n');
    });
  }

  async close(): Promise<void> {
    await this.call('browser.quit', {});
    this.proc.kill();
  }
}
```

## 3. 项目初始化

`ruyi-mcp` 已作为公开 submodule 接入原路径。首次初始化并安装锁定依赖：

```powershell
git -C "D:\reverse_ENV" submodule update --init "mcp/ruyi-mcp"
Set-Location "D:\reverse_ENV\mcp\ruyi-mcp"
& "D:\reverse_ENV\tools\node\npm.cmd" ci
& "D:\reverse_ENV\tools\node\npm.cmd" run build
```

维护者需要跟进公开仓 `main` 时，执行 `git -C "D:\reverse_ENV" submodule update --remote --merge "mcp/ruyi-mcp"`；验证通过后在主仓提交新的 gitlink。

## 4. Phase 1：首批 8 个工具（历史引导验证）

早期 43 tools 设计基线中先选出下列 8 个工具验证架构；当前实现已扩展为 56 tools：

| # | 工具 | 理由 | 复杂度 |
|---|------|------|:---:|
| R01 | `ruyi_new_page` | 核心入口，验证 launch+anti-detection | 中 |
| R02 | `ruyi_navigate_page` | 基础页面操作 | 低 |
| R19 | `ruyi_evaluate_script` | **关键能力** — 对齐 js-reverse 的 evaluate_script | 低 |
| R24 | `ruyi_set_proxy` | ruyi 独有价值 — 反检测代理 | 低 |
| R25 | `ruyi_set_fingerprint` | ruyi 独有价值 — 智能指纹 | 中 |
| R31 | `ruyi_dom_select` | ruyi 独有价值 — DOM 元素定位 | 低 |
| R32 | `ruyi_dom_get_info` | ruyi 独有价值 — DOM 信息读取 | 低 |
| R43 | `ruyi_export_session` | **桥接关键** — 导出 session 给其他工具 | 中 |

**Phase 1 验证目标：**
1. ✅ MCP server 能启动，工具能注册
2. ✅ `ruyi_new_page` 能启动 ruyipage Firefox 并加载页面
3. ✅ `ruyi_evaluate_script` 能在页面执行 JS 并返回结果
4. ✅ `ruyi_set_fingerprint` + `ruyi_set_proxy` 能过 Cloudflare
5. ✅ `ruyi_export_session` 能导出 Cookie → 可被 js-reverse-mcp 消费

## 5. `.mcp.json` 配置

```json
{
  "mcpServers": {
    "ruyi-mcp": {
      "command": "D:\\reverse_ENV\\tools\\node\\node.exe",
      "args": ["D:\\reverse_ENV\\mcp\\ruyi-mcp\\build\\src\\index.js"],
      "env": {
        "RUYI_MCP_PYTHON": "D:\\reverse_ENV\\.venv\\Scripts\\python.exe",
        "RUYI_FIREFOX_PATH": "D:\\reverse_ENV\\tools\\ruyipage\\runtimes\\151-proxy\\firefox\\firefox.exe"
      }
    }
  }
}
```

（与现有 `js-reverse-mcp` 并列，`reverse-coordinator` 按反检测强度路由）

## 6. 从引导到完整的历史路线图

> 当前已落地 56 tools。MCP 内的 3 个 `ruyi_trace_*` 工具是 BiDi JSON Trace；C++ DOMTrace 始终由独立 `tools\ruyitrace\ruyitrace.ps1` 承担。

```
Phase 1 (当前)         Phase 2                Phase 3              Phase 4
引导验证 8 tools ──→ 补齐 22 核心对齐 ──→ ruyi 独有全量 ──→ BiDi Trace
                                                                    │
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ new_page         │ │ list_scripts     │ │ human_move       │ │ trace_start      │
│ navigate_page    │ │ get_script_source│ │ human_click      │ │ trace_stop       │
│ evaluate_script  │ │ save_script_     │ │ human_input      │ │ trace_get_results│
│ set_proxy        │ │ source           │ │ dom_input        │ │                  │
│ set_fingerprint  │ │ search_in_sources│ │ dom_click        │ │                  │
│ dom_select       │ │ list_network_    │ │ intercept_req    │ │ (此时 ruyi-mcp   │
│ dom_get_info     │ │ requests         │ │ intercept_res    │ │  56 tools 齐全)  │
│ export_session   │ │ get_request_     │ │ set_extra_headers│ │                  │
│                  │ │ initiator        │ │ set_cache_       │ │                  │
│ (验证架构可行性)  │ │ get_websocket_   │ │ behavior         │ │                  │
│                  │ │ messages         │ │ take_screenshot  │ │                  │
│                  │ │ set_breakpoint   │ │ select_frame     │ │                  │
│                  │ │ break_on_xhr     │ │ clear_site_data  │ │                  │
│                  │ │ get_paused_info  │ │ close_page       │ │                  │
│                  │ │ pause_or_resume  │ │ emulate_geo      │ │                  │
│                  │ │ step             │ │ emulate_timezone │ │                  │
│                  │ │ list_breakpoints │ │ list_console     │ │                  │
│                  │ │ remove_breakpoint│ │                  │ │                  │
│                  │ │                  │ │                  │ │                  │
│                  │ │ (22 核心对齐      │ │ (+扩展能力)     │ │ (+3 trace)       │
│                  │ │  js-reverse-mcp)  │ │                  │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
        2-3天               1-2周               1-2周               1周
```

## 7. Python Bridge 方法与 MCP 工具映射表

| MCP Tool | Python Bridge Method | ruyipage API |
|----------|---------------------|--------------|
| `ruyi_new_page` | `browser.launch` | `FirefoxPage(opts)` |
| `ruyi_navigate_page` | `page.navigate` | `page.get(url)` |
| `ruyi_close_page` | `page.close` | `page.close()` |
| `ruyi_select_page` | `page.select` | `page.get_tab(id)` |
| `ruyi_evaluate_script` | `script.evaluate` | `page.run_js(script)` |
| `ruyi_list_scripts` | `script.list` | `page.run_js("Array.from(document.scripts).map(...)")` |
| `ruyi_get_script_source` | `script.get_source` | HTTP fetch script URL |
| `ruyi_save_script_source` | `script.save_source` | fetch + write file |
| `ruyi_search_in_sources` | `script.search` | `page.run_js(...)` (grep in DOM) |
| `ruyi_list_network_requests` | `network.list` | `page.capture` / `page.listen` |
| `ruyi_get_request_initiator` | `network.initiator` | `page.listen` + stack trace |
| `ruyi_get_websocket_messages` | `network.ws` | `page.listen` WS events |
| `ruyi_set_breakpoint_on_text` | `debug.set_breakpoint` | `page.add_preload_script(...)` (软断点) |
| `ruyi_break_on_xhr` | `debug.break_xhr` | `page.add_preload_script(XHR proxy)` |
| `ruyi_get_paused_info` | `debug.paused` | N/A (软断点需自建状态管理) |
| `ruyi_pause_or_resume` | `debug.pause` | N/A |
| `ruyi_step` | `debug.step` | N/A |
| `ruyi_list_breakpoints` | `debug.list_breakpoints` | 自建状态管理 |
| `ruyi_remove_breakpoint` | `debug.remove` | `page.remove_preload_script(id)` |
| `ruyi_list_console_messages` | `console.get` | `page.console` |
| `ruyi_take_screenshot` | `page.screenshot` | `page.screenshot()` |
| `ruyi_select_frame` | `page.select_frame` | `page.with_frame(id)` |
| `ruyi_clear_site_data` | `browser.clear_data` | `page.delete_cookies()` + Storage clear |
| **ruyi 独有 ↓** | | |
| `ruyi_set_proxy` | `proxy.set` | `opts.set_proxy(url)` |
| `ruyi_set_fingerprint` | `fingerprint.set` | `opts.smart_fingerprint()` |
| `ruyi_emulate_geolocation` | `emulation.geo` | `page.set_geolocation(lat,lng)` |
| `ruyi_emulate_timezone` | `emulation.tz` | `page.set_timezone(tz)` |
| `ruyi_human_move` | `human.move` | `page.actions.human_move()` |
| `ruyi_human_click` | `human.click` | `page.actions.human_click()` |
| `ruyi_human_input` | `human.input` | `page.ele(sel).input(text)` |
| `ruyi_dom_select` | `dom.select` | `page.ele(selector)` |
| `ruyi_dom_get_info` | `dom.info` | `el.text / el.html / el.attr()` |
| `ruyi_dom_input` | `dom.input` | `el.input(text)` |
| `ruyi_dom_click` | `dom.click` | `el.click_self()` |
| `ruyi_intercept_requests` | `network.intercept` | `page.intercept.start_requests()` |
| `ruyi_intercept_responses` | `network.intercept_resp` | `page.intercept.start_responses()` |
| `ruyi_set_extra_headers` | `network.extra_headers` | `page.network.set_extra_headers()` |
| `ruyi_set_cache_behavior` | `network.cache` | `page.set_cache_behavior(mode)` |
| **BiDi Trace ↓** | | |
| `ruyi_trace_start` | `trace.start` | `opts.enable_trace(True)` |
| `ruyi_trace_stop` | `trace.stop` | `page.trace.dump_json()` |
| `ruyi_trace_get_results` | `trace.results` | `page.trace.latest(n)` |

C++ DOMTrace 不在 MCP Bridge 内启停；需要 DOM API 内核取证时，单独调用 `tools\ruyitrace\ruyitrace.ps1` 和 `trace_analyzer.py`。

## 8. 关键 API 能力对照（已验证存在）

| ruyipage API | MCP 能力映射 | 验证状态 |
|-------------|-------------|:---:|
| `page.run_js(script)` | `evaluate_script` | ✅ 已验证 |
| `page.add_preload_script(script)` | Hook 注入 / 软断点 | ✅ 已验证 |
| `page.get(url)` | `navigate_page` | ✅ 已验证 |
| `page.screenshot()` | `take_screenshot` | ✅ API 存在 |
| `page.capture.start/stop/wait()` | 网络抓包 | ✅ API 存在 |
| `page.intercept.start_requests()` | 请求拦截 | ✅ API 存在 |
| `page.listen` | 网络事件监听 | ✅ API 存在 |
| `page.console` | 控制台消息 | ✅ API 存在 |
| `page.ele(selector)` | DOM 元素定位 | ✅ API 存在 |
| `page.actions.human_move/click()` | 人类行为模拟 | ✅ API 存在 |
| `opts.smart_fingerprint()` | 智能指纹 | ✅ API 存在 |
| `opts.set_proxy()` | 代理设置 | ✅ API 存在 |
| `page.set_geolocation()` | 地理位置模拟 | ✅ API 存在 |
| `page.set_timezone()` | 时区模拟 | ✅ API 存在 |
| `page.handle_cloudflare_challenge()` | CF 验证码自动过 | ✅ API 存在 |
| `page.get_cookies()/set_cookies()` | Cookie CRUD | ✅ API 存在 |
| `opts.enable_trace()` | BiDi 事件追踪 | ✅ API 存在 |
| `page.trace.summary()/dump_json()` | 追踪结果 | ✅ API 存在 |

**结论：ruyipage Python API 已覆盖 ruyi-mcp 所需核心能力。** Python 桥接方案不存在"底层能力缺失"的风险——唯一的差距是断点调试（需用 `add_preload_script` + Proxy/wrap 模式实现软断点）。

## 9. 待确认项

| # | 确认项 | 优先级 |
|---|--------|:---:|
| 1 | BiDi `script.evaluate` 能否获取函数返回值（非 JSON 的 JS 对象） | 🔴 高 |
| 2 | ruyipage 的网络监听能否获取请求的 JS 调用栈（initiator） | 🔴 高 |
| 3 | ruyitrace 能否与 ruyipage 共享同一 Firefox 进程（profile 冲突） | 🟡 中 |
| 4 | `add_preload_script` 注入的脚本能 Hook 到什么程度（能否包装全局函数） | 🟡 中 |
| 5 | ruyipage `page.capture` 能否实时推送给外部消费者（vs 批量 wait） | 🟢 低 |
