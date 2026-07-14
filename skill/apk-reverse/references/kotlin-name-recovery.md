# Kotlin 混淆类名恢复

## 证据等级

Kotlin metadata 能暴露部分原始名称，但不同字段的含义不一样，不能把
所有 descriptor 都当成当前类名。

| 来源 | 含义 | 置信度 | 输出 |
|---|---|---|---|
| `@DebugMetadata(c = "...")` | coroutine 对应的原始声明类 | high | `mapping.json` |
| jadx `/* renamed from: ... */` | jadx 从 DEX 证据恢复的原名 | high | `mapping.json` |
| `@Metadata.d2` 中的 `Lpkg/Type;` | metadata 引用到的类型，可能只是依赖 | low | `candidates.tsv` |

`Metadata.d2` 的第一个非 stdlib descriptor 不是可靠的“当前类”规则。
例如某个混淆类只引用 `com.example.Dependency` 时，盲取第一个 descriptor
会产生确定性的错误映射。因此脚本只把 d2 写入候选，不进入 authoritative
map，除非后续通过文件名、调用链、DebugMetadata 或其他证据独立关联。

## 运行

```powershell
& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/recover-kotlin-names.sh" `
  "D:/reverse_ENV/workspace/<project>/jadx/sources" `
  "D:/reverse_ENV/workspace/<project>/mapping"
```

产物：

| 文件 | 内容 |
|---|---|
| `mapping.json` | high-confidence `obf_fqn -> real_fqn`，供查询脚本使用 |
| `mapping.tsv` | 同一映射，附 source/confidence/file |
| `mapping-details.json` | 结构化证据详情 |
| `candidates.tsv` | low-confidence d2 引用候选 |
| `by_package/` | authoritative map 的包索引；每次运行前安全重建，避免旧结果污染 |

查询：

```powershell
& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh" `
  "D:/reverse_ENV/workspace/<project>/mapping" -o "a.b.C"

& "C:\Program Files\Git\bin\bash.exe" `
  "D:/reverse_ENV/skill/apk-reverse/scripts/lookup-name.sh" `
  "D:/reverse_ENV/workspace/<project>/mapping" --grep '"/api/' `
  "D:/reverse_ENV/workspace/<project>/jadx/sources"
```

`lookup-name.sh --grep` 由项目 Python 直接遍历 `.java` / `.kt`，不再解析
外部 grep 的 `path:line:text` 字符串，因此 Windows 盘符冒号不会截断路径。

## 解读规则

1. 只把 `mapping.json` 的结果当 high-confidence 类名证据。
2. `candidates.tsv` 必须与声明文件、继承关系、方法签名、调用链或运行时类名
   交叉验证后，才能提升为 finding。
3. 一个真实外层类可对应多个混淆 coroutine/lambda 类；这不等于方法名、字段名
   或所有 inner class 都已恢复。
4. 覆盖率高度依赖编译器、R8 配置、inline 程度和 jadx 输出。不得承诺固定
   百分比，也不得声称 Kotlin metadata 能恢复纯 Java 类。
5. `jadx --deobf` 生成的合成名称与原始名称恢复是两回事，可以并行使用，
   但报告中必须标明来源。

## 限制

- 不恢复大多数方法名和字段名。
- 纯 Java 类无 Kotlin metadata。
- top-level function、inline/value class、合成 `*Kt` 文件和跨文件 metadata
  仍需人工关联。
- R8 可重写、合并或移除结构；“文件中出现某个 FQN”不是声明归属证明。
