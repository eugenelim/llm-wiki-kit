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

Family bookmarks — school portals, vendor logins, recipe sources, banking, reference. The live, filterable home page is `homepage.base`; this `index.md` is an editorial overview.

## How this folder works

Each bookmark is a small `.md` file with consistent frontmatter (`type: bookmark`, `url`, `category`, `last_visited`, `icon`). Add bookmarks via the [[ingest-bookmark]] skill ("bookmark this URL") or by copying `_templates/bookmark.md` directly.

The multi-column home page is rendered live by Obsidian Bases via `homepage.base` — open it to see all bookmarks grouped by category.

## Categories

Common categories for the family variant:
- `school-portal` — kids' school logins, parent portals, gradebook
- `vendor-portal` — utilities, internet, services where you log in regularly
- `recipe-source` — favorite recipe sites for [[ingest-recipe]] workflow
- `health-portal` — patient portals, insurance member sites, prescription refills
- `banking` — financial accounts, bill pay
- `shopping` — grocery delivery, household reorder lists
- `reference` — anything evergreen the household reaches for

## Adding a bookmark

Run the [[ingest-bookmark]] skill — it takes a URL, optionally infers the category, and saves to `wiki/bookmarks/{slug}.md`.

## Rendering the home page

Open `homepage.base` in Obsidian. Switch views (cards by category / full table / daily drivers) using the Bases view tabs. Excellent as a browser start page if you publish your vault or open Obsidian to this Base file each morning.

To regenerate or change layout: run [[bookmark-homepage]] which updates the `.base` file structure.
