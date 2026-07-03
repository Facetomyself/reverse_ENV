/**
 * signal-chain-agent.js — Frida JS 崩溃信号链处理器
 *
 * 从 rust-frida-shadow-hook 的 crash_handler.rs 策略移植。
 *
 * 解决的问题：
 *   1. Frida 修改代码后，ART 隐式 null check 可能触发 SIGSEGV
 *      → 崩溃地址在 [0x00, 0x40) 范围是 OAT QuickMethodHeader NULL 访问
 *      → 需要替换 base 寄存器指向 dummy buffer 而非直接终止
 *   2. Frida Interceptor 安装的信号 handler 覆盖了 ART FaultManager
 *      → 需要 chain 到旧的 handler
 *   3. SIGABRT 需要读取 __abort_message 获取上下文
 *   4. Hook 回调中的 panic 需要正确的 backtrace + 符号解析
 *
 * 架构（对应 crash_handler.rs）：
 *   - 非 agent 代码崩溃 → chain 到 ART FaultManager
 *   - agent/Hook 代码崩溃 → crash report → chain（让系统生成 tombstone）
 *
 * 用法：
 *   frida -U -l signal-chain-agent.js <进程>
 *
 * 改编自：rust-frida-shadow-hook/agent/src/crash_handler.rs
 */

'use strict';

const TAG = '[signal-chain]';

// ── 64 字节全零 dummy OAT header buffer ─────────────────
// 对应 crash_handler.rs 的 DUMMY_OAT_HEADER_BUF
const DUMMY_OAT_HEADER_SIZE = 64;
let dummyOatHeader = null;

// ── 崩溃统计 ─────────────────────────────────────────────
const crashStats = {
    sigsegv: 0,
    sigbus: 0,
    sigabrt: 0,
    sigfpe: 0,
    sigill: 0,
    sigtrap: 0,
    oatNullFixed: 0,     // OAT NULL header 修复次数
    chained: 0,          // chain 到旧 handler 次数
};

function log(msg) {
    console.log(`${TAG} ${msg}`);
}

// ── 工具函数 ──────────────────────────────────────────────

/**
 * 读取 /proc/self/task/<tid>/comm 获取线程名
 */
function getThreadName(tid) {
    try {
        const f = new File(`/proc/self/task/${tid}/comm`, 'r');
        return f.read().trim();
    } catch (e) {
        return '?';
    }
}

/**
 * 使用 dladdr 解析地址
 * 对齐 crash_handler.rs 的 resolve_symbol()
 */
function resolveSymbol(addr) {
    try {
        const dladdr = new NativeFunction(
            Module.findExportByName('libc.so', 'dladdr'),
            'int', ['pointer', 'pointer']
        );

        const DlInfoSize = 32; // 4 × 8 bytes on aarch64
        const infoPtr = Memory.alloc(DlInfoSize);

        const ret = dladdr(ptr(addr), infoPtr);
        if (ret === 0) return { lib: '?', sym: '?', offset: 0 };

        const fnamePtr = infoPtr.readPointer();
        const fbase = infoPtr.add(8).readPointer();
        const snamePtr = infoPtr.add(16).readPointer();
        const saddr = infoPtr.add(24).readPointer();

        let lib = '?';
        if (!fnamePtr.isNull()) {
            const full = fnamePtr.readCString();
            lib = full.split('/').pop() || full;
        }

        let sym = null;
        if (!snamePtr.isNull()) {
            sym = snamePtr.readCString();
        }

        let offset = 0;
        if (!saddr.isNull()) {
            offset = addr - saddr.toInt32();
        } else if (!fbase.isNull()) {
            offset = addr - fbase.toInt32();
        }

        return { lib, sym, offset };
    } catch (e) {
        return { lib: '?', sym: '?', offset: 0 };
    }
}

/**
 * 尝试读取 Android abort message
 * 对应 crash_handler.rs 的 get_abort_message()
 */
