---
name: article-archiver
description: |
  Use when processing the D:\reverse_ENV\article Public submodule: converting PDFs/HTML/Markdown drafts from article\pending into clean Markdown articles, classifying them under article\*, updating article\INDEX.md, regenerating the detailed catalog, clearing processed pending inputs, and validating both repositories. Trigger on requests like "归档文章", "pending PDF 转 md", "吸收归档", "更新知识库索引", or "convert article PDFs to Markdown".
---

# Article Archiver

## Scope

Use this skill for knowledge-base intake under `D:\reverse_ENV\article\`, especially files staged in `D:\reverse_ENV\article\pending\`.

This skill handles:

- PDF/HTML/Markdown source triage
- PDF text extraction into Markdown drafts
- Manual cleanup into final article Markdown
- Classification into `article/<category>/`
- `article/INDEX.md` updates
- `article/CATALOG.md` / `article/catalog.json` regeneration and linting
- Pending queue cleanup after successful validation

Do not use this skill for workspace project deliverables (`report.md`, `findings.json`, `triage.md`). Those stay under `workspace/<project>/` unless they are later distilled into reusable article knowledge.

## Required Preflight

Before editing:

1. Run `git status --short --branch` in `D:\reverse_ENV\` and `git -C D:\reverse_ENV\article status --short --branch`.
2. List `D:\reverse_ENV\article\pending\`.
3. Confirm the submodule is initialized, then read `D:\reverse_ENV\article\INDEX.md`; use `CATALOG.md` when the task needs individual articles inside a compilation.
4. Read `D:\reverse_ENV\article\README.md`.
5. Check existing article naming/category patterns with `rg --files D:\reverse_ENV\article`.

If the user supplied a URL or asks to fetch online content, do not use WebFetch. Use `search-layer`, `github-solution-research`, or browser MCP routing according to the project policy.

## Category Selection

Prefer existing categories when accurate:

| Category | Use for |
|----------|---------|
| `protocols/` | Protocol frames, transport formats, handshake, encoding, WebSocket/session state |
| `anti-detection/` | WAF, fingerprinting, crawler/browser/device detection, behavior risk control |
| `signature-algorithms/` | Signatures, request headers, HMAC/MD5/AES/RSA key chains, signer SDKs |
| `packing-bypass/` | Packers, anti-debug, Frida/root/emulator bypass, unpacking |
| `native-analysis/` | SO/ELF/JNI/native runtime deep analysis |
| `mobile-app-reverse/` | Android/App reverse methodology, tooling, environment setup, generic workflow |
| `web-reverse/` | Web JS, Webpack/Vite bundles, browser runtime, frontend encryption |

Create a new category only when none of the above is honest. If adding a category, update:

- `article/README.md`
- `article/INDEX.md`
- `article/AGENTS.md`

## PDF Conversion

Use the bundled script for deterministic draft extraction:

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\article-archiver\scripts\pdf_to_markdown.py" `
  --input "D:\reverse_ENV\article\pending\<file>.pdf" `
  --output "D:\reverse_ENV\article\pending\<slug>.raw.md"
```

For all PDFs in pending:

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\skill\article-archiver\scripts\pdf_to_markdown.py" `
  --input "D:\reverse_ENV\article\pending" `
  --out-dir "D:\reverse_ENV\article\pending"
```

If `fitz` / PyMuPDF is missing, install it only into the project venv:

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" -m pip install pymupdf
```

The script creates a draft, not a final article. Always inspect and rewrite the Markdown before moving it into `article/<category>/`.

## Cleanup Rules

Final Markdown must remove source-platform noise:

- payment markers such as `已付费`
- author-like page chrome repeated by export tools
- `听全文`, `喜欢作者`, `留言`, `写留言`
- raw page markers
- isolated PDF line numbers
- duplicated navigation such as previous/next article links

Preserve technical content:

- commands as fenced code blocks
- tables as Markdown tables
- lifecycle diagrams as fenced `text` blocks
- exact identifiers, class names, method names, headers, algorithms, file paths, and tool versions

When extracting from a paid/public article source, archive a cleaned technical summary and structure. Do not copy irrelevant platform UI text into the knowledge base.

For existing bulk archives, `article/scripts/kb_catalog.py sanitize` is dry-run by default. Add `--apply` only after reviewing the exact files and markers. Preserve honest truncation notes such as "后续内容位于知识星球" when they explain that the archived article is incomplete.

## Article Template

Use `templates/article-template.md` as the starting shape for new articles when the source does not already have a strong structure.

Every final article should include:

- H1 title
- blockquote metadata: source, original date if known, archive date, category
- short technical summary
- searchable section headings
- tables/code fences where they improve retrieval

Use lowercase ASCII slugs for filenames, for example:

- `app-reverse-global-map.md`
- `app-reverse-environment-setup.md`
- `chromium-fingerprint-compilation.md`

## Index Update

After adding an article, update `D:\reverse_ENV\article\INDEX.md`:

1. Update the generated date to the current date.
2. Add the article to the correct category table.
3. Fill `来源项目`; use `— (PDF 归档)` for standalone imported PDFs.
4. Add searchable keywords in backticks.
5. Add a one-sentence summary with the reusable technical value.
6. Update tag sections under:
   - `密码学`
   - `协议`
   - `反检测/对抗`
   - `厂商/平台`
   - `工具/方法`

Do not leave a new article only in the category table. If it is not reachable by tags, the knowledge base search discipline weakens.

## Catalog and Lint

`INDEX.md` is the human-curated canonical/tag index. `CATALOG.md` and `catalog.json` are deterministic generated artifacts and must not be edited manually.

After changing article content or `INDEX.md`:

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" generate
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" check
& "D:\reverse_ENV\.venv\Scripts\python.exe" -m unittest discover -s "D:\reverse_ENV\article\tests" -v
```

The linter validates canonical index coverage, compilation child links, H1 and metadata presence, duplicate titles/content, local links, high-confidence tail noise, and generated-file drift.

## Pending Queue Handling

`article/pending/` is a work queue. After successful conversion, cleanup, index update, and validation:

- Remove processed source PDFs and raw drafts from `article/pending/` unless the user explicitly asks to preserve originals.
- If originals must be preserved, move them to an explicit archival location chosen for that task and document it in the final response.
- Never recursively delete `article/pending/`; remove only the exact processed absolute paths.

## Validation

Before finishing:

```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" generate
& "D:\reverse_ENV\.venv\Scripts\python.exe" "D:\reverse_ENV\article\scripts\kb_catalog.py" --root "D:\reverse_ENV\article" check
& "D:\reverse_ENV\.venv\Scripts\python.exe" -m unittest discover -s "D:\reverse_ENV\article\tests" -v
git -C "D:\reverse_ENV\article" diff --check
git -C "D:\reverse_ENV\article" status --short
git -C "D:\reverse_ENV" diff --check
git -C "D:\reverse_ENV" status --short
```

Also run these checks when applicable:

```powershell
rg -n "已付费|听全文|喜欢作者|写留言|\[PAGE|留言" "D:\reverse_ENV\article\<category>" "D:\reverse_ENV\article\INDEX.md"
```

Check Markdown links in `article/INDEX.md` resolve inside the submodule. A simple Python link checker is acceptable.

Preserve existing file encoding and line endings:

- Existing UTF-8 with BOM remains BOM.
- Existing CRLF files remain CRLF.
- New text files default to UTF-8 without BOM and LF.

## Reporting

Final response should list:

- created article files
- updated index/readme/catalog files
- pending queue result
- catalog article count and validation results
- any dependency installed into `D:\reverse_ENV\.venv`
