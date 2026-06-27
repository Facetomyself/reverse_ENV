---
name: ruyipage
description: |
  ruyiPage — Firefox 指纹浏览器自动化（WebDriver BiDi）。
  用于反检测浏览器操控、过 Cloudflare/验证码、多代理标签页、网络抓包拦截。
  配合 ruyitrace 做深度 DOM 指纹追踪。
---

# ruyiPage 指纹浏览器自动化

## 适用范围

| 场景 | 怎么做 |
|------|--------|
| 过 Cloudflare 5s / hCaptcha / reCAPTCHA | ruyipage 内置反检测 Firefox，直接访问 |
| 多账号 + 独立代理标签页 | `set_per_tab_proxies` + `new_container_tabs` |
| 网络请求抓包/拦截/修改 | `page.capture` / `page.intercept` |
| 浏览器指纹伪装（Canvas/WebGL/时区/语言） | `smart_fingerprint` + `emulation` |
| 页面自动化（登录、爬取、表单填写） | `page.ele` + `page.actions` |
| DOM 深层 API 追踪（指纹取证） | 切 `ruyitrace` skill |

如果只是普通网页请求（不涉及反检测），不需要 ruyipage。

## 本机环境

| 项目 | 值 |
|------|-----|
| Python 包 | `ruyipage` 1.2.43（venv 内） |
| 指纹浏览器 | Firefox 151.0a1（`C:\Users\mengma\AppData\Local\ruyipage\browsers\`） |
| 协议 | WebDriver BiDi（非 CDP） |

## 渐进式披露 — 按深度使用

### L0：快速验证（一行代码）

```python
from ruyipage import FirefoxPage
page = FirefoxPage()
page.get("https://www.browserscan.net/zh")
print(page.title)
page.quit()
```

不需要指定浏览器路径——`FirefoxPage()` 自动查找已安装的 ruyiPage Firefox。

### L1：基础自动化（元素操作 + 表单）

```python
from ruyipage import FirefoxPage

page = FirefoxPage()
page.get("https://example.com/login")

# 定位元素 — 支持 css/xpath/tag/text
page.ele("#username").input("admin")
page.ele("#password").input("password123")
page.ele("tag:button").click_self()

# 获取内容
print(page.ele("css:.result").text)
print(page.html)

page.quit()
```

**元素定位器格式**：`#id` / `css:.class` / `xpath://div` / `tag:input` / `text:登录`

### L2：反检测 + 代理（过验证码）

```python
from ruyipage import FirefoxOptions, FirefoxPage

opts = FirefoxOptions()
opts.set_browser_path(r"C:\Users\mengma\AppData\Local\ruyipage\browsers\firefox-151.0a1-151-ruyi-win64\firefox\firefox.exe")

# 代理
opts.set_proxy("http://127.0.0.1:7890")

# 指纹伪装
ctx = opts.smart_fingerprint(
    proxy_host="proxy.example.com",
    proxy_port=8080,
    proxy_user="user",
    proxy_pwd="pass",
    require_country="US",       # 校验代理出口国家
)

page = FirefoxPage(opts)
ctx.apply_emulation(page)       # 自动设置地理/时区/语言/Headers
page.get("https://bot.sannysoft.com")
page.quit()
```

**smart_fingerprint** 自动检测代理出口 IP 地理位置，生成 22 个硬件指纹维度的匹配配置。如果国家不匹配会抛 `CountryMismatchError`。

### L3：多标签代理池 + 网络拦截

```python
from ruyipage import FirefoxOptions, FirefoxPage

opts = FirefoxOptions()
opts.set_browser_path(r"C:\Users\mengma\AppData\Local\ruyipage\browsers\firefox-151.0a1-151-ruyi-win64\firefox\firefox.exe")

# 每标签页独立 SOCKS5 代理
proxies = [
    "socks5://proxy1.com:1080:user:pass",
    "socks5://proxy2.com:1080:user:pass",
]
opts.set_per_tab_proxies(proxies, exhausted="wrap")
page = FirefoxPage(opts)
tabs = page.new_container_tabs(count=len(proxies), url="https://browserscan.net/")

# 被动抓包
page.capture.start("/api/", method="POST")
page.get("https://target.com")
packets = page.capture.wait(timeout=10, count=5)
for p in packets:
    print(p.url, p.request_body, p.response_body)
page.capture.stop()

# 请求拦截 + 修改
def handler(req):
    if req.url.endswith('.png'):
        req.fail()                               # 阻断图片
    else:
        req.continue_request(headers={"X-Token": "abc"})

page.intercept.start_requests(handler)
page.get("https://target.com")
page.intercept.stop()

page.quit()
```