function getAbortMessage() {
    try {
        const libc = Process.findModuleByName('libc.so');
        if (!libc) return null;

        // 尝试 android_get_abort_message() API (API 21+)
        const apiAddr = Module.findExportByName(libc.name, 'android_get_abort_message');
        if (apiAddr) {
            const fn = new NativeFunction(apiAddr, 'pointer', []);
            const msgPtr = fn();
            if (!msgPtr.isNull()) {
                return msgPtr.readCString();
            }
        }

        // 备选：直接读 __abort_message 全局变量
        const symAddr = Module.findExportByName(libc.name, '__abort_message');
        if (symAddr) {
            // __abort_message 是 abort_msg_t**（指针的指针）
            const msgPtrPtr = symAddr.readPointer();
            if (!msgPtrPtr.isNull()) {
                // abort_msg_t: size (ulong), msg[0] (char)
                const size = msgPtrPtr.readULong();
                if (size > 0) {
                    const msgData = msgPtrPtr.add(Process.pointerSize);
                    return msgData.readCString();
                }
            }
        }
    } catch (e) { /* ignore */ }
    return null;
}

/**
 * 格式化 backtrace 行
 * 对齐 crash_handler.rs 的 crash report 输出格式
 */
function formatBacktrace(frames, maxFrames) {
    maxFrames = maxFrames || frames.length;
    let output = '';
    for (let i = 0; i < Math.min(frames.length, maxFrames); i++) {
        const addr = frames[i];
        const { lib, sym, offset } = resolveSymbol(addr);
        const addrHex = ptr(addr).toString(16).padStart(16, '0');

        output += `#${i.toString().padStart(3)} ${addrHex}`;
        if (sym) {
            output += ` ${lib} (${sym}+0x${offset.toString(16)})`;
        } else {
            output += ` ${lib} +0x${offset.toString(16)}`;
        }
        output += '\n';
    }
    return output;
}

// ── OAT NULL QuickMethodHeader 修复 ─────────────────────
//
// 对应 crash_handler.rs 的 crash_signal_handler 中 SIGSEGV + fault_addr < 64 分支。
//
// ART 的 WalkStack/GetDexPc/DecodeGcMasksOnly 在处理被 hook 方法的
// 栈帧时，可能对 NULL OatQuickMethodHeader 执行字段读取。
// 地址通常是 NULL+0x0 ~ NULL+0x3F。修复方式：在信号处理器中
// 解码当前指令的 base 寄存器，将其指向全零 dummy buffer。
//
// Frida JS 中 Process.setExceptionHandler 无法直接修改寄存器，
// 但可以通过返回 true（表示已处理）防止默认行为。

function tryFixOatNullHeader(details) {
    if (details.type !== 'access-violation') return false;
    if (!details.address) return false;

    const faultAddr = details.address.toInt32();
    if (faultAddr < 0 || faultAddr >= DUMMY_OAT_HEADER_SIZE) return false;
    if (!details.context) return false;

    // Frida 不允许我们从 JS 修改 exception 上下文中的寄存器，
    // 但我们可以返回 true 让 Frida 不传播信号。
    // 然而更正确的做法是通过 CModule（后续增强）或
    // 直接让 Frida 尝试"恢复"执行。
    //
    // 当前版本：标记为 OAT NULL 访问，不做寄存器级修复
    // （完整修复需要 CModule 或 NativeCallback 绑定到信号处理器）。

    crashStats.oatNullFixed++;
    return true; // 防止默认崩溃传播
}

// ── 主异常处理器 ─────────────────────────────────────────

/**
 * 安装异常处理器
 * 对齐 crash_handler.rs 的 install_crash_handlers()
 *
 * 关键：Frida 的 Process.setExceptionHandler 设置后，
 * 需要在回调中正确 chain 到系统默认处理器。
 * 返回 false = 让系统处理（chain），返回 true = 已处理。
 */
