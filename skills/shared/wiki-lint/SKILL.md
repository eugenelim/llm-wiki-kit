---
name: wiki-lint
description: "Run health checks on the vault. Combines deterministic Python scripts (scripts/tag-lint.py for tag hygiene, missing frontmatter, missing synopsis; scripts/convergence-debt.py for unconsolidated themes) with semantic LLM checks (orphan pages, broken wikilinks, contradiction detection). Use on request \"lint the wiki\" / \"check wiki health\", weekly or per-sprint, or after bulk ingestion of new raw sources."
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

### 1. Structural Lint (Script-Assisted)

Run the tag lint script for tag hygiene, missing frontmatter,
and missing synopsis checks:

```bash
python scripts/tag-lint.py wiki/ > log/tag-lint-$(date +%Y-%m-%d).md
```

Read the output report and summarize the key findings.

### 2. Convergence Debt (Script-Assisted)

Run the convergence-debt script to find raw sources with no
referencing wiki page:

```bash
python scripts/convergence-debt.py . > log/convergence-debt-$(date +%Y-%m-%d).md
```

Files in `raw/` that no wiki page references in `sources:` frontmatter
or footnotes represent convergence debt — they were dropped into the
vault but never synthesized into knowledge. Read the output report
and summarize.

Report format:
```markdown
## Convergence Debt

The following raw sources have no corresponding wiki page:
- `raw/project-x/meeting-2026-04-10.md` — ingested but not synthesized
- `raw/project-x/requirements-v3.pdf` — no wiki page references this
```

### 3. Broken Wikilinks (Claude-Driven)

Scan wiki pages for `[[wikilinks]]`. For each link, verify the
target page exists. Report broken links with the source page and
the broken target.

### 4. Orphan Pages (Claude-Driven)

Find wiki pages that have no inbound links from any other page.
These are invisible in the knowledge graph — either link them
from relevant pages or consider archiving.

### 5. Companion Page Coverage (Claude-Driven)

Scan all `_assets/` directories. For each non-markdown file,
check whether a companion `.md` page exists. Report files
without companions.

### 6. Provenance Validation (Claude-Driven)

For pages with `provenance: synthesized` or `provenance: mixed`:
- Check that source footnotes exist
- Verify footnote targets point to files in `raw/` that exist
- Flag `> [!note] Inferred` callouts that have not been resolved

### 7. Contradiction Detection (Claude-Driven)

This is the most token-intensive check. Only run when requested
or when specific pages are flagged.

For a given domain or topic:
1. Find all wiki pages tagged with that topic
2. Read the synopsis of each (depth 1)
3. Identify pages that make claims about the same entity or decision
4. Read those pages in full (depth 2)
5. Check for conflicting claims
6. Report contradictions with specific quotes and page references

### 8. Synonym Suggestions (Script Output → Claude Review)

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
