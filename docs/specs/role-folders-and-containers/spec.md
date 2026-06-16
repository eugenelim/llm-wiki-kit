# Spec: role-folders-and-containers

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0009, RFC-0008, RFC-0004, ADR-0011, ADR-0006
- **Contract:** none
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A vault the kit produces locates pages by *role*, not by *kind*. Under `wiki/`
there are exactly four stable, single-valued role folders — `people/` (entity
nodes), `efforts/` (bounded containers, nested per type), `library/` (capture &
reference), `atlas/` (synthesis) — plus the root `index.md` MOC. Kind is the
`subtype` facet, lifecycle is the `status` facet, and area is RFC-0008's
`workspaces:` lens; none of the three is ever a folder. This realizes the LYT
layout RFC-0009 §C/§D specify, on top of the facets `faceted-frontmatter-schema`
already shipped.

The catalog is re-authored to produce this layout: five entity-kind ontology
primitives (`customers`, `vendors`, `food`, `domains`, `medical`) are removed;
`people`, `trips`, and `projects` are re-authored as the role/container
primitives `people`, `efforts/trips/`, and `efforts/projects/`, joined by the new
`efforts`, `library`, `atlas`, and `cases` primitives; `identity` stays unchanged.
Every content-type *and operation* re-points its `requires:` to the role folder
its pages and the entities they link live in; the three shipped recipes
(`family`, `work-os`, `personal`) install the new set; and the committed starters
are regenerated to match. A **container** is a bounded instance with its
own identity (a trip, a medical case, a project) declared by a `container_mode`
of `folder` (exclusive material, homed in `efforts/<type>/<instance>/`) or `hub`
(shared material, a single `efforts/<type>/<instance>.md` page whose members join
by the `parent:` relation). Every role folder and every folder-mode container is
seeded with a README and a `genre: moc` `_index.md` map so the vault is
navigable, and editable in plain Obsidian, on day one.

The users are the kit author and the produced vault's maintaining agent — and,
**affected**, the downstream people who read and file through the Obsidian UI:
they must learn the four role folders and the container `_index.md` convention to
navigate and create pages. The `_index.md` MOCs and the RFC-0008 Bases lenses are
the mitigation. Success is a catalog whose ontology/container primitives, content
-type `requires:`, recipes, and regenerated starters all render the four-role
tree, with the RFC-0008 area axis untouched and the synthesis-gating and
operation/search re-key left to their sibling specs.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Reshape the produced-vault layout to the four roles by re-authoring the
  catalog in one coordinated PR-series: replace the entity-kind ontology
  primitives with the four role-folder ontologies (`people`, `efforts`,
  `library`, `atlas`) plus the per-type container registries
  (`efforts/trips/`, `efforts/cases/`, `efforts/projects/`); re-point every
  content-type *and operation* `requires:` that names a removed ontology to the
  role folder its pages and linked entities live in (a dangling `requires:`
  fails `resolve_dependencies` at install — `onboarding-pack`'s `customers`
  dependency is the live example); update the `family`/`work-os`/`personal`
  recipe `primitives:` lists; and regenerate the committed starters.
- Seed every role folder and every folder-mode container registry with a
  `README.md` and a `genre: moc` `_index.md` map page.
- Declare `container_mode` (`folder` | `hub`) in each container primitive's
  `primitive.yaml` `config:` block.
- Keep RFC-0008's `workspaces:` field and the shipped workspace `.base` files
  byte-unchanged (they reference no folder this spec moves).
- Keep the RFC-0004 `identity.md` stub at the vault root unchanged — the §C
  reshape is scoped to what lives under `wiki/`.
- Write into a vault only through the kit's render/copy and `safe_write`
  paths — never a direct `write_text`.
- Register the now-stale operation SKILLs, `wiki search` folder globs, and any
  hand-authored starter seed-page `type:`/folder references as deferred in
  `docs/backlog.md#role-folders-and-containers`.

### Ask first

- Changing the four-role set, or adding a fifth top-level `wiki/` role folder.
- Adding an `efforts/<type>` container registry beyond `trips`, `cases`, and
  `projects`, or changing a container's declared `container_mode`.
- Dropping any content-type or operation primitive a shipped recipe installs
  (re-pointing `requires:` is in scope; removing a capability is not).

