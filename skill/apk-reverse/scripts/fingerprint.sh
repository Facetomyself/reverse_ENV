#!/usr/bin/env bash
# fingerprint.sh — Triage an APK/XAPK before decompiling.
#
# Detects mobile framework (Flutter, React Native, Cordova/Capacitor,
# Xamarin, KMP/native), protector markers, HTTP-stack hints, obfuscation
# level, ABI/native libs, and notable third-party SDKs.
#
# Framework markers are not mutually exclusive: a protected or hybrid APK may
# contain Flutter/RN/Unity assets and still carry substantial Java/Kotlin
# business code. Run this before decode, then use the route recommendation as
# a triage decision instead of treating one marker as proof.

set -euo pipefail

usage() {
  cat <<EOF
Usage: fingerprint.sh <file.apk|file.xapk>

Prints a one-screen summary:
  * mobile framework (with rationale)
  * packer / protector markers
  * HTTP / DI / serialization stack hints
  * obfuscation indicator
  * DEX count and ABI coverage
  * native libraries (consolidated across split APKs)
  * notable third-party SDKs found in assets/
EOF
  exit 0
}

[[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]] && usage
INPUT="$1"
[[ ! -f "$INPUT" ]] && { echo "File not found: $INPUT" >&2; exit 1; }
PYTHON_EXE="${PYTHON_EXE:-D:/reverse_ENV/.venv/Scripts/python.exe}"
[[ ! -f "$PYTHON_EXE" ]] && { echo "Python not found: $PYTHON_EXE" >&2; exit 1; }

if ! unzip -tqq -- "$INPUT" >/dev/null 2>&1; then
  echo "Invalid or incomplete APK/XAPK archive: $INPUT" >&2
  exit 2
fi

TMP="$(mktemp -d -t apkfp.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# Resolve to a list of APKs (handle XAPK = ZIP of APKs)
APKS=()
case "${INPUT,,}" in
  *.xapk|*.apks|*.apkm)
    unzip -q -o "$INPUT" -d "$TMP/xapk"
    while IFS= read -r p; do APKS+=("$p"); done < <(find "$TMP/xapk" -maxdepth 2 -type f -name '*.apk')
    ;;
  *.apk)
    APKS=("$INPUT")
    ;;
  *)
    echo "Unsupported input: $INPUT" >&2; exit 1 ;;
esac

