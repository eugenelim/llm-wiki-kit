# Plan: role-folders-and-containers

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The reshape is catalog authoring, not code: an ontology primitive is a folder
plus a verbatim-copied README, so the four-role layout is realized by deleting
the five entity-kind ontologies (`customers`, `vendors`, `food`, `domains`,
`medical`), authoring the four role-folder ontologies (`people`, `efforts`,
`library`, `atlas`) and three per-type container registries under `efforts/`
(`trips` and `projects` re-homed, plus the new `cases`) — `identity` stays
unchanged — and seeding each with a README and a new `genre: moc` `_index.md`. The MOC pages are new seed files — there is
no kit-side query engine, so their bodies are vault-runtime Bases/Dataview, not
rendered. With the folder set changed, every content-type re-points its
`requires:` to the role folder its pages and the entities it links live in (the
re-pointing table under Design), the three recipes drop the removed ontologies
and add the role set, and the committed starters are regenerated. The riskiest
parts are (a) leaving a content-type `requires:` pointing at a deleted ontology
(`resolve_dependencies` aborts) and (b) starter drift (the non-slow
`test_starters_regenerable` gate). Order: role ontologies → container registries
→ remove-old + re-point requires → recipes → vault-side doc re-point + backlog →
end-to-end render + regenerate + lens-unregressed proof.

## Constraints

- **RFC-0009 §C/§D** — the four-role layout, the folders-key-stable-roles rule,
  containers as instances with `container_mode` (folder|hub), `efforts/<type>/`
  homing, flat-inside-container with `_index.md` MOC.
- **RFC-0008** — `workspaces:` axis and shipped `.base` lenses untouched; an
  area is a workspace, never a folder.
- **RFC-0004** — `identity.md` at the vault root is unchanged.
- **ADR-0011 / faceted-frontmatter-schema** — `genre`/`subtype`/`parent` already
  shipped; this spec consumes `genre: moc` and `parent:`, adds no facets.
- **ADR-0006** — managed-region contribution mechanism (unchanged; no new
  region added here).
- **AGENTS.md** — kit writes into a vault only via render/copy + `safe_write`;
  produced-vault folders are not gated by the kit's new-top-level-dir RFC rule.

## Construction tests

Most construction tests live per-task below. Cross-cutting:

**Integration tests:** one end-to-end test renders a temp vault via `wiki init`
over each shipped recipe; asserts `resolve_dependencies` accepts the recipe, the
four role folders and the recipe's `efforts/<type>/` registries exist on disk,
`wiki doctor` reports no orphan/missing, the shipped `.base` files are
byte-unchanged, and the rendered schema carries `workspaces`.
**Manual verification:** open a rendered vault in Obsidian ≥1.9.10; confirm the
four role folders browse, the `_index.md` MOCs render, and a folder-mode
container (`efforts/trips/<trip>/`) groups its contents by its `_index.md`.

## Design (LLD)

### Design decisions

- An ontology primitive carries its folder by shipping `files/wiki/<folder>/`
  with a README; the reshape is therefore add/delete/rename of these seed trees
  plus `requires:` edits — no `render.py`/`install.py`/`models.py` change. Traces
  to: AC "ontology set", AC "layout renders" · no `contracts/`.
- `container_mode` lives in `primitive.yaml`'s existing free-form `config:` dict
  (not a new typed model field), read only by the construction test and by the
  vault-side agent docs; the kit core does not branch on it. Traces to: AC
  "container_mode declared".
- `_index.md` MOC pages are seed files with a Bases/Dataview body; the kit does
  not generate or update them. Their frontmatter is pinned and uniform across
  every role folder and container registry: `genre: moc`, `subtype: moc`
  (a navigational page is not content-type-produced, so its subtype mirrors its
  genre — the content-type-owned `subtype` managed region is *not* touched),
  `status: active`, `provenance: synthesized`, and **literal** `created` /
  `modified` dates (`2026-06-16`). Literal dates — not a templated
  `{{date:…}}` token — because seed files are copied byte-for-byte (no date
  substitution in `render.py`) and `regenerate.py --check` byte-compares; a
  generated token would either flap the gate or leave a literal `{{…}}` in the
  shipped page. Traces to: AC "role folder + container ship `_index.md`"; AC
  "every `_index.md` carries all six required fields".