### Never do

- Introduce a kind-keyed folder (`meetings/`, `records/`, `decisions/`), a
  lifecycle folder (`archive/`, `someday/`), or an area folder (`areas/`,
  `domains/`). Kind is `subtype`, lifecycle is `status`, area is `workspaces:`.
  *(structural)*
- Re-introduce a `domain` facet or a `domains/` folder — the area axis is
  RFC-0008's `workspaces:`; an area is a workspace with an optional `genre: moc`
  page in `atlas/`. *(structural)*
- Add a genre subfolder inside a folder-mode container
  (`efforts/trips/japan-2026/sources/`, `/records/`, `/drafts/`); container
  contents are flat, the only permitted subfolder is a non-semantic bulk sink
  (`_assets/`, `_working/`). *(structural)*
- Add a runtime dependency, a new top-level kit-source directory, a new Python
  module, or a new aggregator — the reshape is primitive/recipe/seed authoring
  over the existing render + managed-region machinery. *(structural)*
- Implement the `atlas/` synthesis-proposal gating (`capture-synthesis-gating`
  owns it) or re-key operation contracts / `wiki search` / `search.py` from
  folder-globs (`operations-and-search-rekey` owns it) in this spec.

## Testing Strategy

Goal-based here means: parse the rendered/shipped artifact and assert its shape;
no production logic mirrors the assertion.

- **Ontology/container primitive set** (the catalog contains exactly the four
  role ontologies + the three container registries + the unchanged `identity`;
  the five collapsed ontologies — `customers`, `vendors`, `food`, `domains`,
  `medical` — are absent): **goal-based** — enumerate `templates/ontologies/*/`.
- **Every role folder and folder-mode container ships a README + a `genre: moc`
  `_index.md`**: **goal-based** — parse the seeded `files/wiki/**/_index.md`
  frontmatter and assert it carries all six `required:` fields with
  schema-valid values: `genre: moc`, `subtype: moc`, `status: active`,
  `provenance: synthesized`, and literal `YYYY-MM-DD` `created`/`modified`
  dates (literal — never a generated/templated token — so starter
  regeneration stays byte-stable).
- **`container_mode` declared and well-formed** (each container primitive's
  `config.container_mode` is `folder` or `hub`; `trips`/`cases` are `folder`,
  `projects` is `hub`): **goal-based** — parse the three container
  `primitive.yaml` `config` blocks; the kit core never branches on the value, so
  there is no production invariant to drive red-green.
- **No dangling `requires:`** (no content-type *or operation* `requires:` names a
  removed ontology; every named primitive exists): **goal-based** + proven by the
  **integration** test below (`resolve_dependencies` accepts every recipe's
  catalog, including `work-os`, whose `onboarding-pack` operation currently names
  the removed `customers`).
- **Layout renders** (`wiki init` over each shipped recipe creates
  `wiki/{people,efforts,library,atlas}/` and the per-type `efforts/<type>/`
  registries, and `wiki doctor` reports no orphan/missing): **goal-based**,
  exercised by an **integration** test against `tmp_path`.
- **Starters regenerated** (`python starters/regenerate.py --check` exits 0):
  **goal-based** — the existing non-slow `test_starters_regenerable` gate.
- **RFC-0008 untouched** (shipped `templates/workspaces/*/files/*.base` files
  byte-unchanged; `workspaces` field present in the rendered schema): **goal
  -based**.

## Acceptance Criteria

- [x] `templates/ontologies/` contains exactly `people`, `efforts`, `library`,
      `atlas`, `trips`, `cases`, `projects`, and the unchanged `identity`; the
      collapsed `customers`, `vendors`, `food`, `domains`, and `medical`
      ontology primitives are removed.
- [x] The `people` ontology seeds `wiki/people/` and its README documents that
      people, organizations, vendors, and customers are all node `subtype`s in
      one folder (the former `customers`/`vendors` homes collapse here).
- [x] The `library` ontology seeds `wiki/library/` (capture & reference,
      absorbing the former `food` and per-record `medical` material); the
      `atlas` ontology seeds `wiki/atlas/` (synthesis); each ships a README and
      a `genre: moc` `_index.md`.
