#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_EPROJECTFILE_COMMIT = "aee36ceea0b63eb5cf83780631dd4d776608cd1e"
EXPECTED_JINGYI_COMMIT = "73a7c454935541f5fb695a75474471bf8c7057d7"
EXPECTED_JINGYI_SHA256 = "2b6ea71d3d56031e266020fbb695b0615839461fcb19a5f3d3389f44c236f8ca"


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime" / "verify-jingyi",
    )
    args = parser.parse_args()

    eprojectfile = ROOT / "upstream" / "EProjectFile"
    jingyi_repo = ROOT / "assets" / "jingyi-ec"
    jingyi_file = jingyi_repo / "精易模块11.1.6.e"

    assert git_head(eprojectfile) == EXPECTED_EPROJECTFILE_COMMIT
    assert git_head(jingyi_repo) == EXPECTED_JINGYI_COMMIT
    assert hashlib.sha256(jingyi_file.read_bytes()).hexdigest() == EXPECTED_JINGYI_SHA256

    safe_project = (ROOT / "src" / "QIQI.EProjectFile.Safe" / "QIQI.EProjectFile.Safe.csproj").read_text(encoding="utf-8")
    assert "PackageReference" not in safe_project
    patch_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (ROOT / "src" / "QIQI.EProjectFile.Safe" / "Patches").glob("*.cs")
    )
    assert "OpenEpl.ELibInfo" not in patch_text
    assert "ELibInfoLoader" not in patch_text

    metadata = json.loads((args.output / "project_metadata.json").read_text(encoding="utf-8"))
    resources = json.loads((args.output / "resources_manifest.json").read_text(encoding="utf-8"))
    errors = json.loads((args.output / "method_errors.json").read_text(encoding="utf-8"))
    counts = metadata["counts"]
    assert metadata["inputSha256"] == EXPECTED_JINGYI_SHA256
    assert counts["classes"] == 106
    assert counts["methods"] == 3556
    assert counts["forms"] == 0
    assert counts["constants"] == 2621
    assert counts["methodParseErrors"] == 0
    assert len(resources) == 91
    assert errors == []
    assert metadata["safety"]["targetExecuted"] is False
    assert metadata["safety"]["supportLibraryLoaded"] is False
    assert metadata["safety"]["externalHelperProcessStarted"] is False

    for item in resources:
        resource_path = args.output / item["path"]
        data = resource_path.read_bytes()
        assert not data.startswith(b"MZ")
        assert not data.startswith(bytes.fromhex("7f454c46"))
        assert resource_path.suffix.lower() not in {
            ".exe", ".dll", ".sys", ".scr", ".ps1", ".bat", ".cmd", ".vbs", ".hta"
        }

    print("epl-source-recovery validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
