#!/usr/bin/env python3
"""
tag-lint.py — Scan an Obsidian vault for tag hygiene issues.

Detects:
  - Tag synonyms (similar tags that likely mean the same thing)
  - Underused tags (only on 1 page)
  - Overused tags (on >50% of pages)
  - Inline tags not in frontmatter (inconsistency)
  - (--provenance-check) synthesized/mixed pages missing footnotes or raw/ sources
  - (--staleness-days N) active pages not modified in N days

Usage:
  python tag-lint.py /path/to/vault/wiki
  python tag-lint.py /path/to/vault/wiki --provenance-check --staleness-days 90

Output:
  Prints a markdown report to stdout. Pipe to a file:
  python tag-lint.py /path/to/vault/wiki > /path/to/vault/log/tag-lint-2026-04-25.md
"""

import argparse
import os
import re
import sys
import yaml
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations


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
        body = content[end + 3:]
        return fm if isinstance(fm, dict) else None, body
    except yaml.YAMLError:
        return None, content


def extract_inline_tags(body):
    """Extract #tags from markdown body text (not in code blocks)."""
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body = re.sub(r"`[^`]+`", "", body)
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
    """Find tag pairs that are likely synonyms based on edit distance."""
    synonyms = []
    tag_list = sorted(tags.keys())

    for t1, t2 in combinations(tag_list, 2):
        n1, n2 = normalize_tag(t1), normalize_tag(t2)

        if n1 == n2:
            synonyms.append((t1, t2, "identical-after-normalize"))
            continue

        if len(n1) > 3 and len(n2) > 3:
            dist = levenshtein(n1, n2)
            max_len = max(len(n1), len(n2))
            if dist <= threshold and dist / max_len < 0.3:
                synonyms.append((t1, t2, f"edit-distance-{dist}"))

    return synonyms