- No content-type writes `atlas/` in this spec: `atlas/` is seeded as an empty
  role folder with its `genre: moc` `_index.md`, and synthesis pages arrive
  through the `capture-synthesis-gating` proposal flow (or by hand) later.
  Extracted types — including `decision` — home in `library/` (capture); §E
  reserves the gated peak for human-gated synthesis, so homing an ingested type
  there ungated would erode it. Traces to: spec Never-do (gating deferred);
  re-pointing table.
- `library`, `atlas`, and `efforts` are each listed **explicitly** in every
  recipe `primitives:` list as a defensive guarantee, not left to transitive
  arrival. `atlas` is pulled by nothing (synthesis peak), so it *must* be
  explicit. `library` and `efforts` *would* arrive transitively today
  (`library` via each capture content-type's re-pointed `requires:`; `efforts`
  via each `efforts/<type>/` registry's `requires: [efforts]`, itself pulled by
  a content-type) — but each chain is single-threaded per recipe, so a future
  edit that drops the one content-type anchoring the chain would silently lose
  the role folder and its `_index.md`. Listing all three explicitly makes the
  four-role floor independent of which content-types a recipe carries. A future
  reader should not collapse the explicit listing assuming the transitive path
  covers it. Traces to: AC "layout renders".

### Data & schema

- `templates/ontologies/`: **add** `people`, `efforts`, `library`, `atlas`
  (role-folder ontologies, each `files/wiki/<role>/README.md` +
  `files/wiki/<role>/_index.md`); **add** `trips`, `cases`, `projects` container
  registries (each `files/wiki/efforts/<type>/README.md` + `_index.md`,
  `config.container_mode`, and `requires: [efforts]` so the base folder + its MOC
  arrive transitively); **remove** `customers`, `vendors`, `food`, `domains`,
  `medical`; **keep** `identity` byte-unchanged.
- `requires:` re-pointing table — **old → new**, built from the on-disk
  manifests. A relocation keeps every surviving dep; only a removed ontology is
  swapped. `library` is added to every content-type whose page is capture/
  reference; `people` is added/kept wherever the type stubs a person/org/vendor/
  customer node (the former `customers`/`vendors` homes).

  | primitive | current `requires:` | new `requires:` | page home |
  |---|---|---|---|
  | `meeting` (ct) | `people` | `people`, `library` | `library/` |
  | `interview` (ct) | `people` | `people`, `library` | `library/` |
  | `recipe` (ct) | `food` | `library` | `library/` |
  | `receipt` (ct) | `vendors` | `people`, `library` | `library/` (vendor node → `people/`) |
  | `tax-document` (ct) | `vendors` | `people`, `library` | `library/` |
  | `medical-record` (ct) | `medical`, `people` | `people`, `library`, `cases` | `library/` (case → `efforts/cases/`) |
  | `trip-doc` (ct) | `trips`, `people` | `trips`, `people` | `efforts/trips/<trip>/` |
  | `vendor-contract` (ct) | `[]` | `people`, `library` | `library/` |
  | `customer-feedback` (ct) | `customers`, `people` | `people`, `library` | `library/` |
  | `stakeholder-update` (ct) | `people`, `projects` | `people`, `projects`, `library` | `library/` (project → `efforts/projects/`) |
  | `action-item` (ct) | `people` | `people`, `library` | `library/` |
  | `decision` (ct) | `[]` | `people`, `library` | `library/` (capture; `atlas/` synthesis is `capture-synthesis-gating`) |
  | `onboarding-pack` (op) | `customers`, `projects`, `decision`, `customer-feedback` | `people`, `projects`, `decision`, `customer-feedback` | — |

  The two rows whose **current** `requires:` is `[]` (`vendor-contract`,
  `decision`) are pure additions — they had no prior dep to preserve, so the
  "no silent drop" check is trivially satisfied for them. No other operation
  `requires:` names a removed ontology (`projects` survives, re-homed).
  `decision` is homed in `library/`, **not** `atlas/`: it is an
  extracted/ingested type, and §E reserves the gated `atlas/` peak for
  human-gated synthesis — so no content-type writes `atlas/` in this spec.

