# Codex repo-scope skill entrypoints

Codex discovers repository skills from `.agents/skills`. The source-of-truth
reverse engineering skills remain under `D:\reverse_ENV\skill\`.

Each directory here is a thin entrypoint. When a skill is selected, read the
matching source `SKILL.md` under `D:\reverse_ENV\skill\<name>\` completely and
follow that file, including its referenced scripts, references, and templates.

Do not duplicate implementation details in this directory. Keep descriptions
short and update them only when routing semantics change.