def parse_date_field(value):
    """Parse a frontmatter date field to a date object, or None."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def check_provenance(relpath, fm, body, vault_root):
    """
    Return a list of violation strings for pages with provenance: synthesized|mixed.
    - Must have at least one [^id] footnote reference.
    - Each footnote definition pointing into raw/ must reference an existing file.
    """
    prov = fm.get("provenance", "")
    if prov not in ("synthesized", "mixed"):
        return []

    violations = []

    # Check for any footnote reference in the body
    footnote_refs = re.findall(r"\[\^[\w-]+\](?!\:)", body)
    if not footnote_refs:
        violations.append("no footnote references ([^id]) found")
        return violations

    # Check footnote definitions that point into raw/
    # Pattern: [^id]: raw/some/path  (anywhere on a line after the definition marker)
    raw_defs = re.findall(r"^\[\^[\w-]+\]:\s*(raw/\S+)", body, re.MULTILINE)
    for raw_ref in raw_defs:
        # Strip trailing punctuation
        raw_ref = raw_ref.rstrip(".,;)")
        target = os.path.join(vault_root, raw_ref)
        if not os.path.exists(target):
            violations.append(f"footnote target not found: `{raw_ref}`")

    return violations


def scan_vault(vault_path, provenance_check=False, staleness_days=None):
    """Scan all markdown files in the vault."""
    vault_root = os.path.dirname(os.path.abspath(vault_path))
    today = date.today()

    tag_usage = defaultdict(set)
    pages_with_frontmatter = 0
    pages_without_frontmatter = []
    pages_missing_provenance = []
    pages_missing_synopsis = []
    inline_only_tags = defaultdict(set)
    provenance_violations = []  # (relpath, [violation_strings])
    stale_pages = []            # (relpath, modified_date)
    total_pages = 0

    for root, dirs, files in os.walk(vault_path):
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

                if "provenance" not in fm:
                    pages_missing_provenance.append(relpath)

                fm_tags = set()
                if "tags" in fm and isinstance(fm["tags"], list):
                    for tag in fm["tags"]:
                        tag_str = str(tag)
                        fm_tags.add(normalize_tag(tag_str))
                        tag_usage[normalize_tag(tag_str)].add(relpath)

                if provenance_check:
                    violations = check_provenance(relpath, fm, body, vault_root)
                    if violations:
                        provenance_violations.append((relpath, violations))

                if staleness_days is not None:
                    status = fm.get("status", "")
                    modified = parse_date_field(fm.get("modified"))
                    if status == "active" and modified is not None:
                        age = (today - modified).days
                        if age > staleness_days:
                            stale_pages.append((relpath, modified, age))
            else:
                pages_without_frontmatter.append(relpath)

            if "## Synopsis" not in body and "## synopsis" not in body.lower():
                pages_missing_synopsis.append(relpath)

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
        "provenance_violations": provenance_violations,
        "stale_pages": stale_pages,
    }


def generate_report(results, vault_path, staleness_days=None):
    """Generate a markdown lint report."""
    tag_usage = results["tag_usage"]
    total = results["total_pages"]
    today = date.today().isoformat()

    lines = [
        "---",
        "type: lint-report",
        "provenance: synthesized",
        f"created: {today}",
        f"modified: {today}",
        "tags: [lint, tags, health-check]",
        "---",
        "",
        "## Synopsis",
        "",
        f"Tag hygiene report for vault at `{vault_path}`. "
        f"Scanned {total} pages, found {len(tag_usage)} unique tags.",
        "",
        f"# Tag Lint Report — {today}",
        "",
        f"Scanned **{total}** markdown pages in `{vault_path}`.",
        "",
    ]

    # Synonym detection
    synonyms = find_synonyms(tag_usage)
    if synonyms:
        lines += [
            "## Possible Synonyms",
            "",
            "These tag pairs may refer to the same concept. "
            "Consider merging to the canonical form.",
            "",
            "| Tag A | Tag B | Reason | Pages (A) | Pages (B) |",
            "|---|---|---|---|---|",
        ]
        for t1, t2, reason in synonyms:
            c1 = len(tag_usage.get(t1, set()))
            c2 = len(tag_usage.get(t2, set()))
            lines.append(f"| `#{t1}` | `#{t2}` | {reason} | {c1} | {c2} |")
        lines.append("")

    # Underused tags
    underused = {t: pages for t, pages in tag_usage.items() if len(pages) == 1}
    if underused:
        lines += [
            "## Underused Tags (1 page only)",
            "",
            "Consider whether these are too specific or should be removed.",
            "",
        ]
        for tag in sorted(underused.keys()):
            page = list(underused[tag])[0]
            lines.append(f"- `#{tag}` — only on `{page}`")
        lines.append("")

    # Overused tags
    threshold = max(total * 0.5, 5)
    overused = {t: pages for t, pages in tag_usage.items() if len(pages) > threshold}
    if overused:
        lines += [
            "## Overused Tags (>50% of pages)",
            "",
            "These tags are so broad they don't aid navigation.",
            "",
        ]
        for tag in sorted(overused.keys(), key=lambda t: -len(overused[t])):
            lines.append(f"- `#{tag}` — on {len(overused[tag])} of {total} pages")
        lines.append("")

    # Inline-only tags
    if results["inline_only_tags"]:
        lines += [
            "## Inline Tags Missing from Frontmatter",
            "",
            "These tags appear in the body text but not in the `tags:` frontmatter field.",
            "",
        ]
        for tag in sorted(results["inline_only_tags"].keys()):
            pages = results["inline_only_tags"][tag]
            lines.append(
                f"- `#{tag}` — in {len(pages)} page(s): "
                + ", ".join(f"`{p}`" for p in sorted(pages)[:3])
            )
        lines.append("")

    # Missing provenance
    if results["pages_missing_provenance"]:
        missing = results["pages_missing_provenance"]
        lines += [
            "## Missing Provenance Field",
            "",
            f"{len(missing)} pages are missing the `provenance` frontmatter field.",
            "",
        ]
        for p in sorted(missing)[:20]:
            lines.append(f"- `{p}`")
        if len(missing) > 20:
            lines.append(f"- ... and {len(missing) - 20} more")
        lines.append("")

    # Missing synopsis
    if results["pages_missing_synopsis"]:
        missing = results["pages_missing_synopsis"]
        lines += [
            "## Missing Synopsis Section",
            "",
            f"{len(missing)} pages are missing the `## Synopsis` section.",
            "",
        ]
        for p in sorted(missing)[:20]:
            lines.append(f"- `{p}`")
        if len(missing) > 20:
            lines.append(f"- ... and {len(missing) - 20} more")
        lines.append("")

    # Provenance footnote violations
    if results["provenance_violations"]:
        pv = results["provenance_violations"]
        lines += [
            "## Provenance Footnote Violations",
            "",
            "Pages with `provenance: synthesized` or `mixed` must have "
            "`[^id]` footnotes referencing files in `raw/`.",
            "",
        ]
        for relpath, violations in sorted(pv):
            for v in violations:
                lines.append(f"- `{relpath}` — {v}")
        lines.append("")

    # Stale pages
    if results["stale_pages"]:
        sp = results["stale_pages"]
        lines += [
            f"## Stale Active Pages (>{staleness_days} days since modified)",
            "",
            f"These pages have `status: active` but haven't been updated in "
            f"over {staleness_days} days.",
            "",
        ]
        for relpath, modified, age in sorted(sp, key=lambda x: -x[2]):
            lines.append(f"- `{relpath}` — last modified {modified} ({age} days ago)")
        lines.append("")

    # Tag frequency table
    lines += [
        "## All Tags by Frequency",
        "",
        "| Tag | Pages |",
        "|---|---|",
    ]
    for tag in sorted(tag_usage.keys(), key=lambda t: -len(tag_usage[t])):
        lines.append(f"| `#{tag}` | {len(tag_usage[tag])} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan an Obsidian vault wiki directory for tag hygiene issues."
    )
    parser.add_argument("vault_wiki", help="Path to the wiki/ directory inside the vault")
    parser.add_argument(
        "--provenance-check",
        action="store_true",
        help="Check that synthesized/mixed pages have footnotes referencing raw/ files",
    )
    parser.add_argument(
        "--staleness-days",
        type=int,
        metavar="N",
        help="Flag status:active pages not modified in N days",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.vault_wiki):
        print(f"Error: {args.vault_wiki} is not a directory", file=sys.stderr)
        sys.exit(1)

    results = scan_vault(
        args.vault_wiki,
        provenance_check=args.provenance_check,
        staleness_days=args.staleness_days,
    )
    report = generate_report(results, args.vault_wiki, staleness_days=args.staleness_days)
    print(report)


if __name__ == "__main__":
    main()
