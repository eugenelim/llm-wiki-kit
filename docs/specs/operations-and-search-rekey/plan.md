# Plan: operations-and-search-rekey

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Two surfaces, both purely substitutional. The **code** surface is small and
typed: `search.py`'s three filter touchpoints and `cli.py`'s subparser swap
`type` for `genre`+`subtype`. The **doc** surface is large but mechanical: ten
operation SKILLs, seven ingest SKILLs, the vault-side `wiki-search` SKILL,
`core/files/AGENTS.md`, operation fixtures, and the living `wiki-search` spec
each lose their removed-folder / `--type` / `type:` / `types`-region references
in favor of the role folders and `genre`/`subtype` facets per the spec's
crosswalk. The riskiest part is the search code (a public CLI flag and the
`SearchHit` shape change ripple into the integration tests and the living
spec); the doc edits carry no logic risk and are pinned by a single
absence-asserting `grep` guard test at the end. Order: search code + tests
first (T1), its docs second (T2); the operation and ingest SKILL re-keys are
independent (T3, T4); the guard test, backlog reconciliation, and full-catalog
re-render close it out (T5).

## Constraints

- **RFC-0009** §B (genre/subtype facets), §C (`outputs/` location unchanged;
  reorg scoped to `wiki/`), §Follow-on (this spec re-keys operations + `wiki
  search`/`search.py` from folder-globs/`--type` to `--genre`/`--subtype`;
  `--tag` unchanged; `--status` retained, `upcoming` dropped).
- **ADR-0011** — genre+subtype replace the fused `type`.
- **`faceted-frontmatter-schema`** — owns the schema baseline + `subtype`
  managed region; this spec adds no managed-region contribution (operations
  stay `contributes_to: []`; entity/output subtypes are emergent values).
- **`role-folders-and-containers`** — owns the four-role layout and already
  re-pointed every `requires:`; this spec changes no folder and no `requires:`.
- **`wiki-search/spec.md`** — Living document; its contract change rides here.
- **AGENTS.md** — kit writes into a vault go through `safe_write`; this spec
  edits only kit-side template/skill/doc files and `search.py`/`cli.py`, no
  vault write path.

## Construction tests

**Integration tests:** the re-keyed `wiki-search` integration suite
(`tests/integration/test_wiki_search.py`) and the existing `wiki init` +
`resolve_dependencies` suites staying green (per-task below).

**Manual verification:** run the re-keyed CLI end-to-end against a `tmp_path`
fixture vault — `wiki search "<q>" --genre record --subtype meeting` — and
record the real stdout + exit code (the documented artifact a user invokes).

## Design (LLD)

### Design decisions

- **Two flags, not one renamed flag.** `--type` becomes `--genre` *and*
  `--subtype` (not a single renamed `--kind`), because the facet model split
  the fused field into two orthogonal axes; a caller filters on either or both.
  Each is an independent AND filter, mirroring the existing `--tag`/`--status`
  shape exactly — no new combination semantics. Traces to: AC1, AC3.
- **`genre`/`subtype` on `SearchHit`, not a generic `facets: dict`.** Two named
  fields keep the dataclass a plain typed record and the rendering explicit,
  matching how `status`/`tags` are already modeled. Traces to: AC2.
- **Output facets are emergent, not contributed.** Operations stay
  `contributes_to: []`; output/entity subtype values live only in the page
  frontmatter, never the managed enum — no validator reads them, and expanding
  the contribution mechanism to operations is the schema spec's surface.
  Traces to: spec §Boundaries Never-do (schema).

### Interfaces & contracts

- `wiki search` CLI surface (no `contracts/` file — internal CLI). The
  authoritative description is the living `docs/specs/wiki-search/spec.md`,
  re-keyed in T2. Traces to: AC1, AC3, AC8.

### Failure, edge cases & resilience

- The empty-filter-value guard (`--<flag> must not be empty`) extends to
  `--genre`/`--subtype`; the `wiki-search` spec AC13 pins it so a future
  rewiring can't reintroduce the "only pages missing this field" surprise.
  Traces to: AC3.

## Tasks

### T1: `wiki search` filters and renders on `genre`/`subtype`

**Depends on:** none

**Tests:**
- `format_results` over a `SearchHit(genre="record", subtype="meeting", …)`
  emits `- genre: record` and `- subtype: meeting` lines and no `- type:` line
  (TDD, pure function). Verifies AC2.
- `run_search` over a `tmp_path` vault with pages of differing `genre`/
  `subtype`: `--genre record` drops a `genre: note` page; `--subtype meeting`
  drops a `subtype: interview` page; both together AND. Verifies AC1.
