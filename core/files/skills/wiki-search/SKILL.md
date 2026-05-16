---
name: wiki-search
description: "Search the vault by content and frontmatter (--type, --tag, --status). Returns ranked pages with title, type, status, tags, and synopsis — ready to read. Default backend is ripgrep (literal substring, zero install); auto-upgrades to SQLite FTS5 with BM25 ranking, stemming, and phrase/prefix queries once the vault crosses ~1000 pages. Use for any *vault content* question; reserve the IDE's built-in Grep for regex, code search, or inspecting a known path."
license: MIT
---

# wiki-search

Two-tier search over the vault. The skill calls one entry point; the
backend is chosen automatically.

| Tier | Backend            | When                                         |
|------|--------------------|----------------------------------------------|
| 1    | **ripgrep**        | Default for new vaults; small vaults stay here forever. |
| 2    | **SQLite FTS5**    | Auto-enabled once the vault crosses ~1000 pages or 50 MB. |

The choice is invisible to you — call `wiki search` and the kit picks
the backend.

## When to use this skill (vs. the IDE's built-in Grep)

Use **wiki-search** for any query whose target is *vault content*
(anything under `wiki/`). Both backends return ranked page references
with frontmatter metadata and a synopsis — that's what you need to
decide which page to actually read. Specifically:

- Plain content queries ("find pages about *X*").
- Frontmatter filters (`--type meeting`, `--tag urgent`,
  `--status active`).
- Stemming-aware queries (`running` matches `runs`, once FTS5 is on).
- Phrase, prefix, or NEAR queries (FTS5 syntax: `"value stream"`,
  `market*`, `kafka NEAR/5 lag`).

Use the IDE's **Grep** tool for:

- Regex queries (this skill's ripgrep tier is literal substring).
- Code search inside `skills/`, `scripts/`, or other infrastructure.
- Inspecting a known file by exact path.

Both tools are unrestricted; routing is your call. When the question is
"which wiki pages…", load this skill.

## Operations

```bash
# Basic search
wiki search "event driven architecture"

# With frontmatter filters
wiki search "compliance" --tag urgent --type meeting

# Limit results
wiki search "kafka" --top 20
```

Output is markdown the agent reads directly: ranked page references
with title, type, status, tags, score (FTS5) or match count (ripgrep),
synopsis, and a snippet.

## Composing a good query

- **Start narrow.** Two or three words specific to the topic. Add
  filters before broadening the query.
- **Filter by frontmatter when you can.** `--type recipe` cuts the
  result set by an order of magnitude in food-heavy vaults.
- **Iterate.** If the first query returns nothing useful, broaden one
  word at a time. Don't dump the user's whole question as the query —
  vault content is terser than chat.

## Reading results

The skill returns the top N pages, each with:

- **Title** — the page's `# H1` or filename.
- **Path** — relative to the vault root.
- **Frontmatter** — type, status, tags.
- **Score / match count** — relative; not comparable across queries.
- **Synopsis** — the page's `## Synopsis` section if present, else the
  first paragraph.
- **Snippet** — the matched lines, with the query terms highlighted
  (FTS5 only).

Open the top 2-3 pages by exact path with your file-reading tool. Don't
re-run the search; the result set is enough to pick.

## Scaling

| Vault size       | Backend          | What to do                                    |
|------------------|------------------|-----------------------------------------------|
| < 100 pages      | ripgrep          | Nothing.                                      |
| 100–500 pages    | ripgrep          | Nothing.                                      |
| 500–1000 pages   | ripgrep          | Nothing; or force FTS5 if queries feel slow.  |
| 1000–5000 pages  | FTS5 (auto)      | Nothing; first call after the flip bootstraps the index. |
| 5000–50,000      | FTS5             | Consider sharding by major folder.            |
| 50,000+          | FTS5 + sharding  | Beyond what file-based FTS5 handles well.     |

Both backends are **lexical**. Synonym matching (`car` ↔ `automobile`)
and conceptual matching (`pricing strategy` ↔ `go-to-market plan`) are
out of scope — that needs embeddings and is a different problem.

## Failure modes

The skill never leaves you without working search:

- **Index missing** → rebuild on the next call (FTS5 only).
- **Schema drift** (kit upgrade changed the index) → rebuild
  automatically; fall back to ripgrep if rebuild fails.
- **`rg` missing** → clear error pointing to the install command for
  the user's OS.

If a search returns zero results, it's not an error — it's a signal.
Either the topic isn't in the wiki yet (suggest ingesting a source) or
the query is too narrow (broaden a word).
