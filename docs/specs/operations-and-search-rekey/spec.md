# Spec: operations-and-search-rekey

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0009, RFC-0008, ADR-0011, `docs/specs/faceted-frontmatter-schema/spec.md`, `docs/specs/role-folders-and-containers/spec.md`, `docs/specs/wiki-search/spec.md`
- **Contract:** none
- **Shape:** mixed

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The vault's read surface speaks the faceted language the rest of the kit
already shipped. `wiki search` filters pages by `--genre` and `--subtype`
instead of the removed fused `--type`; every operation SKILL finds its input
pages in the four role folders (`people/`, `efforts/`, `library/`, `atlas/`)
and selects them by `genre`/`subtype`/`status` facets instead of globbing the
removed entity-kind and content-type-kind folders (`customers/`, `meetings/`,
`medical/`, `vendor-contracts/`, …); every operation's output page and every
content-type ingest SKILL's entity stub carries `genre`/`subtype` frontmatter
instead of the fused `type`. After this spec there is no surviving reference,
in the kit's **operational** read/write guidance — the operation/ingest/search
SKILLs, the `wiki search` command and its docs, and the architecture overview —
to a removed folder, the removed page `type` field, or the removed
`frontmatter.schema.yaml` `types` managed region. (Frozen decision records —
the RFCs under `docs/rfc/` — keep their point-in-time wording; they are history,
not read-guidance.)

The users are the kit author, the produced vault's maintaining agent (which
reads the operation SKILLs and runs `wiki search`), and — **affected** — the
downstream people who run `wiki search` and read operation outputs through the
Obsidian UI: the search flag they type changes from `--type` to
`--genre`/`--subtype`, and operation output pages now declare facets. The
vault-side `wiki-search` SKILL, the operation SKILL examples, and this spec's
crosswalk are the mitigation. Success is a kit whose `search.py`/`cli.py`,
twelve-plus vault-side operation/ingest SKILLs, operation fixtures, and the
living `wiki-search` spec all express the facet model, with the schema surface,
the workspace lenses, and the `outputs/` folder location left exactly as the
sibling specs left them.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Re-key `wiki search` so `--type` is replaced by two independent optional
  flags `--genre <value>` and `--subtype <value>`, each an AND-combined
  frontmatter filter (same shape as the retained `--tag`/`--status`):
  `llm_wiki_kit/search.py` (`SearchFilters`, `SearchHit`, `_filters_match`,
  `format_results`) and `llm_wiki_kit/cli.py` (`_cmd_search`, the `search`
  subparser, the empty-filter-value guard).
- Render each search hit with `genre:` and `subtype:` lines in place of the
  former `type:` line; keep `status:`, `tags:`, `matches:` lines as they are.
- Re-key the `wiki search` flag listing in the architecture overview
  (`docs/architecture/overview.md`, the `search.py` row's `--type` → `--genre`/
  `--subtype`) so the kit's own map of the search surface stays current.
- Re-point the removed-folder references that survive in the two core vault-side
  skills the guard's `core/files/skills/` scan covers — the `ingest` SKILL's
  routing-table diagram (`wiki/food/`, `wiki/meetings/`, `wiki/health/`,
  `wiki/finances/` → `library/`; `wiki/people/` stays) and the `wiki-lint`
  SKILL's example (`wiki/projects/`→`efforts/projects/`, `wiki/customers/`→
  `people/`). These are `role-folders-and-containers`' missed re-points, fixed
  here as a same-class bundled ride-along so the guard's no-removed-folder
  invariant holds across all vault-side skills.
- Re-point every folder reference in the ten operation SKILLs (and their
  `primitive.yaml` / `contract.yaml` descriptions and `path_pattern`s) to the
  role folder its input pages live in, per the §Crosswalk re-pointing table —
  capture pages and standalone content-type pages to `library/`, entity nodes
  to `people/`, container material to the re-homed `efforts/<type>/`
  registries.
- Replace every input-selection `--type <ct>` / `--frontmatter` reference in an
  operation SKILL with the equivalent `--genre`/`--subtype` filter per the
  crosswalk, and replace `wiki/trips/upcoming/` vs `wiki/trips/past/` folder
  selection with the `status: active` vs `status: archived` facet.
- Re-facet each operation's output-page frontmatter from `type: <product>` to
  `genre: update` + `subtype: <product>` (the existing product name as the
  subtype), and delete the now-stale sentence in each output-frontmatter
  section that names the removed `frontmatter.schema.yaml` managed `types`
  region (and the `wiki-lint` "flags it as a gap" follow-on).
