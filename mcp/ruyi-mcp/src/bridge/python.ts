/**
 * Python subprocess bridge for ruyipage.
 *
 * Manages a long-lived Python child process running ruyi_bridge.py.
 * Communication via JSON-RPC over stdio: one JSON line per request/response.
 */

import { spawn, ChildProcess } from 'node:child_process';
import { createInterface, Interface } from 'node:readline';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JsonRpcRequest {
  id: number | null;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  id: number | null;
  result?: unknown;
  error?: { code: number; message: string; data?: string };
}

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const PYTHON_EXE = process.env.RUYI_MCP_PYTHON || 'D:\\reverse_ENV\\.venv\\Scripts\\python.exe';
const MODULE_DIR = dirname(fileURLToPath(import.meta.url));
const BRIDGE_SCRIPT = resolve(MODULE_DIR, '../../../bridge/ruyi_bridge.py');

const DEFAULT_CALL_TIMEOUT_MS = 120_000; // 2 minutes for browser ops

// ---------------------------------------------------------------------------
// PythonBridge
// ---------------------------------------------------------------------------

export class PythonBridge {
  private proc: ChildProcess | null = null;
  private rl: Interface | null = null;
  private nextId = 0;
  private pending = new Map<number, PendingCall>();
  private ready = false;
  private readyResolve!: () => void;
  private readyReject!: (reason?: Error) => void;
  private readyPromise: Promise<void>;
  private stderrLog: string[] = [];

  constructor() {
    this.readyPromise = new Promise<void>((resolve) => {
      this.readyResolve = resolve;
      this.readyReject = () => {};
    });
    this.resetReadyPromise();
  }

  private resetReadyPromise(): void {
    this.readyPromise = new Promise<void>((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = (reason?: Error) => reject(reason ?? new Error('Python bridge failed to become ready'));
    });
  }

  // ------------------------------------------------------------------
  // Lifecycle
  // ------------------------------------------------------------------

  async start(): Promise<void> {
    if (this.proc) return;
    this.resetReadyPromise();

    console.error('[ruyi-mcp] Starting Python bridge...');

    this.proc = spawn(PYTHON_EXE, [BRIDGE_SCRIPT], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });

    // Readline on stdout for JSON-RPC responses
    this.rl = createInterface({ input: this.proc.stdout! });
    this.rl.on('line', (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      try {
        const response: JsonRpcResponse = JSON.parse(trimmed);
        const id = response.id;
        if (id !== null && id !== undefined) {
          const pending = this.pending.get(id);
          if (pending) {
            clearTimeout(pending.timer);
            this.pending.delete(id);
            if (response.error) {
              pending.reject(
                new Error(
                  `[${response.error.code}] ${response.error.message}` +
                    (response.error.data ? `\n${response.error.data}` : '')
                )
              );
            } else {
              pending.resolve(response.result);
            }
          }
        }
      } catch {
        // Ignore non-JSON lines
      }
    });

    // Stderr for logs
    this.proc.stderr!.on('data', (data: Buffer) => {
      const msg = data.toString().trim();
      if (msg.includes('[ruyi_bridge] Ready')) {
        this.ready = true;
        this.readyResolve();
        console.error('[ruyi-mcp] Python bridge ready');
      } else if (msg) {
        this.stderrLog.push(msg);
        console.error(`[ruyi-bridge] ${msg}`);
      }
    });

    // Process exit
    this.proc.on('exit', (code) => {
      console.error(`[ruyi-mcp] Python bridge exited with code ${code}`);
      if (!this.ready) {
        const details = this.stderrLog.length
          ? ` Last stderr: ${this.stderrLog[this.stderrLog.length - 1]}`
          : '';
        this.readyReject(new Error(`Python bridge exited before ready (code ${code}).${details}`));
      }
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
      if (!this.ready) {
        this.readyReject(new Error(`Python bridge spawn error: ${err.message}`));
      }
      this.ready = false;
    });

    // Wait for ready signal
    await this.readyPromise;
  }

  async stop(): Promise<void> {
    if (!this.proc) return;

    try {
      // Try graceful shutdown
      await this.call('__shutdown__', {}, 5000);
    } catch {
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

  async call(
    method: string,
    params?: Record<string, unknown>,
    timeoutMs: number = DEFAULT_CALL_TIMEOUT_MS
  ): Promise<unknown> {
    if (!this.proc || !this.ready) {
      await this.start();
    }

    const id = ++this.nextId;
    const request: JsonRpcRequest = { id, method, params: params || {} };

    return new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Python bridge call timeout: ${method} (${timeoutMs}ms)`));
      }, timeoutMs);

      this.pending.set(id, { resolve, reject, timer });

      const line = JSON.stringify(request);
      this.proc!.stdin!.write(line + '\n');
    });
  }

  async notify(method: string, params?: Record<string, unknown>): Promise<void> {
    if (!this.proc || !this.ready) {
      await this.start();
    }

    const request: JsonRpcRequest = { id: null, method, params: params || {} };
    this.proc!.stdin!.write(JSON.stringify(request) + '\n');
  }

  // ------------------------------------------------------------------
  // Status
  // ------------------------------------------------------------------

  isRunning(): boolean {
    return this.proc !== null && this.ready && !this.proc.killed;
  }
}