- `recipes/{family,work-os,personal}.yaml`: each `primitives:` list drops the
  five removed ontologies and **lists `atlas`, `library`, and `efforts`
  explicitly** (the defensive guarantee above). `people` and the surviving
  `trips`/`projects` registries stay listed where a recipe already names them
  (and also arrive transitively); `cases` arrives transitively via
  `medical-record` (family only).

### Interfaces & contracts

No `contracts/` surface — the produced-vault folder layout and the seed files
*are* the shipped artifact, verified by parsing the rendered tree. No
REST/event/RPC.

## Tasks

### T1: Role-folder ontologies authored and seeded

**Depends on:** none
**Touches:** templates/ontologies/people/**, templates/ontologies/efforts/**, templates/ontologies/library/**, templates/ontologies/atlas/**, tests/unit/test_role_folder_ontologies.py

**Tests:**
- Goal-based: `templates/ontologies/` contains `people`, `efforts`, `library`,
  `atlas`; each ships `files/wiki/<role>/README.md` and a
  `files/wiki/<role>/_index.md` whose frontmatter declares `genre: moc` (AC:
  role ontologies; `_index.md` MOC).
- Goal-based: the `people` README documents people/orgs/vendors/customers as
  node `subtype`s in the one folder (AC: people collapse).

**Approach:**
- Author the four ontology primitives (`primitive.yaml` `kind: ontology`,
  `requires: []`, `contributes_to: []`), each seeding its role folder README +
  `genre: moc` `_index.md`. Carry the capture-vs-synthesis distinction into the
  `library`/`atlas` READMEs.

**Done when:** `pytest tests/unit/test_role_folder_ontologies.py` green; the four
role folders each carry a README and a `genre: moc` `_index.md`.

### T2: Container registries authored with `container_mode`

**Depends on:** T1
**Touches:** templates/ontologies/trips/**, templates/ontologies/cases/**, templates/ontologies/projects/**, tests/unit/test_container_primitives.py

**Tests:**
- Goal-based: each container primitive's `config.container_mode` ∈
  {`folder`, `hub`}; `trips`/`cases` are `folder`, `projects` is `hub`; each
  declares `requires: [efforts]` (AC: container_mode).
- Goal-based: each container registry seeds `files/wiki/efforts/<type>/README.md`
  and a `genre: moc` `_index.md`; no genre/lifecycle subfolder is seeded inside
  any container — including the `upcoming/`/`past/` the current `trips` README
  mandates (AC: efforts registries; Never-do genre/lifecycle subfolder).

**Approach:**
- Re-home the existing `trips`/`projects` ontologies under `efforts/<type>/` and
  add `cases`; set `config.container_mode` and `requires: [efforts]`; **rewrite**
  (do not carry forward) the `trips` README — drop its `upcoming/`/`past/`
  subfolder convention, since lifecycle is the `status` facet, not a location.
  Author each registry's README + `genre: moc` `_index.md` (the registry MOC
  runs `GROUP BY genre` over members).

**Done when:** `pytest tests/unit/test_container_primitives.py` green; the three
`efforts/<type>/` registries exist with `container_mode` declared.

### T3: Collapsed ontologies + content-type kind-folder seeds removed; content-type *and operation* `requires:` re-pointed

**Depends on:** T1, T2
**Touches:** templates/ontologies/{customers,vendors,food,domains,medical}/ (deleted), templates/content-types/{action-item,customer-feedback,decision,interview,meeting,receipt,stakeholder-update,tax-document,vendor-contract}/files/wiki/ (deleted kind-folder README seeds), templates/content-types/*/primitive.yaml, templates/operations/onboarding-pack/primitive.yaml, tests/unit/test_requires_repoint.py

**Tests:**
- Goal-based: `customers`, `vendors`, `food`, `domains`, `medical` ontology dirs
  are gone; no content-type *or operation* `requires:` names a removed ontology;
  every named `requires:` resolves to an existing primitive; and for each row of
  the re-pointing table the *surviving* deps from the current manifest are still
  present (no silent capability drop) (AC: ontology set; no dangling requires).
- Goal-based: no content-type primitive seeds a `files/wiki/<kind>/` folder
  any longer — the nine kind-folder README seeds (`actions/`,
  `customer-feedback/`, `decisions/`, `interviews/`, `meetings/`, `receipts/`,
  `stakeholder-updates/`, `tax/`, `vendor-contracts/`) are gone; the only
  `files/wiki/` seed trees a content-type ships are none (its pages home in the
  role folders the ontologies seed) (AC: no kind-keyed folder; spec Assumption
  on content-type folder seeds).