- Re-facet the entity-node stub frontmatter in the seven content-type ingest
  SKILLs from `type: person|customer|vendor|organization|project` to
  `genre: profile` + the node `subtype` per the §Crosswalk node table.
- Re-key operation fixtures (`templates/operations/*/fixtures/*.md`) and the
  `wiki-search` integration tests so the assertions match the re-keyed output
  format, facets, and `library/` wikilinks; update the **living**
  `wiki-search` spec (`docs/specs/wiki-search/spec.md` + `plan.md`) in the same
  PR so spec and code do not drift.
- Close the two deferral entries this spec resolves —
  `docs/backlog.md#faceted-frontmatter-schema` (the operation-SKILL `type`/
  `types`-region item) and `docs/backlog.md#role-folders-and-containers` (the
  operation-SKILL/search folder-glob item and the ingest-SKILL/template
  value-faceting item) — removing each now-closed bullet.

### Ask first

- Adding a managed-region `subtype` contribution to any operation primitive
  (so the operation/entity subtype values become controlled vocabulary rather
  than emergent values) — this changes the schema-assembly surface the
  `faceted-frontmatter-schema` spec owns.
- Changing the uniform `genre: update` choice for operation outputs, or the
  `genre: profile` choice for entity-node / project-hub stubs.
- Adding a `--genre`/`--subtype` repetition or OR-combination semantics to
  `wiki search` beyond the single-value AND filter the sibling `--tag`/
  `--status` flags already use.

### Never do

- Add a genre/subtype value to a `frontmatter.schema.yaml` managed region, make
  an operation primitive `contributes_to` a region (operations stay
  `contributes_to: []`), or otherwise touch the schema baseline — the schema
  surface is `faceted-frontmatter-schema`'s and the entity/output subtypes ride
  as emergent values (no kit code validates page frontmatter). *(structural)*
- Touch the `journal grep --type` event-type filter (`cli.py` `event_type`) —
  it filters journal **event** types, not page frontmatter, and is unrelated to
  the page `type` this spec removes. *(structural)*
- Reshape any vault folder, move a page between role folders, or change a
  content-type/operation `requires:` — `role-folders-and-containers` owns the
  layout and re-pointed every `requires:` already. *(structural)*
- Add a runtime dependency, a new top-level directory, a new Python module, or
  a new CLI subcommand — the re-key edits existing files only. *(structural)*
- Change the `outputs/` folder location, the workspace `.base` lenses, the
  content-type `_templates/*.md` (already faceted), or `container_mode` — all
  left exactly as the sibling specs shipped them.
- Keep any legacy `--type` flag, `type:` page field, `wiki/<kind>/` folder
  reference, or `types`-region mention as a back-compat shim — greenfield,
  single model.

## Testing Strategy

Goal-based here means: parse the rendered/shipped artifact and assert its
shape; no production logic mirrors the assertion.

- **Search filter logic** (`--genre`/`--subtype` drop pages whose
  `genre`/`subtype` frontmatter differs; absent `--type`; `--tag`/`--status`
  unchanged): **TDD / integration** — `search.run_search` over a `tmp_path`
  fixture vault, exercised through `cli.main(["search", …])` (the documented
  artifact a user invokes), asserting on stdout and exit code per the re-keyed
  `wiki-search` spec ACs.
- **Search hit rendering** (`format_results` emits `genre:`/`subtype:` lines,
  not `type:`): **TDD** — `format_results` is a pure function over `SearchHit`.
- **CLI surface** (`--genre`/`--subtype` parsed onto the namespace; `--type`
  rejected with argparse usage; empty-value guard fires for both new flags):
  **integration** — `cli.main` over `["search", …]`.
- **No stale read reference** (no operation/ingest/search SKILL or doc names a
  removed `wiki/<kind>/` folder, `--type`, the page `type` field, or the
  `types` region): **goal-based** — a `grep` guard test over
  `templates/operations/`, `templates/content-types/*/files/skills/`,
  `core/files/skills/wiki-search/`, and `core/files/AGENTS.md` asserts zero
  matches against the removed-token set.
- **Operation output facets** (each operation output-frontmatter block stamps
  `genre: update` + `subtype: <product>`, no `type:`): **goal-based** — parse
  the YAML frontmatter block in each operation SKILL output section and each
  output fixture.
- **Entity-stub facets** (the seven ingest SKILLs stub `genre: profile` +
  node subtype, no `type:`): **goal-based** — `grep` the ingest SKILLs.
- **Catalog still resolves** (the re-key is doc/output-frontmatter only; no
  `requires:`/manifest change): **goal-based**, proven by the existing
  `wiki init` + `resolve_dependencies` integration tests staying green.

## Acceptance Criteria

