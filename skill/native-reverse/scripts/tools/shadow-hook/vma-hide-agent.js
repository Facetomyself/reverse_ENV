/**
 * vma-hide-agent.js — Frida JS VMA 匿名映射重命名
 *
 * 从 rust-frida-shadow-hook 的 vma_name.rs + exec_mem.rs 策略移植。
 *
 * 原理：
 *   使用 Android 内核的 prctl(PR_SET_VMA, PR_SET_VMA_ANON_NAME) 系统调用
 *   给匿名映射（如 Frida 的 RWX 可执行内存、memfd 映射）设置无害名称，
 *   在 /proc/self/maps 中显示为正常字符串而非空或 "[anon:...]"。
 *
 * 对应源码：
 *   - agent/src/vma_name.rs   → prctl(PR_SET_VMA_ANON_NAME) 封装
 *   - agent/src/exec_mem.rs   → wwb_trace_exec / wwb_hook_exec 命名常量
 *
 * 用法：
 *   frida -U -l vma-hide-agent.js <进程>
 *
 * 改编自：rust-frida-shadow-hook/agent/src/vma_name.rs
 */

'use strict';

const TAG = '[vma-hide]';

// ── prctl 常量 ────────────────────────────────────────────
const PR_SET_VMA = 0x53564d41;
const PR_SET_VMA_ANON_NAME = 0;

// ── 无害 VMA 名称池 ───────────────────────────────────────
// rust-frida-shadow-hook 使用 "wwb_hook_exec" / "wwb_trace_exec" 等自定义名
// 这里改用 Android 系统常见的匿名映射名以降低可疑度
const SAFE_NAMES = [
    '[anon:linker_alloc]',
    '[anon:stack_and_tls]',
    '[anon:scudo:secondary]',     // Scudo 内存分配器（Android 11+）
    '[anon:libc_malloc]',
    '[anon:.bss]',
    '[anon:dalvik-LinearAlloc]',
    '[anon:dalvik-CompilerMetadata]',
];

let safeNameIdx = 0;
function nextSafeName() {
    const name = SAFE_NAMES[safeNameIdx % SAFE_NAMES.length];
    safeNameIdx++;
    return name;
}

// ── 日志 ──────────────────────────────────────────────────
function log(msg) {
    console.log(`${TAG} ${msg}`);
}

// ── prctl syscall 绑定 ───────────────────────────────────
//
// prctl PR_SET_VMA_ANON_NAME 在某些 Android 内核上可能有以下行为：
//   1. 正常接受并修改 VMA 名称
//   2. 返回非零但不报错（内核未实现）
//   3. 存储的是用户空间指针（需要 lifetime 保证）
//
// 由于我们从 Frida JS 传入字符串，Java String 的 GC 可能移动对象，
// 所以使用 Memory.allocUtf8String() 分配不可移动的内存。

let prctlFn = null;

function initPrctl() {
    const libc = Process.findModuleByName('libc.so');
    if (!libc) {
        log('WARN: libc.so not found');
        return false;
    }

    // Android 上 prctl 可能是 syscall 包装而非 libc 导出
    // 尝试 Module.findExportByName 或直接 syscall()
    let prctlAddr = Module.findExportByName(libc.name, 'prctl');
    if (!prctlAddr) {
        // 备选：使用 syscall()
        prctlAddr = Module.findExportByName(libc.name, 'syscall');
        if (prctlAddr) {
            // syscall(__NR_prctl, ...)
            // __NR_prctl = 167 on aarch64, 157 on arm, 175 on x86_64
            const arch = Process.arch;
            const NR_PRCTL = (arch === 'arm64') ? 167 :
                             (arch === 'arm')   ? 157 :
                             (arch === 'ia32')  ? 175 : 175; // x86_64

            prctlFn = new NativeFunction(prctlAddr, 'int',
                ['int', 'uint64', 'uint64', 'uint64', 'uint64']);
            // 使用 syscall 包装
            const nrPrctl = NR_PRCTL;
            const origPrctl = prctlFn;
            prctlFn = function(option, arg2, arg3, arg4, arg5) {
                return origPrctl(nrPrctl, option, arg2, arg3, arg4);
            };
        }
    } else {
        prctlFn = new NativeFunction(prctlAddr, 'int',
            ['int', 'uint64', 'uint64', 'uint64', 'uint64']);
    }

    if (!prctlFn) {
        log('WARN: prctl not available');
        return false;
    }

    return true;
}

