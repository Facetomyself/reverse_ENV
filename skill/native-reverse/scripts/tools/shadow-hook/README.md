# Shadow Hook 隐身工具集

从 [rust-frida-shadow-hook](https://github.com/bibinocode/rust-frida-shadow-hook) 提取并移植的 Frida JS 隐身工具。

## 工具清单

| 文件 | 功能 | 来源 |
|------|------|------|
| `hide-soinfo-agent.js` | dl_iterate_phdr 回调过滤 + /proc/maps read 过滤 + dladdr 混淆 | `agent/src/hide_soinfo.c` |
| `signal-chain-agent.js` | ART FaultManager 兼容信号链 + OAT NULL header 修复 | `agent/src/crash_handler.rs` |
| `vma-hide-agent.js` | prctl(PR_SET_VMA_ANON_NAME) 匿名 RWX 映射重命名 | `agent/src/vma_name.rs` + `exec_mem.rs` |
| `shadow-agent-gadget.js` | 复合隐身 agent（signal → stealth → vma 按序编排） | 综合 |
| `stealth-runner.py` | Python CLI 编排器 | 新增 |

## 快速开始

### CLI 注入（推荐）

```bash
# 完整隐身模式
python stealth-runner.py --package com.example --mode all

# 仅信号链保护（最安全）
python stealth-runner.py --package com.example --mode signal

# 仅 SO 隐藏
python stealth-runner.py --pid 12345 --mode stealth

# 带额外模式的 SO 隐藏
python stealth-runner.py --package com.example --mode stealth --extra-patterns "libbaidu,libtencent"
```

### 手动 Frida CLI

```bash
# 完整隐身
frida -U -l shadow-agent-gadget.js com.example

# 单独使用任何一个 agent
frida -U -l hide-soinfo-agent.js com.example
frida -U -l signal-chain-agent.js com.example
frida -U -l vma-hide-agent.js com.example
```

### Gadget 模式

1. 将 agent 脚本 push 到设备：
```bash
python stealth-runner.py --deploy-gadget-config --package com.example --mode all
```

2. 将生成的 `gadget.config.example.json` 内容合并到 APK 的 `lib/<abi>/libgadget.config.so`

## 能力边界

| 技术 | Frida JS 版 | C 原生版 (hide_soinfo.c) |
|------|------------|--------------------------|
| dl_iterate_phdr 过滤 | ✅ callback wrap | ✅ 真正从 solist 摘除 |
| /proc/self/maps 过滤 | ✅ read hook | ✅ show_map_vma 内核级过滤 |
| r_debug link_map 隐藏 | ❌ 无法安全修改 | ✅ 双向链表摘除 + 恢复 |
| 内核 solist 摘除 | ❌ 需要 linker 内部调用 | ✅ __dl__Z20solist_remove_soinfo |
| VMA 匿名重命名 | ✅ prctl syscall | ✅ 同 |
| 信号链 ART 兼容 | ✅ setExceptionHandler | ✅ sigaction chain |
| OAT NULL header fix | ⚠️ 检测但无法寄存器级修复 | ✅ ucontext 寄存器替换 |

> **Frida JS 版是"过滤器"**，C 原生版是"摘除器"。对于绝大多数通过公开 API 检测的 SDK，Frida JS 版已够用。C 原生版目录 `tools/hide-soinfo/` 当前未内置，属于待建资产；需要对抗内核级或 linker 内部遍历时，先补齐该工程副本并记录来源、license 和 hash。

## 与 C 原生工具的关系

```
                    ┌─────────────────────────┐
                    │   shadow-agent-gadget.js  │  ← Frida JS 复合 agent
                    └───────────┬─────────────┘
                                │ 桥接（编译后 LD_PRELOAD）
                    ┌───────────▼─────────────┐
                    │  tools/hide-soinfo/       │  ← 待建：C 原生 .so
                    │  libhide_soinfo.so        │     .init_array 自动执行
                    └──────────────────────────┘
```

当需要真正的 soinfo 链表摘除时，将 `libhide_soinfo.so` 与 Frida gadget 一起部署，通过 `LD_PRELOAD` 或 gadget config 的 `preload_libraries` 字段加载。

## 改编说明

所有脚本改编自 rust-frida-shadow-hook 的以下源文件：
- `agent/src/hide_soinfo.c` — 版本无关 linker 内部 soinfo 摘除
- `agent/src/crash_handler.rs` — 信号处理 + ART FaultManager chain + OAT NULL header fix
- `agent/src/vma_name.rs` — prctl PR_SET_VMA_ANON_NAME 封装
- `agent/src/exec_mem.rs` — RWX 可执行内存分配 + VMA 命名

改编约束：
- Frida JS 无法直接调用 linker 内部函数 → 改为 hook 公开 API 做过滤
- Frida setExceptionHandler 无法修改 ucontext 寄存器 → 返回 false chain 到旧 handler
- 保持与原项目的命名约定和架构设计一致性
