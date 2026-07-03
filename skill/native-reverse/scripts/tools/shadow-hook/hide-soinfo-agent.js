/**
 * hide-soinfo-agent.js — Frida JS 隐身代理
 *
 * 从 rust-frida-shadow-hook 的 hide_soinfo.c 策略移植。
 * 在 Frida JS 层面近似实现 linker 内部 soinfo 隐藏效果：
 *
 *   1. Hook dl_iterate_phdr → 过滤回调中出现的 frida/gadget 条目
 *   2. Hook open/read → 过滤 /proc/self/maps 中包含 frida 的行
 *   3. Hook r_debug.r_map 遍历路径（拦截常见 linker 符号的读取链）
 *
 * 能力边界：
 *   不同于 C 版 hide_soinfo.c（真正从 soinfo 双向链表中摘除），
 *   Frida JS 版只能做"过滤层"——调用方若直接读取 linker 内部 solist
 *   仍能看到被注入的 SO。但对于绝大多数通过公开 API 枚举模块的检测
 *   SDK（如 dl_iterate_phdr、/proc/self/maps 解析），本脚本有效。
 *
 * 用法：
 *   frida -U -l hide-soinfo-agent.js <目标进程>
 *   或在 gadget 模式下通过 stealth-runner.py 自动加载
 *
 * 改编自：rust-frida-shadow-hook/agent/src/hide_soinfo.c
 */

'use strict';

const TAG = '[hide-soinfo]';

// ── 配置 ──────────────────────────────────────────────────
const HIDDEN_PATTERNS = [
    'frida',
    'gadget',
    'linjector',
    'frida-agent',
    'gum-',
    'gadget-',
];

// 是否也隐藏自身（gadget script 模式）
let HIDE_SELF = false;

// 额外按用户指定的子串匹配
let EXTRA_PATTERNS = [];

// ── 日志 ──────────────────────────────────────────────────
function log(msg) {
    console.log(`${TAG} ${msg}`);
}

// ── 匹配判断 ──────────────────────────────────────────────
function shouldHide(name) {
    if (!name || name === '') return false;
    const all = [...HIDDEN_PATTERNS, ...EXTRA_PATTERNS];
    for (const p of all) {
        if (name.toLowerCase().includes(p.toLowerCase())) return true;
    }
    return false;
}

// ── 1. Hook dl_iterate_phdr ───────────────────────────────
//
// dl_iterate_phdr 原型:
//   int dl_iterate_phdr(int (*callback)(struct dl_phdr_info*, size_t, void*), void* data);
//
// struct dl_phdr_info (aarch64):
//   +0x00: Elf64_Addr  dlpi_addr
//   +0x08: const char* dlpi_name
//   +0x10: const Elf64_Phdr* dlpi_phdr
//   +0x18: Elf64_Half   dlpi_phnum
//   ... (AOSP 自 Android 10+ 还有 dlpi_adds/dlpi_subs 等)
//
// 策略：直接 hook dl_iterate_phdr，在原回调外包装一个过滤层。

function hookDlIteratePhdr() {
    const mod = Process.findModuleByName('libc.so') ||
                Process.findModuleByName('libc.so.6');
    if (!mod) {
        log('WARN: libc.so not found, skip dl_iterate_phdr hook');
        return false;
    }

    const addr = Module.findExportByName(mod.name, 'dl_iterate_phdr');
    if (!addr) {
        log('WARN: dl_iterate_phdr not found in libc');
        return false;
    }

    let hookCount = 0;
    let filteredCount = 0;

    Interceptor.attach(addr, {
        onEnter(args) {
            // args[0] = 原始 callback (struct dl_phdr_info*, size_t, void*) → int
            // args[1] = data
            // 保存后替换为过滤版 callback
            this.origCb = args[0];
            this.dataArg = args[1];
            this.filtered = 0;

            const self = this;
            const filterCb = new NativeCallback(function (infoPtr, size, data) {
                // 读取 dlpi_name
                let name = '';
                try {
                    const namePtr = infoPtr.add(8).readPointer();
                    if (!namePtr.isNull()) {
                        name = namePtr.readCString() || '';
                    }
                } catch (e) { /* ignore */ }

                if (shouldHide(name)) {
                    self.filtered++;
                    return 0; // 跳过该条目
                }

                // 调用原始 callback
                const origFn = new NativeFunction(self.origCb, 'int', ['pointer', 'uint64', 'pointer']);
                return origFn(infoPtr, size, data);
            }, 'int', ['pointer', 'uint64', 'pointer']);

            args[0] = filterCb;
        },
        onLeave(retval) {
            hookCount++;
            if (this.filtered > 0) {
                filteredCount += this.filtered;
                log(`dl_iterate_phdr call #${hookCount}: filtered ${this.filtered} entries`);
            }
        }
    });

    log(`dl_iterate_phdr hooked at ${addr}`);
    return true;
}

