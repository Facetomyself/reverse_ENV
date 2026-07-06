# 逆向知识库文章索引

> 自动生成于 2026-07-05 ｜ 来源: `article/`
>
> 新项目启动时，按主题/技术标签检索相关文章，避免重复分析。

## 按分类浏览

### 协议分析 (`article/protocols/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [mmtls-protocol-analysis.md](../article/protocols/mmtls-protocol-analysis.md) | yyb (应用宝) | `mmtls`, `TLS 1.3`, `ECDHE`, `PSK 0-RTT`, `AES-GCM`, `HKDF`, `腾讯私有协议`, `ShortLink`, `iLink`, `NewDNS` | 腾讯 mmtls 协议完整逆向：Record 层帧格式、ECDHE 握手、PSK 0-RTT 快速重连、密码学细节（HKDF/AES-GCM）、ShortLink 应用帧层、iLink 业务层、NewDNS 服务发现 |

### 反检测/风控对抗 (`article/anti-detection/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [51job-anti-detection-analysis.md](../article/anti-detection/51job-anti-detection-analysis.md) | 51job-web-reverse | `阿里ACW WAF`, `飞林FeiLin`, `神策SensorsData`, `Function.toString`, `debugger绕过`, `WebDriver检测`, `CDP检测`, `hook检测`, `反检测对抗矩阵` | 51job 三层风控体系全面分析：ACW WAF 检测向量、飞林设备指纹、神策行为埋点，20+ 检测向量的逐一对抗设计 |
| [chromium-fingerprint-compilation.md](../article/anti-detection/chromium-fingerprint-compilation.md) | — (CSDN 归档) | `Chromium编译`, `指纹浏览器`, `Canvas指纹`, `WebGL指纹`, `WebRTC`, `TLS/JA3/JA4`, `CDP绕过`, `无头检测`, `源码修改`, `BoringSSL`, `V8`, `Blink` | Chromium 源码级指纹浏览器编译全系列 (38篇)：15+ 指纹维度随机化/固定、反检测绕过 (WebDriver/CDP/无头/Selenium)、爬虫增强 (Shadow DOM/跨域iframe/CSS动画禁用)、工程化 (JWT校验/Cookie明文/任务栏徽章) |

### 签名算法 (`article/signature-algorithms/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [qidian-fock-signature.md](../article/signature-algorithms/qidian-fock-signature.md) | qidian (起点读书) | `QDSign`, `Fock SDK`, `AES-CBC`, `HMAC`, `3DES-CBC`, `阅文`, `签名算法`, `7大签名头`, `borgus`, `cecelia`, `gorgon`, `ibex`, `sora` | 起点读书 Fock SDK 7大签名头完整分析：QDSign 算法链、borgus/cecelia/gorgon 生成逻辑、Native 层 key 派生、请求注入点 |

### 加固绕过 (`article/packing-bypass/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [jiagu-bypass-analysis.md](../article/packing-bypass/jiagu-bypass-analysis.md) | qidian (起点读书) | `Jiagu`, `360加固`, `Frida检测`, `ptrace`, `XOR混淆`, `反调试`, `反注入`, `动态解密`, `raise(9)`, `shadow-hook` | 360 Jiagu VIP 版加固绕过：ELF 结构分析、字符串 XOR(0xA5) 混淆还原、反调试机制 (ptrace/TracerPid/raise)、Frida spawn 注入存活方案 |

### Native 分析 (`article/native-analysis/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [qidian-so-analysis.md](../article/native-analysis/qidian-so-analysis.md) | qidian (起点读书) | `libfock.so`, `libfockrt.so`, `ARM64`, `radare2`, `IDA Pro`, `JNI动态注册`, `RSA-1024`, `AES-256-CBC`, `QuickJS` | 起点读书 Native SO 深度分析：libfock.so/libfockrt.so/libnib.so 反编译、QDSign 结构还原、JNI 调用链追踪、QuickJS 引擎角色 |

