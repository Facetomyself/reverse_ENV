---
name: ruyitrace
description: |
  ruyiTrace — Firefox 内核级 DOM/JS API 追踪。用于网站指纹研究、JS 逆向取证。
  在 C++ 层 Hook 所有 DOM API 调用，输出 NDJSON 日志，页面脚本无法检测。
  配合 ruyipage 指纹浏览器使用：先 ruyipage 自动化访问，再 ruyitrace 做深度追踪。
---

# ruyiTrace — DOM 指纹追踪

## 适用范围

- 分析网站的浏览器指纹采集行为
- 追踪 Canvas/WebGL/Audio/WebRTC/Navigator 等 API 调用
- JS 逆向取证：定位哪些脚本在调用哪些 DOM API
- 生成 NDJSON 日志喂给 AI 分析

如果只需要自动化访问和网络抓包，用 `ruyipage` 即可。

## 本机环境

| 项目 | 值 |
|------|-----|
| 版本 | v1.2（Firefox 151 trace kernel） |
| 内核路径 | `tools\ruyitrace\firefox\firefox.exe` |
| 追踪机制 | `MOZ_DOM_TRACE=1` 环境变量 → C++ 层 Hook |
| 输出格式 | NDJSON（每行一条 API 调用记录） |

## CLI

```powershell
powershell -File "D:\reverse_ENV\tools\ruyitrace\ruyitrace.ps1" -Url "https://target.com" [-Output trace.ndjson] [-Headless]
```

参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-Url` | 目标 URL（必填） | — |
| `-Output` | NDJSON 输出路径 | `$PWD\trace_out.ndjson` |
| `-Profile` | Firefox profile 目录 | 自动创建临时 |
| `-Headless` | 无头模式 | 否 |

## NDJSON 格式

每条记录包含：
```json
{"api": "CanvasRenderingContext2D.fillText", "args": [...], "stack": "file.js:123:45"}
```

### 分析脚本

```bash
# 统计所有分类
python tools\ruyitrace\trace_analyzer.py trace.ndjson

# 只看 Canvas 指纹
python tools\ruyitrace\trace_analyzer.py trace.ndjson -c canvas

# 只看 WebGL
python tools\ruyitrace\trace_analyzer.py trace.ndjson -c webgl
```

覆盖的指纹维度：canvas, webgl, audio, webrtc, navigator, screen, crypto, storage, font, time, webgpu

## 典型工作流

```
1. ruyipage 自动化打开目标页面（处理验证码/登录态）
2. ruyitrace 启动追踪浏览器访问同一页面
3. 在 Firefox 中完成目标操作（触发指纹采集）
4. 关闭 Firefox → NDJSON 自动保存
5. python trace_analyzer.py trace.ndjson 分析指纹维度
6. 将 NDJSON + 分析结果喂给 AI 做深度解读
```

> ⚠️ 追踪浏览器不能与 ruyipage 同时控制同一 profile。追踪期间关闭其他 Firefox 实例。

## 禁止

- 不要删除 `tools\ruyitrace\firefox\RUYI_DOMTRACE.txt` 标记文件
- **禁止登录个人账号** — `MOZ_DOM_TRACE=1` 时 C++ 层记录所有 DOM API 调用到 NDJSON，包括 cookie、表单输入、token。登录 Google/GitHub/邮箱等会导致凭据泄露到追踪日志文件
