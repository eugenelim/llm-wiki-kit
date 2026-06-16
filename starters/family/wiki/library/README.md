# library/

The **capture & reference** role folder. Everything you ingest or keep
for reference that isn't an entity node (`people/`), a bounded effort
(`efforts/`), or a synthesis (`atlas/`) lands here.

## What lives here

A single flat folder, organized by the `genre`/`subtype` facets rather
than by kind subfolders. Capture pages produced by content-type ingesters:

- **Records & logs** — meetings, interviews, medical records, receipts,
  tax documents (`genre: record` / `log`).
- **Decisions** — durable "what we chose and why" pages (`genre: decision`).
- **Updates** — stakeholder updates and the like (`genre: update`).
- **Notes & action items** — lightweight working notes (`genre: note`).
- **Reference** — recipes, durable how-tos, contracts
  (`genre: reference` / `contract`).

There is **no** `meetings/`, `decisions/`, `receipts/`, `food/`, or
`medical/` subfolder. Kind is the `subtype` facet; lifecycle is the
`status` facet; area is the `workspaces:` lens. The `_index.md` map
groups the folder by `genre` so you still browse by kind — without a
folder per kind.

## Conventions

- **Filename:** date-prefixed where the page is time-anchored
  (`YYYY-MM-DD-<slug>.md` for a meeting or decision); a stable slug
  otherwise (`sourdough-bread.md` for a recipe).
- **Frontmatter:** every page declares `genre` + `subtype` (per its
  content-type's crosswalk) plus the baseline fields. Entities the page
  mentions are wikilinks to `wiki/people/`; a containing effort is named
  by the `parent:` relation pointing at `wiki/efforts/<type>/<instance>`.
- **Link, don't duplicate.** A meeting page links its attendees to
  `people/` and its project to `efforts/`; it does not restate them.

## Created by other primitives

Content-type ingesters write their pages here. Operations
(`weekly-digest`, `follow-up-tracker`, `meal-planning`, …) read across
the folder by `genre`/`subtype`/date window. Synthesis that earns a
durable map page graduates to `atlas/`.
