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

Personal bookmarks — daily-driver tools, reading sources, inspiration channels, learning resources, career-relevant tools. The live, filterable home page is `homepage.base`; this `index.md` is an editorial overview.

## How this folder works

Each bookmark is a small `.md` file with consistent frontmatter (`type: bookmark`, `url`, `category`, `last_visited`, `icon`). Add bookmarks via the [[ingest-bookmark]] skill ("bookmark this URL") or by copying `_templates/bookmark.md` directly.

The multi-column home page is rendered live by Obsidian Bases via `homepage.base` — open it to see all bookmarks grouped by category.

## Categories

Common categories for the personal variant:
- `daily-tools` — email, calendar, the apps you use every day
- `reading` — newsletters, blog feeds, RSS sources
- `inspiration` — designers / writers / engineers / creators you follow
- `learning-resources` — courses, paper databases, tutorials worth revisiting
- `career-tools` — resume builders, interview-prep sites, target-company careers pages
- `shopping` — anything you want at hand when reordering / shopping
- `reference` — evergreen reference (style guides, language docs, frameworks)

## Adding a bookmark

Run the [[ingest-bookmark]] skill — it takes a URL, optionally infers the category, and saves to `wiki/bookmarks/{slug}.md`.

## Rendering the home page

Open `homepage.base` in Obsidian. Switch views (cards by category / full table / daily drivers / reading) using the Bases view tabs. Many users open this Base file as their daily start view — it's the personal-OS equivalent of a browser home page.

To regenerate or change layout: run [[bookmark-homepage]] which updates the `.base` file structure.
