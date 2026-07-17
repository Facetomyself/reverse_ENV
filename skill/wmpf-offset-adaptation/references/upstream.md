# 上游来源与更新规则

## 来源

- Repository: `https://github.com/GhostMice/wmpf-offset-adaptation-skill`
- Imported commit: `4d1d59cb0a0f4eec8a02c4fffda293db54039a70`
- Commit date: `2026-07-02T09:56:48Z`
- Imported implementation: `wmpf-offset-adaptation/scripts/extract_wmpf_offsets.py`

上游仓库没有声明 license。本目录保留来源与 commit，不改写来源归属。

## 项目适配

- 上游可执行 Skill 位于仓库内层 `wmpf-offset-adaptation/`；本仓要求 `skill/<name>/SKILL.md` 直接作为唯一源，因此采用固定 commit vendor，而不是把多一层目录的上游仓库直接作为 submodule。
- 上游脚本保留核心 `.pdata` / Capstone 提取逻辑，仅把缺失依赖提示改为项目 venv 命令。
- 项目运行约束、workspace 落点、IDA 升级路径和运行时验收门写入 `SKILL.md`。
- 上游 `reference.md` 与根 README 作为只读快照保存在 `references/upstream-*`；执行时以本目录 `SKILL.md` 和 `references/algorithm.md` 为准。
- Codex 项目入口：`D:\reverse_ENV\.agents\skills\wmpf-offset-adaptation\SKILL.md`
- Claude 项目入口：`D:\reverse_ENV\.claude\skills\wmpf-offset-adaptation\SKILL.md`

## 更新规则

1. 先用 `gh repo view` / `gh api` 核对新 commit、文件树和差异。
2. 只更新上游脚本与只读快照，不覆盖本项目 `SKILL.md`、`references/algorithm.md` 和双端薄入口。
3. 重新应用项目 venv 的缺失依赖提示。
4. 更新本文件的 imported commit，并运行 Python 编译、`--help`、frontmatter、`git diff --check` 和 workspace governance 验证。
