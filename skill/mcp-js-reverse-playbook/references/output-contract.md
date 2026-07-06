# 输出契约

每次任务输出前必须先落地 workspace 三件套，路径固定在对应项目目录：

- `"D:\reverse_ENV\workspace\<项目名>\report.md"`
- `"D:\reverse_ENV\workspace\<项目名>\findings.json"`
- `"D:\reverse_ENV\workspace\<项目名>\triage.md"`

`report.md` 至少包含：

- 目标请求、参数位置、请求方法和关键 header
- 参与生成的脚本 URL、函数名、断点位置或源码位置
- 当前是否已能稳定复现
- 若未完成，还差哪一个环境缺口

`findings.json` 至少包含结构化 claim。每条 claim 必须指向至少一种证据：

- 请求样例或 `requestId`
- initiator 调用栈
- 断点命中信息
- 运行时值、入参或返回值
- 本地复现日志

`triage.md` 至少包含：

- 当前深度等级：L0/L1/L2/L3/L4
- 已确认事实、待验证假设、阻塞原因
- 是否涉及 WASM/VM/强反调试/强反检测

输出前必须脱敏 Cookie、token、手机号、账号、邮箱、身份证号、精确地理位置、设备唯一标识等敏感字段。脱敏后仍需保留字段名、来源和证据类型，不能因为脱敏丢掉可追溯性。
