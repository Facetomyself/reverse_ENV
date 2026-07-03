/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * xiaojianbang-syscall-filter: 按 UID 过滤 App，对 root/frida/xposed/aosp 检测类
 * 系统调用打印 trace 并伪造返回值（-ENOENT）。
 *
 * 基于 KernelPatch demo-syscallhook 扩展。
 *
 * 作者：小肩膀
 * 微信：xiaojianbang8888
 */

#include <compiler.h>
#include <kpmodule.h>
#include <linux/printk.h>
#include <linux/kernel.h>
#include <uapi/asm-generic/unistd.h>
#include <uapi/asm-generic/errno.h>
#include <linux/uaccess.h>
#include <syscall.h>
#include <linux/string.h>
#include <kputils.h>
#include <asm/current.h>
#include <asm/ptrace.h>
#include <linux/sched.h>
#include <linux/err.h>

extern int has_syscall_wrapper;

/* tgid：sched.h 的 __task_pid_nr_ns 依赖未导出的 kf___task_pid_nr_ns 符号，加载会失败，
 * 故自己用 kallsyms_lookup_name 取函数指针（demo 同款）。comm 用 get_task_comm()。 */
static pid_t (*p_task_pid_nr_ns)(struct task_struct *task, enum pid_type type, void *ns) = 0;

/* 内核态调用者解析：命中当下进程必活，用 find_vma 把 pc/lr 解析成 so名!偏移，
 * 根治短命进程（如途虎 fork 检测子进程）事后取不到 maps 的 no-maps 问题。
 * 所有函数都自己 kallsyms 取，避免依赖未导出的 kf_ 封装符号。
 * vm_area_struct 偏移来自本设备 BTF (android13-5.10): vm_start@0x0, vm_file@0xa0。
 * 不同内核版本偏移可能不同，靠 mod_init 里的自检 + g_resolve 开关兜底。 */
static struct mm_struct *(*p_get_task_mm)(struct task_struct *) = 0;
static void (*p_mmput)(struct mm_struct *) = 0;
static struct vm_area_struct *(*p_find_vma)(struct mm_struct *, unsigned long) = 0;
static char *(*p_file_path)(struct file *, char *, int) = 0;
static struct file *(*p_fget)(unsigned int) = 0;
static void (*p_fput)(struct file *) = 0;

#define VMA_OFF_VM_START 0x0
#define VMA_OFF_VM_FILE  0xa0

static int g_resolve = 0; /* 内核态解析调用者 so!偏移（默认关，ctl resolve=on 开） */

KPM_NAME("xiaojianbang-syscall-filter");
KPM_VERSION("1.0.0");
KPM_LICENSE("GPL v2");
KPM_AUTHOR("xiaojianbang");
KPM_DESCRIPTION("Per-UID syscall filter (root/frida/xposed/aosp). Author: xiaojianbang, WeChat: xiaojianbang8888");

/* ============================ 配置 ============================ */

#define MAX_TARGET_UID 8
#define PATH_BUF_LEN 512
#define FD_PATH_LEN 160
#define FD_CACHE_NUM 64
#define MEM_RANGE_NUM 128
#define MEM_NAME_LEN 64

#ifndef PROT_EXEC
#define PROT_EXEC 0x4
#endif
#ifndef MAP_ANONYMOUS
#define MAP_ANONYMOUS 0x20
#endif
#ifndef PR_SET_VMA
#define PR_SET_VMA 0x53564d41
#endif
#ifndef PR_SET_VMA_ANON_NAME
#define PR_SET_VMA_ANON_NAME 0
#endif
#ifndef AT_FDCWD
#define AT_FDCWD -100
#endif

/* 默认目标 UID：川观新闻 10236、1905电影 10240。UID==0 表示空槽。 */
static uid_t target_uids[MAX_TARGET_UID] = { 10236, 10240, 0, 0, 0, 0, 0, 0 };

/* 全局开关 */
static int g_enable_trace = 1; /* 打印命中日志 */
static int g_enable_fake = 1;  /* 伪造返回值 */
static int g_dump_all = 0;     /* 调试：打印目标 UID 的所有 path 类 syscall（不止命中的） */
static int g_exit_trace = 0;   /* 监控退出/致命信号类 syscall（只记录，不拦截） */
static int g_exit_hooks_registered = 0;
static int g_mem_trace = 0;    /* 内存/线程/ptrace 监控，只记录不拦截 */
static int g_mem_dump = 0;     /* 调试：打印目标 UID 的全量内存类 syscall */
static int g_mem_hooks_registered = 0;

/* 规则分类，便于按类开关 */
enum rule_cat {
    CAT_ROOT = 0,
    CAT_FRIDA,
    CAT_XPOSED,
    CAT_AOSP,
    CAT_NUM,
};

static const char *cat_name[CAT_NUM] = { "ROOT", "FRIDA", "XPOSED", "AOSP" };
static int cat_enable[CAT_NUM] = { 1, 1, 1, 1 };

/* 关键词 -> 分类。命中即按该分类伪造返回。
 * 用子串匹配（strstr），对检测对抗足够且快。 */
struct kw_rule {
    const char *kw;
    enum rule_cat cat;
};

