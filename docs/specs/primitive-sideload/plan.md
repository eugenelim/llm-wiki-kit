# Plan: primitive-sideload

> **Implementation plan paired with `spec.md`.** The spec says *what*;
> this plan says *how, in what order, with what verification*.

- **Status:** Done
- **Spec:** `docs/specs/primitive-sideload/spec.md`
- **Owner:** the implementer for each PR; long-term ownership is the
  maintainer per the spec's §Owner clause.

## Approach

Eleven PR-sized tasks. The work decomposes along the surface
boundaries the spec names: discovery + merge (T1), the schema-side
deltas that the merge depends on (T2, T3), validation gates extended
across the merged catalog (T4, T5), user-visible decoration (T6, T7,
T8), the projection-invariant anchor (T9), and documentation closure
(T10, T11). Tasks are linearly readable in the order an implementer
should expect to land them. Each task's `Tests:` subsection names
construction tests (the implementer writes them before code per the
work-loop TDD discipline); contract tests live in `spec.md`'s
acceptance criteria (AC1–AC12, AC13a, AC13b, AC14–AC19, where
AC13 was split into AC13a/AC13b and AC19 covers the
`recipes/`-at-package-root doctor warning per §Edge cases) and
bind across tasks.

Three architectural choices the plan commits to up front so future
tasks don't relitigate:

1. **Source attribution lives on `Primitive`.** The implementation
   PR adds a `source` field (or equivalent — exact name picked in
   T1) carrying either `"bundled"` or `"sideload:<package>"`. Every
   downstream consumer (`wiki doctor`, `wiki outcomes`, the
   slash-stub generator, error messages) reads this field. The
   field is hidden from `primitive.yaml` (it is populated by the
   loader, not declared by the author) and is not part of the
   schema_version-1 surface — sideload package authors don't see
   it and can't set it.
2. **`Primitive.from_sideload` is the source-discriminator.** A
   separate constructor path on the Pydantic model that constructs
   with `extra='ignore'`, captures dropped fields onto the
   instance, and sets `source`. The bundled walk continues to call
   `Primitive.model_validate` exactly as today. The two
   constructors share every field validator. The implementer may
   pick a different naming (e.g. a module-level
   `load_sideload_primitive` helper) provided the contract holds:
   one source-distinguishing path that does not weaken the
   bundled typo guard.
3. **The slash-stub `outcome-provenance` managed-region is always emitted.**
   Bundled stubs ship the block with an empty body; sideloaded
   stubs ship the populated body. Always-present means `wiki
   upgrade` does not have to decide whether to add or remove the
   block, only what to render inside it. Drift detection per
   ADR-0004 sees the region as kit-owned content either way.

### What I considered and declined

