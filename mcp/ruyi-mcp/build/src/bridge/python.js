/**
 * Python subprocess bridge for ruyipage.
 *
 * Manages a long-lived Python child process running ruyi_bridge.py.
 * Communication via JSON-RPC over stdio: one JSON line per request/response.
 */
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PYTHON_EXE = 'D:\\reverse_ENV\\.venv\\Scripts\\python.exe';
const BRIDGE_SCRIPT = 'D:\\reverse_ENV\\ruyi-mcp\\bridge\\ruyi_bridge.py';
const DEFAULT_CALL_TIMEOUT_MS = 120_000; // 2 minutes for browser ops
// ---------------------------------------------------------------------------
// PythonBridge
// ---------------------------------------------------------------------------
export class PythonBridge {
    proc = null;
    rl = null;
    nextId = 0;
    pending = new Map();
    ready = false;
    readyResolve;
    readyPromise;
    stderrLog = [];
    constructor() {
        this.readyPromise = new Promise((resolve) => {
            this.readyResolve = resolve;
        });
    }
    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------
    async start() {
        if (this.proc)
            return;
        console.error('[ruyi-mcp] Starting Python bridge...');
        this.proc = spawn(PYTHON_EXE, [BRIDGE_SCRIPT], {
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });
        // Readline on stdout for JSON-RPC responses
        this.rl = createInterface({ input: this.proc.stdout });
        this.rl.on('line', (line) => {
            const trimmed = line.trim();
            if (!trimmed)
                return;
            try {
                const response = JSON.parse(trimmed);
                const id = response.id;
                if (id !== null && id !== undefined) {
                    const pending = this.pending.get(id);
                    if (pending) {
                        clearTimeout(pending.timer);
                        this.pending.delete(id);
                        if (response.error) {
                            pending.reject(new Error(`[${response.error.code}] ${response.error.message}` +
                                (response.error.data ? `\n${response.error.data}` : '')));
                        }
                        else {
                            pending.resolve(response.result);
                        }
                    }
                }
            }
            catch {
                // Ignore non-JSON lines
            }
        });
        // Stderr for logs
        this.proc.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg.includes('[ruyi_bridge] Ready')) {
                this.ready = true;
                this.readyResolve();
                console.error('[ruyi-mcp] Python bridge ready');
            }
            else if (msg) {
                this.stderrLog.push(msg);
                console.error(`[ruyi-bridge] ${msg}`);
            }
        });
        // Process exit
        this.proc.on('exit', (code) => {
            console.error(`[ruyi-mcp] Python bridge exited with code ${code}`);
            this.ready = false;
            // Reject all pending
            for (const [id, p] of this.pending) {
                clearTimeout(p.timer);
                p.reject(new Error(`Python bridge exited (code ${code})`));
                this.pending.delete(id);
            }
        });
        this.proc.on('error', (err) => {
            console.error(`[ruyi-mcp] Python bridge spawn error: ${err.message}`);
            this.ready = false;
        });
        // Wait for ready signal
        await this.readyPromise;
    }
    async stop() {
        if (!this.proc)
            return;
        try {
            // Try graceful shutdown
            await this.call('__shutdown__', {}, 5000);
        }
        catch {
            // Force kill
        }
        if (this.rl) {
            this.rl.close();
            this.rl = null;
        }
        if (this.proc) {
            this.proc.kill('SIGTERM');
            // On Windows, SIGTERM is not supported, use taskkill as fallback
            setTimeout(() => {
                if (this.proc && !this.proc.killed) {
                    this.proc.kill('SIGKILL');
                }
            }, 3000);
        }
        this.proc = null;
        this.ready = false;
    }
    // ------------------------------------------------------------------
    // RPC
    // ------------------------------------------------------------------
    async call(method, params, timeoutMs = DEFAULT_CALL_TIMEOUT_MS) {
        if (!this.proc || !this.ready) {
            await this.start();
        }
        const id = ++this.nextId;
        const request = { id, method, params: params || {} };
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`Python bridge call timeout: ${method} (${timeoutMs}ms)`));
            }, timeoutMs);
            this.pending.set(id, { resolve, reject, timer });
            const line = JSON.stringify(request);
            this.proc.stdin.write(line + '\n');
        });
    }
    async notify(method, params) {
        if (!this.proc || !this.ready) {
            await this.start();
        }
        const request = { id: null, method, params: params || {} };
        this.proc.stdin.write(JSON.stringify(request) + '\n');
    }
    // ------------------------------------------------------------------
    // Status
    // ------------------------------------------------------------------
    isRunning() {
        return this.proc !== null && this.ready && !this.proc.killed;
    }
}
//# sourceMappingURL=python.js.map