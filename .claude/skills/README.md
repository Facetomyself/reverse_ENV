# Claude project skill entrypoints

Claude discovers project-scoped skills from `.claude/skills`. The source of truth remains under `D:\reverse_ENV\skill\`.

Each skill directory here is a thin entrypoint. It must route to the matching `D:\reverse_ENV\skill\<name>\SKILL.md` and must not copy scripts, references, templates, credentials, or workflow details.

If a Claude entrypoint conflicts with the source skill, the source skill wins and the entrypoint must be corrected.

Current incremental entries include `web-deobfuscation`, `web-env-patcher`, and `emil-design-eng`. Each must read its matching source skill; the Web skills preserve the project's zero-execution/evidence gates and isolated runtime boundary, while `emil-design-eng` preserves its six-skill routing and mandatory post-coding review gate.