static const struct kw_rule kw_rules[] = {
    /* ---- ROOT / Magisk / KernelSU / APatch ---- */
    { "magisk", CAT_ROOT },
    { "/su/", CAT_ROOT },
    { ".magisk", CAT_ROOT },
    { "topjohnwu", CAT_ROOT },
    { "kernelsu", CAT_ROOT },
    { "/data/adb/ksu", CAT_ROOT },
    { "weishu", CAT_ROOT },
    { "apatch", CAT_ROOT },
    { "/data/adb/ap", CAT_ROOT },
    { "supolicy", CAT_ROOT },
    { "busybox", CAT_ROOT },
    { "/data/adb/modules", CAT_ROOT },
    { "daemonsu", CAT_ROOT },
    { "superuser", CAT_ROOT },
    { "/sbin/su", CAT_ROOT },
    { "/system/bin/su", CAT_ROOT },
    { "/system/xbin/su", CAT_ROOT },
    { "/system/sbin/su", CAT_ROOT },
    { "/vendor/bin/su", CAT_ROOT },
    { "/data/local/su", CAT_ROOT },
    { "/data/local/bin/su", CAT_ROOT },
    { "/data/local/xbin/su", CAT_ROOT },
    { "/system/bin/.ext/su", CAT_ROOT },
    { "/system/bin/failsafe/su", CAT_ROOT },
    { "/system/sd/xbin/su", CAT_ROOT },
    { "/system/usr/we-need-root", CAT_ROOT },
    { "/system/app/Superuser", CAT_ROOT },
    { "/cache/su", CAT_ROOT },
    { "/dev/su", CAT_ROOT },
    { "/data/adb/ksud", CAT_ROOT },
    { "/data/adb/magisk", CAT_ROOT },
    { "/vendor/xbin/su", CAT_ROOT },
    { "/odm/bin/su", CAT_ROOT },
    { "/product/bin/su", CAT_ROOT },
    { "/system_ext/bin/su", CAT_ROOT },
    { "/system/su", CAT_ROOT },
    { "/apex/com.android.art/bin/su", CAT_ROOT },
    { "/apex/com.android.runtime/bin/su", CAT_ROOT },
    { "Superuser.apk", CAT_ROOT },
    /* ---- FRIDA / gum / 注入 ---- */
    { "frida", CAT_FRIDA },
    { "gum-js", CAT_FRIDA },
    { "gadget", CAT_FRIDA },
    { "linjector", CAT_FRIDA },
    { "re.frida", CAT_FRIDA },
    { "frida-server", CAT_FRIDA },
    { "frida-agent", CAT_FRIDA },
    { "frida-gadget", CAT_FRIDA },
    { "libgadget", CAT_FRIDA },
    { "libfrida", CAT_FRIDA },
    { "gmain", CAT_FRIDA },        /* frida 线程名 */
    { "gdbus", CAT_FRIDA },        /* frida 线程名 */
    { "gum-js-loop", CAT_FRIDA },
    { "pool-frida", CAT_FRIDA },
    { "/data/local/tmp/re.frida.server", CAT_FRIDA },
    { "27042", CAT_FRIDA },        /* frida 默认端口 */
    { "frida_agent", CAT_FRIDA },
    { "fridaserver", CAT_FRIDA },
    { "collector_lib", CAT_FRIDA },
    /* ---- XPOSED / Riru / Zygisk / LSPosed ---- */
    { "xposed", CAT_XPOSED },
    { "lsposed", CAT_XPOSED },
    { "riru", CAT_XPOSED },
    { "zygisk", CAT_XPOSED },
    { "edxposed", CAT_XPOSED },
    { "de.robv", CAT_XPOSED },
    { "io.github.lsposed", CAT_XPOSED },
    { "substrate", CAT_XPOSED },
    /* ---- AOSP / 模拟器 / 系统完整性检测 ---- */
    { "ro.build.tags", CAT_AOSP },
    { "test-keys", CAT_AOSP },
    { "ro.debuggable", CAT_AOSP },
    { "ro.secure", CAT_AOSP },
    { "qemu", CAT_AOSP },
    { "goldfish", CAT_AOSP },
    { "ranchu", CAT_AOSP },
    { "init.svc.adbd", CAT_AOSP },
    /* 夜神 Nox */
    { "libnox", CAT_AOSP },
    { ".nox.", CAT_AOSP },
    { "nox.rc", CAT_AOSP },
    { "noxd", CAT_AOSP },
    { "nox-", CAT_AOSP },
    { "nox_", CAT_AOSP },
    { "noxscreen", CAT_AOSP },
    { "noxspeedup", CAT_AOSP },
    { "enable_nox", CAT_AOSP },
    { "shellnox", CAT_AOSP },
    /* 逍遥 microvirt / memu */
    { "microvirt", CAT_AOSP },
    { "libmicrovirt", CAT_AOSP },
    { "com.microvirt", CAT_AOSP },
    /* VirtualBox 系 / droid4x / ttVM / vbox86 / androVM */
    { "vboxsf", CAT_AOSP },
    { "vbox-sf", CAT_AOSP },
    { "vbox86", CAT_AOSP },
    { "androVM", CAT_AOSP },
    { "droid4x", CAT_AOSP },
    { "ttVM", CAT_AOSP },
    /* BlueStacks / Bignox */
    { "bluestacks", CAT_AOSP },
    { "com.bignox", CAT_AOSP },
    { "bignox", CAT_AOSP },
    /* 注意：/proc/cpuinfo、/proc/tty/drivers 是必然存在的文件，检测靠内容而非
     * 存在性，不能伪造 -ENOENT（会刷爆日志且破坏正常功能），故不列入。 */
    { "qemu-props", CAT_AOSP },
};

#define KW_RULE_NUM (sizeof(kw_rules) / sizeof(kw_rules[0]))

/* 每类伪造的 errno（取负作为返回值） */
static long cat_errno(enum rule_cat cat)
{
    (void)cat;
    return -ENOENT; /* 统一伪造成“文件不存在”，最符合检测语义 */
}

/* ============================ 工具 ============================ */

static inline int uid_is_target(uid_t uid)
{
    for (int i = 0; i < MAX_TARGET_UID; i++) {
        if (target_uids[i] && target_uids[i] == uid) return 1;
    }
    return 0;
}

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

static struct fd_cache_entry fd_cache[FD_CACHE_NUM];
static int fd_cache_next = 0;
static struct mem_range_entry mem_ranges[MEM_RANGE_NUM];
static int mem_range_next = 0;

static void fd_cache_del(pid_t tgid, int fd)
{
    for (int i = 0; i < FD_CACHE_NUM; i++) {
        if (fd_cache[i].tgid == tgid && fd_cache[i].fd == fd) {
            fd_cache[i].tgid = 0;
            fd_cache[i].fd = -1;
            fd_cache[i].path[0] = '\0';
        }
    }
}

static void fd_cache_put(pid_t tgid, int fd, const char *path)
{
    if (fd < 0 || !path || !path[0]) return;
    fd_cache_del(tgid, fd);
    int idx = fd_cache_next++ % FD_CACHE_NUM;
    fd_cache[idx].tgid = tgid;
    fd_cache[idx].fd = fd;
    strncpy(fd_cache[idx].path, path, sizeof(fd_cache[idx].path) - 1);
    fd_cache[idx].path[sizeof(fd_cache[idx].path) - 1] = '\0';
}

static const char *fd_cache_get(pid_t tgid, int fd)
{
    for (int i = 0; i < FD_CACHE_NUM; i++) {
        if (fd_cache[i].tgid == tgid && fd_cache[i].fd == fd && fd_cache[i].path[0])
            return fd_cache[i].path;
    }
    return "";
}

static void mem_range_put(pid_t tgid, unsigned long start, unsigned long len,
                          int prot, int flags, const char *name)
{
    if (!start || !len) return;
    int idx = mem_range_next++ % MEM_RANGE_NUM;
    mem_ranges[idx].tgid = tgid;
    mem_ranges[idx].start = start;
    mem_ranges[idx].end = start + len;
    if (mem_ranges[idx].end < start) mem_ranges[idx].end = ~0UL;
    mem_ranges[idx].prot = prot;
    mem_ranges[idx].flags = flags;
    if (name && name[0]) {
        strncpy(mem_ranges[idx].name, name, sizeof(mem_ranges[idx].name) - 1);
        mem_ranges[idx].name[sizeof(mem_ranges[idx].name) - 1] = '\0';
    } else {
        mem_ranges[idx].name[0] = '\0';
    }
}

static int mem_range_intersects(pid_t tgid, unsigned long start, unsigned long len)
{
    unsigned long end;
    if (!start || !len) return 0;
    end = start + len;
    if (end < start) end = ~0UL;
    for (int i = 0; i < MEM_RANGE_NUM; i++) {
        if (mem_ranges[i].tgid != tgid || !mem_ranges[i].start || !mem_ranges[i].end) continue;
        if (start < mem_ranges[i].end && end > mem_ranges[i].start) return 1;
    }
    return 0;
}

