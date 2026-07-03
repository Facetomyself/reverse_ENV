#!/usr/bin/env python3
"""Run a Frida agent while xiaojianbang-syscall-filter captures kernel evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

try:
    import frida
except ImportError as exc:
    print(f"[-] python frida module is not available: {exc}", file=sys.stderr)
    sys.exit(2)


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]


def find_project_root(start: pathlib.Path) -> pathlib.Path:
    for path in [start, *start.parents]:
        if (path / "third_party").exists() or (path / "scripts").exists() or (path / "AGENTS.md").exists():
            return path
    return pathlib.Path.cwd().resolve()


PROJECT_ROOT = find_project_root(SCRIPT_DIR)
TOOL_SCF_ROOT = SCRIPT_DIR / "xiaojianbang-syscall-filter"
PROJECT_SCF_ROOT = PROJECT_ROOT / "third_party" / "xiaojianbang-syscall-filter"
PROJECT_ADB = PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb"
PROJECT_ADB_EXE = PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb.exe"
PROJECT_ADB_ALT = PROJECT_ROOT / "third_party" / "platform-tools" / "adb"
PROJECT_ADB_ALT_EXE = PROJECT_ROOT / "third_party" / "platform-tools" / "adb.exe"


def choose_path(env_name: str, candidates: list[pathlib.Path], path_name: str | None = None) -> pathlib.Path:
    override = os.environ.get(env_name)
    if override:
        return pathlib.Path(override).expanduser()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if path_name:
        found = shutil.which(path_name)
        if found:
            return pathlib.Path(found)
    return candidates[0]


SCF_ROOT = choose_path("SYSCALL_FILTER_ROOT", [PROJECT_SCF_ROOT, TOOL_SCF_ROOT])
ADB = choose_path("ADB", [PROJECT_ADB, PROJECT_ADB_EXE, PROJECT_ADB_ALT, PROJECT_ADB_ALT_EXE], "adb")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([str(ADB), *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", "su", "-c", command, **kwargs)


def resolve_package_uid(package: str) -> str:
    checks = [
        ["shell", "cmd", "package", "list", "packages", "-U", package],
        ["shell", "dumpsys", "package", package],
    ]
    for check in checks:
        result = adb(*check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        text = "\n".join(part for part in [result.stdout, result.stderr] if part)
        for pattern in [r"\buid:(\d+)\b", r"\buserId=(\d+)\b", r"\bappId=(\d+)\b"]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return ""


def stop_proc(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Android package identifier to spawn.")
    parser.add_argument("--uid", default="", help="Android app uid for scfilter line selection. Auto-detected when omitted.")
    parser.add_argument("--script", type=pathlib.Path, required=True, help="Main Frida agent.")
    parser.add_argument(
        "--pre-script",
        action="append",
        type=pathlib.Path,
        default=[],
        help="Frida script loaded before --script; may be specified multiple times.",
    )
    parser.add_argument("--tag", default=None)
    parser.add_argument("--duration", type=float, default=35.0)
    parser.add_argument("--device-timeout", type=int, default=10)
    parser.add_argument("--logs-dir", type=pathlib.Path, default=PROJECT_ROOT / "logs")
    parser.add_argument(
        "--no-spawn-gating",
        action="store_true",
        help="Do not attach Frida agents to child processes.",
    )
    parser.add_argument(
        "--spawn-target-regex",
        default=r"^$",
        help="Regex for child process identifiers that should receive agents. Use '.*' for all.",
    )
    parser.add_argument(
        "--child-script",
        type=pathlib.Path,
        default=None,
        help="Frida script for matched child processes. Pre-scripts are still loaded first.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    app_uid = args.uid or resolve_package_uid(args.package)
    if not app_uid:
        print("[-] unable to resolve app uid; pass --uid explicitly", file=sys.stderr)
        return 2
    tag = args.tag or f"frida_scf_{stamp()}"
    scf_raw = SCF_ROOT / "logs" / f"{tag}_raw.log"
    scf_hits = SCF_ROOT / "logs" / f"{tag}_hits.log"
    scf_resolved = SCF_ROOT / "logs" / f"{tag}_resolved.log"
    frida_log = args.logs_dir / f"frida_{tag}.log"
    logcat_log = args.logs_dir / f"logcat_{tag}.log"

    for path in [scf_raw, scf_hits, scf_resolved, frida_log, logcat_log]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    print(f"TAG={tag}", flush=True)
    print(f"PROJECT_ROOT={PROJECT_ROOT}", flush=True)
    print(f"SCF_ROOT={SCF_ROOT}", flush=True)
    print(f"ADB={ADB}", flush=True)
    print(f"APP_UID={app_uid}", flush=True)
    print(f"FRIDA_LOG={frida_log}", flush=True)
    print(f"SCF_RAW={scf_raw}", flush=True)
    print(f"LOGCAT_LOG={logcat_log}", flush=True)

    adb("shell", "am", "force-stop", args.package, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    adb_su("dmesg -C", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    adb("logcat", "-c", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    scf_fp = scf_raw.open("w", encoding="utf-8")
    logcat_fp = logcat_log.open("w", encoding="utf-8", errors="replace")
    scf_proc = subprocess.Popen(
        [str(ADB), "shell", "su", "-c", "dmesg -w 2>/dev/null | grep --line-buffered '\\[scfilter\\]'"],
        stdout=scf_fp,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    logcat_proc = subprocess.Popen(
        [str(ADB), "logcat", "-v", "threadtime"],
        stdout=logcat_fp,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    sessions = {}
    loaded_scripts = []
    attaching_pids = set()
    resumed_pids = set()
    state_lock = threading.RLock()
    start = time.time()
    detached_reason = ""
    child_detached_reasons = []
    spawn_gating_enabled = False
    runner_stopping = False
    spawn_target_re = re.compile(args.spawn_target_regex)

    def emit(line: str) -> None:
        with frida_log.open("a", encoding="utf-8", errors="replace") as fp:
            fp.write(line.rstrip() + "\n")

    def on_message(message: dict, data: bytes | None) -> None:
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict) and payload.get("type") == "log":
                emit(str(payload.get("line", "")))
            else:
                emit(f"[send] {payload}")
        elif message.get("type") == "error":
            emit(f"[script-error] {message}")
        elif message.get("type") == "log":
            emit(f"[console] {message.get('payload', '')}")
        else:
            emit(f"[message] {message}")

    def make_on_detached(detach_pid: int, identifier: str, is_main: bool):
        def on_detached(reason: str, crash: object | None = None) -> None:
            nonlocal detached_reason
            item = f"pid={detach_pid} identifier={identifier} reason={reason} crash={crash}"
            if runner_stopping:
                emit(f"[detached-cleanup] main={is_main} {item}")
            elif is_main:
                detached_reason = item
                emit(f"[detached-main] {item}")
            else:
                child_detached_reasons.append(item)
                emit(f"[detached-child] {item}")
            with state_lock:
                sessions.pop(detach_pid, None)

        return on_detached

    def load_agents_for_pid(device, attach_pid: int, identifier: str, is_main: bool) -> bool:
        with state_lock:
            if attach_pid in sessions or attach_pid in attaching_pids:
                return attach_pid in sessions
            attaching_pids.add(attach_pid)

        try:
            session = device.attach(attach_pid)
            session.on("detached", make_on_detached(attach_pid, identifier, is_main))

            for pre_script in args.pre_script:
                script = session.create_script(pre_script.read_text(encoding="utf-8"))
                script.on("message", on_message)
                script.load()
                loaded_scripts.append(script)
                emit(f"[*] pre-agent loaded pid={attach_pid} identifier={identifier} path={pre_script}")

            agent_path = args.script if is_main or args.child_script is None else args.child_script
            script = session.create_script(agent_path.read_text(encoding="utf-8"))
            script.on("message", on_message)
            script.load()
            loaded_scripts.append(script)

            with state_lock:
                sessions[attach_pid] = session
            emit(f"[*] agent loaded pid={attach_pid} identifier={identifier} main={is_main} path={agent_path}")
            return True
        except Exception as exc:
            emit(f"[attach-agent-error] pid={attach_pid} identifier={identifier} main={is_main} error={exc!r}")
            return False
        finally:
            with state_lock:
                attaching_pids.discard(attach_pid)

    def resume_pid(device, resume_pid_value: int, identifier: str, reason: str) -> None:
        with state_lock:
            if resume_pid_value in resumed_pids:
                return
            resumed_pids.add(resume_pid_value)
        try:
            device.resume(resume_pid_value)
            emit(f"[*] resumed pid={resume_pid_value} identifier={identifier} reason={reason}")
        except Exception as exc:
            emit(f"[resume-error] pid={resume_pid_value} identifier={identifier} reason={reason} error={exc!r}")

    def handle_spawn(device, spawn) -> None:
        spawn_pid = int(getattr(spawn, "pid", 0))
        identifier = str(getattr(spawn, "identifier", ""))
        emit(f"[spawn-added] pid={spawn_pid} identifier={identifier}")
        if spawn_target_re.search(identifier):
            load_agents_for_pid(device, spawn_pid, identifier, False)
            resume_pid(device, spawn_pid, identifier, "target-spawn")
        else:
            resume_pid(device, spawn_pid, identifier, "non-target-spawn")

    rc = 0
    device = None
    try:
        device = frida.get_usb_device(timeout=args.device_timeout)
        pid = device.spawn([args.package])
        emit(f"[*] spawned pid={pid}")
        load_agents_for_pid(device, pid, args.package, True)

        if not args.no_spawn_gating:
            device.on("spawn-added", lambda spawn: handle_spawn(device, spawn))
            device.enable_spawn_gating()
            spawn_gating_enabled = True
            emit("[*] spawn-gating enabled")
            for spawn in device.enumerate_pending_spawn():
                handle_spawn(device, spawn)

        resume_pid(device, pid, args.package, "main")
        while time.time() - start < args.duration:
            if detached_reason:
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        rc = 130
    except Exception as exc:
        rc = 1
        emit(f"[runner-error] {exc!r}")
    finally:
        runner_stopping = True
        adb("shell", "am", "force-stop", args.package, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if device is not None and spawn_gating_enabled:
            try:
                device.disable_spawn_gating()
            except Exception:
                pass
        with state_lock:
            current_sessions = list(sessions.items())
        with ThreadPoolExecutor(max_workers=max(1, len(current_sessions))) as executor:
            futures = [(detach_pid, executor.submit(session.detach)) for detach_pid, session in current_sessions]
            for detach_pid, future in futures:
                try:
                    future.result(timeout=2)
                except TimeoutError:
                    emit(f"[detach-timeout] pid={detach_pid}")
                except Exception as exc:
                    emit(f"[detach-error] pid={detach_pid} error={exc!r}")
        stop_proc(scf_proc)
        stop_proc(logcat_proc)
        scf_fp.close()
        logcat_fp.close()
        adb_su("pkill -f 'dmesg -w'", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

    raw_text = scf_raw.read_text(encoding="utf-8", errors="replace")
    uid_re = re.compile(rf"uid:{re.escape(app_uid)}\b")
    hit_lines = [line for line in raw_text.splitlines() if uid_re.search(line) and " DUMP " not in line]
    scf_hits.write_text("\n".join(hit_lines) + ("\n" if hit_lines else ""), encoding="utf-8")

    resolver = SCF_ROOT / "resolve.py"
    if resolver.exists():
        resolved = run([sys.executable, str(resolver), "--kresolve", str(scf_hits)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        scf_resolved.write_text(resolved.stdout, encoding="utf-8", errors="replace")
    else:
        scf_resolved.write_text("", encoding="utf-8")
        print(f"[warn] resolver not found: {resolver}", flush=True)

    print(f"RC={rc}", flush=True)
    print(f"DETACHED={detached_reason or '<none>'}", flush=True)
    if child_detached_reasons:
        print("CHILD_DETACHED=" + " | ".join(child_detached_reasons[-12:]), flush=True)
    for label, path in [
        ("SCF_HITS", scf_hits),
        ("SCF_RESOLVED", scf_resolved),
        ("FRIDA_LOG", frida_log),
        ("LOGCAT_LOG", logcat_log),
    ]:
        lines = path.read_text(encoding="utf-8", errors="replace").count("\n")
        print(f"{label}={path} lines={lines}", flush=True)

    print("-- scfilter tail --", flush=True)
    print("\n".join(scf_resolved.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
