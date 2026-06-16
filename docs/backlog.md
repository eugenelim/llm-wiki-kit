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
- **Content-type ingest SKILLs and `wiki/` READMEs still reference `type:`**
  — each content-type primitive ships an ingest `SKILL.md` and a `wiki/<area>/`
  `README.md` (vault-side, copied into a user's vault). After faceting, the
  READMEs still document `type: <content-type>` for the page's own frontmatter,
  and the ingest SKILLs still instruct the agent to stub *entity* pages with
  `type: person` / `type: customer` / `type: project`. Re-keying the own-kind
  references is mechanical, but the entity-page references depend on the
  **ontology/entity facets that this spec does not define** (people, customers,
  projects are faceted by `role-folders-and-containers` /
  `recipe-organization-model`), so the whole vault-side content-type doc surface
  is faceted there, together with the `core/files/CORE.md` rewrite (RFC-0009 §H
  Vault-side). Deferred as one unit to keep each primitive's vault-side docs
  internally consistent until then; same interim-staleness category as the
  operation SKILLs above. No kit code validates page frontmatter, so vaults stay
  functional in the interim.
- **Starter seed pages still carry the fused `type:` frontmatter** — after
  `faceted-frontmatter-schema` lands, the committed starters' *rendered*
  artifacts (`frontmatter.schema.yaml`, `_templates/*.md`) are regenerated to
  the facet model, but the hand-authored `starters/_seed/**/*.md` pages (copied
  verbatim by `regenerate.py`) still declare `type:` rather than
  `genre:`/`subtype:`. No kit code validates page frontmatter, so the starters
  stay functional; the seed pages are faceted in the `recipe-organization-model`
  spec (RFC-0009 follow-on), which owns recipe + starter regeneration.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
