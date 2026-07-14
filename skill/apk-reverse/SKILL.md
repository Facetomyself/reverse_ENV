---
name: apk-reverse
description: Use for Android APK/XAPK/APKS reverse engineering in D:\reverse_ENV, including framework/protector fingerprinting, split-aware decode, manifest and Java/Kotlin/smali analysis, LDPlayer/Frida runtime work, validated whole-DEX dumping with panda, Kotlin name recovery, API candidate extraction, patch/rebuild/sign/install, and handoff of native .so, Unity IL2CPP, VMP, or Dex2C targets.
---

# APK Reverse

Use this skill for Android packages. Keep every target and artifact under
`D:\reverse_ENV\workspace\<project>\`; do not place APK/DEX/SO files directly in
the workspace root and do not commit raw targets, dumps, captures, credentials,
or full decompilation trees.

## Required preflight

1. Confirm `D:\reverse_ENV\article\INDEX.md` exists. For a new target, search it
   for the vendor, protector, framework, anti-debug, and protocol family.
2. Run `git status --short --branch` and preserve unrelated dirty work.
3. Copy the reverse-coordinator templates into the project when the four
   canonical artifacts do not exist:
   - `report.md`
   - `findings.json`
   - `triage.md`
   - `workspace.json`
4. Use `search-layer`, then `github-solution-research`, before installing or
   adopting an external unpacker. Do not auto-install APKiD, Flutter, Hermes,
   Unity, Frida, or unpacking dependencies.

## Core decision model

Framework, protector, and code-location markers are a set, not a mutually
exclusive enum. A package can contain Flutter assets, many DEX files, a native
signer, and a commercial shell at the same time.

Priority:

```text
protector / runtime-encrypted DEX
  -> stub + manifest triage
  -> wait for real-code loading
  -> whole-DEX dump when standard DEX exists in memory

no protector, or dump already reviewed
  -> choose business-code surface from evidence:
     Java/Kotlin | smali | native/JNI | Unity IL2CPP | Flutter AOT |
     React Native/Hermes | Cordova assets | Xamarin assemblies
```

Never stop Java/Kotlin triage solely because `libflutter.so`, `libhermes.so`, or
another framework runtime is present. Treat `fingerprint.sh` output as routing
evidence, not proof.

## Phase 0: fingerprint first

```powershell
& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/fingerprint.sh" `
  "D:/reverse_ENV/workspace/<project>/app.apk"
```

The script is split-aware and reports:

- framework markers, primary route, and confidence;
- protector markers for 360 Jiagu, Legu, SecNeo/Bangcle, Ijiami, Baidu,
  Naga, AppSealing, and DexGuard;
- DEX/ABI/native-library counts;
- HTTP, DI, serialization, obfuscation, and SDK hints;
- Unity IL2CPP, Flutter, React Native, Cordova/Capacitor, Xamarin, Kotlin,
  and Compose routing.

Built-in protector patterns are lightweight evidence. If project-local APKiD is
available, use it as additional Phase 0 evidence; absence is not an error.

### Route rules

| Evidence | Main route |
|---|---|
| Protector marker, stub Application, or almost no business classes | Runtime-load observation, then `dump-dex.ps1` |
| Standard whole DEX appears after load | panda whole-DEX baseline |
| Methods remain empty/stubbed after valid DEX export | Method extraction or sample-specific repair; panda is insufficient |
| `cdex` / CompactDex | Dedicated CDEX handling; panda is insufficient |
| VMP / Dex2C / core logic in `.so` | `native-reverse` |
| `libil2cpp.so` + `libunity.so` + `global-metadata.dat` | Unity IL2CPP route, then native/IDA handoff |
| Flutter `libapp.so` | Flutter AOT route plus minimal Android host review |
| Hermes/RN bundle | Hermes bundle route plus minimal Android host review |
| Cordova/Capacitor assets | Web assets plus bridge/manifest review |
| Readable DEX | Normal Java/Kotlin/smali route |

Read `references/packing-and-unpacking.md` whenever a protector, dump, method
extraction, CDEX, VMP, Dex2C, lazy loading, or anti-dump condition appears.

## Phase 1: controlled decode

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\decode.ps1" `
  -ApkPath "D:\reverse_ENV\workspace\<project>\app.apk" `
  -Name "<project>" -Clean
```

