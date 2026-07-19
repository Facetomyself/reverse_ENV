#!/usr/bin/env python3
"""Validate evidence artifacts for a web-deobfuscation case manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Sequence


SCHEMA_VERSION = 1
DEFAULT_MAX_JSON_BYTES = 8 * 1024 * 1024

PROFILE_CONTRACTS: dict[str, dict[str, object]] = {
    "ast-safe": {
        "claim_scopes": {"transform-only", "algorithm-only"},
        "artifacts": {"input_snapshot", "output_snapshot", "parse_before", "parse_after", "transform_report"},
        "checks": {
            "parse_roundtrip": {"parse_before", "parse_after"},
            "safe_passes_only": {"transform_report"},
        },
    },
    "jsvm-verifiable": {
        "claim_scopes": {"partial", "algorithm-recovered"},
        "artifacts": {"input_snapshot", "opcode_map", "disassembly", "runtime_trace", "request_fixture", "parity_report"},
        "checks": {
            "opcode_map_coverage": {"opcode_map", "disassembly"},
            "trace_alignment": {"runtime_trace", "disassembly"},
            "request_parity": {"request_fixture", "parity_report"},
        },
    },
    "wasm-boundary": {
        "claim_scopes": {"boundary-only", "partial"},
        "artifacts": {"input_snapshot", "imports_exports", "boundary_trace", "wrapper_fixture", "parity_report"},
        "checks": {
            "boundary_inventory": {"imports_exports"},
            "boundary_trace": {"boundary_trace"},
            "wrapper_parity": {"wrapper_fixture", "parity_report"},
        },
    },
    "triage-only": {
        "claim_scopes": {"triage-only"},
        "artifacts": {"input_snapshot", "triage"},
        "checks": {"limitations_recorded": {"triage"}},
    },
}

PASS_REPORT_KEYS = {"parse_before", "parse_after", "parity_report"}
JSON_ARTIFACT_KEYS = {
    "parse_before",
    "parse_after",
    "transform_report",
    "opcode_map",
    "parity_report",
    "imports_exports",
    "domtrace_summary",
}


def add_error(errors: list[dict[str, object]], code: str, **details: object) -> None:
    errors.append({"code": code, **details})


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fingerprint_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def resolve_artifact(root: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("artifact path must be a non-empty string")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise ValueError("artifact path must be relative to the case root")
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("artifact path escapes the case root")
    return resolved


def validate_manifest(
    manifest_path: Path,
    root: Path | None = None,
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> dict[str, object]:
    resolved_manifest = manifest_path.expanduser().resolve(strict=True)
    case_root = (root.expanduser().resolve(strict=True) if root else resolved_manifest.parent.resolve())
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    if max_json_bytes <= 0:
        return {
            "ok": False,
            "errors": [{"code": "max_json_bytes_invalid", "actual": max_json_bytes}],
            "warnings": [],
        }
    if not case_root.is_dir():
        return {
            "ok": False,
            "errors": [{"code": "case_root_not_directory", "path": str(case_root)}],
            "warnings": [],
        }

    if resolved_manifest.stat().st_size > max_json_bytes:
        return {
            "ok": False,
            "errors": [
                {
                    "code": "manifest_too_large",
                    "bytes": resolved_manifest.stat().st_size,
                    "max_json_bytes": max_json_bytes,
                }
            ],
            "warnings": [],
        }
    try:
        manifest = load_json(resolved_manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [{"code": "manifest_invalid", "detail": str(exc)}], "warnings": []}
    if not isinstance(manifest, dict):
        return {"ok": False, "errors": [{"code": "manifest_not_object"}], "warnings": []}

    if manifest.get("schema_version") != SCHEMA_VERSION:
        add_error(errors, "schema_version_mismatch", expected=SCHEMA_VERSION, actual=manifest.get("schema_version"))
    case_id = manifest.get("case_id")
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", case_id):
        add_error(errors, "case_id_invalid", actual=case_id)

    profile = manifest.get("profile")
    contract = PROFILE_CONTRACTS.get(str(profile))
    if contract is None:
        add_error(errors, "profile_invalid", actual=profile, allowed=sorted(PROFILE_CONTRACTS))
        contract = {"claim_scopes": set(), "artifacts": set(), "checks": {}}
    claim_scope = manifest.get("claim_scope")
    if claim_scope not in contract["claim_scopes"]:
        add_error(errors, "claim_scope_invalid", profile=profile, actual=claim_scope, allowed=sorted(contract["claim_scopes"]))

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        add_error(errors, "artifacts_not_object")
        artifacts = {}
    required_artifacts = set(contract["artifacts"])
    for key in sorted(required_artifacts - set(artifacts)):
        add_error(errors, "artifact_missing", artifact=key)

    artifact_report: list[dict[str, object]] = []
    artifact_json: dict[str, object] = {}
    for key, raw_path in sorted(artifacts.items()):
        try:
            path = resolve_artifact(case_root, raw_path)
        except ValueError as exc:
            add_error(errors, "artifact_path_invalid", artifact=key, detail=str(exc), path=raw_path)
            continue
        if not path.is_file():
            add_error(errors, "artifact_not_found", artifact=key, path=str(path))
            continue
        size, sha256 = fingerprint_file(path)
        if not size:
            add_error(errors, "artifact_empty", artifact=key, path=str(path))
            continue
        artifact_report.append(
            {"key": key, "path": str(path), "bytes": size, "sha256": sha256}
        )
        if path.suffix.lower() == ".json":
            if size > max_json_bytes:
                add_error(
                    errors,
                    "artifact_json_too_large",
                    artifact=key,
                    path=str(path),
                    bytes=size,
                    max_json_bytes=max_json_bytes,
                )
                continue
            try:
                artifact_json[key] = load_json(path)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                add_error(errors, "artifact_json_invalid", artifact=key, path=str(path), detail=str(exc))
        elif key in JSON_ARTIFACT_KEYS:
            add_error(errors, "artifact_json_required", artifact=key, path=str(path))

    checks = manifest.get("checks")
    if not isinstance(checks, dict):
        add_error(errors, "checks_not_object")
        checks = {}
    required_checks: dict[str, set[str]] = contract["checks"]
    for check_name, required_evidence in required_checks.items():
        check = checks.get(check_name)
        if not isinstance(check, dict):
            add_error(errors, "check_missing", check=check_name)
            continue
        if check.get("passed") is not True:
            add_error(errors, "check_not_passed", check=check_name)
        evidence = check.get("evidence")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            add_error(errors, "check_evidence_invalid", check=check_name)
            continue
        missing_evidence = required_evidence - set(evidence)
        if missing_evidence:
            add_error(errors, "check_evidence_missing", check=check_name, artifacts=sorted(missing_evidence))
        unknown = set(evidence) - set(artifacts)
        if unknown:
            add_error(errors, "check_evidence_unknown", check=check_name, artifacts=sorted(unknown))

    for key in PASS_REPORT_KEYS & set(artifact_json):
        payload = artifact_json[key]
        if not isinstance(payload, dict) or payload.get("passed") is not True:
            add_error(errors, "evidence_report_not_passed", artifact=key)
    transform_report = artifact_json.get("transform_report")
    if profile == "ast-safe":
        if not isinstance(transform_report, dict):
            add_error(errors, "transform_report_invalid")
        else:
            applied = transform_report.get("applied_passes")
            unsafe = transform_report.get("unsafe_passes")
            if not isinstance(applied, list) or not all(isinstance(item, str) for item in applied):
                add_error(errors, "applied_passes_invalid")
            elif not applied:
                add_error(errors, "applied_passes_empty")
            if not isinstance(unsafe, list) or not all(isinstance(item, str) for item in unsafe):
                add_error(errors, "unsafe_passes_invalid")
            elif unsafe:
                add_error(errors, "unsafe_passes_present", passes=unsafe)
    opcode_map = artifact_json.get("opcode_map")
    if profile == "jsvm-verifiable":
        if not isinstance(opcode_map, dict):
            add_error(errors, "opcode_map_invalid")
        else:
            if not opcode_map.get("opcodes"):
                add_error(errors, "opcode_map_empty")
            if not opcode_map.get("instruction_widths"):
                add_error(errors, "instruction_widths_empty")
    imports_exports = artifact_json.get("imports_exports")
    if profile == "wasm-boundary":
        if not isinstance(imports_exports, dict):
            add_error(errors, "imports_exports_invalid")
        elif not isinstance(imports_exports.get("imports"), list) or not isinstance(imports_exports.get("exports"), list):
            add_error(errors, "imports_exports_invalid")
        domtrace_summary = artifact_json.get("domtrace_summary")
        if "domtrace_summary" in artifacts:
            if not isinstance(domtrace_summary, dict):
                add_error(errors, "domtrace_summary_invalid")
            else:
                counts: dict[str, int] = {}
                for key in (
                    "raw_invalid_lines",
                    "repaired_lines",
                    "unrecoverable_lines",
                ):
                    value = domtrace_summary.get(key)
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        add_error(
                            errors,
                            "domtrace_count_invalid",
                            field=key,
                            actual=value,
                        )
                    else:
                        counts[key] = value
                if domtrace_summary.get("schema_version") != 2:
                    add_error(
                        errors,
                        "domtrace_schema_version_invalid",
                        expected=2,
                        actual=domtrace_summary.get("schema_version"),
                    )
                if len(counts) == 3:
                    if counts["raw_invalid_lines"] != (
                        counts["repaired_lines"] + counts["unrecoverable_lines"]
                    ):
                        add_error(errors, "domtrace_count_invariant_failed")
                    if counts["unrecoverable_lines"] != 0:
                        add_error(
                            errors,
                            "domtrace_unrecoverable_lines_present",
                            actual=counts["unrecoverable_lines"],
                        )
                    if domtrace_summary.get("invalid_lines") != counts["unrecoverable_lines"]:
                        add_error(errors, "domtrace_invalid_alias_mismatch")
                    repair_details = domtrace_summary.get("repair_details")
                    if (
                        not isinstance(repair_details, list)
                        or len(repair_details) != counts["repaired_lines"]
                        or not all(
                            isinstance(item, dict)
                            and isinstance(item.get("line"), int)
                            and not isinstance(item.get("line"), bool)
                            and item["line"] > 0
                            and isinstance(item.get("reason"), str)
                            and bool(item["reason"])
                            for item in repair_details
                        )
                    ):
                        add_error(errors, "domtrace_repair_details_mismatch")
                    unrecoverable_details = domtrace_summary.get("unrecoverable_details")
                    if (
                        not isinstance(unrecoverable_details, list)
                        or len(unrecoverable_details) != counts["unrecoverable_lines"]
                    ):
                        add_error(errors, "domtrace_unrecoverable_details_mismatch")
    limitations = manifest.get("limitations")
    if profile == "triage-only" and (not isinstance(limitations, list) or not limitations):
        add_error(errors, "triage_limitations_missing")

    if manifest.get("unsafe_passes"):
        add_error(errors, "unsafe_passes_not_supported", passes=manifest.get("unsafe_passes"))
    return {
        "ok": not errors,
        "case_id": case_id,
        "profile": profile,
        "claim_scope": claim_scope,
        "case_root": str(case_root),
        "artifacts": artifact_report,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, help="case root; defaults to manifest directory")
    parser.add_argument("--max-json-bytes", type=int, default=DEFAULT_MAX_JSON_BYTES, help="per-JSON read limit")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_manifest(args.manifest, args.root, args.max_json_bytes)
    except OSError as exc:
        report = {"ok": False, "errors": [{"code": "io_error", "detail": str(exc)}], "warnings": []}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        output = args.report.expanduser().resolve()
        protected_paths = {args.manifest.expanduser().resolve()}
        protected_paths.update(
            Path(str(item["path"])).resolve()
            for item in report.get("artifacts", [])
            if isinstance(item, dict) and "path" in item
        )
        if output in protected_paths:
            collision = {
                "ok": False,
                "errors": [{"code": "report_path_collides", "path": str(output)}],
                "warnings": [],
            }
            sys.stderr.write(json.dumps(collision, ensure_ascii=False, indent=2) + "\n")
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
