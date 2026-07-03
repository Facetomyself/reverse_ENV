#!/usr/bin/env python3
"""Push and run xiaojianbang stealth hook on an Android device."""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import time


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def find_project_root(start: pathlib.Path) -> pathlib.Path:
    for path in [start, *start.parents]:
        if (path / "third_party").exists() or (path / "AGENTS.md").exists():
            return path
    return pathlib.Path.cwd().resolve()


def choose_stealth_root() -> pathlib.Path:
    override = os.environ.get("STEALTH_HOOK_ROOT")
    if override:
        return pathlib.Path(override).expanduser()
    project_root = find_project_root(SCRIPT_DIR)
    candidates = [
        project_root / "third_party" / "xiaojianbang-stealth-hook-main",
        SCRIPT_DIR / "xiaojianbang-stealth-hook-main",
        SCRIPT_DIR / "tools" / "xiaojianbang-stealth-hook-main",
    ]
    for candidate in candidates:
        if (candidate / "release" / "xiaojianbang_hook").exists():
            return candidate
    return candidates[0]


def choose_adb() -> str:
    override = os.environ.get("ADB")
    if override:
        return override
    project_root = find_project_root(SCRIPT_DIR)
    candidates = [
        project_root / "third_party" / "aosp" / "platform-tools" / "adb",
        project_root / "third_party" / "aosp" / "platform-tools" / "adb.exe",
        project_root / "third_party" / "platform-tools" / "adb",
        project_root / "third_party" / "platform-tools" / "adb.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("adb") or "adb"


ADB = choose_adb()
STEALTH_ROOT = choose_stealth_root()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([ADB, *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", "su", "-c", command, **kwargs)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def push_if_exists(local_file: pathlib.Path, remote_file: str, chmod: bool = True) -> int:
    if not local_file.exists():
        return 0
    pushed = adb("push", str(local_file), remote_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pushed.stdout, end="")
    print(pushed.stderr, end="", file=sys.stderr)
    if pushed.returncode != 0:
        return pushed.returncode
    if chmod:
        chmod_result = adb_su(f"chmod 755 {shell_quote(remote_file)}")
        return chmod_result.returncode
    return 0


def push_release_files(device_dir: str, kpm_remote: str) -> int:
    hook_bin = STEALTH_ROOT / "release" / "xiaojianbang_hook"
    kpm_file = STEALTH_ROOT / "release" / "xiaojianbang-stealth-hook.kpm"
    if not hook_bin.exists() or not kpm_file.exists():
        print(f"[-] release files not found under {STEALTH_ROOT / 'release'}", file=sys.stderr)
        print("    Set STEALTH_HOOK_ROOT=/path/to/xiaojianbang-stealth-hook-main if needed.", file=sys.stderr)
        return 2

    adb_su(f"mkdir -p {shell_quote(device_dir)}")
    for local_file, remote_file, chmod in [
        (hook_bin, f"{device_dir}/xiaojianbang_hook", True),
        (STEALTH_ROOT / "userspace" / "kpm_loader", f"{device_dir}/kpm_loader", True),
        (STEALTH_ROOT / "userspace" / "sh_control", f"{device_dir}/sh_control", True),
        (kpm_file, kpm_remote, False),
    ]:
        rc = push_if_exists(local_file, remote_file, chmod=chmod)
        if rc != 0:
            return rc
    return 0


def resolve_pid(package: str) -> str:
    result = adb("shell", "pidof", package, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip().split()[0] if result.stdout.strip() else ""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Use '--' before raw native args, for example: stealth_hook_android.py -- --pid 123 --so libc.so --offset 0x1 --once.",
    )
    parser.add_argument("--device-dir", default="/data/local/tmp/xjb_stealth_hook")
    parser.add_argument("--kpm-remote", default="/sdcard/xiaojianbang-stealth-hook.kpm")
    parser.add_argument("--push-only", action="store_true", help="Only push release files and chmod the userspace tool.")
    parser.add_argument("--kpm-hello", action="store_true", help="Run kpm_loader hello after pushing files.")
    parser.add_argument("--kpm-list", action="store_true", help="Run kpm_loader list after pushing files.")
    parser.add_argument("--load-kpm", action="store_true", help="Run kpm_loader load <kpm-remote> after pushing files.")
    parser.add_argument("--reload-kpm", action="store_true", help="Run kpm_loader reload <kpm-remote> after pushing files.")
    parser.add_argument("--sh-status", action="store_true", help="Run sh_control status after pushing files.")
    parser.add_argument("--package", help="Resolve target pid with pidof before running the hook tool.")
    parser.add_argument("--pid", help="Target pid. Overrides --package.")
    parser.add_argument("--so", help="Target so name for convenience mode.")
    parser.add_argument("--offset", help="Target offset list for convenience mode, for example 0x41ac0,0x41d7c.")
    parser.add_argument("--dump-size", type=int, default=None)
    parser.add_argument("--replace-ret", default=None)
    parser.add_argument("--modify-arg", action="append", default=[])
    parser.add_argument("--listen-ret", action="store_true")
    parser.add_argument("--nth", type=int, default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--query", action="store_true")
    parser.add_argument("--unhook", action="store_true")
    parser.add_argument("--duration", type=float, default=0.0, help="If >0, run in background and stop after this many seconds.")
    parser.add_argument("native_args", nargs=argparse.REMAINDER, help="Raw xiaojianbang_hook args after --.")
    args = parser.parse_args(argv)
    if args.native_args and args.native_args[0] == "--":
        args.native_args = args.native_args[1:]
    return args


def run_helper(device_dir: str, helper: str, helper_args: list[str]) -> int:
    remote_bin = f"{device_dir}/{helper}"
    command = " ".join([shell_quote(remote_bin), *(shell_quote(item) for item in helper_args)])
    result = adb_su(command, stdout=sys.stdout, stderr=sys.stderr)
    return result.returncode


def build_native_args(args: argparse.Namespace, pid: str) -> list[str]:
    if args.native_args:
        return args.native_args
    if not pid or not args.so or not args.offset:
        raise ValueError("convenience mode requires --pid or --package, plus --so and --offset")

    argv = ["--pid", pid, "--so", args.so, "--offset", args.offset]
    if args.dump_size is not None:
        argv += ["--dump-size", str(args.dump_size)]
    if args.listen_ret:
        argv.append("--listen-ret")
    if args.replace_ret is not None:
        argv += ["--replace-ret", str(args.replace_ret)]
    for item in args.modify_arg:
        argv += ["--modify-arg", item]
    if args.nth is not None:
        argv += ["--nth", str(args.nth)]
    if args.once:
        argv.append("--once")
    if args.query:
        argv.append("--query")
    if args.unhook:
        argv.append("--unhook")
    return argv


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(f"STEALTH_ROOT={STEALTH_ROOT}", flush=True)
    print(f"ADB={ADB}", flush=True)

    rc = push_release_files(args.device_dir, args.kpm_remote)
    if rc != 0 or args.push_only:
        if args.push_only and rc == 0:
            print(f"[pushed] userspace={args.device_dir} kpm={args.kpm_remote}", flush=True)
        return rc

    helper_actions = [
        (args.kpm_hello, "kpm_loader", ["hello"]),
        (args.kpm_list, "kpm_loader", ["list"]),
        (args.load_kpm, "kpm_loader", ["load", args.kpm_remote]),
        (args.reload_kpm, "kpm_loader", ["reload", args.kpm_remote]),
        (args.sh_status, "sh_control", ["status"]),
    ]
    ran_helper = False
    for enabled, helper, helper_args in helper_actions:
        if not enabled:
            continue
        ran_helper = True
        rc = run_helper(args.device_dir, helper, helper_args)
        if rc != 0:
            return rc
    if ran_helper and not (args.native_args or args.pid or args.package or args.so or args.offset):
        return 0

    pid = args.pid or (resolve_pid(args.package) if args.package else "")
    try:
        native_args = build_native_args(args, pid)
    except ValueError as exc:
        print(f"[-] {exc}", file=sys.stderr)
        return 2

    remote_bin = f"{args.device_dir}/xiaojianbang_hook"
    if args.duration > 0:
        remote_log = f"{args.device_dir}/stealth_hook.log"
        command = "{bin} {argv} > {log} 2>&1 & echo $!".format(
            bin=shell_quote(remote_bin),
            argv=" ".join(shell_quote(item) for item in native_args),
            log=shell_quote(remote_log),
        )
        start = adb_su(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(start.stdout, end="")
        print(start.stderr, end="", file=sys.stderr)
        time.sleep(max(0.1, args.duration))
        adb_su(f"pkill -INT -f {shell_quote(remote_bin)} 2>/dev/null || true")
        adb_su(f"cat {shell_quote(remote_log)}", stdout=sys.stdout, stderr=sys.stderr)
        return 0

    command = " ".join([shell_quote(remote_bin), *(shell_quote(item) for item in native_args)])
    result = adb_su(command, stdout=sys.stdout, stderr=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