Use `-NoDexChecksum` only for a dumped DEX/APK whose checksum failure is already
recorded. The wrapper pins project-local jadx/apktool, preserves the source APK,
refuses to overwrite old generated directories without `-Clean`, and writes:

- `decode-summary.json` with SHA-256, tool exit codes, counts, and pipeline status;
- `manifest-summary.txt`;
- `jadx\` and `apktool\` outputs.

Interpretation:

- jadx non-zero with useful source output can be `partial`, not total failure;
- apktool output is the source of truth for manifest/resources/smali patching;
- `<50` Java files is only a packing heuristic, not proof;
- if both branches produce no useful artifact, the wrapper fails.

## Phase 2: choose the business-code surface

Inspect, in order:

1. `manifest-summary.txt`, Application, launcher, exported components, providers,
   processes, network-security flags, and native library loading.
2. `BuildConfig`, network clients, login/token/sign/encrypt/root/certificate/
   WebView/JNI paths.
3. `apktool\smali*`, resources, assets, and native libraries when jadx is partial.
4. Runtime behavior only after static evidence identifies a target or a loading
   boundary.

Handoff immediately when evidence says the main surface is elsewhere:

- `.so`, JNI, anti-Frida, anti-debug, syscall, anonymous executable mappings,
  VMP, or Dex2C -> `native-reverse`;
- pure static SO/ELF work -> `ida-reverse` or `radare2`;
- Unity IL2CPP -> read `references/unity-il2cpp-dump.md`, then hand off extracted
  native artifacts and metadata;
- Flutter/RN external tools are optional and may be absent. Prefer current
  blutter or Hermes decompilers only after version and repository evidence is
  checked; do not silently fall back to obsolete hbctool/Doldrums guidance.

## Phase 3: LDPlayer, Frida, and DEX export

Use `ldplayer-control` to create or resolve a project instance. Templates are
not target workspaces. Then initialize the explicit ADB device:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\init-ldplayer-re.ps1" `
  -DeviceSerial "<adb-serial>"
```

This validates ADB, root, ABI/native bridge, host/device Frida version, server
startup, and a real host-to-device Frida process-enumeration handshake.

### Whole-DEX baseline: panda on LDPlayer

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\dump-dex.ps1" `
  -Project "<project>" -Package "<package>" `
  -DeviceSerial "<adb-serial>" -Launch
```

The project binary is AArch64. The validated LDPlayer 9 route is an x86_64
Android 9 instance with Root and `libnb.so` native bridge. The wrapper enforces:

- connected explicit device and Root;
- AArch64 ABI/native-bridge compatibility;
- one unambiguous PID, or an explicit PID whose `/proc/<pid>/cmdline` belongs
  to the package;
- isolated output, timeout, SHA-256, DEX magic/header/class validation;
- unconditional best-effort `SIGCONT` because panda pauses the target;
- device evidence retention when the dump or validation is not clean.

`metadata.json` statuses:

| Status | Meaning |
|---|---|
| `complete-enough` | Every pulled file is structurally valid and the tool/pull exited cleanly; still not proof of complete unpacking |
| `partial` | At least one valid DEX exists, but another file or tool stage is incomplete |
| `invalid` | Files exist but none pass structural validation |
| `no-dex` | No DEX was pulled |

Local evidence as of 2026-07-14:

- ordinary app: 19 DEX / 21,134,420 bytes; largest DEX produced 2,884 Java files;
- 360 Jiagu VIP sample: 13 DEX / 73,247,772 bytes; best DEX produced 4,181
  Java files, including 4,073 `com.qidian` files, but with substantial load and
  decompile errors. Record this as **partial unpacking**, not universal support.

The LDPlayer route is therefore usable for standard whole-DEX recovery after
runtime loading, including some enterprise-shell samples. It does not claim
support for every shell, edition, Android version, method extraction, CDEX,
VMP, Dex2C, anti-dump, or lazy-loaded process.

### Frida observation and hooks

Use `frida-run.ps1` for stable device/target selection:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\frida-run.ps1" `
  -DeviceId "<frida-device-id>" -Spawn -Package "<package>" `
  -ScriptPath "D:\reverse_ENV\skill\apk-reverse\scripts\dex-dump.js"
```

`dex-dump.js` is observation-only. It traces `DexFile`, file-backed loaders,
`InMemoryDexClassLoader`, `Application.attach`, and registered DEX elements; it
does not read or write DEX bytes. Read `references/frida-best-practices.md`
before native hooks or loader-timing work.

