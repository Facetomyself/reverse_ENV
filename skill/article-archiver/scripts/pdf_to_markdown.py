#!/usr/bin/env python
"""Extract text from PDF files into Markdown drafts for article archiving."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


NOISE_PATTERNS = [
    re.compile(r"^原创$"),
    re.compile(r"^听全文$"),
    re.compile(r"^喜欢作者$"),
    re.compile(r"^\d+\s*人付费$"),
    re.compile(r"^留言$"),
    re.compile(r"^写留言$"),
    re.compile(r"^(上一篇|下一篇)[·\s].*$"),
]


def import_fitz():
    try:
        import fitz  # type: ignore
    except ImportError:
        print(
            "PyMuPDF is required. Install it in the project venv:\n"
            r'  D:\reverse_ENV\.venv\Scripts\python.exe -m pip install pymupdf',
            file=sys.stderr,
        )
        raise SystemExit(2)
    return fitz


def slugify(name: str) -> str:
    lowered = name.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "article"


def clean_line(line: str, strip_noise: bool) -> str | None:
    line = line.replace("\u00a0", " ").replace("\u3000", " ").strip()
    line = re.sub(r"\s+", " ", line)
    if not line:
        return ""
    if line.isdigit():
        return None
    if strip_noise:
        line = line.replace("已付费", "")
        if any(pattern.match(line) for pattern in NOISE_PATTERNS):
            return None
    return line


def extract_pdf(pdf_path: Path, strip_noise: bool) -> tuple[str, list[str]]:
    fitz = import_fitz()
    doc = fitz.open(pdf_path)
    title = pdf_path.stem
    lines: list[str] = []

    for page_number, page in enumerate(doc, start=1):
        page_text = page.get_text("text")
        page_lines: list[str] = []
        for raw_line in page_text.splitlines():
            cleaned = clean_line(raw_line, strip_noise)
            if cleaned is None:
                continue
            page_lines.append(cleaned)
        while page_lines and page_lines[-1] == "":
            page_lines.pop()
        if page_lines:
            lines.append(f"<!-- page: {page_number} -->")
            lines.extend(page_lines)
            lines.append("")

    for line in lines:
        if line and not line.startswith("<!-- page:"):
            title = line.strip("# ")
            break

    return title, lines


def write_markdown(pdf_path: Path, output_path: Path, title: str, lines: list[str]) -> None:
    body = "\n".join(lines).strip() + "\n"
    markdown = (
        f"# {title}\n\n"
        f"> 来源: PDF 草稿 `{pdf_path.name}`\n"
        f"> 状态: raw extraction; review, clean, classify, and index before archiving.\n\n"
        f"{body}"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8", newline="\n")


def iter_inputs(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(input_path.glob("*.pdf"))
    return [input_path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="PDF file or directory containing PDFs.")
    parser.add_argument("--output", help="Output Markdown file. Only valid for one input PDF.")
    parser.add_argument("--out-dir", help="Output directory for directory or multi-file conversion.")
    parser.add_argument("--keep-noise", action="store_true", help="Keep common article platform chrome/noise lines.")
    args = parser.parse_args(argv)

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Input does not exist: {input_path}", file=sys.stderr)
        return 1

    pdfs = iter_inputs(input_path)
    if not pdfs:
        print(f"No PDF files found: {input_path}", file=sys.stderr)
        return 1
    if args.output and len(pdfs) != 1:
        print("--output can only be used with a single PDF input.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).resolve() if args.out_dir else None
    for pdf_path in pdfs:
        if pdf_path.suffix.lower() != ".pdf":
            print(f"Skipping non-PDF input: {pdf_path}", file=sys.stderr)
            continue
        title, lines = extract_pdf(pdf_path, strip_noise=not args.keep_noise)
        if args.output:
            output_path = Path(args.output).resolve()
        else:
            target_dir = out_dir or pdf_path.parent
            output_path = target_dir / f"{slugify(pdf_path.stem)}.raw.md"
        write_markdown(pdf_path, output_path, title, lines)
        print(f"wrote {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
