# 逆向知识库索引（兼容入口）

知识库已拆分为独立 Public 仓库，并以 `article/` submodule 接入本仓库。

- Canonical index：[`article/INDEX.md`](../article/INDEX.md)
- 逐篇详细目录：[`article/CATALOG.md`](../article/CATALOG.md)
- 机器可读目录：[`article/catalog.json`](../article/catalog.json)
- GitHub：`https://github.com/Facetomyself/reverse-engineering-knowledge-base`

若本地尚未初始化知识库：

```powershell
git submodule update --init article
```

检索时先用 `article/INDEX.md` 找 canonical 入口和技术标签；需要合集子文章时再用 `article/CATALOG.md`。新增、移动或归档文章时只编辑正文与 `article/INDEX.md`，不要手工修改生成文件或在本兼容入口复制维护第二份索引。

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" generate
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" check
```
