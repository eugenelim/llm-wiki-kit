---
name: bookmark-homepage
description: "Render the bookmark collection as a multi-column home page (Obsidian Bases .base file + optional static markdown export) — usable as a browser start page, daily-driver dashboard, or quick-reference for \"all your home needs\". Use after accumulating 10+ bookmarks, after a major bookmark sweep (cleanup, reorganization), when configuring a new device, or on request: \"render my bookmark homepage\"."
license: MIT
metadata:
  variant: shared
---

# Bookmark Homepage Skill

Render the bookmark collection as a multi-column home page — usable as a browser start page, a daily-driver dashboard, or a quick-reference for "all your home needs." Generates an Obsidian Bases (`.base`) file for live filtered views, plus optionally a static markdown page for export.

## When to Use

- After accumulating 10+ bookmarks; render the homepage to see what you have
- After a major bookmark sweep (cleanup, reorganization, category restructure)
- When configuring a new device — render the homepage as the starting view
- On request: "Render my bookmark homepage" / "Generate the bookmark dashboard"

## Approach

The kit uses **Obsidian Bases** to render bookmarks as a live, filterable view. Each bookmark page has consistent frontmatter (`type: bookmark`, `category`, `tags`); the `.base` file declares the views' filters, grouping, and layout. For publishing or sharing, the skill can also generate a static markdown homepage with category-grouped multi-column tables.

## Inputs

User provides:
- Optional: filter (e.g., "work bookmarks only," "exclude archived")
- Optional: layout preference — `cards` (default) | `table` | `columns` | `static-markdown`
- Optional: featured categories to add as dedicated views

Reads:
- All `wiki/bookmarks/*.md` pages — for the bookmark collection
- Existing `wiki/bookmarks/homepage.base` — to update rather than overwrite
- The user's preferred categories — derived from `category:` frontmatter values across the collection

## Algorithm

1. **Inventory bookmarks.** Read all `type: bookmark` pages.
2. **Detect categories.** Unique values of `category:` frontmatter; rank by count.
3. **Apply layout.** For `.base` files, generate the Bases YAML with views (cards by category, full table, plus dedicated views for top categories). For static markdown, generate sections per category with bullet lists or columned tables.
4. **Sort within category.** By `last_visited` (most recent first) by default; alphabetical for evergreen categories like `reference`.

## Output

### Default: `wiki/bookmarks/homepage.base`

Multi-view layout — the user switches views in Obsidian. Generated YAML filters by `type: bookmark` and `status: active`, then declares views: **By Category** (cards, grouped), **All Bookmarks** (table sortable by every field), plus dedicated card views for featured categories (work: `daily-tools` + `reference`; family: `school-portal` + `recipe-source` + `vendor-portal`; personal: `daily-tools` + `reading` + `career-tools`). See each variant's `vault-templates/{variant}/wiki/bookmarks/homepage.base` for the concrete YAML the kit ships.

New bookmarks automatically appear in the relevant views via the `type: bookmark` filter.

### Optional: `wiki/bookmarks/homepage.md` (static markdown export)

For users who want to publish or share, generate a static markdown page with multi-column category layout (markdown tables — one column per category, one bookmark per row):

```markdown
## Daily Drivers
| Tools | Reference | Inspiration |
|---|---|---|
| [Granola](https://granola.ai) | [MDN](https://developer.mozilla.org) | [@dhh](https://twitter.com/dhh) |
| [Linear](https://linear.app) | [Stripe Docs](https://stripe.com/docs) | …
```

Useful for Obsidian Publish, static-site export, or sharing.

## Side-effects

1. **Update `wiki/bookmarks/index.md`** with a pointer to `homepage.base`.
2. **Append to `log/changelog.md`**: "Bookmark homepage rendered: {N} bookmarks across {M} categories."

## Browser Integration

To use the rendered homepage as your **browser startup page**:

- **Obsidian Publish** (paid): publish your vault, set the published bookmark homepage URL as your browser's start page
- **Local-only:** open Obsidian to the homepage Base on each device; or use a local markdown-to-HTML pipeline to convert `homepage.md` to a local file you point your browser at

The kit doesn't ship an integrated browser-startup-page service — that's per-user infrastructure. The output (Base file + static markdown) gives users the building blocks; the browser-integration choice is up to them.

## Interactive Review

```
Bookmark homepage:
  Total bookmarks: 47 active, 3 archived
  Categories detected: daily-tools (8), reference (12), inspiration (4),
    shopping (3), reading (15), school (3), recipe-sources (2)

Layout: card view by category (default)
Featured-category views to add: daily-tools, reading

Generate / update homepage.base? Also generate static homepage.md?
```

## Failure Modes

- **No bookmarks captured yet.** Surface: "no bookmarks found. Use [[ingest-bookmark]] to start a collection."
- **Many bookmarks but inconsistent categorization.** Surface: "37 bookmarks have `category:` set; 10 don't. Categorize them, or run with the un-categorized in 'uncategorized' bucket?"
- **Obsidian Bases not installed.** Skip the .base file generation; produce static markdown instead.
- **Existing custom Base file.** If `homepage.base` was hand-edited, surface a diff before overwriting; offer to merge or version.

## Cadence

- **On demand:** Run after major bookmark additions or cleanup.
- **Quarterly:** Run as part of vault-hygiene to surface bookmarks no longer used (high `last_visited` deltas).
- **Live with Bases:** The `.base` file auto-updates as bookmarks change; manual regeneration only needed for layout changes.

## Future: dashboard composition with inventories

The bookmark homepage is the kit's first multi-column dashboard. As inventories grow (restaurants, software, subscriptions, …), each gets its own `.base` file. A future "dashboard" skill could compose multiple Bases into a vault-level home page (bookmarks at the top, restaurants nearby, software inventory in a tab) — same `.base`-driven rendering, broader scope.
