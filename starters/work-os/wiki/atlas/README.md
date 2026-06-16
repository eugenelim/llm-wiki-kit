# atlas/

The **synthesis** role folder — the top of the vault. Where `library/`
holds what you captured, `atlas/` holds what you *concluded*: the durable
maps, overviews, and cross-cutting syntheses that make the rest navigable.

## What lives here

- **Area MOCs** — a `genre: moc` map page per subject area you steer
  (an area is a `workspaces:` lens, *not* a folder; its optional map page
  lives here).
- **Syntheses** — "what we know about X", a project retrospective, a
  decision-rationale rollup: pages that read *across* many `library/`
  captures and distil them.

Pages here are short, high-signal, and heavily wikilinked down into
`library/`, `people/`, and `efforts/`. They are the pages you'd hand
someone to orient them.

## Human-gated by design

`atlas/` is **not** an ingest target. No content-type writes here. A
synthesis earns its place by review: the `capture-synthesis-gating` flow
proposes a synthesis page from accumulated capture, and a human promotes
it — or you write one by hand. This gate is what keeps the synthesis layer
trustworthy; homing an ungated, machine-extracted page here would erode it.

## Conventions

- **Filename:** a stable slug naming the subject (`billing.md`,
  `q2-hiring.md`), not a date.
- **Frontmatter:** `genre: moc` for a map page; otherwise the synthesis
  genre that fits, plus the baseline fields. `status: draft` until a human
  has reviewed it.
