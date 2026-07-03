# xiaojianbang-syscall-filter

> 作者：**小肩膀**　微信：**xiaojianbang8888**

一个工作在 **内核态** 的 APatch/KernelPatch 模块，按 App(UID) 过滤，主要做四件事：

1. **路径检测 trace** —— 记录是谁（调用者 so）、用哪个 syscall、查了什么路径；
2. **伪造返回值** —— 命中 root / frida / xposed / 模拟器特征时返回 `-ENOENT`（文件不存在）；
3. **退出/闪退 trace** —— 记录 `kill/exit/tgkill` 等退出相关 syscall，定位是谁主动杀进程；
4. **内存执行来源 trace** —— 记录 `mmap/mprotect/memfd_create/prctl/clone/ptrace/wait` 等事件，定位匿名执行段、memfd 执行段和 watcher 线程。

因为运行在内核态，目标 App 在用户态无法察觉自己的 syscall 被改写，也无法通过扫描
自身内存发现 hook（对比用户态 inline svc hook，后者容易被反检测代码反查）。

> 想读懂代码实现/改造模块，看 [ARCHITECTURE.md](./ARCHITECTURE.md)。本文只讲怎么用。

---

## 功能特性

- **按 UID 精准过滤**：只对指定 App 生效，其余进程零影响。最多 8 个目标，可运行时增删。
- **四类检测拦截**：ROOT / FRIDA / XPOSED / AOSP(模拟器)，每类可单独开关。
- **命中即伪造**：被检测的 su 路径、注入库、模拟器特征文件统一返回"不存在"。
- **调用者定位**：日志带 `tgid`(进程) / `comm`(线程) / `pc`(svc 位置) / `lr`(调用者)。
- **内核态解析调用者**：命中当下把 pc/lr 解析成 `so名!偏移`，连秒闪退、fork 即退的
  短命进程、加固壳匿名内存都能定位（这是事后抓 maps 做不到的）。
- **退出/闪退监控**：记录 `exit`、`exit_group`、`kill`、`tkill`、`tgkill`、
  `rt_sigqueueinfo`、`rt_tgsigqueueinfo`、`pidfd_send_signal` 等退出/发信号 syscall，
  包括 `SIGKILL(9)`、`SIGABRT(6)`、`SIGSEGV(11)` 等，并解析触发代码段。
- **内存执行来源监控**：`memmon=on` 后记录 `mmap/mprotect/pkey_mprotect/memfd_create`
  以及 `prctl(PR_SET_VMA_ANON_NAME)`、`clone/clone3`、`ptrace/wait` 等事件，只记录不拦截，
  用于定位匿名 RX/RWX、memfd 执行段和 watcher 线程来源。
- **全量调试模式**：dump 目标 App 访问的所有路径，用于发现规则没覆盖的检测点。
- **运行时控制**：所有开关、目标 UID 都能在不重新加载的情况下动态调整。

---

## 系统要求

- **设备**：已 root，安装 APatch / KernelPatch。实测于 Pixel 6 / Android 13 /
  内核 **5.10 (android13)** / kpver c02。
- **架构**：arm64 (aarch64)。
- **加载工具**：设备端 `/data/local/tmp/kpatch`（`load.sh` / `load.ps1` 里已配置）。
- **superkey**：APatch 安装时设置的密码，默认 `xiaojianbang8888`；可用环境变量 `XJB_KP_SUPERKEY` 覆盖。
- **PC 端**：`adb` + `python3`（解析脚本用）。
- **编译（仅改代码时）**：clang（推荐 AOSP 自带，见下文「重新编译」）。

`adb` 路径按 `XJB_ADB` -> `ADB` -> PATH 中 `adb` 的顺序选择，Linux/macOS 可直接运行 `load.sh`，Windows PowerShell 使用 `load.ps1`。若设备上 `kpatch` 路径不同，改 `load.sh` 和 `load.ps1` 顶部的 `KP`。

---

## 快速开始