### Web 逆向 (`article/web-reverse/`)

| 文章 | 来源项目 | 关键词 | 摘要 |
|------|----------|--------|------|
| [51job-webpack-analysis.md](../article/web-reverse/51job-webpack-analysis.md) | 51job-web-reverse | `Webpack 4`, `Vue 2.7`, `模块自吐`, `加密定位`, `sign`, `AES`, `SM4`, `国密`, `webpackJsonp` | 51job Webpack 模块自吐分析：1634 个 factory 模块识别、加密/签名模块定位、Vue 组件反编译、chunk 加载机制 |

---

## 按技术标签检索

### 密码学
- **AES-GCM**: [mmtls](../article/protocols/mmtls-protocol-analysis.md), [qidian-fock](../article/signature-algorithms/qidian-fock-signature.md)
- **AES-CBC**: [qidian-fock](../article/signature-algorithms/qidian-fock-signature.md), [qidian-so](../article/native-analysis/qidian-so-analysis.md)
- **3DES-CBC**: [qidian-fock](../article/signature-algorithms/qidian-fock-signature.md)
- **ECDHE (P-256)**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **HKDF**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **RSA-1024**: [qidian-so](../article/native-analysis/qidian-so-analysis.md)
- **SM4 (国密)**: [51job-webpack](../article/web-reverse/51job-webpack-analysis.md)

### 协议
- **TLS 1.3 变体**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **PSK 0-RTT**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **自定义应用帧**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **HTTP DNS**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)

### 反检测/对抗
- **WAF 绕过**: [51job-anti-detection](../article/anti-detection/51job-anti-detection-analysis.md)
- **设备指纹**: [51job-anti-detection](../article/anti-detection/51job-anti-detection-analysis.md)
- **加固绕过**: [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **反调试 (ptrace/TracerPid)**: [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **Frida 检测绕过**: [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **WebDriver/CDP 检测**: [51job-anti-detection](../article/anti-detection/51job-anti-detection-analysis.md), [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)
- **Chromium 源码修改/指纹浏览器**: [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)
- **TLS/JA3/JA4 指纹**: [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)
- **Canvas/WebGL 指纹**: [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)

### 厂商/平台
- **腾讯 (微信/应用宝)**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **阅文 (起点)**: [qidian-fock](../article/signature-algorithms/qidian-fock-signature.md), [qidian-so](../article/native-analysis/qidian-so-analysis.md), [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **阿里 (ACW/飞林)**: [51job-anti-detection](../article/anti-detection/51job-anti-detection-analysis.md)
- **360 (Jiagu)**: [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **51job**: [51job-anti-detection](../article/anti-detection/51job-anti-detection-analysis.md), [51job-webpack](../article/web-reverse/51job-webpack-analysis.md)
- **CSDN/w1101662433 (fivcan)**: [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)

### 工具/方法
- **Webpack 模块自吐**: [51job-webpack](../article/web-reverse/51job-webpack-analysis.md)
- **抓包+逐字节匹配**: [mmtls](../article/protocols/mmtls-protocol-analysis.md)
- **IDA Pro 静态分析**: [qidian-so](../article/native-analysis/qidian-so-analysis.md), [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **radare2 快速侦察**: [qidian-so](../article/native-analysis/qidian-so-analysis.md)
- **Frida spawn 注入**: [jiagu-bypass](../article/packing-bypass/jiagu-bypass-analysis.md)
- **Chromium 源码编译与修改**: [chromium-fingerprint-compilation](../article/anti-detection/chromium-fingerprint-compilation.md)

---

## 维护规则

1. 新增文章时，在对应分类表添加一行
2. 同步更新「按技术标签检索」中的标签映射
3. 新增分类时，在 `article/` 下创建子目录 + 更新本索引
4. 来源项目列始终指向原始 workspace 项目名
