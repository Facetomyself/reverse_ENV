#!/usr/bin/env bash
# recover-kotlin-names.sh — Rebuild a (obfuscated -> real) class-name map
# from Kotlin metadata strings left in decompiled sources.
#
# R8 obfuscates JVM symbols but cannot strip the Kotlin metadata strings —
# the Kotlin runtime (reflection, coroutines) needs them at runtime. Two
# annotations carry the original FQN:
#
#   * @DebugMetadata(c = "<full.qualified.Name>", f = "<File.kt>", ...)
#     emitted for almost every `suspend` function (every coroutine
#     SuspendLambda).
#
#   * @Metadata(... d2 = {"...L<pkg/Class>;..."} ...) listing internal
#     class refs of the file.
#
# Coverage is sample-dependent. DebugMetadata and jadx rename comments are
# authoritative enough for the main map; Metadata.d2 references are emitted as
# low-confidence candidates because they may name a dependency instead of the
# declaring class.

set -euo pipefail

usage() {
  cat <<EOF
Usage: recover-kotlin-names.sh <decompiled-sources-dir> [output-dir]

Walks every *.java under <decompiled-sources-dir>, mines @DebugMetadata
and @Metadata annotations, and writes:

  <output-dir>/mapping.tsv   authoritative high-confidence mappings
  <output-dir>/mapping.json  same data as JSON  { obf_fqn: real_fqn, ... }
  <output-dir>/candidates.tsv low-confidence @Metadata.d2 candidates
  <output-dir>/by_package/   one file per real package, listing
                             real_fqn <TAB> obf_fqn <TAB> file

If [output-dir] is omitted, files are written next to the sources dir.
EOF
  exit 0
}

[[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]] && usage
SRC="$1"
OUT="${2:-$(dirname "$SRC")/mapping}"
[[ ! -d "$SRC" ]] && { echo "not a directory: $SRC" >&2; exit 1; }

PYTHON_EXE="${PYTHON_EXE:-D:/reverse_ENV/.venv/Scripts/python.exe}"
[[ ! -x "$PYTHON_EXE" ]] && { echo "Python not found or not executable: $PYTHON_EXE (set PYTHON_EXE)" >&2; exit 1; }

mkdir -p "$OUT"

"$PYTHON_EXE" - "$SRC" "$OUT" <<'PY'
import os, re, sys, json, shutil
from collections import defaultdict

SRC, OUT = sys.argv[1], sys.argv[2]

# @DebugMetadata(c = "com.foo.Bar$Inner$1", ...)
RE_DEBUG = re.compile(r'@DebugMetadata\([^)]*?c\s*=\s*"([^"]+)"', re.S)
# @Metadata(... d2 = { "...Lcom/foo/Bar;..." ...} )
RE_DTWO  = re.compile(r'@Metadata\([^)]*?d2\s*=\s*\{([^}]*)\}', re.S)
RE_LCLASS = re.compile(r'L([A-Za-z][\w/$]+);')
# jadx sometimes emits this comment for renamed classes
RE_RENAMED = re.compile(r'/\*\s*renamed from:\s*([\w.$]+)\s*\*/')

# Skip third-party / framework trees — their names are already real.
SKIP_PREFIXES = (
    "kotlin.", "kotlinx.", "androidx.", "android.", "java.", "javax.",
    "com.google.", "com.facebook.", "com.appsflyer.", "com.datadog.",
    "io.ktor.", "io.sentry.", "io.realm.", "okhttp3.", "okio.",
    "com.squareup.", "com.bumptech.", "com.airbnb.", "com.payu.",
    "com.storyteller.", "zendesk.", "io.intercom.", "com.microsoft.",
    "com.tinder.", "com.hotjar.", "com.amplitude.", "com.segment.",
    "com.mixpanel.", "com.onesignal.", "com.stripe.", "com.braintreepayments.",
    "retrofit2.", "dagger.", "javax.inject.", "org.jetbrains.",
)

mapping = {}
file_real = {}
details = {}
d2_candidates = []
counts = defaultdict(int)

by_package_dir = os.path.join(OUT, "by_package")
if os.path.isdir(by_package_dir):
    shutil.rmtree(by_package_dir)
os.makedirs(by_package_dir, exist_ok=True)

for dp, _, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".java"):
            continue
        path = os.path.join(dp, f)
        rel = os.path.relpath(path, SRC)
        obf = rel[:-5].replace(os.sep, ".")
        if obf.startswith(SKIP_PREFIXES):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace", newline=None) as fh:
                text = fh.read()
        except OSError:
            continue
        real = None
        source = None

        m = RE_DEBUG.search(text)
        if m:
            real = m.group(1).split("$", 1)[0]
            source = "DebugMetadata.c"
            counts["debug_meta"] += 1

        if not real:
            m = RE_RENAMED.search(text)
            if m:
                real = m.group(1)
                source = "jadx-renamed-comment"
                counts["renamed"] += 1

        if real:
            mapping[obf] = real
            file_real[obf] = path
            details[obf] = {
                "real_fqn": real,
                "source": source,
                "confidence": "high",
                "file": path,
            }

        # d2 contains referenced types, not necessarily the declaring class.
        # Preserve candidates as low-confidence evidence, but never insert them
        # into the authoritative map without an independent correlation.
        m = RE_DTWO.search(text)
        if m:
            seen = set()
            for lm in RE_LCLASS.finditer(m.group(1)):
                cand = lm.group(1).replace("/", ".").split("$", 1)[0]
                if "." not in cand or cand.startswith(("kotlin.", "java.", "android")) or cand in seen:
                    continue
                seen.add(cand)
                d2_candidates.append((obf, cand, path))
                counts["d2_candidates"] += 1

with open(os.path.join(OUT, "mapping.tsv"), "w", encoding="utf-8", newline="\n") as f:
    f.write("obf_fqn\treal_fqn\tsource\tconfidence\tfile\n")
    for k in sorted(mapping):
        item = details[k]
        f.write(f"{k}\t{mapping[k]}\t{item['source']}\t{item['confidence']}\t{file_real[k]}\n")

with open(os.path.join(OUT, "mapping.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(mapping, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

with open(os.path.join(OUT, "mapping-details.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(details, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

with open(os.path.join(OUT, "candidates.tsv"), "w", encoding="utf-8", newline="\n") as f:
    f.write("obf_fqn\tcandidate_real_fqn\tsource\tconfidence\tfile\n")
    for obf, cand, path in sorted(d2_candidates):
        f.write(f"{obf}\t{cand}\tMetadata.d2-reference\tlow\t{path}\n")

by_pkg = defaultdict(list)
for obf, real in mapping.items():
    pkg = real.rsplit(".", 1)[0] if "." in real else "(default)"
    by_pkg[pkg].append((real, obf, file_real[obf]))

for pkg, rows in by_pkg.items():
    safe = os.path.basename(pkg).replace(".", "_") or "default"
    with open(os.path.join(by_package_dir, f"{safe}.txt"), "w", encoding="utf-8", newline="\n") as f:
        for real, obf, p in sorted(rows):
            f.write(f"{real}\t{obf}\t{p}\n")

print(f"Recovered {len(mapping)} high-confidence class names")
for k, v in counts.items():
    print(f"  via {k}: {v}")
print(f"Real packages: {len(by_pkg)}")
print(f"Low-confidence d2 candidates: {len(d2_candidates)}")
print(f"Wrote {OUT}/mapping.tsv, mapping.json, mapping-details.json, candidates.tsv, by_package/")
PY
