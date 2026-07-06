#!/usr/bin/env python3
"""Push MemDumper to an Android device, dump a loaded so, and pull the result."""

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


def choose_memdumper_root() -> pathlib.Path:
    override = os.environ.get("MEMDUMPER_ROOT")
    if override:
        return pathlib.Path(override).expanduser()
    project_root = find_project_root(SCRIPT_DIR)
    candidates = [
        project_root / "third_party" / "MemDumper-master",
        SCRIPT_DIR / "MemDumper-master",
        SCRIPT_DIR / "tools" / "MemDumper-master",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


MEMDUMPER_ROOT = choose_memdumper_root()


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


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([ADB, *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", "su", "-c", command, **kwargs)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def shell_join(argv: list[str]) -> str:
    return " ".join(shell_quote(str(item)) for item in argv)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--package", help="Target Android package/process name.")
    target.add_argument("--pid", help="Target pid.")
    parser.add_argument("--name", required=True, help="Library name or maps segment name.")
    parser.add_argument("--out-dir", type=pathlib.Path, required=True, help="Local output directory.")
    parser.add_argument("--device-dir", default="/data/local/tmp/xjb_memdump", help="Device work/output directory.")
    parser.add_argument("--timestamp-device-dir", action="store_true", help="Append a timestamp to --device-dir to avoid reusing old device files.")
    parser.add_argument("--abi", choices=["arm64-v8a", "armeabi-v7a"], default="arm64-v8a")
    parser.add_argument("--raw", action="store_true", help="Dump raw library without MemDumper ELF rebuild.")
    parser.add_argument("--fast", action="store_true", help="Enable MemDumper fast mode.")
    parser.add_argument("--manual", action="store_true", help="Manual address dump mode.")
    parser.add_argument("--start", help="Manual dump start address, hex.")
    parser.add_argument("--end", help="Manual dump end address, hex.")
    parser.add_argument("--remote-name", default=None, help="Remote output filename. Defaults to --name.")
    parser.add_argument("--keep-device-files", action="store_true", help="Do not remove device work directory after pull.")
    parser.add_argument("--no-clean-device-dir", action="store_true", help="Do not remove --device-dir before pushing memdumper.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    dumper = MEMDUMPER_ROOT / "libs" / args.abi / "memdumper"
    if not dumper.exists():
        print(f"[-] memdumper not found: {dumper}", file=sys.stderr)
        print("    Set MEMDUMPER_ROOT=/path/to/MemDumper-master if needed.", file=sys.stderr)
        return 2
    if args.manual and (not args.start or not args.end):
        print("[-] --manual requires --start and --end", file=sys.stderr)
        return 2

    remote_bin = f"{args.device_dir}/memdumper"
    if args.timestamp_device_dir:
        args.device_dir = f"{args.device_dir}_{time.strftime('%Y%m%d_%H%M%S')}"
        remote_bin = f"{args.device_dir}/memdumper"
    remote_name = args.remote_name or args.name
    local_out = args.out_dir.expanduser().resolve()
    local_out.mkdir(parents=True, exist_ok=True)
    print(f"MEMDUMPER_ROOT={MEMDUMPER_ROOT}", flush=True)
    print(f"ADB={ADB}", flush=True)

    if args.no_clean_device_dir:
        adb_su(shell_join(["mkdir", "-p", args.device_dir]))
    else:
        adb_su("; ".join([
            shell_join(["rm", "-rf", args.device_dir]),
            shell_join(["mkdir", "-p", args.device_dir]),
        ]))
    push = adb("push", str(dumper), remote_bin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if push.returncode != 0:
        print(push.stdout, end="")
        print(push.stderr, end="", file=sys.stderr)
        return push.returncode
    adb_su(shell_join(["chmod", "755", remote_bin]))

    cmd = [remote_bin]
    if args.pid:
        cmd += ["-i", str(args.pid)]
    else:
        cmd += ["-p", str(args.package)]
    if args.manual:
        cmd += ["-m", "-n", remote_name, "-s", str(args.start), "-e", str(args.end)]
    else:
        cmd += ["-l", "-n", args.name]
    if args.raw:
        cmd.append("-r")
    if args.fast:
        cmd.append("-f")
    cmd += ["-o", args.device_dir]

    shell_cmd = shell_join(cmd)
    dump = adb_su(shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(dump.stdout, end="")
    print(dump.stderr, end="", file=sys.stderr)
    if dump.returncode != 0:
        return dump.returncode

    remote_out = f"{args.device_dir}/{remote_name}"
    pull = adb("pull", remote_out, str(local_out / remote_name), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pull.stdout, end="")
    print(pull.stderr, end="", file=sys.stderr)

    if not args.keep_device_files:
        adb_su(shell_join(["rm", "-rf", args.device_dir]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out_file = local_out / remote_name
    if out_file.exists():
        print(f"[dumped] {out_file} size={out_file.stat().st_size}", flush=True)
        return 0
    print(f"[-] output file not found after pull: {out_file}", file=sys.stderr)
    return pull.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
