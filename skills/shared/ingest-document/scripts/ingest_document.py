#!/usr/bin/env python3
"""
ingest_document.py — Convert a document (PDF, DOCX, PPTX, XLSX, image) to markdown.

Default backend: Docling (preserves tables, headings, reading order; runs locally).
Fast backend (--fast, PDF only): pymupdf4llm (much faster, no ML deps; loses
table structure).

Setup:
  pip install docling
  pip install pymupdf4llm   # optional, only needed for --fast

Usage:
  python ingest_document.py path/to/file.pdf > out.md
  python ingest_document.py path/to/file.pdf --fast > out.md
  python ingest_document.py https://example.com/doc.pdf > out.md
"""

import argparse
import os
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


SUPPORTED_EXTS = {
    "pdf": "pdf",
    "docx": "docx",
    "doc": "doc",
    "pptx": "pptx",
    "ppt": "ppt",
    "xlsx": "xlsx",
    "xls": "xls",
    "html": "html",
    "htm": "html",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "tif": "image",
    "tiff": "image",
}


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    return SUPPORTED_EXTS.get(ext, "unknown")


def fetch_url(url: str) -> str:
    """Download a URL to a temp file and return the local path."""
    parsed = urlparse(url)
    base = os.path.basename(parsed.path) or "downloaded"
    suffix = os.path.splitext(base)[1]
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    print(f"Downloading {url} -> {tmp_path}", file=sys.stderr)
    urllib.request.urlretrieve(url, tmp_path)
    return tmp_path


def fast_pdf(path: str) -> str:
    """Fast path: pymupdf4llm. PDFs only. Loses table structure."""
    try:
        import pymupdf4llm
    except ImportError:
        sys.exit(
            "Error: --fast requires pymupdf4llm. Install with: pip install pymupdf4llm"
        )
    return pymupdf4llm.to_markdown(path)


def docling_convert(path: str) -> str:
    """Default path: Docling. Handles PDF, DOCX, PPTX, XLSX, HTML, images."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        sys.exit("Error: docling not installed. Run: pip install docling")
    converter = DocumentConverter()
    result = converter.convert(path)
    return result.document.export_to_markdown()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a document to markdown for wiki ingestion."
    )
    parser.add_argument("input", help="Local path or http(s):// URL to a document")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use pymupdf4llm for PDFs (faster, no ML deps; loses table structure)",
    )
    args = parser.parse_args()

    is_url = args.input.startswith("http://") or args.input.startswith("https://")
    local_path = fetch_url(args.input) if is_url else args.input

    if not os.path.exists(local_path):
        sys.exit(f"Error: {local_path} not found")

    fmt = detect_format(local_path)
    if fmt == "unknown":
        sys.exit(
            f"Error: unsupported file extension on {local_path}. "
            f"Supported: {', '.join(sorted(set(SUPPORTED_EXTS.values())))}"
        )

    if args.fast and fmt == "pdf":
        body = fast_pdf(local_path)
        parser_name = "pymupdf4llm"
    else:
        if args.fast:
            print(
                f"--fast not applicable to {fmt}; falling back to docling.",
                file=sys.stderr,
            )
        body = docling_convert(local_path)
        parser_name = "docling"

    print("---")
    print(f"source_path: {args.input}")
    print(f"source_format: {fmt}")
    print(f"parser: {parser_name}")
    print(f"parsed_at: {date.today().isoformat()}")
    print("---")
    print()
    print(body)


if __name__ == "__main__":
    main()
