#!/usr/bin/env python3
"""Push and run the Android arm64 eCapture binary, then pull capture outputs."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
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


def choose_ecapture_root() -> pathlib.Path:
    override = os.environ.get("ECAPTURE_ROOT")
    if override:
        return pathlib.Path(override).expanduser()
    project_root = find_project_root(SCRIPT_DIR)
    candidates = [
        project_root / "third_party" / "ecapture-v2.3.0-android-arm64",
        SCRIPT_DIR / "ecapture-v2.3.0-android-arm64",
        SCRIPT_DIR / "tools" / "ecapture-v2.3.0-android-arm64",
    ]
    for candidate in candidates:
        if (candidate / "ecapture").exists():
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
ECAPTURE_ROOT = choose_ecapture_root()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([ADB, *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", f"su -c {shell_quote(command)}", **kwargs)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def remote_output_path(value: str, device_out_dir: str, allow_url: bool = False) -> str:
    if allow_url and "://" in value:
        return value
    if value.startswith("/"):
        return value
    return f"{device_out_dir}/{value}"


def rewrite_output_args(args: list[str], device_out_dir: str) -> list[str]:
    rewritten = list(args)
    for idx, item in enumerate(args):
        if item.startswith("--pcapfile="):
            rewritten[idx] = "--pcapfile=" + remote_output_path(item.split("=", 1)[1], device_out_dir)
        elif item.startswith("-w="):
            rewritten[idx] = "-w=" + remote_output_path(item.split("=", 1)[1], device_out_dir)
        elif item in {"--pcapfile", "-w"} and idx + 1 < len(args):
            rewritten[idx + 1] = remote_output_path(args[idx + 1], device_out_dir)
        elif item.startswith("--keylogfile="):
            rewritten[idx] = "--keylogfile=" + remote_output_path(item.split("=", 1)[1], device_out_dir)
        elif item.startswith("-k="):
            rewritten[idx] = "-k=" + remote_output_path(item.split("=", 1)[1], device_out_dir)
        elif item in {"--keylogfile", "-k"} and idx + 1 < len(args):
            rewritten[idx + 1] = remote_output_path(args[idx + 1], device_out_dir)
        elif item in {"-l", "--logaddr", "--eventaddr"} and idx + 1 < len(args):
            rewritten[idx + 1] = remote_output_path(args[idx + 1], device_out_dir, allow_url=True)
        elif item.startswith("-l="):
            rewritten[idx] = "-l=" + remote_output_path(item.split("=", 1)[1], device_out_dir, allow_url=True)
        elif item.startswith("--logaddr="):
            rewritten[idx] = "--logaddr=" + remote_output_path(item.split("=", 1)[1], device_out_dir, allow_url=True)
        elif item.startswith("--eventaddr="):
            rewritten[idx] = "--eventaddr=" + remote_output_path(item.split("=", 1)[1], device_out_dir, allow_url=True)
    return rewritten


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Use '--' before native eCapture args, for example: ecapture_android.py -- tls -m text.",
    )
    parser.add_argument("--device-dir", default="/data/local/tmp/xjb_ecapture")
    parser.add_argument("--timestamp-device-dir", action="store_true", help="Append a timestamp to --device-dir to avoid reusing old device files.")
    parser.add_argument("--out-dir", type=pathlib.Path, default=None, help="Local directory for pulled outputs.")
    parser.add_argument("--duration", type=float, default=30.0, help="Seconds to run before stopping.")
    parser.add_argument("--keep-device-files", action="store_true")
    parser.add_argument("--no-clean-device-dir", action="store_true", help="Do not remove --device-dir before pushing ecapture.")
    parser.add_argument("--no-pull", action="store_true", help="Do not pull device output directory.")
    parser.add_argument("ecapture_args", nargs=argparse.REMAINDER, help="Native eCapture args after --.")
    args = parser.parse_args(argv)
    if args.ecapture_args and args.ecapture_args[0] == "--":
        args.ecapture_args = args.ecapture_args[1:]
    if not args.ecapture_args:
        args.ecapture_args = ["tls", "-m", "text"]
    if args.timestamp_device_dir:
        args.device_dir = f"{args.device_dir}_{time.strftime('%Y%m%d_%H%M%S')}"
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ecapture_bin = ECAPTURE_ROOT / "ecapture"
    if not ecapture_bin.exists():
        print(f"[-] ecapture not found: {ecapture_bin}", file=sys.stderr)
        print("    Set ECAPTURE_ROOT=/path/to/ecapture-v2.3.0-android-arm64 if needed.", file=sys.stderr)
        return 2

    local_out = (args.out_dir or (pathlib.Path.cwd() / "logs" / "ecapture")).expanduser().resolve()
    local_out.mkdir(parents=True, exist_ok=True)

    print(f"ECAPTURE_ROOT={ECAPTURE_ROOT}", flush=True)
    print(f"ADB={ADB}", flush=True)
    print(f"LOCAL_OUT={local_out}", flush=True)

    device_bin_dir = f"{args.device_dir}/bin"
    device_out_dir = f"{args.device_dir}/out"
    remote_bin = f"{device_bin_dir}/ecapture"
    quoted_device_dir = shell_quote(args.device_dir)
    quoted_bin_dir = shell_quote(device_bin_dir)
    quoted_out_dir = shell_quote(device_out_dir)
    prepare_device_dir = (
        f"mkdir -p {quoted_bin_dir} {quoted_out_dir}; "
        f"chmod 777 {quoted_bin_dir}; "
        f"chmod 777 {quoted_out_dir}"
    )
    if args.no_clean_device_dir:
        adb_su(prepare_device_dir)
    else:
        adb_su(f"rm -rf {quoted_device_dir}; {prepare_device_dir}")
    push = adb("push", str(ecapture_bin), remote_bin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(push.stdout, end="")
    print(push.stderr, end="", file=sys.stderr)
    if push.returncode != 0:
        return push.returncode
    adb_su(f"chmod 755 {shell_quote(remote_bin)}")

    remote_args = rewrite_output_args(args.ecapture_args, device_out_dir)

    remote_log = f"{device_out_dir}/ecapture_console.log"
    command = "cd {dir}; {bin} {argv} > {log} 2>&1 & echo $!".format(
        dir=quoted_out_dir,
        bin=shell_quote(remote_bin),
        argv=" ".join(shell_quote(item) for item in remote_args),
        log=shell_quote(remote_log),
    )
    start = adb_su(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(start.stdout, end="")
    print(start.stderr, end="", file=sys.stderr)
    pid_match = re.search(r"\b(\d+)\b", start.stdout or "")
    remote_pid = pid_match.group(1) if pid_match else ""
    print(f"REMOTE_PID={remote_pid or '<unknown>'}", flush=True)

    time.sleep(max(0.1, args.duration))
    if remote_pid:
        adb_su(f"kill -INT {remote_pid} 2>/dev/null || kill {remote_pid} 2>/dev/null || true")
    else:
        adb_su("pkill -INT ecapture 2>/dev/null || pkill ecapture 2>/dev/null || true")
    time.sleep(1.0)

    rc = 0
    if not args.no_pull:
        pull = adb("pull", f"{device_out_dir}/.", str(local_out), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(pull.stdout, end="")
        print(pull.stderr, end="", file=sys.stderr)
        rc = pull.returncode

    if not args.keep_device_files:
        adb_su(f"rm -rf {args.device_dir}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[ecapture] output_dir={local_out}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