- **Tempted to add a `WIKI_SIDELOAD_DISABLE` env var to skip
  sideload discovery in tests.** Declining — env-var test seams
  become de-facto contracts (the same reviewer concern that landed
  on `starter-seed-coverage`'s plan). Tests monkeypatch
  `_discover_sideloaded_template_dirs` to inject `tmp_path`-built
  fake-package paths directly (the strategy pinned in spec
  §Acceptance criteria); `pip install -e <fixture>` is explicitly
  not used. The kit has no user-facing "disable sideload" knob and
  the test discipline inherits that constraint.
- **Tempted to add a `wiki sideload list` CLI verb to surface the
  installed sideload set on demand.** Declining — `wiki doctor`
  already carries the listing per spec §Outputs. A dedicated verb
  would be a UX wrapper for one query the doctor already answers.
  Defer until contributor feedback identifies real friction (the
  same posture RFC-0007 §Unresolved questions took toward the
  `wiki contribute` umbrella verb).
- **Tempted to introduce a `SideloadPrimitive` subclass of
  `Primitive` for the source-discriminated path.** Declining —
  the `source` field on `Primitive` (architectural choice 1
  above) does the discrimination cleaner than a class hierarchy.
  A subclass would require every existing call site that takes
  `Primitive` to decide whether it cares about the subclass; a
  field is invisible to consumers that don't read it. ADR-0005's
  "Pydantic for disk-bound schemas" framing also argues against
  a subclass that crosses no disk boundary.
- **Tempted to surface dropped fields as `wiki doctor` issues
  (counted toward exit code), not just informational warnings.**
  Declining — spec §Outputs treats dropped fields as soft
  warnings. A sideload package shipping forward-compat hints
  (anticipating kit 2.2's added field) is a legitimate, declared
  use case; making it doctor-loud would punish the very pattern
  the source-scoped `extra='ignore'` policy is designed to enable.
- **Tempted to short-circuit sideload discovery on a `--no-sideload`
  CLI flag for performance.** Declining — entry-point discovery is
  in the 10s-to-100s ms range on typical installs (per spec §"The
  kit's environment at discovery time") and amortises over the CLI
  invocation's other work; a CLI flag for an optimization that isn't
  pressing would be unrequested surface. If a sideload package author's package becomes
  performance-pathological (e.g. very large `templates/` tree)
  the kit's existing per-CLI-invocation discovery cost is the
  natural pressure to make them improve their package.
- **Tempted to add an `--upstream` or `--sideload` filter to
  `wiki outcomes`.** Declining — the `Source` column is enough.
  Filtering is a UX wrapper the implementation PR should resist
  until the column itself proves insufficient.
- **Tempted to ship a worked-example sideload package alongside
  task T10's CONTRIBUTING.md.** Declining — RFC-0007 §Unresolved
  Q named this and the author's lean was "docs artifact under
  `docs/guides/explanation/extending-the-kit.md`, not a published
  PyPI package." The plan preserves that lean. The worked example
  in the contributor guide cites a sideload package structure but
  does not publish one.

## Pre-conditions

- RFC-0007 (`docs/rfc/0007-primitive-contribution-model.md`)
  reaches `Status: Accepted` in the same PR as this spec + plan
  (the status flip and the spec/plan drafting land together).
- `llm_wiki_kit/primitives.py` has `discover_primitives`,
  `_CATALOG_DIRS`, `RESERVED_OUTCOME_VERBS`, and the existing
  outcome-verb validation surfaces at their current line numbers
  (spec §"Contracts with other modules" pins the references).
- `llm_wiki_kit/models.py` has `Primitive(_StrictModel)` with
  `extra='forbid'` (per `_StrictModel` at lines 36–44). `Primitive`
  has no `schema_version` field today; T2 adds it.
- `llm_wiki_kit/install.py` has
  `validate_outcome_skill_fragments(sources: Mapping[str, Path])`
  and the `aggregate_region_contributions` region-collision pass.
  Both surfaces are stable enough to extend additively.
- `starters/regenerate.py` defines `RECIPE_TARGETS`. T9's
  amendment to `docs/specs/starter-seed-coverage/spec.md` makes the
  constant load-bearing across the two scripts; today the constant
  is already shared by direct import per `starter-seed-coverage`'s
  approach, so the amendment is spec-level not code-level for that
  pair.
- Test infrastructure: `tests/unit/`, `tests/integration/`, and
  `tests/fixtures/` exist; new files slot under the existing
  directories per spec §Constraints (no new top-level directory).

## Tasks

Each task is one verifiable goal. `Tests:` enumerates construction
tests the implementer writes before code (TDD mode), goal-based
checks (a one-liner), or manual checks. Contract tests bind across
tasks; the AC numbers reference `spec.md`'s acceptance criteria.

### T1: Sideload discovery helper + merge in `discover_primitives`

**Done when:** `_discover_sideloaded_template_dirs() -> list[tuple[str, str, Path]]`
exists in `llm_wiki_kit/primitives.py`; `discover_primitives` walks
the bundled `templates_dir` and every sideloaded templates path
returned by the helper, producing a merged list. With no
`wiki-primitive` entry points installed, `discover_primitives`
output is byte-equivalent to today's loader output.

**Tests (construction):**

- `tests/unit/test_primitive_sideload.py::test_empty_entry_point_group_returns_empty`
  — patch `importlib.metadata.entry_points` to return no
  `wiki-primitive` group; assert helper returns `[]`.
- `…::test_helper_resolves_entry_point_to_templates_path` —
  fixture entry-point whose value is a package with a
  `templates/` directory; assert helper returns
  `[(<package>, <version>, <path>)]` and the path is
  filesystem-traversable.
- `…::test_helper_raises_on_missing_templates_dir` — fixture
  entry-point whose package has no `templates/`; assert
  `WikiError` is raised with package name in message.
- `tests/integration/test_primitive_sideload.py::test_discover_primitives_no_sideload_byte_equivalent`
  — run `discover_primitives` against the real
  `kit_root / "templates"` with no `wiki-primitive` entry points
  installed; assert the returned list (serialized for comparison)
  matches a pinned snapshot of today's output. (AC1.)
- `…::test_discover_primitives_merges_one_sideload_package` —
  install a fixture sideload package providing one content-type
  named `sample-foo`; assert the returned list contains both
  bundled primitives and `sample-foo`, alphabetically sorted.
  (Partial AC2.)
- `…::test_recipe_resolves_against_merged_catalog` — fixture
  user-authored recipe references one bundled and one sideloaded
  primitive; assert `recipes.resolve_recipe_primitives` returns
  the merged closure including both. (AC15.)
- `…::test_zipped_wheel_sideload_surfaces_primitive_error` —
  fixture sideload installed as a zipped-wheel layout; assert
  `PrimitiveError` is raised at the first filesystem operation
  with the package name in the message. (AC18.)

**Approach:** New `_discover_sideloaded_template_dirs()` calls
`importlib.metadata.entry_points(group="wiki-primitive")`, iterates
the returned `EntryPoint`s, and for each one resolves
`importlib.resources.files(ep.value) / "templates"`. The function
returns a list of `(package_name, version, templates_path)`
tuples. `discover_primitives` is extended so its existing walk
runs once per templates path (bundled first, then each sideloaded
path in deterministic order — sorted by package name for
reproducibility). The merge happens before
`check_outcome_verb_uniqueness` so the uniqueness check operates
on the merged contract list. Test fixtures live under
`tests/fixtures/primitive-sideload/<scenario-name>/` and are
plain `templates/<kind>/<name>/primitive.yaml` filesystem trees
(no `pyproject.toml`, no installation). Tests inject these via
`monkeypatch.setattr(llm_wiki_kit.primitives, "_discover_sideloaded_template_dirs", lambda: [(name, version, fixture_path)])`
per the spec §Acceptance criteria fixture strategy; one focused
AC for `_discover_sideloaded_template_dirs` itself monkeypatches
`importlib.metadata.entry_points` with a fake `EntryPoint`
returning a `SimpleNamespace` whose `__path__` points at the
filesystem fixture.

**Depends on:** none.

### T2: `Primitive.schema_version` field + Pydantic precedent extended

**Done when:** `Primitive` (in `llm_wiki_kit/models.py`) declares
`schema_version: int = 1`. A bundled `primitive.yaml` omitting
the field parses with default `1`. A `primitive.yaml` declaring
`schema_version: 2` raises a load-time `WikiError` (or
`ValidationError` wrapped into one — implementer picks the
exact shape, the contract is "named, machine-readable failure").

**Tests (construction):**

- `tests/unit/test_primitive_model.py::test_schema_version_defaults_to_1`
  — load a fixture `primitive.yaml` without the field; assert
  `primitive.schema_version == 1`.
- `…::test_schema_version_explicit_1_parses` — fixture with
  `schema_version: 1` declared; assert parses cleanly.
- `…::test_schema_version_2_raises_for_bundled` — bundled
  fixture with `schema_version: 2`; assert raises with a message
  containing the supported-versions range. Pairs with the
  sideload-side AC8 assertion to cover the symmetric contract.

**Approach:** Add the field to `Primitive` matching the existing
pattern on event models (`VaultInitEvent.schema_version` at
`models.py:283`, `VaultGitInitializedEvent.schema_version` at
`models.py:299`). A field-level validator rejects values other
than 1. Existing bundled `primitive.yaml` files do not need
updating — the default makes the field invisible to them.

**Depends on:** none.

### T3: Source-scoped `extra='ignore'` for sideload + dropped-field capture

**Done when:** `Primitive.from_sideload(data: dict, source: str)`
(or equivalent loader helper — see "Approach" for naming
flexibility) constructs a `Primitive` with `extra='ignore'`,
captures the dropped-field names on the instance (as e.g.
`_dropped_fields: tuple[str, ...]`), and sets `source` to
`"sideload:<package>"`. Bundled primitives continue to load via
`Primitive.model_validate` with `extra='forbid'` unchanged.

**Tests (construction):**

- `tests/unit/test_primitive_model.py::test_from_sideload_accepts_unknown_field`
  — fixture data with a `hint_for_kit_2_2: anything` field;
  assert `Primitive.from_sideload(...)` returns a model whose
  `_dropped_fields == ("hint_for_kit_2_2",)`.
- `…::test_model_validate_rejects_unknown_field_for_bundled` —
  same fixture data through `Primitive.model_validate`; assert
  `ValidationError`. (AC7.)
- `…::test_from_sideload_sets_source` — assert
  `primitive.source == "sideload:<package>"` after
  `Primitive.from_sideload(data, source="sideload:test-pkg")`.

**Approach:** The classmethod (or module-level helper)
constructs a model with a temporary
`ConfigDict(extra='ignore')` override. Pydantic v2 supports
this via `model_validate(..., context=...)` or a dedicated
class with overridden config — the implementer picks the
cleanest. Dropped-field capture compares the input dict's keys
against the model's known fields. The `source` and
`_dropped_fields` attributes are private to the kit (not part
of `primitive.yaml`'s public schema). The bundled load path
(`Primitive.model_validate(data)` at the existing
`load_primitive` call site `primitives.py:269–307`) is updated
only to set `source="bundled"` on the returned instance — no
extra-policy change.

**Depends on:** T1, T2. T2 because the `schema_version` field
needs to exist before `from_sideload` can rely on it being part
of the model shape. T1 because the bundled-load path
(`Primitive.model_validate` at the `load_primitive` call site)
is updated in this task to assign `source="bundled"`, and T1's
merge reads `source` to drive the alphabetical sort and the
collision detection — the field must be populated by every
loader path before the merge can use it.

### T4: Collision policy across merged catalog (name, region, SKILL path)

**Done when:** `discover_primitives` raises a load-time
`WikiError` on (a) a sideloaded primitive name colliding with a
bundled name; (b) two sideloaded primitives with the same name;
(c) a sideloaded primitive's region contribution colliding with a
bundled region; (d) a sideloaded primitive's SKILL directory
colliding with a bundled SKILL directory. Two-sideload region
and SKILL collisions raise the same way. The error messages name
both contributors with their source attribution.

**Tests (construction):**

- `tests/integration/test_primitive_sideload.py::test_name_collision_bundled_vs_sideload_raises`
  — fixture sideload provides `recipe` (a bundled content-type
  name); assert raise with `recipe` and the package name in
  message. (AC3.)
- `…::test_name_collision_sideload_vs_sideload_raises` — two
  fixture packages provide `dnd-session-notes`; assert raise
  naming both. (AC4.)
- `…::test_region_collision_bundled_vs_sideload_raises` —
  fixture sideload's `regions/` contributes to a region a
  bundled primitive already owns; assert
  `aggregate_region_contributions` (or its caller) raises with
  both contributors named. (AC9.)
- `…::test_skill_path_collision_raises` — fixture sideload
  ships `files/skills/ingest/SKILL.md` (a bundled SKILL path);
  assert raise. (AC10.)

**Approach:** Each `Primitive` instance carries `source`
(from T3). The merge in `discover_primitives` builds an index
of name → `(primitive, source)` and raises on collision before
returning the list. Region-collision detection in
`install.aggregate_region_contributions` already attributes per
contributing primitive; extending the error message to include
source attribution is a one-line change in the existing error
path. SKILL-path collision is a new check (today's bundled
catalog has no collision case); it lives next to
`aggregate_region_contributions` or in a new helper called by
the install pipeline before `validate_outcome_skill_fragments`
runs. Spec §"Collision policy" enumerates the five collision
points; this task addresses the four bundled-vs-sideload and
sideload-vs-sideload cases. Outcome-verb collision (the fifth)
is T5.

**Depends on:** T1 (the merged catalog), T3 (`source`
attribution).

### T5: Outcome-verb uniqueness + SKILL-fragment gate across merged catalog

**Done when:** `check_outcome_verb_uniqueness` (already at
`primitives.py:411`) operates on the merged contract list. A
sideloaded operation primitive declaring an outcome verb that
collides with a bundled verb raises with both contributors named
(verb-shape errors continue to use the existing message).
`install.validate_outcome_skill_fragments` accepts sideloaded
primitive paths via the existing `sources: Mapping[str, Path]`
parameter; a sideloaded primitive whose SKILL.md fragment lacks
its declared outcome verb raises the existing
`validate_outcome_skill_fragments` error.

**Tests (construction):**

- `tests/integration/test_primitive_sideload.py::test_outcome_verb_collision_across_catalog_raises`
  — fixture sideload declares `outcomes: [weekly-digest]`
  (bundled); assert raise. (AC5.)
- `…::test_outcome_verb_collision_two_sideloads_raises` — two
  fixture sideloads both declaring `outcomes:
  [plan-podcasts]`; assert raise naming both.
- `…::test_skill_fragment_gate_fires_on_sideload` — fixture
  sideload's SKILL.md description lacks its declared verb as a
  whole word; assert `validate_outcome_skill_fragments`
  raises. (AC11.)
- `…::test_skill_fragment_gate_clean_for_sideload` — sanity
  case: sideload's SKILL.md contains the verb; assert no raise.

**Approach:** `check_outcome_verb_uniqueness` already operates
on whatever contract list it receives; verify (via a focused
test against a merged list) that the function's contract holds
under T1's merge. No code change should be needed in the
function itself — only in its call site to ensure it receives
the merged list. The SKILL-fragment gate similarly takes its
`sources` mapping from the caller (`install.py`); the caller
needs to populate the mapping with sideloaded primitive paths.
The implementer locates the caller(s) and verifies (or
extends) the population logic.

**Depends on:** T1, T3 (source attribution for the error
messages).

### T6: `wiki doctor` sideload section + dropped-field surfacing

**Done when:** A new check function (e.g.
`check_sideload_packages` in `doctor.py`) returns
informational/`Note`-shaped output that `wiki doctor` renders
as a "Sideload primitives" section (only when at least one
sideload package is installed) plus a "Sideload primitives with
dropped unknown fields" subsection (only when any sideloaded
primitive has captured dropped fields). Bundled primitives
never appear in either subsection. Neither subsection counts
toward `wiki doctor`'s exit code.

**Tests (construction):**

- `tests/integration/test_sideload_doctor.py::test_doctor_lists_installed_sideload_packages`
  — vault state has two sideloaded primitives installed; assert
  `wiki doctor` output contains the section listing the package,
  version, and primitive names. (AC12.)
- `…::test_doctor_no_section_when_no_sideloads` — no sideload
  packages installed; assert no "Sideload primitives" header in
  output.
- `…::test_doctor_lists_dropped_fields` — sideloaded primitive
  has `_dropped_fields = ("hint_for_kit_2_2",)`; assert
  doctor output contains the dropped-field subsection. (AC6.)
- `…::test_doctor_dropped_field_does_not_affect_exit_code` —
  same case; assert `wiki doctor` exit code is 0 if no
  finding-level issues exist.
- `…::test_doctor_warns_on_package_recipes_directory` — fixture
  sideload package ships `recipes/` at its package root; assert
  doctor output names the package and the dropped `recipes/`
  path with a removal-recommendation hint; assert exit code is
  unaffected. (AC19.)
- `…::test_doctor_reports_uninstalled_sideload_mismatch` —
  fixture vault journal contains a `PrimitiveInstallEvent` for
  a sideloaded primitive whose owning package has been
  uninstalled; assert doctor surfaces a `missing-primitive`
  issue with a hint naming the previously-installed package.
  (AC17.)

**Approach:** Add the new check function next to existing
`doctor.py` checks. The function reads the merged catalog via
the kit's existing entry points (presumably the same catalog
the rest of the kit reads), partitions by `source`, and emits
informational output. The implementer matches the existing
`Issue` / `Note` shapes in `doctor.py`.

**Depends on:** T1, T3.

### T7: `wiki outcomes` `Source` column

**Done when:** `_cmd_outcomes` (in `cli.py`) renders a `Source`
column whose values are `bundled` or `sideload:<package>`. The
column is always present (even when no sideload packages are
installed — all rows show `bundled`). Output ordering and the
existing column set are unchanged.

**Tests (construction):**

- `tests/integration/test_sideload_outcomes.py::test_outcomes_renders_source_column`
  — vault with one bundled and one sideloaded operation; assert
  `wiki outcomes` output contains both verbs with their
  respective `Source` values. (AC13a.)
- `…::test_outcomes_source_column_always_present` — no sideload
  packages installed; assert the column header appears in
  output with every row showing `bundled`. (AC13b.)
- `…::test_outcomes_ordering_unchanged` — same fixture as
  today's `wiki outcomes` tests; assert verb ordering matches
  today's output (only the `Source` column is added).

**Approach:** Extend the row-formatting logic in
`_cmd_outcomes` to include the new column. Source attribution
comes from each primitive's `source` field (T3); the operation
→ primitive resolution already happens during outcome listing.

**Depends on:** T1, T3.

### T8: Slash-stub provenance managed-region

**Done when:** Every slash-stub generated by the kit at
`.claude/commands/<verb>.md` carries a
`<!-- BEGIN MANAGED: outcome-provenance --> … <!-- END MANAGED: outcome-provenance -->`
block. Bundled-primitive stubs ship the block with empty body;
sideloaded-primitive stubs ship the block populated with the
blockquote text from spec §Outputs. A no-op `wiki upgrade` does
not surface a drift for either case (round-trips byte-identically
through `safe_write`).

**Tests (construction):**

- `tests/integration/test_sideload_slash_stub.py::test_bundled_stub_has_empty_provenance_block`
  — install a bundled operation primitive; assert
  `.claude/commands/<verb>.md` contains the region delimiters
  with empty body. (Partial AC14.)
- `…::test_sideloaded_stub_has_populated_provenance_block` —
  install a sideloaded operation primitive; assert the region
  body contains `From sideload package:` plus the package name
  and version. (AC14.)
- `…::test_upgrade_round_trip_no_drift` — install a sideloaded
  operation, then run `wiki upgrade`; assert no `.proposed`
  sidecar is created and journal shows no
  `PageConflictResolved`.

**Approach:** Modify the slash-stub generator (currently part
of `install.py`'s SKILL-fragment installation logic per
`docs/specs/outcome-named-entry-points/spec.md`). Add a
`outcome-provenance` managed-region block to the generated
content (per ADR-0003 / ADR-0006's
`<!-- BEGIN MANAGED: <id> -->` / `<!-- END MANAGED: <id> -->`
convention).
Region body computed from the contributing primitive's
`source` field. The block is emitted unconditionally so the
managed-region machinery (per ADR-0003 / ADR-0006) treats it
as kit-owned content in both cases — no special case for
"absent vs. present" block handling.

**Depends on:** T1, T3.

### T9: Elevate `RECIPE_TARGETS` to the load-bearing definition of "starter input"

**Done when:**

1. `docs/specs/starter-seed-coverage/spec.md` is amended so that
   `RECIPE_TARGETS` (currently defined in
   `starters/regenerate.py`) is named as the single source of
   truth for "starter input" — the recipe set that
   `starters/regenerate.py` renders, the recipe set
   `starters/check_coverage.py` audits, and (by RFC-0006's
   projection invariant) the recipe set that any future
   "starter" surface treats as in-scope. A cross-reference to
   this spec (`docs/specs/primitive-sideload/spec.md`) is added
   under §Related.
2. `starters/regenerate.py` carries a leading comment marker
   `# Load-bearing: see docs/specs/starter-seed-coverage/spec.md
   and docs/specs/primitive-sideload/spec.md (RFC-0006 projection
   invariant; RFC-0007 sideload).` immediately above the
   `RECIPE_TARGETS = { ... }` definition (currently
   `starters/regenerate.py:71`).
3. `starters/regenerate.py` gains an `__all__` entry naming
   `RECIPE_TARGETS` (and any other symbols already informally
   public — `STARTERS_DIR`, etc., at the implementer's
   judgment). The `__all__` declaration is the machine-readable
   anchor that AC16's static check verifies.

User-authored recipes composing sideloaded primitives are out of
`RECIPE_TARGETS` by construction and therefore out of starter
rendering and seed-coverage audit.

**Tests (construction):**

- `tests/unit/test_recipe_targets_anchor.py::test_recipe_targets_in_all`
  — read `starters/regenerate.py` as text or via importable
  module; assert `"RECIPE_TARGETS"` appears in the `__all__`
  tuple/list.
- `…::test_load_bearing_comment_present` — read
  `starters/regenerate.py` as text; assert the
  `# Load-bearing:` comment marker is the line immediately
  preceding the `RECIPE_TARGETS = ` assignment.
- The existing `tests/integration/test_starters_regenerable.py`
  and `tests/integration/test_starter_seed_coverage.py` continue
  to pass without modification (behavior is unchanged).

**Approach:** Two-line edit to `starters/regenerate.py`
(comment + `__all__`); spec-text edit to
`docs/specs/starter-seed-coverage/spec.md` adding the
load-bearing paragraph in §Inputs and the cross-reference in
§Related.

**Depends on:** none for the code/spec edits themselves. AC16's
static-check test binds to T9's `__all__` + comment-marker
anchor and runs independently of T1–T8. T9 should land in the
same wave as the rest of the implementation so the projection
invariant is pinned before sideload reaches users — the
implementer can land T9 first (it's independent), or fold it
into T1's PR.

### T10: `CONTRIBUTING.md` + extending-the-kit explanation guide + add-a-primitive how-to

**Done when:** A top-level `CONTRIBUTING.md` lands at the repo
root carrying the inlined decision tree from RFC-0007 §(1) plus
the upstream-PR walkthrough and the sideload walkthrough. A new
`docs/guides/explanation/extending-the-kit.md` carries the
architectural framing (why hybrid, what each path costs, when
each is right). A new `docs/guides/how-to/add-a-primitive.md`
carries the step-by-step for the upstream PR path with full
file-tree examples. None of the three docs ship a published
sideload package — the worked example is a checked-in fixture
under `docs/guides/explanation/_examples/sideload-package/`.

**Tests (construction):**

- `tests/unit/test_docs_links.py::test_contributing_decision_tree_matches_rfc`
  — read the decision tree section in `CONTRIBUTING.md`,
  compare it for substantive content (modulo trivial wording)
  against the equivalent section in RFC-0007. The tree is the
  policy; the document is the document. Drift between them is
  a bug.
- Manual check: read the three docs end-to-end. Assert the
  contributor scenario from RFC-0007 §Motivation §2 (an
  external upstream contributor with `ingest-podcast`, an
  author with `ingest-dnd-session-notes`) walks cleanly
  through whichever path the decision tree picks.
- `ruff format --check` and `ruff check` pass (docs are
  markdown; no python lint impact, but the CI gates run).

**Approach:** Copy the decision tree from RFC-0007 §(1)
verbatim. Expand the upstream-PR walkthrough with concrete
file paths and the spec-or-PR threshold. Expand the sideload
walkthrough with a `pyproject.toml` skeleton, the package
templates layout, and a "how to test locally without
publishing" subsection. The how-to under `docs/guides/how-to/`
mirrors the upstream-PR walkthrough but expands every step
with a full file-tree example.

**Depends on:** T1–T8 ideally complete (so the walkthroughs
reference real behavior), but the documentation work can
proceed in parallel once T1's contract is pinned (the
decision tree and the upstream-PR walkthrough don't depend on
sideload behavior at all).

### T11: Roadmap edit naming the hybrid model

**Done when:** `docs/ROADMAP.md` carries a one-paragraph note
naming the hybrid contribution model and pointing at this RFC
and spec. The note sits next to the existing Tier-2 starter
section (lines 60–86 of today's roadmap) as the
*kit-extension* counterpart to RFC-0006's *vault-distribution*
direction.

**Tests (construction):**

- `ruff format --check` passes on the updated `docs/ROADMAP.md`.
- Manual check: read the paragraph; assert it names the
  hybrid model, references RFC-0007 + this spec, and does not
  commit to a timeline.

**Approach:** Add one paragraph to `docs/ROADMAP.md`. Lands
last because the note refers to the rest of the spec as
"shipped" or "in progress."

**Depends on:** T1–T10 (lands last).

## What this plan does *not* do

- **Does not include the spec amendment text for
  `starter-seed-coverage`.** Task T9 names the amendment; the
  exact wording is the T9 PR's responsibility.
- **Does not pre-implement any task in this plan PR.** This PR
  is RFC status flip + new spec + new plan only. No Python code
  changes.
- **Does not commit to single-PR or multi-PR landing for the
  implementation.** The per-task `Depends on:` declarations are
  the canonical order — T2 lands before or alongside T3; T1
  lands before T3, T4, T5, T6, T7, T8; T9 is independent
  (`Depends on: none`). The implementer groups tasks into PRs
  based on review bandwidth, not the order this plan lists them
  in.
- **Does not gate any task on `starter-seed-coverage/spec.md`
  reaching `Status: Implemented`.** T9 is the amendment to that
  spec; the spec's own status moves independently.

## Out-of-scope follow-ups (post-spec)

Items the plan deliberately defers, with the trigger that would
re-open each.

- **Worked example sideload package on PyPI.** Defer until
  contributor demand surfaces (an actual contributor asks
  where the canonical example is). The checked-in fixture
  under T10's docs tree is the v1 worked example.
- **`wiki doctor --json` output for sideload-aware tooling.**
  Defer until an external tool needs to consume the sideload
  listing programmatically.
- **Cross-kit-version compatibility metadata on sideload
  packages.** Defer until a sideload package breaks on a kit
  upgrade and the user has no clear error. The spec's v1
  schema freeze plus `pyproject.toml` pip-range pinning is the
  v1 answer.
- **`wiki sideload list` / `wiki sideload disable <pkg>` CLI
  verbs.** Defer until friction surfaces. `wiki doctor`'s
  listing is the v1 answer.
- **A separate `llm-wiki-kit-primitive-*` namespace policy on
  PyPI.** The kit takes no position. Defer until package-naming
  collisions in the wild surface, at which point the
  community-or-maintainer convention can be documented in
  `CONTRIBUTING.md` without further RFC work.
