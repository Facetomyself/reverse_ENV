# Skills

逆向项目 skill 源目录。每个 skill 一个子目录，包含 `SKILL.md` + `scripts/` + `references/`。

Codex 的 repo-scope skill 发现入口在 `.agents/skills/`；Claude 的项目级发现入口在 `.claude/skills/`。两端都采用薄封装策略：入口只负责发现和路由，并要求读取对应的 `skill/<name>/SKILL.md` 作为唯一源。

## Skill 清单

| Skill | 目录 | 场景 |
|-------|------|------|
| `reverse-coordinator` | `reverse-coordinator/` | 元 skill — 分类→路由→编排→交付 |
| `apk-reverse` | `apk-reverse/` | Android APK 主链（多 marker 指纹 → 安全 decode → LDPlayer/Frida → panda whole-DEX → Kotlin/API 候选 → patch/16KB 重建 → native/Unity 分流），并支持 JAR/AAR/Vineflower 关键类对照 |
| `ida-reverse` | `ida-reverse/` | IDA Pro PE/ELF/DLL/SO 深度分析 |
| `wmpf-offset-adaptation` | `wmpf-offset-adaptation/` | WMPF `flue.dll` → `addresses.{version}.json` 偏移提取、静态复核与运行时验收分流 |
| `ruyi-reverse` | `ruyi-reverse/` | Web JS 逆向唯一入口 — 7 模块 × 两级深度编排 |
| `mcp-js-reverse-playbook` | `mcp-js-reverse-playbook/` | CDP 完整断点调试（无反检测需求时） |
| `native-reverse` | `native-reverse/` | Android Native .so 反检测/绕过（syscall→dump→IDA→patch→验证） |
| `radare2` | `radare2/` | 通用二进制 CLI 快速侦察 |
| `ldplayer-control` | `ldplayer-control/` | 雷电模拟器 RE 多实例模板、项目实例复制、代理、备份、恢复与清理 |
| `proxy-usage` | `proxy-usage/` | 代理统一管理（快代理 + Cliproxy） |
| `web-env-patcher` | `web-env-patcher/` | Web JS Node 补环境工程化闭环（隔离 runtime / cURL-HAR 检查 / Trace API 覆盖 / fixtures / TLS 门禁） |
| `protocol-recovery` | `protocol-recovery/` | Web 签名算法 → Python 采集器 |
| `article-archiver` | `article-archiver/` | 文章知识库归档（pending PDF/HTML/Markdown → 分类 Markdown + 索引） |
| `herosms-api` | `herosms-api/` | HeroSMS API：余额/目录/价格、号码购买、验证码轮询与激活生命周期 |
| `reverse-engineering` | `reverse-engineering/` | CTF 参考知识库（自动加载） |

## Skill 结构规范

每个 skill 目录结构：
```
skill/<name>/
  SKILL.md          # 必选 — skill 定义（含 YAML frontmatter）
  scripts/           # 可选 — PS/Bash/Python 脚本
  references/        # 可选 — 参考文档
  templates/         # 可选 — 产出模板
```

## 维护规则

- 新增 skill 后同步更新本 README + `CLAUDE.md` / `AGENTS.md` Skill 速查表 + 对应的 `.agents/skills/` / `.claude/skills/` 薄入口
- 脚本路径变更后同步更新 `CLAUDE.md` / `AGENTS.md` 脚本速查表 + `docs/脚本参考.md`
- 每个 SKILL.md 必须有 YAML frontmatter（name + description）
- `.agents/skills/` / `.claude/skills/` 不复制实现细节；若入口描述与源 skill 冲突，以 `skill/<name>/SKILL.md` 为准并修正入口
