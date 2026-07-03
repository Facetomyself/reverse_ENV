#!/usr/bin/env python3
"""Initialize a native reverse-engineering workspace without overwriting files."""

from __future__ import annotations

import argparse
from pathlib import Path


DIRS = [
    "artifacts/dumps",
    "artifacts/inp",
    "artifacts/maps",
    "docs",
    "logs",
    "scripts",
    "third_party",
    "so",
]

DOCS = {
    "docs/experiment_record.md": "# 实验记录\n\n",
    "docs/detection_summary.md": "# 检测点汇总\n\n",
    "docs/reproduction.md": "# 手工复现记录\n\n",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create standard directories and placeholder docs for native reverse analysis."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Workspace root. Defaults to current directory.",
    )
    parser.add_argument(
        "--with-docs",
        action="store_true",
        help="Create placeholder docs if they do not exist.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    print(f"[workspace] {root}")
    for rel in DIRS:
        path = root / rel
        path.mkdir(parents=True, exist_ok=True)
        print(f"[dir] {path}")

    if args.with_docs:
        for rel, content in DOCS.items():
            path = root / rel
            if path.exists():
                print(f"[keep] {path}")
                continue
            path.write_text(content, encoding="utf-8")
            print(f"[create] {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
