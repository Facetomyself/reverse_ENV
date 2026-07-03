/**
 * shadow-agent-gadget.js — 复合隐身 Frida Agent
 *
 * 按正确的 timing 编排信号链 → soinfo 隐藏 → VMA 重命名：
 *   1. Phase 0: 检测运行模式（gadget / spawn / attach）
 *   2. Phase 1: 安装信号链处理器（最先，保护后续操作）
 *   3. Phase 2: dl_iterate_phdr + /proc/maps 过滤
 *   4. Phase 3: VMA 匿名映射重命名
 *
 * 对应 rust-frida-shadow-hook 的 agent 启动流程：
 *   hello_entry() → install_crash_handlers() → hide_from_solist() → jsinit()
 *
 * 用法：
 *   # CLI 注入：
 *   frida -U -l shadow-agent-gadget.js <进程>
 *
 *   # Gadget 模式（配置 gadget.config.json）：
 *   { "interaction": { "type": "script", "path": "shadow-agent-gadget.js" } }
 *
 *   # stealth-runner.py 自动加载：
 *   python stealth-runner.py --package com.target.app --mode all
 */

'use strict';

const TAG = '[shadow]';
const VERSION = '1.0.0';

// ── 运行模式检测 ──────────────────────────────────────────
let mode = 'unknown';

function detectMode() {
    try {
        // Gadget 模式：通常没有 Frida CLI 连接
        // Spawn 模式：进程刚启动，线程数少
        // Attach 模式：进程已运行一段时间
        const threads = Process.enumerateThreads();
        const modules = Process.enumerateModules();

        // 如果存在 frida-gadget 模块，则为 gadget 模式
        const hasGadget = modules.some(m =>
            m.name.toLowerCase().includes('gadget') ||
            (m.path && m.path.toLowerCase().includes('gadget'))
        );

        if (hasGadget) {
            mode = 'gadget';
        } else if (threads.length < 10) {
            mode = 'spawn';
        } else {
            mode = 'attach';
        }
    } catch (e) {
        mode = 'attach';
    }
    console.log(`${TAG} mode=${mode} pid=${Process.id} process=${Process.name || '?'}`);
    return mode;
}

// ── 内联模块 ──────────────────────────────────────────────

// 1. 信号链（精简版，完整版见 signal-chain-agent.js）
function installSignalChain() {
    if (typeof Process.setExceptionHandler !== 'function') {
        console.log(`${TAG} [!] setExceptionHandler not available`);
        return false;
    }

    let sigCount = { segv: 0, bus: 0, abrt: 0, fpe: 0, ill: 0, trap: 0 };

    Process.setExceptionHandler(function (details) {
        let sig;
        switch (details.type) {
            case 'access-violation': sig = 'segv'; break;
            case 'illegal-instruction': sig = 'ill'; break;
            case 'breakpoint': sig = 'trap'; break;
            case 'arithmetic': sig = 'fpe'; break;
            case 'abort': sig = 'abrt'; break;
            default: sig = 'other'; break;
        }
        sigCount[sig] = (sigCount[sig] || 0) + 1;

        // OAT NULL header fix: fault < 64 bytes → suppress
        if (details.type === 'access-violation' && details.address) {
            const fault = details.address.toInt32();
            if (fault >= 0 && fault < 64) {
                sigCount.oatFixed = (sigCount.oatFixed || 0) + 1;
                // Let ART handle it — return false to chain
                return false;
            }
        }

        // Always chain to system handler (ART FaultManager)
        return false;
    });

    console.log(`${TAG} [1/3] signal chain installed`);
    return true;
}

// 2. dl_iterate_phdr 过滤
function installPhdrFilter(extraPatterns) {
    const patterns = extraPatterns || ['frida', 'gadget', 'linjector'];
    const libc = Process.findModuleByName('libc.so');
    if (!libc) return false;

    const dlIterate = Module.findExportByName(libc.name, 'dl_iterate_phdr');
    if (!dlIterate) return false;

    function shouldHide(name) {
        if (!name) return false;
        const lower = name.toLowerCase();
        return patterns.some(p => lower.includes(p));
    }

    let filteredTotal = 0;

    Interceptor.attach(dlIterate, {
        onEnter(args) {
            this.origCb = args[0];
            this.filtered = 0;
            this.cbCount = 0;

            const self = this;
            const filterCb = new NativeCallback(function (infoPtr, size, data) {
                let name = '';
                try {
                    const namePtr = infoPtr.add(8).readPointer();
                    if (!namePtr.isNull()) name = namePtr.readCString() || '';
                } catch (e) { /* skip */ }

                if (shouldHide(name)) {
                    self.filtered++;
                    return 0;
                }

                const origFn = new NativeFunction(self.origCb, 'int', ['pointer', 'uint64', 'pointer']);
                return origFn(infoPtr, size, data);
            }, 'int', ['pointer', 'uint64', 'pointer']);

            args[0] = filterCb;
        },
        onLeave() {
            if (this.filtered > 0) filteredTotal += this.filtered;
        }
    });

    console.log(`${TAG} [2/3] dl_iterate_phdr filter installed (${patterns.length} patterns)`);
    return true;
}

