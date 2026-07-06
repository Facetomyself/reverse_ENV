# Codex project hooks for reverse_ENV

This directory contains project-local Codex configuration and lifecycle hooks. It intentionally does not mirror `.claude/settings.json` one-to-one because Claude and Codex use different file formats and discovery rules.

## Layering model

- Claude side: global and project layers both commonly hold MCP, skills, and hooks. The current project `.claude/settings.json` is Claude-specific and should not be copied verbatim into Codex.
- Codex side: project MCP belongs in `.codex/config.toml`; project lifecycle policy belongs in `.codex/hooks.json`; durable repo instructions stay in `AGENTS.md`.
- Codex repo-scope skills are discovered from `.agents/skills`; this repo keeps thin entrypoints there and preserves the source-of-truth workflows under `D:\reverse_ENV\skill\`.
- Project-local Codex config and hooks load only after the project `.codex` layer is trusted. If Codex prompts through `/hooks`, review and trust these commands before expecting them to run.
- reverse_ENV MCP servers are project-scoped here: `ida-multi-mcp` and `ruyi-mcp` are enabled in `.codex/config.toml`. GUI/SSE/client-bound MCPs remain disabled/commented until their prerequisites are active.
- User-level `C:\Users\mengma\.codex\config.toml` should keep personal defaults, providers, features, plugins, and project trust only. Do not put `D:\reverse_ENV`-specific MCP paths there.
- `search-layer` is a Codex skill in the user skill layer, not a project `.mcp.json` server and not the same thing as Claude's global MCP tier.

## Hooks

- `config.toml`: project-scoped Codex MCP configuration for reverse_ENV.
- `hooks/session-preflight.ps1`: non-blocking session reminder and lightweight path checks.
- `hooks/pre-tool-policy.ps1`: conservative shell-command guard for destructive Git and filesystem operations.
- `../.agents/skills/`: repo-scope Codex skill discovery entrypoints that route to `D:\reverse_ENV\skill\`.

The config and hooks are deliberately project-local. Do not move these checks or reverse_ENV MCP servers into global Codex config unless the policy or tools should apply to every project on the machine.
