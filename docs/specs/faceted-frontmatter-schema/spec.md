# Spec: faceted-frontmatter-schema

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0009, RFC-0008, ADR-0011, ADR-0003, ADR-0006, ADR-0005
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The vault's page-kind axis is carried by two orthogonal frontmatter facets,
`genre` and `subtype`, instead of a single fused `type` field. `genre` is a
fixed, generic vocabulary of nine document shapes — `note`, `record`,
`update`, `decision`, `reference`, `profile`, `log`, `contract`, `moc` — and,
being fixed, is a hand-written baseline enum in the schema, **not** a managed
region (RFC-0009 §B; ADR-0011). `subtype` is the controlled, growable specific
form (`meeting`, `medical`, `recipe`, …) and **is** the single managed region
each content-type contributes to (replacing the former `types` region). The pre-existing `status` field (already required, already
`active`/`draft`/`archived`) gains a fourth value `someday`; a new `parent`
relation carries container/hub membership. RFC-0008's `workspaces:` area axis
and the shipped workspace `.base` lenses are untouched.

Removing `type` ripples through all twelve content-type primitives, in their
entirety: the `core/files/frontmatter.schema.yaml` baseline + managed regions,
each primitive's `primitive.yaml` `contributes_to` manifest, its `.types`
snippet (which becomes a `.subtype` snippet), the `when: type == …` guards in
its `.fields` snippet, its `description`, and its page template. A fixed crosswalk
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
  page `type`: the schema baseline + managed regions (the fixed nine-value
  `genre` baseline enum, the `subtype` managed region replacing `types`); each
  of the twelve `primitive.yaml` `contributes_to` blocks (`region: types` →
  `region: subtype`); each `.types` snippet (→ `.subtype`); each `.fields`
  snippet's `when: type == X` guards (→ `when: subtype == <subtype>` per
  crosswalk); each manifest `description`; and each page template.
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
- Leave any content-type manifest, snippet (`.subtype`/`.fields`),
  description, or page template still referencing the page `type` field.
- Make `genre` a managed region or a per-content-type `contributes_to` entry.
  The aggregator concatenates without deduplicating and several content-types
  share a genre, so a contributed `genre` region would emit duplicate enum
  values; `genre` is a fixed baseline enum. *(structural)*
- Re-key `wiki search` / operation contracts, or reshape vault folders, in
  this spec — those are the `operations-and-search-rekey` and
  `role-folders-and-containers` specs.

## Testing Strategy

Goal-based here means: parse the rendered/shipped artifact and assert its
shape; no production logic mirrors the assertion.

- **Schema shape** (`genre` baseline enum of exactly nine, `subtype`,
  `parent` present with shape `list`/`items: string`/`optional`; `status` with
  `someday`; `type` absent; `workspaces` present; managed regions are
  `subtype`/`fields` only — no `genre` region): **goal-based** — parse
  `core/files/frontmatter.schema.yaml`.
- **No surface references `type`** (12 manifests, all `.subtype`/`.fields`
  snippets, 12 descriptions, 12 templates): **goal-based** — grep asserts zero
  page-`type` references across content-type primitives.
- **Manifest/snippet consistency** (each manifest's declared regions match its
  on-disk snippet files): **goal-based**, proven by an **integration** test
  that runs `wiki init` and asserts `install.validate_contributions` accepts
  the catalog, the assembled `subtype` enum equals the union of installed
  content-types' `subtype` contributions with no duplicate lines, and the
  assembled `genre` enum is exactly the fixed nine (independent of which
  content-types are installed, since `genre` is a baseline enum, not
  contributed).
- **Crosswalk totality** (keys == the twelve legacy types): **TDD** — a
  compressible invariant worth a unit test.
- **Lifecycle fields retained** (`decision_status`/`update_status`/
  `trip_status` present as subtype-scoped fields): **goal-based**.
- **No regression in workspace lenses**: **goal-based** — shipped `.base`
  files byte-unchanged.

## Acceptance Criteria

- [x] `core/files/frontmatter.schema.yaml` declares `genre` as a fixed
      baseline enum (exactly `note, record, update, decision, reference,
      profile, log, contract, moc`, hand-written — not a managed region),
      `subtype`, and `parent` (shape `list` / `items: string` / `optional`);
      `status` gains `someday` (`active`/`draft`/`archived`/`someday`); `type`
      is absent; `workspaces` is byte-unchanged.
- [x] `required:` is exactly `[genre, subtype, status, provenance, created,
      modified]` (replacing `type` with `genre`+`subtype`); `workspaces`,
      `parent`, and `tags` stay optional.
- [x] The schema's managed regions are `subtype` and `fields`; no `types`
      region and no `genre` region exist (`genre` is a fixed baseline enum).
- [x] All twelve `primitive.yaml` `contributes_to` blocks declare
      `region: subtype` (plus `region: fields`); none declares `region: types`
      or `region: genre`.
- [x] Each content-type ships a `.subtype` snippet matching the crosswalk; no
      `.types` or `.genre` snippet remains; each `.fields` snippet's guards
      are `when: subtype == <subtype>` (no `when: type == …` remains).
