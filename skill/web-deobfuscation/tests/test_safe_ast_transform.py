from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REVERSE_ROOT = SKILL_ROOT.parents[1]
NODE = REVERSE_ROOT / "tools" / "node" / "node.exe"
CLI = SKILL_ROOT / "scripts" / "safe_ast_transform.mjs"
VALIDATOR = SKILL_ROOT / "scripts" / "validate_web_deobfuscation_case.py"
INPUT = Path(__file__).resolve().parent / "fixtures" / "safe-ast-input.js"


class SafeAstTransformTests(unittest.TestCase):
    def run_transform(self, root: Path, passes: str | None = None) -> subprocess.CompletedProcess[str]:
        command = [
            str(NODE),
            str(CLI),
            "--input",
            str(INPUT),
            "--output",
            str(root / "output.js"),
            "--parse-before",
            str(root / "parse-before.json"),
            "--parse-after",
            str(root / "parse-after.json"),
            "--report",
            str(root / "transform-report.json"),
        ]
        if passes:
            command.extend(["--passes", passes])
        return subprocess.run(
            command,
            cwd=REVERSE_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_default_passes_are_static_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.run_transform(root)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            output = (root / "output.js").read_text(encoding="utf-8")
            report = json.loads((root / "transform-report.json").read_text(encoding="utf-8"))
            before = json.loads((root / "parse-before.json").read_text(encoding="utf-8"))
            after = json.loads((root / "parse-after.json").read_text(encoding="utf-8"))
        self.assertIn("const folded = 12;", output)
        self.assertIn("answer: folded", output)
        self.assertIn('["__proto__"]', output)
        self.assertIn("const selected = object.answer;", output)
        self.assertNotIn("sideEffect", output)
        self.assertIn("debugger;", output)
        self.assertTrue(before["passed"])
        self.assertTrue(after["passed"])
        self.assertEqual(report["unsafe_passes"], [])
        self.assertFalse(report["target_code_executed"])
        self.assertEqual(report["unsafe_constructs_detected"]["direct_eval"], 1)

    def test_debugger_removal_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.run_transform(root, "remove-debugger-statements")
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            output = (root / "output.js").read_text(encoding="utf-8")
            report = json.loads((root / "transform-report.json").read_text(encoding="utf-8"))
        self.assertNotIn("debugger;", output)
        self.assertEqual(report["applied_passes"], ["remove-debugger-statements"])

    def test_unknown_pass_is_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.run_transform(root, "execute-string-decoder")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "output.js").exists())
        self.assertIn("unknown or unsafe pass", result.stderr)

    def test_generated_artifacts_pass_ast_manifest_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.run_transform(root)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            (root / "input.js").write_bytes(INPUT.read_bytes())
            manifest = {
                "schema_version": 1,
                "case_id": "safe-ast-baseline",
                "profile": "ast-safe",
                "claim_scope": "transform-only",
                "artifacts": {
                    "input_snapshot": "input.js",
                    "output_snapshot": "output.js",
                    "parse_before": "parse-before.json",
                    "parse_after": "parse-after.json",
                    "transform_report": "transform-report.json",
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
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            validation = subprocess.run(
                [
                    str(REVERSE_ROOT / ".venv" / "Scripts" / "python.exe"),
                    str(VALIDATOR),
                    "--manifest",
                    str(manifest_path),
                ],
                cwd=REVERSE_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        self.assertEqual(validation.returncode, 0, validation.stderr or validation.stdout)


if __name__ == "__main__":
    unittest.main()
