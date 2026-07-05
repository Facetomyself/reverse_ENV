# Skills

Claude Code skill 集合，每个 skill 一个子目录，包含 `SKILL.md` + `scripts/` + `references/`。

## Skill 清单

| Skill | 目录 | 场景 |
|-------|------|------|
| `reverse-coordinator` | `reverse-coordinator/` | 元 skill — 分类→路由→编排→交付 |
| `apk-reverse` | `apk-reverse/` | Android APK 逆向（jadx/apktool/frida + 指纹/Kotlin类名恢复/API提取） |
| `ida-reverse` | `ida-reverse/` | IDA Pro PE/ELF/DLL/SO 深度分析 |
| `ruyi-reverse` | `ruyi-reverse/` | Web JS 逆向唯一入口 — 7 模块 × 两级深度编排 |
| `mcp-js-reverse-playbook` | `mcp-js-reverse-playbook/` | CDP 完整断点调试（无反检测需求时） |
| `native-reverse` | `native-reverse/` | Android Native .so 反检测/绕过（syscall→dump→IDA→patch→验证） |
| `radare2` | `radare2/` | 通用二进制 CLI 快速侦察 |
| `ldplayer-control` | `ldplayer-control/` | 雷电模拟器 RE 实例管理 |
| `proxy-usage` | `proxy-usage/` | 代理统一管理（快代理 + Cliproxy） |
| `protocol-recovery` | `protocol-recovery/` | Web 签名算法 → Python 采集器 |
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

- 新增 skill 后同步更新本 README + `CLAUDE.md` Skill 速查表
- 脚本路径变更后同步更新 `CLAUDE.md` 脚本速查表 + `docs/脚本参考.md`
- 每个 SKILL.md 必须有 YAML frontmatter（name + description）