- [ ] `wiki search` exposes `--genre <value>` and `--subtype <value>` as
      independent optional AND filters and no longer exposes `--type`; `--tag`,
      `--status`, and `--top` are byte-unchanged in behavior. `search.py`'s
      `SearchFilters` carries `genre`/`subtype` (not `type`) and `_filters_match`
      gates on the `genre`/`subtype` frontmatter fields.
- [ ] `SearchHit` carries `genre` and `subtype` (not `type`) and
      `format_results` renders a `- genre:` and a `- subtype:` line per hit in
      place of the former `- type:` line; `- status:`/`- tags:`/`- matches:`
      lines are unchanged.
- [ ] `cli.py`'s `search` subparser defines `--genre` and `--subtype` (no
      `--type`), the empty-filter guard rejects `--genre ""` and `--subtype ""`
      with `--<flag> must not be empty`, and `journal grep --type` is untouched.
- [ ] No operation SKILL, `primitive.yaml`, or `contract.yaml` references a
      removed folder (`customers/`, `vendors/`, `food/`, `domains/`, `medical/`,
      `meetings/`, `actions/`, `decisions/`, `interviews/`, `customer-feedback/`,
      `receipts/`, `tax/`, `stakeholder-updates/`, `vendor-contracts/`,
      `trips/upcoming/`, `trips/past/`, or `projects/` outside `efforts/projects/`);
      every input-page reference resolves to `people/`, `library/`, or an
      `efforts/<type>/` registry per the §Crosswalk table, and trip
      upcoming/past selection uses `status: active`/`archived`.
- [ ] No operation SKILL uses `--type` or `--frontmatter` for input selection;
      each is replaced by the crosswalk `--genre`/`--subtype` filter (e.g.
      renewal-reminders `--type vendor-contract` → `--subtype vendor`,
      stakeholder-map-refresh `--type stakeholder-update` → `--subtype
      stakeholder`).
- [ ] Every operation output-frontmatter block — the **nine** in
      `templates/operations/*/files/skills/*/SKILL.md` that write output
      frontmatter (all operations except `trip-prep`, which augments an existing
      trip page and writes none), plus the `weekly-digest` expected-output
      fixture — stamps `genre: update` and `subtype: <product>` and no longer
      stamps `type:`; the stale sentence naming the removed
      `frontmatter.schema.yaml` `types` region / `wiki-lint` gap is gone.
- [ ] The seven content-type ingest SKILLs that stub entity nodes
      (`customer-feedback`, `decision`, `interview`, `medical-record`,
      `meeting`, `stakeholder-update`, `vendor-contract`) stub `genre: profile`
      + the node subtype (`person`/`customer`/`vendor`/`organization`/`project`)
      per the §Crosswalk node table; none stubs `type:`.
- [ ] A `grep` guard test asserts zero occurrences of the removed read-surface
      tokens, using **anchored** patterns that do not false-match legitimate
      prose — specifically: the `--type` flag as a whole word; a **line-anchored**
      output stub `^type: <kind>` for the nine operation-output values that sit
      column-0 in YAML fences (`digest|status-synthesis|action-rollup|follow-up-report|
      renewal-reminders|meal-plan|onboarding-pack|stakeholder-map|medical-summary`);
      an **inline** whole-token `` `type: <kind>` `` for the five backtick-wrapped
      mid-sentence entity-node stubs (`person|customer|vendor|organization|project`),
      since the node stubs are prose, not column-0 YAML, and a line-anchored
      pattern alone would blind-spot a reintroduced node stub; each removed
      `wiki/<kind>/` folder name; and the literal phrase `managed \`types\` region`.
      The patterns explicitly
      exclude `journal grep --type` / `--type page.`, `asset_type`, the
      `*_status` lifecycle fields, the `<!-- BEGIN MANAGED: content-types -->`
      comment, and the `wiki-research-skill` spec line that states `--type` does
      not exist on that CLI. Scan set:
      `templates/operations/`, `templates/content-types/*/files/skills/`,
      `core/files/skills/`, `core/files/AGENTS.md`, and
      `docs/architecture/overview.md`. The regenerated
      `docs/guides/how-to/_examples/conflict-pending/` is *not* scanned by the
      guard — it is covered by `python starters/regenerate.py --check` (it is
      rebuilt from the scanned sources, and its hand-authored seed pages carry
      the `type:` frontmatter whose value-faceting `role-folders-and-containers`
      deferred to a separate backlog item). Frozen `docs/rfc/` is out of scope.
- [ ] `docs/specs/wiki-search/spec.md` and `plan.md` describe `--genre`/
      `--subtype` (not `--type`), the re-keyed `genre:`/`subtype:` output block,
      and re-keyed ACs; the spec's status line and ACs reflect the shipped
      contract (drift is a bug, fixed in this PR).
