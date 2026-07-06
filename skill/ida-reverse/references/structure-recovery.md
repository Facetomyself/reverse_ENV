# 结构体恢复方法论

## 五步恢复流程

### Step 1: 读取目标函数
- 从 IDA 反编译输出读取指定函数的 `.c` 文件
- 解析元数据: callers / callees / 地址
- 识别指针参数（潜在的结构体指针）

### Step 2: 收集内存访问模式
```c
// 直接偏移
*(a1 + 0x10)              // offset 0x10
*(_DWORD *)(a1 + 8)       // offset 0x8, uint32
*(_QWORD *)(a1 + 0x20)    // offset 0x20, uint64

// 数组
*(a1 + 8 * i)             // 元素大小 8 字节

// 嵌套
*(*a1 + 0x10)             // 第一个字段是指针, 再偏移 0x10

// 记录格式: offset=0x00, size=8, access=r/w, type=QWORD
```

### Step 3: 遍历调用者
- 参数来源: `sub_401000(v1)` / `sub_401000(malloc(64))` → 大小 ~64
- 调用前后操作: `*v1 = 0` (offset 0 初始化) / `*(v1 + 8) = cb` (函数指针)
- 收集更多偏移访问

### Step 4: 遍历被调用者
- 参数使用方式: `*(a1 + 0x18)` → 访问 offset 0x18
- 传递给其他函数: `another_func(a1 + 0x20)` → 嵌套结构体

### Step 5: 聚合推断
- 合并所有偏移按 offset 排序
- 计算大小: `max(offset) + last_field_size`
- 推断类型:
  - 作为函数指针调用 → 函数指针
  - 传给 `strlen`/`printf` → 字符串指针
  - 与常量比较 → 枚举/标志位
  - ++/-- 操作 → 计数器/引用计数

## 常见模式

| 模式 | 推断 |
|------|------|
| offset 0 是函数指针表 | vtable (C++ 对象) |
| next/prev 指针对 | 链表节点 |
| refcount 字段 (++/--) | 引用计数对象 |
| size + data 指针 | 缓冲区描述符 |

## 输出格式

```c
// 估算大小: 0x48 字节 | 置信度: 高/中/低
struct suggested_name {
    /* 0x00 */ void *vtable;       // 虚函数表
    /* 0x08 */ int refcount;       // 引用计数
    /* 0x0C */ int flags;          // 标志位 (AND 0x1, 0x2)
    /* 0x10 */ char *name;         // 字符串 (传 strlen)
    /* 0x18 */ void *data;         // 数据指针
    /* 0x20 */ size_t size;
    /* 0x28 */ callback_fn handler; // 回调
};
// 证据: 0x401000: *(this + 0x08)++; 0x401100: printf(*(this + 0x10))
```
