---
name: wiki-search
description: "Optional, large-scale. BM25 full-text search via scripts/wiki-search.py for vaults that have outgrown progressive loading (index.md → synopsis scan → full read). Use only when the vault has 500+ wiki pages, query operations frequently scan many synopses before finding relevant pages, fuzzy matching is needed, or multiple people query the vault frequently. For smaller vaults use progressive loading."
license: MIT
compatibility: "Requires Python 3.10+ and bm25s[core] PyStemmer pyyaml."
metadata:
  variant: shared
---

# Wiki Search Skill (Optional — Large Scale)

BM25 full-text search for vaults that outgrow progressive loading.

## When to Use

Progressive loading (index.md → synopsis scan → full read) is the
default retrieval method and works well up to ~500 wiki pages. Beyond
that, scanning synopses to find relevant content becomes token-expensive.

Enable this skill when:
- The vault has 500+ wiki pages
- Query operations frequently scan many synopses before finding relevant pages
- You need fuzzy matching (progressive loading is exact wikilink navigation)
- Multiple people query the vault frequently

## Prerequisites

Install dependencies (once per machine):
```bash
pip install bm25s[core] PyStemmer pyyaml
```

## Operations

### Build the Index

Run after any significant ingest session or on a schedule:
```bash
python scripts/wiki-search.py index wiki/
```

This creates a `.wiki-search-index/` directory inside `wiki/` containing
the BM25 index and a metadata.json with page titles, types, and synopses.
Add `.wiki-search-index/` to `.gitignore` — it's a derived artifact.

Rebuild time: <5 seconds for 1,000 pages. <30 seconds for 10,000 pages.

### Search

```bash
python scripts/wiki-search.py search wiki/ "event driven architecture" --top 10
```

Returns ranked results as markdown with wikilinks, scores, and synopses.

### Using Search in the Query Operation

When this skill is active, the Query operation changes:

1. **Search first.** Run a BM25 query to get ranked candidate pages
2. **Read synopses** from the search results (already included in output)
3. **Read full content** of only the top relevant pages (depth 2)
4. Synthesize answer as normal

This replaces the "read index.md → scan synopses" step with a faster,
more targeted search. Progressive loading remains as the fallback if
the search index is stale or missing.

### Keeping the Index Fresh

The index must be rebuilt after significant wiki changes. Options:

- **Manual:** Run `wiki-search.py index` after each ingest session
- **Scheduled:** Add to a Cowork scheduled task (e.g., nightly rebuild)
- **Git hook:** If using Git sync, add a post-merge hook that rebuilds

A stale index returns slightly less accurate results but never returns
wrong results — it just misses pages added after the last build. Claude
can fall back to progressive loading for recently-added pages.

## How It Works

The script scans all `.md` files in `wiki/`, extracts:
- Title (from frontmatter or filename)
- Tags (from frontmatter)
- Synopsis section
- Full body text

It builds a BM25 index with English stemming and stop-word removal
using the `bm25s` library (pure Python, backed by sparse matrices).
Search queries are stemmed the same way.

Results include the synopsis for each hit, so the agent can assess
relevance without reading the full page — preserving the progressive
loading pattern at the search layer.

## Scaling Notes

| Vault size | Recommended retrieval | Rationale |
|---|---|---|
| <100 pages | Progressive loading only | Claude navigates the structure efficiently |
| 100-500 pages | Progressive loading | Synopsis scanning is still manageable |
| 500-2,000 pages | BM25 search (this skill) | Too many synopses to scan efficiently |
| 2,000-10,000 pages | BM25 search + sharded index | Split index by project/domain |
| 10,000+ pages | Consider dedicated search (Typesense, MeiliSearch) | Beyond what file-based BM25 handles well |
