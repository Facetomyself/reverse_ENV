#!/usr/bin/env python3
"""Collect decisive native-analysis evidence lines from log files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable


PATTERNS = {
    "termination": re.compile(r"\b(SIGKILL|SIGSEGV|SIGTRAP|SIGABRT|BRK|tgkill|tkill|kill\(|exit_group|abort)\b", re.I),
    "loading": re.compile(r"\b(dlopen|android_dlopen_ext|call_constructors|JNI_OnLoad|RegisterNatives|mprotect|mmap)\b", re.I),
    "root_path": re.compile(r"\b(faccessat|openat|readlinkat|/data/adb|/system/.*/su|/sbin/su|magisk|busybox)\b", re.I),
    "frida_hook": re.compile(r"\b(frida|gum-js-loop|gadget|memfd|xposed|substrate|inline hook|hook)\b", re.I),
    "patch": re.compile(r"\b(patch|patched|force|bypass|status0|nop|replace|writeByteArray)\b", re.I),
    "anr": re.compile(r"\b(ANR|Application Not Responding|FATAL EXCEPTION|卡顿)\b", re.I),
}


def iter_files(paths: list[str]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in {".log", ".txt", ".md"}:
                    yield child


def compile_patterns(extra_so: list[str], extra_pattern: list[str]) -> dict[str, re.Pattern[str]]:
    patterns = dict(PATTERNS)
    if extra_so:
        escaped = [re.escape(item) for item in extra_so]
        patterns["target_so_custom"] = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.I)
    for idx, pattern in enumerate(extra_pattern, start=1):
        patterns[f"custom_{idx}"] = re.compile(pattern, re.I)
    return patterns


def scan_file(path: Path, context: int, patterns: dict[str, re.Pattern[str]]) -> list[tuple[int, str, str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [(0, "error", f"cannot read: {exc}")]

    hits: list[tuple[int, str, str]] = []
    used_context: set[int] = set()
    for idx, line in enumerate(lines, start=1):
        labels = [name for name, pat in patterns.items() if pat.search(line)]
        if not labels:
            continue
        hits.append((idx, ",".join(labels), line))
        if context:
            start = max(1, idx - context)
            end = min(len(lines), idx + context)
            for cidx in range(start, end + 1):
                if cidx == idx or cidx in used_context:
                    continue
                used_context.add(cidx)
                hits.append((cidx, "context", lines[cidx - 1]))
    return sorted(hits, key=lambda item: item[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract key evidence lines from reverse-analysis logs.")
    parser.add_argument("paths", nargs="+", help="Log files or directories.")
    parser.add_argument("--context", type=int, default=0, help="Context lines around hits.")
    parser.add_argument("--so", action="append", default=[], help="Additional target so name to highlight; may be repeated.")
    parser.add_argument("--pattern", action="append", default=[], help="Additional regex to highlight; may be repeated.")
    parser.add_argument("--out", default="", help="Write output to this file.")
    args = parser.parse_args()

    patterns = compile_patterns(args.so, args.pattern)
    output: list[str] = []
    for path in iter_files(args.paths):
        hits = scan_file(path, args.context, patterns)
        if not hits:
            continue
        output.append(f"## {path}")
        for lineno, label, line in hits:
            output.append(f"{path}:{lineno}: [{label}] {line}")
        output.append("")

    text = "\n".join(output)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"[written] {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
