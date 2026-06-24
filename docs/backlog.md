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

- **Starter seed pages still carry the fused `type:` frontmatter** — after
  `faceted-frontmatter-schema` lands, the committed starters' *rendered*
  artifacts (`frontmatter.schema.yaml`, `_templates/*.md`) are regenerated to
  the facet model, but the hand-authored `starters/_seed/**/*.md` pages (copied
  verbatim by `regenerate.py`) still declare `type:` rather than
  `genre:`/`subtype:`. The recipe-rewrite + starter regeneration (rendered
  artifacts *and* seed-page relocation into the role folders) moved from
  `recipe-organization-model` to `role-folders-and-containers` (per that spec's
  Assumptions) and are done there; only the seed-page value-faceting remains,
  tracked under its section below. No kit code validates page frontmatter, so
  the starters stay functional.

## role-folders-and-containers

The reshape to the four role folders (`people/`, `efforts/`, `library/`,
`atlas/`) re-pointed every *folder* reference — content-type `requires:`,
recipe `primitives:`, ingest-SKILL paths — and removed the collapsed
ontologies and kind-folder seeds. These value-level / cross-spec re-keys are
deliberately scoped out and tracked here (no user vaults exist pre-release; no
kit code validates page frontmatter, so the vault stays functional in the
interim):

- **Hand-authored starter seed pages** (`starters/_seed/**/*.md`) still declare
  the fused `type:` frontmatter value. Their *folders* were relocated into the
  four-role layout by this spec's T6 (required by the "rendered tree matches the
  four-role layout" AC), but the `type:`→`genre`/`subtype` value re-key rides
  with the vault-side-doc faceting pass above — no kit code validates page
  frontmatter, so the starters stay functional in the interim.
- **`atlas/` synthesis-proposal gating** is owned by the
  `capture-synthesis-gating` spec; this spec seeds `atlas/` as an empty,
  human-gated role folder with its `_index.md` map only.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