```bash
cd ~/bin/xiaojianbang-syscall-filter

./load.sh reload               # 1. 推送并加载模块（默认拦截 UID 10236/10240）
./load.sh status               # 2. 确认运行状态

./load.sh ctl 'resolve=on'     # 3. 开内核态调用者解析（推荐）
./load.sh ctl 'exitmon=on'     # 4. 开退出/信号监控（定位闪退代码段）
./load.sh ctl 'memmon=on'      # 5. 开内存执行来源监控（只记录，不拦截）
./load.sh ctl 'dump=on'        # 6. 开全量路径调试（调试完记得关）
./capture_live.sh cbgc start   # 7. 冷启动 App + 后台采集
#    >>> 拿起手机操作 App：同意隐私协议 → 进主页 → 点功能 <<<
#    （秒闪退的 App 不用操作，等几秒直接 stop）
./capture_live.sh cbgc stop    # 8. 停止，自动分类 + 解析调用者

cat logs/cbgc_resolved.log     # 9. 看结果：路径/退出/内存事件 + 调用者 so!偏移
./load.sh ctl 'dump=off'       # 10. 关掉 dump（否则日志一直刷）
./load.sh ctl 'memmon=off'     # 11. 关掉 memmon（调试完建议关）
./load.sh ctl 'exitmon=off'    # 12. 关掉 exitmon
```

Windows PowerShell 入口：

```powershell
$env:XJB_ADB = "C:\Android\platform-tools\adb.exe"
$env:XJB_KP_SUPERKEY = "xiaojianbang8888"
.\load.ps1 reload
.\load.ps1 ctl resolve=on
.\load.ps1 ctl exitmon=on
.\load.ps1 status
```

只想抓启动期/秒闪退，用快速采集：

```bash
./capture_test.sh cbgc 12
cat logs/cbgc_resolved.log
```

---

## 定位闪退 / 主动退出

退出监控由 `exitmon` 控制，只记录不拦截。建议同时打开 `resolve=on`，这样进程死前就能把
调用点解析成 `so!偏移` 或 `anon:基址+偏移`。

```bash
./load.sh ctl 'uidadd=<目标UID>'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh <tag> 12
cat logs/<tag>_resolved.log
```

重点看这些事件：

```text
[SIGNAL/SIGABRT(6)/crash=1] tgkill ...
[SIGNAL/SIGKILL(9)/crash=1] kill ...
[EXIT/status=.../0x...] exit_group ...
```

日志里的 `[pc]` 是 syscall 触发点，`[lr]` 通常更接近业务/壳检测逻辑的调用点。匿名加固代码会显示成：

```text
anon:<基址>+0x<偏移>
```

每次启动基址会因为 ASLR 改变，定位时看 `+0x偏移`。

### signed.apk / tuhu 示例

项目根目录的 `signed.apk` 包名是 `cn.TuHu.android`，脚本内置 tag 为 `tuhu`，设备上 UID 为 `10239`：

```bash
./load.sh reload
./load.sh ctl 'uidadd=10239'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh tuhu 8
cat logs/tuhu_resolved.log
```

已复现到的关键结论：

```text
[SIGNAL/SIGKILL(9)/crash=1] kill target_tgid:6005 ...
        [pc] anon:7aa6e94000+0x2bb2c   [lr] anon:7aa6e94000+0x29cb8
```

说明 App 在匿名 native 代码段中主动调用 `kill(pid, SIGKILL)` 杀掉自身；稳定偏移是：

```text
PC: anon + 0x2bb2c
LR: anon + 0x29cb8
```

---

## 定位匿名执行 / memfd / watcher 线程

内存监控由 `memmon` 控制，只记录、不拦截、不修改返回值，不受 `fake=on` 影响。它适合回答这些问题：

- 匿名 RX/RWX 段是谁 `mmap` 出来的；
- 已有内存是谁 `mprotect(PROT_EXEC)` 改成可执行的；
- `memfd_create` 后是否被 `mmap(PROT_EXEC)`；
- `[anon:.bss]` 这类 VMA 名称是谁通过 `prctl(PR_SET_VMA_ANON_NAME)` 设置的；
- watcher 线程、ptrace monitor、waitpid 监控链是谁创建和驱动的。

推荐命令：

```bash
./load.sh reload
./load.sh ctl 'uidadd=10236'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./load.sh ctl 'memmon=on'
./capture_test.sh cbgc 12
cat logs/cbgc_resolved.log
```

重点 grep：

```bash
grep -E '\[MEM/EXEC|\[MEMFD|\[MEM/VMA_NAME|\[THREAD/CLONE|\[DEBUG/PTRACE|\[DEBUG/WAIT|\[SIGNAL' logs/cbgc_resolved.log
grep -E 'libDexHelper|anon_name:.bss|fdpath:memfd|ptrace|wait4' logs/cbgc_resolved.log
```

