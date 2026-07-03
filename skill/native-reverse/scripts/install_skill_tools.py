#!/usr/bin/env python3
"""Copy bundled reverse-engineering tools from this skill into a project workspace."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = SCRIPT_DIR / "tools"
RUNNER_NAMES = [
    "frida_scfilter_runner.py",
    "frida_memdump_so.py",
    "memdump_so.py",
    "ecapture_android.py",
    "stealth_hook_android.py",
    "ida_fix_function_range.py",
]


IDA_ROOT_NAMES = [
    "ida-pro-9.3",
    "ida-pro-9.2",
    "ida-pro-9.1",
    "ida-pro-9.0",
    "ida-pro",
    "IDA Pro 9.3",
    "IDA Pro 9.2",
    "IDA Pro 9.1",
    "IDA Pro 9.0",
    "IDA Professional 9.3",
    "IDA Professional 9.2",
    "IDA Professional 9.1",
    "IDA Professional 9.0",
]


def add_candidate(candidates: list[Path], value: str | Path | None, *, plugin_child: bool = False) -> None:
    if not value:
        return
    path = Path(value).expanduser()
    candidates.append(path / "plugins" if plugin_child else path)


def add_root_candidates(candidates: list[Path], root: Path | None) -> None:
    if root is None:
        return
    for name in IDA_ROOT_NAMES:
        candidates.append(root / name / "plugins")


def candidate_ida_plugin_dirs() -> list[Path]:
    candidates: list[Path] = []
    # project-known paths first
    add_candidate(candidates, "D:/reverse_ENV/resource/portable_win", plugin_child=True)
    for env_name in ("IDA_PLUGIN_DIR", "IDA_PLUGINS_DIR"):
        add_candidate(candidates, os.environ.get(env_name))
    for env_name in ("IDA_ROOT", "IDAPRO_ROOT"):
        add_candidate(candidates, os.environ.get(env_name), plugin_child=True)
    for exe_name in ("ida", "ida64", "idat", "idat64"):
        exe = shutil.which(exe_name)
        if exe:
            candidates.append(Path(exe).resolve().parent / "plugins")
    home = Path.home()
    add_root_candidates(candidates, home / "bin")
    add_root_candidates(candidates, home / "tools")
    add_root_candidates(candidates, home / "Applications")
    add_root_candidates(candidates, Path("/opt"))
    add_root_candidates(candidates, Path("/Applications"))
    add_root_candidates(candidates, Path("/usr/local"))
    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            value = os.environ.get(env_name)
            if value:
                add_root_candidates(candidates, Path(value))
        for drive in ("C:", "D:"):
            add_root_candidates(candidates, Path(drive) / "Program Files")
            add_root_candidates(candidates, Path(drive) / "Program Files (x86)")
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_dir():
            result.append(resolved)
    return result


def copy_file_clean(src: Path, dst: Path, *, force: bool = False, backup: bool = False, dry_run: bool = False) -> str:
    if dry_run:
        if dst.exists():
            if backup:
                return "would back up existing and copy"
            if force:
                return "would replace existing"
            return "would keep existing; use --force or --backup-existing to replace"
        return "would copy"
    if dst.exists():
        if backup:
            backup_path = dst.with_name(f"{dst.name}.bak")
            idx = 1
            while backup_path.exists():
                backup_path = dst.with_name(f"{dst.name}.bak{idx}")
                idx += 1
            shutil.move(str(dst), str(backup_path))
            shutil.copy2(src, dst)
            return f"backed up existing to {backup_path}"
        if not force:
            return "kept existing; use --force or --backup-existing to replace"
    shutil.copy2(src, dst)
    return "copied"


def copytree_clean(src: Path, dst: Path, *, force: bool = False, backup: bool = False, dry_run: bool = False) -> str:
    ignore = shutil.ignore_patterns(".git", "__pycache__", "logs", "*.pyc", "*.o")
    if dry_run:
        if dst.exists():
            if backup:
                return "would back up existing and copy"
            if force:
                return "would replace existing"
            return "would keep existing; use --force or --backup-existing to replace"
        return "would copy"
    if dst.exists():
        if backup:
            backup_path = dst.with_name(f"{dst.name}.bak")
            idx = 1
            while backup_path.exists():
                backup_path = dst.with_name(f"{dst.name}.bak{idx}")
                idx += 1
            shutil.move(str(dst), str(backup_path))
            shutil.copytree(src, dst, ignore=ignore)
            return f"backed up existing to {backup_path}"
        if not force:
            return "kept existing; use --force or --backup-existing to replace"
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)
    return "copied"


def safe_chmod_executable(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.chmod(0o755)
    except OSError:
        pass


def describe_platform() -> str:
    return f"{platform.system() or os.name} {platform.machine() or ''}".strip()


def find_cache_artifacts() -> list[Path]:
    return sorted(
        path
        for path in SKILL_ROOT.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    )


def validate_skill_frontmatter() -> list[str]:
    failures: list[str] = []
    skill_md = SKILL_ROOT / "SKILL.md"
    if not skill_md.is_file():
        return [f"missing file: {skill_md}"]
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [f"frontmatter missing opening delimiter: {skill_md}"]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [f"frontmatter missing closing delimiter: {skill_md}"]
    frontmatter = text[4:end].splitlines()
    fields: dict[str, str] = {}
    extra_fields: list[str] = []
    for line in frontmatter:
        if not line.strip():
            continue
        if ":" not in line:
            failures.append(f"frontmatter invalid line: {line}")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        fields[key] = value
        if key not in {"name", "description"}:
            extra_fields.append(key)
    if fields.get("name") != "native-reverse":
        failures.append(f"frontmatter name invalid: {fields.get('name')!r}")
    if not fields.get("description"):
        failures.append("frontmatter description missing")
    if extra_fields:
        failures.append(f"frontmatter has unsupported fields: {', '.join(extra_fields)}")
    return failures


def find_unneeded_sample_artifacts() -> list[Path]:
    sample_roots = [TOOLS_DIR / "ollvm_deobfuscator"]
    return sorted(
        path
        for root in sample_roots
        if root.exists()
        for path in root.glob("sample*.so")
    )


def run_self_check() -> int:
    failures: list[str] = []
    required_dirs = [
        TOOLS_DIR / "xiaojianbang-syscall-filter",
        TOOLS_DIR / "ollvm_deobfuscator",
        TOOLS_DIR / "MemDumper-master",
        TOOLS_DIR / "ecapture-v2.3.0-android-arm64",
        TOOLS_DIR / "xiaojianbang-stealth-hook-main",
    ]
    required_files = [
        SCRIPT_DIR / "make_experiment_note.py",
        SCRIPT_DIR / "collect_key_evidence.py",
        SCRIPT_DIR / "init_reverse_workspace.py",
        TOOLS_DIR / "frida_scfilter_runner.py",
        TOOLS_DIR / "frida_memdump_so.py",
        TOOLS_DIR / "memdump_so.py",
        TOOLS_DIR / "ecapture_android.py",
        TOOLS_DIR / "stealth_hook_android.py",
        TOOLS_DIR / "ida_fix_function_range.py",
        TOOLS_DIR / "INP.py",
    ]
    for path in required_dirs:
        if not path.is_dir():
            failures.append(f"missing dir: {path}")
    for path in required_files:
        if not path.is_file():
            failures.append(f"missing file: {path}")
    for path in find_cache_artifacts():
        failures.append(f"cache artifact present: {path}")
    for item in validate_skill_frontmatter():
        failures.append(item)
    for path in find_unneeded_sample_artifacts():
        failures.append(f"unneeded sample artifact present: {path}")
    py_files = [p for p in SCRIPT_DIR.rglob("*.py")]
    for path in py_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:  # pragma: no cover - diagnostic path
            failures.append(f"syntax failed: {path}: {type(exc).__name__}: {exc}")
    help_targets = [
        SCRIPT_DIR / "make_experiment_note.py",
        SCRIPT_DIR / "collect_key_evidence.py",
        TOOLS_DIR / "memdump_so.py",
        TOOLS_DIR / "stealth_hook_android.py",
    ]
    help_env = os.environ.copy()
    help_env["PYTHONDONTWRITEBYTECODE"] = "1"
    for path in help_targets:
        if not path.is_file():
            continue
        proc = subprocess.run([sys.executable, str(path), "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=help_env)
        if proc.returncode != 0:
            failures.append(f"help failed: {path}: {proc.stderr.strip()}")
    for path in find_cache_artifacts():
        failures.append(f"cache artifact present after help check: {path}")
    if failures:
        print(f"[self-check] failed={len(failures)}")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"[self-check] ok python_files={len(py_files)} required_dirs={len(required_dirs)} required_files={len(required_files)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", nargs="?", default=".", help="Target project root.")
    parser.add_argument("--with-runner", action="store_true", help="Also copy Python wrapper scripts to scripts/. Does not copy INP.py.")
    parser.add_argument("--with-inp", "--install-project-inp", dest="install_project_inp", action="store_true", help="Copy INP.py to project scripts/ for IDA batch export. Use only when IDA export data is needed.")
    parser.add_argument("--install-ida-plugin", dest="install_ida_plugin", action="store_true", help="Auto-detect an IDA plugins directory and install INP.py there.")
    parser.add_argument("--ida-root", help="IDA installation root. INP.py will be copied to <ida-root>/plugins/.")
    parser.add_argument("--ida-plugin-dir", help="IDA plugins directory. Overrides --ida-root and auto detection.")
    parser.add_argument("--force", action="store_true", help="Replace existing tool directories and runner scripts.")
    parser.add_argument("--backup-existing", action="store_true", help="Move existing tool directories/scripts aside before copying.")
    parser.add_argument("--dry-run", "--audit", dest="dry_run", action="store_true", help="Print planned copy/install actions without writing files.")
    parser.add_argument("--self-check", action="store_true", help="Validate bundled resources, cache cleanliness, and script entrypoints without copying files.")
    parser.set_defaults(install_ida_plugin=False)
    args = parser.parse_args()
    if args.self_check:
        return run_self_check()
    if args.force and args.backup_existing:
        parser.error("--force and --backup-existing are mutually exclusive")

    root = Path(args.project_root).expanduser().resolve()
    third_party = root / "third_party"
    scripts = root / "scripts"
    if not args.dry_run:
        third_party.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)
    else:
        print(f"[audit] project root: {root}")
        print(f"[audit] no files will be written")

    tool_dirs = [
        (TOOLS_DIR / "xiaojianbang-syscall-filter", third_party / "xiaojianbang-syscall-filter"),
        (TOOLS_DIR / "ollvm_deobfuscator", third_party / "OLLVM_Deobfuscator"),
        (TOOLS_DIR / "MemDumper-master", third_party / "MemDumper-master"),
        (TOOLS_DIR / "ecapture-v2.3.0-android-arm64", third_party / "ecapture-v2.3.0-android-arm64"),
        (TOOLS_DIR / "xiaojianbang-stealth-hook-main", third_party / "xiaojianbang-stealth-hook-main"),
    ]
    for src, dst in tool_dirs:
        status = copytree_clean(src, dst, force=args.force, backup=args.backup_existing, dry_run=args.dry_run)
        print(f"[{status}] {dst}")

    if args.with_runner:
        for name in RUNNER_NAMES:
            src = TOOLS_DIR / name
            dst = scripts / name
            status = copy_file_clean(src, dst, force=args.force, backup=args.backup_existing, dry_run=args.dry_run)
            if not args.dry_run:
                safe_chmod_executable(dst)
            print(f"[{status}] {dst}")

    if args.install_project_inp:
        src = TOOLS_DIR / "INP.py"
        dst = scripts / "INP.py"
        status = copy_file_clean(src, dst, force=args.force, backup=args.backup_existing, dry_run=args.dry_run)
        if not args.dry_run:
            safe_chmod_executable(dst)
        print(f"[{status}] {dst}")

    if args.install_ida_plugin or args.ida_root or args.ida_plugin_dir:
        if args.ida_plugin_dir:
            plugin_dir = Path(args.ida_plugin_dir).expanduser().resolve()
        elif args.ida_root:
            plugin_dir = (Path(args.ida_root).expanduser().resolve() / "plugins")
        else:
            plugin_dirs = candidate_ida_plugin_dirs()
            if not plugin_dirs:
                print(f"[not found] IDA plugins directory on {describe_platform()}; pass --ida-plugin-dir or --ida-root")
                plugin_dir = None
            else:
                if len(plugin_dirs) > 1:
                    print("[detected] IDA plugins candidates:")
                    for candidate in plugin_dirs:
                        print(f"  - {candidate}")
                plugin_dir = plugin_dirs[0]
                print(f"[selected] IDA plugins directory: {plugin_dir}")
        if plugin_dir is None:
            pass
        else:
            if (args.ida_plugin_dir or args.ida_root) and not args.dry_run:
                plugin_dir.mkdir(parents=True, exist_ok=True)
            elif not args.dry_run and not plugin_dir.is_dir():
                print(f"[not found] IDA plugins directory: {plugin_dir}")
                return 2
            dst = plugin_dir / "INP.py"
            status = copy_file_clean(TOOLS_DIR / "INP.py", dst, force=args.force, backup=args.backup_existing, dry_run=args.dry_run)
            print(f"[{status}] {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