## Phase 4: code recovery and API candidates

For obfuscated Kotlin, produce an evidence-aware map:

```powershell
& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/recover-kotlin-names.sh" `
  "D:/reverse_ENV/workspace/<project>/jadx/sources" `
  "D:/reverse_ENV/workspace/<project>/mapping"
```

- `mapping.json` contains high-confidence `DebugMetadata.c` or jadx rename
  evidence only;
- `candidates.tsv` contains low-confidence `Metadata.d2` references and must
  not be treated as authoritative class identity;
- coverage is sample-dependent; never promise a recovery percentage.

Use `lookup-name.sh` for queries or annotated regex search. Read
`references/kotlin-name-recovery.md` for interpretation.

For HTTP/API triage:

```powershell
& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/find-api-calls.sh" `
  "D:/reverse_ENV/workspace/<project>/jadx/sources" --all
```

This script prints grep-based candidates for Retrofit, OkHttp, Ktor, Apollo,
Volley, paths, URLs, auth, and signing signals. It does **not** automatically
produce a verified Tier 1/Tier 2 inventory. Promote candidates into findings
only after call-site, request-method, host/path, auth, and runtime evidence are
correlated. Read `references/api-extraction-patterns.md` and
`references/call-flow-analysis.md`.

## Phase 5: patch, rebuild, sign, install

Patch smali/resources only after the target branch is evidenced. Then:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "D:\reverse_ENV\skill\apk-reverse\scripts\rebuild-sign-install.ps1" `
  -ProjectDir "D:\reverse_ENV\workspace\<project>\apktool" `
  -Install -Reinstall -DeviceSerial "<adb-serial>" -Clean
```

The wrapper uses project-local apktool/JDK/build-tools, sanitizes output names,
keeps signing passwords out of child-process arguments, signs/verifies, and:

- uses build-tools 35 `zipalign -P 16` for APKs containing native libraries;
- verifies APK alignment after writing;
- inspects ELF `PT_LOAD` alignment with NDK `llvm-readelf`;
- reports 16 KB ELF risk but cannot repair a prebuilt misaligned `.so`;
- supports `-FailOn16KbRisk` when the pipeline must fail closed.

After install, verify launch, process survival, the modified branch, signature
impact, and network/native regressions. Rebuild success alone is not runtime
success.

## Delivery and review gate

Use the reverse-coordinator templates as the only schema. Do not invent a
second APK-specific `findings.json` shape.

Before final delivery, read `references/verification-checklist.md` and verify:

- every claim points to a file/line/class/method/address/runtime log;
- each finding has evidence, confidence, redaction, and rebuild status;
- `triage.md` separates blockers from untested assumptions;
- `workspace.json.artifacts` points to the actual three deliverables;
- tokens, cookies, credentials, private keys, and proxy secrets are masked or
  omitted;
- `complete-enough` DEX output is not called complete unpacking;
- L4 targets remain `triage-only` unless independently proven.

## References

| Reference | Read when |
|---|---|
| `references/packing-and-unpacking.md` | Protector, panda, method extraction, CDEX, VMP/Dex2C, anti-dump |
| `references/verification-checklist.md` | Before delivery or after any dump/rebuild |
| `references/frida-best-practices.md` | Java/native hooks, loader timing, Frida 17 APIs |
| `references/kotlin-name-recovery.md` | Reading authoritative mappings and low-confidence candidates |
| `references/api-extraction-patterns.md` | Promoting endpoint candidates into evidence |
| `references/call-flow-analysis.md` | Activity/ViewModel/Repository/request call-chain recovery |
| `references/unity-il2cpp-dump.md` | Unity IL2CPP metadata/native route |
| `references/third_party_hosts.txt` | URL third-party bucketing rules |

## Hard stops

- Do not skip fingerprinting and manifest triage to start blind hooks.
- Do not treat one framework marker as proof that DEX is irrelevant.
- Do not call `dex-dump.js` a dumper.
- Do not delete device dump evidence after invalid/no-DEX output.
- Do not use panda repeatedly against method extraction, CDEX, VMP, or Dex2C.
- Do not keep analyzing Java when evidence places the core in native code.
- Do not claim universal enterprise-shell support from one partial sample.
