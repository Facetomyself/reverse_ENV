#!/usr/bin/env python3
"""Append a timestamped detailed experiment note."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def block(args: argparse.Namespace) -> str:
    now = args.time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    did = args.did or args.commands or args.tools or "待补充"
    why = args.why or args.purpose or "待补充"
    analysis = args.analysis or args.reasoning or "待补充"
    tools_used = args.tools or "无"
    commands_used = args.commands or "无"
    code_changes = args.code_changes or "无"
    detection_code = args.detection_code or args.pseudocode or "待静态分析"
    result = args.result or args.conclusion or args.evidence or "待补充"
    next_step = args.next_step or "待补充"
    lines = [
        f"\n## {now} {args.title}",
        "",
        f"- 记录时间：{now}",
        f"- 分析思路：{analysis}",
        f"- 本轮操作：{did}",
        f"- 操作目的：{why}",
        f"- 所用工具：{tools_used}",
        f"- 运行命令：{commands_used}",
        f"- 代码变更：{code_changes}",
        f"- 检测代码明细：{detection_code}",
        f"- 实验结果：{result}",
        f"- 下一步计划：{next_step}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or append an experiment note.")
    parser.add_argument("--title", required=True, help="Section title.")
    parser.add_argument("--analysis", default="", help="Analysis reasoning, assumptions, and evidence basis.")
    parser.add_argument("--reasoning", default="", help="Alias for --analysis.")
    parser.add_argument("--did", default="", help="What was done.")
    parser.add_argument("--why", default="", help="Why it was done.")
    parser.add_argument("--code-changes", default="", help="Changed files, offsets, scripts, or patch semantics.")
    parser.add_argument("--detection-code", default="", help="Detailed detection code, offsets, branches, constants, and call chain.")
    parser.add_argument("--pseudocode", default="", help="Backward-compatible alias for --detection-code.")
    parser.add_argument("--result", default="", help="Experiment result.")
    parser.add_argument("--process", default="", help="Target process.")
    parser.add_argument("--target", default="", help="Target so/function/offset.")
    parser.add_argument("--purpose", default="", help="Analysis purpose.")
    parser.add_argument("--authorization", default="", help="Authorization boundary for this target.")
    parser.add_argument("--tool-route", default="", help="Task type and selected tool route.")
    parser.add_argument("--jadx-path", default="", help="jadx path used for Java/Kotlin analysis.")
    parser.add_argument("--ida-path", default="", help="IDA path used for so analysis.")
    parser.add_argument("--inp-status", default="", help="INP.py copy/install/export status.")
    parser.add_argument("--fallback", default="", help="Fallback tool and reason, only after user says jadx/IDA is unavailable.")
    parser.add_argument("--tools", default="", help="Tools used.")
    parser.add_argument("--commands", default="", help="Commands used.")
    parser.add_argument("--so-encryption", default="", help="Disk so encryption/packing/self-decrypting judgment.")
    parser.add_argument("--dump-timing", default="", help="Dump timing, preferably call_constructors.")
    parser.add_argument("--dump-artifact", default="", help="Dump/fixed ELF artifact path.")
    parser.add_argument("--ida-export", default="", help="IDA export path.")
    parser.add_argument("--anon-rx", default="", help="Anonymous RX maps/syscall/pc-lr check result.")
    parser.add_argument("--function-range", default="", help="IDA function range confirmation result.")
    parser.add_argument("--ollvm", default="", help="OLLVM/non-standard control-flow status.")
    parser.add_argument("--crc", default="", help="CRC/integrity check result.")
    parser.add_argument("--patch-script", default="", help="Patch script path.")
    parser.add_argument("--artifacts", default="", help="Generated artifacts.")
    parser.add_argument("--evidence", default="", help="Key log/code evidence.")
    parser.add_argument("--confirmed", default="", help="Confirmed conclusions.")
    parser.add_argument("--inferred", default="", help="Inferences.")
    parser.add_argument("--unconfirmed", default="", help="Unconfirmed items.")
    parser.add_argument("--patch-candidate", default="", help="Patch candidate location.")
    parser.add_argument("--original-semantics", default="", help="Original behavior at patch location.")
    parser.add_argument("--modified-semantics", default="", help="Modified behavior at patch location.")
    parser.add_argument("--risk", default="", help="Patch risk boundary.")
    parser.add_argument("--rollback", default="", help="Rollback method.")
    parser.add_argument("--duration", default="", help="Verification duration.")
    parser.add_argument("--so-chain", default="", help="Observed so loading chain.")
    parser.add_argument("--crash", default="", help="Crash/termination result.")
    parser.add_argument("--anr", default="", help="ANR/stutter result.")
    parser.add_argument("--conclusion", default="", help="Current conclusion.")
    parser.add_argument("--next", dest="next_step", default="", help="Next step.")
    parser.add_argument("--time", default="", help="Timestamp override.")
    parser.add_argument("--out", default="", help="Markdown file to append. Omit for stdout.")
    args = parser.parse_args()

    text = block(args)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fp:
            fp.write(text)
        print(f"[appended] {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