- [x] Every seeded `_index.md` carries all six `required:` schema fields with
      schema-valid values — `genre: moc`, `subtype: moc`, `status: active`,
      `provenance: synthesized`, and literal `created`/`modified` dates (a
      `moc`-genre page is navigational and not content-type-produced, so its
      `subtype` mirrors its `genre`; the content-type-owned `subtype` managed
      region is untouched).
- [x] The `efforts` ontology seeds `wiki/efforts/` with a README and a
      `genre: moc` `_index.md`; the `trips`, `cases`, and `projects` container
      registries each seed `wiki/efforts/<type>/` with a README and a
      `genre: moc` `_index.md`.
- [x] Each container primitive declares `config.container_mode` ∈
      {`folder`, `hub`}: `trips` and `cases` are `folder`, `projects` is `hub`;
      a goal-based test parses each container manifest and asserts the value.
- [x] No content-type *or operation* `primitive.yaml` `requires:` names a removed
      ontology, and no re-point silently drops a dependency that is not itself
      removed (a relocation preserves every surviving dep; a removal is listed):
      the plan's old→new re-pointing table is the reference, every named target
      primitive exists, and `resolve_dependencies` accepts the full catalog. The
      live cases the table must cover include `onboarding-pack` (`customers`→
      `people`, keeping `projects`/`decision`/`customer-feedback`),
      `medical-record` (`medical`→`library`+`cases`, keeping `people`),
      `customer-feedback` (drop `customers`, keep `people`, add `library`),
      `recipe`/`receipt`/`tax-document` (`food`/`vendors`→`library`, adding
      `people` where a vendor node is stubbed), and `decision`→`library`
      (capture; any `atlas/` decision-synthesis is `capture-synthesis-gating`).
- [x] `wiki init` over `family`, `work-os`, and `personal` renders
      `wiki/{people,efforts,library,atlas}/` and the recipe's per-type
      `efforts/<type>/` registries; `resolve_dependencies` accepts each recipe
      and `wiki doctor` reports no orphan/missing files.
- [x] No produced-vault folder is kind-keyed, lifecycle-keyed, or area-keyed,
      and no folder-mode container carries a genre/lifecycle subfolder: a grep
      asserts no kind folder is seeded by any primitive — both the
      ontology-seeded `customers/`, `vendors/`, `food/`, `medical/`,
      `domains/` and the content-type-seeded `meetings/`, `actions/`,
      `decisions/`, `interviews/`, `customer-feedback/`, `receipts/`, `tax/`,
      `stakeholder-updates/`, `vendor-contracts/`, plus the
      lifecycle/area/synthesis-subfolder set `records/`, `sources/`,
      `drafts/`, `archive/`, `someday/`, `upcoming/`, `past/`, `areas/` (only
      `_assets/`/`_working/` bulk sinks are permitted inside a container).
- [x] The shipped `templates/workspaces/*/files/*.base` files are
      byte-unchanged and the rendered schema still carries `workspaces`.
- [x] The committed starters (`starters/{family,work-os}/`, the
      `conflict-pending` example vault) are regenerated so their rendered tree
      matches the four-role layout — the hand-authored `starters/_seed/**`
      pages are **relocated** into the role folders (so no committed starter
      retains a removed kind/ontology folder) and their cross-folder wikilinks
      re-pointed; their `type:`→`genre`/`subtype` frontmatter-value faceting
      stays deferred. `python starters/regenerate.py --check` exits 0 and
      `python starters/check_coverage.py` exits 0.
