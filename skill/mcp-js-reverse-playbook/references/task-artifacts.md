# 任务产物

建议每个任务至少保留：

- 目标请求样例
- initiator 调用栈
- 可疑脚本 URL
- 关键断点位置
- 关键函数入参/返回值
- first divergence 记录
- 每次补环境补丁说明

产物路径硬约束：

- 所有脚本、样本、source dump、日志、截图、trace、任务记录统一放在 `"D:\reverse_ENV\workspace\<项目名>\"`
- 最终必须形成 `"D:\reverse_ENV\workspace\<项目名>\report.md"`、`"D:\reverse_ENV\workspace\<项目名>\findings.json"`、`"D:\reverse_ENV\workspace\<项目名>\triage.md"`
- Node 执行器固定写 `"D:\reverse_ENV\tools\node\node.exe"`，产物和命令示例都不要写裸 `node`
- 如需 Python 辅助处理，必须使用项目内解释器绝对路径 `"D:\reverse_ENV\.venv\Scripts\python.exe"`，不要写裸 `python`