// 3. VMA 重命名（尝试性，某些内核可能不支持）
function installVmaHide() {
    const libc = Process.findModuleByName('libc.so');
    if (!libc) return false;

    let prctlAddr = Module.findExportByName(libc.name, 'prctl');
    if (!prctlAddr) {
        // Fallback: try syscall(__NR_prctl, ...)
        prctlAddr = Module.findExportByName(libc.name, 'syscall');
        if (!prctlAddr) {
            console.log(`${TAG} [3/3] VMA hide skipped (no prctl/syscall)`);
            return false;
        }
    }

    const PR_SET_VMA = 0x53564d41;
    const PR_SET_VMA_ANON_NAME = 0;
    const safeNames = [
        '[anon:linker_alloc]', '[anon:stack_and_tls]',
        '[anon:scudo:secondary]', '[anon:libc_malloc]',
    ];
    let nameIdx = 0;

    let renamed = 0;
    let attempted = 0;

    const ranges = Process.enumerateRanges({ protection: 'rwx', coalesce: true });
    for (const range of ranges) {
        if (range.file && range.file.path && range.file.path.length > 0) continue;
        const size = range.size.toInt32();
        if (size <= 0 || size > 10 * 1024 * 1024) continue;

        attempted++;
        try {
            const name = safeNames[nameIdx % safeNames.length];
            nameIdx++;
            const nameBuf = Memory.allocUtf8String(name);

            if (prctlAddr.equals(Module.findExportByName(libc.name, 'syscall'))) {
                // syscall(__NR_prctl, PR_SET_VMA, PR_SET_VMA_ANON_NAME, addr, size, name)
                const syscallFn = new NativeFunction(prctlAddr, 'int',
                    ['int', 'uint64', 'uint64', 'uint64', 'uint64']);
                const NR_PRCTL = (Process.arch === 'arm64') ? 167 : 175;
                syscallFn(NR_PRCTL, PR_SET_VMA, PR_SET_VMA_ANON_NAME, range.base, size, nameBuf);
            } else {
                const prctlFn = new NativeFunction(prctlAddr, 'int',
                    ['int', 'uint64', 'uint64', 'uint64', 'uint64']);
                prctlFn(PR_SET_VMA, PR_SET_VMA_ANON_NAME, range.base, size, nameBuf);
            }
            renamed++;
        } catch (e) {
            // Best-effort, don't crash if prctl fails
        }
    }

    console.log(`${TAG} [3/3] VMA hide: ${renamed}/${attempted} RWX ranges renamed`);
    return true;
}

// ── Gadget 模式专用 ───────────────────────────────────────
//
// 在 gadget 模式下，Frida 内部使用 %load / %resume / %reload 等
// 内置指令。shadow-agent 可以注册自己的 RPC 接口与之共存。

const rpcHandlers = {
    /**
     * 获取当前状态
     * @returns {object}
     */
    status() {
        return {
            version: VERSION,
            mode,
            pid: Process.id,
            process: Process.name || '?',
            modules: Process.enumerateModules().length,
            threads: Process.enumerateThreads().length,
        };
    },

    /**
     * 仅安装信号链（轻量模式）
     */
    signalOnly() {
        return { signal: installSignalChain() };
    },

    /**
     * 完全初始化（默认在脚本加载时执行）
     * @param {string[]} extraPatterns - 额外隐藏模式
     */
    fullInit(extraPatterns) {
        return {
            signal: installSignalChain(),
            phdr: installPhdrFilter(extraPatterns),
            vma: installVmaHide(),
        };
    },
};

// ── 入口 ──────────────────────────────────────────────────

// 在脚本加载时自动检测模式并初始化
setImmediate(function () {
    detectMode();
    console.log(`${TAG} shadow-agent-gadget v${VERSION} — initializing...`);
    installSignalChain();
    installPhdrFilter(null);
    installVmaHide();
    console.log(`${TAG} initialization complete (mode=${mode})`);
});

// 导出 RPC（与 Frida gadget %load / frida CLI 兼容）
rpc.exports = rpcHandlers;

// 兼容 gadget 的 %load 触发
if (typeof global !== 'undefined') {
    global.shadow = rpcHandlers;
}
