#!/usr/bin/env python3
"""Hold a library at linker constructors and immediately dump/fix it with MemDumper.

This tool combines Frida's Python API with MemDumper library mode:

  Frida spawn -> hook linker64 soinfo::call_constructors ->
  target .so mapped -> send hold_ready -> memdumper -l -n <so> -> pull fixed ELF

It is intended for short constructor windows where running a separate Frida CLI
and then manually launching MemDumper may be too slow.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

try:
    import frida
except ImportError as exc:
    print(f"[-] python frida module is not available: {exc}", file=sys.stderr)
    sys.exit(2)


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def find_project_root(start: pathlib.Path) -> pathlib.Path:
    for path in [start, *start.parents]:
        if (path / "third_party").exists() or (path / "AGENTS.md").exists():
            return path
    return pathlib.Path.cwd().resolve()


PROJECT_ROOT = find_project_root(SCRIPT_DIR)


def choose_adb() -> str:
    override = os.environ.get("ADB")
    if override:
        return override
    candidates = [
        PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb",
        PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb.exe",
        PROJECT_ROOT / "third_party" / "platform-tools" / "adb",
        PROJECT_ROOT / "third_party" / "platform-tools" / "adb.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("adb") or "adb"


def choose_memdumper_root() -> pathlib.Path:
    override = os.environ.get("MEMDUMPER_ROOT")
    if override:
        return pathlib.Path(override).expanduser()
    candidates = [
        PROJECT_ROOT / "third_party" / "MemDumper-master",
        SCRIPT_DIR / "MemDumper-master",
        SCRIPT_DIR / "tools" / "MemDumper-master",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


ADB = choose_adb()
MEMDUMPER_ROOT = choose_memdumper_root()


AGENT_TEMPLATE = r"""
'use strict';

const TAG = '[frida-memdump-so]';
const TARGET_NAME = __TARGET_NAME__;
const HOLD_MS = __HOLD_MS__;
const FALLBACK_CALL_CONSTRUCTORS_OFF = __FALLBACK_OFF__;

let held = false;
let calls = 0;

function emit(line, payload) {
  const msg = Object.assign({ type: 'log', line }, payload || {});
  send(msg);
  console.log(`${TAG} ${line}`);
}

function findTargetModule() {
  const direct = Process.findModuleByName(TARGET_NAME);
  if (direct) return direct;
  for (const mod of Process.enumerateModules()) {
    const name = mod.name || '';
    const path = mod.path || '';
    if (name === TARGET_NAME || path.endsWith('/' + TARGET_NAME) || path.indexOf(TARGET_NAME) !== -1) {
      return mod;
    }
  }
  return null;
}

function findLinker() {
  return Process.findModuleByName('linker64') ||
    Process.findModuleByName('/apex/com.android.runtime/bin/linker64');
}

function enumerateSymbols(mod) {
  try {
    if (typeof mod.enumerateSymbols === 'function') {
      return mod.enumerateSymbols();
    }
  } catch (_) {
  }
  try {
    return Module.enumerateSymbols(mod.name);
  } catch (_) {
  }
  try {
    return Module.enumerateSymbols(mod.path);
  } catch (_) {
  }
  return [];
}

function findCallConstructors(linker) {
  const wanted = [
    '__dl__ZN6soinfo17call_constructorsEv',
    'soinfo::call_constructors'
  ];
  for (const sym of enumerateSymbols(linker)) {
    const name = sym.name || '';
    if (wanted.some((needle) => name.indexOf(needle) !== -1)) {
      return { address: sym.address, source: `symbol ${name}` };
    }
  }
  // 符号查找失败：仅在用户显式提供偏移、且偏移校验通过时才使用，否则不猜
  if (FALLBACK_CALL_CONSTRUCTORS_OFF === null) {
    return null;
  }
  const addr = linker.base.add(FALLBACK_CALL_CONSTRUCTORS_OFF);
  if (!validateCodeAddr(addr, linker)) {
    emit(
      `fallback offset 0x${FALLBACK_CALL_CONSTRUCTORS_OFF.toString(16)} failed validation (out of linker range / unreadable / not a prologue)`,
      { type: 'error' }
    );
    return null;
  }
  return {
    address: addr,
    source: `validated fallback linker64+0x${FALLBACK_CALL_CONSTRUCTORS_OFF.toString(16)}`
  };
}

function validateCodeAddr(addr, linker) {
  try {
    if (addr.compare(linker.base) < 0) return false;
    if (addr.compare(linker.base.add(linker.size)) >= 0) return false;
    const insn = addr.readU32();
    if (insn === 0 || insn === 0xffffffff) return false;  // 全零/全一基本不是合法序言
    return true;
  } catch (_) {
    return false;
  }
}

