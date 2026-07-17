# Codex repo-scope skill entrypoints

Codex discovers repository skills from `.agents/skills`. The source-of-truth
reverse engineering skills remain under `D:\reverse_ENV\skill\`.

Each directory here is a thin entrypoint. When a skill is selected, read the
matching source `SKILL.md` under `D:\reverse_ENV\skill\<name>\` completely and
follow that file, including its referenced scripts, references, and templates.

Do not duplicate implementation details in this directory. Keep descriptions
short and update them only when routing semantics change.

Current project-specific additions include `web-env-patcher`, which must read `D:\reverse_ENV\skill\web-env-patcher\SKILL.md` and must not install or switch Node runtimes outside the project isolation rules; `herosms-api`, which must read `D:\reverse_ENV\skill\herosms-api\SKILL.md` and keep API credentials outside the repository; and `wmpf-offset-adaptation`, which must read `D:\reverse_ENV\skill\wmpf-offset-adaptation\SKILL.md`, keep binaries and outputs under the owning workspace, and route runtime WMPF work to the dedicated miniapp tooling.
