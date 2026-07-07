# Android Modules

LDPlayer App reverse-engineering runtime modules used by the template emulator instances.

These binaries are third-party runtime assets and are intentionally kept out of Git by the repository `.gitignore` rules for large/tooling assets. Keep this README as the tracked manifest and verify local files by SHA-256 before use.

## Assets

| File | Purpose | Source | SHA-256 |
|------|---------|--------|---------|
| `Kitsune-Mask-27.0.apk` | Magisk/Kitsune root manager for LDPlayer emulator templates | Local verified asset from `tools/Kitsune-Mask-27.0.apk` | `0ACD5919430C7583CB274ABB33CCEF64CA8E2537EF5D3ECF489F8D76734158D0` |
| `LSPosed-v1.9.2-7024-zygisk-release.zip` | Zygisk LSPosed framework module for `re-xposed` / `re-stealth` | `LSPosed/LSPosed` release v1.9.2 | `0EBC6BCB465D1C4B44B7220AB5F0252E6B4EB7FE43DA74650476D2798BB29622` |
| `JustTrustMe-v2.apk` | Classic Xposed SSL pinning bypass module | `Fuzion24/JustTrustMe` release v.2 | `1AC9A8274AD80980A0DC84C29795C537DC7E18A84569E36919530D5D55C7ED7B` |
| `JustTrustMe-v3.apk` | Newer JustTrustMe fork for compatibility testing | `SekiBetu/JustTrustMe` release v.3 | `51C7236E75B2BBA62547A3E38F5BDB4EA3BD8CF7939884292302E9BAF512034A` |
| `Hide-My-Applist-V3.6.1.apk` | Xposed app-list hiding module for `re-stealth` | `Dr-TSNG/Hide-My-Applist` release V3.6.1 | `AFC2A7938434A9414BCEDCC0D2C7C14E87BA79254E4A6B786389363E6708AC2E` |
| `Shamiko-v0.7.5-194-release.zip` | Verified Zygisk root hiding module for current `re-stealth` | `LSPosed/LSPosed.github.io` release shamiko-194 | `C28D1AC7C003429E5899F7987F2727670D5330C9FB461FA84E6BDCE79D730F94` |
| `Shamiko-v1.2.5-414-release.zip` | Archived candidate for future Magisk Canary templates | `LSPosed/LSPosed.github.io` release shamiko-414 | `308D31B2F52A80E49EB58F46BC4C764A6588A79E4B8D101B44860832023F88B4` |

## Template Usage

| Template | Modules |
|----------|---------|
| `re-base` | Kitsune/Magisk root, Frida server, mitmproxy CA |
| `re-xposed` | `re-base` + LSPosed + JustTrustMe |
| `re-stealth` | `re-xposed` + Hide My Applist + Shamiko v0.7.5 |

Keep LSPosed module scopes narrow. Enable JustTrustMe and Hide My Applist per target app instead of globally unless a test explicitly requires system-wide scope.

`Shamiko-v1.2.5-414-release.zip` was retained for future testing, but it requires Magisk Canary greater than 27005. The current Kitsune/Magisk 27001 LDPlayer templates use the verified `Shamiko-v0.7.5-194-release.zip`.