function holdForDump(mod) {
  if (held) return;
  held = true;
  const holdSec = Math.floor(HOLD_MS / 1000);
  emit(
    `HOLD_READY pid=${Process.id} base=${mod.base} size=0x${mod.size.toString(16)} path=${mod.path} hold=${holdSec}s`,
    {
      type: 'hold_ready',
      pid: Process.id,
      base: mod.base.toString(),
      size: `0x${mod.size.toString(16)}`,
      path: mod.path,
      name: TARGET_NAME,
      hold_sec: holdSec
    }
  );
  Thread.sleep(holdSec);
  emit('sleep finished; app thread resumes');
}

function hookCallConstructors() {
  const linker = findLinker();
  if (!linker) {
    emit('linker64 not found', { type: 'error' });
    return;
  }

  const target = findCallConstructors(linker);
  if (!target) {
    emit('cannot resolve soinfo::call_constructors: symbol lookup failed and no valid fallback offset; pass --fallback-call-constructors-offset for this linker version', { type: 'error' });
    return;
  }
  emit(`hook call_constructors at ${target.address} (${target.source}) linker=${linker.base} path=${linker.path}`);

  Interceptor.attach(target.address, {
    onEnter(args) {
      calls += 1;
      const mod = findTargetModule();
      if (mod || calls <= 30) {
        emit(`call_constructors #${calls} target=${mod ? `${mod.base}/0x${mod.size.toString(16)}` : 'no'}`);
      }
      if (mod) {
        holdForDump(mod);
      }
    }
  });
}

function main() {
  emit(`agent loaded process=${Process.name} pid=${Process.id} target=${TARGET_NAME}`);
  hookCallConstructors();
}