static int describe_fd_path(int fd, char *out, int outlen)
{
    if (outlen <= 0) return 0;
    out[0] = '\0';
    if (fd < 0) return 0;

    pid_t tgid = p_task_pid_nr_ns ? p_task_pid_nr_ns(current, PIDTYPE_TGID, 0) : 0;
    const char *cached = fd_cache_get(tgid, fd);
    if (cached && cached[0]) {
        strncpy(out, cached, outlen - 1);
        out[outlen - 1] = '\0';
        return 1;
    }

    if (p_fget && p_fput && p_file_path) {
        struct file *f = p_fget((unsigned int)fd);
        if (f) {
            char pbuf[256];
            char *pp = p_file_path(f, pbuf, sizeof(pbuf));
            if (pp && !IS_ERR(pp)) {
                strncpy(out, pp, outlen - 1);
                out[outlen - 1] = '\0';
                p_fput(f);
                return 1;
            }
            p_fput(f);
        }
    }
    return 0;
}

/* 在 path 中查找命中的规则，返回命中分类，未命中返回 -1 */
static int match_path(const char *path, const char **hit_kw)
{
    for (int i = 0; i < (int)KW_RULE_NUM; i++) {
        enum rule_cat c = kw_rules[i].cat;
        if (!cat_enable[c]) continue;
        if (strstr(path, kw_rules[i].kw)) {
            if (hit_kw) *hit_kw = kw_rules[i].kw;
            return c;
        }
    }
    return -1;
}

static const char *signal_name(long sig)
{
    switch (sig) {
    case 1:  return "SIGHUP";
    case 2:  return "SIGINT";
    case 3:  return "SIGQUIT";
    case 4:  return "SIGILL";
    case 5:  return "SIGTRAP";
    case 6:  return "SIGABRT";
    case 7:  return "SIGBUS";
    case 8:  return "SIGFPE";
    case 9:  return "SIGKILL";
    case 10: return "SIGUSR1";
    case 11: return "SIGSEGV";
    case 12: return "SIGUSR2";
    case 13: return "SIGPIPE";
    case 14: return "SIGALRM";
    case 15: return "SIGTERM";
    case 16: return "SIGSTKFLT";
    case 17: return "SIGCHLD";
    case 18: return "SIGCONT";
    case 19: return "SIGSTOP";
    case 20: return "SIGTSTP";
    case 21: return "SIGTTIN";
    case 22: return "SIGTTOU";
    case 23: return "SIGURG";
    case 24: return "SIGXCPU";
    case 25: return "SIGXFSZ";
    case 26: return "SIGVTALRM";
    case 27: return "SIGPROF";
    case 28: return "SIGWINCH";
    case 29: return "SIGIO";
    case 30: return "SIGPWR";
    case 31: return "SIGSYS";
    default: return "SIG?";
    }
}

static int signal_is_crash_related(long sig)
{
    switch (sig) {
    case 4:  /* SIGILL */
    case 5:  /* SIGTRAP */
    case 6:  /* SIGABRT */
    case 7:  /* SIGBUS */
    case 8:  /* SIGFPE */
    case 9:  /* SIGKILL */
    case 11: /* SIGSEGV */
    case 15: /* SIGTERM */
    case 31: /* SIGSYS */
        return 1;
    default:
        return 0;
    }
}

/* 读取某个用户态字符串参数到内核 buf。失败返回 0。 */
static int read_user_str(const char __user *uptr, char *buf, int len)
{
    if (!uptr) return 0;
    long n = compat_strncpy_from_user(buf, uptr, len);
    if (n < 0) return 0;
    buf[len - 1] = '\0';
    return 1;
}

/* 取调用者寄存器现场。带 syscall wrapper 的内核，fargs->args[0] 即 pt_regs*。
 * pc=触发 svc 时的用户态 PC，lr(x30)=调用者返回地址，sp=用户栈指针。
 * 拿不到时三者置 0。 */
static struct pt_regs *get_user_regs(hook_fargs4_t *args)
{
    if (has_syscall_wrapper)
        return (struct pt_regs *)args->args[0];
    return 0;
}

/* 内核态把用户态地址 addr 解析成 "so名!0x偏移" 或 "anon:基址+0x偏移"，写入 out。
 * 趁命中进程存活（current 即调用者），用 find_vma 查所属 vma。
 * 失败/未启用时写 "0x<addr>"。 */
static void resolve_addr(struct mm_struct *mm, uint64_t addr, char *out, int outlen)
{
    if (!mm || !p_find_vma || !addr) {
        snprintf(out, outlen, "0x%llx", addr);
        return;
    }
    struct vm_area_struct *vma = p_find_vma(mm, addr);
    if (!vma) {
        snprintf(out, outlen, "0x%llx (no-vma)", addr);
        return;
    }
    unsigned long vm_start = *(unsigned long *)((char *)vma + VMA_OFF_VM_START);
    /* addr 可能落在 find_vma 返回的 vma 之前（find_vma 返回 end>addr 的第一个）。 */
    if (addr < vm_start) {
        snprintf(out, outlen, "0x%llx (gap)", addr);
        return;
    }
    struct file *vf = *(struct file **)((char *)vma + VMA_OFF_VM_FILE);
    if (vf && p_file_path) {
        char pbuf[256];
        char *pp = p_file_path(vf, pbuf, sizeof(pbuf));
        if (pp && !IS_ERR(pp)) {
            /* 取 basename */
            char *base = pp;
            for (char *q = pp; *q; q++)
                if (*q == '/') base = q + 1;
            snprintf(out, outlen, "%s!0x%lx", base, (unsigned long)(addr - vm_start));
            return;
        }
    }
    /* 匿名段（无文件）：动态生成/解密的可执行内存 */
    snprintf(out, outlen, "anon:%lx+0x%lx", vm_start, (unsigned long)(addr - vm_start));
}

/* 统一处理：取 path 参数 -> 匹配 -> 命中则打印+伪造返回。
 * path_argi: 路径参数在 syscall 参数里的下标。 */
static void handle_path_syscall(hook_fargs4_t *args, const char *scname, int path_argi)
{
    uid_t uid = current_uid();
    if (!uid_is_target(uid)) return;

    const char __user *p = (const char __user *)syscall_argn(args, path_argi);
    char buf[PATH_BUF_LEN];
    if (!read_user_str(p, buf, sizeof(buf))) return;

    const char *hit_kw = 0;
    int cat = match_path(buf, &hit_kw);

    struct pt_regs *regs = get_user_regs(args);
    uint64_t pc = regs ? regs->pc : 0;
    uint64_t lr = regs ? regs->regs[30] : 0;
    uint64_t sp = regs ? regs->sp : 0;

    /* 取调用进程 tgid 和进程名，便于区分主进程/子进程（解析 maps 时按 tgid 匹配）。 */
    struct task_struct *task = current;
    pid_t tgid = p_task_pid_nr_ns ? p_task_pid_nr_ns(task, PIDTYPE_TGID, 0) : 0;
    const char *comm = get_task_comm(task);

    /* 内核态解析调用者 so!偏移（命中进程此刻必活，根治 no-maps）。 */
    char pcsym[160] = "", lrsym[160] = "";
    if (g_resolve && p_get_task_mm && (g_dump_all ? 1 : cat >= 0)) {
        struct mm_struct *mm = p_get_task_mm(task);
        if (mm) {
            resolve_addr(mm, pc, pcsym, sizeof(pcsym));
            resolve_addr(mm, lr, lrsym, sizeof(lrsym));
            if (p_mmput) p_mmput(mm);
        }
    }

    if (cat < 0) {
        /* 未命中规则：dump 模式下仍打印，用于发现 App 实际检测的路径特征 */
        if (g_dump_all && g_enable_trace)
            pr_info("[scfilter] uid:%d tgid:%d comm:%s %s DUMP pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s path:%s\n",
                    uid, tgid, comm, scname, pc, lr, sp, pcsym, lrsym, buf);
        return;
    }

    if (g_enable_trace) {
        pr_info("[scfilter] uid:%d tgid:%d comm:%s %s [%s/%s] pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s path:%s\n",
                uid, tgid, comm, scname, cat_name[cat], hit_kw, pc, lr, sp, pcsym, lrsym, buf);
    }

    if (g_enable_fake) {
        args->skip_origin = 1;
        args->ret = cat_errno(cat);
        if (g_enable_trace)
            pr_info("[scfilter] -> FAKE ret=%ld for uid:%d %s\n", args->ret, uid, scname);
    }
}

