#!/usr/bin/env python3
"""
tag-lint.py — Scan an Obsidian vault for tag hygiene issues.

Detects:
  - Tag synonyms (similar tags that likely mean the same thing)
  - Underused tags (only on 1 page)
  - Overused tags (on >50% of pages)
  - Inline tags not in frontmatter (inconsistency)

Usage:
  python tag-lint.py /path/to/vault/wiki

Output:
  Prints a markdown report to stdout. Pipe to a file:
  python tag-lint.py /path/to/vault/wiki > /path/to/vault/log/tag-lint-2026-04-25.md
"""

import os
import re
import sys
import yaml
from collections import defaultdict
from itertools import combinations
from datetime import date


def extract_frontmatter(filepath):
    """Extract YAML frontmatter from a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        return None, ""

    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    try:
        fm = yaml.safe_load(content[3:end])
        body = content[end + 3 :]
        return fm if isinstance(fm, dict) else None, body
    except yaml.YAMLError:
        return None, content


def extract_inline_tags(body):
    """Extract #tags from markdown body text (not in code blocks)."""
    # Remove code blocks first
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body = re.sub(r"`[^`]+`", "", body)
    # Match #tags (kebab-case, may include slashes for nested)
    return set(re.findall(r"(?<!\w)#([\w][\w\-/]*)", body))


def normalize_tag(tag):
    """Normalize a tag for comparison."""
    return tag.lower().strip().replace("_", "-")


def levenshtein(s1, s2):
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def find_synonyms(tags, threshold=2):
    """Find tag pairs that are likely synonyms based on edit distance and prefix."""
    synonyms = []
    tag_list = sorted(tags.keys())

    for t1, t2 in combinations(tag_list, 2):
        n1, n2 = normalize_tag(t1), normalize_tag(t2)

        # Skip if identical after normalization
        if n1 == n2:
            synonyms.append((t1, t2, "identical-after-normalize"))
            continue

        # Levenshtein distance for short tags
        if len(n1) > 3 and len(n2) > 3:
            dist = levenshtein(n1, n2)
            max_len = max(len(n1), len(n2))
            if dist <= threshold and dist / max_len < 0.3:
                synonyms.append((t1, t2, f"edit-distance-{dist}"))

    return synonyms


def scan_vault(vault_path):
    """Scan all markdown files in the vault."""
    tag_usage = defaultdict(set)  # tag -> set of filepaths
    pages_with_frontmatter = 0
    pages_without_frontmatter = []
    pages_missing_provenance = []
    pages_missing_synopsis = []
    inline_only_tags = defaultdict(set)  # tag -> files where it's inline but not in fm
    total_pages = 0

    for root, dirs, files in os.walk(vault_path):
        # Skip hidden directories and _assets
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for fname in files:
            if not fname.endswith(".md"):
                continue

            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, vault_path)
            total_pages += 1

            fm, body = extract_frontmatter(filepath)

            if fm:
                pages_with_frontmatter += 1

                # Check provenance
                if "provenance" not in fm:
                    pages_missing_provenance.append(relpath)

                # Collect frontmatter tags
                fm_tags = set()
                if "tags" in fm and isinstance(fm["tags"], list):
                    for tag in fm["tags"]:
                        tag_str = str(tag)
                        fm_tags.add(normalize_tag(tag_str))
                        tag_usage[normalize_tag(tag_str)].add(relpath)
            else:
                pages_without_frontmatter.append(relpath)

            # Check for synopsis
            if "## Synopsis" not in body and "## synopsis" not in body.lower():
                pages_missing_synopsis.append(relpath)

            # Collect inline tags
            inline_tags = extract_inline_tags(body)
            for tag in inline_tags:
                normalized = normalize_tag(tag)
                tag_usage[normalized].add(relpath)
                if fm and normalized not in (
                    normalize_tag(str(t))
                    for t in (fm.get("tags") or [])
                ):
                    inline_only_tags[normalized].add(relpath)

    return {
        "tag_usage": dict(tag_usage),
        "total_pages": total_pages,
        "pages_with_frontmatter": pages_with_frontmatter,
        "pages_without_frontmatter": pages_without_frontmatter,
        "pages_missing_provenance": pages_missing_provenance,
        "pages_missing_synopsis": pages_missing_synopsis,
        "inline_only_tags": dict(inline_only_tags),
    }