/**
 * 为地址范围设置 VMA 匿名名称
 * @param {NativePointer} addr - 起始地址
 * @param {number} size - 大小（字节）
 * @param {string} name - 新名称（null-terminated）
 * @returns {boolean} 成功返回 true
 */
function setVmaName(addr, size, name) {
    if (!prctlFn) return false;
    try {
        const nameBuf = Memory.allocUtf8String(name);
        const ret = prctlFn(PR_SET_VMA, PR_SET_VMA_ANON_NAME, addr, size, nameBuf);
        return ret === 0;
    } catch (e) {
        return false;
    }
}

/**
 * 判断一个内存范围是否需要隐藏
 * 匹配条件：
 *   - 匿名映射（无文件路径）
 *   - 权限包含 RWX（可执行+可写）
 *   - 名称可疑（空、frida、gum、memfd、anon）
 */
function isSuspiciousVma(range) {
    // 非匿名映射（有文件路径）通常不需要隐藏
    if (range.file && range.file.path && range.file.path.length > 0) {
        return false;
    }

    const prot = range.protection;
    if (!prot) return false;

    // 可执行 + 可写 = 高度可疑（正常代码页是 r-x 或 r--）
    const isRwx = prot.includes('rwx') ||
                  (prot.includes('r') && prot.includes('w') && prot.includes('x'));

    if (!isRwx) return false;

    return true;
}

/**
 * 扫描所有内存范围并重命名可疑的匿名映射
 * @returns {{renamed: number, failed: number}}
 */
function hideAllSuspiciousVmas() {
    let renamed = 0;
    let failed = 0;

    const ranges = Process.enumerateRanges({ protection: 'rwx', coalesce: true });
    for (const range of ranges) {
        try {
            const name = nextSafeName();
            const size = range.size.toInt32();
            if (size <= 0 || size > 10 * 1024 * 1024) continue; // 跳过异常大小

            if (setVmaName(range.base, size, name)) {
                renamed++;
            } else {
                failed++;
            }
        } catch (e) {
            failed++;
        }
    }

    log(`VMA rename: ${renamed} ok, ${failed} failed (${ranges.length} RWX ranges total)`);
    return { renamed, failed };
}

// ── 公共 API ──────────────────────────────────────────────

function init() {
    if (!initPrctl()) {
        return { available: false, reason: 'prctl not available' };
    }
    log('prctl(PR_SET_VMA) available');

    const result = hideAllSuspiciousVmas();
    return {
        available: true,
        ...result,
    };
}

/**
 * 按地址重命名单个 VMA
 * @param {string|number} addr - 地址（十六进制字符串或数字）
 * @param {string} name - 新名称
 */
function renameVma(addr, name) {
    const ptr = (typeof addr === 'string') ? ptr(addr) : ptr(addr);
    // 查找该地址所在的范围
    const ranges = Process.enumerateRanges({ protection: '---', coalesce: true });
    for (const range of ranges) {
        if (ptr.compare(range.base) >= 0 && ptr.compare(range.base.add(range.size)) < 0) {
            const size = range.size.toInt32();
            const ok = setVmaName(range.base, size, name || nextSafeName());
            log(`rename ${range.base} (${size}B) → ${name || 'auto'}: ${ok ? 'ok' : 'fail'}`);
            return ok;
        }
    }
    log(`no VMA found at ${ptr}`);
    return false;
}

// ── 导出 ──────────────────────────────────────────────────
rpc.exports = { init, renameVma };

setImmediate(() => {
    init();
});