### L4：人类行为模拟 + 隐身增强

```python
from ruyipage import FirefoxOptions, launch

opts = FirefoxOptions()
opts.set_browser_path(r"C:\Users\mengma\AppData\Local\ruyipage\browsers\firefox-151.0a1-151-ruyi-win64\firefox\firefox.exe")
opts.enable_action_visual(True)   # 鼠标轨迹可视化调试
opts.enable_xpath_picker(True)    # 元素 XPath 拾取器
opts.private_mode(True)           # 隐私模式

page = launch(opts)
page.get("https://target.com")

# 人类行为模拟 — bezier 曲线或 windmouse 算法
btn = page.ele("#submit")
page.actions.human_move(btn, algorithm="bezier", style="arc").perform()
page.actions.human_click(btn, algorithm="windmouse").perform()

# 模拟触摸
page.touch.tap(page.ele("#mobile-btn"))
page.touch.long_press(page.ele("#long-press"))

page.quit()
```

## 元素操作完整参考

```python
el = page.ele("#target")

# 读
el.text          # 文本
el.html          # outerHTML
el.value         # 表单值
el.attr("href")  # 属性

# 写
el.input("text", clear=True)            # 输入文本
el.input(r"D:\file.txt")                # 上传文件（单个）
el.input([r"D:\1.txt", r"D:\2.txt"])    # 上传文件（多个）
el.clear()                               # 清空

# 交互
el.click_self()    # 点击
el.hover()         # 悬停
el.drag_to(other)  # 拖拽

# 链式
page.ele("css:.card").ele("css:h2 a").click_self()
```

## 网络操作速查

| 操作 | API | 场景 |
|------|-----|------|
| 被动抓包 | `page.capture.start/stop/wait` | 监听特定 API 请求 |
| 请求拦截 | `page.intercept.start_requests(handler)` | 修改请求头/阻断/ mock |
| 响应拦截 | `page.intercept.start_responses(handler)` | 读取响应体 |
| 额外请求头 | `page.network.set_extra_headers({...})` | 全局 Headers |
| 缓存控制 | `page.network.set_cache_behavior("bypass")` | 跳过缓存 |

## Cookie 操作

```python
page.get_cookies()                                  # 全部
page.get_cookies_filtered(name="session", all_info=True)  # 按名筛选
page.set_cookies({"name": "t", "value": "v", "domain": "x.com", "path": "/"})
page.set_cookies([{...}, {...}])                    # 批量
page.delete_cookies(name="token")                   # 删特定
page.delete_cookies()                               # 清空
```

## 与其他 skill 的配合

| 配合 | 流程 |
|------|------|
| **ruyitrace** | ruyipage 过验证码拿到登录态 → ruyitrace 做 DOM 指纹追踪 |
| **mcp-js-reverse-playbook** | ruyipage 抓网络包 → mcp-js-reverse-playbook 定位签名 JS |
| **apk-reverse** | ruyipage 截获 APK 内嵌 H5 的网络请求 → apk-reverse 分析 native 层 |

## 约束与禁止

1. **不得在追踪浏览器中登录个人账号** — 所有 DOM API 调用被 C++ 层 Hook 记录
2. **不得在生产环境使用 action_visual** — 鼠标轨迹可视化会留下可检测的 DOM 痕迹
3. **代理认证走 fpfile** — HTTP 代理用户名密码不要明文写在代码里，用 `set_fpfile` 引用外部文件
4. **不要与 ruyitrace 共享同一 profile** — 追踪浏览器和自动化浏览器使用独立 Firefox profile
5. **优先用 `launch()` 而非 `FirefoxPage()`** — 当需要自定义选项时，`launch()` 更简洁

## 快速命令

```python
# 环境检查
python -m ruyipage doctor

# 获取浏览器路径
python -m ruyipage path
```
