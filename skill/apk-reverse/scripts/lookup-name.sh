#!/usr/bin/env bash
# lookup-name.sh — Query the mapping produced by recover-kotlin-names.sh.
#
# Modes:
#   lookup-name.sh <mapping-dir> <substring>      search by real-FQN substring
#   lookup-name.sh <mapping-dir> -o <obf>         resolve obf -> real
#   lookup-name.sh <mapping-dir> -p <pkg>         list a real package
#   lookup-name.sh <mapping-dir> --grep <regex> <sources-dir>
#       grep decompiled sources and annotate each hit with the real class name

set -euo pipefail

usage() {
  cat <<EOF
Usage: lookup-name.sh <mapping-dir> <query>
       lookup-name.sh <mapping-dir> -o <obf-fqn>
       lookup-name.sh <mapping-dir> -p <real-package-substring>
       lookup-name.sh <mapping-dir> --grep <regex> <sources-dir>

<mapping-dir> is the directory produced by recover-kotlin-names.sh
(must contain mapping.json).
EOF
  exit 0
}

[[ $# -lt 2 ]] && usage
DIR="$1"; shift
[[ ! -f "$DIR/mapping.json" ]] && { echo "no mapping.json in $DIR" >&2; exit 1; }

PYTHON_EXE="${PYTHON_EXE:-D:/reverse_ENV/.venv/Scripts/python.exe}"
[[ ! -x "$PYTHON_EXE" ]] && { echo "Python not found or not executable: $PYTHON_EXE (set PYTHON_EXE)" >&2; exit 1; }

"$PYTHON_EXE" - "$DIR" "$@" <<'PY'
import json, os, re, sys
DIR = sys.argv[1]
args = sys.argv[2:]
with open(os.path.join(DIR, "mapping.json"), "r", encoding="utf-8") as fh:
    MAP = json.load(fh)
REV = {}
for o, r in MAP.items():
    REV.setdefault(r, []).append(o)

def search(q):
    ql = q.lower()
    for r in sorted(REV):
        if ql in r.lower():
            print(r)
            for o in sorted(REV[r]):
                print(f"    {o}")

def by_obf(o):
    if o not in MAP:
        print(f"no mapping for {o}", file=sys.stderr); sys.exit(1)
    print(f"{o}  ->  {MAP[o]}")
    sibs = [s for s in REV[MAP[o]] if s != o]
    for s in sorted(sibs):
        print(f"    sibling: {s}")

def by_pkg(p):
    pl = p.lower()
    for r in sorted(REV):
        if pl in r.rsplit(".", 1)[0].lower():
            print(r)
            for o in sorted(REV[r]):
                print(f"    {o}")

def grep_annot(pattern, sources):
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        print(f"invalid regex: {exc}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isdir(sources):
        print(f"source directory not found: {sources}", file=sys.stderr)
        sys.exit(1)
    for root, _, files in os.walk(sources):
        for name in sorted(files):
            if not name.endswith((".java", ".kt")):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = list(fh)
            except OSError:
                continue
            rel = os.path.relpath(path, sources)
            obf = os.path.splitext(rel)[0].replace(os.sep, ".")
            suffix = f"  // {MAP[obf]}" if obf in MAP else ""
            for lineno, content in enumerate(lines, 1):
                if not compiled.search(content):
                    continue
                display = rel.replace(os.sep, "/")
                print(f"{display}:{lineno}:{content.rstrip()}{suffix}")

if args[0] == "-o" and len(args) == 2:
    by_obf(args[1])
elif args[0] == "-p" and len(args) == 2:
    by_pkg(args[1])
elif args[0] == "--grep" and len(args) == 3:
    grep_annot(args[1], args[2])
else:
    search(" ".join(args))
PY
