# Spec: primitive-sideload

> **Living document.** Updated alongside the code. Drift between spec
> and code is a bug — fix the code or the spec in the same PR.

- **Status:** Shipped
- **Owner:** `llm_wiki_kit/primitives.py` (catalog discovery + merge);
  `llm_wiki_kit/models.py` (`Primitive` schema + `schema_version` +
  sideload-scoped extra-field policy); `llm_wiki_kit/install.py`
  (existing collision + SKILL-fragment gates, extended transitively);
  `llm_wiki_kit/doctor.py` (new sideload section); `llm_wiki_kit/cli.py`
  (`wiki outcomes` provenance column); the slash-stub generator
  (managed-region provenance block).
- **Related:** RFC-0007
  (`docs/rfc/0007-primitive-contribution-model.md`) is the direction.
  ADR-0002 (journal), ADR-0003 + ADR-0006 (managed regions; the
  slash-stub provenance block reuses this machinery), ADR-0005
  (Pydantic for disk-bound schemas — `_StrictModel`'s
  `extra='forbid'` is the bundled-side default this spec extends).
  Specs that share surfaces: `docs/specs/outcome-named-entry-points/spec.md`
  (verb shape + catalog uniqueness, extended across the merged
  catalog); `docs/specs/wheel-bundled-assets/spec.md` (the
  `importlib.resources` mechanism this spec reuses; the
  zipped-wheel non-goal is inherited); `docs/specs/starter-seed-coverage/spec.md`
  (`RECIPE_TARGETS` becomes the load-bearing definition of "starter
  input" — amendment is task T9 in the paired plan).
- **Constrained by:** Charter Principle 1 (honesty over capability —
  Principle 1 is the source of §"Provenance decoration" and the
  reason silent shadowing is ruled out in favor of load-time
  errors); Principle 3 (no new runtime dependency — this spec uses
  only `importlib.metadata`, `importlib.resources`, and the
  existing `pyyaml` / `pydantic` already in the runtime set);
  Principle 4 (common core + droppable primitives — the catalog
  grows additively from a second source, never replaces); Principle 5
  (library-not-application — entry-point discovery is the
  library-shape pattern Hugo themes and Sphinx extensions use; the
  kit retains the dispatch surface throughout, see RFC-0007 §"Why
  entry-points don't soften Principle 5"). RFC-0006's projection
  invariant — preserved by mechanical anchor (T9 elevates
  `RECIPE_TARGETS`).

## What this is

`primitive-sideload` extends the kit's catalog-discovery surface to
include third-party Python packages that ship primitives, discovered
via a `wiki-primitive` entry-point group. The bundled
`templates/<kind>/<name>/primitive.yaml` tree continues to load
unchanged; sideloaded packages contribute additional primitives that
the kit merges into the same catalog at runtime under additive-only
collision rules. Recipes resolve primitive names from the merged
catalog without caring about source.

The kit treats sideloaded primitives like bundled ones for every
load-bearing gate (outcome-verb shape, outcome-verb catalog
uniqueness, install-time SKILL-fragment validation,
recipe-binding name resolution, region-collision detection) and
differs only on three audited surfaces:

- **Schema laxity:** sideloaded primitives load with Pydantic
  `extra='ignore'` (bundled stay `extra='forbid'`). Dropped fields
  are not silent — `wiki doctor` reports them.
- **Provenance decoration:** every user-visible affordance produced
  by a sideloaded primitive (the verb listed by `wiki outcomes`, the
  slash-stub at `.claude/commands/<verb>.md`, the entry in `wiki
  doctor`'s installed-primitive listing) carries provenance metadata
  the user can read at a glance.
- **Doctor surface:** `wiki doctor` lists the installed sideload set
  separately from bundled primitives, surfaces dropped-field warnings
  for each sideloaded primitive, and points at the package author
  for any user-visible affordance whose underlying primitive is
  sideloaded.

This spec pins those mechanics. It does *not* introduce a new
primitive kind, a new write path, a new vault-resident surface, a
sideload registry, or any softening of the library boundary. The
plan paired with this spec
(`docs/specs/primitive-sideload/plan.md`) breaks the implementation
into PR-sized tasks; **task T9 amends
`docs/specs/starter-seed-coverage/spec.md`** to elevate
`RECIPE_TARGETS` to the load-bearing definition of "starter input,"
which is the mechanical anchor for RFC-0006's projection invariant
under the merged-catalog regime.

## Inputs

### The entry-point group

- **Group name:** `wiki-primitive`. Stable string declared by this
  spec; this is the kit's public extension contract.
- **Discovery mechanism:**
  `importlib.metadata.entry_points(group="wiki-primitive")`.
- **Entry-point value semantics:** the value is a Python package
  (importable module path) whose installed location contains a
  `templates/<kind>/<name>/primitive.yaml` tree. The kit resolves
  the templates path via
  `importlib.resources.files(value) / "templates"`. The kit does
  not invoke any entry-point callable — the package is named, then
  read.

### Sideload package layout (the contract a sideload author ships against)

A sideload package MUST contain a `templates/` directory at the
package's installed root. The directory mirrors the bundled
`templates/` layout exactly:

```
<package>/
  templates/
    content-types/<name>/primitive.yaml      # required for content-types
    content-types/<name>/files/              # optional — files contributed to vaults
    content-types/<name>/regions/            # optional — schema region contributions (ADR-0006)
    content-types/<name>/fixtures/           # optional — sample-input/expected-output
    operations/<name>/primitive.yaml         # required for operations
    operations/<name>/contract.yaml          # required for operations
    operations/<name>/files/skills/<skill>/SKILL.md   # required if outcome verbs declared
    operations/<name>/fixtures/              # optional
    ontologies/<name>/primitive.yaml
    ontologies/<name>/files/wiki/<name>/     # the seed folder convention
    infrastructure/<name>/primitive.yaml
    agents/<name>/primitive.yaml
```

The same five `_CATALOG_DIRS` apply (`llm_wiki_kit/primitives.py`
lines 61–69). A sideload package MUST NOT contain a sixth kind
directory; discovery silently skips unknown top-level names inside
the package's `templates/` (mirroring the bundled-catalog skip
behavior — debris does not crash discovery), and a primitive whose
`primitive.yaml` declares a `kind` outside the five-kind enum raises
the same Pydantic `ValidationError` it would raise for a bundled
primitive.

A sideload package MUST NOT ship a `recipes/` directory at its
package root. Recipes today live at the kit's repo-root `recipes/`
(distinct from `templates/`); the kit's loader does not look for
recipes inside any sideload package's tree. A sideload package
that ships `recipes/` is silently inert today (the kit ignores it);
`wiki doctor` surfaces a soft warning naming the package and
recommending removal (see §"Edge cases"). Whether sideload packages
ever ship recipes is a separate, future-RFC question — see
§Non-goals.

### Sideload package installation

- **Regular wheel install only.** Sideload packages MUST install
  such that `importlib.resources.files(<package>)` returns a
  filesystem-traversable `pathlib.Path` (i.e. the kit can use
  `path.iterdir()` and `path.open()` directly). This is the same
  constraint `docs/specs/wheel-bundled-assets/spec.md` names for
  the kit's own bundled assets (zipped wheel / zipapp layouts are
  out of scope). The constraint is documented, not actively
  enforced — install-time path operations will fail naturally for
  zipped layouts and produce a `PrimitiveError` with the offending
  package name in the message.

### The kit's environment at discovery time

`discover_primitives` is invoked from many CLI entry points
(`wiki init`, `wiki add`, `wiki upgrade`, `wiki doctor`, `wiki run`,
`wiki ingest`, `wiki outcomes`). Sideload discovery runs every
time — there is no caching across CLI invocations. The cost of the
discovery call itself (`importlib.metadata.entry_points(group=…)`)
is dominated by the site-packages metadata scan on first call
(typically tens to a few hundred milliseconds, environment-
dependent) and is amortised over the rest of the CLI invocation's
work. The kit does not pin a numeric performance budget at this
spec's acceptance — see §"Non-goals" on why performance is not a
behavior-shape gate.

## Outputs

### Loader return shape

`discover_primitives(templates_dir: Path) -> list[Primitive]`
retains its current signature and return shape. Sideloaded primitives
are appended to the same list, alphabetically sorted by name after
the merge (same final sort the bundled walk uses today,
`primitives.py:413`). Each `Primitive` instance gains a `source`
attribute (see §"Contracts with other modules" — the field's
visibility and exact name belong to the implementation PR, but the
contract is: every primitive instance carries enough metadata for
downstream consumers to know whether it was bundled or sideloaded,
and for sideloaded ones, which package).

### `wiki doctor` sideload section

A new section appears in `wiki doctor` output (only when at least
one sideload package is installed; absent otherwise). Shape:

```
Sideload primitives:
  From package <package-a> (version <X.Y.Z>):
    - <kind>: <name>
    - <kind>: <name>
  From package <package-b> (version <X.Y.Z>):
    - <kind>: <name>

Sideload primitives with dropped unknown fields:
  <package-a>::<name>: unknown fields {<field-a>, <field-b>} ignored (extra='ignore')
```

The "Sideload primitives" subsection is informational (no
issue-shape entry). The "dropped unknown fields" subsection is a
soft warning — listed but not counted toward the `wiki doctor`
finding count or exit code. Bundled primitives never appear here
(they load with `extra='forbid'`; an unknown field on a bundled
primitive is a load-time `ValidationError`, not a doctor warning).

### `wiki outcomes` provenance column

`wiki outcomes` adds a `Source` column to its existing output.
Values: `bundled` (no decoration) or `sideload:<package>` (the
distribution name from `importlib.metadata`). Rendering:

```
Verb                Source                          Operation
weekly-digest       bundled                         weekly-digest
plan-meals          bundled                         meal-planning
roll-up-podcasts    sideload:wiki-primitive-pod     roll-up-podcasts
```

Column ordering, exact whitespace, and the inline-column-vs-section
choice belong to the implementation PR; the contract is that a
reader of `wiki outcomes` can see provenance at a glance.

### Slash-stub managed-region provenance block

Every slash-stub written by the kit at `.claude/commands/<verb>.md`
carries a managed-region block with id `outcome-provenance`. The
region contents differ by source:

- **Bundled primitive.** The region block is present but empty (no
  body content between the delimiters). Treating bundled as
  "present-and-empty" rather than "absent" keeps the managed-region
  diff stable across `wiki upgrade` runs and avoids a separate code
  path for "decide whether to emit the block."
- **Sideloaded primitive.** The region body is a single
  blockquote-rendered note:

  ```
  <!-- BEGIN MANAGED: outcome-provenance -->
  > From sideload package: `<package>` (version `<version>`).
  > The kit does not validate third-party trigger rates.
  <!-- END MANAGED: outcome-provenance -->
  ```

The managed-region id is **`outcome-provenance`** (deliberately
namespaced to "outcome" to reserve the id for slash-stubs and avoid
collisions with any future `provenance`-named region in a different
file). The delimiters follow the convention pinned by
`llm_wiki_kit/managed_regions.py:7-9, 52-55` —
`<!-- BEGIN MANAGED: <id> -->` / `<!-- END MANAGED: <id> -->`. The
region's owner is the kit itself (the slash-stub generator); no other
primitive contributes to this region. The region body is re-rendered
fresh on every `safe_write` of the slash-stub from
`importlib.metadata.version(package)`; a sideload package version
bump between `wiki upgrade` runs therefore changes the region body
and surfaces through the existing drift detection in ADR-0004 (the
new body lands as a `.proposed` sidecar if the user has edited the
file, otherwise re-renders cleanly). This is intentional: a sideload
package upgrade is something the user should *see*, not something
the kit silently absorbs.

### Error messages on collision

Three load-time error shapes (raised as `WikiError` subclasses; the
implementation PR picks the exact subclass and the message wording,
the contract is that the user sees a specific, actionable message
and a non-zero exit):

1. **Name collision with bundled:**
   `"Sideload package '{pkg}' provides primitive '{name}', but
    '{name}' is already bundled with the kit. Uninstall '{pkg}' or
    rename its primitive."`
2. **Name collision between two sideloads:**
   `"Sideload packages '{pkg_a}' and '{pkg_b}' both provide
    primitive '{name}'. Uninstall one."`
3. **Sideload `templates/` missing or unreadable:**
   `"Sideload package '{pkg}' is installed but no templates/
    directory was found at its package root."`

Outcome-verb collisions across the merged catalog raise via the
existing `check_outcome_verb_uniqueness` path
(`primitives.py:411`); the message is unchanged but the catalog
the check operates on now includes sideloaded operation primitives.

## Behavior

### Happy path: discovery + merge

1. `discover_primitives(templates_dir)` walks the bundled
   `templates_dir` exactly as today (`primitives.py:359–414`),
   collecting `Primitive` instances and `OperationContract`
   instances per the existing loop body.
1. After the bundled walk, the loader invokes
   `_discover_sideloaded_template_dirs()` (new helper). The helper
   calls
   `importlib.metadata.entry_points(group="wiki-primitive")`,
   resolves each entry point to a `(package_name, version,
   templates_path)` triple, and returns the list. An empty entry-
   point group returns an empty list.
1. For each sideloaded triple, the loader runs the same per-kind
   directory walk it ran against the bundled `templates_dir`, with
   one source-discriminating change: every `Primitive` instance
   produced for a sideloaded primitive is constructed through the
   `extra='ignore'` policy (see §"Source-scoped extra-field
   policy" below) and carries metadata identifying the source
   package + version.
1. After every walk completes, the loader checks for collisions
   across the merged catalog (see §"Collision policy" below). If
   any collision fires, the loader raises immediately — the caller
   sees a load-time error, not a partial catalog.
1. After the collision check, the loader runs
   `check_outcome_verb_uniqueness` against the merged
   `OperationContract` list (same call as today,
   `primitives.py:411`). The check is source-agnostic — verbs from
   sideloaded contracts compete with verbs from bundled contracts
   in the same namespace. The catalog-is-the-namespace invariant
   from `docs/specs/outcome-named-entry-points/spec.md` extends
   transitively.
1. The loader returns the alphabetically-sorted merged list.

### Source-scoped extra-field policy

The current `Primitive` model uses `_StrictModel` with
`extra='forbid'` (`llm_wiki_kit/models.py:36–44`). This catches
typos in hand-edited bundled `primitive.yaml` files and is
load-bearing for bundled-catalog quality. The spec preserves it for
bundled primitives and applies `extra='ignore'` only for sideloaded
primitives.

**Mechanism (the contract):**

- A bundled primitive loads through `Primitive.model_validate(...)`
  exactly as today. Unknown fields raise `ValidationError`. No
  change.
- A sideloaded primitive loads through
  `Primitive.from_sideload(...)` (new classmethod or equivalent
  loader helper — the implementation PR picks the exact shape;
  contract is "a separate constructor path that the bundled walk
  does not invoke"). The constructor:
  1. Computes top-level dropped-field names as
     `tuple(sorted(set(data.keys()) - set(Primitive.model_fields)))`
     *before* validation.
  2. Iterates the same set-difference against
     `Contribution.model_fields` for every entry in
     `data.get("contributes_to", [])` and against
     `PrimitiveRouting.model_fields` for `data.get("routing")`,
     concatenating the nested dropped-field names with a
     `<key>.<field>` namespace so the doctor surfacing can name
     where the drop happened.
  3. **Pre-strips** the captured unknown fields by constructing
     a shallow-copied input — `stripped_data = {k: v for k, v in data.items() if k in Primitive.model_fields}`,
     with the same key-filter recursively applied to each
     `Contribution` entry under `contributes_to` and to the
     `routing` dict if present. The caller's `data` dict is not
     mutated. After stripping, constructs the `Primitive` via
     standard `Primitive.model_validate(stripped_data)` — the nested
     `_StrictModel`-based `Contribution` and `PrimitiveRouting`
     now see only known fields and accept cleanly. This avoids
     the parallel-class problem (`ContributionLax` /
     `PrimitiveRoutingLax`) that downstream `isinstance` callers
     would otherwise have to handle; the type system stays single-
     hierarchy, the dropped-field surfacing still works (the names
     are captured before stripping). Pydantic v2 does not allow
     overriding nested `model_config.extra` from outside at
     validation time, so pre-stripping is the only mechanism that
     preserves both the single-hierarchy invariant and the
     ignore-mode behavior for sideloads.
  4. Sets the resulting model's `_dropped_fields` private attribute
     to the captured tuple (Pydantic v2 supports private attributes
     via `PrivateAttr` or `__pydantic_extra__`). The attribute
     travels with the `Primitive` until `wiki doctor` reads it.

The two paths share **everything else**: the same field
validators, the same `kind` enum, the same `schema_version` field
(see next subsection), the same `Contribution` / `PrimitiveRouting`
nested-model validation. The only behavioral difference is the
`extra` policy and the dropped-field capture. A sideloaded
primitive that ships only declared fields loads identically to a
bundled one with the same `primitive.yaml`.

### Schema versioning (v1 freeze)

The `Primitive` model gains a `schema_version: int = 1` field
(precedent already exists on event models, e.g.
`models.py:283` `VaultInitEvent.schema_version` and
`models.py:299` `VaultGitInitializedEvent.schema_version`). The
kit accepts only `schema_version == 1` at this RFC's acceptance.

- A bundled primitive omitting `schema_version` parses with the
  default `1`. No bundled `primitive.yaml` needs updating to ship.
- A sideloaded primitive omitting `schema_version` likewise parses
  with the default `1`. The sideload package author may declare
  `schema_version: 1` explicitly for clarity but is not required to.
- A primitive declaring `schema_version: 2` (or any value other
  than `1`) raises a load-time `WikiError` with the message
  `"primitive.yaml schema_version {n} is not supported by kit
   {kit_version}; supported: 1"`. This message applies equally to
  bundled and sideloaded primitives — the same future-compat error
  surface fires from both sources.

The change-path policy is the kit's commitment, not part of the
loader behavior, but lives here so it can be cited:

1. **Additive change (new optional field with a default).**
   Backward-compatible. Ships in any kit release without an RFC.
   Sideload packages depending on v1 continue to parse.
1. **Breaking change (field rename, removal, type change,
   semantics change).** Requires a fresh RFC, a pinned deprecation
   period, and a named migration path. May not land in a minor
   release.
1. **Major version bump.** A kit 3.0.0 may introduce
   `schema_version: 2`; the kit reads both schemas during a stated
   deprecation window. Sideload packages at v1 see a deprecation
   warning, not a load failure, during the window.

### Collision policy (additive-only)

Five collision points across the merged catalog, all enforced at
load time:

1. **Primitive name collision: sideloaded vs. bundled.** Load-time
   `WikiError`. Message per §Outputs. Bundled wins is *not* the
   policy; the policy is to *forbid* the collision and force the
   sideload author to rename. This is the load-bearing
   "additive-only" mechanic that the previous "bundled wins by
   default" framing (an earlier RFC-0007 revision) was rejected in
   favor of. Override is fork-the-kit territory or upstream-PR
   territory, not sideload territory.
1. **Primitive name collision: sideloaded vs. sideloaded.**
   Load-time `WikiError`. Message per §Outputs. The user resolves
   by uninstalling one of the two packages.
1. **Outcome-verb collision across the merged catalog.** Existing
   `check_outcome_verb_uniqueness` at `primitives.py:411` fires.
   The catalog-is-the-namespace invariant from
   `docs/specs/outcome-named-entry-points/spec.md` extends —
   sideloaded operation primitives compete in the same verb
   namespace as bundled ones. Reserved verbs
   (`RESERVED_OUTCOME_VERBS`, `primitives.py:91–112`) remain off
   limits for both sources.
1. **Region collision (per ADR-0006).** Existing region-collision
   detection in the install pipeline
   (`install.aggregate_region_contributions` plus the
   region-owner-uniqueness gate) extends across the merged
   catalog. A sideloaded primitive that contributes to a managed
   region a bundled primitive already owns raises the existing
   region-collision error path; the message text remains as-is,
   only the contributors involved change.
1. **SKILL-directory path collision.** Two primitives contributing
   the same `files/skills/<skill>/` directory across the merged
   catalog raise a load-time error. Today's bundled-only loader
   has no such case (the catalog is hand-curated); the merged
   catalog must enforce it because sideload package names are not
   coordinated. The implementation extends the existing
   contribution-validation pass in `install.py` to detect the
   collision.

### Install-time gates extended across the merged catalog

The four install-time gates RFC-0007 §(2) named:

1. **Catalog-load outcome-verb shape + uniqueness** — see §"Happy
   path" step 5 above.
1. **SKILL-fragment validation** —
   `install.validate_outcome_skill_fragments` reads
   `<source>/files/skills/<skill>/SKILL.md` per operation primitive
   to verify the SKILL.md description contains each declared
   outcome verb as a whole word (per
   `docs/specs/outcome-named-entry-points/spec.md`). For a
   sideloaded primitive, `<source>` is the resolved
   `importlib.resources.files(package) / "templates" / <kind> / <name>`
   path. The gate's existing implementation operates on
   `pathlib.Path`; the regular-wheel-install requirement (see
   §Inputs) ensures the path is filesystem-traversable. A
   sideloaded primitive whose SKILL.md fragment lacks its declared
   outcome verb raises the existing
   `validate_outcome_skill_fragments` error.
1. **Recipe-binding name resolution** — when a recipe's
   `primitives:` list references a name, the resolver walks the
   merged catalog. Resolution is name-only; no source filter, no
   precedence beyond the additive-only collision policy.
1. **Regular-wheel install requirement** — documented in §Inputs.
   No active enforcement code; the kit's reliance on
   `pathlib.Path` operations is sufficient to surface a
   zipped-wheel sideload at the first SKILL-fragment read.

### Provenance decoration

Three surfaces (see §Outputs for shapes):

- `wiki outcomes` adds a `Source` column.
- The slash-stub at `.claude/commands/<verb>.md` carries a
  `outcome-provenance` managed-region block, populated for sideloaded
  primitives and empty for bundled.
- `wiki doctor` adds a Sideload-primitives section.

These three are the **only** user-visible provenance surfaces.
This spec does **not** mutate the `by` field on journal events,
does **not** add a "from-sideload" prefix to `wiki ingest` output,
and does **not** decorate the bundled-primitive output of
`wiki outcomes` or any other affordance. The principle is:
provenance is visible where the affordance lives, not annotated
everywhere downstream.

### Edge cases

- **No sideload packages installed.** `discover_primitives` returns
  the bundled catalog unchanged. No `wiki doctor` sideload
  section, no `wiki outcomes` `Source` column drift (the column is
  always rendered for consistency, all rows show `bundled`).
  Performance and behavior identical to today's loader.
- **Sideload package installed but its `templates/` directory is
  empty.** Treated as "package contributes no primitives" — no
  collision, no error. The package's metadata still surfaces in
  `wiki doctor`'s installed-sideload listing (with an empty
  primitives sub-list) so the user sees the package is recognized
  but inactive.
- **Sideload package installed but `templates/` directory does not
  exist.** Load-time `WikiError` per §"Error messages." This is a
  package-author bug; the kit surfaces it loudly.
- **Sideload package's `primitive.yaml` declares a `kind` outside
  the five-kind enum.** Same `ValidationError` a bundled primitive
  would raise. The five-kind taxonomy is enforced uniformly.
- **Sideload package ships a `recipes/` directory at the package
  root.** Silently inert today (the kit's recipe loader only
  looks at the kit's repo-root `recipes/`, not at any sideload
  package's tree). The merged catalog walk doesn't trip on it
  either — discovery walks `templates/`, not the package root.
  `wiki doctor` surfaces a soft warning naming the package and
  recommending removal so the user who installed a package
  expecting it to ship a recipe sees the kit dropped it (the
  smallest "honesty over capability" surface). Sideload-package
  recipes are not a kit feature today; whether they become one is
  a future RFC.
- **Sideloaded primitive declares a `schema_version` greater than
  1.** Load-time `WikiError` per §"Schema versioning." The error
  message tells the user the kit's supported version range and
  names the offending package.
- **Sideloaded primitive declares an unknown field at the top
  level of `primitive.yaml`.** The field is dropped via
  `extra='ignore'`. The dropped field name is captured and
  surfaced in `wiki doctor`'s "Sideload primitives with dropped
  unknown fields" subsection. No load failure.
- **Bundled primitive declares an unknown field.** Load-time
  `ValidationError` (existing `_StrictModel` `extra='forbid'`
  behavior). No change.
- **User-authored recipe (`recipes/my-vault.yaml`) composes
  sideloaded primitives.** Supported. The recipe resolver walks
  the merged catalog the same way it walks the bundled catalog
  for `family.yaml`. The recipe is not a *starter input* — see
  §Invariants on the projection invariant pin.
- **Sideload package uninstalled while a vault has it installed.**
  Vault state in the journal continues to show the primitive as
  installed (the journal is the source of truth per ADR-0002).
  Discovery does not surface the primitive in the catalog. Next
  kit invocation that touches the primitive (e.g. `wiki upgrade`
  with the primitive still listed in the recipe) raises
  `PrimitiveError("primitive '<name>' not found in catalog")`.
  `wiki doctor` reports the mismatch as a `missing-primitive`
  issue, with a hint pointing at the previously-installed
  sideload package.
- **Two entry points in the same package.** A single package
  declaring multiple entries under `wiki-primitive` resolves each
  one. Each entry's templates path is walked independently.
  Useful when one package wants to ship two unrelated primitive
  groups.

### Error cases

- **`importlib.metadata.entry_points` raises.** The kit lets the
  exception propagate with the original message — this is a
  Python-runtime infrastructure failure, not a kit concern.
- **A sideload package's `primitive.yaml` is malformed YAML.**
  Existing `load_primitive` error path
  (`PrimitiveError` / `WikiError` shape). The package name is
  prepended to the error message so the user can find the
  offending file.
- **A sideload package's `contract.yaml` is malformed.** Existing
  `load_operation_contract` error path
  (`primitives.py:309–357`). Same package-prefix treatment.
- **Outcome-verb collision after merge.** Existing
  `check_outcome_verb_uniqueness` error. The message lists every
  primitive contributing the colliding verb, with `bundled` or
  the sideload package name as the source attribution.

## Invariants

- **Additive-only catalog growth.** A sideload package adds
  primitives to the catalog; it cannot replace a bundled primitive
  by name, cannot override a bundled region, cannot claim a
  bundled SKILL path, cannot duplicate an outcome verb. Override
  is fork-the-kit or upstream-PR territory.
- **Bundled-catalog behavior unchanged in the no-sideload case.**
  An installation with no `wiki-primitive` entry points behaves
  bit-for-bit identically to today's kit, in every CLI path and
  output. No log line, no doctor section, no `wiki outcomes`
  column drift, no slash-stub region change (bundled
  slash-stubs ship the empty `outcome-provenance` block, see §Outputs).
- **Source-scoped `extra` policy preserves the bundled typo
  guard.** A bundled primitive's hand-edited `primitive.yaml`
  continues to fail loudly on unknown fields. Only sideloaded
  primitives accept unknown fields, and even then only with a
  visible `wiki doctor` surface.
- **Five-kind taxonomy is invariant.** Sideload packages cannot
  introduce a sixth kind. `_CATALOG_DIRS` remains the load-bearing
  enumeration (`primitives.py:61–69`). A future sixth kind
  requires an upstream RFC and touches the recipe binding,
  loader, validators, and `wiki doctor` together.
- **The library boundary holds.** Sideloaded primitives are
  *content* (manifests, templates, schemas) plus declarative
  dispatch metadata (`contract.yaml`'s outcome verbs). The kit
  invokes no callable shipped by a sideload package. Discovery is
  package-name → templates-path, never package-name → function.
  The kit retains the dispatch surface; sideloaded primitives are
  inputs at install-and-dispatch time, not surfaces the kit
  delegates to.
- **RFC-0006's projection invariant is preserved by mechanical
  anchor.** `RECIPE_TARGETS` (today
  `{family → starters/, work-os → starters/, personal → docs/guides/how-to/_examples/}`
  in `starters/regenerate.py`) becomes the load-bearing definition
  of "starter input." `regenerate.py` and the
  `starter-seed-coverage` check both read it; the seed-coverage
  check additionally filters to entries whose parent directory is
  `starters/` so the `personal` entry (a docs-infrastructure
  vault, per RFC-0006) is excluded from seed-coverage audit while
  still being a `regenerate.py` target. User-authored recipes
  composing sideloaded primitives are *not* in `RECIPE_TARGETS`,
  are not rendered by `regenerate.py`, and are not audited by
  the seed-coverage check. This invariant is enforced by task T9
  in the plan (amendment to `starter-seed-coverage/spec.md`).
- **No new write path.** `safe_write` remains the only sanctioned
  vault write. Sideloaded primitives contribute pages and managed
  regions through the same install pipeline bundled primitives
  use.
- **No new top-level directory.** This spec adds none. The new
  test fixture directory `tests/fixtures/primitive-sideload/`
  sits inside the existing `tests/fixtures/` tree.

## Contracts with other modules

- **`llm_wiki_kit.primitives`.** Gains
  `_discover_sideloaded_template_dirs() -> list[tuple[str, str, Path]]`
  (the tuple holds package name, version, templates-path). The
  existing `discover_primitives(templates_dir)` signature is
  unchanged; the merge with sideloaded sources happens inside the
  function. The exact internal structure (whether a new
  `_walk_kind_directories(dir)` extracted helper appears, or the
  existing nested-loop body is repeated) is the implementer's
  call. The function returns a list of `Primitive` instances,
  each carrying source attribution.
- **`llm_wiki_kit.models`.** Gains `schema_version: int = 1` on
  `Primitive`. Gains `Primitive.from_sideload(data, source: str)`
  classmethod (or equivalent — the implementation PR picks the
  exact name) constructing a `Primitive` with `extra='ignore'` and
  capturing dropped-field names per the recursive mechanism in
  §"Source-scoped extra-field policy." Gains a
  `source: str = Field(default="bundled", exclude=True)` field on
  `Primitive` so the attribute is accessible as `primitive.source`
  but does not appear in `model_dump()` output (preserving JSON-
  serialisation round-trips for any caller that consumes the
  dump shape — including the journal's primitive-install events,
  which today serialise primitives as their declarative shape, not
  as their loader-populated state). The bundled-load path
  (`Primitive.model_validate`) is unchanged behaviourally; it
  defaults `source` to `"bundled"`.
- **`llm_wiki_kit.install`.**
  `validate_outcome_skill_fragments(*, primitives: Sequence[Primitive], sources: Mapping[str, Path])`
  (actual signature at `install.py:531-535`) is unchanged; the
  call site is extended to pass the merged primitive list plus a
  `sources` mapping that includes sideloaded primitive paths.
  `aggregate_region_contributions` plus the region-collision
  check extend to detect cross-source collisions (no signature
  change; the source attribution on `Primitive` flows into
  existing error messages).
- **`llm_wiki_kit.doctor`.** Gains a new check function (e.g.
  `check_sideload_packages`) that returns a list of informational
  `Issue` or `Note` shapes (the implementation PR picks the
  shape to match `doctor.py`'s existing patterns). The check runs
  unconditionally; the rendered section is suppressed when the
  installed sideload set is empty.
- **`llm_wiki_kit.cli`.** `_cmd_outcomes` reads each primitive's
  source attribution and emits a `Source` column.
- **The slash-stub generator** (currently embedded in
  `install.py`'s SKILL-fragment installation per
  `docs/specs/outcome-named-entry-points/spec.md`). Adds a
  `outcome-provenance` managed-region block to every emitted
  `.claude/commands/<verb>.md`. Block body computed from the
  contributing primitive's source attribution.
- **`starters/regenerate.py`.** `RECIPE_TARGETS` is elevated to
  the load-bearing constant for "starter input" (task T9 in the
  plan). No code change in this PR; the elevation is the
  amendment to `docs/specs/starter-seed-coverage/spec.md` that
  T9 lands together with any re-export refactor needed to share
  the constant between `regenerate.py` and `check_coverage.py`.
- **`pyproject.toml`** (the kit's). **Unchanged.** The
  `wiki-primitive` group is declared by *sideload package
  authors* in their packages, not by the kit. The kit reads the
  group at runtime via `importlib.metadata.entry_points`; it
  does not publish to it.

## Acceptance criteria

Tests live under `tests/unit/test_primitive_sideload.py` and
`tests/integration/test_primitive_sideload.py`. Fixtures live in
`tests/fixtures/primitive-sideload/`. Two-layer test strategy:

- **For most ACs (the merge logic, collision policy, validation
  gates, doctor surface, outcomes column, slash-stub region):**
  `monkeypatch.setattr(llm_wiki_kit.primitives, "_discover_sideloaded_template_dirs", lambda: [(name, version, tmp_path / "fake-pkg" / "templates")])`
  combined with a `tmp_path`-built fake package `templates/<kind>/<name>/primitive.yaml`
  tree. This isolates each AC from `importlib.metadata`'s
  site-packages scan and lets the test fixture vary the
  sideloaded primitive set freely. No `pip install` in the test
  loop; the fixture is filesystem-only.
- **For `_discover_sideloaded_template_dirs` itself (one focused
  AC):**
  `monkeypatch.setattr(importlib.metadata, "entry_points", lambda group=None: [<fake EntryPoint>] if group == "wiki-primitive" else [])`
  combined with a `tmp_path`-built fake package whose
  `importlib.resources.files()` returns the fake package path.
  The fake EntryPoint's `load()` returns a `SimpleNamespace`
  with the right `__name__` and `__path__` so the kit's
  resolution finds the templates tree.

`pip install -e <fixture>` is **not used** — it pollutes the
test environment, parallel test runs collide, and the resulting
test loop is slow. The monkeypatch-plus-filesystem approach
exercises the same contract (the loader reads from a directory
on disk after entry-point resolution) without the install cost.

- [ ] **AC1.** Against the live repo state at the time the
      implementation PR opens, with no `wiki-primitive` entry
      points installed, `discover_primitives(templates_dir)`
      returns a list byte-equivalent to today's loader output.
      Behavior parity for the no-sideload case.
- [ ] **AC2.** With one fixture sideload package installed
      providing one content-type primitive `sample-foo`,
      `discover_primitives` returns the bundled list plus the
      sideloaded primitive (alphabetically sorted). The
      sideloaded `Primitive` instance reports its source as
      `sideload:<package>` (asserted via the source-attribution
      attribute the implementation PR introduces).
- [ ] **AC3.** Name collision: a fixture sideload package
      attempting to provide a primitive named `recipe` (a bundled
      content-type) raises a `WikiError` at discovery whose
      message contains both the bundled primitive name and the
      offending sideload package name.
- [ ] **AC4.** Two fixture sideload packages both providing a
      primitive named `dnd-session-notes` raise a `WikiError`
      whose message names both contributing packages. (The
      "uninstall either" remediation is verified at use-site by
      the user, not by the test — the catalog returns to clean
      once either package leaves the entry-point set; the test
      asserts the *contract*, the user-visible error message.)
- [ ] **AC5.** Outcome-verb uniqueness across merged catalog: a
      fixture sideload operation primitive declaring
      `outcomes: [weekly-digest]` (a bundled outcome verb) raises
      via `check_outcome_verb_uniqueness`. The error message
      attributes both contributors (`bundled` and the sideload
      package name).
- [ ] **AC6.** Sideload `extra='ignore'` with doctor surfacing: a
      fixture sideload primitive whose `primitive.yaml` declares
      an unknown field `hint_for_kit_2_2: <anything>` loads
      cleanly; `wiki doctor` (run against an installed vault)
      lists the package + primitive + dropped-field name under
      the "Sideload primitives with dropped unknown fields"
      subsection.
- [ ] **AC7.** Bundled `extra='forbid'` preserved: a bundled
      `primitive.yaml` (fixture) with the same unknown field
      raises a `ValidationError` at discovery. Asymmetry
      asserted directly — the same field, two sources, two
      outcomes.
- [ ] **AC8.** Schema version freeze (symmetric across sources):
      a fixture *sideload* primitive declaring `schema_version: 2`
      raises a `WikiError` at discovery whose message names the
      supported version range (`1`) and the offending package; a
      fixture *bundled* primitive declaring `schema_version: 2`
      raises the same error class with the same message shape
      (the package name slot is replaced with the primitive's
      `templates/<kind>/<name>/primitive.yaml` path). The
      bundled-side and sideload-side errors share the contract.
- [ ] **AC9.** Region collision across merged catalog: a fixture
      sideload primitive declaring a `regions/` contribution to a
      region a bundled primitive owns raises the existing
      region-collision error path. Asserted via the install
      pipeline (`install.aggregate_region_contributions` or its
      caller), not just discovery — the error must fire at the
      right pipeline stage.
- [ ] **AC10.** SKILL-directory path collision: a fixture sideload
      primitive whose `files/skills/<skill>/` path matches a
      bundled primitive's SKILL path raises a load-time
      `WikiError` naming both contributors.
- [ ] **AC11.** SKILL-fragment install gate: a fixture sideload
      operation primitive declaring `outcomes: [plan-podcasts]`
      whose `files/skills/<skill>/SKILL.md` description does
      *not* contain `plan-podcasts` as a whole word raises the
      existing `validate_outcome_skill_fragments` error. The
      gate runs against sideloaded paths.
- [ ] **AC12.** `wiki doctor` sideload section: against a vault
      with one installed sideload package providing two
      primitives, `wiki doctor` output contains a "Sideload
      primitives" section listing the package, version, and the
      two primitives. Bundled primitives never appear in this
      section.
- [ ] **AC13a.** `wiki outcomes` `Source` column populated: against
      a vault with one bundled operation and one sideloaded
      operation installed, `wiki outcomes` output renders a
      `Source` column with values `bundled` and
      `sideload:<package>`, respectively.
- [ ] **AC13b.** `wiki outcomes` `Source` column always-present:
      against a vault with no sideload packages installed,
      `wiki outcomes` output renders the `Source` column on every row
      with the value `bundled`. The column is unconditional (no
      header row is emitted — `wiki outcomes` has never rendered
      column headers, and the Source column inherits that contract).
- [ ] **AC14.** Slash-stub provenance region: the slash-stub
      generated for a sideloaded operation primitive contains a
      `<!-- BEGIN MANAGED: outcome-provenance --> … <!-- END MANAGED: outcome-provenance -->`
      block whose body is a blockquote naming the sideload
      package and version (read fresh from
      `importlib.metadata.version(package)` at render time). The
      bundled-counterpart stub contains the same region delimiters
      with an empty body. Both round-trip through `safe_write`
      without drift on a no-op `wiki upgrade` **when the sideload
      package version is unchanged between runs**; a sideload
      version bump between runs legitimately produces drift (the
      new version lands in the region body) that flows through the
      existing `.proposed` path per ADR-0004 — this is the
      contract, not a bug.
- [ ] **AC15.** Recipe binding across merged catalog: a fixture
      user-authored recipe `recipes/test-vault.yaml` referencing
      one bundled primitive and one sideloaded primitive resolves
      cleanly via the existing recipe-resolver path. The closure
      walker (`recipes.resolve_recipe_primitives`) treats both
      sources identically.
- [ ] **AC16.** Projection invariant pin: with one sideloaded
      primitive installed and `recipes/test-vault.yaml`
      referencing it, `starters/regenerate.py --check` is
      unaffected (operates only on `RECIPE_TARGETS` recipes,
      which remain `{family, work-os, personal}` — with
      `personal` rendering into the docs `_examples/` tree, not
      `starters/`), and `starters/check_coverage.py` likewise
      does not audit the user-authored recipe (the check filters
      `RECIPE_TARGETS` to entries whose parent is `starters/`,
      so the user-authored recipe and the docs-infrastructure
      `personal` entry both stay out of seed-coverage scope). The assertion has two halves: (a)
      the existing tests
      (`tests/integration/test_starters_regenerable.py`,
      `tests/integration/test_starter_seed_coverage.py`) continue
      to pass with the user-authored recipe present in `recipes/`
      (the existing tests' baseline does not include it); (b)
      `starters/regenerate.py` carries an `__all__` export
      naming `RECIPE_TARGETS` plus a leading
      `# Load-bearing: …` comment per T9, asserted by a static
      check (`tests/unit/test_recipe_targets_anchor.py`) that
      reads the file and verifies both the `__all__` entry and
      the comment marker exist. (c) `starters/check_coverage.py`
      reads `RECIPE_TARGETS` from `starters.regenerate` through
      its `_load_recipe_targets()` helper (which intentionally
      keeps the import lazy per the boundary guarantee at
      `check_coverage.py:79-91`), asserted by an identity check:
      `check_coverage._load_recipe_targets() is regenerate.RECIPE_TARGETS`
      (same object returned by the helper, not a duplicated
      literal — defeats the "same-output-different-source"
      refactor that would silently break the projection
      invariant, while preserving the lazy-import boundary the
      seed-coverage script relies on). The anchor is what makes
      T9's "no behavior change" testable — the sigil plus the
      identity assertion is the contract.
- [ ] **AC17.** Uninstalled-sideload mismatch: a fixture journal
      contains a `PrimitiveInstallEvent` for a sideloaded
      primitive whose owning package has been pip-uninstalled.
      `wiki doctor` reports a `missing-primitive` issue with a
      hint naming the previously-installed package. The exit
      code follows the existing doctor contract.
- [ ] **AC18.** Zipped-wheel sideload non-goal documented: a
      fixture installation of a zipped-wheel sideload package
      surfaces a `PrimitiveError` at the first filesystem
      operation (e.g. SKILL.md read), with the package name in
      the message. The kit does **not** silently mis-load; the
      error is the contract.
- [ ] **AC19.** `recipes/`-at-package-root soft warning: a
      fixture sideload package ships a `recipes/` directory at
      its package root. Discovery completes without raising (the
      directory is silently inert as named in §"Edge cases"), and
      `wiki doctor` includes a soft warning in its output naming
      the package and the dropped `recipes/` path with a hint
      recommending removal. The warning does not affect doctor's
      exit code (it sits alongside the dropped-unknown-fields
      subsection per AC6, not in the issue-level findings).

## Non-goals

1. **Does not introduce a sixth primitive kind.** Per
   §Invariants and RFC-0007. A sideload package needing a sixth
   kind requires an upstream RFC.
1. **Does not ship an `llm-wiki-kit-primitive-examples` reference
   package on PyPI.** The CONTRIBUTING.md (plan task T10) carries
   a worked example as a docs artifact; no external package the
   kit maintains.
1. **Does not provide an "explicit override" mechanism.** A
   sideloaded primitive cannot replace a bundled one. The
   contributor who wants to override either forks the kit or
   sends an upstream PR.
1. **Does not vendor or sandbox sideloaded packages.** The kit
   does not sandbox bundled primitives either; the trust model
   is "the user installed it on purpose."
1. **Does not validate sideloaded primitives' eval coverage.**
   The kit's `tests/evals/` covers bundled primitives only.
   Sideload package authors run their own evals; the kit's
   gates are install-time validation. Provenance decoration
   (§Outputs) makes the boundary visible at the affordance.
1. **Does not support zipped-wheel or zipapp sideload installs.**
   Same non-goal as `docs/specs/wheel-bundled-assets/spec.md`.
   AC18 asserts the failure is loud, not silent.
1. **Does not introduce a `wiki extension` umbrella verb.** The
   contributor's surface is the kit's existing CLI; the
   CONTRIBUTING.md (plan task T10) documents the workflow.
1. **Does not modify journal `by` semantics.** Sideloaded
   primitives writing through `safe_write` produce
   `PageWriteEvent` rows with `by` reflecting the operation /
   primitive name (existing convention). The journal does not
   gain a "by_sideload_package" field; provenance lives on
   user-visible affordances, not on every journal event.
1. **Does not provide cross-kit-version compatibility metadata
   on sideload packages.** The schema is frozen at v1; behavioral
   compatibility (kit-side function signatures) follows SemVer
   best-effort. Sideload package authors pin
   `llm-wiki-kit>=2.1,<3` (or equivalent) in their `pyproject.toml`.
   A future RFC may introduce richer compatibility metadata when
   evidence justifies it.
1. **Does not change `safe_write` or the journal contract.**
   Sideloaded primitives use the existing write path; no new
   sanctioned bypass.

## Constraints

- **No new runtime dependency.** Uses `importlib.metadata` and
  `importlib.resources` (stdlib) plus the existing `pydantic`
  and `pyyaml`. Per Charter Principle 3.
- **No new top-level directory.** Test fixtures live under the
  existing `tests/fixtures/` tree.
- **No new public CLI verb.** Discovery is automatic; the user
  does not invoke a "sideload" command. Behind-the-scenes the
  `wiki doctor` and `wiki outcomes` outputs gain new sections /
  columns, but the verb set is unchanged.
- **No changes to `pyproject.toml` for the kit itself.** Only
  sideload package authors declare the entry-point group.
- **No bypass of `_StrictModel` for the bundled load path.** The
  bundled typo guard remains intact; only the sideload load path
  uses `extra='ignore'`.
- **No silent shadowing.** Every collision surfaces a load-time
  error. The previous "bundled wins by default" framing
  (RFC-0007 second-draft revision) is explicitly rejected.

## Why these mechanics (over the alternatives)

### Picked: entry-point discovery + source-scoped extra-field + provenance decoration

The five RFC-0007 attack points (pytest analogy carrying conclusions,
projection-invariant user-recipe hole, ambiguous collision policy,
missing SKILL-fragment gate, casual schema versioning) are each
turned from direction into pinned behavior:

- *Pytest analogy.* The spec ports pytest's `pytest11` discovery
  *mechanism* (`importlib.metadata.entry_points` over a stable
  group string) but pins the *content shape* via the package-layout
  contract — sideloaded primitives are content trees, not Python
  hookimpls.
- *Projection invariant.* `RECIPE_TARGETS` becomes the load-bearing
  anchor (T9 amends `starter-seed-coverage/spec.md`). The merged
  catalog can grow without contaminating starter rendering.
- *Collision policy.* Additive-only. Every collision surfaces a
  load-time error with a specific message. Override is not a
  supported sideload use case.
- *SKILL-fragment gate.* The gate runs against sideloaded paths
  via the regular-wheel install requirement (AC11, AC18).
- *Schema versioning.* `schema_version: 1` field, source-scoped
  `extra` policy, deprecation path named.

### Rejected: `pytest11`-style code plugins (no separate catalog)

Sideload packages ship Python hookimpls that register primitives
imperatively. Plugin discovery runs `entry_point.load()` and
invokes a callable.

- **Pros:** maximally flexible; sideload packages can compute
  primitives at runtime.
- **Cons:** the kit's primitives are content-shaped, not
  code-shaped. Inviting code-shaped plugins re-opens the
  application-shape question Principle 5 already settled.
  Discovery-time exception handling becomes complex; debugging a
  primitive that "didn't appear" is harder when the contributor
  is a Python module rather than a file tree. The kit's existing
  validation gates (Pydantic, outcome-verb shape, SKILL-fragment
  check) all assume primitives are loaded from disk; a
  code-shaped plugin would either re-implement them or bypass
  them.

### Rejected: silent shadowing on collision (bundled wins by default)

A sideloaded primitive whose name matches a bundled one is
silently dropped; `wiki doctor` reports the shadow as a warning.

- **Pros:** allows a sideload package to "claim a name" without
  breaking the kit.
- **Cons:** the only legitimate reason to claim a colliding name
  is to *override* the bundled behavior, and the silent-shadow
  policy doesn't support that — the bundled primitive still
  wins. The policy is the worst of both: it doesn't enable
  override, but it also doesn't tell the sideload author their
  primitive is being ignored loudly. The additive-only
  alternative (this spec) surfaces the conflict at install time;
  the author sees the error and either renames their primitive
  or, if they truly want to override, forks the kit.

### Rejected: sideload primitives load through bundled validator (`extra='forbid'`)

Treat sideloaded primitives identically to bundled ones, including
the strict typo guard.

- **Pros:** simpler — one Pydantic configuration.
- **Cons:** breaks forward-compat for sideload packages. A
  sideload package shipping a `hint_for_kit_2_2: <anything>` field
  (anticipating a kit minor release) would fail to load on the
  current kit even though the field is harmless to ignore. The
  kit's freedom to add optional fields to v1 (per §"Schema
  versioning") is meaningful only if sideload packages can
  *forward-declare* them. `extra='ignore'` (sideload only) is the
  cheapest mechanism that preserves both forward-compat for
  sideloads and the typo guard for bundled.

**The Principle 1 trade-off, named.** Dropping a sideloaded
primitive's unknown field is itself a small honesty cost — the kit
accepted data it then ignored. The spec accepts the trade because
sideload's whole point is to enable forward-compat *across an
ecosystem the kit cannot coordinate the way it coordinates its own
catalog*. A sideload package that ships `hint_for_kit_2_2`
deliberately is in the right; a sideload package that ships
`outcoms` as a typo is in the wrong, and the user catches it
because `wiki doctor` surfaces the dropped-field names by package.
The bundled-side typo guard is preserved (every hand-edited
`primitive.yaml` in `templates/` still load-fails on unknown
fields). The asymmetry is the same shape RFC-0007 §"Why
entry-points don't soften Principle 5" defends: the kit retains
strict control over its own surface while permitting a documented,
visible looseness at the ecosystem boundary.

### Rejected: entry-point group named `llm_wiki_kit.primitives`

Use the Python package name as the group string.

- **Pros:** explicit pairing with the kit's import path.
- **Cons:** ties the public extension contract to a Python
  identifier the kit might want to rename later. Pytest
  deliberately uses `pytest11` (not `pytest.plugins`) for this
  reason. The kit follows the same convention with `wiki-primitive`.
