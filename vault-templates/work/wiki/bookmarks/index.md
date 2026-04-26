---
type: index
folder: bookmarks
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, bookmarks]
---

## Synopsis

Team bookmarks — daily tools, internal dashboards, project resources, reference docs. The live, filterable home page is `homepage.base`; this `index.md` is an editorial overview.

## How this folder works

Each bookmark is a small `.md` file with consistent frontmatter (`type: bookmark`, `url`, `category`, `last_visited`, `icon`). Add bookmarks via the [[ingest-bookmark]] skill ("bookmark this URL") or by copying `_templates/bookmark.md` directly.

The multi-column home page is rendered live by Obsidian Bases via `homepage.base` — open it to see all bookmarks grouped by category, filtered to active, with quick navigation across views (cards / table / by-category).

## Categories

Common categories for the work variant:
- `daily-tools` — Slack, GitHub, Linear, Granola, etc.
- `internal-dashboards` — observability, deploys, status pages, runbooks
- `project-resources` — design docs, ADRs hosted externally, RFC drafts
- `reference` — engineering docs, API references, vendor docs the team relies on
- `inspiration` — engineering blogs, talks, learning resources

## Adding a bookmark

Run the [[ingest-bookmark]] skill — it takes a URL, optionally infers the category, and saves to `wiki/bookmarks/{slug}.md`.

## Rendering the home page

Open `homepage.base` in Obsidian. Switch views (cards by category / full table / daily drivers) using the Bases view tabs.

To regenerate or change layout: run [[bookmark-homepage]] which updates the `.base` file structure.
