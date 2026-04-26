---
name: ingest-bookmark
description: "Save a URL as a lightweight bookmark — no content extraction, just the URL preserved with a slug page in wiki/bookmarks/. Use when the user says \"bookmark this\" / \"save this URL\" / \"add to bookmarks\" (NOT \"ingest\" / \"summarize\"), or the URL is a tool/dashboard/app the user will return to. For full content extraction (article summary, recipe extract, tax-form capture) use ingest-website or its content-type siblings."
license: MIT
metadata:
  variant: shared
---

# Ingest Bookmark Skill

Specialized content-type ingester for URLs that should be **saved as bookmarks** rather than ingested as full content. The lighter-weight cousin of [[ingest-website]] — when you want to remember a URL without summarizing or extracting from it.

## When to Use

The orchestrator routes here when:
- The user says "bookmark this" / "save this URL" / "add to bookmarks" (not "ingest" / "summarize")
- The URL is a tool / dashboard / app the user will return to (vs. an article to read once)
- The URL is part of a curated collection (favorites, frequently-used, reference, daily drivers)

For full content extraction (article summarization, recipe extraction), route to [[ingest-website]] or its content-type-specialized siblings instead.

## Composition (two-axis routing)

Lightweight by design — minimal cleanup needed:

| Source | Cleanup | Result |
|---|---|---|
| URL provided | none — skip defuddle | URL preserved as-is |
| Pasted text with URL inside | extract URL | URL only |

Optional: a quick `curl` for the page's `<title>` tag and favicon URL — gives the bookmark a useful default `title:` and `icon:` without the cost of a full defuddle pass. Skip on internal / auth-protected URLs.

## Inputs

User provides:
- URL to bookmark
- Optional: category, title, description, icon
- Optional: collection / homepage to add it to

Reads:
- The bookmark template at `_templates/bookmark.md`
- Existing bookmarks in `wiki/bookmarks/` — for duplicate detection
- The variant's category conventions (from `wiki/bookmarks/index.md`)

## Algorithm

1. **Validate URL.** Reject if obviously malformed.
2. **Detect duplicate.** If a bookmark with the same URL already exists, surface and ask: update categories / metadata, or skip?
3. **Lightweight metadata fetch** *(optional)*. Fetch the page's `<title>` tag for default title; resolve the domain favicon for `icon:`. Skip on internal / auth-protected URLs.
4. **Default category.** Infer from URL pattern when possible:
   - `github.com`, `linear.app`, `slack.com` → `daily-tools` (work)
   - `nytcooking.com`, `seriouseats.com`, `bonappetit.com` → `recipe-source` (family)
   - `nymag.com`, `theatlantic.com`, blog domains → `reading` (personal)
   - School-domain URLs → `school-portal` (family)
   - Bank / utility URLs → `banking` / `vendor-portal` (family)
   The user can override.
5. **Save.** Write `wiki/bookmarks/{slug}.md` using the template.

## Output

Write `wiki/bookmarks/{slug}.md`:

```yaml
---
title: "{title}"
type: bookmark
url: "{url}"
status: active
created: {today}
modified: {today}
tags: [bookmark, {inferred-category}]
category: "{inferred-category}"
last_visited: ""
icon: "{favicon-or-emoji}"
---
```

Body — brief synopsis + why-I-bookmarked-this from user input.

## Side-effects

1. **Bases auto-includes** the new bookmark in `wiki/bookmarks/homepage.base` (no regeneration needed — the Base file filters by `type: bookmark`).
2. **Update `wiki/bookmarks/index.md`** if the user maintains category descriptions there.
3. **Append to `log/changelog.md`**: "Bookmark added: [[bookmarks/{slug}]]."

## Interactive Review

Brief — bookmarks are quick:

```
Bookmark proposed:
  Title: Granola — meeting note-taker
  URL: https://granola.ai
  Category: daily-tools (inferred from domain pattern)
  Save to: wiki/bookmarks/granola.md

Confirm or adjust?
```

For obviously-low-friction bookmarks, the user can pre-confirm at invocation ("bookmark this without prompting").

## Failure Modes

- **URL is internal / auth-protected.** Skip the metadata-fetch step; ask the user for the title + description directly.
- **Duplicate exists.** Surface; offer to update existing rather than create new.
- **URL is dynamic / temporary** (search results page, session-tokened link). Surface; ask whether the user really wants to save this transient link.
- **Many bookmarks share a domain** (e.g., 30+ GitHub repos). Suggest sub-categorizing or using tags rather than treating each repo as a separate bookmark.

## Cadence

- **On demand:** Run when the user encounters a URL worth saving.
- **No scheduling:** Reactive.
- **Pairs with [[bookmark-homepage]]:** the homepage operation renders the bookmark collection.

## Future: extension to inventory tracking

This skill's pattern (small per-item file + Bases-rendered view) is the prototype for general inventory tracking — see future inventories for restaurants, software, vendors, etc. Same shape, different `type:` and template; same `.base`-driven rendering.
