# 自动化入口

推荐开场顺序：

1. `js-reverse_new_page` 或 `js-reverse_navigate_page` 打开页面
2. `js-reverse_list_network_requests` 看最近请求
3. 从 `js-reverse_list_network_requests` 结果里记录目标请求的 `requestId`
4. `js-reverse_get_request_initiator({ "requestId": "<requestId>" })` 找调用栈
5. `js-reverse_list_scripts` 建立脚本范围
6. `js-reverse_search_in_sources` 搜请求路径、参数名、函数名
7. 必要时 `js-reverse_break_on_xhr` 或 `js-reverse_set_breakpoint_on_text`

Observe 记录模板：

```md
## Observe
- 页面：
- 目标请求：
- requestId：
- initiator：
- 可疑脚本：
```

没有 `requestId` 时不要直接调用 `js-reverse_get_request_initiator`，先回到网络列表筛选目标请求。

默认不要一上来就猜 `window`、`document`、`navigator` 该怎么补。