- Integration: `primitives.resolve_dependencies` accepts the full catalog for
  every recipe — including `work-os`, whose `onboarding-pack` currently names the
  removed `customers` (AC: no dangling requires).

**Approach:**
- Delete the five ontology primitive dirs.
- Delete the nine content-type `files/wiki/<kind>/` seed dirs (a content-type
  no longer owns a folder — its pages home in `library/`, which the `library`
  ontology seeds; per-kind guidance moves to the `library` README + each type's
  ingest `SKILL.md`/`_template`). `medical-record`, `recipe`, `trip-doc` seed
  no kind folder, so they are untouched here.
- Re-point each content-type's `requires:` per the Design old→new table.
- Re-point `onboarding-pack`'s operation `requires:` (`customers`→`people`,
  keeping `projects`/`decision`/`customer-feedback`); confirm no other operation
  names a removed ontology.

**Done when:** the goal-based + integration assertions pass; `grep -r` finds no
`requires:` naming a deleted ontology across `templates/content-types` and
`templates/operations`, and no `templates/content-types/*/files/wiki/`
directory remains.

### T4: Recipes install the role-folder set

**Depends on:** T3
**Touches:** recipes/family.yaml, recipes/work-os.yaml, recipes/personal.yaml, tests/integration/test_recipe_role_layout.py, and the existing layout/closure tests that bake in the old folder set — tests/integration/test_family_recipe.py, tests/integration/test_work_os_recipe.py, tests/integration/test_personal_recipe.py, tests/unit/test_recipes.py (and any unit test asserting the catalog's ontology set, e.g. tests/unit/test_models.py / tests/unit/test_starter_seed_coverage.py) updated to the four-role layout

**Tests:**
- Integration: `wiki init` over each recipe renders `wiki/{people,efforts,
  library,atlas}/` and the recipe's `efforts/<type>/` registries; `wiki doctor`
  reports no orphan/missing (AC: layout renders).
- Goal-based: no recipe `primitives:` list names a removed ontology (AC: ontology
  set).

**Approach:**
- Update each recipe's `primitives:` list — drop the five removed ontologies and
  **add `atlas`, `library`, and `efforts` explicitly** to each of `family`,
  `work-os`, and `personal` (nothing pulls `atlas`; `library`/`efforts` are
  listed defensively so the role folders exist regardless of which content-types
  a recipe carries — see the §Design decision). `people` and the surviving
  `trips`/`projects` registries stay where already listed. Refresh each recipe's
  header comment/description prose that names a removed ontology.

**Done when:** the integration test renders all three layouts cleanly and
`resolve_dependencies` accepts each recipe.

### T5: Vault-side content-type folder references re-pointed; deferrals registered

**Depends on:** T3
**Touches:** templates/content-types/*/files/skills/**/SKILL.md, docs/backlog.md

**Tests:**
- Goal-based: no vault-side content-type ingest `SKILL.md` references a removed
  ontology folder (`customers/`, `vendors/`, `food/`, `medical/`, `domains/`) or
  a removed content-type kind folder (`meetings/`, `actions/`, `decisions/`,
  `interviews/`, `customer-feedback/`, `receipts/`, `tax/`,
  `stakeholder-updates/`, `vendor-contracts/`); person/org/vendor/customer
  entity stubs reference `people/`; page-home references point at `library/`
  (capture) or the re-homed `efforts/<type>/` registries (AC: entity-stub
  re-point; no SKILL points at a deleted/re-homed folder).
- Goal-based: `docs/backlog.md#role-folders-and-containers` exists and names the
  residual `type:`→`genre`/`subtype` value faceting in the content-type docs and
  `_templates`, the six stale operation SKILLs, the `wiki search`/`search.py`
  folder globs, and the starter seed-page deferral; and the existing
  `faceted-frontmatter-schema` backlog entries that pointed the vault-side doc
  re-key + starter seed-page faceting at this spec / `recipe-organization-model`
  are reconciled to the spec that now owns each (AC: deferral registered;
  CONVENTIONS § Spec-metadata invariant 4 — no dangling deferral pointer).

**Approach:**
- Re-point **every folder reference** in the vault-side content-type ingest
  `SKILL.md` docs so none points at a deleted or re-homed folder — shipping a
  SKILL that tells an agent to write into a folder the reshape removed is a
  day-one correctness defect for the produced vault (review Concern 5), not
  cosmetic drift:
  - **entity stubs** (person/org/vendor/customer node) → `people/` (the former
    `customers/`/`vendors/` stub homes collapse here);
  - **page-home** (where the ingested page itself lands) → `library/` for every
    capture type (`meeting`, `interview`, `decision`, `action-item`,
    `customer-feedback`, `receipt`, `tax-document`, `vendor-contract`,
    `recipe`, `medical-record`), and `efforts/cases/` for the case dimension of
    `medical-record`;
  - **re-homed container** references (`wiki/trips/`→`wiki/efforts/trips/`,
    `wiki/projects/`→`wiki/efforts/projects/`) in `trip-doc`/`stakeholder-update`.
- This is folder-path re-pointing only. The orthogonal `type:`→`genre`/`subtype`
  **frontmatter-value** faceting in these SKILLs and the `_templates` is *not*
  touched here — it changes field values, not paths, and is the deferred
  vault-side-doc re-key.
- Register the out-of-scope re-keys under the new backlog anchor
  `docs/backlog.md#role-folders-and-containers`: (a) the residual
  `type:`→`genre`/`subtype` faceting in content-type docs and `_templates`;
  (b) the six stale operation SKILLs; (c) the `wiki search`/`search.py` folder
  globs; (d) the hand-authored starter seed-page `type:`/folder references
  (seed pages stay verbatim — `regenerate.py --check` is their only gate).
- Update the `faceted-frontmatter-schema` backlog entries so no pointer dangles.

**Done when:** both goal-based tests pass; no vault-side doc stubs an *entity*
into a removed ontology folder; the backlog anchor names every deferred re-key;
no backlog deferral pointer names a spec that no longer owns the work.

### T6: End-to-end layout proven; starters regenerated; lenses unregressed

**Depends on:** T1, T2, T3, T4, T5
**Touches:** tests/integration/test_role_layout_render.py, starters/**, docs/guides/how-to/_examples/conflict-pending/**

**Tests:**
- Integration: `wiki init` a temp vault per recipe; assert the four role folders
  + `efforts/<type>/` registries on disk, `type`-free schema, `workspaces`
  present, shipped `.base` files byte-unchanged (AC: layout renders; RFC-0008
  untouched).
- Goal-based: no primitive seeds a kind/lifecycle/area folder or a container
  genre/lifecycle subfolder — the forbidden seed-folder set is the
  ontology-kind `customers/`, `vendors/`, `food/`, `medical/`, `domains/`; the
  content-type-kind `meetings/`, `actions/`, `decisions/`, `interviews/`,
  `customer-feedback/`, `receipts/`, `tax/`, `stakeholder-updates/`,
  `vendor-contracts/`; and the lifecycle/area/synthesis-subfolder
  `records/`, `sources/`, `drafts/`, `archive/`, `someday/`, `upcoming/`,
  `past/`, `areas/` (only `_assets/`/`_working/` permitted inside a
  container) (AC: no kind/lifecycle/area folder).
- Goal-based: `python starters/regenerate.py --check` exits 0 (AC: starters
  regenerated).

**Approach:**
- Add the end-to-end test; run `python starters/regenerate.py --apply` to rebuild
  the committed starters against the new layout (seed pages stay verbatim — their
  faceting is the registered deferral).

**Done when:** the integration + goal-based tests are green,
`starters/regenerate.py --check` exits 0, and `pytest -m 'not slow'`,
`ruff check`, `ruff format --check`, `mypy llm_wiki_kit tests` all pass.

## Rollout

- **Delivery:** atomic within the kit — T1–T6 land as a coordinated PR-series
  (a recipe referencing a deleted ontology fails `resolve_dependencies`; the
  intermediate state is un-shippable). T1/T2 (additive ontologies) may land
  before the removals in T3. No user vaults exist (pre-release); no migration;
  reversible by revert.
- **Infrastructure:** none.
- **External-system integration:** none.
- **Deployment sequencing:** lands after `faceted-frontmatter-schema` (shipped);
  `operations-and-search-rekey` and `capture-synthesis-gating` build on the
  folders defined here and land after.

## Risks

- **Dangling `requires:` aborts install.** `resolve_dependencies` rejects a
  reference to a deleted ontology. Mitigation: T3 deletes ontologies and
  re-points `requires:` together; the T3 integration test runs
  `resolve_dependencies` over the full catalog.
- **Starter drift breaks the non-slow gate.** Changing the rendered tree drifts
  the committed starters. Mitigation: T6 regenerates them and asserts
  `regenerate.py --check` exits 0.
- **Operation SKILLs / `wiki search` glob removed folders.** Six operation SKILLs
  and `search.py` glob the old entity-kind folders; they go stale on landing.
  Out of scope (re-keyed in `operations-and-search-rekey`); registered in
  `docs/backlog.md#role-folders-and-containers` in T5.
- **Drift with RFC-0008's shipped lenses.** The `.base` files must stay
  byte-unchanged. Mitigation: T6 asserts byte-equality.

## Changelog

- 2026-06-16: pre-EXECUTE adversarial review response. (Blocker) Pinned the
  full MOC `_index.md` frontmatter contract — `genre: moc`, `subtype: moc`,
  `status: active`, `provenance: synthesized`, literal `created`/`modified`
  dates — in the spec AC + Testing Strategy and plan §Design, with a goal-based
  assertion on all six required fields; the content-type-owned `subtype` managed
  region is left untouched (a navigational MOC mirrors its genre). (Blocker)
  Specified literal dates so `regenerate.py --check` stays byte-stable.
  (Concern) Recipes now list `efforts` explicitly alongside `atlas`/`library`
  rather than relying on a single-threaded transitive chain. (Concern) Pulled
  the content-type ingest-SKILL **page-home** folder re-key into T5 (a shipped
  SKILL pointing at a deleted folder is a day-one defect); deferred only the
  orthogonal `type:`→`genre`/`subtype` value faceting. (Nits) Annotated the
  `[]`-baseline `requires:` rows as additions-only.
- 2026-06-16: pre-EXECUTE reconciliation with the on-disk catalog. Found that
  nine **content-type** primitives seed their own kind-keyed `files/wiki/<kind>/`
  folder (the spec's mental model treated folders as ontology-only); these
  violate the "exactly four role folders" Objective and the T6 grep gate (which
  already forbids `meetings/`/`decisions/`), so T3 now deletes them too and the
  spec gains an Assumption + a widened "no kind-keyed folder" AC. Widened the T6
  forbidden-folder grep to the full ontology-kind + content-type-kind set.
  Clarified T5: only **entity-stub** references into removed *ontology* folders
  are re-pointed (gated); content-type ingest-SKILL **page-home** folder
  references and the `type:`→`genre`/`subtype` faceting are deferred to the
  backlog anchor alongside the operation SKILLs and search globs. Pulled the
  existing layout/closure tests (`test_{family,work-os,personal}_recipe.py`,
  `test_recipes.py`, catalog-set unit tests) into T4's scope — a layout change
  drifts them by construction. Confirmed `_seed/` pages stay verbatim (their
  relocation is the registered deferral; `regenerate.py --check` is the gate).
- 2026-06-16: spec-mode adversarial review — rebuilt the `requires:` re-pointing
  table from the on-disk manifests as old→new (the draft table dropped surviving
  deps like `medical-record`'s `people` and `stakeholder-update`'s `projects`);
  brought operation `requires:` into scope (T3) after finding `onboarding-pack`'s
  `customers` dependency would dangle and fail `resolve_dependencies` over
  `work-os`; re-homed `decision` from the gated `atlas/` to `library/` (it is an
  extracted type — §E); made T2 rewrite the `trips` README to drop its
  `upcoming/`/`past/` lifecycle subfolders and widened the T6 forbidden-folder
  grep; reclassified the `container_mode` check from TDD to goal-based (it parses
  static manifests, kit core never branches on it); added container
  `requires: [efforts]`; added the `faceted-frontmatter-schema` backlog
  reconciliation to T5; fixed the Objective's ontology arithmetic.
- 2026-06-16: initial plan.
