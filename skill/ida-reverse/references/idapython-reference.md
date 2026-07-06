# IDAPython / IDALib 速查手册

## API 速查

### 寄存器/内存
| 操作 | 代码 |
|------|------|
| 读寄存器 | `idc.get_reg_value('rax')` |
| 写寄存器 | `idaapi.set_reg_val("rax", 1234)` |
| 读调试内存(byte) | `idc.read_dbg_byte(addr)` |
| 读调试内存(块) | `idc.read_dbg_memory(addr, size)` |
| 写调试内存 | `idc.patch_dbg_byte(addr, val)` |
| 读IDB内存 | `idc.get_bytes(addr, size)` |
| 写IDB内存 | `idc.patch_byte(addr, val)` |
| 读字符串 | `idc.get_strlit_contents(addr)` |

### 反汇编
| 操作 | 代码 |
|------|------|
| 获取反汇编文本 | `GetDisasm(addr)` |
| 下一指令 | `idc.next_head(ea)` |
| 创建指令 | `idc.create_insn(addr)` |
| 创建函数 | `ida_funcs.add_func(addr)` |
| 取消定义 | `idc.del_items(addr)` |

### 函数操作
```python
for func in idautils.Functions():
    print("0x%x, %s" % (func, idc.get_func_name(func)))
```

### 交叉引用
```python
for ref in idautils.XrefsTo(ea):
    print(hex(ref.frm))
```

### 基本块遍历
```python
fn = 0x4800
f_blocks = idaapi.FlowChart(idaapi.get_func(fn), flags=idaapi.FC_PREDS)
for block in f_blocks:
    for succ in block.succs():
        print(hex(succ.start_ea))
```

### Hex-Rays 反编译
```python
dec = ida_hexrays.decompile(func_addr)
print(str(dec))
```

## 常用代码片段

### 字节模式搜索
```python
def find_bytes_list(bytes_pattern):
    ea = -1
    result = []
    while True:
        ea = idc.find_bytes(bytes_pattern, ea + 1)
        if ea == ida_idaapi.BADADDR:
            break
        result.append(ea)
    return result
```

### 调试内存读写
```python
def read_dbg_mem(addr, size):
    return bytes(idc.read_dbg_byte(addr + i) for i in range(size))

def patch_dbg_mem(addr, data):
    for i, b in enumerate(data):
        idc.patch_dbg_byte(addr + i, b)
```

### std::string 读取 (x64)
```python
def dbg_read_cppstr_64(obj_addr):
    str_ptr = idc.read_dbg_qword(obj_addr)
    result = ''
    i = 0
    while True:
        b = idc.read_dbg_byte(str_ptr + i)
        if b == 0: break
        result += chr(b)
        i += 1
    return result
```

### 导入表枚举
```python
nimps = ida_nalt.get_import_module_qty()
for i in range(nimps):
    name = ida_nalt.get_import_module_name(i)
    def imp_cb(ea, name, ordinal):
        print("%08x: %s (ordinal #%d)" % (ea, name, ordinal))
        return True
    ida_nalt.enum_import_names(i, imp_cb)
```

### 结构体成员遍历
```python
def extract_struct_members(type_name):
    tif = ida_typeinf.tinfo_t()
    if tif.get_named_type(None, type_name):
        for iter in tif.iter_struct():
            yield {"offset": iter.offset // 8, "size": iter.type.get_size()}
```

### 调用者分析
```python
def ida_get_callees(func_addr):
    callees = []
    for head in idautils.Heads(func_addr, idaapi.get_func(func_addr).end_ea):
        if idaapi.is_call_insn(head):
            callee_ea = idc.get_operand_value(head, 0)
            callees.append(callee_ea)
    return callees
```

### OLLVM 真实块断点
```python
fn = 0x401F60
ollvm_tail = 0x405D4B  # 分发器汇合点
f_blocks = idaapi.FlowChart(idaapi.get_func(fn), flags=idaapi.FC_PREDS)
for block in f_blocks:
    for succ in block.succs():
        if succ.start_ea == ollvm_tail:
            idc.add_bpt(block.start_ea)
```

### NOP 函数
```python
def nop_func(addr_func, arch='arm'):
    func = ida_funcs.get_func(addr_func)
    if arch == 'x86': nop = [0x90]
    elif arch == 'arm': nop = [0x1F, 0x20, 0x03, 0xD5]
    ea = func.start_ea
    while ea < func.end_ea:
        insn = ida_ua.insn_t()
        length = ida_ua.decode_insn(insn, ea)
        for i in range(length):
            idc.patch_byte(ea + i, nop[i % len(nop)])
        ea += length
```

## IDALib (Headless, IDA 9.0+)

```python
import idapro  # 必须第一个 import
import idautils, idc

ida.open_database("target.so", True)
for func in idautils.Functions():
    name = idc.get_func_name(func)
    dec = ida_hexrays.decompile(func)
    print(name, str(dec) if dec else "FAILED")
ida.close_database(save=False)
```

批量反编译到 JSON:
```bash
python decompile.py input.so output.json
```
