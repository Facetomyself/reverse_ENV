# 回退策略

当当前路径无进展时按顺序回退：

1. 从断点回退到请求观察
2. 从源码猜测回退到运行时证据
3. 从 Node 补环境回退到页面取证
4. 从深度去混淆回退到最小可复现链路

证据分流：

- AST 混淆、JSVMP 或 WASM 是核心阻塞时，先把 source、runtime Trace 和脱敏 fixture 交给 `web-deobfuscation` 只读 gate
- JSVMP 有 opcode Trace + request fixture，或 WASM 有可观察 boundary Trace + wrapper fixture 时，可由 `web-deobfuscation` 升到 L3/partial
- VM/WASM 缺 Trace、fixture、稳定 opcode 语义时保持 L4/triage-only
- 强反调试、强反检测、TLS/CDP 痕迹检测、验证码或行为风控仍由本 skill 只做 triage，并回退 `ruyi-reverse`
- triage-only 只能交付已验证证据、阻塞点、可疑模块、下一步路由建议，不得声称完整还原
- 强反检测或指纹对抗优先回退到 `ruyi-reverse`；需要浏览器会话迁移时使用 `ruyi_export_session` 导出 Cookie/Storage 后再桥接到 `js-reverse-mcp`
- 未通过 `web-deobfuscation` validator 的 WASM/VM 目标必须在 `"D:\reverse_ENV\workspace\<项目名>\triage.md"` 标注证据缺口和未还原边界
