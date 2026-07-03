#!/usr/bin/env python3
"""Apply reviewed function ranges inside IDA and emit a validation report.

Run inside IDA/IDAT, for example:

  idat64 -A -S"/path/ida_fix_function_range.py --spec ranges.json --out reports/ranges.md" target.i64

The script does not guess function ranges. It only applies reviewed ranges from
JSON, then verifies boundaries and evidence offsets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_name
    import ida_nalt
    import ida_ua
    import idaapi
    import idc
except ImportError as exc:  # pragma: no cover - IDA-only script
    print(f"[ida_fix_function_range] must run inside IDA Python: {exc}")
    raise SystemExit(2)


TERMINAL_MNEMS = {
    "ret",
    "retn",
    "br",
    "blr",
    "b",
    "bx",
    "jmp",
}


def ida_script_argv() -> list[str]:
    try:
        argv = list(getattr(idc, "ARGV", []) or [])
        if len(argv) > 1:
            return argv[1:]
    except Exception:
        pass
    return sys.argv[1:]


def parse_int(value: Any, *, field: str) -> int:
    if isinstance(value, int):
        return value
    if value is None:
        raise ValueError(f"missing {field}")
    text = str(value).strip()
    if text.startswith("+"):
        text = text[1:]
    try:
        return int(text, 0)
    except ValueError as exc:
        raise ValueError(f"invalid integer for {field}: {value!r}") from exc


def fmt_ea(ea: int) -> str:
    return f"0x{ea:x}"


def input_file_path() -> str:
    try:
        return ida_nalt.get_input_file_path()
    except Exception:
        try:
            return idaapi.get_input_file_path()
        except Exception:
            return ""


def load_spec(path: Path) -> tuple[list[dict[str, Any]], int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, 0
    if not isinstance(data, dict):
        raise ValueError("spec must be a list or object")
    base = parse_int(data.get("base", 0), field="base")
    funcs = data.get("functions") or data.get("ranges")
    if funcs is None and "start" in data and "end" in data:
        funcs = [data]
    if not isinstance(funcs, list):
        raise ValueError("spec object must contain functions/ranges list")
    return funcs, base


def with_base(value: Any, base: int, *, field: str) -> int:
    return base + parse_int(value, field=field)


def iter_overlapping_funcs(start: int, end: int) -> list[ida_funcs.func_t]:
    seen: set[int] = set()
    funcs: list[ida_funcs.func_t] = []

    for candidate in (ida_funcs.get_prev_func(start), ida_funcs.get_func(start)):
        if candidate and candidate.start_ea not in seen and candidate.end_ea > start:
            funcs.append(candidate)
            seen.add(candidate.start_ea)

    func = ida_funcs.get_next_func(start)
    while func and func.start_ea < end:
        if func.start_ea not in seen:
            funcs.append(func)
            seen.add(func.start_ea)
        func = ida_funcs.get_next_func(func.start_ea)

    return sorted(funcs, key=lambda f: f.start_ea)


def make_code_range(start: int, end: int, *, undefine_items: bool) -> list[str]:
    actions: list[str] = []
    if undefine_items:
        ida_bytes.del_items(start, ida_bytes.DELIT_SIMPLE, end - start)
        actions.append(f"undefined items in {fmt_ea(start)}..{fmt_ea(end)}")

    ea = start
    while ea < end:
        size = ida_ua.create_insn(ea)
        if not size:
            size = ida_bytes.get_item_size(ea)
        if not size or size <= 0:
            ea += 1
        else:
            ea += size
    actions.append(f"created instructions in {fmt_ea(start)}..{fmt_ea(end)}")
    return actions


def delete_overlaps(start: int, end: int) -> list[str]:
    actions: list[str] = []
    for func in iter_overlapping_funcs(start, end):
        ok = ida_funcs.del_func(func.start_ea)
        actions.append(
            f"{'deleted' if ok else 'failed to delete'} existing function "
            f"{fmt_ea(func.start_ea)}..{fmt_ea(func.end_ea)}"
        )
    return actions


def apply_range(item: dict[str, Any], global_base: int, *, dry_run: bool, undefine_items: bool) -> dict[str, Any]:
    local_base = parse_int(item.get("base", global_base), field="base")
    start = with_base(item.get("start"), local_base, field="start")
    end = with_base(item.get("end"), local_base, field="end")
    if end <= start:
        raise ValueError(f"end must be greater than start for {item!r}")

    name = str(item.get("name", "") or "")
    reason = str(item.get("reason", "") or "")
    must_contain = [with_base(v, local_base, field="must_contain") for v in item.get("must_contain", [])]
    must_not_contain = [with_base(v, local_base, field="must_not_contain") for v in item.get("must_not_contain", [])]
    item_undefine = bool(item.get("undefine_items", undefine_items))

    result: dict[str, Any] = {
        "name": name or fmt_ea(start),
        "reason": reason,
        "start": start,
        "end": end,
        "actions": [],
        "errors": [],
        "warnings": [],
        "checks": [],
    }

    if dry_run:
        result["actions"].append("dry-run: no database changes")
    else:
        result["actions"].extend(delete_overlaps(start, end))
        result["actions"].extend(make_code_range(start, end, undefine_items=item_undefine))
        ok = ida_funcs.add_func(start, end)
        result["actions"].append(f"{'added' if ok else 'failed to add'} function {fmt_ea(start)}..{fmt_ea(end)}")
        if not ok:
            func = ida_funcs.get_func(start)
            if func and func.start_ea == start:
                set_ok = ida_funcs.set_func_end(start, end)
                result["actions"].append(f"{'set' if set_ok else 'failed to set'} function end {fmt_ea(end)}")
        if name:
            ida_name.set_name(start, name, ida_name.SN_CHECK | ida_name.SN_FORCE)
            result["actions"].append(f"set name {name}")
        ida_auto.plan_range(start, end)
        ida_auto.auto_wait()

    func = ida_funcs.get_func(start)
    if not func:
        result["errors"].append(f"no function contains start {fmt_ea(start)}")
    else:
        result["checks"].append(f"IDA function range: {fmt_ea(func.start_ea)}..{fmt_ea(func.end_ea)}")
        if func.start_ea != start:
            result["errors"].append(f"function start mismatch: expected {fmt_ea(start)}, got {fmt_ea(func.start_ea)}")
        if func.end_ea != end:
            result["errors"].append(f"function end mismatch: expected {fmt_ea(end)}, got {fmt_ea(func.end_ea)}")

    for ea in must_contain:
        func_at = ida_funcs.get_func(ea)
        if not (start <= ea < end):
            result["errors"].append(f"must_contain {fmt_ea(ea)} is outside requested range")
        elif not func_at or func_at.start_ea != start:
            result["errors"].append(f"must_contain {fmt_ea(ea)} is not owned by target function")
        else:
            result["checks"].append(f"must_contain {fmt_ea(ea)} covered")

    for ea in must_not_contain:
        if start <= ea < end:
            result["errors"].append(f"must_not_contain {fmt_ea(ea)} is inside requested range")
        else:
            result["checks"].append(f"must_not_contain {fmt_ea(ea)} excluded")

    overlaps = [
        f for f in iter_overlapping_funcs(start, end)
        if not (func and f.start_ea == func.start_ea)
    ]
    for other in overlaps:
        result["errors"].append(f"overlaps other function {fmt_ea(other.start_ea)}..{fmt_ea(other.end_ea)}")

    last = idc.prev_head(end, start)
    if last == idaapi.BADADDR:
        result["warnings"].append("cannot find last instruction before end")
    else:
        mnem = idc.print_insn_mnem(last).lower()
        result["checks"].append(f"last instruction before end: {fmt_ea(last)} {mnem}")
        if mnem not in TERMINAL_MNEMS:
            result["warnings"].append(f"last instruction is not a common terminal branch: {fmt_ea(last)} {mnem}")

    return result


def render_report(results: list[dict[str, Any]], spec_path: Path) -> str:
    lines = [
        "# IDA Function Range Fix Report",
        "",
        f"- spec: `{spec_path}`",
        f"- ida_input: `{input_file_path()}`",
        f"- imagebase: `{fmt_ea(idaapi.get_imagebase())}`",
        "",
    ]
    for res in results:
        status = "FAIL" if res["errors"] else ("WARN" if res["warnings"] else "PASS")
        lines.extend([
            f"## {res['name']}",
            "",
            f"- status: {status}",
            f"- range: `{fmt_ea(res['start'])}..{fmt_ea(res['end'])}`",
        ])
        if res["reason"]:
            lines.append(f"- reason: {res['reason']}")
        for label in ("actions", "checks", "warnings", "errors"):
            if not res[label]:
                continue
            lines.append(f"- {label}:")
            for item in res[label]:
                lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="JSON file with reviewed function ranges.")
    parser.add_argument("--out", default="", help="Write markdown report to this path.")
    parser.add_argument("--base", default=None, help="Optional base added to every JSON address.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without changing IDA database.")
    parser.add_argument("--undefine-items", action="store_true", help="Undefine items in the requested range before creating code.")
    args = parser.parse_args(ida_script_argv())

    spec_path = Path(args.spec).expanduser().resolve()
    funcs, spec_base = load_spec(spec_path)
    if args.base is not None:
        spec_base = parse_int(args.base, field="--base")

    ida_auto.auto_wait()
    results = [
        apply_range(item, spec_base, dry_run=args.dry_run, undefine_items=args.undefine_items)
        for item in funcs
    ]
    report = render_report(results, spec_path)

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"[ida_fix_function_range] wrote {out_path}")
    else:
        print(report)

    failures = sum(1 for res in results if res["errors"])
    warnings = sum(1 for res in results if res["warnings"])
    print(f"[ida_fix_function_range] ranges={len(results)} failures={failures} warnings={warnings}")
    return 1 if failures else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
