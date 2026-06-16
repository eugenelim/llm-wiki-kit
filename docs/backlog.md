# Backlog — open items by spec

Single index of **open** work across every spec in `docs/specs/`. Each item
names the spec, the Acceptance Criterion (where one applies), what's blocking
it, and how it gets unblocked. Closed/shipped work is **not** kept here — see
each spec's Changelog and [`ROADMAP.md`](ROADMAP.md).

This is the tactical **backlog**: it's yours to curate. It is distinct from
the **product roadmap** (strategy, not a work index) at
[`ROADMAP.md`](ROADMAP.md). "Roadmap" = direction; "backlog" = the
work/deferral index.

Deferred acceptance criteria point here by **anchor**: a spec criterion written
`- [ ] <outcome> (deferred: <anchor>)` means `<anchor>` resolves to a heading in
this file (GitHub heading-slug rules — lowercase, spaces become hyphens). The
deferral lives here, version-controlled and greppable, not in a PR comment that
rots. See the Spec metadata contract in [`CONVENTIONS.md`](CONVENTIONS.md).

## How this file is maintained

- Every spec records its own `Status:` field and `Acceptance Criteria`
  checkboxes. This file aggregates the **open** items so they're visible in one
  place — it is not the source of truth.
- When an AC closes or a spec ships, update the spec first, then **remove** the
  now-closed item here in the same change (closed work lives in the spec
  Changelog / `product/changelog.md`, not here).
- When a new spec lands with open ACs, add a section here.
- If an item here is no longer accurate against the underlying spec, trust the
  spec and fix this file.

---

## faceted-frontmatter-schema

- **Operation SKILLs reference the removed `type` field and `types` region**
  — six operation SKILLs (`status-synthesis`, `action-item-rollup`,
  `medical-summary`, `renewal-reminders`, `onboarding-pack`,
  `stakeholder-map-refresh`) read the page `type` value and/or name the
  `frontmatter.schema.yaml` managed `types` region, which
  `faceted-frontmatter-schema` removes. They go stale the moment that spec
  lands. Re-keyed to `genre`/`subtype` in the `operations-and-search-rekey`
  spec (RFC-0009 follow-on); registered here so the known-stale state is
  tracked, not discovered.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
