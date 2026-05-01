---
name: wiki-search
description: "Vault search across wiki pages with frontmatter-aware filters (--tag, --type, --status). Default backend is ripgrep (literal substring, zero install, always-fresh content); auto-upgrades to SQLite FTS5 with BM25 ranking, porter stemming, phrase/NEAR/prefix queries, and snippet extraction once the vault grows past ~1000 pages. Use this skill for any wiki/ content search — it returns titles, types, tags, and synopses ready for the agent to read. Reserve the IDE's built-in Grep tool for: regex queries, code search inside .claude/ or other infrastructure paths outside wiki/, or single-file inspection by exact path."
license: MIT
compatibility: "Requires Python 3.10+. ripgrep (`rg`) on PATH for the default backend. SQLite with FTS5 ships with standard Python — no pip install required."
metadata:
  variant: shared
---

# Wiki Search Skill

Two-tier search over the vault. The skill calls one entry point; the backend is
chosen automatically and the choice is invisible to the agent.

| Tier | Backend | When | Setup |
|---|---|---|---|
| 1 | **ripgrep** | Default for new vaults; small vaults stay here forever | Just `rg` on PATH |
| 2 | **SQLite FTS5** | Auto-enabled once the vault crosses ~1000 pages or 50 MB | Stdlib Python (`sqlite3` + FTS5) — no pip install |

## When to use this skill (vs the IDE's built-in Grep)

Use **this skill** for any search whose target is *vault content* (anything
under `wiki/`). Both backends return ranked page references with frontmatter
metadata and a synopsis or snippet — that's what the agent needs to decide
which page to actually read. Specifically:

- Plain content queries ("find pages about *X*") — both backends handle these.
- Frontmatter filters (`--type meeting`, `--tag urgent`, `--status active`,
  case-insensitive).
- Stemming-aware queries (`running` matches `runs`, once FTS5 is active).
- Phrase, prefix, or NEAR queries (FTS5 syntax: `"value stream"`, `market*`,
  `kafka NEAR/5 lag`).