setImmediate(main);
"""


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([ADB, *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", "su", "-c", command, **kwargs)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def make_agent(target_name: str, hold_ms: int, fallback_offset: int | None) -> str:
    fallback_js = "null" if fallback_offset is None else f"0x{fallback_offset:x}"
    return (
        AGENT_TEMPLATE
        .replace("__TARGET_NAME__", json.dumps(target_name))
        .replace("__HOLD_MS__", str(hold_ms))
        .replace("__FALLBACK_OFF__", fallback_js)
    )


def prepare_memdumper(remote_dir: str, abi: str) -> str:
    dumper = MEMDUMPER_ROOT / "libs" / abi / "memdumper"
    if not dumper.exists():
        raise FileNotFoundError(
            f"memdumper not found: {dumper}; set MEMDUMPER_ROOT if needed"
        )
    remote_bin = f"{remote_dir}/memdumper"
    adb_su(f"rm -rf {shell_quote(remote_dir)}; mkdir -p {shell_quote(remote_dir)}")
    pushed = adb("push", str(dumper), remote_bin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pushed.stdout, end="")
    print(pushed.stderr, end="", file=sys.stderr)
    if pushed.returncode != 0:
        raise RuntimeError(f"adb push memdumper failed: {pushed.returncode}")
    chmod = adb_su(f"chmod 755 {shell_quote(remote_bin)}", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(chmod.stdout, end="")
    print(chmod.stderr, end="", file=sys.stderr)
    if chmod.returncode != 0:
        raise RuntimeError(f"chmod memdumper failed: {chmod.returncode}")
    return remote_bin


def dump_with_memdumper(
    *,
    pid: int,
    so_name: str,
    remote_dir: str,
    remote_bin: str,
    out_dir: pathlib.Path,
    raw: bool,
    fast: bool,
) -> int:
    started = time.monotonic()
    cmd = [remote_bin, "-i", str(pid), "-l", "-n", so_name]
    if raw:
        cmd.append("-r")
    if fast:
        cmd.append("-f")
    cmd += ["-o", remote_dir]
    dump_cmd = " ".join(cmd)
    dumped = adb_su(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elapsed = time.monotonic() - started
    log_text = dumped.stdout + dumped.stderr + f"\n[host] memdumper_elapsed={elapsed:.3f}s returncode={dumped.returncode}\n"
    (out_dir / "memdumper.log").write_text(log_text, encoding="utf-8", errors="replace")
    print(dumped.stdout, end="")
    print(dumped.stderr, end="", file=sys.stderr)
    print(f"[host] memdumper_elapsed={elapsed:.3f}s returncode={dumped.returncode}", flush=True)
    if dumped.returncode != 0:
        return dumped.returncode

    remote_out = f"{remote_dir}/{so_name}"
    local_out = out_dir / so_name
    pulled = adb("pull", remote_out, str(local_out), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pulled.stdout, end="")
    print(pulled.stderr, end="", file=sys.stderr)
    return pulled.returncode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Android package to spawn.")
    parser.add_argument("--name", required=True, help="Library name, for example libtarget.so.")
    parser.add_argument("--out-dir", type=pathlib.Path, required=True, help="Local output directory.")
    parser.add_argument("--device-dir", default="/data/local/tmp/xjb_frida_memdump", help="Device work/output directory.")
    parser.add_argument("--timestamp-device-dir", action="store_true")
    parser.add_argument("--abi", choices=["arm64-v8a", "armeabi-v7a"], default="arm64-v8a")
    parser.add_argument("--timeout", type=float, default=35.0, help="Host timeout in seconds.")
    parser.add_argument("--hold-ms", type=int, default=20000, help="How long the constructor thread sleeps after hold_ready.")
    parser.add_argument("--fallback-call-constructors-offset", default=None, help="Optional linker64 offset used ONLY if symbol lookup fails. No default; agent aborts instead of guessing.")
    parser.add_argument("--raw", action="store_true", help="Pass MemDumper -r; disables rebuild/fix.")
    parser.add_argument("--fast", action="store_true", help="Pass MemDumper -f.")
    parser.add_argument("--keep-device-files", action="store_true")
    parser.add_argument("--force-stop-before", action="store_true", help="Force-stop package before spawning.")
    parser.add_argument("--no-force-stop-after", action="store_true", help="Do not force-stop package after dump/timeout.")
    parser.add_argument("--clear-logcat", action="store_true", help="Clear logcat before spawning.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    remote_dir = str(args.device_dir)
    if args.timestamp_device_dir:
        remote_dir = f"{remote_dir}_{time.strftime('%Y%m%d_%H%M%S')}"

    fallback_offset = (
        int(str(args.fallback_call_constructors_offset), 0)
        if args.fallback_call_constructors_offset is not None
        else None
    )
    remote_bin = prepare_memdumper(remote_dir, args.abi)
    if args.force_stop_before:
        adb("shell", "am", "force-stop", args.package, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args.clear_logcat:
        adb("logcat", "-c", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    event_q: queue.Queue[dict[str, Any]] = queue.Queue()
    dump_done = threading.Event()
    result: dict[str, int] = {"rc": 1}
    frida_log = out_dir / "frida.log"
    script_obj = None
    session = None

    def append_log(line: str) -> None:
        print(line, flush=True)
        with frida_log.open("a", encoding="utf-8", errors="replace") as fp:
            fp.write(line.rstrip() + "\n")

    def dump_worker(payload: dict[str, Any]) -> None:
        try:
            pid_value = int(payload["pid"])
            (out_dir / "hold_ready.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            maps = adb_su(f"cat /proc/{pid_value}/maps", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out_dir / "maps.txt").write_text(maps.stdout + maps.stderr, encoding="utf-8", errors="replace")
            result["rc"] = dump_with_memdumper(
                pid=pid_value,
                so_name=args.name,
                remote_dir=remote_dir,
                remote_bin=remote_bin,
                out_dir=out_dir,
                raw=args.raw,
                fast=args.fast,
            )
        finally:
            dump_done.set()

    def on_message(message: dict[str, Any], data: bytes | None) -> None:
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict):
                line = str(payload.get("line", payload))
                append_log(f"[agent] {line}")
                if payload.get("type") == "hold_ready":
                    event_q.put(payload)
            else:
                append_log(f"[agent-send] {payload}")
        elif message.get("type") == "error":
            append_log(f"[agent-error] {message}")
        else:
            append_log(f"[agent-message] {message}")

    try:
        device = frida.get_usb_device(timeout=10)
        pid = device.spawn([args.package])
        append_log(f"[host] spawned pid={pid}")
        session = device.attach(pid)
        source = make_agent(args.name, args.hold_ms, fallback_offset)
        (out_dir / "agent.js").write_text(source, encoding="utf-8")
        script_obj = session.create_script(source)
        script_obj.on("message", on_message)
        script_obj.load()
        device.resume(pid)
        append_log("[host] resumed app")

        deadline = time.monotonic() + args.timeout
        worker_started = False
        while time.monotonic() < deadline:
            if not worker_started:
                try:
                    payload = event_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                worker_started = True
                threading.Thread(target=dump_worker, args=(payload,), daemon=True).start()
            if dump_done.wait(timeout=0.1):
                break

        if not worker_started:
            append_log("[host] timeout waiting for hold_ready")
            result["rc"] = 1
        elif not dump_done.is_set():
            append_log("[host] timeout waiting for memdumper")
            result["rc"] = 1
    finally:
        try:
            if script_obj is not None:
                script_obj.unload()
        except Exception:
            pass
        try:
            if session is not None:
                session.detach()
        except Exception:
            pass
        if not args.no_force_stop_after:
            adb("shell", "am", "force-stop", args.package, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not args.keep_device_files:
            adb_su(f"rm -rf {shell_quote(remote_dir)}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out_file = out_dir / args.name
    if out_file.exists():
        print(f"[dumped] {out_file} size={out_file.stat().st_size}", flush=True)
    return int(result["rc"])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
