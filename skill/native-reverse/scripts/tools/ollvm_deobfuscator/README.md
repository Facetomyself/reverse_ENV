# OLLVM Universal Deobfuscator

通用 OLLVM 反混淆工具，基于 Unicorn 模拟执行，支持 ARM64 ELF 共享库的自动化混淆还原。

| | |
|------|------|
| 作者 | **小肩膀** |
| 微信 | xiaojianbang8888 |
| 官网 | https://xjbedu.site |
| B站 | https://space.bilibili.com/534838862 |
| 公众号 | 非攻code |
| 知识星球 | 小肩膀和他的朋友们 |

**平台定位：**
- **B站**：免费视频教程（爬虫、JS、Android、iOS逆向、浏览器内核）
- **公众号（非攻code）**：免费技术文章
- **知识星球（小肩膀和他的朋友们）**：可直接落地的技术方案、源码、成品工具

---

## 支持的混淆类型

| 混淆类型 | 说明 | 通用性 |
|---------|------|--------|
| 控制流平坦化 (CFF) | 状态机驱动的 dispatcher + 比较树 | ✓ 通用（含魔改变体） |
| 间接跳转 (BR) | 表驱动的计算跳转 | ✓ 通用 |
| 间接函数调用 (BLR) | 多层间接寻址的函数调用 | ✓ 通用 |
| 虚假控制流 (BCF) | 不透明谓词产生的虚假分支 | ✓ 通用 |

## 环境要求

- Python 3.8+
- capstone >= 5.0
- unicorn >= 2.0
- keystone-engine >= 0.9

```bash
pip install capstone unicorn keystone-engine
```

## 使用方法

### 基本用法

```bash
python ollvm_deobfuscator.py <input.so> <start_hex> <end_hex> [-o output.so] [--type auto|cff|indirect]
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `input` | 输入的 .so 文件路径 |
| `start` | 函数起始地址（十六进制） |
| `end` | 函数结束地址（十六进制） |
| `-o, --output` | 输出文件路径（默认：input.patched.so） |
| `--type` | 混淆类型：`auto`（自动检测）、`cff`、`indirect` |

### 使用示例

```bash
# CFF / BCF 还原（自动检测）
python ollvm_deobfuscator.py input.so 0x14400 0x14898 -o output.so

# 间接跳转还原
python ollvm_deobfuscator.py input.so 0xd5cc 0xdbc8 --type indirect -o output.so

# 处理同一 so 中的多个函数
python ollvm_deobfuscator.py input.so 0x14400 0x14898 -o step1.so
python ollvm_deobfuscator.py step1.so 0x95c8 0xa960 -o step2.so
python ollvm_deobfuscator.py step2.so 0x13728 0x13a48 -o final.so
```

本 Skill 不随包分发测试样本 `.so`。使用前先按 `workflow-standards.md` 的函数范围确认规则确定目标函数起止地址，再对项目副本中的真实目标 so 运行工具。

## 如何确定函数地址范围

1. 用 IDA Pro 打开 .so 文件
2. 在 Exports 窗口找到目标函数
3. 函数起始地址：IDA 显示的函数头地址
4. 函数结束地址：RET 指令地址 + 4（或下一个函数的起始地址）

## 工作原理

### CFF 还原流程

```
基本块划分 → 找Dispatcher → 找状态寄存器 → 数据流分类真实块
→ Unicorn模拟恢复控制流 → 消除虚假分支 → Patch + NOP
```

### 间接跳转还原流程

```
扫描BR/BLR → 提取rebase常量 → 模拟常量区域
→ 对每个BR模拟读取目标 → 重定位表回退解析BLR → Patch
```

## 输出说明

```
[*] Input:  input.so
[*] Range:  0x14400 - 0x14898
[*] Loaded ELF with 2 LOAD segments
[*] Extracted 51 basic blocks
[*] Detected obfuscation type: cff
[CFF] Dispatcher found at 0x144a0 (fan-in: 20)
[CFF] State register: w8
[CFF] Real blocks: 21, Dispatch blocks: 30
[CFF] Flow graph recovered: 21 nodes

[CFF] Applying patches...
  0x14400 -> B 0x14580
  0x14580 -> B 0x14848
  ...
[PATCH] Saved to output.so (20 patches applied)
[*] Done!
```

## 验证结果

将 patched .so 文件拖入 IDA：
1. 按 `G` 跳转到目标函数地址
2. 按 `P` 重新识别函数（如需要）
3. 按 `F5` 查看反编译结果
4. 对比原始混淆版本，确认控制流清晰可读

## 相关文章

- OLLVM还原（一）：控制流平坦化还原
- OLLVM还原（二）：间接跳转还原
- OLLVM还原（三）：间接函数调用还原
- OLLVM还原（四）：虚假控制流还原
- OLLVM还原（五）：适配魔改OLLVM

## License

仅供学习研究使用。

---

## 联系作者

有问题或建议，欢迎通过以下方式联系：

- **微信**：xiaojianbang8888
- **官网**：https://xjbedu.site
- **B站**：https://space.bilibili.com/534838862
- **公众号**：非攻code
- **知识星球**：小肩膀和他的朋友们
