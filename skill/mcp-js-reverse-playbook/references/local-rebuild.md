# 本地复现

页面侧确认以下内容后再回到 Node：

- 真实入口函数
- 调用顺序
- 参数来源
- 依赖的浏览器对象
- 是否依赖时间、随机数、storage、cookie、UA、canvas、crypto

先最小复现，再逐步补环境，不要一次性模拟整浏览器。

本地复现落盘约束：

- Node 固定使用 `"D:\reverse_ENV\tools\node\node.exe"`，不要写裸 `node`
- 复现脚本、依赖脚本、source dump、样本请求、运行日志统一放入 `"D:\reverse_ENV\workspace\<项目名>\"`
- `js-reverse_save_script_source` 保存源码时 `filePath` 必须使用 `"D:\reverse_ENV\workspace\<项目名>\..."` 绝对路径
- 截图、trace、临时观察记录也放入对应项目目录，不放在 skill 目录或仓库根目录
