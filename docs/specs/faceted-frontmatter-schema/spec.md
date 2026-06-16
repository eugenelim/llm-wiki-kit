# Spec: faceted-frontmatter-schema

- **Status:** Draft <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0009, RFC-0008, ADR-0011, ADR-0003, ADR-0005
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The vault's page-kind axis is carried by two orthogonal frontmatter facets,
`genre` and `subtype`, instead of a single fused `type` field. `genre` is a
fixed, generic vocabulary of nine document shapes — `note`, `record`,
`update`, `decision`, `reference`, `profile`, `log`, `contract`, `moc`;
`subtype` is the controlled, growable specific form (`meeting`, `medical`,
`recipe`, …). The pre-existing `status` field (already required, already
`active`/`draft`/`archived`) gains a fourth value `someday`; a new `parent`
relation carries container/hub membership. RFC-0008's `workspaces:` area axis
and the shipped workspace `.base` lenses are untouched.

Removing `type` ripples through all twelve content-type primitives, in their
entirety: the `core/files/frontmatter.schema.yaml` baseline + managed regions,
each primitive's `primitive.yaml` `contributes_to` manifest, its `.types`
snippet, the `when: type == …` guards in its `.fields` snippet, its
`description`, and its page template. A fixed crosswalk
(`crosswalk.yaml`) pins how each former fused `type` maps to `genre` +
`subtype`. Type-specific lifecycle fields that shipped operations read
(`decision_status`, `update_status`, `trip_status`) survive as subtype-scoped
`fields` entries.

The users are the kit author and the produced vault's maintaining agent —
and, **affected**, the downstream people who read and file in the vault
through the Obsidian UI: they must learn the facet vocabulary (and, via the
sibling `role-folders-and-containers` spec, the folder roles) to navigate and
create notes. Success is an internally consistent schema, twelve content-types
whose manifests/snippets/templates all express genre+subtype, a total
crosswalk, and manual affordances (templates pre-stamping facets, Properties
autocomplete, Bases views) that keep filing a few keystrokes rather than YAML
authoring.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Change, in one coordinated PR-series, every surface that references the
  page `type`: the schema baseline + managed regions; each of the twelve
  `primitive.yaml` `contributes_to` blocks (`region: types` → `region: genre`
  + `region: subtype`); each `.types` snippet (→ `.genre` + `.subtype`); each
  `.fields` snippet's `when: type == X` guards (→ `when: subtype == <subtype>`
  per crosswalk); each manifest `description`; and each page template.
- Keep RFC-0008's `workspaces:` field and the shipped workspace `.base` files
  exactly as they are (they reference no frontmatter `type`).
- Retain `decision_status`, `update_status`, and `trip_status` as
  subtype-scoped `fields` entries — they are read by the `status-synthesis`
  and `onboarding-pack` operation SKILLs.
- Write the schema into a vault only through the managed-region aggregator
  (`install.py` → `safe_write_region`), never a direct `write_text`.

### Ask first

- Changing the nine-value `genre` vocabulary fixed by RFC-0009 (adding,
  removing, or renaming a genre).
- Dropping any `*_status` field beyond the three named above, or any
  subtype-scoped field a shipped operation reads.
- Any change to `workspaces:` semantics (owned by RFC-0008).

### Never do

- Introduce a parallel `domain` field — area-membership is `workspaces:`
  (RFC-0008). *(structural)*
- Add a runtime dependency or a new top-level directory. *(structural)*
- Keep legacy `type:` read-tolerance — greenfield, single model.
- Leave any content-type manifest, snippet (`.genre`/`.subtype`/`.fields`),
  description, or page template still referencing the page `type` field.
- Re-key `wiki search` / operation contracts, or reshape vault folders, in
  this spec — those are the `operations-and-search-rekey` and
  `role-folders-and-containers` specs.

## Testing Strategy

Goal-based here means: parse the rendered/shipped artifact and assert its
shape; no production logic mirrors the assertion.

- **Schema shape** (`genre` enum of nine, `subtype`, `status` with `someday`,
  `parent` present; `type` absent; `workspaces` present; regions are
  `genre`/`subtype`/`fields`): **goal-based** — parse
  `core/files/frontmatter.schema.yaml`.
- **No surface references `type`** (12 manifests, all `.genre`/`.subtype`/
  `.fields` snippets, 12 descriptions, 12 templates): **goal-based** — grep
  asserts zero page-`type` references across content-type primitives.
- **Manifest/snippet consistency** (each manifest's declared regions match its
  on-disk snippet files): **goal-based**, proven by an **integration** test
  that runs `wiki init` and asserts `install.validate_contributions` accepts
  the catalog and the assembled `genre`/`subtype` enums equal the union of
  installed content-types' contributions.
- **Crosswalk totality** (keys == the twelve legacy types): **TDD** — a
  compressible invariant worth a unit test.