Use the **built-in Grep** tool for:
- Regex queries (this skill's ripgrep tier defaults to literal substring;
  there's no `--regex` flag).
- Code search inside `.claude/`, `scripts/`, or other infrastructure paths.
- Log files, configs, anything outside the `wiki/` content tree.
- Inspecting a known file by exact path (the skill is for finding pages, not
  reading them).

The kit deliberately leaves the IDE's built-in tools unrestricted; routing is a
prose decision the agent makes. If you (the agent) are unsure, prefer the skill
when querying *vault content* and Grep otherwise.

## Operations

The script lives at `scripts/wiki-search.py`. Run it from the vault root with
the path to the `wiki/` directory.

### Search (the common case)

```bash
python .claude/skills/wiki-search/scripts/wiki-search.py search wiki/ "event driven architecture"
python .claude/skills/wiki-search/scripts/wiki-search.py search wiki/ "compliance" --tag urgent --type meeting
python .claude/skills/wiki-search/scripts/wiki-search.py search wiki/ "kafka" --top 20
```

The output is markdown the agent can read directly: ranked page references with
title, type, status, tags, score (FTS5) or match-count (ripgrep), synopsis, and
a snippet.

### Inspect or change the backend

```bash
# Show the current backend, last vault measurement, and recent notes
python .claude/skills/wiki-search/scripts/wiki-search.py backend wiki/

# Force ripgrep (e.g., after archiving most of the vault)
python .claude/skills/wiki-search/scripts/wiki-search.py backend wiki/ --set ripgrep --delete-index

# Force FTS5 (e.g., small vault but you want stemming/snippets now)
python .claude/skills/wiki-search/scripts/wiki-search.py backend wiki/ --set fts5

# Restore the default (auto-detect)
python .claude/skills/wiki-search/scripts/wiki-search.py backend wiki/ --set auto

# Forget the auto-flip and re-evaluate from scratch
python .claude/skills/wiki-search/scripts/wiki-search.py backend wiki/ --reset
```

### Manage the FTS5 index (only meaningful once FTS5 is active)

```bash
# Incremental refresh — usually unnecessary; fts5 search refreshes itself.
python .claude/skills/wiki-search/scripts/wiki-search.py index wiki/

# Full rebuild — escape hatch for cases where mtime-based diffing misses
# changes (e.g., bulk file moves that preserved mtimes).
python .claude/skills/wiki-search/scripts/wiki-search.py index wiki/ --rebuild
```

## How the backend choice works

On the first search call in a session (or whenever `wiki/.wiki-search/state.json`
ages out of its cache window), the script reads three inputs in priority order:

1. **Explicit override** in `wiki/.wiki-search/config.yaml` — wins outright.
2. **Persistent flip flag** in `wiki/.wiki-search/state.json` — if FTS5 was
   previously auto-enabled, stay flipped (one-way hysteresis, no thrash).
3. **Vault measurement** — count `.md` pages and total bytes. Cross either
   threshold (1000 pages or 50 MB by default) and the script bootstraps the
   FTS5 index, sets the flip flag, and uses FTS5 thereafter.

After the decision is recorded, subsequent searches within the cache window
(default: 1 hour, or until the vault root mtime is newer) skip the walk and
just read the recorded backend. Per-call cost is approximately zero.

## Freshness (FTS5)

When FTS5 is the active backend, every search call performs a quick incremental
refresh: it walks the vault, upserts pages whose `mtime` differs from the
recorded value, and deletes entries for pages that no longer exist. The diff is
small because most pages haven't changed, so the cost is sub-second on medium
vaults. The user does not need to run `index --rebuild` after the first time.

`index --rebuild` exists as an escape hatch — use it after bulk moves where
mtimes are preserved, or if a kit upgrade bumps the FTS5 schema (the script
detects the schema mismatch and rebuilds automatically on the next call).

## Health checks and fallbacks

The skill is designed to never leave the user without a working search:

- **Index missing** — silently rebuild on next search.
- **Schema drift** (kit upgrade changed the FTS5 schema) — wipe and rebuild
  automatically; if even rebuild fails, fall back to ripgrep for the call.
- **Corrupt index** (any `sqlite3.DatabaseError`) — wipe and rebuild once;
  if rebuild also fails, fall back to ripgrep for this call and log a note.
- **`rg` missing** — return a clear error pointing to the install command for
  the user's OS, or suggest forcing FTS5 via config.
- **All fallbacks log a one-line note** in `state.json` (last 20 retained) so
  the user can see what happened by running `backend wiki/`.

## Configuration (optional)

By default no config file is needed. To override:

```yaml
# wiki/.wiki-search/config.yaml — commit this file to share team-wide
kit:
  search:
    backend: auto                          # ripgrep | fts5 | auto (default)
    auto_enable_threshold_pages: 1000
    auto_enable_threshold_bytes: 50000000  # 50 MB; trips first
    cache_window_seconds: 3600             # how long state.json is trusted
```

`config.yaml` is the only file in `.wiki-search/` that should be committed.
`state.json` and `index.sqlite` are derived runtime artifacts; the kit's
`.gitignore` excludes the entire `.wiki-search/` directory, so add an explicit
`!wiki/.wiki-search/config.yaml` entry if you want to commit the config.

## Scaling

| Vault size | Active backend | What you do |
|---|---|---|
| <100 pages | ripgrep | Nothing — progressive loading is usually faster anyway |
| 100–500 pages | ripgrep | Nothing |
| 500–1000 pages | ripgrep | Nothing; or set `backend: fts5` if queries feel slow |
| 1000–5000 pages | **FTS5** (auto-enabled) | Nothing; first call after the flip does a one-time bootstrap |
| 5000–50,000 pages | FTS5 | Consider sharding by major folder (one index per project) |
| 50,000+ pages | FTS5 + sharding, or external | Beyond what file-based FTS5 handles well; consider Typesense or Meilisearch |

Both backends are **lexical** by design. Synonyms (`car` ↔ `automobile`) and
conceptual matches (`pricing strategy` ↔ `go-to-market plan`) are out of scope
for this skill — that needs embeddings and is a different problem.