// ── 2. Hook open/read — 过滤 /proc/self/maps ──────────────
//
// 部分检测 SDK 不经过 dl_iterate_phdr，直接 open/read /proc/self/maps，
// 手工解析 maps 文本行来枚举模块。我们在 read 返回后过滤包含 frida 的行。
//
// ⚠ 注意事项：
//   - read buffer 大小不定（常见 4KB/64KB），必须以整行为单位过滤
//   - openat 可能代替 open（Android 7+ 常用）
//   - /proc/self/maps 也可能通过 /proc/<pid>/maps 访问
//   - 性能：read 调用频率极高，回调应尽量轻量

function hookProcMapsRead() {
    const libc = Process.findModuleByName('libc.so') ||
                 Process.findModuleByName('libc.so.6');
    if (!libc) return false;

    // 维护一个 fd → path 映射，以便在 read 时判断是否为目标文件
    const fdMap = {};
    const openSym = Module.findExportByName(libc.name, 'open') ||
                    Module.findExportByName(libc.name, 'open64');
    const openatSym = Module.findExportByName(libc.name, 'openat');

    function tryMapFd(fd, pathPtr) {
        try {
            if (!pathPtr || pathPtr.isNull()) return;
            const path = pathPtr.readCString();
            if (path && (path.includes('/proc/') && path.includes('maps'))) {
                fdMap[fd] = path;
            }
        } catch (e) { /* ignore */ }
    }

    if (openSym) {
        Interceptor.attach(openSym, {
            onLeave(retval) {
                const fd = retval.toInt32();
                if (fd >= 0) tryMapFd(fd, this.context.x0); // ARM64: x0 = path
            }
        });
    }

    if (openatSym) {
        Interceptor.attach(openatSym, {
            onLeave(retval) {
                const fd = retval.toInt32();
                if (fd >= 0) tryMapFd(fd, this.context.x1); // ARM64: x0=dirfd, x1=path
            }
        });
    }

    // Hook read — 只修改已跟踪的 /proc/*/maps fd 的返回内容
    const readSym = Module.findExportByName(libc.name, 'read');
    if (readSym) {
        Interceptor.attach(readSym, {
            onEnter(args) {
                const fd = args[0].toInt32();
                this.isMapsFd = !!fdMap[fd];
            },
            onLeave(retval) {
                if (!this.isMapsFd) return;
                const nread = retval.toInt32();
                if (nread <= 0) return;

                // 从 args[1] (buffer) 读取，过滤含 frida 的行
                // ⚠ 这是高频操作，避免 console.log 和复杂字符串处理
                const buf = this.context.x1;
                try {
                    const content = buf.readUtf8String(nread);
                    const lines = content.split('\n');
                    const filtered = lines.filter(l => !shouldHide(l));

                    if (filtered.length !== lines.length) {
                        const newContent = filtered.join('\n');
                        const newLen = Math.min(newContent.length, nread);
                        // 用空格填充剩余
                        const padded = newContent.slice(0, newLen).padEnd(nread, ' ');
                        buf.writeUtf8String(padded);
                        // 保持原始返回长度（调用方不期望长度变化）
                    }
                } catch (e) { /* ignore corrupt reads */ }
            }
        });
        log('open/openat+read maps filter installed');
    }

    return true;
}

