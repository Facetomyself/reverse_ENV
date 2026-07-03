# 架构与代码分析 — xiaojianbang-syscall-filter

> 作者：小肩膀　微信：xiaojianbang8888
>
> 本文档面向想读懂/改造代码的人，详细记录模块的实现原理、关键数据结构、踩过的坑。
> 只想用工具看 [README.md](./README.md)。

---

## 1. 总体架构

整套工具分三层，跨「内核态模块」「设备端脚本」「PC 端脚本」：

```
┌─────────────────────── PC (开发机) ───────────────────────┐
│  load.sh         加载/卸载/运行时控制（经 adb + libkpatch）   │
│  capture_live.sh 流式采集 dmesg + 调度解析                  │
│  resolve.py      地址→so!偏移 解析（--kresolve / --mapsdir） │
└───────────────┬───────────────────────────────────────────┘
                │ adb shell su -c
┌───────────────▼─────────────── Android 设备 ──────────────┐
│  libkpatch.so    APatch 自带的 KPM 管理 CLI                 │
│  scf_snap.sh     设备端 maps 快照器（resolve=off 时用）      │
│  ┌──────────────────── 内核态 ────────────────────────┐    │
│  │  syscallhook.kpm  ← 本项目核心                       │    │
│  │   fp_hook 9 个 path 类 syscall                       │    │
│  │   exitmon=on 时再 fp_hook 8 个退出/发信号 syscall     │    │
│  │   memmon=on 时再 fp_hook 内存/线程/ptrace syscall     │    │
│  │   path: UID 过滤 → 关键词匹配 → trace + 伪造 -ENOENT │    │
│  │   exit/signal: UID 过滤 → trace 调用点，不改返回值    │    │
│  │   memmon: UID 过滤 → after ret → trace，不改返回值     │    │
│  │   resolve=on 时内核态解析调用者 so!偏移              │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

数据流：App 发起 syscall → 内核 hook 回调 → 命中规则 → `pr_info` 写内核 log →
`dmesg -w` 流式传到 PC → 分类/解析成 `logs/*.log`。

---

## 2. 内核模块 syscallhook.c

### 2.1 它是什么

一个 **KernelPatch Module (KPM)**——APatch/KernelPatch 的可加载内核模块。
编译产物 `syscallhook.kpm` 是一个 ELF 可重定位文件，由 `libkpatch.so kpm load`
在运行时加载进内核、做重定位、调用 `KPM_INIT` 注册的入口。

三个生命周期入口（文件末尾）：
```c
KPM_INIT(mod_init);   // 加载时：解析符号 + 注册 hook
KPM_CTL0(mod_ctl0);   // 运行时：接收控制命令（kpm ctl0）
KPM_EXIT(mod_exit);   // 卸载时：解除所有 hook
```

### 2.2 Hook 机制

用 KernelPatch 的 `fp_hook_syscalln`（function-pointer hook，改 sys_call_table 指针）
挂三类系统调用：

1. 加载时默认注册 9 个 **path 类 syscall**，用于隐藏 root/frida/xposed/aosp 路径检测；
2. `exitmon=on` 时动态注册 8 个 **退出/发信号 syscall**，用于定位秒闪退/自杀逻辑；
3. `memmon=on` 时动态注册 **内存/线程/ptrace syscall**，用于定位匿名执行段、memfd、VMA 命名和 watcher 线程。

path 类 syscall：

```c
static struct sc_hook hooks[] = {
    { __NR_faccessat, 3, ... },   { __NR_faccessat2, 4, ... },
    { __NR_openat, 4, ... },      { __NR_openat2, 4, ... },
    { __NR3264_fstatat, 4, ... }, // newfstatat
    { __NR_readlinkat, 4, ... },  { __NR_statx, 5, ... },
    { __NR_execve, 3, ... },      { __NR_name_to_handle_at, 5, ... },
};
```

选这 9 个的依据：它们都有一个用户态路径指针参数，是 App 做文件存在性检测的入口。
每个 syscall 一个 `before_xxx` 薄包装，统一转调 `handle_path_syscall(args, 名字, 路径参数下标)`。

> `newfstatat` 用 `__NR3264_fstatat`(=79)：`__NR_newfstatat` 宏被 `#if defined(__ARCH_WANT_NEW_STAT)`
> 包住，模块编译环境没定义该宏，直接用无条件的 `__NR3264_fstatat`。

退出/发信号类 syscall：

```c
{ __NR_exit, 1, ... },
{ __NR_exit_group, 1, ... },
{ __NR_kill, 2, ... },
{ __NR_tkill, 2, ... },
{ __NR_tgkill, 3, ... },
{ __NR_rt_sigqueueinfo, 3, ... },
{ __NR_rt_tgsigqueueinfo, 4, ... },
{ __NR_pidfd_send_signal, 4, ... }, // 仅当内核头定义该宏
```

它们不做拦截、不伪造返回，只打印调用点。这样不会改变 App 退出行为，但能在进程死亡前
把 `pc/lr -> so!offset` 固化到内核日志里。特别是 native 主动崩溃常见的：

```text
tgkill(getpid(), gettid(), SIGABRT)
kill(getpid(), SIGKILL)
exit_group(status)
```

都能被记录。

### 2.3 核心处理流程 handle_path_syscall

```
current_uid() ──不在 target_uids[] → return（过滤非目标 App）
   │
   ├─ syscall_argn(args, path_argi) 取用户态路径指针
   ├─ compat_strncpy_from_user 把路径拷进内核 buf（用户内存不能直接解引用）
   ├─ match_path(buf) 子串匹配 kw_rules[] → 命中分类 cat
   ├─ get_user_regs(args) 取 pc/lr/sp
   ├─ 取 tgid / comm
   ├─ resolve=on 时 resolve_addr() 解析 pc/lr → pcsym/lrsym
   ├─ 命中 → pr_info 打印；未命中 + dump=on → pr_info DUMP 行
   └─ fake=on + 命中 → args->skip_origin=1; args->ret=-ENOENT（跳过真实调用，伪造不存在）
```

关键点：
- **UID 过滤优先**：`uid_is_target` 不中直接返回，零开销放过全机其它进程。
- **读用户态字符串**必须用 `compat_strncpy_from_user`，不能直接 `strlen(p)`——
  `p` 是用户空间指针，内核直接解引用会 oops。
- **伪造返回**靠 hook 框架的 `args->skip_origin` + `args->ret`：置 skip 后框架不执行
  真实 syscall，直接把 ret 当返回值返回用户态。统一返 `-ENOENT`（文件不存在），
  最符合检测语义（让 App 以为没装 root/frida）。

### 2.4 规则表 kw_rules[]

```c
struct kw_rule { const char *kw; enum rule_cat cat; };
```
一张 `{关键词, 分类}` 表，`strstr` 子串匹配。四个分类 `CAT_ROOT/FRIDA/XPOSED/AOSP`，
每类一个 `cat_enable[]` 开关。命中即按分类伪造 `-ENOENT`（`cat_errno` 目前所有类都返 ENOENT）。

增删检测特征只改这张表，逻辑代码不动。当前约 100 条，覆盖：
- ROOT：各目录 su 路径、magisk/kernelsu/apatch、busybox、superuser 等
- FRIDA：frida/gadget/gum 文件名与线程名、27042 端口等明确 Frida 特征
- XPOSED：xposed/lsposed/riru/zygisk/substrate
- AOSP：qemu/goldfish + 夜神/逍遥/雷电/droid4x/ttVM/vbox/bluestacks 等模拟器特征

维护规则表时不要把定制系统自带的 `libcapture`、`libtrace` 加回 fake 规则。它们在本环境里是
系统侧采集/轮询噪声，不是目标 App 的 Frida/注入检测证据；误拦会扩大规则误伤面。

### 2.5 退出/信号监控链路

退出类和发信号类 syscall 共用 `fill_current_call_ctx()`：

```
current_uid() ──不在 target_uids[] → return
   │
   ├─ get_user_regs() 取 pc/lr/sp
   ├─ 取 tgid / tid / comm
   ├─ resolve=on 时 resolve_addr() 解析 pc/lr → pcsym/lrsym
   └─ pr_info 打印 EXIT 或 SIGNAL 事件
```

`handle_exit_syscall()` 记录：

```text
[EXIT/status=<status>/0x<status>] pc/lr/sp pcsym/lrsym
```

`handle_signal_syscall()` 记录：

```text
[SIGNAL/<signal_name>(<num>)/crash=<0|1>] target_tgid target_tid pidfd flags info
```

`signal_name()` 把 1~31 号常见 Linux signal 映射成人可读名字，重点包括：

| Signal | 含义 | 典型来源 |
|--------|------|----------|
| `SIGABRT(6)` | 主动 abort | `abort()`、assert、反调试/完整性失败 |
| `SIGKILL(9)` | 强制杀进程 | 自杀、父进程/守护线程杀主进程、系统 kill |
| `SIGSEGV(11)` | 非法内存访问 | native crash |
| `SIGTRAP(5)` | trap/breakpoint | 反调试、断点 |
| `SIGSYS(31)` | bad syscall | seccomp 拦截 |
| `SIGTERM(15)` | 请求退出 | 业务逻辑退出、外部管理进程 |

`crash=1` 目前对 `SIGILL/SIGTRAP/SIGABRT/SIGBUS/SIGFPE/SIGKILL/SIGSEGV/SIGTERM/SIGSYS`
置 1，便于 grep 快速筛选。注意 `kill(pid, 0)` 是探活，不是退出信号，日志会显示
`SIG?(0)/crash=0`。

**为什么只记录不拦截**：退出类 syscall 是定位问题用的观测面，伪造返回会改变 App 行为，
甚至可能导致调用方以为 kill 成功但进程未退出，产生更复杂的状态问题。本项目定位闪退时只需要
调用点，所以 `exitmon` 不设置 `skip_origin`。

### 2.6 内存/线程/反调试监控链路（memmon）

`memmon=on` 注册一组只观察、不拦截的 after hook，用于补齐匿名执行段、memfd 执行段、VMA 命名和 watcher 线程证据。它和 path fake 是两条完全独立的链路：内存类 syscall 不设置 `skip_origin`，不改 `args->ret`，`fake=on/off` 不影响它。

当前 mem 相关 syscall：

```c
{ __NR3264_mmap, 6, after_mmap },
{ __NR_mprotect, 3, after_mprotect },
{ __NR_pkey_mprotect, 4, after_pkey_mprotect }, // 仅当内核头定义
{ __NR_memfd_create, 2, after_memfd_create },   // 仅当内核头定义
{ __NR_munmap, 2, after_munmap },
{ __NR_mremap, 5, after_mremap },
{ __NR_madvise, 3, after_madvise },
{ __NR_prctl, 5, after_prctl },
{ __NR_clone, 5, after_clone },
{ __NR_clone3, 2, after_clone3 },               // 仅当内核头定义
{ __NR_ptrace, 4, after_ptrace },
{ __NR_wait4, 4, after_wait4 },
{ __NR_waitid, 5, after_waitid },
{ __NR_openat, 4, after_openat },               // fd 缓存增强
{ __NR_openat2, 4, after_openat2 },             // fd 缓存增强
{ __NR_close, 1, after_close },                 // fd 缓存清理
```

必须用 after hook 的原因：`mmap/memfd_create/clone/wait` 的关键证据在返回值里。`mmap` 的 `ret` 是实际映射起始地址，`memfd_create/openat` 的 `ret` 是 fd，`clone` 的 `ret` 是新 tid/pid，`wait4/waitid` 的 `ret` 是被回收的 pid。

默认 `memmon=on` 只打印高价值事件：

- `mmap`：`prot & PROT_EXEC` 或 `flags & MAP_ANONYMOUS`；
- `mprotect/pkey_mprotect`：`prot & PROT_EXEC`；
- 所有 `memfd_create`；
- `prctl(PR_SET_VMA, PR_SET_VMA_ANON_NAME, addr, len, name)`；
- 所有 `clone/clone3`；
- 所有 `ptrace/wait4/waitid`；
- `munmap/mremap/madvise` 仅当地址命中已记录的可疑 range。

`memdump=on` 会放宽过滤，打印全量内存类 syscall，用于排查漏项。它只改变日志量，不改变 hook 注册和目标行为。

### 2.7 memmon 辅助状态：fd 缓存和 range 缓存

memmon 维护两个小型环形缓存，仅用于日志增强：

```c
struct fd_cache_entry {
    pid_t tgid;
    int fd;
    char path[FD_PATH_LEN];
};

struct mem_range_entry {
    pid_t tgid;
    unsigned long start;
    unsigned long end;
    int prot;
    int flags;
    char name[MEM_NAME_LEN];
};
```

fd 缓存来源：

1. `memfd_create` after：`ret_fd -> memfd:<name>`；
2. `openat/openat2` after：`ret_fd -> path`；
3. `close` after：删除 `tgid + fd` 记录；
4. `mmap(fd >= 0)` 时优先查缓存，查不到再尝试 `fget(fd) + file_path()` 解析当前 fd。

range 缓存来源：

1. `mmap` 成功后记录 `ret .. ret+len`；
2. `mprotect/pkey_mprotect(PROT_EXEC)` 且 `ret == 0` 后记录改权范围；
3. `prctl(PR_SET_VMA_ANON_NAME)` 且 `ret == 0` 后记录命名范围；
4. `mremap` 成功后记录新地址范围。

range 缓存只用于默认模式下过滤 `munmap/mremap/madvise`，避免这些高频 syscall 把日志刷爆。它不是安全边界，也不影响 syscall 返回。

当前没有解析 `clone3` 的用户态 `struct clone_args`，只记录 `clone_args` 指针和 `size`。项目里没有通用 `copy_from_user` 兼容封装，直接解引用用户指针会有内核崩溃风险；如后续要解析 clone3 结构，先补可靠的用户内存读取封装。

### 2.8 调用者信息：tgid / tid / comm / pc / lr / sp

为了回答「**是谁发起的检测**」，每条日志带：
- `tgid`：进程 ID（区分主进程/子进程）。用 `kallsyms_lookup_name("__task_pid_nr_ns")`
  取函数指针调用——**不能用 sched.h 的内联 `__task_pid_nr_ns`**，它走 `kfunc_direct_call`
  依赖未导出符号 `kf___task_pid_nr_ns`，加载时会 `unknown symbol` 失败。
- `tid`：当前线程 ID。memmon/exitmon 输出会显式带 `tid`，便于区分 watcher 线程。
- `comm`：线程名。用 sched.h 提供的 `get_task_comm(current)`，内部读 `task_struct_offset.comm_offset`
  （KernelPatch 启动时自适应探测的偏移，跨版本稳）。
- `pc`：触发 svc 指令的用户态地址（通常在 libc 的 syscall 封装里）。
- `lr (x30)`：**调用者返回地址 —— 真正写检测逻辑的业务 so**。逆向时定位这个。
- `sp`：用户栈指针。

寄存器从 `get_user_regs` 取：带 syscall wrapper 的内核，`fargs->args[0]` 即 `struct pt_regs*`，
读 `regs->pc` / `regs->regs[30]` / `regs->sp`。

### 2.9 内核态调用者解析 resolve_addr（resolve=on）

这是解决「短命进程事后取不到 maps」的核心。原理：命中发生时调用进程**必然存活**
（它正卡在这个 syscall 里），直接在内核里把 pc/lr 解析成 `so名!偏移`：

```c
mm = p_get_task_mm(current);          // 取当前进程地址空间
vma = p_find_vma(mm, addr);           // 找 addr 所属 vma
vm_start = *(ulong*)(vma + 0x0);      // VMA_OFF_VM_START
file    = *(file**)(vma + 0xa0);      // VMA_OFF_VM_FILE
if (file) p_file_path(file, buf, ...) // → so 路径，取 basename + 偏移
else      "anon:基址+偏移"            // 匿名段（加固壳动态代码）
p_mmput(mm);
```

输出形态：
- `libDexHelper.so!0x5e0ac` —— 命中所在 so + 模块内偏移
- `anon:6d31b23000+0x96f24` —— 无名匿名可执行内存（VMP/壳运行时生成的代码）
- `[anon:.bss]+0x..` —— 内核命名匿名区间
- `memfd:frida-agent-64.so!0x..` —— frida 经 memfd 注入

4 个解析用内核函数（`get_task_mm`/`mmput`/`find_vma`/`file_path`）全部 `mod_init` 里
`kallsyms_lookup_name` 自取——同样为避开未导出的 `kf_` 封装符号。init 日志会打印
各函数解析地址，0 表示该内核 kallsyms 名字不同、resolve 降级。

memmon 的 fd 路径增强还会尝试解析 `fget/fput`。这两个符号缺失时只影响 `mmap(fd)` 的
`fdpath` 兜底解析，不影响 path/exit/memmon 主流程。

**关键依赖：`vm_area_struct` 字段偏移**（`VMA_OFF_VM_START=0x0`、`VMA_OFF_VM_FILE=0xa0`）
来自本设备 BTF（android13-5.10）。`vm_start` 是结构体第一字段、跨版本恒为 0；
`vm_file` 偏移可能随内核版本/配置变。换内核时见 README「换设备/内核」一节用 BTF 重取。

不加 mmap 锁：命中发生在当前进程自己的 syscall 上下文，进程不会同时改自己的地址空间，
`find_vma` 只读，安全。

### 2.10 Hook 注册策略：path 默认，exitmon/memmon 动态

`struct sc_hook` 同时描述 before/after、退出类分组和 mem 类分组：

```c
struct sc_hook {
    int nr;
    int narg;
    void *before;
    void *after;
    const char *name;
    int exit_related; // 1=退出/信号类
    int mem_related;  // 1=内存/线程/ptrace 类
};
```

`mod_init()` 只调用 `register_hooks(0)` 注册 path 类 syscall。退出/信号类 hook 等
`ctl exitmon=on` 才调用 `register_hooks(1)`，mem 类 hook 等 `ctl memmon=on` 才调用
`register_mem_hooks()`。这个设计有三个目的：

1. 模块加载阶段保持最小行为面，避免新增 syscall hook 出问题时导致 KPM 无法加载；
2. 退出监控和 memmon 都是调试观测能力，不是日常隐藏检测能力，按需打开更稳；
3. memmon hook 数量多、日志量大，必须能单独启停。

`exitmon=off` 会调用 `unregister_hooks(1)` 卸载退出/信号类 hook，path 类 hook 保持不变。
`memmon=off` 会调用 `unregister_mem_hooks()` 卸载 mem 类 hook。`mod_exit()` 卸载时按
`unregister_mem_hooks()`、`unregister_hooks(1)`、`unregister_hooks(0)` 顺序清理全部 hook。

维护注意：`reload` 前如果已经打开 `exitmon=on` 或 `memmon=on`，理论上卸载会先解除动态 hook；当前实测可用。但做内核模块迭代时更推荐先：

```bash
./load.sh ctl 'memmon=off'
./load.sh ctl 'exitmon=off'
./load.sh reload
```

这样可以降低 KernelPatch fp hook 链上的不确定性。

### 2.11 运行时控制 mod_ctl0

通过 `kpm ctl0 <模块名> <命令>` 接收控制。**命令必须是单个无空格 token**——
kpatch 只把 argv[0] 传进内核，带空格会被截断。所以用 `key=value` 紧凑格式：

```
trace=on/off  fake=on/off  dump=on/off  resolve=on/off  exitmon=on/off
memmon=on/off  memdump=on/off
ROOT=on/off  FRIDA=on/off  XPOSED=on/off  AOSP=on/off
uidadd=10299  uiddel=10299  uidclear
其它/空 → 打印当前状态到 dmesg（load.sh 再从 dmesg 取最近状态行）
```

状态不再通过 `out_msg` 回写用户态。原因见「踩坑记录」：本设备上 `kpatch ctl0` 的 out_msg
通道和长格式状态输出组合曾触发 kpatch 进程硬锁死，最后由 watchdog 重启。当前实现里
`mod_ctl0()` 只 `pr_info` 四条短状态日志：

```text
[scfilter] status: trace=1 fake=1 dump=0 resolve=1 exitmon=1 hooks=1 memmon=1 memhooks=1 memdump=0
[scfilter] status_cat: ROOT=1 FRIDA=1 XPOSED=1 AOSP=1
[scfilter] status_uid: uid0=10236 uid1=10240 uid2=10239 uid3=0
[scfilter] status_uid: uid4=0 uid5=0 uid6=0 uid7=0
```

`load.sh status` / `load.sh ctl` 执行完 ctl 后再 grep 最近 4 条状态行展示。

### 2.12 几个全局开关语义

| 开关 | 默认 | 作用 |
|------|------|------|
| `g_enable_trace` | 1 | 是否 `pr_info` 打印命中（关掉则静默拦截） |
| `g_enable_fake` | 1 | 是否伪造返回（关掉则只观察不拦截） |
| `g_dump_all` | 0 | 是否打印目标 UID 的**所有** path syscall（不止命中），用于发现新检测路径 |
| `g_resolve` | 0 | 是否内核态解析 pc/lr 成 so!偏移 |
| `g_exit_trace` | 0 | 是否打印退出/信号事件，由 `exitmon=on/off` 控制 |
| `g_exit_hooks_registered` | 0 | 退出/信号 hook 是否已实际注册 |
| `g_mem_trace` | 0 | 是否打印 memmon 事件，由 `memmon=on/off` 控制 |
| `g_mem_dump` | 0 | 是否打印全量内存类 syscall；默认只打印高价值事件 |
| `g_mem_hooks_registered` | 0 | memmon hook 是否已实际注册 |
| `cat_enable[4]` | 全1 | 四个分类各自的开关 |

---

## 3. 编译：为什么必须用 clang large model

KPM 是可重定位 ELF，由 KernelPatch 的 `relo.c` 在加载时做重定位。`relo.c` 只支持
固定几类 AArch64 重定位（ABS64、CALL26、MOVW_UABS_G0~G3 等），**不支持 GOT 类**。

三种编译方式的结果：
| 编译方式 | 产生的重定位 | 结果 |
|----------|--------------|------|
| GCC 默认（-fPIC） | `R_AARCH64_ADR_GOT_PAGE` 等 GOT | relo.c 不支持，**静默失败** |
| GCC `-mcmodel=large -fno-pic` | 残留 `ADR_PREL_PG_HI21`(ADRP) | 加载到内核高地址时 **overflow** |
| **clang `--target=aarch64-none-elf -mcmodel=large -fno-pic`** | 纯 `MOVW_UABS_G*`（64位绝对寻址） | **正确** ✓ |

clang 的 large model 实现彻底用 movw 四指令构造 64 位绝对地址，不依赖 PC 相对的
ADRP，也不走 GOT。Makefile 默认用 AOSP 自带 clang-r522817，`ld.lld -r` 打包。

其它必要 flag：
- `-fno-stack-protector`：否则引用未导出的 `__stack_chk_guard/fail`，加载失败。
- `-fno-asynchronous-unwind-tables -fno-unwind-tables`：去掉 `.eh_frame`，减重定位。
- `-ffreestanding -fno-builtin -nostdlib`：裸机环境，不链接标准库。

---

## 4. 采集与解析（PC + 设备脚本）

### 4.1 capture_live.sh —— 主力采集

`start` 流程：
1. `am force-stop` 目标 App
2. `dmesg -C` 清内核环形缓冲（**关键**：否则 `dmesg -w` 会把上一轮历史日志一起 dump 出来，
   导致新旧命中混杂、旧行没有 pcsym）
3. 后台 `dmesg -w | grep [scfilter]` 流式写 `<tag>_live_raw.log`
4. push 并后台运行 `scf_snap.sh`（maps 快照器，仅 resolve=off 时有用）
5. `monkey` 冷启动 App

`stop` 流程：
1. kill 流式采集 + 杀设备端 `dmesg -w` / `scf_snap.sh`
2. 从 raw 提取 `<tag>_hits.log`（命中+FAKE）、`<tag>_allpaths.log`（全量去重）
3. **判断 hits.log 有没有 `lrsym:`**：
   - 有（resolve=on）→ `resolve.py --kresolve` 直接从日志提取，无需 maps
   - 无（resolve=off）→ 拉回 maps 快照，`resolve.py --mapsdir` 按 tgid 解析

内置 tag→包名/UID 映射在脚本顶部 case，加 App 改这里。

### 4.2 scf_snap.sh —— 设备端 maps 快照器

resolve=off 时才需要。每 100ms 用 `pgrep -f 包名` 精准定位目标进程（含子进程），
把没存过的进程 maps 存成 `maps_<tgid>.txt`。

为什么独立成脚本 push 到设备：原来内联在 `dev "nohup sh -c '...$(pgrep)...'"` 里，
多层引号 + 命令替换经 `adb shell su -c` 传输会被解析破坏（实测 `unexpected do`）。
独立脚本文件 + 简单参数传递规避了引号嵌套。

> 局限：再快的轮询也追不上 fork 后毫秒级退出的短命检测进程 → no-maps。这正是
> 内核态解析（resolve=on）存在的根本理由——它在命中当下解析，不靠事后抓。

### 4.3 resolve.py —— 地址解析

三个入口：
- `--kresolve <log>`：日志已含内核态 `pcsym:`/`lrsym:`，正则提取美化成
  `[分类] 路径` + `[pc]/[lr] so!偏移` 两行，跳过 FAKE 杂行。**resolve=on 时用这个**。
  当前同时支持 path 命中日志、退出/信号事件和 memmon 事件：

  ```text
  [ROOT/magisk] faccessat path:/system/bin/magisk
          [pc] anon:...+0x18220   [lr] anon:...+0x96c30

  [SIGNAL/SIGKILL(9)/crash=1] kill target_tgid:6005 ...
          [pc] anon:...+0x2bb2c   [lr] anon:...+0x29cb8

  [MEM/EXEC|MEM/FD] mmap addr:... len:... prot:0x5 fd:42 fdpath:memfd:jit-cache ...
          [pc] libc.so!0x...   [lr] libDexHelper.so!0x4a604
  ```

- `--mapsdir <目录> <log>`：多进程。目录里 `maps_<tgid>.txt`，按每行 tgid 选对应
  maps 解析；无对应 maps 显示 `(no-maps:tgid)`。
- `<maps文件> <log>` / `--pid <PID> <log>`：单 maps / 在线取 maps。

解析核心 `resolve(addr)`：在 maps 区间里找 addr 落点，命名 so 输出 `basename!偏移`
（偏移相对该 so 最小 start，处理多段映射），无名匿名段输出 `anon:基址+偏移`。

### 4.4 capture_test.sh 的时间戳坑

早期 `capture_test.sh` 用 dmesg 当前时间戳做锚点，然后 awk 过滤「本轮之后」的日志。
Android 设备 dmesg 输出里时间戳可能是 `[  251.436306]`，中间有空格，简单取 `$1`
只能拿到 `[`，导致本轮明明有内核日志，脚本产物却是 0 行。

现在快速测试改成更直接的流程：

1. `am force-stop` 目标；
2. `dmesg -C` 清空环形缓冲；
3. `monkey` 冷启动；
4. 等待 N 秒；
5. `dmesg | grep '[scfilter]'` 作为本轮 raw。

这样不会被 dmesg 时间戳格式影响。`capture_test.sh` 也已加入 `tuhu`：

```text
tuhu) PKG=cn.TuHu.android; APPUID=10239; TAG=tuhu ;;
```

---

## 5. 关键设计决策与踩坑记录

| 问题 | 根因 | 解法 |
|------|------|------|
| KPM 加载静默失败 | GCC -fPIC 产生 GOT 重定位，relo.c 不支持 | 改 clang large model |
| 加载 overflow | GCC large model 残留 ADRP，内核高地址超 ±4GB | clang 纯 movw |
| `unknown symbol __stack_chk_*` | 栈保护引用未导出符号 | `-fno-stack-protector` |
| `unknown symbol kf___task_pid_nr_ns` | sched.h 内联函数依赖未导出 kfunc 封装 | 自己 kallsyms 取函数指针 |
| ctl 命令带空格失效 | kpatch 只传 argv[0] | 改 `key=value` 单 token |
| `kpatch ctl0 status` 卡死到 watchdog | 本设备上 out_msg 回写/用户态读取路径不稳定，曾卡在 `ctl: status` 后 | 内核只 `pr_info` 状态，`load.sh` 从 dmesg grep |
| status 打一条超长 `pr_info` 卡死 | KPM/printk varargs 路径对长参数列表不稳，卡在 `uidadd=10239` 后 | 状态拆成 4 条短日志 |
| `reload` 后模块路径读不到 | `/data/scfilter.kpm` SELinux context 拒绝 kpatch 读 | 改用 `/data/local/tmp/scfilter.kpm` |
| `/proc/cpuinfo` 命中 1.8 万次 | 它是必然存在、靠内容判断的文件 | 移出规则表（内容类检测不能伪造存在性） |
| 短命进程 no-maps | 事后抓 maps 追不上 fork 即退的进程 | 内核态实时解析（resolve=on） |
| 新旧日志混杂、半数缺 pcsym | dmesg -w 会 dump 历史缓冲 | start 时 dmesg -C 清缓冲 |
| `capture_test.sh` 产物 0 行 | awk 解析 dmesg `[  123.456]` 时间戳失败 | 快速测试改为先 `dmesg -C` 再启动 |

### 5.1 维护动态 hook 的注意事项

- `exitmon=on` 会注册 8 个额外 syscall hook。`memmon=on` 会注册内存/线程/ptrace 相关 syscall hook。二者都是调试观测面，平时可关掉：

  ```bash
  ./load.sh ctl 'exitmon=on'
  ./load.sh ctl 'exitmon=off'
  ./load.sh ctl 'memmon=on'
  ./load.sh ctl 'memdump=off'
  ./load.sh ctl 'memmon=off'
  ```

- 退出/信号和 memmon 日志都只记录，不拦截；不要在这些路径里设置 `skip_origin`，否则会改变 App 的退出、内存布局或线程语义。
- `SIGKILL(9)` 已覆盖。它可能通过 `kill/tkill/tgkill/rt_sigqueueinfo/rt_tgsigqueueinfo/pidfd_send_signal`
  任一 syscall 发送，不能只看 `kill`。
- `kill(pid, 0)` 是探活，不是杀进程。判断闪退优先看 `crash=1`，再结合 signal 号和 target pid。
- `exit(status=0)` 不一定是闪退，可能是正常线程/子进程退出；主进程 `exit_group` 或
  主进程对自己 `SIGKILL/SIGABRT` 更有定位价值。
- 匿名段地址每次启动会因 ASLR 变化，维护记录时要看 `+0x偏移`，不要看绝对地址。
- memmon 的 fd/range 缓存只用于日志增强和默认日志过滤，不参与行为决策；缓存丢失时允许降级为少量 `fdpath` 缺失或 `munmap/mremap/madvise` 少打印，不应影响 syscall 返回。
- `memdump=on` 只改变日志过滤，不改变 hook 注册。定位默认过滤漏掉的事件时短时间打开，采集后立即关掉。
- reload 前建议先关 `memdump/memmon/exitmon`，降低 KernelPatch fp hook 链在模块迭代时的不确定性。

### 能力边界（重要）

模块只伪造 syscall **返回值**，所以：
- ✅ **路径类检测**有效：文件存在性检测（su 路径、模拟器特征文件、注入库文件名）被骗过。
- ❌ **内容类检测**无效：读 `/proc/self/maps` 扫内存、`/proc/cpuinfo` 看 CPU 指纹、
  `/proc/<pid>/status` 查 TracerPid/线程名——这些文件必然存在，App 看的是**内容**。
  对抗需要 hook read 改写内容（本项目按需求未做）。

---

## 6. 实测案例（解析能力验证）

- **川观新闻**：libDexHelper.so（加固壳）里两处 su 检测循环，lr 偏移连续递增=遍历路径表；
  memmon 能看到 `libDexHelper.so!0x4a604` 发起匿名 mmap、`.bss` VMA 命名、`memfd:jit-cache`
  可执行映射，以及 `ptrace/wait4` 监控链。
- **1905电影**：多进程（主进程+ZIDThreadPool+lelinkps），跨进程解析；frida 检测在 libopenjdk。
- **khapp**：qemud/riru 检测落在同一段匿名内存相邻偏移=同一加固壳模块。
- **途虎（秒闪退+多 fork 检测进程）**：PC 端 maps 100% no-maps；内核态解析 100% 命中，
  9 轮不同 ASLR 基址下检测函数偏移完全一致（`anon:基址+0x96bd0~+0x96f24` root 特征表循环，
  svc 封装统一 `+0x18220`），含对 `me.bmax.apatch` 的检测。这组数据是内核态解析价值的最强证明。

### 6.1 signed.apk / cn.TuHu.android 闪退定位结论

测试 APK：项目根目录 `signed.apk`，包名 `cn.TuHu.android`，设备上 UID `10239`。

复现命令：

```bash
cd ~/bin/xiaojianbang-syscall-filter
./load.sh reload
./load.sh ctl 'uidadd=10239'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh tuhu 8
```

最终状态：

```text
[scfilter] status: trace=1 fake=1 dump=0 resolve=1 exitmon=1 hooks=1
[scfilter] status_uid: uid0=10236 uid1=10240 uid2=10239 uid3=0
```

最终日志在 `logs/tuhu_resolved.log`，关键行：

```text
[SIGNAL/SIGKILL(9)/crash=1] kill target_tgid:6005 target_tid:0 pidfd:-1 flags:0 info:0
        [pc] anon:7aa6e94000+0x2bb2c   [lr] anon:7aa6e94000+0x29cb8   (comm:cn.TuHu.android)
```

结论：

- App 主进程自己调用 `kill(pid, SIGKILL)` 杀掉自身；
- 触发闪退的代码位于匿名可执行/解密代码段；
- ASLR 变化时基址会变，但稳定偏移是：

```text
PC: anon + 0x2bb2c
LR: anon + 0x29cb8
```

同一轮日志里，SIGKILL 前紧挨着 root/APatch 检测：

```text
[ROOT/magisk]      path:/data/data/com.topjohnwu.magisk   [lr] anon:+0x96d2c
[ROOT/kernelsu]   path:/data/data/me.weishu.kernelsu     [lr] anon:+0x96e28
[ROOT/apatch]     path:/data/data/me.bmax.apatch         [lr] anon:+0x96f24
[SIGNAL/SIGKILL]  kill(SIGKILL)                          [pc] anon:+0x2bb2c
```

维护判断：这不是 Java 层普通 crash，也不是系统杀后台；是壳/保护逻辑在匿名 native 代码中做环境检测后主动 `SIGKILL` 自杀。

---

**作者：小肩膀　微信：xiaojianbang8888**
