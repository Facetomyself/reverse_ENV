# Shadow Hook 隐身工具参考

从 [rust-frida-shadow-hook](https://github.com/bibinocode/rust-frida-shadow-hook) 提取的隐身技术工具集。

## 工具目录

```
third_party/shadow-hook/             # install_skill_tools.py 复制后的工程副本
├── hide-soinfo-agent.js       # dl_iterate_phdr / /proc/maps 过滤
├── signal-chain-agent.js      # ART FaultManager 兼容信号链 + OAT NULL header fix
├── vma-hide-agent.js          # prctl VMA 匿名重命名
├── shadow-agent-gadget.js     # 复合隐身 agent (signal→stealth→vma)
├── stealth-runner.py          # Python CLI 编排器
└── README.md                  # 完整使用手册

tools/hide-soinfo/             # 待建：C 原生 soinfo 摘除库，当前 Skill 未内置
tools/stealth-hook-engine/     # 待建：ARM64 inline hook 引擎，当前 Skill 未内置
tools/memfd-inject/            # 待建：memfd 隐身注入器，当前 Skill 未内置
```

## 触发场景

| 场景 | 推荐工具 | 模式 |
|------|---------|------|
| 目标 app 通过 dl_iterate_phdr / /proc/maps 检测 Frida | `hide-soinfo-agent.js` 或 `shadow-agent-gadget.js` | stealth / all |
| Hook Java 方法后 ART 崩溃 (WalkStack / OAT header) | `signal-chain-agent.js` | signal |
| app 扫描匿名 RWX 映射检测注入 | `vma-hide-agent.js` | vma |
| 完整隐身（全栈保护） | `shadow-agent-gadget.js` 或 `third_party/shadow-hook/stealth-runner.py --mode all` | all |
| 需要从 linker soinfo 链表真正摘除 | `tools/hide-soinfo/`（待建，当前 Skill 未内置） | — |
| 需要替代 Frida Interceptor 的 inline hook | `tools/stealth-hook-engine/`（待建，当前 Skill 未内置） | — |

## 分层防御

```
Layer 0: 注入器隐身    → memfd-inject (待建，当前 Skill 未内置)
Layer 1: SO 枚举隐身    → hide-soinfo-agent.js (dl_iterate_phdr + maps 过滤)
Layer 2: VMA 隐身       → vma-hide-agent.js (RWX 映射重命名)
Layer 3: 崩溃保护       → signal-chain-agent.js (ART FaultManager chain)
Layer 4: 内核级隐身     → xiaojianbang-stealth-hook KPM (HWBP + PTE + MapsHide)
```

## 与现有工具的协作

- **hide-soinfo-agent.js** 配合 **Frida gadget** → gadget 注入后自动过滤自身
- **signal-chain-agent.js** 配合 **frida_memdump_so.py** → dump 期间防止 ART 崩溃
- **shadow-agent-gadget.js** 配合 **stealth_hook_android.py** → Frida 层隐身 + 内核层隐身
- **vma-hide-agent.js** 配合 **ecapture_android.py** → eCapture 也产生匿名映射，需要隐藏

## 改编来源

所有技术移植自 rust-frida-shadow-hook 的以下源文件：
- `agent/src/hide_soinfo.c` — 版本无关 linker soinfo 摘除
- `agent/src/crash_handler.rs` — 信号处理 + ART FaultManager chain + OAT NULL header fix
- `agent/src/vma_name.rs` — prctl PR_SET_VMA_ANON_NAME 封装
- `agent/src/exec_mem.rs` — RWX 可执行内存分配 + VMA 命名
- `agent/src/recompiler.rs` — 页级代码重编译 (stealth hook, 需要自定义内核)
- `quickjs-hook/src/hook_engine.c` — ARM64 inline hook 引擎