- **Lifecycle fields retained** (`decision_status`/`update_status`/
  `trip_status` present as subtype-scoped fields): **goal-based**.
- **No regression in workspace lenses**: **goal-based** — shipped `.base`
  files byte-unchanged.

## Acceptance Criteria

- [ ] `core/files/frontmatter.schema.yaml` declares `genre` (enum exactly
      `note, record, update, decision, reference, profile, log, contract, moc`),
      `subtype`, and `parent`; `status` gains `someday`
      (`active`/`draft`/`archived`/`someday`); `type` is absent; `workspaces`
      is byte-unchanged.
- [ ] `required:` is exactly `[genre, subtype, status, provenance, created,
      modified]` (replacing `type` with `genre`+`subtype`); `workspaces`,
      `parent`, and `tags` stay optional.
- [ ] The schema's managed regions are `genre`, `subtype`, and `fields`; no
      `types` region remains.
- [ ] All twelve `primitive.yaml` `contributes_to` blocks declare
      `region: genre` and `region: subtype` (plus `region: fields`); none
      declares `region: types`.
- [ ] Each content-type ships `.genre` and `.subtype` snippets matching the
      crosswalk; no `.types` snippet remains; each `.fields` snippet's guards
      are `when: subtype == <subtype>` (no `when: type == …` remains).
- [ ] `decision_status`, `update_status`, and `trip_status` remain as
      subtype-scoped `fields` entries.
- [ ] No content-type manifest `description`, snippet, or page template
      references the page `type` field.
- [ ] Each of the twelve page templates stamps `genre:`, `subtype:`, and
      `status:`; none stamps `type:`.
- [ ] `docs/specs/faceted-frontmatter-schema/crosswalk.yaml` maps all twelve
      legacy fused types to `genre`+`subtype` (+ subtype-scoped lifecycle
      field where applicable); a test asserts the mapping is total **and**
      that every row's `subtype` differs from its `genre` (so `subtype`
      refines, never duplicates, the genre — e.g. legacy `decision` →
      `genre: decision, subtype: decision-record`).
- [ ] Rendering a vault via `wiki init` over a content-type-bearing recipe
      passes `install.validate_contributions`, and the assembled schema's
      `genre`/`subtype` enums equal the union of installed contributions.
- [ ] The shipped `templates/workspaces/*/files/*.base` files are unchanged.
- [ ] Operation SKILLs that reference the removed `type` field / `types`
      region are registered as deferred to `operations-and-search-rekey`
      (deferred: backlog.md#faceted-frontmatter-schema).
- [ ] `ruff check llm_wiki_kit tests`, `ruff format --check llm_wiki_kit tests`,
      `mypy llm_wiki_kit tests`, and `pytest -m 'not slow'` pass.

## Assumptions

- Technical: `core/files/frontmatter.schema.yaml` is a managed-region-assembled shipped contract, not a Python page-validator — consumed by `managed_regions/render/install/upgrade/adopt/write_helper.py`; `models.py`'s `discriminator="type"` is the journal-event discriminator, not page-type validation (source: grep of `llm_wiki_kit/`; adversarial-review verification).
- Technical: blast radius is, for each of the twelve content-types, its `primitive.yaml` `contributes_to` (`region: types`) + `description`, its `.types` snippet, its `.fields` snippet's `when: type == …` guards (64 total), and its page template — plus the schema baseline and the crosswalk (source: grep — 12 manifests, 64 `when: type ==`, 12 templates).
- Technical: `install._plan`/`validate_contributions` derive region ids from each manifest's `contributes_to`, not a hand-maintained list in `install.py`; so the migration is manifest edits, not aggregator edits (source: `llm_wiki_kit/install.py`; adversarial-review verification).
- Technical: the shipped workspace `.base` files reference no frontmatter `type` — `type:` there is the Bases view-type keyword; ADR-0011's earlier "`.base` reference `type`" claim is wrong and is corrected in this PR (source: cat of `templates/workspaces/*/files/*.base`).
- Technical: `status` already exists in the live schema and is already required; only `someday` is new (source: `core/files/frontmatter.schema.yaml`).
- Process: scope stops at the schema + content-type primitives + crosswalk; operations/`wiki search` re-key and folder reshape are separate RFC-0009 follow-on specs, and the six operation SKILLs that read `type`/`types` are registered in `docs/backlog.md` (source: user confirmation 2026-06-16; adversarial-review).
- Process: the unified `status` facet gains `someday`; `decision_status`/`update_status`/`trip_status` survive as subtype-scoped fields (read by `status-synthesis`/`onboarding-pack`) (source: user confirmation 2026-06-16; adversarial-review verification of the reading operations).
- Product: end users are affected — they must understand the facets (and, via the sibling folders spec, the folder roles) to file and navigate in the Obsidian UI; page templates, Properties autocomplete, Bases views, and the explanation doc are the mitigations (source: user confirmation 2026-06-16).