[[ ${#APKS[@]} -eq 0 ]] && { echo "No APK files found inside bundle: $INPUT" >&2; exit 2; }

for apk in "${APKS[@]}"; do
  if ! unzip -tqq -- "$apk" >/dev/null 2>&1; then
    echo "Invalid split APK inside bundle: $apk" >&2
    exit 2
  fi
done

# Aggregate ZIP listings from every APK in the bundle (split-aware view)
LISTING="$TMP/listing.txt"
: > "$LISTING"
for apk in "${APKS[@]}"; do
  unzip -l -- "$apk" 2>/dev/null | awk '{print $NF}' >> "$LISTING"
done

# Most class-level libs live inside classes*.dex, not as visible zip paths.
# Extract type descriptors with the project Python instead of relying on the
# host `strings` binary (Git Bash does not ship it by default).
DEX_STRINGS="$TMP/dex_strings.txt"
: > "$DEX_STRINGS"
for apk in "${APKS[@]}"; do
  for dex in $(unzip -Z1 -- "$apk" 2>/dev/null | grep -E '^classes[0-9]*\.dex$' || true); do
    unzip -p -- "$apk" "$dex" 2>/dev/null \
      | "$PYTHON_EXE" -c 'import re,sys; data=sys.stdin.buffer.read(); values=sorted(set(re.findall(rb"L[A-Za-z_$][A-Za-z0-9_$]*(?:/[A-Za-z0-9_$]+)+;", data))); sys.stdout.write("\n".join(v[1:-1].decode("ascii", "ignore") for v in values))' \
      >> "$DEX_STRINGS" || true
  done
done
sort -u "$DEX_STRINGS" -o "$DEX_STRINGS"

has() { grep -qE "$1" "$LISTING" || grep -qE "$1" "$DEX_STRINGS"; }

NATIVE=$(grep -E '^lib/[^/]+/[^/]+\.so$' "$LISTING" | sort -u || true)
NATIVE_COUNT=$(printf '%s\n' "$NATIVE" | grep -c . || true)
ABIS=$(grep -E '^lib/[^/]+/[^/]+\.so$' "$LISTING" | cut -d/ -f2 | sort -u | paste -sd, - || true)
DEX_COUNT=$(grep -Ec '^classes[0-9]*\.dex$' "$LISTING" || true)
APKID_BIN="D:/reverse_ENV/.venv/Scripts/apkid.exe"
if [[ -x "$APKID_BIN" ]]; then
  APKID_STATUS="available (run project-local APKiD for deeper signatures)"
else
  APKID_STATUS="not installed; built-in markers are lightweight evidence only"
fi

# ----------------------------------------------------------------------
# Framework detection (priority order — first match wins)
# ----------------------------------------------------------------------
FRAMEWORK="unknown"
RATIONALE=""

if has '^lib/[^/]+/libil2cpp\.so$' && has '^lib/[^/]+/libunity\.so$' && has '(^|/)global-metadata\.dat$'; then
  FRAMEWORK="Unity IL2CPP"
  RATIONALE="libil2cpp.so + libunity.so + global-metadata.dat"
elif has '^lib/[^/]+/libflutter\.so$'; then
  FRAMEWORK="Flutter"
  RATIONALE="lib/<abi>/libflutter.so present"
  has '^lib/[^/]+/libapp\.so$' && RATIONALE+="; libapp.so contains AOT-compiled Dart"
  if [[ "$DEX_COUNT" -ge 6 ]]; then
    FRAMEWORK="Mixed / Hybrid (Native Android + Flutter marker)"
    RATIONALE+="; $DEX_COUNT DEX files require parallel Java/Kotlin triage"
  fi
elif has '^lib/[^/]+/libhermes\.so$' || has '^assets/index\.android\.bundle$' || has '^lib/[^/]+/libreactnativejni\.so$'; then
  FRAMEWORK="React Native"
  reasons=()
  has '^lib/[^/]+/libhermes\.so$'             && reasons+=("libhermes.so")
  has '^lib/[^/]+/libreactnativejni\.so$'     && reasons+=("libreactnativejni.so")
  has '^assets/index\.android\.bundle$'       && reasons+=("assets/index.android.bundle")
  RATIONALE="${reasons[*]}"
elif has '^assets/www/index\.html$' || has '^assets/www/cordova\.js$' || has '^assets/public/index\.html$'; then
  FRAMEWORK="Cordova / Capacitor (WebView hybrid)"
  RATIONALE="assets/www/ or assets/public/ shell present"
elif has '^lib/[^/]+/libmonodroid\.so$' || has '^assemblies/'; then
  FRAMEWORK="Xamarin / .NET MAUI"
  RATIONALE="libmonodroid.so or assemblies/ present — code is in .NET DLLs"
elif has '^lib/[^/]+/libmaui\.so$'; then
  FRAMEWORK=".NET MAUI"
  RATIONALE="libmaui.so present"
elif has '^assets/flutter_assets/' && ! has '^lib/[^/]+/libflutter\.so$'; then
  FRAMEWORK="Flutter (code-only split?)"
  RATIONALE="flutter_assets/ but no libflutter.so in this APK — check splits"
else
  # Native: distinguish Compose vs classic Android by androidx.compose presence
  if has 'androidx[./]compose'; then
    FRAMEWORK="Native Android (Kotlin + Jetpack Compose)"
    RATIONALE="androidx.compose.* libraries detected"
  elif has '^META-INF/.*\.kotlin_module$'; then
    FRAMEWORK="Native Android (Kotlin)"
    RATIONALE="kotlin_module metadata present, no Compose markers"
  else
    FRAMEWORK="Native Android (Java/Kotlin)"
    RATIONALE="no cross-platform framework markers found"
  fi
fi

# ----------------------------------------------------------------------
# HTTP / DI / serialization stack hints
# ----------------------------------------------------------------------
http=()
has 'retrofit2'                && http+=("Retrofit")
has 'okhttp3'                  && http+=("OkHttp")
has 'io/ktor/'                 && http+=("Ktor")
has 'com/apollographql/'       && http+=("Apollo (GraphQL)")
has 'com/android/volley'       && http+=("Volley")

di=()
has 'dagger/hilt/'              && di+=("Hilt")
has '^META-INF/.*dagger.*'      && di+=("Dagger")
has 'org/koin/'                 && di+=("Koin")
has 'javax/inject/'             && [[ ${#di[@]} -eq 0 ]] && di+=("javax.inject")

ser=()
has 'kotlinx/serialization/'    && ser+=("kotlinx.serialization")
has 'com/google/gson/'          && ser+=("Gson")
has 'com/squareup/moshi/'       && ser+=("Moshi")
has 'com/fasterxml/jackson/'    && ser+=("Jackson")

# ----------------------------------------------------------------------
# Obfuscation indicator (R8/ProGuard) — count short root DEX packages
# ----------------------------------------------------------------------
# Note: pipefail is on, so guard greps that may legitimately return 0 matches.
short_dirs=$( { grep -oE '^[a-z]{1,2}/' "$DEX_STRINGS" || true; } | sort -u | wc -l | tr -d ' ')
if [[ "$short_dirs" -gt 30 ]]; then
  OBFUSCATION="HIGH ($short_dirs single/double-letter dirs at root)"
elif [[ "$short_dirs" -gt 10 ]]; then
  OBFUSCATION="MODERATE ($short_dirs short root dirs)"
else
  OBFUSCATION="LOW (no significant short-name namespace pollution)"
fi

# ----------------------------------------------------------------------
# Packer / protector markers (lightweight fallback when APKiD is absent)
# ----------------------------------------------------------------------
protectors=()
has 'lib/[^/]+/lib(jiagu|jgdtc)[^/]*\.so$|com/stub/StubApp|com/qihoo/util/StubApplication' \
  && protectors+=("360 Jiagu marker")
has 'lib/[^/]+/libshell[^/]*\.so$|com/tencent/StubShell/TxAppEntry' \
  && protectors+=("Tencent Legu marker")
has 'lib/[^/]+/(libDexHelper|libSecShell|libsecexe)[^/]*\.so$|com/secneo/apkwrapper/' \
  && protectors+=("Bangcle / SecNeo marker")
has 'lib/[^/]+/libexec[^/]*\.so$|com/shell/SuperApplication' \
  && protectors+=("Ijiami marker")
has 'lib/[^/]+/libbaiduprotect[^/]*\.so$|com/baidu/protect/' \
  && protectors+=("Baidu protector marker")
has 'lib/[^/]+/libnaga[^/]*\.so$' \
  && protectors+=("Naga marker")
has 'lib/[^/]+/libcovault[^/]*\.so$|^assets/sealed[^/]*\.dex$' \
  && protectors+=("AppSealing marker")
has '^assets/.*dexguard|com/guardsquare/dexguard/' \
  && protectors+=("DexGuard marker")

PRIMARY_ROUTE="native-static-first"
ROUTE_CONFIDENCE="medium"
if [[ ${#protectors[@]} -gt 0 ]]; then
  PRIMARY_ROUTE="protection-first: stub/manifest -> runtime load -> whole-DEX dump"
  ROUTE_CONFIDENCE="high (protector marker; edition still requires validation)"
elif [[ "$FRAMEWORK" == "Unity IL2CPP" ]]; then
  PRIMARY_ROUTE="unity-il2cpp: metadata + native analysis"
  ROUTE_CONFIDENCE="high"
elif [[ "$FRAMEWORK" == Flutter* ]]; then
  PRIMARY_ROUTE="flutter-aot plus minimal Android host decode"
  ROUTE_CONFIDENCE="medium"
elif [[ "$FRAMEWORK" == React* ]]; then
  PRIMARY_ROUTE="react-native bundle/Hermes plus minimal Android host decode"
  ROUTE_CONFIDENCE="high"
elif [[ "$FRAMEWORK" == Mixed* ]]; then
  PRIMARY_ROUTE="hybrid: decode DEX and inspect framework runtime in parallel"
  ROUTE_CONFIDENCE="high"
elif [[ "$FRAMEWORK" == Cordova* ]]; then
  PRIMARY_ROUTE="web assets plus Android bridge/manifest review"
  ROUTE_CONFIDENCE="high"
elif [[ "$FRAMEWORK" == Xamarin* || "$FRAMEWORK" == .NET* ]]; then
  PRIMARY_ROUTE="managed assemblies plus Android host review"
  ROUTE_CONFIDENCE="high"
fi

# ----------------------------------------------------------------------
# Notable third-party SDKs (assets-based markers)
# ----------------------------------------------------------------------
sdks=()
has '^assets/com/appsflyer/'        && sdks+=("AppsFlyer")
has 'datadog\.buildId|com/datadog/' && sdks+=("Datadog")
has 'io/sentry/'                    && sdks+=("Sentry")
has 'com/google/firebase/'          && sdks+=("Firebase")
has 'com/google/android/gms/'       && sdks+=("Google Play Services")
has 'com/facebook/'                 && sdks+=("Facebook SDK")
has 'com/payu/'                     && sdks+=("PayU")
has 'com/stripe/'                   && sdks+=("Stripe")
has 'com/braintreepayments/'        && sdks+=("Braintree")
has 'com/storyteller/'              && sdks+=("Storyteller")
has 'zendesk/'                      && sdks+=("Zendesk")
has 'com/intercom/'                 && sdks+=("Intercom")
has 'com/segment/analytics'         && sdks+=("Segment")
has 'com/amplitude/'                && sdks+=("Amplitude")
has 'com/mixpanel/'                 && sdks+=("Mixpanel")
has 'com/onesignal/'                && sdks+=("OneSignal")
has 'com/microsoft/clarity'         && sdks+=("Microsoft Clarity")
has 'com/hotjar/'                   && sdks+=("Hotjar")
has 'com/instabug/'                 && sdks+=("Instabug")

# BuildConfig.java is almost never obfuscated and often holds base URLs / flavor.
if grep -qE '(^|/)BuildConfig$' "$DEX_STRINGS"; then
  BUILDCONFIG="present (grep BuildConfig.java after decompile for base URLs / flavor)"
else
  BUILDCONFIG="not detected in DEX descriptors (still worth grepping after decompile)"
fi

# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
echo "=== APK Fingerprint: $(basename "$INPUT") ==="
echo
echo "Framework:        $FRAMEWORK"
echo "  Rationale:      $RATIONALE"
echo "Primary route:    $PRIMARY_ROUTE"
echo "  Confidence:     $ROUTE_CONFIDENCE"
echo "Protector:        ${protectors[*]:-none detected}"
echo "APKiD:            $APKID_STATUS"
echo "Obfuscation:      $OBFUSCATION"
echo "APK splits:       ${#APKS[@]}"
echo "DEX files:        $DEX_COUNT"
echo "ABIs:             ${ABIS:-none}"
echo
echo "HTTP stack:       ${http[*]:-none detected}"
echo "DI:               ${di[*]:-none detected}"
echo "Serialization:    ${ser[*]:-none detected}"
echo "BuildConfig:      $BUILDCONFIG"
echo

if [[ ${#protectors[@]} -gt 0 ]]; then
  echo "Protection route:"
  echo "  Treat marker matches as triage evidence, not proof of a specific edition."
  echo "  Decode manifest/stub first; if business classes are absent after runtime load,"
  echo "  use dump-dex.ps1 for whole-DEX packing. Method extraction/VMP/Dex2C must"
  echo "  route to specialized unpacking or native-reverse instead of blind re-dumps."
  echo
fi
echo "Third-party SDKs: ${sdks[*]:-none detected}"
echo
echo "Native libraries: $NATIVE_COUNT total across splits"
if [[ -n "$NATIVE" ]]; then
  echo "$NATIVE" | head -n 40 | sed 's/^/  /'
  if [[ "$NATIVE_COUNT" -gt 40 ]]; then
    echo "  ... $((NATIVE_COUNT - 40)) more (inspect the APK listing for the full set)"
  fi
else
  echo "  (none)"
fi
echo

# ----------------------------------------------------------------------
# Recommendation
# ----------------------------------------------------------------------
echo "Recommended next step:"
if [[ ${#protectors[@]} -gt 0 ]]; then
  echo "  Protection markers take priority. Decode the stub/manifest, start the app"
  echo "  until real classes are loaded, then use the validated wrapper:"
  echo "    powershell -File \"D:\\reverse_ENV\\skill\\apk-reverse\\scripts\\dump-dex.ps1\" -Project <project> -Package <package> -DeviceSerial <serial> -Launch"
  echo "  Treat output as partial until DEX structure, business classes, method bodies,"
  echo "  and decompiler errors are reviewed. VMP/Dex2C is a native-reverse route."
  echo
fi
case "$FRAMEWORK" in
  "Unity IL2CPP")
    echo "  Keep a minimal manifest/Java host review, then extract libil2cpp.so and"
    echo "  global-metadata.dat. Follow references/unity-il2cpp-dump.md; current"
    echo "  external dumpers are optional and may not be installed locally."
    ;;
  Mixed*)
    echo "  Do not stop at the Flutter marker. Run decode.ps1 and inspect the recovered"
    echo "  DEX alongside libapp.so/flutter_assets; choose the business-code side from evidence."
    ;;
  Flutter*)
    echo "  The main Dart logic usually lives in libapp.so (AOT), but still decode the"
    echo "  Android host/manifest. Prefer blutter for supported snapshots; use reFlutter"
    echo "  only when its version/patching constraints are acceptable. These tools may"
    echo "  need separate installation and sample-specific validation."
    echo "    - strings/rabin2 on libapp.so for endpoints & string constants"
    ;;
  React*)
    echo "  Inspect the Android host and the JS/Hermes bundle. Prefer hermes-decomp or"
    echo "  hermes-dec for analysis; use r2hermes only when bytecode modification is needed."
    echo "  These external tools are optional and are not assumed installed."
    echo "    - if JSC:    js-beautify the bundle and grep for 'fetch('/'axios'"
    ;;
  Cordova*)
    echo "  All app code is in assets/www/ (or assets/public/). Just unzip and"
    echo "  inspect the HTML/JS — no Java decompile needed."
    ;;
  Xamarin*|.NET*)
    echo "  App logic is in .NET DLLs (assemblies/). Use ILSpy or dotPeek;"
    echo "  jadx will only show the Mono host."
    ;;
  *)
    echo "  Proceed with Phase 1 decode:"
    echo "    powershell -File \"D:\\reverse_ENV\\skill\\apk-reverse\\scripts\\decode.ps1\" -ApkPath \"<file>\" -Clean"
    ;;
esac
