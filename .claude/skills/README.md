# Claude project skill entrypoints

Claude discovers project-scoped skills from `.claude/skills`. The source of truth remains under `D:\reverse_ENV\skill\`.

Each skill directory here is a thin entrypoint. It must route to the matching `D:\reverse_ENV\skill\<name>\SKILL.md` and must not copy scripts, references, templates, credentials, or workflow details.

If a Claude entrypoint conflicts with the source skill, the source skill wins and the entrypoint must be corrected.
