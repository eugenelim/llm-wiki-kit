#!/usr/bin/env python3
"""
lint-assets.py — Detect assets without companion wiki pages.

For each non-markdown file found in any _assets/ directory under wiki_path,
checks whether a corresponding .md page exists anywhere in the vault.
Matching is by stem: image.png matches if any wiki page stem is "image".

Usage:
  python lint-assets.py /path/to/vault/wiki > log/asset-lint-2026-04-27.md

Output:
  Markdown report with ## Unclaimed Assets section.
"""

import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


def collect_assets(wiki_path):
    """Return list of (relpath, filepath) for all non-.md files in _assets/ dirs."""
    assets = []
    for root, dirs, files in os.walk(wiki_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if os.path.basename(root) != "_assets":
            continue
        for fname in files:
            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, wiki_path)
            assets.append((relpath, filepath))
    return assets


def collect_page_stems(wiki_path):
    """Return set of lowercase stems for all .md files in the vault."""
    stems = set()
    for root, dirs, files in os.walk(wiki_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.endswith(".md"):
                stems.add(Path(fname).stem.lower())
    return stems


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/vault/wiki", file=sys.stderr)
        sys.exit(1)

    wiki_path = sys.argv[1]
    if not os.path.isdir(wiki_path):
        print(f"Error: {wiki_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    assets = collect_assets(wiki_path)
    page_stems = collect_page_stems(wiki_path)

    unclaimed = []
    for relpath, filepath in sorted(assets):
        asset_stem = Path(filepath).stem.lower()
        if asset_stem not in page_stems:
            unclaimed.append(relpath)

    today = date.today().isoformat()
    lines = [
        "---",
        "type: lint-report",
        "provenance: extracted",
        f"created: {today}",
        f"modified: {today}",
        "tags: [lint, assets, health-check]",
        "---",
        "",
        "## Synopsis",
        "",
        f"Asset coverage report for `{wiki_path}`. "
        f"Scanned {len(assets)} asset(s); {len(unclaimed)} have no companion wiki page.",
        "",
        f"# Asset Lint Report — {today}",
        "",
        f"Scanned **{len(assets)}** asset file(s) across all `_assets/` directories.",
        "",
    ]

    if unclaimed:
        lines += [
            "## Unclaimed Assets",
            "",
            "These files have no `.md` page whose stem matches the asset filename. "
            "Either create a companion page or move the file to a referenced location.",
            "",
        ]
        for relpath in unclaimed:
            lines.append(f"- `{relpath}`")
        lines.append("")
    else:
        lines += ["## Unclaimed Assets", "", "None — every asset has a companion page.", ""]

    print("\n".join(lines))


if __name__ == "__main__":
    main()