常见标签：

| 标签 | 含义 |
|------|------|
| `[MEM/ANON]` | 匿名映射，常见于堆、线程栈、JIT、壳分配缓冲 |
| `[MEM/EXEC]` | 可执行映射或可执行改权，重点看 `pcsym/lrsym` |
| `[MEM/EXEC|MEM/FD]` | 文件或 memfd 的可执行映射，重点看 `fdpath` |
| `[MEMFD]` | `memfd_create(name, flags)` 返回 fd |
| `[MEM/VMA_NAME]` | `prctl(PR_SET_VMA_ANON_NAME)` 设置 `[anon:name]` |
| `[THREAD/CLONE]` | `clone/clone3` 创建线程或子进程 |
| `[DEBUG/PTRACE]` | `ptrace` 调试/反调试相关调用 |
| `[DEBUG/WAIT]` | `wait4/waitid` 监控子进程状态 |

默认 `memmon=on` 已经会打印高价值事件：匿名映射、可执行映射/改权、memfd、VMA 命名、线程创建、ptrace/wait。日志仍然太多时，先缩短 `capture_test.sh` 时间窗口，或者只看 `logs/<tag>_resolved.log` 中 `lrsym:` 指向目标 so 的行。

需要排查漏项时再打开全量内存调试：

```bash
./load.sh ctl 'memdump=on'
./capture_test.sh cbgc 8
./load.sh ctl 'memdump=off'
```

`memdump=on` 会显著放大日志量，调试完建议关闭 `memdump/memmon/exitmon`。

---

## 命令参考

### load.sh / load.ps1（加载与控制）

| 命令 | 作用 |
|------|------|
| `./load.sh load` / `unload` | 加载设备上已有模块 / 卸载模块 |
| `./load.sh reload` | 重新推送 + 加载（改完代码用） |
| `./load.sh status` | 查看当前运行配置 |
| `./load.sh list` / `info` | 列出已加载 KPM / 查看本模块详情 |
| `./load.sh ctl '<命令>'` | 运行时控制，见下表 |

Windows PowerShell 等价命令为 `.\load.ps1 load`、`.\load.ps1 reload`、`.\load.ps1 ctl resolve=on`。

### 运行时控制命令（`ctl`，参数必须是无空格单 token）

| 命令 | 作用 |
|------|------|
| `trace=on` / `off` | 命中打印开关（关掉则静默拦截） |
| `fake=on` / `off` | 伪造返回开关（关掉则只观察不拦截） |
| `dump=on` / `off` | 全量调试：打印目标 UID **所有** path syscall（不止命中的） |
| `resolve=on` / `off` | 内核态解析调用者 so!偏移（推荐开，根治短命进程定位） |
| `exitmon=on` / `off` | 退出/信号 syscall 监控开关，只记录不拦截 |
| `memmon=on` / `off` | 内存/线程/ptrace syscall 监控开关，只记录不拦截 |
| `memdump=on` / `off` | 全量内存 syscall 调试输出；默认 `memmon` 只打印高价值事件 |
| `ROOT/FRIDA/XPOSED/AOSP=on` / `off` | 分类开关 |
| `uidadd=10299` / `uiddel=10299` / `uidclear` | 动态增删 / 清空目标 UID |
| `status` | 打印当前状态到 dmesg，并由 `load.sh` 显示最近状态行 |

`status` 示例：
```
[scfilter] status: trace=1 fake=1 dump=0 resolve=1 exitmon=1 hooks=1 memmon=1 memhooks=1 memdump=0
[scfilter] status_cat: ROOT=1 FRIDA=1 XPOSED=1 AOSP=1
[scfilter] status_uid: uid0=10236 uid1=10240 uid2=10239 uid3=0
[scfilter] status_uid: uid4=0 uid5=0 uid6=0 uid7=0
```

字段说明：

| 字段 | 含义 |
|------|------|
| `resolve=1` | 日志会带 `pcsym/lrsym`，可直接解析调用者 |
| `exitmon=1` | 退出/发信号事件打印开关已打开 |
| `memmon=1` | 内存/线程/ptrace 事件打印开关已打开 |
| `memdump=1` | 全量内存 syscall 调试输出已打开 |
| `hooks=1` | 退出/发信号 syscall hook 已实际注册 |
| `uidN=` | 当前目标 UID 槽位，最多 8 个 |

