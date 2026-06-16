# Plan: faceted-frontmatter-schema

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Removing the fused `type` is a coordinated edit across the schema baseline and
all twelve content-type primitives — and within each primitive it touches four
surfaces, not one: the `primitive.yaml` `contributes_to` manifest, the `.types`
snippet, the `when: type == …` guards inside the `.fields` snippet, and the
page template (plus the `description` text). The schema is a
managed-region-assembled document, and `install._plan`/`validate_contributions`
derive region ids **from each manifest's `contributes_to`** — so the migration
is manifest + snippet edits, with no aggregator code change. The crosswalk is
the spec of all the edits and is pinned first. The riskiest parts are (a) the
manifest↔snippet consistency (`validate_contributions` aborts on a mismatch)
and (b) not stranding the `when: type ==` guards or the lifecycle fields
(`decision_status`/`update_status`/`trip_status`) that two operations read.
Order: crosswalk → schema baseline → manifests+snippets → `.fields` guards +
lifecycle + descriptions → page templates → end-to-end assembly proof.

## Constraints

- **RFC-0009** — the facet model; greenfield single-model; no `domain` field.
- **RFC-0008** — `workspaces:` axis and shipped `.base` lenses untouched.
- **ADR-0011** — genre+subtype replace fused `type` (corrected here re `.base`).
- **ADR-0003 / ADR-0006** — managed-region contribution mechanism; region ids
  declared per-primitive in `contributes_to`.
- **AGENTS.md** — kit writes into a vault only via `safe_write`/`safe_write_region`.

## Construction tests

Most construction tests live per-task below. Cross-cutting:

**Integration tests:** one end-to-end test renders a temp vault via `wiki
init` over a recipe installing several content-types; asserts
`install.validate_contributions` accepts the catalog, the assembled
`genre`/`subtype` enums equal the union of installed contributions, `type`
absent, `workspaces` present, and the shipped `.base` files byte-unchanged.
**Manual verification:** open the rendered vault in Obsidian ≥1.9.10; confirm
Properties autocomplete offers genre/subtype and the workspace lenses render.

## Design (LLD)

### Design decisions

- The single `types` managed region becomes **two** regions, `genre` and
  `subtype`; each content-type's manifest declares both. Reuses the ADR-0003
  mechanism. Traces to: AC "managed regions are genre/subtype/fields", AC
  "manifests declare genre+subtype" · no `contracts/`.
- Type-specific lifecycle (`decision_status` proposed→accepted→superseded,
  `update_status`, `trip_status`) survives as **subtype-scoped `fields`**, not
  parallel `status` values, because `status-synthesis`/`onboarding-pack` read
  them. Traces to: AC "lifecycle fields retained" · spec Always-do.
- `genre` is a fixed enum in the schema baseline (catalog grows only
  `subtype`). Traces to: AC "genre enum of nine".
- `.fields` guards re-key from `when: type == X` to `when: subtype == <subtype>`
  (per crosswalk), since `subtype` is the canonical specific identifier.
  Traces to: AC "no `when: type ==` remains".

### Data & schema

- `core/files/frontmatter.schema.yaml`: `required: [genre, subtype, status,
  provenance, created, modified]`; baseline `genre` enum (9); `subtype`
  (region-populated); `statuses:` gains `someday`; `parent` (list, optional);
  `workspaces` (unchanged); managed regions `genre`, `subtype`, `fields`.
- 12 × `templates/content-types/<ct>/primitive.yaml`: `contributes_to` →
  `region: genre`, `region: subtype`, `region: fields`; `description` rewritten
  off `type:`.
- 12 × `regions/frontmatter.schema.yaml.{genre,subtype}` (replacing `.types`);
  `.fields` guards re-keyed to `subtype`.
- `docs/specs/faceted-frontmatter-schema/crosswalk.yaml`: 12 rows, each
  `legacy-type: {genre, subtype, lifecycle_field?}`.

### Interfaces & contracts