struct call_ctx {
    uid_t uid;
    pid_t tgid;
    pid_t tid;
    const char *comm;
    uint64_t pc;
    uint64_t lr;
    uint64_t sp;
    char pcsym[160];
    char lrsym[160];
};

static int fill_current_call_ctx(hook_fargs4_t *args, struct call_ctx *ctx)
{
    ctx->uid = current_uid();
    if (!uid_is_target(ctx->uid)) return 0;

    struct pt_regs *regs = get_user_regs(args);
    ctx->pc = regs ? regs->pc : 0;
    ctx->lr = regs ? regs->regs[30] : 0;
    ctx->sp = regs ? regs->sp : 0;

    struct task_struct *task = current;
    ctx->tgid = p_task_pid_nr_ns ? p_task_pid_nr_ns(task, PIDTYPE_TGID, 0) : 0;
    ctx->tid = p_task_pid_nr_ns ? p_task_pid_nr_ns(task, PIDTYPE_PID, 0) : 0;
    ctx->comm = get_task_comm(task);
    ctx->pcsym[0] = '\0';
    ctx->lrsym[0] = '\0';

    if (g_resolve && p_get_task_mm) {
        struct mm_struct *mm = p_get_task_mm(task);
        if (mm) {
            resolve_addr(mm, ctx->pc, ctx->pcsym, sizeof(ctx->pcsym));
            resolve_addr(mm, ctx->lr, ctx->lrsym, sizeof(ctx->lrsym));
            if (p_mmput) p_mmput(mm);
        }
    }
    return 1;
}

static void handle_exit_syscall(hook_fargs4_t *args, const char *scname)
{
    if (!g_exit_trace || !g_enable_trace) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    long status = (long)syscall_argn(args, 0);
    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [EXIT/status=%ld/0x%lx] pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname, status, status,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_signal_syscall(hook_fargs4_t *args, const char *scname,
                                  long target_tgid, long target_tid,
                                  long sig, unsigned long info,
                                  long pidfd, long flags)
{
    if (!g_exit_trace || !g_enable_trace) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [SIGNAL/%s(%ld)/crash=%d] pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s target_tgid:%ld target_tid:%ld pidfd:%ld flags:%ld info:%llx\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname, signal_name(sig), sig, signal_is_crash_related(sig),
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym,
            target_tgid, target_tid, pidfd, flags, (uint64_t)info);
}

static int memmon_enabled(void)
{
    return g_mem_trace && g_enable_trace;
}

static void make_mmap_tags(int prot, int flags, int fd, char *out, int outlen)
{
    out[0] = '\0';
    if (prot & PROT_EXEC)
        strncat(out, "|MEM/EXEC", outlen - strlen(out) - 1);
    if (flags & MAP_ANONYMOUS)
        strncat(out, "|MEM/ANON", outlen - strlen(out) - 1);
    if (fd >= 0)
        strncat(out, "|MEM/FD", outlen - strlen(out) - 1);
    if (!out[0])
        strncat(out, "|MEM/MMAP", outlen - 1);
    out[0] = '[';
    strncat(out, "]", outlen - strlen(out) - 1);
}

static int is_error_ret(long ret)
{
    return ret < 0 && ret > -4096;
}