- [x] `decision_status`, `update_status`, and `trip_status` remain as
      subtype-scoped `fields` entries.
- [x] No content-type catalog *schema surface* — manifest `description`,
      `.subtype`/`.fields` snippet, or page template — references the page
      `type` field. (The vault-side ingest `SKILL.md` and `wiki/` `README.md`
      shipped inside each primitive are a separate surface, deferred below.)
- [x] Each of the twelve page templates stamps `genre:`, `subtype:`, and
      `status:`; none stamps `type:`.
- [x] `docs/specs/faceted-frontmatter-schema/crosswalk.yaml` maps all twelve
      legacy fused types to `genre`+`subtype` (+ subtype-scoped lifecycle
      field where applicable); a test asserts the mapping is total, that every
      row's `genre` is one of the fixed nine, that every row's `subtype`
      differs from its `genre` (so `subtype` refines, never duplicates, the
      genre — e.g. legacy `decision` → `genre: decision, subtype:
      decision-record`), **and** that the twelve `subtype` values are pairwise
      distinct (so the assembled `subtype` region carries no duplicate lines).
- [x] Rendering a vault via `wiki init` over a content-type-bearing recipe
      passes `install.validate_contributions`; the assembled `subtype` enum
      equals the union of installed content-types' `subtype` contributions
      with no duplicate lines; and the assembled `genre` enum is exactly the
      fixed nine.
- [x] The shipped `templates/workspaces/*/files/*.base` files are unchanged.
- [x] Operation SKILLs that reference the removed `type` field / `types`
      region are registered as deferred to `operations-and-search-rekey`
      (deferred: backlog.md#faceted-frontmatter-schema).
- [x] The committed starters (`starters/{family,work-os}/`, the
      `conflict-pending` example vault) are regenerated so their *rendered*
      schema/templates match the facet model; their hand-authored seed pages'
      `type:` faceting is deferred (deferred: backlog.md#faceted-frontmatter-schema).
- [x] The vault-side content-type ingest `SKILL.md` and `wiki/` `README.md`
      `type:` references are registered as deferred — their full re-key
      depends on the ontology/entity facets defined by
      `role-folders-and-containers` (which owns the vault-side-doc value
      re-key; the `wiki/` READMEs were removed and the SKILL *folder*
      references re-pointed there)
      (deferred: backlog.md#faceted-frontmatter-schema).
- [x] `ruff check llm_wiki_kit tests`, `ruff format --check llm_wiki_kit tests`,
      `mypy llm_wiki_kit tests`, and `pytest -m 'not slow'` pass.

## Assumptions

- Technical: `core/files/frontmatter.schema.yaml` is a managed-region-assembled shipped contract, not a Python page-validator — consumed by `managed_regions/render/install/upgrade/adopt/write_helper.py`; `models.py`'s `discriminator="type"` is the journal-event discriminator, not page-type validation (source: grep of `llm_wiki_kit/`; adversarial-review verification).
- Technical: blast radius is, for each of the twelve content-types, its `primitive.yaml` `contributes_to` (`region: types`) + `description`, its `.types` snippet, its `.fields` snippet's `when: type == …` guards (64 total), and its page template — plus the schema baseline and the crosswalk (source: grep — 12 manifests, 64 `when: type ==`, 12 templates).
- Technical: `install._plan`/`validate_contributions` derive region ids from each manifest's `contributes_to`, not a hand-maintained list in `install.py`; so the migration is manifest edits, not aggregator edits (source: `llm_wiki_kit/install.py`; adversarial-review verification).
- Technical: the shipped workspace `.base` files reference no frontmatter `type` — `type:` there is the Bases view-type keyword; ADR-0011 already carries the correction of its earlier "`.base` reference `type`" claim (source: cat of `templates/workspaces/*/files/*.base`; `docs/adr/0011-genre-subtype-facets-replace-fused-type.md`).
- Technical: `status` already exists in the live schema and is already required; only `someday` is new (source: `core/files/frontmatter.schema.yaml`).
- Process: scope stops at the schema + content-type catalog *schema surfaces* (manifest/snippet/template/description) + crosswalk; operations/`wiki search` re-key, folder reshape, and the vault-side content-type ingest-`SKILL.md`/`README.md` re-key are separate RFC-0009 follow-on specs. The six operation SKILLs that read `type`/`types`, the content-type ingest-SKILL/README `type:` references, and the starter seed-page `type:` are all registered as deferred in `docs/backlog.md` (source: user confirmation 2026-06-16; pre-EXECUTE + implementation adversarial review).
- Process: the unified `status` facet gains `someday`; `decision_status`/`update_status`/`trip_status` survive as subtype-scoped fields (read by `status-synthesis`/`onboarding-pack`) (source: user confirmation 2026-06-16; adversarial-review verification of the reading operations).
- Product: end users are affected — they must understand the facets (and, via the sibling folders spec, the folder roles) to file and navigate in the Obsidian UI; page templates, Properties autocomplete, Bases views, and the explanation doc are the mitigations (source: user confirmation 2026-06-16).