// ── 3. Hook linker r_debug 遍历路径 ─────────────────────
//
// 某些高级检测 SDK 会手动遍历 _r_debug.r_map (link_map*) 链表。
// 这些函数通常是 __dl_* 内部符号。我们可以 hook 已知的 linker
// 导出函数来拦截 link_map 的访问。
//
// Android linker 内部关键函数：
// - __dl__Z15solist_get_headv / __dl__ZL6solist  → 获取 soinfo 链表头
// - __dl__ZNK6soinfo12get_realpathEv            → 获取 SO 路径
//
// Frida 无法直接 hook linker 的内部（非导出）符号，但可以 hook
// dladdr (公开 API) 来对地址查询返回混淆后的名称。

function hookDladdr() {
    const libc = Process.findModuleByName('libc.so');
    if (!libc) return;
    const dladdrSym = Module.findExportByName(libc.name, 'dladdr');
    if (!dladdrSym) return;

    Interceptor.attach(dladdrSym, {
        onLeave(retval) {
            if (retval.toInt32() === 0) return;
            // dladdr 填充 Dl_info 结构：
            //   dli_fname (ptr), dli_fbase (ptr), dli_sname (ptr), dli_saddr (ptr)
            const infoPtr = this.context.x1;
            try {
                const fnamePtr = infoPtr.readPointer();
                if (!fnamePtr.isNull()) {
                    const fname = fnamePtr.readCString() || '';
                    if (shouldHide(fname)) {
                        // 替换为无害名称（匿名映射常见名）
                        fnamePtr.writeUtf8String('[anon:stack_and_tls]');
                    }
                }
            } catch (e) { /* ignore */ }
        }
    });
    log('dladdr filter installed');
}

// ── 4. 自检测模式 ─────────────────────────────────────────
//
// gadget 模式下，自动查找自身所属模块并加入隐藏列表

function detectSelf() {
    try {
        // Frida gadget 加载后，当前 SO 路径包含 "frida" / "gadget"
        // 通过回溯调用栈找自身
        const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
        for (const addr of bt) {
            const mod = Process.findModuleByAddress(addr);
            if (mod && shouldHide(mod.name)) {
                if (!HIDDEN_PATTERNS.includes(mod.name)) {
                    HIDDEN_PATTERNS.push(mod.name);
                    log(`auto-hide self: ${mod.name} @ ${mod.base}`);
                }
                HIDE_SELF = true;
                return mod;
            }
        }
    } catch (e) {
        log(`self-detect failed: ${e.message}`);
    }
    return null;
}

// ── 公共 API ──────────────────────────────────────────────

/**
 * 初始化隐身：安装所有 hook
 * @param {string[]} extraPatterns - 额外需要隐藏的模式（SO 名、路径子串）
 */
function init(extraPatterns) {
    if (extraPatterns && Array.isArray(extraPatterns)) {
        EXTRA_PATTERNS = extraPatterns;
    }
    detectSelf();
    log(`hiding patterns: ${JSON.stringify([...HIDDEN_PATTERNS, ...EXTRA_PATTERNS])}`);

    const results = {
        dl_iterate_phdr: hookDlIteratePhdr(),
        maps_read: hookProcMapsRead(),
        dladdr: hookDladdr(),
    };

    log(`hook results: ${JSON.stringify(results)}`);
    return results;
}

/**
 * 运行时添加新的隐藏模式
 * @param {string} pattern
 */
function addPattern(pattern) {
    EXTRA_PATTERNS.push(pattern);
    log(`added pattern: ${pattern}`);
}

/**
 * 移除指定模式
 * @param {string} pattern
 */
function removePattern(pattern) {
    const idx = EXTRA_PATTERNS.indexOf(pattern);
    if (idx >= 0) {
        EXTRA_PATTERNS.splice(idx, 1);
        log(`removed pattern: ${pattern}`);
    }
}

/**
 * 获取当前隐藏的模式列表
 * @returns {string[]}
 */
function getPatterns() {
    return [...HIDDEN_PATTERNS, ...EXTRA_PATTERNS];
}

// ── 导出 ──────────────────────────────────────────────────
// gadget 模式：由 stealth-runner.py 通过 rpc.exports 调用
// CLI 模式：脚本加载时自动执行 init()
rpc.exports = {
    init,
    addPattern,
    removePattern,
    getPatterns,
};

// 在非 gadget 模式下（作为独立脚本加载时）自动初始化
setImmediate(() => {
    init();
});