- [ ] The `faceted-frontmatter-schema` operation-SKILL deferral bullet and the
      `role-folders-and-containers` operation/search folder-glob and
      ingest-SKILL/template value-faceting bullets are removed from
      `docs/backlog.md` (closed work lives in each spec's Changelog, not the
      backlog).
- [ ] `wiki init` over `family`, `work-os`, and `personal` still renders and
      `resolve_dependencies` still accepts each recipe (the re-key is doc/
      output-frontmatter only; no manifest or `requires:` change).
- [ ] `python starters/regenerate.py --check` exits 0 — the committed starters
      and the `conflict-pending` example vault embed copies of the re-keyed
      operation/search SKILLs, so the regenerated bytes are committed in this PR
      (the example-vault drift guard, as `role-folders-and-containers` used it).
- [ ] `ruff check llm_wiki_kit tests`, `ruff format --check llm_wiki_kit tests`,
      `mypy llm_wiki_kit tests`, and `pytest -m 'not slow'` pass.

## Crosswalk

### Operation input re-pointing (read side)

The role-folder home is determined by the content-type `requires:` that
`role-folders-and-containers` already re-pointed.

| Operation | Old reference | Re-keyed to |
|---|---|---|
| `status-synthesis` | stakeholder-update / decision / customer-feedback pages | `library/`, `--subtype stakeholder` / `decision-record` / `customer-feedback` |
| `action-item-rollup` | meeting / stakeholder-update / customer-feedback / interview "walk its directory"; `wiki/people/` | `library/` filtered by the four `--subtype`s; `wiki/people/` unchanged |
| `medical-summary` | `wiki/medical/<person>-medical.md`, `wiki/medical/{medications,providers,insurance}.md`, `wiki/medical/records/`, `wiki/people/` | per-person case material → `efforts/cases/`; medication/insurance reference → `library/`; providers → vendor nodes in `people/`; `medical-record` pages → `library/ --subtype medical`; `wiki/people/` unchanged |
| `follow-up-tracker` | `wiki/actions/`, `wiki/medical/medications.md`, `wiki/vendors/` | `library/ --subtype action-item`; medication reference → `library/` (or `efforts/cases/` case material); vendor/service nodes → `people/` |
| `trip-prep` | `wiki/trips/upcoming/<slug>.md`, `wiki/trips/past/`, `wiki/medical/<name>-medical.md`, `wiki/people/` | `efforts/trips/<slug>/`; past trips → `efforts/trips/` with `status: archived`; medical case material → `efforts/cases/`; `wiki/people/` unchanged |
| `renewal-reminders` | `wiki/vendor-contracts/`, `--type vendor-contract` | `library/`, `--subtype vendor` (genre `contract`) |
| `onboarding-pack` | `wiki/customers/`, `wiki/projects/`, `wiki/decisions/*.md` | customer nodes → `people/`; `efforts/projects/`; `library/ --subtype decision-record` |
| `stakeholder-map-refresh` | `wiki/stakeholder-updates/`, `--type stakeholder-update`, `wiki/projects/<project>` | `library/ --subtype stakeholder`; `efforts/projects/<project>` |
| `meal-planning` | `wiki/food/`, `wiki/food/dietary-notes.md` | `library/ --subtype recipe` (genre `reference`); dietary-notes reference page → `library/` |
| `weekly-digest` | "walk its directory under `wiki/`", `--type`/`--frontmatter` | `library/ --subtype meeting`; `--genre`/`--subtype` filters |

### Operation output facets (write side)

Every operation output page is a synthesized, regenerated document → uniform
`genre: update`; the existing product name becomes the `subtype`. (`trip-prep`
augments an existing trip page and writes no output frontmatter of its own.)

| Operation | Old output `type:` | Re-faceted to |
|---|---|---|
| `weekly-digest` | `digest` | `genre: update`, `subtype: digest` |
| `status-synthesis` | `status-synthesis` | `genre: update`, `subtype: status-synthesis` |
| `action-item-rollup` | `action-rollup` | `genre: update`, `subtype: action-rollup` |
| `follow-up-tracker` | `follow-up-report` | `genre: update`, `subtype: follow-up-report` |
| `renewal-reminders` | `renewal-reminders` | `genre: update`, `subtype: renewal-reminders` |
| `meal-planning` | `meal-plan` | `genre: update`, `subtype: meal-plan` |
| `onboarding-pack` | `onboarding-pack` | `genre: update`, `subtype: onboarding-pack` |
| `stakeholder-map-refresh` | `stakeholder-map` | `genre: update`, `subtype: stakeholder-map` |
| `medical-summary` | `medical-summary` | `genre: update`, `subtype: medical-summary` |

