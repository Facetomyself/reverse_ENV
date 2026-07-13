# 逆向知识库索引（兼容入口）

知识库已拆分为独立 Private 仓库，并以 `article/` submodule 接入本仓库。

- Canonical index：[`article/INDEX.md`](../article/INDEX.md)
- GitHub：`https://github.com/Facetomyself/reverse-engineering-knowledge-base`

若本地尚未初始化知识库：

```powershell
git submodule update --init article
```

新增、移动或归档文章时只编辑 `article/INDEX.md`，不要在本兼容入口复制维护第二份索引。