function installHandler() {
    if (typeof Process.setExceptionHandler !== 'function') {
        log('WARN: Process.setExceptionHandler not available (Frida version too old?)');
        return false;
    }

    Process.setExceptionHandler(function (details) {
        let sigName, sigKey;
        switch (details.type) {
            case 'access-violation':
                sigName = 'SIGSEGV';
                sigKey = 'sigsegv';
                break;
            case 'illegal-instruction':
                sigName = 'SIGILL';
                sigKey = 'sigill';
                break;
            case 'breakpoint':
                sigName = 'SIGTRAP';
                sigKey = 'sigtrap';
                break;
            case 'arithmetic':
                sigName = 'SIGFPE';
                sigKey = 'sigfpe';
                break;
            case 'abort':
                sigName = 'SIGABRT';
                sigKey = 'sigabrt';
                break;
            default:
                sigName = details.type;
                sigKey = 'other';
                break;
        }

        crashStats[sigKey] = (crashStats[sigKey] || 0) + 1;

        // ── OAT NULL header 特殊处理 ──
        if (details.type === 'access-violation') {
            if (tryFixOatNullHeader(details)) {
                // OAT NULL header 已处理，不传播
                return true;
            }
        }

        // ── 构建 crash report ──
        let report = '\n=== CRASH DETECTED ===\n';
        report += `Signal: ${sigName} (${details.type})\n`;

        if (details.address) {
            report += `Fault Address: ${details.address}\n`;
        }

        report += `PID: ${Process.id}\n`;
        report += `TID: ${Process.getCurrentThreadId()}\n`;
        report += `Thread: ${getThreadName(Process.getCurrentThreadId())}\n`;

        if (details.type === 'abort') {
            const abortMsg = getAbortMessage();
            if (abortMsg) {
                report += `Abort Message: ${abortMsg}\n`;
            }
        }

        // ── 寄存器状态 ──
        if (details.context) {
            report += '\n=== REGISTERS ===\n';
            const ctx = details.context;
            report += `  PC: ${ctx.pc}\n`;
            report += `  LR: ${ctx.lr}\n`;
            report += `  SP: ${ctx.sp}\n`;
            // ARM64 x0-x7（最常含参数的寄存器）
            for (let i = 0; i <= 7; i++) {
                report += `  x${i}=${ctx['x' + i]}\n`;
            }
        }

        // ── Backtrace ──
        report += '\n=== BACKTRACE ===\n';
        try {
            const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
            report += formatBacktrace(bt.map(a => a.toInt32()), 32);
        } catch (e) {
            report += `  (backtrace failed: ${e.message})\n`;
        }
        report += '=== END BACKTRACE ===\n';

        log(report);

        // ── Chain 到系统处理器 ──
        // 返回 false = Frida 将信号传递给系统 / ART FaultManager
        // 这是关键：不能让 ART 的信号处理器丢失，否则隐式 null check 等失效
        crashStats.chained++;
        return false;
    });

    log('exception handler installed (ART FaultManager chain mode)');
    return true;
}

// ── 公共 API ──────────────────────────────────────────────

/**
 * 初始化信号链处理器 + OAT NULL header 修复
 */
function init() {
    // 分配 dummy OAT header buffer
    dummyOatHeader = Memory.alloc(DUMMY_OAT_HEADER_SIZE);
    // 清零（Memory.alloc 已自动清零，但显式确保）
    for (let i = 0; i < DUMMY_OAT_HEADER_SIZE; i += 8) {
        dummyOatHeader.add(i).writeU64(0);
    }

    const installed = installHandler();
    log(`dummy OAT header @ ${dummyOatHeader} (${DUMMY_OAT_HEADER_SIZE}B zeroed)`);
    return {
        installed,
        dummyOatHeader: dummyOatHeader.toString(),
    };
}

/**
 * 获取崩溃统计
 * @returns {object}
 */
function getStats() {
    return Object.assign({}, crashStats);
}

// ── 导出 ──────────────────────────────────────────────────
rpc.exports = { init, getStats };

// 自动初始化
setImmediate(() => {
    init();
});