- [x] Every folder reference in the vault-side content-type ingest `SKILL.md`
      docs is re-pointed so none names a deleted or re-homed folder: entity-stub
      references (person/org/vendor/customer node) home in `people/`, page-home
      references home in `library/` (capture) or the re-homed `efforts/<type>/`
      registries, so no shipped SKILL instructs an agent to write into a removed
      kind/ontology folder. The orthogonal `type:`→`genre`/`subtype` value
      faceting in those SKILLs and the `_templates`, the six stale operation
      SKILLs, the `wiki search`/`search.py` folder globs, and the hand-authored
      starter seed-page `type:`/folder references are registered as deferred
      (deferred: backlog.md#role-folders-and-containers). The existing
      `faceted-frontmatter-schema` backlog entries that route the vault-side
      content-type doc re-key and the starter seed-page faceting to this spec /
      `recipe-organization-model` are reconciled to point at the spec that now
      owns each (this spec absorbs the recipe-rewrite + starter-regen).
- [x] `ruff check llm_wiki_kit tests`, `ruff format --check llm_wiki_kit tests`,
      `mypy llm_wiki_kit tests`, and `pytest -m 'not slow'` pass.

## Assumptions

- Technical: ontology primitives are folder+README seeds copied verbatim — a
  folder exists because a file lives in it, with no ontology render logic or
  build var; the reshape is seed/manifest authoring, not aggregator code
  (source: `templates/ontologies/*/files/wiki/<f>/README.md`; `render.py` has no
  ontologies region).
- Technical: content-types pull their folder via `requires:` (resolved
  transitively) and recipes list leaf primitives, so collapsing the ontology set
  ripples into content-type `requires:` and the three recipe `primitives:` lists
  (source: `recipes/family.yaml` header; 10 content-type `requires:` blocks;
  `primitives.resolve_dependencies`).
- Technical: nine content-type primitives *also* seed a kind-keyed
  `files/wiki/<kind>/README.md` of their own (`action-item`→`actions/`,
  `customer-feedback`→`customer-feedback/`, `decision`→`decisions/`,
  `interview`→`interviews/`, `meeting`→`meetings/`, `receipt`→`receipts/`,
  `stakeholder-update`→`stakeholder-updates/`, `tax-document`→`tax/`,
  `vendor-contract`→`vendor-contracts/`) — folders are *not* ontology-only.
  Because the produced vault holds exactly four role folders and every capture
  page homes in `library/`, these nine seed folders are removed alongside the
  five collapsed ontologies; their per-kind guidance now lives in the `library`
  README plus each type's ingest `SKILL.md`/`_template`. (`medical-record`,
  `recipe`, `trip-doc` seed no kind folder.) Source: starter trees
  `starters/{family,work-os}/wiki/`; `templates/content-types/*/files/wiki/`.
- Technical: no `_index.md`/MOC mechanism exists today, so the MOC pages are
  newly introduced as seed files; their bodies are vault-runtime Bases/Dataview,
  not kit-rendered (source: grep for `_index.md`/MOC across `templates`/`core`/
  `llm_wiki_kit` returned nothing).
- Technical: `container_mode` has a home in `primitive.yaml`'s free-form
  `config:` dict — no `models.py` change is required (source: `models.py`
  `Primitive.config: dict[str, object]`).
- Technical: the `parent` list-relation and `genre: moc` this spec consumes
  shipped in `faceted-frontmatter-schema`; this spec adds no frontmatter facets
  (source: `core/files/frontmatter.schema.yaml`).
- Process: this spec lands after `faceted-frontmatter-schema` (shipped) and
  before `operations-and-search-rekey` and `capture-synthesis-gating`; per user
  direction (2026-06-16) it absorbs the recipe-rewrite + starter-regeneration
  originally sketched for `recipe-organization-model`, which then narrows to
  workspace-primitive coordination — a follow-on-scope shift flagged for the RFC
  in the implementing PR (source: RFC-0009 §Follow-on/Sequencing; user
  confirmation 2026-06-16).
- Process: reshaping produced-vault folders and renaming/removing ontology
  primitive directories is authorized by RFC-0009 §C and is not gated by the
  kit's new-top-level-dir RFC rule, which governs the kit source tree
  (source: RFC-0009 §C; AGENTS.md kit-vs-vault scope split).
- Product: the entity→role mapping is `people`+`vendors`+`customers`→`people/`,
  `projects`→`efforts/projects/` (hub), `trips`→`efforts/trips/` (folder),
  `medical`→`efforts/cases/` (folder) + records in `library/`, `food`→`library/`,
  `domains`→dropped (a `workspaces:` lens + optional `atlas/` MOC), `identity`→
  unchanged at the vault root (source: user confirmation 2026-06-16).
- Product: end users are affected — they must learn the four role folders and
  the container `_index.md` convention to file and navigate; the `_index.md`
  MOCs, Properties autocomplete, and RFC-0008 Bases lenses are the mitigations
  (source: user confirmation 2026-06-16).
