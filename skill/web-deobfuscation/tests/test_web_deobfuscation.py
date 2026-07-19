from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate = load_module("web_deobfuscation_gate", SKILL_ROOT / "scripts" / "web_deobfuscation_gate.py")
validator = load_module(
    "validate_web_deobfuscation_case",
    SKILL_ROOT / "scripts" / "validate_web_deobfuscation_case.py",
)


class GateTests(unittest.TestCase):
    def test_ast_source_is_ast_safe(self) -> None:
        report = gate.classify_paths([FIXTURES / "ast-source.js"])
        self.assertEqual(report["profile"], "ast-safe")
        self.assertEqual(report["claim_scope"], "transform-only")

    def test_vm_without_trace_stays_triage_only(self) -> None:
        report = gate.classify_paths([FIXTURES / "vm-source.js"])
        self.assertEqual(report["profile"], "triage-only")
        self.assertEqual(report["depth"], "L4")

    def test_vm_trace_and_fixture_are_verifiable(self) -> None:
        report = gate.classify_paths(
            [FIXTURES / "vm-source.js"],
            [FIXTURES / "vm-trace.ndjson"],
            [FIXTURES / "request.fixture.json"],
        )
        self.assertEqual(report["profile"], "jsvm-verifiable")
        self.assertIn("opcode_event", report["marker_summary"]["trace_vm"])

    def test_trace_markers_do_not_reclassify_plain_source(self) -> None:
        report = gate.classify_paths(
            [FIXTURES / "plain-source.js"],
            [FIXTURES / "vm-trace.ndjson"],
            [FIXTURES / "request.fixture.json"],
        )
        self.assertEqual(report["profile"], "plain-js")

    def test_wasm_boundary_trace_is_partial_l3(self) -> None:
        report = gate.classify_paths(
            [FIXTURES / "wasm-source.js"],
            [FIXTURES / "wasm-boundary.ndjson"],
            [FIXTURES / "request.fixture.json"],
        )
        self.assertEqual(report["profile"], "wasm-boundary")
        self.assertEqual(report["claim_scope"], "boundary-only")
        self.assertGreaterEqual(len(report["marker_summary"]["trace_wasm_boundary"]), 2)

    def test_wasm_without_boundary_trace_stays_triage_only(self) -> None:
        report = gate.classify_paths(
            [FIXTURES / "wasm-source.js"],
            [FIXTURES / "vm-trace.ndjson"],
            [FIXTURES / "request.fixture.json"],
        )
        self.assertEqual(report["profile"], "triage-only")

    def test_plain_source_returns_to_upstream(self) -> None:
        report = gate.classify_paths([FIXTURES / "plain-source.js"])
        self.assertEqual(report["profile"], "plain-js")

    def test_gate_refuses_to_overwrite_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "target.js"
            original = "const _0xabc = ['keep'];\n"
            source.write_text(original, encoding="utf-8", newline="\n")
            with contextlib.redirect_stderr(io.StringIO()):
                result = gate.main(["--source", str(source), "--output", str(source)])
            self.assertEqual(result, 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


class ManifestValidatorTests(unittest.TestCase):
    def write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def make_ast_case(self, root: Path) -> Path:
        samples = root / "samples"
        evidence = root / "evidence"
        samples.mkdir(parents=True)
        evidence.mkdir(parents=True)
        (samples / "input.js").write_text("const _0xabc = ['ok'];\n", encoding="utf-8", newline="\n")
        (samples / "output.js").write_text("const values = ['ok'];\n", encoding="utf-8", newline="\n")
        self.write_json(evidence / "parse-before.json", {"passed": True, "parser": "fixture"})
        self.write_json(evidence / "parse-after.json", {"passed": True, "parser": "fixture"})
        self.write_json(
            evidence / "transform-report.json",
            {"applied_passes": ["rename-string-array"], "unsafe_passes": []},
        )
        manifest = {
            "schema_version": 1,
            "case_id": "ast-case",
            "profile": "ast-safe",
            "claim_scope": "transform-only",
            "artifacts": {
                "input_snapshot": "samples/input.js",
                "output_snapshot": "samples/output.js",
                "parse_before": "evidence/parse-before.json",
                "parse_after": "evidence/parse-after.json",
                "transform_report": "evidence/transform-report.json",
            },
            "checks": {
                "parse_roundtrip": {
                    "passed": True,
                    "evidence": ["parse_before", "parse_after"],
                },
                "safe_passes_only": {
                    "passed": True,
                    "evidence": ["transform_report"],
                },
            },
            "limitations": [],
        }
        manifest_path = root / "case.json"
        self.write_json(manifest_path, manifest)
        return manifest_path

    def make_wasm_case(self, root: Path, unrecoverable_lines: int = 0) -> Path:
        samples = root / "samples"
        evidence = root / "evidence"
        samples.mkdir(parents=True)
        evidence.mkdir(parents=True)
        (samples / "input.js").write_text(
            "WebAssembly.instantiate(new Uint8Array());\n",
            encoding="utf-8",
            newline="\n",
        )
        self.write_json(
            evidence / "imports-exports.json",
            {"imports": [], "exports": []},
        )
        self.write_json(evidence / "boundary-trace.json", {"events": []})
        self.write_json(evidence / "wrapper-fixture.json", {"request_id": "fixture"})
        self.write_json(evidence / "parity-report.json", {"passed": True})
        repaired_lines = 1
        self.write_json(
            evidence / "domtrace-summary.json",
            {
                "schema_version": 2,
                "invalid_lines": unrecoverable_lines,
                "raw_invalid_lines": repaired_lines + unrecoverable_lines,
                "repaired_lines": repaired_lines,
                "unrecoverable_lines": unrecoverable_lines,
                "repair_details": [
                    {
                        "line": 7,
                        "reason": "typeof-function-source-closing-quote",
                    }
                ],
                "unrecoverable_details": (
                    []
                    if unrecoverable_lines == 0
                    else [
                        {
                            "line": 8,
                            "reason": "fixture-invalid",
                            "column": 1,
                        }
                    ]
                ),
            },
        )
        manifest = {
            "schema_version": 1,
            "case_id": "wasm-case",
            "profile": "wasm-boundary",
            "claim_scope": "boundary-only",
            "artifacts": {
                "input_snapshot": "samples/input.js",
                "imports_exports": "evidence/imports-exports.json",
                "boundary_trace": "evidence/boundary-trace.json",
                "wrapper_fixture": "evidence/wrapper-fixture.json",
                "parity_report": "evidence/parity-report.json",
                "domtrace_summary": "evidence/domtrace-summary.json",
            },
            "checks": {
                "boundary_inventory": {
                    "passed": True,
                    "evidence": ["imports_exports"],
                },
                "boundary_trace": {
                    "passed": True,
                    "evidence": ["boundary_trace", "domtrace_summary"],
                },
                "wrapper_parity": {
                    "passed": True,
                    "evidence": ["wrapper_fixture", "parity_report"],
                },
            },
            "limitations": ["boundary-only fixture"],
        }
        manifest_path = root / "case.json"
        self.write_json(manifest_path, manifest)
        return manifest_path

    def test_valid_ast_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = validator.validate_manifest(self.make_ast_case(root))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(report["artifacts"]), 5)

    def test_valid_domtrace_summary_passes_wasm_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = validator.validate_manifest(self.make_wasm_case(root))
        self.assertTrue(report["ok"], report["errors"])

    def test_unrecoverable_domtrace_line_fails_wasm_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = validator.validate_manifest(
                self.make_wasm_case(root, unrecoverable_lines=1)
            )
        codes = {item["code"] for item in report["errors"]}
        self.assertFalse(report["ok"])
        self.assertIn("domtrace_unrecoverable_lines_present", codes)

    def test_artifact_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "case"
            root.mkdir()
            manifest_path = self.make_ast_case(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["input_snapshot"] = "../outside.js"
            self.write_json(manifest_path, manifest)
            report = validator.validate_manifest(manifest_path)
        codes = {item["code"] for item in report["errors"]}
        self.assertFalse(report["ok"])
        self.assertIn("artifact_path_invalid", codes)

    def test_pass_report_must_be_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self.make_ast_case(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            (root / "evidence" / "parse-before.txt").write_text("passed\n", encoding="utf-8", newline="\n")
            manifest["artifacts"]["parse_before"] = "evidence/parse-before.txt"
            self.write_json(manifest_path, manifest)
            report = validator.validate_manifest(manifest_path)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("artifact_json_required", codes)

    def test_manifest_size_limit_is_enforced_before_json_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self.make_ast_case(root)
            report = validator.validate_manifest(manifest_path, max_json_bytes=1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("manifest_too_large", codes)

    def test_unsafe_ast_pass_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self.make_ast_case(root)
            self.write_json(
                root / "evidence" / "transform-report.json",
                {
                    "applied_passes": ["execute-string-decoder"],
                    "unsafe_passes": ["execute-string-decoder"],
                },
            )
            report = validator.validate_manifest(manifest_path)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("unsafe_passes_present", codes)

    def test_empty_ast_pass_list_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self.make_ast_case(root)
            self.write_json(
                root / "evidence" / "transform-report.json",
                {"applied_passes": [], "unsafe_passes": []},
            )
            report = validator.validate_manifest(manifest_path)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("applied_passes_empty", codes)

    def test_validator_refuses_to_overwrite_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self.make_ast_case(root)
            original = manifest_path.read_text(encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                result = validator.main(
                    ["--manifest", str(manifest_path), "--report", str(manifest_path)]
                )
            self.assertEqual(result, 2)
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
