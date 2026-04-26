#!/usr/bin/env python3
"""
convergence-debt.py — Find raw sources that have no wiki page referencing them.

These represent "convergence debt": documents that were dropped into raw/
but never synthesized into the knowledge base.

Usage:
  python convergence-debt.py /path/to/vault

Output:
  Prints a markdown report to stdout.
"""

import os
import re
import sys
from datetime import date
from pathlib import Path


def collect_raw_files(vault_path):
    """Collect all files in raw/ directory."""
    raw_dir = os.path.join(vault_path, "raw")
    if not os.path.isdir(raw_dir):
        return []

    raw_files = []
    for root, dirs, files in os.walk(raw_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.startswith("."):
                continue
            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, vault_path)
            raw_files.append(relpath)

    return raw_files


def collect_wiki_references(vault_path):
    """Scan all wiki markdown files for references to raw/ files."""
    wiki_dir = os.path.join(vault_path, "wiki")
    research_dir = os.path.join(vault_path, "research")
    references = set()

    for scan_dir in [wiki_dir, research_dir]:
        if not os.path.isdir(scan_dir):
            continue

        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue

                filepath = os.path.join(root, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                except (UnicodeDecodeError, OSError):
                    continue

                # Match references in frontmatter sources field
                # e.g., - raw/project-x/document.pdf
                for match in re.finditer(r"raw/[\w\-./]+", content):
                    references.add(match.group(0))

                # Match wikilink references
                # e.g., [[raw/project-x/document.pdf]]
                for match in re.finditer(r"\[\[(raw/[^\]]+)\]\]", content):
                    references.add(match.group(1))

    return references


def find_debt(raw_files, references):
    """Find raw files not referenced by any wiki page."""
    debt = []
    for raw_file in raw_files:
        # Check if any reference matches this file
        # (partial match: reference might omit extension or use different path format)
        fname = os.path.basename(raw_file)
        referenced = False

        for ref in references:
            if raw_file in ref or ref in raw_file or fname in ref:
                referenced = True
                break

        if not referenced:
            debt.append(raw_file)

    return debt


def generate_report(debt, raw_files, vault_path):
    """Generate markdown report."""
    lines = [
        "---",
        "type: lint-report",
        "provenance: extracted",
        f"created: {date.today().isoformat()}",
        f"modified: {date.today().isoformat()}",
        "tags: [lint, convergence-debt, health-check]",
        "---",
        "",
        "## Synopsis",
        "",
        f"Convergence debt report: {len(debt)} of {len(raw_files)} raw sources "
        "have no wiki page referencing them.",
        "",
        f"# Convergence Debt Report — {date.today().isoformat()}",
        "",
        f"Scanned **{len(raw_files)}** files in `raw/`.",
        f"Found **{len(debt)}** files with no wiki page referencing them.",
        "",
    ]

    if not debt:
        lines.append("All raw sources are referenced by at least one wiki page.")
        return "\n".join(lines)

    # Group by subfolder
    by_folder = {}
    for filepath in debt:
        parts = filepath.split(os.sep)
        # raw/subfolder/... -> subfolder
        folder = parts[1] if len(parts) > 2 else "(root)"
        by_folder.setdefault(folder, []).append(filepath)

    lines.append("## Unreferenced Sources")
    lines.append("")

    for folder in sorted(by_folder.keys()):
        lines.append(f"### {folder}")
        lines.append("")
        for filepath in sorted(by_folder[folder]):
            # Get file modification time for age info
            try:
                mtime = os.path.getmtime(os.path.join(
                    vault_path, filepath))
                from datetime import datetime
                mod_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                lines.append(f"- `{filepath}` (modified: {mod_date})")
            except OSError:
                lines.append(f"- `{filepath}`")
        lines.append("")

    lines.append("## Recommended Actions")
    lines.append("")
    lines.append("For each unreferenced source, decide:")
    lines.append("1. **Ingest it** — ask Claude to read the source and create/update wiki pages")
    lines.append("2. **Defer it** — the source is intentionally unprocessed (add a note)")
    lines.append("3. **Archive it** — the source is no longer relevant")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/vault", file=sys.stderr)
        sys.exit(1)

    vault_path = sys.argv[1]
    if not os.path.isdir(vault_path):
        print(f"Error: {vault_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    raw_files = collect_raw_files(vault_path)
    references = collect_wiki_references(vault_path)
    debt = find_debt(raw_files, references)
    report = generate_report(debt, raw_files, vault_path)
    print(report)
