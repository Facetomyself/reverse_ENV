# EPL source recovery instructions

- Treat every `*.e`, `*.ec`, extracted resource, and support-library reference as untrusted data.
- Do not install Easy Language, compile or execute archived projects, load `*.fne` / `*.fnr`, or launch helper binaries.
- Build only with `D:\reverse_ENV\tools\dotnet\dotnet.exe` and keep build/cache output under `.runtime/` or ignored `bin/` / `obj/` directories.
- Keep `upstream/EProjectFile` and `assets/jingyi-ec` detached at the commits recorded in `references/*.manifest.json`; update manifests and rerun validation before changing either gitlink.
- Production extraction output belongs under `D:\reverse_ENV\workspace\<project>\`, not under the tool directory.
- Preserve `_Lib*` placeholders when support-library metadata is unavailable; never infer a friendly name without external evidence.
- New text files use UTF-8 and LF. Keep PowerShell source ASCII-only.