No `contracts/<type>/` surface — the frontmatter schema YAML *is* the shipped
contract, assembled by the managed-region aggregator. No REST/event/RPC.

## Tasks

### T1: Crosswalk pinned and total

**Depends on:** none
**Touches:** docs/specs/faceted-frontmatter-schema/crosswalk.yaml, tests/unit/test_facet_crosswalk.py

**Tests:**
- TDD: a unit test asserts the crosswalk's key set equals the twelve legacy
  fused types discovered from `templates/content-types/*/` (AC: crosswalk total).
- Each row's `genre` is one of the fixed nine; each names a `subtype` that
  **differs from its `genre`** (the `decision` row is `genre: decision,
  subtype: decision-record`); rows whose content-type carries a read lifecycle
  field record it (AC: genre enum; subtype≠genre; lifecycle retained).

**Approach:**
- Author `crosswalk.yaml` mapping `meeting, decision, interview, recipe,
  receipt, medical-record, tax-document, trip-doc, vendor-contract,
  customer-feedback, stakeholder-update, action-item` → `{genre, subtype,
  lifecycle_field?}`.
- Add `tests/unit/test_facet_crosswalk.py` enumerating content-type dirs.

**Done when:** `pytest tests/unit/test_facet_crosswalk.py` green; crosswalk
covers all twelve.

### T2: Schema baseline restructured to facets

**Depends on:** T1
**Touches:** core/files/frontmatter.schema.yaml, tests/unit/test_frontmatter_schema_shape.py

**Tests:**
- Goal-based: parse the schema; assert `genre` enum is exactly the nine;
  `subtype`/`parent` present; `statuses:` is exactly
  `active/draft/archived/someday`; `type` absent; `workspaces` present;
  `required:` is exactly `[genre, subtype, status, provenance, created,
  modified]`; regions are `genre`/`subtype`/`fields`, no `types` region (AC:
  schema declares facets; required set; regions; someday added).

**Approach:**
- Edit `core/files/frontmatter.schema.yaml`: replace the `type` baseline +
  `# BEGIN MANAGED: types` with the `genre` baseline enum + `# BEGIN MANAGED:
  genre` and `# BEGIN MANAGED: subtype`; add `parent`; add `someday` to the
  existing `statuses:` block; update `required:`; update the file-header
  comment enumerating managed sections (`types` → `genre`, `subtype`); keep
  `workspaces` and the `fields` region and their comments verbatim.

**Done when:** the schema-shape test passes.

### T3: Manifests + genre/subtype snippets migrated

**Depends on:** T1, T2
**Touches:** templates/content-types/*/primitive.yaml, templates/content-types/*/regions/frontmatter.schema.yaml.*

**Tests:**
- Goal-based: every `primitive.yaml` `contributes_to` declares `region: genre`
  + `region: subtype` (+ `region: fields`), none declares `region: types`;
  each `.genre`/`.subtype` snippet matches the crosswalk; no `.types` snippet
  remains (AC: manifests declare genre+subtype; snippets match crosswalk).
- Integration: `wiki init` passes `install.validate_contributions` (no orphan/
  missing snippet) (AC: assembly).

**Approach:**
- For each of the twelve `primitive.yaml`: rewrite `contributes_to` (`region:
  types` → two entries `region: genre`, `region: subtype`); rewrite the
  `description` off `type:`.
- For each `regions/`: replace `frontmatter.schema.yaml.types` with
  `.genre` + `.subtype` per the crosswalk.

**Done when:** the goal-based manifest/snippet test and the `validate_contributions`
integration assertion pass; no `region: types`, no `.types` snippet remain.

### T3b: `.fields` guards re-keyed; lifecycle fields retained