static void handle_open_after(hook_fargs4_t *args, const char *scname)
{
    long ret = (long)args->ret;
    if (ret < 0) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    char path[PATH_BUF_LEN];
    const char __user *p = (const char __user *)syscall_argn(args, 1);
    if (!read_user_str(p, path, sizeof(path))) return;
    fd_cache_put(ctx.tgid, (int)ret, path);

    if (g_mem_dump && memmon_enabled())
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [FD/OPEN] fd:%ld path:%s ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname, ret, path, ret,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_close_after(hook_fargs4_t *args)
{
    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;
    int fd = (int)syscall_argn(args, 0);
    fd_cache_del(ctx.tgid, fd);
}

static void handle_mmap_after(hook_fargs8_t *args, const char *scname)
{
    if (!memmon_enabled()) return;

    unsigned long addr = (unsigned long)syscall_argn(args, 0);
    unsigned long len = (unsigned long)syscall_argn(args, 1);
    int prot = (int)syscall_argn(args, 2);
    int flags = (int)syscall_argn(args, 3);
    int fd = (int)syscall_argn(args, 4);
    unsigned long off = (unsigned long)syscall_argn(args, 5);
    long ret = (long)args->ret;
    int interesting = g_mem_dump || (prot & PROT_EXEC) || (flags & MAP_ANONYMOUS);
    if (!interesting) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    char fdpath[FD_PATH_LEN];
    fdpath[0] = '\0';
    if (fd >= 0) describe_fd_path(fd, fdpath, sizeof(fdpath));

    if (!is_error_ret(ret))
        mem_range_put(ctx.tgid, (unsigned long)ret, len, prot, flags, fdpath);

    char tag[64];
    make_mmap_tags(prot, flags, fd, tag, sizeof(tag));
    unsigned long end = (!is_error_ret(ret) && len) ? ((unsigned long)ret + len) : 0;
    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s %s addr:%lx len:%lx prot:%x flags:%x fd:%d off:%lx ret:%lx start:%lx end:%lx fdpath:%s pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname, tag,
            addr, len, prot, flags, fd, off, (unsigned long)ret,
            is_error_ret(ret) ? 0UL : (unsigned long)ret, end, fdpath,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_mprotect_after(hook_fargs4_t *args, const char *scname, int has_pkey)
{
    if (!memmon_enabled()) return;

    unsigned long addr = (unsigned long)syscall_argn(args, 0);
    unsigned long len = (unsigned long)syscall_argn(args, 1);
    int prot = (int)syscall_argn(args, 2);
    int pkey = has_pkey ? (int)syscall_argn(args, 3) : -1;
    long ret = (long)args->ret;
    int interesting = g_mem_dump || (prot & PROT_EXEC);
    if (!interesting) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    char vmasym[160] = "";
    if (g_resolve && p_get_task_mm) {
        struct mm_struct *mm = p_get_task_mm(current);
        if (mm) {
            resolve_addr(mm, addr, vmasym, sizeof(vmasym));
            if (p_mmput) p_mmput(mm);
        }
    }
    if ((prot & PROT_EXEC) && ret == 0)
        mem_range_put(ctx.tgid, addr, len, prot, 0, vmasym);

    const char *tag = (prot & PROT_EXEC) ? "[MEM/EXEC]" : "[MEM/MPROTECT]";
    if (has_pkey) {
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s %s addr:%lx len:%lx prot:%x pkey:%d ret:%ld range:%lx-%lx vma:%s pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname,
                tag, addr, len, prot, pkey, ret, addr, addr + len, vmasym,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    } else {
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s %s addr:%lx len:%lx prot:%x ret:%ld range:%lx-%lx vma:%s pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname,
                tag, addr, len, prot, ret, addr, addr + len, vmasym,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    }
}

static void handle_memfd_after(hook_fargs4_t *args)
{
    if (!memmon_enabled()) return;

    char name[PATH_BUF_LEN];
    const char __user *p = (const char __user *)syscall_argn(args, 0);
    if (!read_user_str(p, name, sizeof(name))) name[0] = '\0';
    unsigned int flags = (unsigned int)syscall_argn(args, 1);
    long ret = (long)args->ret;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    char fdname[FD_PATH_LEN];
    snprintf(fdname, sizeof(fdname), "memfd:%s", name);
    if (ret >= 0) fd_cache_put(ctx.tgid, (int)ret, fdname);

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s memfd_create [MEMFD] name:%s flags:%x ret_fd:%ld ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, name, flags, ret, ret,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_simple_mem_after(hook_fargs8_t *args, const char *scname)
{
    if (!memmon_enabled()) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    unsigned long a0 = (unsigned long)syscall_argn(args, 0);
    unsigned long a1 = (unsigned long)syscall_argn(args, 1);
    long ret = (long)args->ret;

    if (!g_mem_dump && !mem_range_intersects(ctx.tgid, a0, a1)) return;

    if (!strcmp(scname, "munmap")) {
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s munmap [MEM/MUNMAP] addr:%lx len:%lx ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, a0, a1, ret,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    } else if (!strcmp(scname, "madvise")) {
        int advice = (int)syscall_argn(args, 2);
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s madvise [MEM/MADVISE] addr:%lx len:%lx advice:%x ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, a0, a1, advice, ret,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    }
}

static void handle_mremap_after(hook_fargs8_t *args)
{
    if (!memmon_enabled()) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    unsigned long old_addr = (unsigned long)syscall_argn(args, 0);
    unsigned long old_size = (unsigned long)syscall_argn(args, 1);
    unsigned long new_size = (unsigned long)syscall_argn(args, 2);
    unsigned long flags = (unsigned long)syscall_argn(args, 3);
    unsigned long new_addr_arg = (unsigned long)syscall_argn(args, 4);
    long ret = (long)args->ret;

    if (!g_mem_dump && !mem_range_intersects(ctx.tgid, old_addr, old_size) &&
        (is_error_ret(ret) || !mem_range_intersects(ctx.tgid, (unsigned long)ret, new_size)))
        return;

    if (!is_error_ret(ret))
        mem_range_put(ctx.tgid, (unsigned long)ret, new_size, 0, 0, "mremap");

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s mremap [MEM/MREMAP] old_addr:%lx old_size:%lx new_size:%lx flags:%lx new_addr_arg:%lx ret:%lx pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, old_addr, old_size, new_size,
            flags, new_addr_arg, (unsigned long)ret,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_prctl_after(hook_fargs8_t *args)
{
    if (!memmon_enabled()) return;

    unsigned long option = (unsigned long)syscall_argn(args, 0);
    unsigned long arg2 = (unsigned long)syscall_argn(args, 1);
    unsigned long arg3 = (unsigned long)syscall_argn(args, 2);
    unsigned long arg4 = (unsigned long)syscall_argn(args, 3);
    unsigned long arg5 = (unsigned long)syscall_argn(args, 4);
    if (!g_mem_dump && !(option == PR_SET_VMA && arg2 == PR_SET_VMA_ANON_NAME)) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    char name[PATH_BUF_LEN];
    name[0] = '\0';
    if (option == PR_SET_VMA && arg2 == PR_SET_VMA_ANON_NAME)
        read_user_str((const char __user *)arg5, name, sizeof(name));
    if (name[0] && (long)args->ret == 0)
        mem_range_put(ctx.tgid, arg3, arg4, 0, 0, name);

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s prctl [MEM/VMA_NAME] option:%lx arg2:%lx arg3:%lx arg4:%lx arg5:%lx ret:%ld anon_name:%s pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, option, arg2, arg3, arg4, arg5,
            (long)args->ret, name, ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_clone_after(hook_fargs8_t *args, const char *scname, int clone3)
{
    if (!memmon_enabled()) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    if (clone3) {
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [THREAD/CLONE] clone_args:%llx size:%llx ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname,
                syscall_argn(args, 0), syscall_argn(args, 1), (long)args->ret,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    } else {
        pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [THREAD/CLONE] flags:%llx stack:%llx parent_tid:%llx child_tid:%llx tls:%llx ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
                ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname,
                syscall_argn(args, 0), syscall_argn(args, 1), syscall_argn(args, 2),
                syscall_argn(args, 3), syscall_argn(args, 4), (long)args->ret,
                ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
    }
}

static void handle_ptrace_after(hook_fargs4_t *args)
{
    if (!memmon_enabled()) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx(args, &ctx)) return;

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s ptrace [DEBUG/PTRACE] request:%ld pid:%ld addr:%llx data:%llx ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm,
            (long)syscall_argn(args, 0), (long)syscall_argn(args, 1),
            syscall_argn(args, 2), syscall_argn(args, 3), (long)args->ret,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

static void handle_wait_after(hook_fargs8_t *args, const char *scname)
{
    if (!memmon_enabled()) return;

    struct call_ctx ctx;
    if (!fill_current_call_ctx((hook_fargs4_t *)args, &ctx)) return;

    pr_info("[scfilter] uid:%d tgid:%d tid:%d comm:%s %s [DEBUG/WAIT] pid_or_id:%ld status_ptr:%llx options:%llx rusage_or_infop:%llx ret:%ld pc:%llx lr:%llx sp:%llx pcsym:%s lrsym:%s\n",
            ctx.uid, ctx.tgid, ctx.tid, ctx.comm, scname,
            (long)syscall_argn(args, 0), syscall_argn(args, 1), syscall_argn(args, 2),
            syscall_argn(args, 3), (long)args->ret,
            ctx.pc, ctx.lr, ctx.sp, ctx.pcsym, ctx.lrsym);
}

/* ============================ 各 syscall 回调 ============================ */
/* 参数布局：
 *   faccessat(dfd, path, mode)            path=arg1
 *   faccessat2(dfd, path, mode, flags)    path=arg1
 *   openat(dfd, path, flags, mode)        path=arg1
 *   openat2(dfd, path, how, size)         path=arg1
 *   newfstatat(dfd, path, statbuf, flag)  path=arg1
 *   readlinkat(dfd, path, buf, sz)        path=arg1
 *   statx(dfd, path, flags, mask, buf)    path=arg1
 *   execve(path, argv, envp)              path=arg0
 *   name_to_handle_at(dfd, path, ...)     path=arg1
 *   exit(status)                          status=arg0
 *   exit_group(status)                    status=arg0
 *   kill(pid, sig)                        pid=arg0 sig=arg1
 *   tkill(tid, sig)                       tid=arg0 sig=arg1
 *   tgkill(tgid, tid, sig)                tgid=arg0 tid=arg1 sig=arg2
 *   rt_sigqueueinfo(pid, sig, info)       pid=arg0 sig=arg1 info=arg2
 *   rt_tgsigqueueinfo(tgid, tid, sig, info) tgid=arg0 tid=arg1 sig=arg2 info=arg3
 *   pidfd_send_signal(pidfd, sig, info, flags) pidfd=arg0 sig=arg1 info=arg2 flags=arg3
 *   mmap(addr, len, prot, flags, fd, off) addr=arg0 len=arg1 prot=arg2 flags=arg3 fd=arg4 off=arg5
 *   mprotect(addr, len, prot)             addr=arg0 len=arg1 prot=arg2
 *   pkey_mprotect(addr, len, prot, pkey)  addr=arg0 len=arg1 prot=arg2 pkey=arg3
 *   memfd_create(name, flags)             name=arg0 flags=arg1
 *   munmap(addr, len)                     addr=arg0 len=arg1
 *   mremap(old, oldsz, newsz, flags, new) old=arg0 oldsz=arg1 newsz=arg2 flags=arg3 new=arg4
 *   madvise(addr, len, advice)            addr=arg0 len=arg1 advice=arg2
 *   prctl(option, arg2, arg3, arg4, arg5) option=arg0
 *   clone(flags, stack, parent_tid, child_tid, tls)
 *   clone3(clone_args, size)
 *   ptrace(request, pid, addr, data)
 *   wait4(pid, status, options, rusage)
 *   waitid(which, upid, infop, options, rusage)
 *   close(fd)
 */

static void before_faccessat(hook_fargs4_t *args, void *udata)  { (void)udata; handle_path_syscall(args, "faccessat", 1); }
static void before_faccessat2(hook_fargs4_t *args, void *udata) { (void)udata; handle_path_syscall(args, "faccessat2", 1); }
static void before_openat(hook_fargs4_t *args, void *udata)     { (void)udata; handle_path_syscall(args, "openat", 1); }
static void before_openat2(hook_fargs4_t *args, void *udata)    { (void)udata; handle_path_syscall(args, "openat2", 1); }
static void before_newfstatat(hook_fargs4_t *args, void *udata) { (void)udata; handle_path_syscall(args, "newfstatat", 1); }
static void before_readlinkat(hook_fargs4_t *args, void *udata) { (void)udata; handle_path_syscall(args, "readlinkat", 1); }
static void before_statx(hook_fargs4_t *args, void *udata)      { (void)udata; handle_path_syscall(args, "statx", 1); }
static void before_execve(hook_fargs4_t *args, void *udata)     { (void)udata; handle_path_syscall(args, "execve", 0); }
static void before_n2h(hook_fargs4_t *args, void *udata)        { (void)udata; handle_path_syscall(args, "name_to_handle_at", 1); }
static void after_openat(hook_fargs4_t *args, void *udata)      { (void)udata; handle_open_after(args, "openat"); }
static void after_openat2(hook_fargs4_t *args, void *udata)     { (void)udata; handle_open_after(args, "openat2"); }
static void after_close(hook_fargs4_t *args, void *udata)       { (void)udata; handle_close_after(args); }
static void before_exit(hook_fargs4_t *args, void *udata)       { (void)udata; handle_exit_syscall(args, "exit"); }
static void before_exit_group(hook_fargs4_t *args, void *udata) { (void)udata; handle_exit_syscall(args, "exit_group"); }
static void before_kill(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "kill",
                          (long)syscall_argn(args, 0), 0,
                          (long)syscall_argn(args, 1), 0, -1, 0);
}
static void before_tkill(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "tkill",
                          0, (long)syscall_argn(args, 0),
                          (long)syscall_argn(args, 1), 0, -1, 0);
}
static void before_tgkill(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "tgkill",
                          (long)syscall_argn(args, 0), (long)syscall_argn(args, 1),
                          (long)syscall_argn(args, 2), 0, -1, 0);
}
static void before_rt_sigqueueinfo(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "rt_sigqueueinfo",
                          (long)syscall_argn(args, 0), 0,
                          (long)syscall_argn(args, 1), syscall_argn(args, 2), -1, 0);
}
static void before_rt_tgsigqueueinfo(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "rt_tgsigqueueinfo",
                          (long)syscall_argn(args, 0), (long)syscall_argn(args, 1),
                          (long)syscall_argn(args, 2), syscall_argn(args, 3), -1, 0);
}
#ifdef __NR_pidfd_send_signal
static void before_pidfd_send_signal(hook_fargs4_t *args, void *udata)
{
    (void)udata;
    handle_signal_syscall(args, "pidfd_send_signal",
                          0, 0,
                          (long)syscall_argn(args, 1), syscall_argn(args, 2),
                          (long)syscall_argn(args, 0), (long)syscall_argn(args, 3));
}
#endif
static void after_mmap(hook_fargs8_t *args, void *udata)          { (void)udata; handle_mmap_after(args, "mmap"); }
static void after_mprotect(hook_fargs4_t *args, void *udata)      { (void)udata; handle_mprotect_after(args, "mprotect", 0); }
#ifdef __NR_pkey_mprotect
static void after_pkey_mprotect(hook_fargs4_t *args, void *udata) { (void)udata; handle_mprotect_after(args, "pkey_mprotect", 1); }
#endif
#ifdef __NR_memfd_create
static void after_memfd_create(hook_fargs4_t *args, void *udata)  { (void)udata; handle_memfd_after(args); }
#endif
static void after_munmap(hook_fargs8_t *args, void *udata)        { (void)udata; handle_simple_mem_after(args, "munmap"); }
static void after_mremap(hook_fargs8_t *args, void *udata)        { (void)udata; handle_mremap_after(args); }
static void after_madvise(hook_fargs8_t *args, void *udata)       { (void)udata; handle_simple_mem_after(args, "madvise"); }
static void after_prctl(hook_fargs8_t *args, void *udata)         { (void)udata; handle_prctl_after(args); }
static void after_clone(hook_fargs8_t *args, void *udata)         { (void)udata; handle_clone_after(args, "clone", 0); }
#ifdef __NR_clone3
static void after_clone3(hook_fargs8_t *args, void *udata)        { (void)udata; handle_clone_after(args, "clone3", 1); }
#endif
static void after_ptrace(hook_fargs4_t *args, void *udata)        { (void)udata; handle_ptrace_after(args); }
static void after_wait4(hook_fargs8_t *args, void *udata)         { (void)udata; handle_wait_after(args, "wait4"); }
static void after_waitid(hook_fargs8_t *args, void *udata)        { (void)udata; handle_wait_after(args, "waitid"); }

