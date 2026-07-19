#!/usr/bin/env python3
"""Classify Web JavaScript deobfuscation depth without executing target code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = 1
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Marker:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class InputDocument:
    role: str
    path: Path
    text: str
    size: int
    sha256: str


def marker(name: str, pattern: str, flags: int = re.IGNORECASE) -> Marker:
    return Marker(name=name, pattern=re.compile(pattern, flags))


MARKER_GROUPS: dict[str, tuple[Marker, ...]] = {
    "wasm_core": (
        marker("wasm_api", r"\bWebAssembly\.(?:instantiate|instantiateStreaming|compile|Module)\b"),
        marker("wasm_asset", r"\.wasm\b"),
    ),
    "wasm_boundary": (
        marker("module_imports", r"\bWebAssembly\.Module\.imports\b"),
        marker("module_exports", r"\bWebAssembly\.Module\.exports\b"),
        marker("text_codec", r"\bText(?:Decoder|Encoder)\b"),
        marker("linear_memory", r"\b(?:WebAssembly\.)?Memory\b|\bmemory\.buffer\b"),
        marker("crypto_random", r"\b(?:crypto|Crypto)\.?getRandomValues\b|\bgetRandomValues\b"),
        marker("typed_memory_view", r"\bnew\s+Uint(?:8|16|32)Array\s*\([^)]*buffer"),
    ),
    "vm_core": (
        marker("bytecode_container", r"\bnew\s+Uint(?:8|16|32)Array\s*\("),
        marker("bytecode_word", r"\bbytecode\b"),
        marker("opcode_word", r"\bopcode\b"),
        marker("dispatch_switch", r"\bswitch\s*\([^)]{1,96}\)"),
        marker("interpreter_loop", r"\bwhile\s*\(\s*(?:true|1)\s*\)"),
        marker("instruction_pointer", r"\b(?:instructionPointer|programCounter|opcodeIndex)\b"),
    ),
    "vm_trace": (
        marker("opcode_event", r"(?:[\"'](?:opcode|op)[\"']|\b(?:opcode|op)\b)\s*[:=]"),
        marker(
            "instruction_event",
            r"(?:[\"'](?:ip|pc|instructionPointer|programCounter)[\"']|\b(?:ip|pc|instructionPointer|programCounter)\b)\s*[:=]",
        ),
        marker("function_entry", r"\b(?:function[_ -]?entry|enter[_ -]?function|call[_ -]?frame)\b"),
    ),
    "ast_obfuscation": (
        marker("hex_identifier", r"\b_0x[0-9a-f]{3,}\b"),
        marker("string_array", r"\b(?:var|let|const)\s+_0x[0-9a-f]+\s*=\s*\["),
        marker("computed_string_property", r"\[[\"'][A-Za-z_$][\w$]*[\"']\]"),
        marker("control_flow_dispatch", r"\bwhile\s*\([^)]*\)\s*\{.{0,4096}?\bswitch\s*\(", re.IGNORECASE | re.DOTALL),
        marker("debugger_trap", r"\bdebugger\s*;"),
        marker("proxy_function", r"\breturn\s+[A-Za-z_$][\w$]*\s*\([^;]{0,160}\)\s*;"),
    ),
    "dynamic_execution": (
        marker("direct_eval", r"\beval\s*\("),
        marker("function_constructor", r"\b(?:new\s+)?Function\s*\("),
        marker("string_timer", r"\bset(?:Timeout|Interval)\s*\(\s*[\"']"),
    ),
}


PROFILE_GATES: dict[str, list[dict[str, str]]] = {
    "ast-safe": [
        {"id": "AST-01", "requirement": "input and output both pass an AST parse round-trip"},
        {"id": "AST-02", "requirement": "transform report lists every applied pass and no unsafe pass"},
        {"id": "AST-03", "requirement": "target-specific transforms have input/output fixtures"},
    ],
    "jsvm-verifiable": [
        {"id": "VM-01", "requirement": "opcode map and instruction widths are evidence-backed"},
        {"id": "VM-02", "requirement": "disassembly aligns with a runtime opcode trace"},
        {"id": "VM-03", "requirement": "forward request fixture or signer parity passes"},
    ],
    "wasm-boundary": [
        {"id": "WASM-01", "requirement": "imports and exports are inventoried"},
        {"id": "WASM-02", "requirement": "JS/WASM boundary events include memory and codec evidence"},
        {"id": "WASM-03", "requirement": "wrapper fixture reproduces observed boundary I/O"},
        {"id": "WASM-04", "requirement": "claim scope remains boundary-only or partial"},
    ],
    "triage-only": [
        {"id": "TRIAGE-01", "requirement": "record missing evidence and the next bounded experiment"},
        {"id": "TRIAGE-02", "requirement": "do not claim algorithm recovery"},
    ],
    "plain-js": [
        {"id": "PLAIN-01", "requirement": "return to the upstream runtime or protocol workflow"},
    ],
}


def load_document(path: Path, role: str, max_bytes: int) -> InputDocument:
    resolved = path.expanduser().resolve(strict=True)
    size = resolved.stat().st_size
    if size == 0:
        raise ValueError(f"input is empty: {resolved}")
    if size > max_bytes:
        raise ValueError(f"input exceeds --max-bytes ({size} > {max_bytes}): {resolved}")
    raw = resolved.read_bytes()
    if not raw:
        raise ValueError(f"input is empty: {resolved}")
    if len(raw) > max_bytes:
        raise ValueError(f"input exceeds --max-bytes ({len(raw)} > {max_bytes}): {resolved}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not UTF-8: {resolved}: {exc}") from exc
    return InputDocument(
        role=role,
        path=resolved,
        text=text,
        size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def scan_document(document: InputDocument) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for group, markers in MARKER_GROUPS.items():
        for item in markers:
            matches = list(item.pattern.finditer(document.text))
            if not matches:
                continue
            first = matches[0]
            line = document.text.count("\n", 0, first.start()) + 1
            evidence.append(
                {
                    "group": group,
                    "marker": item.name,
                    "role": document.role,
                    "path": str(document.path),
                    "line": line,
                    "count": len(matches),
                }
            )
    return evidence


def marker_names(
    evidence: Iterable[dict[str, object]],
    group: str,
    roles: set[str] | None = None,
) -> set[str]:
    return {
        str(item["marker"])
        for item in evidence
        if item["group"] == group and (roles is None or item["role"] in roles)
    }


def classify_documents(documents: Sequence[InputDocument]) -> dict[str, object]:
    evidence = [item for document in documents for item in scan_document(document)]
    evidence.sort(key=lambda item: (str(item["group"]), str(item["marker"]), str(item["path"]), int(item["line"])))

    source_roles = {"source"}
    trace_roles = {"trace"}
    wasm_core = marker_names(evidence, "wasm_core", source_roles)
    wasm_boundary = marker_names(evidence, "wasm_boundary")
    trace_wasm_boundary = marker_names(evidence, "wasm_boundary", trace_roles)
    vm_core = marker_names(evidence, "vm_core", source_roles)
    trace_vm = marker_names(evidence, "vm_trace", trace_roles)
    ast_markers = marker_names(evidence, "ast_obfuscation", source_roles)
    dynamic_markers = marker_names(evidence, "dynamic_execution", source_roles)

    roles = {document.role for document in documents}
    has_fixture = "fixture" in roles
    vm_shape = (
        "bytecode_container" in vm_core
        and "dispatch_switch" in vm_core
        and bool(vm_core & {"opcode_word", "bytecode_word", "interpreter_loop", "instruction_pointer"})
    )

    warnings: list[str] = []
    if dynamic_markers:
        warnings.append("dynamic execution markers found; keep unsafe passes disabled unless an isolated runtime is explicitly approved")
    if wasm_core and vm_shape:
        warnings.append("hybrid WASM and VM markers found; classify by the first evidence boundary and keep unresolved internals in triage")

    if wasm_core:
        if len(trace_wasm_boundary) >= 2:
            profile = "wasm-boundary"
            depth = "L3/partial"
            claim_scope = "boundary-only"
            route = "web-deobfuscation"
            next_steps = [
                "inventory WebAssembly imports and exports",
                "align TextEncoder/TextDecoder, memory views, randomness, DOM, and network boundary events",
                "reproduce the JS wrapper against a scrubbed fixture without claiming WASM internals",
            ]
            if not has_fixture:
                warnings.append("boundary classification passed, but acceptance still requires a scrubbed wrapper fixture")
        else:
            profile = "triage-only"
            depth = "L4"
            claim_scope = "triage-only"
            route = "ruyi-reverse -> web-deobfuscation"
            next_steps = [
                "capture a runtime trace containing at least two JS/WASM boundary marker classes",
                "record the module hash, imports, exports, memory object, and observed input/output",
            ]
    elif vm_shape:
        if "opcode_event" in trace_vm and has_fixture:
            profile = "jsvm-verifiable"
            depth = "L3"
            claim_scope = "partial"
            route = "web-deobfuscation"
            next_steps = [
                "recover bytecode header, function boundaries, opcode map, and instruction widths",
                "align disassembly with the runtime opcode trace",
                "close the loop with a forward request or signer fixture",
            ]
        else:
            profile = "triage-only"
            depth = "L4"
            claim_scope = "triage-only"
            route = "ruyi-reverse or mcp-js-reverse-playbook -> web-deobfuscation"
            next_steps = [
                "capture opcode execution trace and function-entry evidence",
                "add a scrubbed request or signer fixture before claiming devirtualization",
            ]
    elif ast_markers:
        profile = "ast-safe"
        depth = "L2"
        claim_scope = "transform-only"
        route = "web-deobfuscation"
        next_steps = [
            "run parser round-trip before any transform",
            "apply only named safe passes and emit a transform report",
            "validate target-specific transforms with input/output fixtures",
        ]
    else:
        profile = "plain-js"
        depth = "L1/L2"
        claim_scope = "not-applicable"
        route = "ruyi-reverse, web-env-patcher, or protocol-recovery"
        next_steps = ["continue the upstream runtime, environment, or protocol workflow; deobfuscation is not yet the blocker"]

    inputs = [
        {
            "role": document.role,
            "path": str(document.path),
            "bytes": document.size,
            "sha256": document.sha256,
        }
        for document in sorted(documents, key=lambda item: (item.role, str(item.path)))
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": profile,
        "depth": depth,
        "claim_scope": claim_scope,
        "route": route,
        "inputs": inputs,
        "marker_summary": {
            "wasm_core": sorted(wasm_core),
            "wasm_boundary": sorted(wasm_boundary),
            "trace_wasm_boundary": sorted(trace_wasm_boundary),
            "vm_core": sorted(vm_core),
            "trace_vm": sorted(trace_vm),
            "ast_obfuscation": sorted(ast_markers),
            "dynamic_execution": sorted(dynamic_markers),
        },
        "evidence": evidence,
        "gates": PROFILE_GATES[profile],
        "next_steps": next_steps,
        "warnings": warnings,
    }


def classify_paths(
    sources: Sequence[Path],
    traces: Sequence[Path] = (),
    fixtures: Sequence[Path] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, object]:
    if not sources:
        raise ValueError("at least one --source is required")
    if max_bytes <= 0:
        raise ValueError("--max-bytes must be greater than zero")
    documents = [load_document(path, "source", max_bytes) for path in sources]
    documents.extend(load_document(path, "trace", max_bytes) for path in traces)
    documents.extend(load_document(path, "fixture", max_bytes) for path in fixtures)
    return classify_documents(documents)


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Web Deobfuscation Gate",
        "",
        f"- Profile: `{report['profile']}`",
        f"- Depth: `{report['depth']}`",
        f"- Claim scope: `{report['claim_scope']}`",
        f"- Route: `{report['route']}`",
        "",
        "## Required gates",
        "",
    ]
    for gate in report["gates"]:
        lines.append(f"- `{gate['id']}`: {gate['requirement']}")
    lines.extend(["", "## Evidence markers", ""])
    for group, names in report["marker_summary"].items():
        lines.append(f"- `{group}`: {', '.join(names) if names else 'none'}")
    lines.extend(["", "## Next steps", ""])
    lines.extend(f"- {item}" for item in report["next_steps"])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True, help="JavaScript/source file; repeatable")
    parser.add_argument("--trace", action="append", type=Path, default=[], help="runtime trace file; repeatable")
    parser.add_argument("--fixture", action="append", type=Path, default=[], help="request/signer fixture; repeatable")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="per-input read limit")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="optional report path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = classify_paths(args.source, args.trace, args.fixture, args.max_bytes)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    rendered = render_markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output.expanduser().resolve()
        protected_inputs = {Path(str(item["path"])).resolve() for item in report["inputs"]}
        if output in protected_inputs:
            print(
                json.dumps(
                    {"ok": False, "error": "output path collides with an input", "path": str(output)},
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
