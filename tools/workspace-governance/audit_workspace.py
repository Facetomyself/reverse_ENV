#!/usr/bin/env python3
"""Read-only audit for reverse_ENV workspace repository governance."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator


BANNED_EXTENSIONS = {
    ".apk", ".ipa", ".apks", ".aab", ".dex", ".odex", ".vdex", ".oat",
    ".so", ".dll", ".exe", ".bin", ".dmp", ".dump", ".i64", ".id0",
    ".id1", ".id2", ".nam", ".til", ".har", ".pcap", ".pcapng", ".flow",
    ".keystore", ".jks",
}
SENSITIVE_NAMES = {
    ".env", ".secret", "credentials.json", "cookies.json", "cookie.json",
    "proxy_creds.json", "mailboxes.json", "id_rsa", "id_ed25519",
    ".credentials.local.json", ".account_cache.local.json",
}
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".cache", "dist", "build",
}
FORBIDDEN_EVIDENCE_DIRS = {
    "captures", "raw", "output", "runtime", "artifacts", "browser-profiles",
    ".chrome-profile", "decompiled", "decompile", "unpacked", "jadx-output",
    "apktool-output",
}


@dataclass
class Finding:
    level: str
    code: str
    project: str
    message: str


@dataclass
class ProjectResult:
    name: str
    path: str
    repository_root: str
    lifecycle: str
    integration: str
    readiness: str
    exists: bool = False
    git_repo: bool = False
    branch: str | None = None
    head: str | None = None
    remote: str | None = None
    dirty: bool = False
    files: int = 0
    bytes: int = 0
    banned_candidates: int = 0
    evidence_tree_candidates: int = 0
    sensitive_candidates: int = 0
    tracked_banned: list[str] = field(default_factory=list)
    tracked_sensitive: list[str] = field(default_factory=list)
    tracked_large: list[str] = field(default_factory=list)
    tracked_evidence_tree: list[str] = field(default_factory=list)
    tracked_secret_markers: list[str] = field(default_factory=list)
    nested_git_roots: list[str] = field(default_factory=list)
    github_visibility: str | None = None
    github_default_branch: str | None = None


def run(command: list[str], cwd: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def normalize_remote(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().replace("\\", "/")
    return value[:-4] if value.lower().endswith(".git") else value


def github_slug(remote: str | None) -> str | None:
    normalized = normalize_remote(remote)
    marker = "github.com/"
    if not normalized or marker not in normalized:
        return None
    return normalized.split(marker, 1)[1]


def immediate_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def iter_files(root: Path) -> Iterable[Path]:
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in SKIP_DIRS:
                    pending.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path)


def tracked_files(path: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(path),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [path / item.decode("utf-8", "replace") for item in completed.stdout.split(b"\0") if item]


SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bauthorization\s*[:=]\s*(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)\b(?:client[_-]?secret|password|passwd)\b\s*[:=]\s*[\"']?[^\s\"']{12,}"),
)


def contains_secret_marker(path: Path) -> bool:
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            return False
        raw = path.read_bytes()
    except OSError:
        return False
    if b"\0" in raw:
        return False
    text = raw.decode("utf-8", "replace")
    if "REDACTED" in text and not any(pattern.search(text.replace("REDACTED", "")) for pattern in SECRET_PATTERNS):
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def scan_project(path: Path, repository_path: Path, result: ProjectResult, large_limit: int) -> None:
    for file_path in iter_files(path):
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        result.files += 1
        result.bytes += size
        if file_path.suffix.lower() in BANNED_EXTENSIONS:
            result.banned_candidates += 1
        relative_parts = {part.lower() for part in file_path.relative_to(path).parts[:-1]}
        if relative_parts & FORBIDDEN_EVIDENCE_DIRS:
            result.evidence_tree_candidates += 1
        if file_path.name.lower() in SENSITIVE_NAMES:
            result.sensitive_candidates += 1

    for git_marker in path.rglob(".git"):
        if git_marker.parent == repository_path:
            continue
        try:
            result.nested_git_roots.append(git_marker.parent.relative_to(path).as_posix())
        except ValueError:
            result.nested_git_roots.append(str(git_marker.parent))

    if not result.git_repo:
        return

    for file_path in tracked_files(repository_path):
        relative = file_path.relative_to(repository_path).as_posix()
        if file_path.suffix.lower() in BANNED_EXTENSIONS:
            result.tracked_banned.append(relative)
        if file_path.name.lower() in SENSITIVE_NAMES:
            result.tracked_sensitive.append(relative)
        if {part.lower() for part in Path(relative).parts[:-1]} & FORBIDDEN_EVIDENCE_DIRS:
            result.tracked_evidence_tree.append(relative)
        try:
            if file_path.is_file() and file_path.stat().st_size > large_limit:
                result.tracked_large.append(relative)
        except OSError:
            continue
        if contains_secret_marker(file_path):
            result.tracked_secret_markers.append(relative)


def git_metadata(path: Path, result: ProjectResult, remote_name: str) -> None:
    result.git_repo = immediate_git_repo(path)
    if not result.git_repo:
        return
    branch = run(["git", "branch", "--show-current"], path)
    head = run(["git", "rev-parse", "HEAD"], path)
    remote = run(["git", "remote", "get-url", remote_name], path)
    status = run(["git", "status", "--porcelain"], path)
    result.branch = branch.stdout.strip() or None
    result.head = head.stdout.strip() or None
    result.remote = remote.stdout.strip() if remote.returncode == 0 else None
    result.dirty = bool(status.stdout.strip())


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        raise ValueError("registry must contain a top-level projects list")
    return data


def validate_schema(data: dict[str, Any], schema_path: Path) -> list[str]:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    normalized = json.loads(json.dumps(data, default=str))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(x) for x in error.path) or '<root>'}: {error.message}" for error in validator.iter_errors(normalized)]


def root_submodule_paths(root: Path) -> set[str]:
    modules = root / ".gitmodules"
    if not modules.exists():
        return set()
    completed = run(
        ["git", "config", "--file", str(modules), "--get-regexp", r"^submodule\..*\.path$"],
        root,
    )
    paths: set[str] = set()
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            paths.add(parts[1].replace("\\", "/"))
    return paths


def root_gitlink_paths(root: Path) -> set[str]:
    completed = run(["git", "ls-files", "--stage"], root)
    paths: set[str] = set()
    for line in completed.stdout.splitlines():
        metadata, _, path = line.partition("\t")
        if metadata.startswith("160000 ") and path:
            paths.add(path.replace("\\", "/"))
    return paths


def audit(args: argparse.Namespace) -> tuple[list[ProjectResult], list[Finding]]:
    root = args.root.resolve()
    registry = load_registry(args.registry.resolve())
    projects = registry["projects"]
    selected = set(args.project or [])
    findings: list[Finding] = []
    results: list[ProjectResult] = []
    names: set[str] = set()
    paths: set[str] = set()
    submodules = root_submodule_paths(root)
    gitlinks = root_gitlink_paths(root)
    for error in validate_schema(registry, args.schema.resolve()):
        findings.append(Finding("error", "registry-schema", "<registry>", error))
    registry_names = {str(item.get("name", "")) for item in projects}
    for unknown in sorted(selected - registry_names):
        findings.append(Finding("error", "unknown-project", unknown, "requested project is absent from registry"))

    for entry in projects:
        name = str(entry.get("name", ""))
        rel = str(entry.get("path", "")).replace("\\", "/")
        if selected and name not in selected:
            continue
        lifecycle = str(entry.get("lifecycle", ""))
        integration = str(entry.get("integration", ""))
        readiness = str(entry.get("readiness", ""))
        ownership = str(entry.get("ownership", ""))
        visibility = str(entry.get("visibility", ""))
        repository_rel = str(entry.get("repository_root") or rel).replace("\\", "/")
        result = ProjectResult(
            name=name,
            path=rel,
            repository_root=repository_rel,
            lifecycle=lifecycle,
            integration=integration,
            readiness=readiness,
        )
        results.append(result)

        if not name or name in names:
            findings.append(Finding("error", "registry-name", name or "<empty>", "missing or duplicate project name"))
        names.add(name)
        if not rel.startswith("workspace/") or rel in paths:
            findings.append(Finding("error", "registry-path", name, f"invalid or duplicate path: {rel}"))
        paths.add(rel)
        if readiness not in {"ready", "existing", "deferred", "curation-required", "incomplete", "excluded"}:
            findings.append(Finding("error", "registry-readiness", name, f"invalid readiness: {readiness or '<empty>'}"))
        if lifecycle not in {"planned", "active", "deferred-active", "archived", "excluded"}:
            findings.append(Finding("error", "registry-lifecycle", name, f"invalid lifecycle: {lifecycle or '<empty>'}"))
        if integration not in {"registry", "submodule", "excluded"}:
            findings.append(Finding("error", "registry-integration", name, f"invalid integration: {integration or '<empty>'}"))
        if visibility not in {"private", "public"}:
            findings.append(Finding("error", "registry-visibility", name, f"invalid visibility: {visibility or '<empty>'}"))
        if ownership not in {"owned", "external"}:
            findings.append(Finding("error", "registry-ownership", name, f"invalid ownership: {ownership or '<empty>'}"))
        if not entry.get("last_audited"):
            findings.append(Finding("error", "registry-audit-date", name, "last_audited is required"))
        if integration == "excluded" and lifecycle != "excluded":
            findings.append(Finding("error", "excluded-lifecycle", name, "excluded integration requires excluded lifecycle"))
        if ownership == "external" and integration != "excluded":
            findings.append(Finding("error", "external-integration", name, "external worktrees must use excluded integration"))

        project_path = root / Path(rel)
        repository_path = root / Path(repository_rel)
        result.exists = project_path.is_dir()
        if not result.exists:
            if integration == "submodule" or selected or args.require_local:
                findings.append(Finding("error", "missing-path", name, f"required local checkout does not exist: {rel}"))
            continue

        try:
            repository_path.resolve().relative_to(project_path.resolve())
            repository_within_project = True
        except ValueError:
            repository_within_project = False
        if not repository_path.is_dir() or not repository_within_project:
            findings.append(Finding("error", "repository-root", name, f"invalid repository_root: {repository_rel}"))
            continue

        git_metadata(repository_path, result, str(entry.get("remote_name") or "origin"))
        scan_project(project_path, repository_path, result, args.large_limit_mb * 1024 * 1024)

        expected_remote = normalize_remote(entry.get("remote"))
        actual_remote = normalize_remote(result.remote)
        if expected_remote and result.git_repo and actual_remote != expected_remote:
            findings.append(Finding("error", "remote-mismatch", name, f"expected {expected_remote}, found {actual_remote or 'none'}"))
        if lifecycle in {"active", "deferred-active"} and not expected_remote:
            findings.append(Finding("error", "missing-remote", name, "active or deferred-active projects require a registry remote"))
        if ownership == "owned" and integration != "excluded" and not expected_remote:
            findings.append(Finding("error", "missing-owned-remote", name, "owned non-excluded projects require a reserved or active remote"))
        if args.check_github and expected_remote:
            slug = github_slug(expected_remote)
            if not slug:
                findings.append(Finding("error", "github-remote", name, "--check-github only supports github.com remotes"))
            else:
                completed = run(
                    [str(args.gh), "repo", "view", slug, "--json", "visibility,defaultBranchRef"],
                    root,
                )
                if completed.returncode != 0:
                    findings.append(Finding("error", "github-missing", name, completed.stderr.strip() or "GitHub repository lookup failed"))
                else:
                    info = json.loads(completed.stdout)
                    result.github_visibility = str(info.get("visibility") or "").lower() or None
                    branch_info = info.get("defaultBranchRef") or {}
                    result.github_default_branch = branch_info.get("name")
                    if result.github_visibility != visibility:
                        findings.append(Finding("error", "github-visibility", name, f"registry={visibility}, GitHub={result.github_visibility}"))
                    if lifecycle in {"active", "deferred-active"} and result.github_default_branch != str(entry.get("default_branch")):
                        findings.append(Finding("error", "github-default-branch", name, f"registry={entry.get('default_branch')}, GitHub={result.github_default_branch}"))
        if lifecycle in {"active", "deferred-active"} and integration != "excluded" and not result.git_repo:
            findings.append(Finding("error", "missing-git", name, "active project is not an independent Git repository"))
        if lifecycle == "deferred-active" and not bool(entry.get("protected")):
            findings.append(Finding("error", "missing-protection", name, "deferred-active project must set protected: true"))
        if integration == "submodule" and (rel not in submodules or rel not in gitlinks):
            findings.append(Finding("error", "missing-submodule", name, "submodule requires both a .gitmodules entry and a mode 160000 gitlink"))
        if integration != "submodule" and (rel in submodules or rel in gitlinks):
            findings.append(Finding("error", "unexpected-submodule", name, "path is a submodule but registry integration differs"))
        if result.tracked_banned:
            level = "warning" if integration == "excluded" else "error"
            findings.append(Finding(level, "tracked-banned", name, f"tracked forbidden files: {', '.join(result.tracked_banned[:5])}"))
        if result.tracked_sensitive:
            level = "warning" if integration == "excluded" else "error"
            findings.append(Finding(level, "tracked-sensitive", name, f"tracked sensitive files: {', '.join(result.tracked_sensitive[:5])}"))
        if result.tracked_large:
            level = "warning" if integration == "excluded" else "error"
            findings.append(Finding(level, "tracked-large", name, f"tracked files exceed {args.large_limit_mb} MiB: {', '.join(result.tracked_large[:5])}"))
        if result.tracked_evidence_tree:
            level = "warning" if integration == "excluded" else "error"
            findings.append(Finding(level, "tracked-evidence-tree", name, f"tracked raw/generated evidence paths: {', '.join(result.tracked_evidence_tree[:5])}"))
        if result.tracked_secret_markers:
            level = "warning" if integration == "excluded" else "error"
            findings.append(Finding(level, "tracked-secret-marker", name, f"tracked text contains secret markers: {', '.join(result.tracked_secret_markers[:5])}"))
        if not result.git_repo and lifecycle == "planned" and (result.banned_candidates or result.evidence_tree_candidates):
            findings.append(Finding("warning", "curation-required", name, f"contains {result.banned_candidates} forbidden files and {result.evidence_tree_candidates} raw/generated evidence paths before initialization"))
        if result.sensitive_candidates:
            findings.append(Finding("warning", "sensitive-candidates", name, f"contains {result.sensitive_candidates} sensitive-name candidates; inspect before staging"))
        if result.nested_git_roots:
            findings.append(Finding("warning", "nested-git", name, f"contains nested Git roots: {', '.join(result.nested_git_roots[:5])}"))

    if not selected:
        workspace = root / "workspace"
        actual_dirs = {item.name for item in workspace.iterdir() if item.is_dir()}
        registered_dirs = {Path(item["path"]).name for item in projects if item.get("path")}
        for missing in sorted(actual_dirs - registered_dirs):
            findings.append(Finding("error", "unregistered-directory", missing, "workspace directory is absent from registry"))
        if args.require_local:
            for stale in sorted(registered_dirs - actual_dirs):
                findings.append(Finding("error", "stale-registry", stale, "registry entry has no local workspace directory"))

    return results, findings


def print_human(results: list[ProjectResult], findings: list[Finding]) -> None:
    for item in results:
        size_mb = item.bytes / (1024 * 1024)
        print(
            f"{item.name}: {item.lifecycle}/{item.integration}/{item.readiness} "
            f"git={'yes' if item.git_repo else 'no'} dirty={'yes' if item.dirty else 'no'} "
            f"files={item.files} size={size_mb:.1f}MiB banned={item.banned_candidates} raw={item.evidence_tree_candidates}"
        )
    if findings:
        print("\nFindings:")
        for finding in findings:
            print(f"[{finding.level.upper()}] {finding.project} {finding.code}: {finding.message}")
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    print(f"\nSummary: projects={len(results)} errors={errors} warnings={warnings}")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_root = script.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--registry", type=Path, default=default_root / "docs" / "workspace-projects.yaml")
    parser.add_argument("--schema", type=Path, default=script.parent / "workspace-projects.schema.json")
    parser.add_argument("--project", action="append", help="audit only one named project; repeatable")
    parser.add_argument("--large-limit-mb", type=int, default=50)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--output", type=Path, help="write the JSON report using UTF-8")
    parser.add_argument("--strict", action="store_true", help="treat warnings as a failing exit status")
    parser.add_argument("--require-local", action="store_true", help="require every registry path to exist in this checkout")
    parser.add_argument("--check-github", action="store_true", help="verify GitHub visibility and active default branches")
    parser.add_argument("--gh", type=Path, default=default_root / "tools" / "gh" / "bin" / "gh.exe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        results, findings = audit(args)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 2

    payload = {
        "projects": [asdict(item) for item in results],
        "findings": [asdict(item) for item in findings],
        "summary": {
            "projects": len(results),
            "errors": sum(item.level == "error" for item in findings),
            "warnings": sum(item.level == "warning" for item in findings),
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(results, findings)

    if payload["summary"]["errors"]:
        return 1
    if args.strict and payload["summary"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