/* 注册表：syscall号、参数个数、回调 */
struct sc_hook {
    int nr;
    int narg;
    void *before;
    void *after;
    const char *name;
    int exit_related;
    int mem_related;
};

static struct sc_hook hooks[] = {
    { __NR_faccessat, 3, before_faccessat, 0, "faccessat", 0, 0 },
    { __NR_faccessat2, 4, before_faccessat2, 0, "faccessat2", 0, 0 },
    { __NR_openat, 4, before_openat, 0, "openat", 0, 0 },
    { __NR_openat2, 4, before_openat2, 0, "openat2", 0, 0 },
    { __NR3264_fstatat, 4, before_newfstatat, 0, "newfstatat", 0, 0 },
    { __NR_readlinkat, 4, before_readlinkat, 0, "readlinkat", 0, 0 },
    { __NR_statx, 5, before_statx, 0, "statx", 0, 0 },
    { __NR_execve, 3, before_execve, 0, "execve", 0, 0 },
    { __NR_name_to_handle_at, 5, before_n2h, 0, "name_to_handle_at", 0, 0 },
    { __NR_exit, 1, before_exit, 0, "exit", 1, 0 },
    { __NR_exit_group, 1, before_exit_group, 0, "exit_group", 1, 0 },
    { __NR_kill, 2, before_kill, 0, "kill", 1, 0 },
    { __NR_tkill, 2, before_tkill, 0, "tkill", 1, 0 },
    { __NR_tgkill, 3, before_tgkill, 0, "tgkill", 1, 0 },
    { __NR_rt_sigqueueinfo, 3, before_rt_sigqueueinfo, 0, "rt_sigqueueinfo", 1, 0 },
    { __NR_rt_tgsigqueueinfo, 4, before_rt_tgsigqueueinfo, 0, "rt_tgsigqueueinfo", 1, 0 },
#ifdef __NR_pidfd_send_signal
    { __NR_pidfd_send_signal, 4, before_pidfd_send_signal, 0, "pidfd_send_signal", 1, 0 },
#endif
    { __NR3264_mmap, 6, 0, after_mmap, "mmap", 0, 1 },
    { __NR_mprotect, 3, 0, after_mprotect, "mprotect", 0, 1 },
#ifdef __NR_pkey_mprotect
    { __NR_pkey_mprotect, 4, 0, after_pkey_mprotect, "pkey_mprotect", 0, 1 },
#endif
#ifdef __NR_memfd_create
    { __NR_memfd_create, 2, 0, after_memfd_create, "memfd_create", 0, 1 },
#endif
    { __NR_munmap, 2, 0, after_munmap, "munmap", 0, 1 },
    { __NR_mremap, 5, 0, after_mremap, "mremap", 0, 1 },
    { __NR_madvise, 3, 0, after_madvise, "madvise", 0, 1 },
    { __NR_prctl, 5, 0, after_prctl, "prctl", 0, 1 },
    { __NR_clone, 5, 0, after_clone, "clone", 0, 1 },
#ifdef __NR_clone3
    { __NR_clone3, 2, 0, after_clone3, "clone3", 0, 1 },
#endif
    { __NR_ptrace, 4, 0, after_ptrace, "ptrace", 0, 1 },
    { __NR_wait4, 4, 0, after_wait4, "wait4", 0, 1 },
    { __NR_waitid, 5, 0, after_waitid, "waitid", 0, 1 },
    { __NR_openat, 4, 0, after_openat, "openat(fd)", 0, 1 },
    { __NR_openat2, 4, 0, after_openat2, "openat2(fd)", 0, 1 },
    { __NR_close, 1, 0, after_close, "close(fd)", 0, 1 },
};

