---
name: ingest-document
description: "Convert binary documents (PDF, DOCX, PPTX, XLSX, images) to clean markdown using Docling locally via scripts/ingest_document.py — preserves tables, headings, and reading order via a layout model. Source-type cleanup ingester — output is markdown saved to raw/, then handed back to the ingest orchestrator. Use when the source is any binary file. For HTML web pages use ingest-website instead."
license: MIT
compatibility: "Requires Python 3.10+ and docling (pip install docling). Optional: pymupdf4llm for the --fast path."
metadata:
  variant: shared
---

# Ingest Document Skill

Specialized ingester for binary documents — PDF, DOCX, PPTX, XLSX, images. Uses [Docling](https://github.com/docling-project/docling) (LF AI & Data Foundation, MIT-licensed) via a local Python script. Output is markdown saved to `raw/`, then handed back to the orchestrator (`ingest.md`) for the shared post-extraction flow.

For HTML web pages, use [[ingest-website]] instead.

## Tooling: scripts/ingest_document.py

Docling handles PDF, DOCX, PPTX, XLSX, HTML, and images through one CLI, runs locally (no cloud calls), and preserves tables, headings, and reading order via a layout model.

### Setup (one time)

```bash
pip install docling
# Optional, for the --fast path on plain-text PDFs:
pip install pymupdf4llm
```

> [!note] First run downloads ML models
> Docling's first invocation downloads layout/OCR models — expect a few hundred MB and a multi-second pause. Subsequent calls reuse the cached models.

Requires Python 3.10+.

### Usage

```bash
# Default — Docling, preserves tables and structure
python scripts/ingest_document.py <input> > raw/<YYYY-MM-DD>-<slug>.md

# Fast — pymupdf4llm, plain-text PDFs only, no ML deps
python scripts/ingest_document.py <input> --fast > raw/<YYYY-MM-DD>-<slug>.md
```

`<input>` can be a local path or an `http(s)://` URL pointing to a binary file (the script downloads to a temp file before processing).

The script emits markdown with frontmatter:
```yaml
---
source_path: <original-path-or-url>
source_format: pdf | docx | pptx | xlsx | image | html
parser: docling | pymupdf4llm
parsed_at: <YYYY-MM-DD>
---
```

## Operation

1. Receive a path or URL from the orchestrator.
2. Run `ingest_document.py`. Use `--fast` only if the user explicitly requests low-latency, plain-text-only extraction.
3. Save the output to `raw/<YYYY-MM-DD>-<slug>.md`.
4. Create the **companion page** for the original binary file in the appropriate `_assets/` folder (per CLAUDE.md's Asset Management section). The companion page's `asset_path` points to the binary; the markdown extraction at `raw/...md` is the readable form.
5. Hand back to the orchestrator's document-extraction flow (identify document type, extract per type — requirements doc, design spec, report, proposal — run scope check, contradiction check, wiki updates).

## When to use `--fast`

- Plain-text PDFs (research papers, articles, simple reports)
- Bulk ingest where latency matters more than table fidelity
- Environments where you can't install Docling's ML stack

When NOT to use `--fast`:
- Documents with tables, multi-column layouts, or figures with captions
- Spreadsheets (`.xlsx`) — pymupdf4llm doesn't handle them
- Image-only PDFs (scans) — needs Docling's OCR
- DOCX, PPTX — pymupdf4llm is PDF-only

## Failure modes

- **Cold-start latency (5-30s on first call).** Expected — Docling loads layout models. Amortizes across batch calls.
- **OCR garbage on low-quality scans.** Docling's OCR works on clean scans but struggles with hand-scanned, low-DPI, or rotated pages. Pre-process with `tesseract` or a dedicated OCR pipeline.
- **Multi-sheet XLSX flattens into one document.** Each sheet is extracted, but boundaries can be unclear — review the output and split into separate pages if useful.
- **Install size concerns.** Docling pulls PyTorch + transformers (~hundreds of MB). If that's a blocker, use `--fast` for PDFs and skip non-PDF formats — but you lose table structure and DOCX/PPTX/XLSX support.
- **Network needed only for first model download.** After that, everything is local.