def generate_report(results, vault_path):
    """Generate a markdown lint report."""
    tag_usage = results["tag_usage"]
    total = results["total_pages"]

    lines = [
        "---",
        "type: lint-report",
        "provenance: synthesized",
        f"created: {date.today().isoformat()}",
        f"modified: {date.today().isoformat()}",
        "tags: [lint, tags, health-check]",
        "---",
        "",
        "## Synopsis",
        "",
        f"Tag hygiene report for vault at `{vault_path}`. "
        f"Scanned {total} pages, found {len(tag_usage)} unique tags.",
        "",
        f"# Tag Lint Report — {date.today().isoformat()}",
        "",
        f"Scanned **{total}** markdown pages in `{vault_path}`.",
        "",
    ]

    # Synonym detection
    synonyms = find_synonyms(tag_usage)
    if synonyms:
        lines.append("## Possible Synonyms")
        lines.append("")
        lines.append("These tag pairs may refer to the same concept. "
                      "Consider merging to the canonical form.")
        lines.append("")
        lines.append("| Tag A | Tag B | Reason | Pages (A) | Pages (B) |")
        lines.append("|---|---|---|---|---|")
        for t1, t2, reason in synonyms:
            c1 = len(tag_usage.get(t1, set()))
            c2 = len(tag_usage.get(t2, set()))
            lines.append(f"| `#{t1}` | `#{t2}` | {reason} | {c1} | {c2} |")
        lines.append("")

    # Underused tags
    underused = {t: pages for t, pages in tag_usage.items() if len(pages) == 1}
    if underused:
        lines.append("## Underused Tags (1 page only)")
        lines.append("")
        lines.append("Consider whether these are too specific or should be removed.")
        lines.append("")
        for tag in sorted(underused.keys()):
            page = list(underused[tag])[0]
            lines.append(f"- `#{tag}` — only on `{page}`")
        lines.append("")

    # Overused tags
    threshold = max(total * 0.5, 5)
    overused = {t: pages for t, pages in tag_usage.items() if len(pages) > threshold}
    if overused:
        lines.append("## Overused Tags (>50% of pages)")
        lines.append("")
        lines.append("These tags are so broad they don't aid navigation.")
        lines.append("")
        for tag in sorted(overused.keys(), key=lambda t: -len(overused[t])):
            lines.append(f"- `#{tag}` — on {len(overused[tag])} of {total} pages")
        lines.append("")

    # Inline-only tags
    if results["inline_only_tags"]:
        lines.append("## Inline Tags Missing from Frontmatter")
        lines.append("")
        lines.append("These tags appear in the body text but not in the "
                      "`tags:` frontmatter field.")
        lines.append("")
        for tag in sorted(results["inline_only_tags"].keys()):
            pages = results["inline_only_tags"][tag]
            lines.append(f"- `#{tag}` — in {len(pages)} page(s): "
                         + ", ".join(f"`{p}`" for p in sorted(pages)[:3]))
        lines.append("")

    # Missing provenance
    if results["pages_missing_provenance"]:
        lines.append("## Missing Provenance Field")
        lines.append("")
        lines.append(f"{len(results['pages_missing_provenance'])} pages "
                      "are missing the `provenance` frontmatter field.")
        lines.append("")
        for p in sorted(results["pages_missing_provenance"])[:20]:
            lines.append(f"- `{p}`")
        if len(results["pages_missing_provenance"]) > 20:
            lines.append(f"- ... and {len(results['pages_missing_provenance']) - 20} more")
        lines.append("")

    # Missing synopsis
    if results["pages_missing_synopsis"]:
        lines.append("## Missing Synopsis Section")
        lines.append("")
        lines.append(f"{len(results['pages_missing_synopsis'])} pages "
                      "are missing the `## Synopsis` section.")
        lines.append("")
        for p in sorted(results["pages_missing_synopsis"])[:20]:
            lines.append(f"- `{p}`")
        if len(results["pages_missing_synopsis"]) > 20:
            lines.append(f"- ... and {len(results['pages_missing_synopsis']) - 20} more")
        lines.append("")

    # Tag frequency table
    lines.append("## All Tags by Frequency")
    lines.append("")
    lines.append("| Tag | Pages |")
    lines.append("|---|---|")
    for tag in sorted(tag_usage.keys(), key=lambda t: -len(tag_usage[t])):
        lines.append(f"| `#{tag}` | {len(tag_usage[tag])} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/vault/wiki", file=sys.stderr)
        sys.exit(1)

    vault_path = sys.argv[1]
    if not os.path.isdir(vault_path):
        print(f"Error: {vault_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    results = scan_vault(vault_path)
    report = generate_report(results, vault_path)
    print(report)