#define HOOK_NUM (sizeof(hooks) / sizeof(hooks[0]))

static int register_hooks(int exit_related)
{
    int ok = 0;
    int want = 0;
    for (int i = 0; i < (int)HOOK_NUM; i++) {
        if (hooks[i].mem_related) continue;
        if (hooks[i].exit_related != exit_related) continue;
        want++;
        hook_err_t err = fp_hook_syscalln(hooks[i].nr, hooks[i].narg, hooks[i].before, hooks[i].after, 0);
        if (err) {
            pr_err("[scfilter] hook %s (nr=%d) failed: %d\n", hooks[i].name, hooks[i].nr, err);
        } else {
            ok++;
            pr_info("[scfilter] hooked %s (nr=%d)\n", hooks[i].name, hooks[i].nr);
        }
    }
    pr_info("[scfilter] %s hooks registered: %d/%d\n",
            exit_related ? "exit/signal" : "path", ok, want);
    return ok == want ? 0 : -1;
}

static void unregister_hooks(int exit_related)
{
    for (int i = 0; i < (int)HOOK_NUM; i++) {
        if (hooks[i].mem_related) continue;
        if (hooks[i].exit_related != exit_related) continue;
        fp_unhook_syscalln(hooks[i].nr, hooks[i].before, hooks[i].after);
    }
}

static int register_mem_hooks(void)
{
    int ok = 0;
    int want = 0;
    for (int i = 0; i < (int)HOOK_NUM; i++) {
        if (!hooks[i].mem_related) continue;
        want++;
        hook_err_t err = fp_hook_syscalln(hooks[i].nr, hooks[i].narg, hooks[i].before, hooks[i].after, 0);
        if (err) {
            pr_err("[scfilter] hook %s (nr=%d) failed: %d\n", hooks[i].name, hooks[i].nr, err);
        } else {
            ok++;
            pr_info("[scfilter] hooked %s (nr=%d)\n", hooks[i].name, hooks[i].nr);
        }
    }
    pr_info("[scfilter] mem hooks registered: %d/%d\n", ok, want);
    return ok == want ? 0 : -1;
}

static void unregister_mem_hooks(void)
{
    for (int i = 0; i < (int)HOOK_NUM; i++) {
        if (!hooks[i].mem_related) continue;
        fp_unhook_syscalln(hooks[i].nr, hooks[i].before, hooks[i].after);
    }
}

/* ============================ 生命周期 ============================ */

static long mod_init(const char *args, const char *event, void *__user reserved)
{
    (void)event;
    (void)reserved;
    pr_info("[scfilter] init, args: %s\n", args ? args : "(null)");

    p_task_pid_nr_ns = (typeof(p_task_pid_nr_ns))kallsyms_lookup_name("__task_pid_nr_ns");

    /* 内核态调用者解析所需函数（自己 kallsyms 取，避免 kf_ 封装未导出问题）。 */
    p_get_task_mm = (typeof(p_get_task_mm))kallsyms_lookup_name("get_task_mm");
    p_mmput       = (typeof(p_mmput))kallsyms_lookup_name("mmput");
    p_find_vma    = (typeof(p_find_vma))kallsyms_lookup_name("find_vma");
    p_file_path   = (typeof(p_file_path))kallsyms_lookup_name("file_path");
    p_fget        = (typeof(p_fget))kallsyms_lookup_name("fget");
    p_fput        = (typeof(p_fput))kallsyms_lookup_name("fput");
    pr_info("[scfilter] resolve syms: get_task_mm=%llx mmput=%llx find_vma=%llx file_path=%llx fget=%llx fput=%llx\n",
            (uint64_t)p_get_task_mm, (uint64_t)p_mmput, (uint64_t)p_find_vma, (uint64_t)p_file_path,
            (uint64_t)p_fget, (uint64_t)p_fput);
    if (!p_get_task_mm || !p_mmput || !p_find_vma || !p_file_path)
        pr_warn("[scfilter] 部分解析符号缺失，resolve 模式将降级\n");

    register_hooks(0);
    pr_info("[scfilter] init done, exit/signal hooks are off until ctl exitmon=on; mem hooks are off until ctl memmon=on.\n");
    for (int i = 0; i < MAX_TARGET_UID; i++)
        if (target_uids[i]) pr_info("[scfilter]   target uid=%d\n", target_uids[i]);
    return 0;
}

