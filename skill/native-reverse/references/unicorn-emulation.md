# Unicorn 模拟执行调试

## 核心原则

1. **Raw 加载优先** — 不解析 ELF/PE 头，直接 `mmap` 到 Unicorn 内存
2. **识别上下文依赖** — 分析目标对外部调用 (JNI/syscall/libc) 的依赖，Hook 模拟
3. **充分利用回调** — `UC_HOOK_CODE`/`UC_HOOK_BLOCK`/`UC_HOOK_MEM_*`
4. **迭代修复** — 模拟崩溃 → 用回调信息诊断 → 修复 → 重新运行

## 环境模拟策略

| 类别 | 示例 | 模拟方法 |
|------|------|---------|
| libc | `malloc`, `memcpy`, `strlen` | Hook 地址 → Python 实现 (bump allocator) |
| JNI | `GetStringUTFChars`, `FindClass` | 构造假 JNIEnv 函数表 → RET stub |
| Syscall | `read`, `write`, `mmap` | `UC_HOOK_INTR` → 按 syscall 编号分发 |
| C++ | `operator new`, `__cxa_throw` | Hook + 返回 stub |

**Hook 模式**: `UC_HOOK_CODE` → PC 命中已知导入地址时执行 Python 模拟 → 设 PC=LR 跳过原函数

## 回调类型

| 回调 | 用途 |
|------|------|
| `UC_HOOK_CODE` | 拦截导入调用 (按地址) |
| `UC_HOOK_BLOCK` | 块级追踪 (优先于指令级) |
| `UC_HOOK_MEM_UNMAPPED` | 自动映射缺失页 |
| `UC_HOOK_INTR` | SVC/INT 拦截 (syscall 模拟) |

## 迭代调试循环

```
1. Run → 崩溃
2. 读回调输出 → 哪个地址? 什么类型?
3. 诊断 → 缺代码页(映射) / 缺数据(映射/hook) / 导入桩(加模拟hook) / 死循环(加计数器)
4. 修复 → 添加 hook / 映射内存 / 调整寄存器
5. Re-run → 重复直到完成
```

## 架构速查

| Arch | SP | LR | Args | Return | Syscall |
|------|----|----|------|--------|---------|
| ARM64 | SP | X30 | X0-X7 | X0 | X8 + SVC #0 |
| ARM32 | SP | LR | R0-R3 | R0 | R7 + SVC #0 |
| x86-64 | RSP | (stack) | RDI,RSI,RDX,RCX,R8,R9 | RAX | RAX + syscall |
| x86-32 | ESP | (stack) | (stack) | EAX | EAX + int 0x80 |
| MIPS32 | $sp | $ra | $a0-$a3 | $v0 | $v0 + syscall |

## 最小示例 (ARM64)

```python
from unicorn import *
from unicorn.arm64_const import *

# 加载原始字节到 0x400000
with open("target_func.bin", "rb") as f:
    code = f.read()

mu = Uc(UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN)
mu.mem_map(0x400000, 0x200000)
mu.mem_write(0x400000, code)
mu.mem_map(0x0, 0x10000)  # stack
mu.reg_write(UC_ARM64_REG_SP, 0xF000)

# Hook 未映射内存
def hook_unmapped(uc, access, address, size, value, user_data):
    uc.mem_map(address & ~0xFFF, 0x1000)
    return True

mu.hook_add(UC_HOOK_MEM_UNMAPPED, hook_unmapped)

mu.emu_start(0x400000, 0x400000 + len(code))
print("X0:", mu.reg_read(UC_ARM64_REG_X0))
```