### 采集脚本

```bash
./capture_live.sh <tag> start    # 冷启动 App + 流式采集（主力，能抓深层检测）
./capture_live.sh <tag> stop     # 停止 + 分类 + 解析
./capture_test.sh <tag> [秒数]   # 冷启动快速抓（只能抓启动期，不需手动操作）
```

内置 `<tag>`（在 `capture_live.sh` / `capture_test.sh` 顶部 case 增删）：
`cbgc`(川观新闻) `m1905`(1905电影) `sig`(SIGFFCNFN) `khapp`(信泰) `tuhu`(途虎/signed.apk)。

### 新增一个目标 App

```bash
# 1. 查 UID
adb shell su -c "pm list packages -U | grep <包名>"   # 输出 uid:10xxx
# 2. 运行时加入目标
./load.sh ctl 'uidadd=10xxx'
# 3.（可选）在 capture_live.sh / capture_test.sh 顶部 case 加一行 tag
```

### 看日志

采集产物在 `logs/`：

| 文件 | 内容 |
|------|------|
| `<tag>_resolved.log` | **路径命中/退出事件/内存事件 + 调用者 so!偏移** ← 主要看这个 |
| `<tag>_hits.log` | 命中原始记录（含 tgid/tid/comm/pc/lr/sp/signals/mem events） |
| `<tag>_allpaths.log` | dump 模式全量去重路径（找规则未覆盖的检测） |
| `<tag>_allpaths_resolved.log` | 全量路径 + 解析 |
| `<tag>_live_raw.log` | 原始流式日志（最大，可删） |

`capture_test.sh` 会先 `dmesg -C` 清空历史日志，再冷启动 App；它适合启动期检测和秒闪退。
`capture_live.sh` 适合需要手动操作 App 后才触发检测的场景。

也可直接看设备内核日志：`adb shell su -c "dmesg | grep '\[scfilter\]'"`

---

## 配置检测规则

规则在源码 `src/syscallhook.c` 的 `kw_rules[]` 数组，每条一行：

```c
{ "关键词", 分类 },
```

- **关键词**：路径子串（`strstr` 匹配，命中即算）。如 `"magisk"` 命中任何含 magisk 的
  路径；`"/system/bin/su"` 只命中该完整路径。
- **分类**：`CAT_ROOT` / `CAT_FRIDA` / `CAT_XPOSED` / `CAT_AOSP`，决定日志标签和归哪个开关管。

例：
```c
{ "libDexHelper", CAT_ROOT },           // 拦某加固检测库
{ "/data/local/tmp/myhook", CAT_FRIDA },// 拦自定义注入路径
{ "redfinger", CAT_AOSP },              // 拦某云手机特征
```

改完重新编译加载：`cd src && make && cd .. && ./load.sh reload`

### 选关键词的原则（避免误伤）

1. **够具体**：太短会误伤正常路径。反例 `"su"` 会命中 `/system/usr`、`busybox` 等海量
   正常路径。要用完整路径或带分隔符的 `"/su/"`。
2. **只用于存在性检测**：仅当「App 靠文件存不存在判断」才适合伪造 `-ENOENT`。
   **绝不要**加 `/proc/cpuinfo`、`/proc/self/maps`、`/proc/<pid>/status` 这类——
   它们必然存在、App 读的是**内容**，伪造不存在会刷爆日志且破坏正常功能（见注意事项）。
3. **别加高频系统文件**：会被正常访问命中无数次。

定制系统自带的 `libcapture`、`libtrace` 不在 fake 规则里，默认视为系统侧采集/轮询噪声；不要仅凭这两个字符串判断目标 App 做了 Frida/注入检测。

### 用 dump 模式发现该加哪些规则

```bash
./load.sh ctl 'dump=on'
./capture_live.sh <tag> start
#   操作 App（或等几秒）
./capture_live.sh <tag> stop
./load.sh ctl 'dump=off'

# 从全量路径里挑检测特征
grep -iE 'su|magisk|frida|xposed|riru|zygisk|qemu|nox|emulator' logs/<tag>_allpaths.log | sort -u
# 看调用者：哪些访问来自可疑 so（resolve=on 时）
less logs/<tag>_allpaths_resolved.log
```