/* 运行时控制（CTL_ARGS 必须是单个无空格 token，kpatch 只传 argv[0]）：
 *   "trace=on" / "trace=off"      打印开关
 *   "fake=on" / "fake=off"        伪造返回开关
 *   "exitmon=on" / "exitmon=off"  退出/致命信号 syscall 监控开关
 *   "memmon=on" / "memmon=off"    内存/线程/ptrace syscall 监控开关
 *   "memdump=on" / "memdump=off"  全量内存 syscall 调试输出
 *   "ROOT=on" / "ROOT=off"        分类开关（ROOT/FRIDA/XPOSED/AOSP）
 *   "uidadd=10299" / "uiddel=10299" / "uidclear"
 *   其它/空：仅回写当前状态到用户态
 */
static long mod_ctl0(const char *ctl_args, char *__user out_msg, int outlen)
{
    char cmd[128];
    if (ctl_args) {
        strncpy(cmd, ctl_args, sizeof(cmd) - 1);
        cmd[sizeof(cmd) - 1] = '\0';
    } else {
        cmd[0] = '\0';
    }
    pr_info("[scfilter] ctl: %s\n", cmd);

    if (!strncmp(cmd, "uidadd=", 7)) {
        long v = 0; const char *p = cmd + 7;
        while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0');
        for (int i = 0; i < MAX_TARGET_UID; i++)
            if (!target_uids[i]) { target_uids[i] = (uid_t)v; pr_info("[scfilter] add uid %ld\n", v); break; }
    } else if (!strncmp(cmd, "uiddel=", 7)) {
        long v = 0; const char *p = cmd + 7;
        while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0');
        for (int i = 0; i < MAX_TARGET_UID; i++)
            if (target_uids[i] == (uid_t)v) { target_uids[i] = 0; pr_info("[scfilter] del uid %ld\n", v); }
    } else if (!strcmp(cmd, "uidclear")) {
        for (int i = 0; i < MAX_TARGET_UID; i++) target_uids[i] = 0;
    } else if (!strcmp(cmd, "trace=on")) {
        g_enable_trace = 1;
    } else if (!strcmp(cmd, "trace=off")) {
        g_enable_trace = 0;
    } else if (!strcmp(cmd, "fake=on")) {
        g_enable_fake = 1;
    } else if (!strcmp(cmd, "fake=off")) {
        g_enable_fake = 0;
    } else if (!strcmp(cmd, "exitmon=on")) {
        if (!g_exit_hooks_registered) {
            if (register_hooks(1) == 0) {
                g_exit_hooks_registered = 1;
            } else {
                unregister_hooks(1);
                g_exit_hooks_registered = 0;
            }
        }
        g_exit_trace = g_exit_hooks_registered ? 1 : 0;
    } else if (!strcmp(cmd, "exitmon=off")) {
        g_exit_trace = 0;
        if (g_exit_hooks_registered) {
            unregister_hooks(1);
            g_exit_hooks_registered = 0;
        }
    } else if (!strcmp(cmd, "memmon=on")) {
        if (!g_mem_hooks_registered) {
            if (register_mem_hooks() == 0) {
                g_mem_hooks_registered = 1;
            } else {
                unregister_mem_hooks();
                g_mem_hooks_registered = 0;
            }
        }
        g_mem_trace = g_mem_hooks_registered ? 1 : 0;
    } else if (!strcmp(cmd, "memmon=off")) {
        g_mem_trace = 0;
        if (g_mem_hooks_registered) {
            unregister_mem_hooks();
            g_mem_hooks_registered = 0;
        }
    } else if (!strcmp(cmd, "memdump=on")) {
        g_mem_dump = 1;
    } else if (!strcmp(cmd, "memdump=off")) {
        g_mem_dump = 0;
    } else if (!strcmp(cmd, "dump=on")) {
        g_dump_all = 1;
    } else if (!strcmp(cmd, "dump=off")) {
        g_dump_all = 0;
    } else if (!strcmp(cmd, "resolve=on")) {
        g_resolve = 1;
    } else if (!strcmp(cmd, "resolve=off")) {
        g_resolve = 0;
    } else {
        /* 分类开关：<CAT>=on|off */
        int c = -1;
        const char *p = cmd;
        if (!strncmp(cmd, "ROOT=", 5)) { c = CAT_ROOT; p = cmd + 5; }
        else if (!strncmp(cmd, "FRIDA=", 6)) { c = CAT_FRIDA; p = cmd + 6; }
        else if (!strncmp(cmd, "XPOSED=", 7)) { c = CAT_XPOSED; p = cmd + 7; }
        else if (!strncmp(cmd, "AOSP=", 5)) { c = CAT_AOSP; p = cmd + 5; }
        if (c >= 0) {
            cat_enable[c] = !strncmp(p, "on", 2) ? 1 : 0;
            pr_info("[scfilter] cat %s = %d\n", cat_name[c], cat_enable[c]);
        }
    }

    pr_info("[scfilter] status: trace=%d fake=%d dump=%d resolve=%d exitmon=%d hooks=%d memmon=%d memhooks=%d memdump=%d\n",
            g_enable_trace, g_enable_fake, g_dump_all, g_resolve, g_exit_trace, g_exit_hooks_registered,
            g_mem_trace, g_mem_hooks_registered, g_mem_dump);
    pr_info("[scfilter] status_cat: ROOT=%d FRIDA=%d XPOSED=%d AOSP=%d\n",
            cat_enable[0], cat_enable[1], cat_enable[2], cat_enable[3]);
    pr_info("[scfilter] status_uid: uid0=%d uid1=%d uid2=%d uid3=%d\n",
            target_uids[0], target_uids[1], target_uids[2], target_uids[3]);
    pr_info("[scfilter] status_uid: uid4=%d uid5=%d uid6=%d uid7=%d\n",
            target_uids[4], target_uids[5], target_uids[6], target_uids[7]);
    (void)out_msg;
    (void)outlen;
    return 0;
}

static long mod_exit(void *__user reserved)
{
    (void)reserved;
    pr_info("[scfilter] exit, unhooking ...\n");
    unregister_mem_hooks();
    unregister_hooks(1);
    unregister_hooks(0);
    return 0;
}

KPM_INIT(mod_init);
KPM_CTL0(mod_ctl0);
KPM_EXIT(mod_exit);