**Depends on:** T1, T3
**Touches:** templates/content-types/*/regions/frontmatter.schema.yaml.fields

**Tests:**
- Goal-based: zero `when: type ==` across all `.fields` snippets; every guard
  is `when: subtype == <subtype>` per crosswalk (AC: no `when: type ==`).
- Goal-based: `decision_status`, `update_status`, `trip_status` still present
  as subtype-scoped fields — each in exactly its single owning content-type's
  `.fields` snippet (`decision`/`stakeholder-update`/`trip-doc`) (AC: lifecycle
  retained).

**Approach:**
- In each `.fields` snippet, re-key `when: type == <ct>` → `when: subtype ==
  <subtype>`; leave the three named lifecycle fields in place.

**Done when:** both goal-based tests pass; `grep -r 'when: type =='
templates/content-types` is empty.

### T4: Page templates stamp facets, not `type`

**Depends on:** T1
**Touches:** templates/content-types/*/files/_templates/*.md

**Tests:**
- Goal-based: each `_templates/<ct>.md` frontmatter stamps `genre:`,
  `subtype:`, `status:`; none stamps `type:` (AC: page templates).

**Approach:**
- Edit each of the twelve `_templates/*.md` frontmatter per the crosswalk.

**Done when:** `grep -rl '^type:' templates/content-types/*/files/` is empty
and the template test passes.

### T5: End-to-end assembly proven; lenses unregressed; deferral registered

**Depends on:** T2, T3, T3b, T4
**Touches:** tests/integration/test_faceted_schema_assembly.py, docs/backlog.md

**Tests:**
- Integration: `wiki init` a temp vault; assert assembled `genre`/`subtype`
  enums == union of installed contributions, `type` absent, `workspaces`
  present (AC: assembly).
- Goal-based: shipped `.base` files byte-unchanged (AC: lenses unchanged);
  the `docs/backlog.md#faceted-frontmatter-schema` deferral entry exists (AC:
  operation-SKILL deferral registered).

**Approach:**
- Add `tests/integration/test_faceted_schema_assembly.py` driving `wiki init`
  against `tmp_path`.

**Done when:** the integration test is green and `pytest -m 'not slow'`,
`ruff check`, `ruff format --check`, `mypy llm_wiki_kit tests` all pass.

## Rollout

- **Delivery:** atomic within the kit — T2/T3/T3b/T4 land together (a schema
  without matching manifests/snippets/templates renders an inconsistent vault
  and can fail `validate_contributions`). No user vaults exist (pre-release);
  no migration; reversible by revert.
- **Infrastructure:** none.
- **External-system integration:** none.
- **Deployment sequencing:** this spec is the **first** RFC-0009 follow-on and
  must land before `role-folders-and-containers`, `operations-and-search-rekey`,
  and `recipe-organization-model`, which build on the facets defined here.

## Risks

- **Manifest↔snippet mismatch aborts install.** `validate_contributions`
  derives region ids from each `primitive.yaml` `contributes_to` and rejects an
  orphan/missing snippet; renaming a snippet without editing its manifest fails
  the catalog. Mitigation: T3 edits manifests and snippets together; the T3
  integration test runs `validate_contributions`. (There is no region-id list
  in `install.py` to update — the migration is manifest-side.)
- **`*_status` collapse strands a lifecycle an operation reads.** Verified now:
  `status-synthesis` and `onboarding-pack` read `decision_status`/
  `update_status`. Mitigation: T3b retains the three named fields as
  subtype-scoped; goal-based test asserts their presence.
- **Operation SKILLs reference the removed `type`/`types`.** Six SKILLs go
  stale on landing; out of scope here, re-keyed in `operations-and-search-rekey`.
  Mitigation: registered in `docs/backlog.md#faceted-frontmatter-schema`.
- **Drift with RFC-0008's shipped schema.** T2 must preserve `workspaces` and
  its comments verbatim. Mitigation: the schema-shape test asserts presence.

## Changelog

- 2026-06-16: initial plan.
- 2026-06-16: post spec-mode review — added the `primitive.yaml`
  `contributes_to` manifest edits (T3), the `.fields` `when: type ==` guard
  re-key + lifecycle-field retention (T3b), `description` rewrites, and the
  crosswalk path pin; corrected the false "install.py enumerates region ids"
  risk to the manifest-declaration reality; registered the operation-SKILL
  staleness as a backlog deferral.
