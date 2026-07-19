# ruyipage Python API 参考（T2 回退）

> **这不是独立 skill。** 仅在 ruyi-mcp 的 `ruyi_*` 工具无法满足需求时回退使用。
> 升级决策见 `references/tier-system.md` 的 T2 升级触发信号。

## 本机环境

| 项目 | 值 |
|------|-----|
| Python 包 | `ruyipage` 1.2.54（`D:\reverse_ENV\.venv\Lib\site-packages\ruyipage\`） |
| 浏览器 | Firefox 151.0a1 `151-proxy`（`D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`） |
| 协议 | WebDriver BiDi |
| 启动 | `"D:\reverse_ENV\.venv\Scripts\python.exe" -m ruyipage` |

## 渐进式披露

### L0：快速验证

```python
from ruyipage import FirefoxPage
page = FirefoxPage()
page.get("https://www.browserscan.net/zh")
print(page.title)
page.quit()
```

### L1：元素操作

```python
page = FirefoxPage()
page.get("https://example.com/login")
page.ele("#username").input("admin")
page.ele("#password").input("password123")
page.ele("tag:button").click_self()
print(page.ele("css:.result").text)
page.quit()
```

**定位器格式**：`#id` / `css:.class` / `xpath://div` / `tag:input` / `text:登录`

### L2：反检测 + 代理

```python
from ruyipage import FirefoxOptions, FirefoxPage

opts = FirefoxOptions()
opts.set_browser_path(r"D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe")
opts.set_proxy("http://127.0.0.1:7890")

ctx = opts.smart_fingerprint(
    proxy_host="proxy.example.com", proxy_port=8080,
    proxy_user="user", proxy_pwd="pass",
    require_country="US",
)
page = FirefoxPage(opts)
ctx.apply_emulation(page)  # screen+geo+locale+timezone+headers；不隐式调整 outer/viewport
page.set_window_size(1280, 720)  # 1.2.54 起仅设置 outer window
page.set_viewport(1200, 700, 1.25)  # 显式 viewport + DPR
page.emulation.set_screen_size(1920, 1080, device_pixel_ratio=1.25)  # runtime 可能忽略 DPR，需实测
page.get("https://bot.sannysoft.com")
page.quit()
```

### L3：多标签代理池 + 网络拦截

```python
opts = FirefoxOptions()
opts.set_browser_path(r"D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe")

ctx = opts.smart_fingerprint(
    manual_geo={
        "ip": "203.0.113.10", "country_code": "US",
        "timezone": "America/New_York",
        "latitude": 40.7128, "longitude": -74.0060,
    }
)

# 每标签独立 SOCKS5
opts.set_per_tab_proxies(
    ["socks5://p1:1080:user:pass", "socks5://p2:1080:user:pass"],
    exhausted="wrap"
)
page = FirefoxPage(opts)
tabs = [page.new_container_tab(url=None) for _ in range(2)]
for tab in tabs:
    ctx.apply_emulation(tab)  # container 首跳前重放完整 fingerprint
    tab.get("https://browserscan.net/")

# 流式抓包
page.capture.start("/api/", method="POST")
page.get("https://target.com")
packets = page.capture.wait(timeout=10, count=5)
# 上游合同：count=1 -> CapturePacket | None；count>1 -> list[CapturePacket]
# ruyi-mcp 在 Python Bridge 边界统一为 MCP result.packets 数组。

# 自定义拦截
def handler(req):
    if req.url.endswith('.png'): req.fail()
    else: req.continue_request(headers={"X-Token": compute_signature(req)})
page.intercept.start_requests(handler)
```

### L4：人类模拟 + 隐身

```python
opts = FirefoxOptions()
opts.set_browser_path(r"D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe")
opts.enable_action_visual(True)
opts.private_mode(True)

page = FirefoxPage(opts)
page.get("https://target.com")

btn = page.ele("#submit")
page.actions.human_move(btn, algorithm="bezier", style="arc").perform()
page.actions.human_click(btn, algorithm="windmouse").perform()
page.actions.move_to(btn).hold().wait(0.12).human_move(
    page.ele("#drop-target"), algorithm="windmouse"
).wait(0.08).release().perform()
# 触摸: page.touch.tap(page.ele("#mobile-btn"))
```

---

## 元素操作

```python
el = page.ele("#target")

# 读
el.text           # 文本
el.html           # outerHTML
el.value          # 表单值
el.attr("href")   # 属性

# 写
el.input("text", clear=True)
el.input(r"D:\file.txt")               # 上传文件
el.clear()

# 交互
el.click_self()   # 点击
el.hover()        # 悬停
el.drag_to(other) # 拖拽

# 链式
page.ele("css:.card").ele("css:h2 a").click_self()
```

## 网络操作

| 操作 | API |
|------|-----|
| 被动抓包 | `page.capture.start/stop/wait` |
| 请求拦截 | `page.intercept.start_requests(handler)` |
| 响应拦截 | `page.intercept.start_responses(handler)` |
| 全局 Headers | `page.network.set_extra_headers({...})` |
| 缓存控制 | `page.network.set_cache_behavior("bypass")` |

## Cookie 操作

```python
page.get_cookies()
page.get_cookies_filtered(name="session", all_info=True)
page.set_cookies({"name": "t", "value": "v", "domain": "x.com", "path": "/"})
page.set_cookies([{...}, {...}])
page.delete_cookies(name="token")
page.delete_cookies()  # 全部
```

## 约束

1. **`smart_fingerprint` 依赖代理出口 IP** — 无代理时指纹不完整
2. **不与 ruyitrace 共享 Firefox profile**
3. **Firefox 151.0a1 是定制版** — 不指向系统 Firefox
4. **优先用 ruyi_* MCP 工具** — 本参考仅在 MCP 不足时使用

## 快速命令

```bash
"D:\reverse_ENV\.venv\Scripts\python.exe" -m ruyipage doctor   # 环境检查
"D:\reverse_ENV\.venv\Scripts\python.exe" -m ruyipage path     # 浏览器路径
```
