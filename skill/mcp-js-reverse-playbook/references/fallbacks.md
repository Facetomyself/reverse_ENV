# 回退策略

当当前路径无进展时按顺序回退：

1. 从断点回退到请求观察
2. 从源码猜测回退到运行时证据
3. 从 Node 补环境回退到页面取证
4. 从深度去混淆回退到最小可复现链路

L4 边界：

- 遇到 WASM、VM 虚拟机保护、强反调试、强反检测、TLS/CDP 痕迹检测、验证码或行为风控时，本 skill 只做 triage-only
- triage-only 只能交付已验证证据、阻塞点、可疑模块、下一步路由建议，不得声称完整还原
- 强反检测或指纹对抗优先回退到 `ruyi-reverse`；需要浏览器会话迁移时使用 `ruyi_export_session` 导出 Cookie/Storage 后再桥接到 `js-reverse-mcp`
- WASM/VM 目标必须在 `"D:\reverse_ENV\workspace\<项目名>\triage.md"` 标注 L4、证据来源和未还原边界