### Ingest-SKILL entity-node stubs (write side)

A node's home is `people/` (`person`/`customer`/`vendor`/`organization`) or
`efforts/projects/` (`project` hub); the home is orthogonal to the genre.

| Old entity stub | Re-faceted to | Stubbed by |
|---|---|---|
| `type: person` | `genre: profile`, `subtype: person` | decision, interview, meeting, vendor-contract |
| `type: customer` | `genre: profile`, `subtype: customer` | customer-feedback |
| `type: vendor` | `genre: profile`, `subtype: vendor` | medical-record (providers) |
| `type: project` | `genre: profile`, `subtype: project` | stakeholder-update |
| `type: organization` | `genre: profile`, `subtype: organization` | (none today — reserved for an org-node stub if one is added) |

## Assumptions

- Technical: today (pre-change) `wiki search` filters on the page `type` field
  via a `--type` flag; `journal grep --type` is a separate event-type filter and
  is out of scope (source: `llm_wiki_kit/search.py`; `llm_wiki_kit/cli.py:2851,2906`).
- Technical: `README.md` documents `wiki search <query>` generically with no
  `--type` flag, so it needs no edit; `docs/rfc/*` and
  `docs/specs/wiki-research-skill/spec.md` (which states `--type` does *not*
  exist on the research CLI) are out of scope (source: grep over `docs/`,
  `README.md`).
- Technical: all twelve content-type `_templates/*.md` already stamp
  `genre:`/`subtype:` (faceted-frontmatter-schema did them); the only residual
  page `type` *values* are entity-node stubs in seven ingest SKILLs and the
  operation output blocks (source: grep over `templates/content-types/*/files/`
  and `templates/operations/`).
- Technical: every operation writes its output under `outputs/` (trip-prep
  augments a `wiki/` trip page); all ten output-frontmatter blocks carry a
  stale sentence naming the removed `frontmatter.schema.yaml` managed `types`
  region (source: grep over `templates/operations/*/files/skills/*/SKILL.md`).
- Technical: each content-type's role-folder home follows the `requires:` that
  `role-folders-and-containers` re-pointed — `library/` for capture types,
  `people/` for entity nodes, `efforts/{projects,cases,trips}/` for container
  material (source: `templates/content-types/*/primitive.yaml` `requires:`).
- Technical: no kit code validates page frontmatter (`wiki doctor` checks
  journal-vs-disk only), so emergent operation/entity `subtype` values that are
  not in the managed `subtype` enum leave vaults functional (source:
  `faceted-frontmatter-schema` spec Assumptions; user direction 2026-06-16).
- Process: `docs/specs/wiki-search/spec.md` is a Living document — its contract
  change rides in this PR rather than a follow-on (source: that spec's header).
- Process: RFC-0009 §C scopes the reorg to `wiki/` and leaves `outputs/`
  unchanged as a *location*; re-faceting the frontmatter of pages that live in
  `outputs/` to follow the single facet model is in scope here (source:
  RFC-0009 §C; user confirmation 2026-06-16).
- Product: operation outputs are uniformly `genre: update` with the product
  name as `subtype`; entity-node and project-hub stubs are `genre: profile`
  with the node kind as `subtype`; both ride as emergent (uncontrolled) subtype
  values (source: user confirmation 2026-06-16).
- Product: a `project` hub instance page is `genre: profile, subtype: project`
  — `profile` is the genre for a canonical identity/coordination node, and a
  hub *is* the identity node for its effort (members join via `parent:`);
  genre is orthogonal to the `efforts/projects/` folder home, and `genre: moc`
  is reserved by `role-folders-and-containers` for the navigational `_index.md`
  registry pages, not instance hubs. This is the one facet assignment with no
  crosswalk precedent; a change to it is Ask-first and it is flagged for
  explicit confirmation in the implementing PR (source: user confirmation
  2026-06-16; RFC-0009 §B; role-folders-and-containers spec).
- Process: re-faceting operation-output frontmatter is **consistency-only** —
  outputs live under `outputs/`, which `wiki search` does not scan (it scans
  `wiki/`), so the change has no functional retrieval effect; the emergent
  output/entity subtype values are deliberately left out of the managed
  `subtype` enum, and giving them a controlled-vocabulary home (and any lint
  against it) is `capture-synthesis-gating`'s surface, not this spec's (source:
  `docs/specs/wiki-search/spec.md` §Invariants; RFC-0009 §F; user direction
  2026-06-16).
