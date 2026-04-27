#!/usr/bin/env python3
"""
lint-links.py — Detect broken wikilinks and orphan pages in an Obsidian vault.

Broken link  : a [[wikilink]] target that matches no .md file in the vault.
Orphan page  : a .md file that no other page links to (index.md excluded).

Single-pass: builds the full adjacency graph in memory, then reports.

Usage:
  python lint-links.py /path/to/vault/wiki > log/link-lint-2026-04-27.md

Output:
  Markdown report with ## Broken Wikilinks and ## Orphan Pages sections.
"""

import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*)?\]\]")


def collect_pages(wiki_path):
    """Return {relpath: filepath} for all .md files under wiki_path."""
    pages = {}
    for root, dirs, files in os.walk(wiki_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, wiki_path)
            pages[relpath] = filepath
    return pages


def build_name_index(pages):
    """Map lowercase stem -> list of relpaths (Obsidian shortest-path resolution)."""
    index = defaultdict(list)
    for relpath in pages:
        stem = Path(relpath).stem.lower()
        index[stem].append(relpath)
    return index


def extract_links(filepath):
    """Return list of raw wikilink targets from a file, code blocks excluded."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        return []
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"`[^`]+`", "", content)
    return [m.strip() for m in WIKILINK_RE.findall(content)]


def resolves(target, name_index):
    """Return True if target matches at least one known page."""
    stem = Path(target).stem.lower()
    return stem in name_index


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/vault/wiki", file=sys.stderr)
        sys.exit(1)

    wiki_path = sys.argv[1]
    if not os.path.isdir(wiki_path):
        print(f"Error: {wiki_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    pages = collect_pages(wiki_path)
    name_index = build_name_index(pages)

    broken = defaultdict(list)   # relpath -> [broken_target, ...]
    inbound = defaultdict(set)   # relpath -> {pages that link to it}

    for relpath, filepath in sorted(pages.items()):
        for target in extract_links(filepath):
            stem = Path(target).stem.lower()
            if resolves(target, name_index):
                for matched in name_index[stem]:
                    inbound[matched].add(relpath)
            else:
                broken[relpath].append(target)

    orphans = sorted(
        p for p in pages
        if p not in inbound and Path(p).stem.lower() != "index"
    )

    today = date.today().isoformat()
    broken_count = sum(len(v) for v in broken.values())

    lines = [
        "---",
        "type: lint-report",
        "provenance: extracted",
        f"created: {today}",
        f"modified: {today}",
        "tags: [lint, links, health-check]",
        "---",
        "",
        "## Synopsis",
        "",
        f"Link health report for `{wiki_path}`. "
        f"{broken_count} broken link(s) across {len(broken)} page(s); "
        f"{len(orphans)} orphan page(s).",
        "",
        f"# Link Lint Report — {today}",
        "",
        f"Scanned **{len(pages)}** pages.",
        "",
    ]

    if broken:
        lines += [
            "## Broken Wikilinks",
            "",
            "Link target matches no `.md` file in the vault.",
            "",
        ]
        for page in sorted(broken):
            for target in sorted(set(broken[page])):
                lines.append(f"- `{page}` → `[[{target}]]`")
        lines.append("")
    else:
        lines += ["## Broken Wikilinks", "", "None found.", ""]

    if orphans:
        lines += [
            "## Orphan Pages",
            "",
            "No other page links to these. Not necessarily a problem — "
            "surface for review.",
            "",
        ]
        for page in orphans:
            lines.append(f"- `{page}`")
        lines.append("")
    else:
        lines += ["## Orphan Pages", "", "None found.", ""]

    print("\n".join(lines))


if __name__ == "__main__":
    main()
