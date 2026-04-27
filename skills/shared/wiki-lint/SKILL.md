---
name: wiki-lint
description: "Run health checks on the vault. Scripts handle structural checks (tag hygiene, broken links, orphans, asset coverage, provenance footnotes, staleness); Claude handles semantic checks (contradiction detection, synonym judgment). Use on request \"lint the wiki\" / \"check wiki health\", weekly or per-sprint, or after bulk ingestion of new raw sources."
license: MIT
compatibility: "Requires Python 3.10+ and pyyaml."
metadata:
  variant: shared
---

# Wiki Lint Skill

Run comprehensive health checks on the vault. Combines Claude's
reasoning (for semantic checks) with Python scripts (for structural
checks that benefit from deterministic scanning).

## When to Use

- On request: "Lint the wiki" or "Check wiki health"
- Scheduled: weekly or per-sprint
- After bulk ingestion of new raw sources

## Operations

### 1. Structural Lint (Script)

```bash
python scripts/tag-lint.py wiki/ \
  --provenance-check \
  --staleness-days 90 \
  > log/tag-lint-$(date +%Y-%m-%d).md
```

Covers: tag hygiene, missing frontmatter, missing synopsis, provenance footnote
violations, and active pages not modified in 90 days. Read the output and
summarize key findings.

### 2. Convergence Debt (Script)

```bash
python scripts/convergence-debt.py . > log/convergence-debt-$(date +%Y-%m-%d).md
```

Files in `raw/` that no wiki page references represent convergence debt —
ingested but never synthesized. Read the output and summarize.

### 3. Broken Wikilinks + Orphan Pages (Script)

```bash
python scripts/lint-links.py wiki/ > log/link-lint-$(date +%Y-%m-%d).md
```

Reports: broken `[[wikilinks]]` (target matches no `.md` file) and orphan
pages (no inbound links). Read the output and surface findings.

### 4. Asset Coverage (Script)

```bash
python scripts/lint-assets.py wiki/ > log/asset-lint-$(date +%Y-%m-%d).md
```

Reports non-markdown files in `_assets/` directories with no companion `.md`
page. Read the output and surface findings.

### 5. Contradiction Detection (Claude-Driven)

This is the most token-intensive check. Only run when requested
or when specific pages are flagged.

For a given domain or topic:
1. Find all wiki pages tagged with that topic
2. Read the synopsis of each (depth 1)
3. Identify pages that make claims about the same entity or decision
4. Read those pages in full (depth 2)
5. Check for conflicting claims
6. Report contradictions with specific quotes and page references

### 6. Synonym Suggestions (Script Output → Claude Review)

Read the tag lint report. For each synonym pair flagged by the
script, decide:
- Are these genuinely the same concept? → Propose a canonical tag
  and list the pages that need updating
- Are they distinct concepts that happen to have similar names?
  → No action needed, note in the report

### Output

Compile all findings into `log/lint-{date}.md` with:
- Summary of issues found (counts by category)
- Detailed findings per category
- Recommended actions (auto-fixable vs. requires human review)

Update `log/changelog.md` with a lint summary entry.

### Auto-Fix (With Confirmation)

The following can be fixed automatically after human confirmation:
- Add missing `> [!warning] Outdated` callouts to stale pages
- Update `modified` dates on pages that were changed
- Add missing `provenance` field (default to `mixed` for existing pages)
- Add missing `## Synopsis` sections (Claude generates from content)

The following always require human review:
- Resolving contradictions
- Merging synonym tags
- Archiving orphan pages
- Deleting convergence debt (the source might be intentionally unprocessed)
