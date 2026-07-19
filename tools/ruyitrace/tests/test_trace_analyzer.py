from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "trace_analyzer.py"
SPEC = importlib.util.spec_from_file_location("trace_analyzer", MODULE_PATH)
assert SPEC and SPEC.loader
trace_analyzer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trace_analyzer
SPEC.loader.exec_module(trace_analyzer)


class TraceAnalyzerTests(unittest.TestCase):
    def test_current_interface_member_schema_is_normalized(self) -> None:
        event = {
            "type": "call",
            "interface": "CanvasRenderingContext2D",
            "member": "fillText",
        }
        self.assertEqual(
            trace_analyzer.event_api(event),
            "CanvasRenderingContext2D.fillText",
        )

    def test_legacy_api_schema_remains_supported(self) -> None:
        self.assertEqual(
            trace_analyzer.event_api({"api": "Crypto.getRandomValues"}),
            "Crypto.getRandomValues",
        )

    def test_summary_categorizes_both_schemas(self) -> None:
        events = [
            {"api": "Crypto.getRandomValues", "stack": "fixture.js:1:1"},
            {
                "type": "call",
                "interface": "HTMLCanvasElement",
                "member": "toDataURL",
                "stack": [{"file": "fixture.js", "line": 2, "col": 3}],
            },
            {"type": "trace_init", "pid": 1},
        ]
        categorized = trace_analyzer.categorize(events)
        summary = trace_analyzer.build_summary(events, categorized)
        self.assertEqual(summary["api_events"], 2)
        self.assertEqual(summary["call_events"], 2)
        self.assertEqual(summary["unique_apis"], 2)
        self.assertEqual(summary["categories"]["crypto"]["calls"], 1)
        self.assertEqual(summary["categories"]["canvas"]["calls"], 1)

    @staticmethod
    def malformed_function_source_line() -> tuple[str, dict[str, object]]:
        event = {
            "seq": 7,
            "type": "typeof",
            "operand": {
                "type": "Function",
                "source": "function fixture() {\n  return 1;\n}\n",
            },
            "result": "function",
            "stack": [{"func": "supportsMethod", "file": "fixture.mjs"}],
        }
        valid = json.dumps(event, separators=(",", ":"))
        malformed = valid.replace(
            '"},"result":"function","stack":',
            '\\"},"result":"function","stack":',
            1,
        )
        return malformed, event

    def test_known_function_source_boundary_is_repaired_and_audited(self) -> None:
        malformed, expected = self.malformed_function_source_line()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.ndjson"
            path.write_text(malformed + "\n", encoding="utf-8", newline="\n")
            events, diagnostics = trace_analyzer.load_trace(path)
        self.assertEqual(events, [expected])
        self.assertEqual(diagnostics["raw_invalid_lines"], 1)
        self.assertEqual(diagnostics["repaired_lines"], 1)
        self.assertEqual(diagnostics["unrecoverable_lines"], 0)
        self.assertEqual(
            diagnostics["repair_details"],
            [
                {
                    "line": 1,
                    "reason": trace_analyzer.FUNCTION_SOURCE_REPAIR_REASON,
                }
            ],
        )

    def test_valid_json_is_not_rewritten(self) -> None:
        expected = {"type": "call", "interface": "Performance", "member": "now"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.ndjson"
            path.write_text(
                json.dumps(expected) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            events, diagnostics = trace_analyzer.load_trace(path)
        self.assertEqual(events, [expected])
        self.assertEqual(diagnostics, trace_analyzer.empty_trace_diagnostics())

    def test_unrelated_invalid_line_remains_unrecoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.ndjson"
            path.write_text(
                json.dumps({"interface": "Performance", "member": "now"})
                + "\nnot-json\n",
                encoding="utf-8",
                newline="\n",
            )
            events, diagnostics = trace_analyzer.load_trace(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(diagnostics["raw_invalid_lines"], 1)
        self.assertEqual(diagnostics["repaired_lines"], 0)
        self.assertEqual(diagnostics["unrecoverable_lines"], 1)

    def test_non_object_json_line_remains_unrecoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.ndjson"
            path.write_text("[]\n", encoding="utf-8", newline="\n")
            events, diagnostics = trace_analyzer.load_trace(path)
        self.assertEqual(events, [])
        self.assertEqual(diagnostics["raw_invalid_lines"], 1)
        self.assertEqual(diagnostics["repaired_lines"], 0)
        self.assertEqual(diagnostics["unrecoverable_lines"], 1)
        self.assertEqual(
            diagnostics["unrecoverable_details"][0]["reason"],
            "trace event must be a JSON object",
        )

    def test_ambiguous_boundary_is_not_repaired(self) -> None:
        malformed, _expected = self.malformed_function_source_line()
        ambiguous = malformed + trace_analyzer.FUNCTION_SOURCE_BAD_BOUNDARY
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.ndjson"
            path.write_text(ambiguous + "\n", encoding="utf-8", newline="\n")
            events, diagnostics = trace_analyzer.load_trace(path)
        self.assertEqual(events, [])
        self.assertEqual(diagnostics["raw_invalid_lines"], 1)
        self.assertEqual(diagnostics["repaired_lines"], 0)
        self.assertEqual(diagnostics["unrecoverable_lines"], 1)

    def test_summary_separates_raw_repaired_and_unrecoverable_counts(self) -> None:
        diagnostics = {
            "raw_invalid_lines": 2,
            "repaired_lines": 1,
            "unrecoverable_lines": 1,
            "repair_details": [{"line": 2, "reason": "fixture"}],
            "unrecoverable_details": [{"line": 3, "reason": "fixture", "column": 1}],
        }
        summary = trace_analyzer.build_summary([], {}, diagnostics)
        self.assertEqual(summary["schema_version"], 2)
        self.assertEqual(summary["raw_invalid_lines"], 2)
        self.assertEqual(summary["repaired_lines"], 1)
        self.assertEqual(summary["unrecoverable_lines"], 1)
        self.assertEqual(summary["invalid_lines"], 1)

    def test_cli_strict_fails_only_for_unrecoverable_lines(self) -> None:
        malformed, _expected = self.malformed_function_source_line()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repaired_path = Path(temporary_directory) / "repaired.ndjson"
            invalid_path = Path(temporary_directory) / "invalid.ndjson"
            repaired_path.write_text(malformed + "\n", encoding="utf-8", newline="\n")
            invalid_path.write_text("not-json\n", encoding="utf-8", newline="\n")
            repaired_result = subprocess.run(
                [sys.executable, str(MODULE_PATH), str(repaired_path), "--json", "--strict"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=False,
            )
            invalid_result = subprocess.run(
                [sys.executable, str(MODULE_PATH), str(invalid_path), "--json", "--strict"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=False,
            )
        self.assertEqual(repaired_result.returncode, 0)
        self.assertEqual(json.loads(repaired_result.stdout)["repaired_lines"], 1)
        self.assertEqual(invalid_result.returncode, 2)
        self.assertEqual(json.loads(invalid_result.stdout)["unrecoverable_lines"], 1)


if __name__ == "__main__":
    unittest.main()