把发现的特征按上面格式加进 `kw_rules[]`。

### 改默认目标 UID

源码顶部 `target_uids[]`（默认 `{10236, 10240, ...}`）。也可不改代码、用 `uidadd=` 运行时加。

---

## 重新编译

**必须用 clang 的 large code model**，否则加载失败（原因见 ARCHITECTURE.md）：

```bash
# 如果当前模块已加载且打开了动态监控，建议先执行：
# ./load.sh ctl 'memdump=off'
# ./load.sh ctl 'memmon=off'
# ./load.sh ctl 'exitmon=off'
cd src
make            # 默认用 AOSP 自带 clang (clang-r522817)
cd ..
./load.sh reload
```

`src/Makefile` 会生成 `src/syscallhook.kpm` 并同步到项目根目录 `syscallhook.kpm`，供 `load.sh` 推送。
`CLANG` / `LD_LLD` 可覆盖为你自己的 clang 路径。

---

## 注意事项

### 能力边界：路径检测有效，内容检测无效

模块只伪造 syscall **返回值**：
- ✅ **路径类检测**（su 路径、模拟器特征文件、注入库文件名）—— 文件存在性检测被骗过。
- ❌ **内容类检测**（读 `/proc/self/maps` 扫内存、`/proc/cpuinfo` 看 CPU 指纹、
  `/proc/<pid>/status` 查 TracerPid 或线程名）—— 文件必然存在，App 看的是内容，
  伪造返回值无效。对抗这类需要 hook read 改写内容（本模块未做）。

### BTF / 内核版本适配（内核态解析）

模块大部分能力跨内核通用，**只有内核态解析（resolve=on）依赖 `vm_area_struct`
字段偏移**。当前值取自本设备 BTF（android13-5.10）：源码 `VMA_OFF_VM_START=0x0`、
`VMA_OFF_VM_FILE=0xa0`。

换设备/内核若 resolve 结果明显错乱，用设备自带 BTF 重新取偏移：
```bash
adb shell su -c "cat /sys/kernel/btf/vmlinux" > /tmp/vmlinux.btf
pahole -C vm_area_struct /tmp/vmlinux.btf | grep -E 'vm_start|vm_file'
# 改 src/syscallhook.c 的 VMA_OFF_* 宏后 make && ./load.sh reload
```

- `vm_start` 是结构体第一字段，跨版本恒为 0；`vm_file` 偏移可能变。
- 加载时 init 日志打印 `resolve syms: get_task_mm=.. find_vma=.. file_path=..`，
  若有 0 说明该符号在此内核名字不同，resolve 自动降级（仍输出裸 pc/lr，可用 PC 端
  maps 解析兜底）。
- `fget/fput` 只用于 `memmon` 解析 `mmap(fd)` 的 fd 路径兜底；缺失时不影响路径拦截、
  退出监控和内存监控主流程，只是部分 `fdpath` 为空或来自 fd 缓存。
- 6.1+ 内核 vma 改用 maple tree，需重新核对偏移。

### 调试模式开销

- `dump=on` 会持续刷大量日志，调试完务必 `dump=off`。
- `resolve=on` 开销很小（只在命中时解析），可常开。
- `exitmon=on` 会额外挂 8 个退出/发信号 syscall，只记录不拦截；定位完可 `exitmon=off`。
- `memmon=on` 会额外挂内存/线程/ptrace 相关 syscall。默认只打印高价值事件，但启动期仍可能有不少日志；定位完建议 `memmon=off`。
- `memdump=on` 会打印全量内存类 syscall，日志量明显大于默认 `memmon`；只适合短时间排查漏项。
- `exit(status=0)` 不一定表示闪退，可能只是普通线程/子进程退出；优先看
  `[SIGNAL/.../crash=1]`、主进程 `exit_group`、以及 `target_tgid` 是否等于当前主进程。

### 其它

- 默认 superkey 可通过 `XJB_KP_SUPERKEY` 覆盖；不要外传含真实 superkey 的命令历史、脚本或实验记录。
- 加固壳的检测代码常在匿名可执行内存（解析显示 `anon:基址+偏移`）——dump 该段内存
  （`/proc/<tgid>/mem` 从基址起）即可逆向定位检测逻辑。

---

**作者：小肩膀　微信：xiaojianbang8888**