- Through `cli.main(["search", q, "--genre", "record"])`: exit 0, stdout shows
  the `genre`/`subtype` lines. `cli.main(["search", q, "--type", "x"])` exits
  non-zero (argparse rejects the unknown flag). `--genre ""`/`--subtype ""`
  exit with `--<flag> must not be empty`. Verifies AC3.
- A `journal grep --type page.write …` test stays green (untouched). Verifies
  AC3 (separation).

**Approach:**
- `search.py`: rename `SearchFilters.type` → `.genre` + add `.subtype`;
  `SearchHit.type` → `.genre` + `.subtype`; `_filters_match` gates on both
  `genre` and `subtype` frontmatter; `run_search` reads `fm.get("genre")`/
  `fm.get("subtype")` into the hit; `format_results` renders the two lines;
  update the module docstring (`--type` → `--genre`/`--subtype`).
- `cli.py:_cmd_search` + `search` subparser: replace the `--type`/`search_type`
  argument with `--genre` and `--subtype`; extend the empty-value guard tuple;
  build `SearchFilters(genre=…, subtype=…, tag=…, status=…)`. Leave the
  `journal grep --type`/`event_type` argument and every other subparser
  untouched.
- Re-key `tests/integration/test_wiki_search.py` (the `--type` cases → `--genre`
  / `--subtype`; output-format assertions → `genre:`/`subtype:`).

**Done when:** the re-keyed `test_wiki_search.py` and the four tests above pass;
`grep -n "\.type\b\|--type\|search_type" llm_wiki_kit/search.py
llm_wiki_kit/cli.py` shows only the `journal grep` `event_type` occurrences.

### T2: `wiki-search` docs and living spec describe `--genre`/`--subtype`

**Depends on:** T1

**Tests:**
- Goal-based: `grep -rn "\-\-type" core/files/skills/wiki-search/SKILL.md
  core/files/AGENTS.md docs/specs/wiki-search/ docs/architecture/overview.md`
  returns nothing; the SKILL's documented output block shows
  `- genre:`/`- subtype:`. Verifies AC8.

**Approach:**
- `core/files/skills/wiki-search/SKILL.md`: description, the
  `[--type …]` usage line, the `--type meeting`/`--type recipe` examples, and
  the documented output block (`- type:` → `- genre:` + `- subtype:`).
- `core/files/AGENTS.md`: the two `--type`/`--tag`/`--status` flag listings.
- `docs/architecture/overview.md`: the `search.py` row's `--type` flag listing
  → `--genre`/`--subtype` (Blocker from spec-review; keeps the kit's own map
  current).
- `docs/specs/wiki-search/spec.md` (Living): inputs (`--genre`/`--subtype`
  paragraphs), the §Outputs block, the edge/error cases naming `--type`, and
  ACs (AC3 `--genre`/`--subtype` drop; AC13 empty-value for both); reflect the
  shipped contract in the status line.
- `docs/specs/wiki-search/plan.md`: the `--type` references in its task notes.

**Done when:** the T2 grep is clean and the `wiki-search` spec reads as a
present-tense description of `--genre`/`--subtype`.

### T3: operation SKILLs read role folders + facets and write faceted outputs

**Depends on:** none

**Tests:**
- Goal-based: for each of the ten operations, `grep` its SKILL/`primitive.yaml`/
  `contract.yaml` for the removed-folder set and `--type`/`--frontmatter` →
  zero matches; the output-frontmatter block parses to `genre: update` +
  `subtype: <product>` with no `type:` and no `types`-region sentence. Verifies
  AC4, AC5, AC6.
- Goal-based: the `weekly-digest` expected-output fixture frontmatter parses to
  `genre: update`/`subtype: digest`, and its body wikilinks point at `library/…`
  not `meetings/…`; the `sample-meeting` input fixture carries
  `genre: record`/`subtype: meeting`. Verifies AC6.

**Approach:**
- Per the spec §Crosswalk input table, re-point folder references and
  `--type`/`--frontmatter` filters in each of the ten operation SKILLs and
  their `primitive.yaml`/`contract.yaml` descriptions + `path_pattern`s;
  convert `trips/upcoming`↔`trips/past` to `status: active`↔`archived`.
- Per the spec §Crosswalk output table, replace each `type: <product>` output
  block line with `genre: update` + `subtype: <product>`, and delete the stale
  "may not yet exist in `frontmatter.schema.yaml`'s managed `types` region …
  `wiki-lint` flags it" sentence in each.
- Re-key `templates/operations/weekly-digest/fixtures/*.md` (output facets +
  `library/` wikilinks; input fixture facets).

**Done when:** the T3 greps are clean across all ten operations and the fixture
assertions pass.

### T4: ingest-SKILL entity-node stubs carry `genre: profile` + subtype

**Depends on:** none

