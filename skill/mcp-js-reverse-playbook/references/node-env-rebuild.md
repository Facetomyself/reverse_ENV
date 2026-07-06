# Node 环境复现

Node 侧默认顺序：

1. 导入目标脚本
2. 最小 shim 宿主对象
3. 跑入口函数
4. 记录首个异常或 first divergence
5. 回到页面证据补齐缺口

执行约束：

- Node 固定使用 `"D:\reverse_ENV\tools\node\node.exe"`，不要写裸 `node`
- 复现脚本、样本输入、source dump、运行日志都放在 `"D:\reverse_ENV\workspace\<项目名>\"` 下
- 命令示例必须使用绝对路径，例如：`"D:\reverse_ENV\tools\node\node.exe" "D:\reverse_ENV\workspace\<项目名>\rebuild\run.js"`
- 本地脚本只能根据页面请求、调用栈、断点、运行时值或复现日志补环境，不能空想式补全浏览器对象
