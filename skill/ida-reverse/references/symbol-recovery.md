# 符号恢复方法论

## 三步式恢复

### Step 1: 内部特征分析

逐函数检查:
- **字符串常量**: 函数内引用的字符串揭示用途
- **Magic Number**:
  - MD5: `0x67452301`, `0xEFCDAB89`, `0x98BADCFE`, `0x10325476`
  - CRC32: `0xEDB88320`
  - Base64: 字符集 `ABCDEFGH...789+/`
  - AES S-Box: `0x63, 0x7C, 0x77, 0x7B...`
  - Zlib: 头 `0x78 0x9C`
- **代码结构**: 循环模式、位运算、算法流程

### Step 2: 交叉引用分析

**从被调用函数 (callees) 推断:**
- 查 `imports.txt` 匹配已知导入
- 配对模式识别:
  - `malloc/free`, `new/delete` → 内存管理
  - `mutex_lock/unlock` → 线程同步
  - `fopen/fclose`, `socket/close` → 资源管理
  - `pthread_create/join` → 线程创建

**参数模式识别:**
```c
// socket(AF_INET, SOCK_STREAM, 0)
sub_XXX(2, 1, 0);

// memset(ptr, 0, 0x100)
sub_XXX(ptr, 0, 0x100);

// strcmp(s1, s2) or strncmp(s1, s2, n)
if (sub_XXX(s1, s2) == 0)

// memcpy(dst, src, size) — 3参数: dst, src, count
sub_XXX(dst, src, n);
```

**返回值模式:**
```c
// 文件/网络操作: -1 = 错误
if ((fd = sub_XXX(...)) == -1) goto error;
// 分配: NULL = 失败
if (!(ptr = sub_XXX(size))) goto error;
// strlen: 返回 size_t → 配合 memcpy 使用
len = sub_XXX(str); sub_YYY(dst, src, len);
```

**从调用者 (callers) 推断:**
- 向上追溯调用链，直到找到有符号的函数
- 分析调用者对返回值的用途

### Step 3: 信息搜集与搜索

1. 本地推理: 函数签名 + 配对模式 + 导入 + 代码结构
2. 不确定时搜索: `0x67452301 algorithm` / 代码特征 / 字符串

## 输出格式

```
## 符号恢复: <0x地址>
### 特征: 字符串 / 常量 / 导入
### 交叉引用: callers / callees
### 推断: 建议符号名 | 置信度: 高/中/低 | 理由
### 参考: 开源实现链接
```