**Tests:**
- Goal-based: `grep -rn "type: \(person\|customer\|vendor\|organization\|project\)"
  templates/content-types/*/files/skills/` returns nothing; each of the seven
  ingest SKILLs that stub a node now writes `genre: profile` + the node
  `subtype` per the spec §Crosswalk node table. Verifies AC7.

**Approach:**
- Edit the entity-stub frontmatter lines in `customer-feedback`, `decision`,
  `interview`, `medical-record`, `meeting`, `stakeholder-update`, and
  `vendor-contract` ingest SKILLs (`type: person` → `genre: profile, subtype:
  person`, etc.). Leave the already-faceted `_templates/*.md` and every prose
  use of the word "type" that is not a page-`type:` stub (e.g. tax-document's
  "form type:") untouched.

**Done when:** the T4 grep is clean.

### T5: guard test, backlog reconciliation, full re-render

**Depends on:** T1, T2, T3, T4

**Tests:**
- New goal-based guard test (`tests/unit/test_facet_rekey_guards.py` or extend
  an existing catalog-shape test): asserts zero occurrences of the removed
  read-surface tokens, using the **anchored** patterns the spec AC8 enumerates
  (whole-word `--type` excluding `journal grep --type` / `--type page.`;
  line-anchored `^type: <kind>` for the nine column-0 output stubs AND inline
  whole-token `` `type: <kind>` `` for the five backtick-wrapped prose node
  stubs; removed `wiki/<kind>/` folder names; the literal `` managed `types` region `` phrase;
  excluding `asset_type`, `*_status`, the `BEGIN MANAGED: content-types`
  comment, and the `wiki-research-skill` "does not exist" line). Scan set:
  `templates/operations/`, `templates/content-types/*/files/skills/`,
  `core/files/skills/`, `core/files/AGENTS.md`, and
  `docs/architecture/overview.md`. The regenerated example vault is covered by
  `regenerate.py --check`, not the guard (its seed pages carry deferred
  `type:`). Verifies AC8.
- Existing `wiki init` over `family`/`work-os`/`personal` + `resolve_dependencies`
  integration tests stay green. Verifies the no-manifest-change AC.
- `python starters/regenerate.py --check` exits 0 (the committed starters and
  the `conflict-pending` example vault embed copies of the re-keyed SKILLs).
  Verifies the regenerate AC.

**Approach:**
- Re-run `starters/regenerate.py` first (the committed starters + the
  `conflict-pending` example vault embed copies of the re-keyed
  operation/search/ingest SKILLs and `AGENTS.md`); commit the regenerated bytes
  so the example-vault copies carry the facets too.
- Author the absence-asserting guard test with the anchored patterns above.
- Remove the now-closed bullets from `docs/backlog.md`
  (`#faceted-frontmatter-schema` operation-SKILL item; the
  `#role-folders-and-containers` operation/search and ingest/template items);
  add the closing note to each affected spec's Changelog if present.
- Run the full gate suite.

**Done when:** the guard test passes, `docs/backlog.md` no longer lists the
closed items, and `ruff`/`ruff format --check`/`mypy`/`pytest -m 'not slow'`
plus `starters/regenerate.py --check` are all green.

## Rollout

Pure kit-side change — no infra, no migration, no external system. The CLI
flag change (`--type` → `--genre`/`--subtype`) is a hard cutover (greenfield,
no vaults in the field); there is no deprecation shim. Reversible by revert.

## Risks

- **Stale reference missed by the crosswalk.** A folder/`--type`/`type:`/
  `types`-region occurrence the crosswalk didn't enumerate slips through. The
  T5 absence-asserting guard test is the backstop; it fails the build until
  every occurrence in the scanned trees is gone.
- **A committed starter embeds a re-keyed SKILL.** If `starters/{family,work-os}`
  copied an operation/ingest SKILL verbatim, its bytes drift; `regenerate.py
  --check` catches it (T5).
- **Living-spec drift.** Editing `search.py` without the matching `wiki-search`
  spec edit would leave the Living document stale; T2 is gated on T1 and the
  guard grep covers the spec tree.

## Changelog

- 2026-06-16: initial plan.
- 2026-06-24: executed T1–T5. Mid-EXECUTE the AC8 guard (T5) surfaced
  removed-folder references `role-folders-and-containers` had missed — the
  core `ingest`/`wiki-lint` skills and the `trip-doc`/`tax-document`/`receipt`
  content-type ingest SKILLs — folded in as same-class bundled re-points and
  the guard scan-set broadened to all of `core/files/skills/` (the example
  vault dropped from the guard, covered by `regenerate.py --check`).
  Adversarial review added the `status-synthesis` input re-point (its original
  step carried no removed-folder token, so the guard couldn't surface the
  missing crosswalk re-key) and the `customer-feedback/` guard-regex entry;
  quality review added the `--type`-rejection integration test and tightened
  the scan-set coverage check.
