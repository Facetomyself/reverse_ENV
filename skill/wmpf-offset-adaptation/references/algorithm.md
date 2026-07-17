# WMPF 偏移提取算法

## `.pdata` 函数边界

x64 PE 的 `.pdata` 由 12 字节 `RUNTIME_FUNCTION` 项组成：

```text
BeginRVA, EndRVA, UnwindRVA
```

用 `BeginRVA <= target_rva < EndRVA` 确定函数边界，比扫描 `0xCC` 或猜测 prologue 稳定。所有输出保持 RVA 语义。

## `CDPFilterHookOffset`

1. 搜索 ASCII `SendToClientFilter`。
2. 在可执行节查找 RIP-relative `lea` 对该字符串的引用。
3. 用 `.pdata` 找到包含引用点的父函数。
4. 从父函数入口向后扫描第一条 `E8 call rel32`。
5. 计算 `target_rva = call_rva + 5 + rel32`。

该 target RVA 才是 `CDPFilterHookOffset`。不要把字符串 helper、引用点或父函数入口误当成最终偏移。

## `LoadStartHookOffset`

遍历合理大小的 `.pdata` 函数，解析函数体内 RIP-relative 字符串引用。目标函数必须同时包含：

- `applet_index_container.cc`
- `AppletIndexContainer::OnLoadStart(bool`

匹配函数的 `BeginRVA` 是 `LoadStartHookOffset`。普通 `OnLoadStart` 日志包装函数很多，只命中函数名不足以确认。

## `SceneOffsets`

从 `OnLoadStart` 尾部调用链恢复六段指针链：

```text
p1 = read(this + offset0)
p2 = read(p1 + offset1)
p3 = read(p2 + offset2)
p4 = read(p3 + offset3)
p5 = read(p4 + offset4)
scene_addr = p5 + offset5
```

典型证据包括：

- `this + 0x40`
- 下一层版本相关偏移
- callee 中的 `+0x8`、版本相关容器偏移、`+0x10`
- `cmp dword ptr [...+0x1C8], 0x44D`

最后一段 `offset5` 是字段地址，不再 `readPointer`。邻近版本的数值只用于发现异常，不能替代目标 DLL 证据。

## IDA 复核映射

项目使用 `ida-multi-mcp`，不是上游文档中的 Cursor `idalib-mcp` 配置。最小工具链：

```text
idalib_open
  -> survey_binary(detail_level="minimal")
  -> find_regex
  -> xrefs_to
  -> analyze_function / disasm
  -> get_bytes（必要时验证 E8 与 rel32）
```

只分析三个 marker 对应的局部函数。若 GUI 正在占用同一 IDB，关闭 GUI 或改用现有 GUI MCP 实例，不要删除数据库文件。

## 结果审查

- 两个 Hook offset 落在 PE 映像 RVA 范围。
- `SceneOffsets` 长度固定为 6。
- `Version` 与输入目录/目标版本一致。
- 输入 DLL SHA-256、脚本输出、IDA 证据和运行时状态可追溯。
- 没有运行时证据时只标 `static-verified / runtime-pending`。
