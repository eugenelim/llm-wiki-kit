# RFC-0007: Primitive contribution model — upstream PR plus sideload extension

- **Status:** Draft
- **Author:** eugenelim
- **Date opened:** 2026-05-26
- **Date closed:**
- **Related:** RFC-0001 (v2 architecture — primitive system), RFC-0005
  (narrow charter mission to the author), RFC-0006 (starters as
  projections), ADR-0002 (journal), `docs/specs/outcome-named-entry-points/spec.md`,
  `docs/specs/starter-seed-coverage/spec.md`,
  `docs/specs/wheel-bundled-assets/spec.md`

## Summary

The kit has five primitive kinds (`ontology`, `content-type`,
`operation`, `infrastructure`, `agent`) and three recipes that compose
them. Adding a *new* primitive — a new ingest skill (`ingest-podcast`),
a new content-type with template + schema cross-links, a new operation
with contract + SKILL — is the kit's most natural extension shape. But
the kit ships no `CONTRIBUTING.md`, the catalog loader walks only the
bundled `templates/` tree (`llm_wiki_kit/primitives.py:359–414`), and
no entry-point or plugin hook exists in `pyproject.toml` (only the
`wiki` script). The result is that every primitive extension today
requires forking the kit itself, and no document tells a contributor
whether their primitive belongs upstream or in their own tree.

This RFC ratifies a **hybrid contribution model**:

- **Upstream PR** to the kit's bundled catalog for primitives that
  serve any author (generic ingest skills, broadly useful
  content-types, shareable operations).
- **Sideload via a `wiki-primitive` entry-point group** for primitives
  that serve one audience or one author (audience-specific
  content-types, private operations, experimental skills). The kit
  discovers sideloaded primitives through `importlib.metadata` at
  install time and merges them into the catalog at runtime.

Both paths share the same `primitive.yaml` shape, the same recipe
binding, the same outcome-verb validation, the same install-time
SKILL-fragment gate, and the same `safe_write` write contract. The
kit's library boundary (Principle 5) is preserved — extension via
entry points over a content-shaped catalog is the pattern Hugo's
theme distribution and Sphinx's theme/extension surfaces ratified for
the same problem. RFC-0006's projection invariant (starters are
render results) is preserved by *mechanical anchor*: the follow-on
spec pins the kit-shipped recipe set as the load-bearing definition
of "starter input," and sideloaded primitives are out of that set by
construction.

The substantive RFC commitments are five: (1) two named contribution
paths with an *inlined* decision tree; (2) the `wiki-primitive`
entry-point group name and the shared validation gates; (3) a v1
schema freeze for `primitive.yaml` with a documented deprecation
path; (4) an additive-only collision policy (name collisions fail
load); (5) provenance decoration on every user-visible affordance so
Principle 1's honesty target survives. Spec follow-ons land per
§Follow-on artifacts.

## Motivation

### Three real frictions, none addressed today

1. **No `CONTRIBUTING.md` exists.** Verified absence at repo root,
   `docs/`, `.github/`. A contributor with a generic primitive
   (`ingest-podcast`, say) has no document explaining the kit's
   primitive shape, the recipe-binding requirement, the outcome-verb
   validation, the starter-seed-coverage rule, or even what shape a
   PR should take. They reverse-engineer from
   `templates/content-types/recipe/` or
   `templates/operations/weekly-digest/`.
2. **No out-of-tree primitive path.** `_CATALOG_DIRS` is a frozenset
   pinned in `llm_wiki_kit/primitives.py:61–69`; `discover_primitives`
   at `primitives.py:359–414` walks exactly one `templates_dir` and
   returns the bundled catalog. `pyproject.toml` declares one entry
   point (`wiki = "llm_wiki_kit.cli:main"`), no plugin group. An
   author who wants a private primitive — say
   `ingest-dnd-session-notes` for a personal vault — has only one
   option: fork the kit, add the primitive to `templates/`, maintain
   the fork across kit upgrades.
3. **Five-plus touchpoints with no walkthrough.** Adding one
   content-type requires: `primitive.yaml` manifest, `files/`
   directory (template + SKILL), `regions/` (schema contribution per
   ADR-0006), recipe binding (`recipes/<name>.yaml` `primitives:`
   list), and a starter seed page (per
   `docs/specs/starter-seed-coverage/spec.md`). For operations, add a
   `contract.yaml` whose outcome verbs pass
   `is_well_formed_outcome_verb` and `check_outcome_verb_uniqueness`
   (`primitives.py:407–411`). For agents, add a recipe `agents:`
   binding per RFC-0004. A contributor who misses one step doesn't
   get a clear error — they get either a load-time `WikiError`, a
   starter-seed-coverage CI failure, or a recipe-resolution gap.

### Two contributor shapes emerge from the friction

The frictions split cleanly along where the primitive *lives*. Two
distinct contributor shapes, both serving the v2 kit's
"engineering-comfortable author" (RFC-0005) but with different
shipping vehicles:

- **External upstream contributor.** Has a primitive that serves any
  author — a new ingest skill (`ingest-podcast`), a generic
  operation (`monthly-roll-up`), a broadly useful content-type
  (`book-review`). Wants to PR it into the kit's catalog so future
  `wiki init` users get it. Pain: no document tells them how. Wants:
  a CONTRIBUTING.md + clear evaluation bar.
- **Author with an audience-specific primitive.** Has a primitive
  meaningful only to them or to one audience —
  `ingest-dnd-session-notes` for a TTRPG vault, `ingest-ehr-followup`
  for a chronic-condition vault, `ingest-competitor-brief` for one
  consultancy. The primitive does not belong upstream because it
  cannot be recipe-bound generically (no kit recipe should ship it;
  no starter should be expected to demo it). Pain: no sideload path.
  Wants: a plugin-style mechanism to package and install the
  primitive without forking the kit.

A third option — authoring a user-level recipe
(`recipes/my-vault.yaml`) that composes the bundled primitives
differently — is the cheapest answer for many audience-specific
needs. Sideload's audience is the narrower case where *no bundled
primitive exists* **and** *the gap cannot be closed by recipe
composition over the existing catalog*.

### The audience signal is architectural, not pending

The reviewer's reasonable adversarial concern: neither contributor
shape has a named GitHub issue, pending PR, or maintainer-asked-for
sideload thread today. This RFC accepts that as the defensive
posture rather than fabricating evidence. The signal that justifies
acting now is architectural inevitability, not pending demand:

- RFC-0001 designed the catalog as "common core + droppable
  primitives composed by recipes" (Charter Principle 4). That
  framing presupposes the catalog grows. The catalog cannot grow
  through any path other than maintainer-authored PRs today, which
  is the friction §1 names.
- RFC-0005 narrowed the audience to the engineering-comfortable
  author, who is *exactly* the demographic willing to author a
  Python package for their own vault. Sideload is the
  affordance-shape that audience would naturally reach for.
- The cost of waiting for pending demand is paid in the fork tax —
  every kit upgrade rebases a contributor's private primitives.
  Building sideload now means the next contributor's fork tax is
  zero.

The honest bound on the addressable audience: sideload serves a
*small* fraction of the engineering-comfortable author audience —
those whose primitive is reusable enough to package as a Python
distribution but not generic enough to upstream. Most
audience-specific needs are cheaper to meet through a user-authored
recipe over the bundled catalog (per §"Two contributor shapes
emerge" above). The cost of building sideload for an empty tail is
small: one loader function and a documented entry-point group; the
v1 schema freeze and §(5) provenance decoration are the heavier
commitments and they're what reviewers should adversarially weigh.
The fallback if the audience proves empty is the (A) PR-only path
with no architectural code change at all.

This RFC asks reviewers to accept the architectural argument as
warrant. If reviewers reject it, the fallback shape is to land only
the `CONTRIBUTING.md` half (which addresses the friction §1 names
with no architectural change) and defer sideload until concrete
demand surfaces.

### What changes if we do nothing

- The kit's catalog grows only as fast as the maintainer's bandwidth
  for upstream review. Generic primitives that *would* fit upstream
  pile up in contributor forks because there's no path to land them.
- Audience-specific primitives don't get written at all — the cost
  of forking-and-rebasing-on-every-upgrade exceeds the benefit of
  one ingest skill. The kit's "common core + droppable primitives"
  framing (Principle 4) is honored only for primitives the kit
  itself ships.
- Principle 1 (honesty over capability) takes a quiet hit. The kit
  *says* it's a catalog of droppable primitives; the install
  experience is that you get exactly the bundled set and the only
  way to add to it is to become a kit maintainer.

## Proposal

The RFC ratifies five commitments. The architectural moves are
small; the policy moves are real.

### (1) Two named contribution paths

The kit recognizes two contribution paths for primitives,
distinguished by where the primitive *lives*, not by who writes it:

| Path                   | Lives in                                                | Discovered by                                                                  | Decision rule                                                                                                                          |
|------------------------|---------------------------------------------------------|--------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| **Upstream PR**        | `templates/<kind>/<name>/` in the kit                   | Existing `discover_primitives(templates_dir)`                                  | The primitive is generic — any author could plausibly use it; the kit's three shipped recipes could bind it cleanly.                   |
| **Sideload extension** | A separate Python package's `templates/<kind>/<name>/`  | New entry-point group `wiki-primitive` (see §(2) below)                        | The primitive serves one author or one narrow audience; no kit-shipped recipe should be expected to bind it.                            |

A contributor decides which path by reading the decision tree in the
new `CONTRIBUTING.md`. The tree (inlined here so reviewers ratify the
actual policy, not the promise of one) is:

> **Decision: upstream PR or sideload?**
>
> Answer all three. **Yes to all three → upstream PR.**
> **No to any one → sideload.**
>
> 1. **Could any of the kit's three shipped recipes (`family`,
>    `work-os`, `personal`) bind this primitive without surprising a
>    typical user of that recipe?** A hypothetical `ingest-podcast`
>    content-type is plausibly bound in `personal` and `family` —
>    anyone might want to clip a podcast. (For evidence the rule is
>    meaningful: the kit's shipped `meeting` content-type, pulled
>    transitively into `work-os.yaml`, and the shipped `recipe`
>    content-type, bound in `family.yaml`, both answered yes to all
>    three questions when they landed.) A new
>    `ingest-dnd-session-notes` content-type is not — no shipped
>    recipe should bind it by default.
> 2. **Does this primitive's vocabulary apply outside one audience's
>    mental model?** "Meeting", "recipe", "trip", "stakeholder" —
>    every author understands what these mean. "DnD session", "EHR
>    followup", "competitor brief" — domain-narrow. If you have to
>    explain the vocabulary before the primitive name makes sense,
>    the primitive belongs in a sideload package that targets the
>    audience that already knows it.
> 3. **Are you willing to write the starter-seed demonstration the
>    upstream path requires?** Per
>    `docs/specs/starter-seed-coverage/spec.md`, every upstream
>    content-type or ontology must be demoed by at least one seed
>    page in `starters/_seed/<recipe>/wiki/`. If you cannot produce
>    a credible seed page (because the primitive's audience has no
>    seed-shaped example among the bundled recipes), the primitive
>    belongs in a sideload package.
>
> **Spec-or-PR threshold.** Most primitives ship via plain PR (one
> ingest skill, one content-type, one operation). Specs under
> `docs/specs/` are required for: a new primitive *kind* (an RFC,
> not a spec); a new infrastructure primitive that changes
> catalog-load semantics; an operation introducing a new outcome-verb
> stem (`docs/specs/outcome-named-entry-points/spec.md` calls this
> out). When in doubt, draft a spec and ask in the PR description.

Both paths use the same `primitive.yaml` shape, the same five
`_CATALOG_DIRS`, the same outcome-verb validation, the same
install-time SKILL-fragment gate, the same `safe_write` write
contract. Sideload is not a different product — it's the same product
with a different shipping vehicle.

The `CONTRIBUTING.md` lands as a top-level file in the follow-on PR
and contains the decision tree above plus two walkthroughs (the
upstream-PR walkthrough and the sideload package walkthrough). The
walkthroughs are documentation, not policy — policy lives in this
RFC.

### (2) The `wiki-primitive` entry-point group

The smallest possible architectural change for sideload. Three
deltas:

- **`pyproject.toml`** (the kit's): no change. The entry-point
  *group name* is declared by contract in this RFC and consumed by
  the loader; only sideload-package authors declare entries.
- **A sideload package**'s `pyproject.toml`:

  ```toml
  [project.entry-points."wiki-primitive"]
  my-extension = "my_extension"
  ```

  The value is the Python package whose installed location contains
  a `templates/<kind>/<name>/primitive.yaml` tree. The kit resolves
  the path via `importlib.resources.files(value)` — the same
  mechanism `docs/specs/wheel-bundled-assets/spec.md` uses to find
  the kit's own bundled catalog inside `llm_wiki_kit/_assets/`.

- **`llm_wiki_kit/primitives.py`** gains a sideload-source resolver
  and one merge point in `discover_primitives`. The mechanical
  details (function signature, merge order, error wrapping) are
  implementation, not policy; they belong in the follow-on
  `primitive-sideload/spec.md` per §Follow-on artifacts.

The entry-point group name is `wiki-primitive`. The name is
deliberately *not* `llm_wiki_kit.primitives` (which would tie the
public extension-contract string to a Python identifier the kit
might want to rename later — a future package rename would *appear*
to break every sideload even if the contract were ported). It is
*not* `llm-wiki-kit.primitives` either (which would tie it to the
distribution name). It is a short, hyphenated, project-prefixed string in the
style of pytest's `pytest11` — intentionally decoupled from any
Python identifier the kit might want to rename. The lock the kit accepts at this RFC's acceptance is
only the string itself, not any code structure.

**Shared validation gates.** Both bundled and sideloaded primitives
pass through every existing validation gate. Three are load-bearing
and bear naming:

1. **Catalog-load time** — `is_well_formed_outcome_verb` (per-verb
   shape) and `check_outcome_verb_uniqueness` (catalog uniqueness)
   at `primitives.py:407–411`. A sideloaded primitive cannot claim
   a reserved verb (`RESERVED_OUTCOME_VERBS`, `primitives.py:91–112`)
   or duplicate a bundled verb. The catalog-is-the-namespace
   invariant from `docs/specs/outcome-named-entry-points/spec.md`
   holds across the merged catalog, not just the bundled half.
2. **Install time, SKILL fragment** — `install.validate_outcome_skill_fragments`
   reads `<source>/files/skills/<skill>/SKILL.md` from each
   primitive's source tree to verify the SKILL.md description
   contains the declared outcome verb as a whole word. For a
   sideloaded primitive, the source tree is inside a third-party
   package's installed location. **Sideload packages MUST install as
   regular wheels** (not zipped wheels, not zipapps); the kit's own
   `wheel-bundled-assets/spec.md` already names zipped/`zipapp`
   layouts as out-of-scope because the install pipeline takes
   `pathlib.Path` and uses `path.open()` / `path.iterdir()`.
   Sideload inherits the same constraint. A future RFC may extend
   `zipfile.Path` support; until then, sideload package authors
   publish unzipped wheels (the default for `pip wheel`).
3. **Install time, recipe binding** — when a recipe references a
   sideloaded primitive by name, the resolver finds it in the
   merged catalog the same way it finds bundled primitives. Recipe
   shape is unchanged.

### (3) A v1 schema freeze for `primitive.yaml`

Publishing a public extension contract today means the
`primitive.yaml` shape — today validated by the `Primitive` Pydantic
model — becomes part of the kit's public API at this RFC's
acceptance. Without an explicit commitment to stability, every
internal change to the `Primitive` model would silently break
sideload packages.

The commitment:

- The kit publishes the current `primitive.yaml` shape as **v1**
  and freezes it. A `schema_version: 1` field is added to
  `primitive.yaml` (defaulting to `1` if absent, so existing
  bundled primitives continue to parse).
- Any change to v1 must take one of three shapes:
  1. **Additive — new optional field with a default.** Backward
     compatible; can ship in any kit release without an RFC.
     Sideload packages depending on v1 continue to parse.
  2. **Breaking — new RFC required.** Any field rename, removal,
     type change, or semantics change requires a fresh RFC justifying
     the break, pinning a deprecation period, and naming the
     migration path for sideload packages.
  3. **Major version bump (kit 3.0.0).** A kit major-version bump
     can introduce a v2 schema; sideload packages declare
     `schema_version: 2` and the kit reads both schemas during a
     stated deprecation window. Sideload packages at v1 see a
     deprecation warning, not a load failure, during the window.

**Unknown-field policy (scoped by source).** Today the `Primitive`
Pydantic model is loaded via `_StrictModel` with `extra='forbid'`
(`llm_wiki_kit/models.py:36–44`) — a load-bearing typo guard for
hand-edited bundled YAML. The v1 contract preserves that guard for
bundled primitives and applies `extra='ignore'` *only when the
primitive's source path is a sideload-discovered package*. A
sideload primitive that ships a field the kit doesn't recognize
loads cleanly; the unknown field is dropped from the parsed model
and `wiki doctor` surfaces the dropped name so the author can see
the field isn't reaching the kit. A bundled primitive with the same
unknown field still load-fails — the typo guard the kit relies on
for its own catalog is unchanged. The follow-on spec pins the
source-discrimination mechanism (the most natural shape is a thin
loader wrapper that selects `Primitive` vs.
`Primitive.from_sideload` based on the discovered source).

**Behavioral compatibility (kit-side functions sideloads rely on).**
The v1 contract is *YAML shape only*. Kit-side function signatures
that sideloads transitively depend on
(`importlib.resources.files`'s lookup target,
`validate_outcome_skill_fragments`'s file-layout expectation, the
recipe resolver's name-lookup contract) follow SemVer best-effort —
breaking changes land in major-version bumps (kit 3.0.0) with the
same RFC + deprecation discipline the schema-break path uses.
Sideload packages should pin `llm-wiki-kit>=2.1,<3` (or equivalent)
in their `pyproject.toml`. The follow-on spec enumerates the v1
behavioral-compat surface explicitly so the boundary between "we
froze the YAML" and "we'll change the Python" is named, not
implied.

Sideload package authors who declare a `schema_version` other than
`1` against a v1-only kit see a clear load-time error
("`primitive.yaml schema_version 2 is not supported by kit 2.x`")
rather than silent breakage.

### (4) Additive-only collision policy

Naming collisions are an explicit error, not silent shadowing. The
policy:

- **A sideloaded primitive whose name matches a bundled primitive is
  a load-time error.** "Sideload package `X` provides primitive `Y`,
  but `Y` is already bundled with the kit. Uninstall `X` or rename
  its primitive." Sideload is *additive only*. A contributor who
  wants to *replace* a bundled primitive's behavior either forks the
  kit (legitimate for private vault setups) or sends an upstream PR
  with the replacement (so the kit's catalog reflects the better
  behavior).
- **Two sideloaded primitives with the same name is a load-time
  error.** Same shape as the existing outcome-verb-uniqueness gate
  at `primitives.py:411`. The user resolves by uninstalling one of
  the two packages.
- **`wiki doctor` reports the installed sideload set.** "Sideload
  primitives loaded: from package `X` — `Y`, `Z`. From package `W`
  — `V`." This is the smallest UX assist that lets the user
  understand what their kit catalog contains, and is the surface
  any collision-error message points at.
- **All existing collision gates apply transitively across the
  merged catalog.** Region collisions (per ADR-0006's
  `additive-managed-region-contributions`), SKILL-directory path
  collisions, and recipe-binding name resolution behave the same
  whether the contributing primitive is bundled or sideloaded. A
  sideload primitive cannot contribute a region a bundled primitive
  already owns, cannot write a SKILL.md path a bundled primitive
  writes, and cannot claim a recipe-binding name a bundled primitive
  claims. The follow-on spec enumerates each gate by function name
  so reviewers don't have to take the transitivity claim on faith.

The "explicit override" use case some plugin systems support
(pytest's `--noconftest`, Hugo's theme override directory) is
*excluded* from sideload's intended audience. Override is upstream-PR
territory or fork territory. Sideload exists to add primitives the
kit doesn't have, not to replace primitives the kit does have.

### (5) Provenance decoration on every user-visible affordance

Sideloaded primitives install kit-managed affordances into the
user's vault: CLI verb aliases, slash-stubs at
`.claude/commands/<verb>.md`, SKILL.md trigger fragments,
journal-event `by` fields. Once those affordances exist, a user
troubleshooting a misbehaving operation cannot tell from the
affordance surface whether the kit or a sideload package owns the
bug. Principle 1 (honesty over capability) is exactly what this
violates if left unaddressed.

Three surfaces carry provenance decoration:

- **`wiki outcomes`** lists kit-bundled and sideloaded outcomes in
  separate sections, or with an inline column distinguishing them
  ("Source: bundled" / "Source: sideload package `X`"). Spec
  follow-on picks the exact rendering.
- **The slash-stub** at `.claude/commands/<verb>.md`, when
  installed from a sideload primitive, carries a provenance line
  inside a kit-managed region (per ADR-0003 / ADR-0006). Because
  slash-stubs are kit-written and managed-region-aware, the
  provenance travels through `safe_write` like every other kit write
  — re-render on `wiki upgrade` preserves the region, and a user
  editing the stub triggers drift detection per ADR-0004. The exact
  managed-region key and rendering convention are pinned in the
  follow-on spec; the commitment in this RFC is that provenance is
  visible to a reader of the slash-stub file and that the file-format
  surface this introduces uses the existing managed-regions
  machinery, not a new convention.
- **`wiki doctor`** reports the installed sideload set as above
  and surfaces any verb whose owning primitive is sideloaded under
  a section "Sideloaded affordances." A user filing a bug against
  the kit can read this section first and decide whether to file
  upstream or against the sideload's repo.

No `verification_status` field on `primitive.yaml` — the kit doesn't
adjudicate sideload eval quality, only the *provenance* of every
affordance. A user who installs a flaky sideload sees the bug; the
provenance decoration tells them where to file it.

### What stays the same

- The five primitive kinds and `_CATALOG_DIRS` are unchanged
  (`primitives.py:61–69`).
- The recipe binding shape (`recipes/<name>.yaml`'s `primitives:`
  and `agents:` blocks) is unchanged. A recipe references primitives
  by *name*; the loader resolves names from the merged catalog
  without the recipe caring whether a primitive is bundled or
  sideloaded.
- `safe_write` and the journal contract are untouched. A primitive
  contributes to writes the same way it does today (region
  contributions, page writes via `safe_write`).
- **RFC-0006's projection invariant is preserved by mechanical
  anchor.** The follow-on spec amends
  `docs/specs/starter-seed-coverage/spec.md` (currently `Status:
  Draft`) so that `RECIPE_TARGETS` — the recipe set the
  starter-seed-coverage check audits — is the load-bearing
  definition of "starter input." `starters/regenerate.py` reads the
  same anchor. A user authoring `recipes/my-vault.yaml` that
  composes bundled + sideloaded primitives is producing a *vault*,
  not a *starter*; `regenerate.py` doesn't operate on it, and the
  starter-seed-coverage check doesn't audit it.

### What this proposal does *not* do

- **No new primitive kind.** `_CATALOG_DIRS` (`primitives.py:61–69`)
  remains load-bearing. A sideload package cannot introduce a sixth
  kind — the catalog walk only inspects the five known directories.
  A contributor whose primitive needs a sixth kind has to land an
  upstream RFC introducing it (the surfaces this RFC extends are
  stable for five kinds but a sixth would touch the recipe binding,
  the loader, the validation gates, and `wiki doctor`'s coverage —
  RFC-shaped work). Sideload makes a single primitive contribution
  cheaper; it does not make the taxonomy less load-bearing.
- **No vault-resident extension.** Sideloaded primitives install at
  the Python-environment level (the kit's), not into the vault. The
  vault never carries primitive *code*; it carries rendered output.
- **No registry, no marketplace.** The kit takes no position on
  where sideload packages live. PyPI is the obvious default; a
  contributor who wants to keep their primitive private (private
  PyPI, a git URL, a local path) is free to do so. The kit's
  discovery is `importlib.metadata`-based — wherever pip can install
  it, the kit can find it.
- **No zipped-wheel / zipapp sideload installs.** Sideload packages
  install as regular wheels so the install-time SKILL-fragment gate
  can read `<source>/files/skills/<skill>/SKILL.md` via
  `pathlib.Path` (see §(2) gate 2). The non-goal mirrors
  `wheel-bundled-assets/spec.md`'s own non-goal.
- **No commitment to ship an official sideload primitive.** The kit
  does not maintain an `llm-wiki-kit-primitive-examples` package.
  Sideloaded primitives are user-owned by construction.
- **No softening of Principle 5.** Entry-point discovery over a
  content-shaped catalog is a library-shaped extension pattern.
  See §"Why entry-points don't soften Principle 5" below.

### Why entry-points don't soften Principle 5

The kit's primitives are mostly *content* — `primitive.yaml`
manifests, `files/` trees of markdown and SKILL.md text, schema
region contributions in YAML. The one kit-executable surface a
primitive contributes is its `contract.yaml`'s outcome verbs, which
drive CLI dispatch (`wiki <verb>` routing, slash-stub generation,
the `wiki outcomes` listing). That's a real *hook-shaped
contribution*, not declarative metadata — closer to a Sphinx
*extension* than to a Sphinx *theme*. The honest precedent for that
half of the surface is therefore Sphinx extensions (which register
directives, builders, and domains and still don't drag Sphinx into
application-shape because the registrations are inputs the Sphinx
core invokes at build time, not surfaces the core delegates to).
The kit's position is the same: outcome verbs are catalog inputs
the kit registers at install time and the dispatcher reads at each
CLI invocation; the kit retains the dispatch surface throughout. The right precedent for content-shaped extension is *theme
catalogs*; the right precedent for the dispatch-surface
contributions is *Sphinx extensions*. Both are library-shaped:

- **Hugo themes.** Hugo themes are independently installable
  packages of templates, archetypes, partials, and assets — content
  by mass, with optional shortcodes (Go code) at the margins. Hugo
  discovers them via filesystem conventions
  ([Hugo themes documentation](https://gohugo.io/hugo-modules/theme-components/)).
  The Hugo binary remains a library-shaped static-site generator;
  themes are inputs to the renderer, not parts of it. Themes don't
  move Hugo into application-shape because they don't claim the
  renderer's surface — they just supply more material for it to
  render. The kit's primitive sits in the same position relative to
  the install pipeline: inputs the kit reads, not surfaces the kit
  becomes.
- **Sphinx themes and extensions.** Sphinx ships a richer extension
  surface than Hugo (extensions can register directives, transforms,
  builders) but the *theme* shape — `package_data` containing
  templates and static files, discoverable through entry points —
  is content-shaped and library-compatible. Sphinx remains a
  documentation generator (library), not an application, despite a
  large theme/extension ecosystem.

The mechanism we borrow from pytest is the *discovery mechanism*
(`importlib.metadata` entry points). The *content shape* of what
sideload packages ship — a primitive catalog — is closer to Hugo
themes than to pytest plugins. Pytest plugins are Python modules
that register hookimpls and fixtures; the kit's primitives are
template trees that the kit renders.

The application-shape risk Principle 5 forbids is *the kit doing
the agent's job*. Sideload doesn't move that line. The agent
(Claude) still reads SKILL.md and calls the kit's existing CLI;
sideloaded primitives expand what the kit *can produce*, not what
the kit *is*.

## Alternatives considered

Four paths. This RFC argues for (D); the others are recorded so the
choice is explicit.

### (A) PR-only catalog (status quo + a CONTRIBUTING.md)

Ship the `CONTRIBUTING.md` from §Proposal but reject the sideload
half. Every primitive lives upstream or doesn't exist.

*Why rejected.* Closes the upstream half of the gap, leaves the
audience-specific-primitive half open. The TTRPG vault, the
chronic-condition vault, the consultancy vault — every audience
whose primitive doesn't belong in `recipes/family.yaml` or
`work-os.yaml` gets nothing. The "common core + droppable
primitives" framing (Principle 4) is honored selectively: only for
primitives the maintainer agrees to maintain. The kit becomes more
bottlenecked, not less, as adoption grows.

*Fallback shape.* If reviewers reject the architectural-warrant
argument in §"The audience signal is architectural, not pending,"
this RFC's fallback is (A) — land only the `CONTRIBUTING.md` and
defer sideload until concrete demand surfaces. The
`CONTRIBUTING.md`'s decision tree still ships (the upstream-only
half of the tree), and the v1 schema freeze and §(5) provenance
decoration are dropped because they're sideload-supporting
commitments.

### (B) Sideload-only (no curated catalog growth)

Ship the entry-point hook but freeze the bundled catalog — every
new primitive is a sideload package, including the generically
useful ones. The kit's three shipped recipes stay frozen.

*Why rejected.* Discoverability suffers. A new user running `wiki
init --recipe family` should *get* a useful family vault without
first discovering that "actually, you should also `pipx inject
llm-wiki-kit-primitive-meal-planning`." The kit's promise (Charter
§Mission — "a catalog of droppable primitives composed by recipes")
presupposes some baseline catalog.

### (C) Fork-and-publish (every extension forks the kit)

The kit's current de-facto policy: if you want a private primitive,
fork. No documented contribution path, no plugin hook.

*Why rejected.* This is the status quo and the source of every
friction §Motivation names. The fork tax compounds with every kit
upgrade.

### (D) Hybrid — upstream PR plus sideload entry-point (this proposal)

Picked. See §Proposal.

The trade-off this RFC asks reviewers to accept: a small loader
change, a v1 schema-freeze commitment, provenance decoration on
three user-visible surfaces, and a `CONTRIBUTING.md`, in exchange
for both contribution shapes being served. The bundled-catalog path
is unchanged; sideload is an additive merge over the existing
`discover_primitives` walk.

## Drawbacks

The honest costs of accepting this direction.

- **The catalog-is-the-namespace invariant gets harder to reason
  about.** Today, "what primitives are available?" is answered by
  reading `templates/`. After this RFC, it's `templates/` plus
  whatever the active Python environment has installed under the
  entry-point group. Mitigation: `wiki doctor`'s sideload section
  per §(5) makes the merged catalog inspectable; the additive-only
  collision policy means there is never silent shadowing to puzzle
  through.
- **Outcome-verb uniqueness now spans installations.** Two sideload
  packages that both declare `outcomes: [digest-x]` collide at
  install time. Today this is impossible because the kit is the
  only catalog. Mitigation: the existing
  `check_outcome_verb_uniqueness` gate already enforces this for
  the bundled catalog; extending it across the merged catalog is
  the same code path. The error names which package to uninstall.
- **The v1 schema freeze constrains internal evolution.** Once
  `primitive.yaml` v1 is published, the kit's freedom to refactor
  the `Primitive` Pydantic model is bounded by the additive /
  RFC-gated / major-version-bump rules in §(3). Mitigation:
  intentional. The cost of publishing a public extension contract
  *is* the freeze; the alternative (refactor freely, break
  sideloads silently) is the Principle 1 violation this RFC exists
  to prevent.
- **Sideload packages can be abandoned.** A user who installs a
  primitive package from an inactive maintainer inherits a primitive
  that may not get updated as the kit evolves. Mitigation: same
  drawback every plugin ecosystem has. The kit's response is
  honest framing in CONTRIBUTING.md ("sideload packages are
  user-maintained; abandonment is on you") and the provenance
  decoration in §(5) so the user knows where to file the bug.
- **CI cannot validate sideload packages.** The kit's eval harness
  doesn't run third-party primitives. Mitigation: sideload package
  authors run their own evals. The kit's gates are install-time
  validation (outcome verbs, primitive.yaml schema, SKILL-fragment
  shape) plus the §(5) provenance decoration so the user can tell
  which affordances the kit has *not* eval-gated.
- **`starter-seed-coverage/spec.md` is still `Status: Draft` at
  this RFC's acceptance.** The references to it are directional, not
  version-locked (see §"What stays the same" for the anchor); a
  shape change to the spec amends references in the same wave
  rather than invalidating this RFC's policy.
- **Sideload is additive-only; override-shaped extension is
  unsupported.** A contributor who wants to *replace* a bundled
  primitive's behavior cannot do so via sideload. Mitigation: the
  audience this RFC names doesn't need overrides — they need new
  primitives. Override-shaped extension is fork or upstream-PR
  territory.
- **The `wiki-primitive` entry-point group name is now locked
  public API.** Renaming it later would break every sideload
  package's `pyproject.toml` declaration. Mitigation: the name is a
  short, stable string deliberately decoupled from any Python
  identifier in the kit. It can outlive a Python-package rename
  (`llm_wiki_kit` → `wiki_kit` someday) because it references no
  Python identifier.

## Prior art

External precedent for *content-shaped extension via entry-point
discovery*:

- **Hugo themes.**
  [Hugo themes documentation](https://gohugo.io/hugo-modules/theme-components/).
  Hugo themes are content distributions (templates, archetypes,
  partials, layouts, assets) plus optional shortcodes. They install
  alongside the Hugo binary, are discovered by filesystem
  convention, and are composed by the site's configuration. Hugo
  itself remains a library-shaped static-site generator; themes
  don't drag it into application-shape because they're inputs to
  the renderer, not parts of it. *Read for this RFC:* the kit's
  primitive shape is closer to Hugo's theme shape than to any code
  plugin model; the audience-segmentation a Hugo site does at theme
  selection time is the same shape the kit does at recipe selection
  time.
- **Sphinx themes and extensions.**
  [Sphinx theme documentation](https://www.sphinx-doc.org/en/master/development/html_themes/index.html).
  Sphinx themes ship as Python packages with `package_data`
  containing HTML templates and static assets, discovered through
  entry points. *Read for this RFC:* Sphinx is the closest precedent
  for "library-shaped tool that discovers third-party content
  packages via Python entry points." The kit borrows Sphinx's
  shape almost directly, scaled down to primitive catalogs.

External precedent for *the entry-point mechanism itself*:

- **pytest's `pytest11` entry-point group.**
  [Pytest plugins documentation](https://docs.pytest.org/en/stable/how-to/writing_plugins.html)
  and
  [setuptools entry-points guide](https://setuptools.pypa.io/en/stable/userguide/entry_point.html).
  Pytest plugins are *code* (hookimpls and fixtures), not content
  — so they're not the right precedent for what sideload packages
  *contain*. But the discovery mechanism (`importlib.metadata`
  entry points) and the group-name shape (a short, stable string
  deliberately decoupled from the project's Python identifier) are
  exactly what this RFC borrows.

External precedent for *curated catalog growth via PR*:

- **Obsidian community plugins.**
  [Submission process](https://docs.obsidian.md/Plugins/Releasing/Submit+your+plugin).
  A curated catalog model: plugins are PR'd to
  `obsidianmd/obsidian-releases`'s `community-plugins.json` file,
  automated review scans for security and code quality. *Read for
  this RFC:* the upstream-PR half in §(1) matches Obsidian's
  curated-catalog discipline. The difference: the kit's catalog is
  *part of the kit*, not a separate registry repo. The kit is small
  enough that a separate registry repo would be premature.

In-repo precedent:

- **`docs/specs/wheel-bundled-assets/spec.md`** — pins
  `importlib.resources` as the kit's mechanism for finding bundled
  assets inside the wheel, and names zipped/`zipapp` layouts as
  out-of-scope. Sideloaded primitives use the same mechanism with a
  different target package and inherit the same non-goal.
- **`docs/specs/outcome-named-entry-points/spec.md`** — pins the
  catalog-is-the-namespace invariant and the outcome-verb
  uniqueness gate at `primitives.py:411`. Sideloaded primitives
  pass through the same gate; §(4)'s additive-only policy is an
  application of that gate to the merged catalog.
- **`docs/specs/starter-seed-coverage/spec.md`** — pins
  `RECIPE_TARGETS` as the recipe set the coverage check audits.
  The follow-on spec elevates this constant to the load-bearing
  definition of "starter input" so the projection invariant in
  §"What stays the same" holds.
- **RFC-0004 (agent identity primitives)** — added the fifth
  primitive kind (`agent`). A sixth kind via sideload is excluded
  by §"What this proposal does not do"; if a sixth kind is ever
  needed, RFC-0004's pattern is the template.

## Unresolved questions

Each carries the author's lean.

- **What does the sideload package's `templates/` layout look like
  *exactly*?** This RFC says
  "`templates/<kind>/<name>/primitive.yaml` inside the package," and
  §(2) names the four shared validation gates. The full directory
  contract (`files/`, `regions/`, `fixtures/`, optional `evals/`)
  belongs in the follow-on spec. *Author's lean:* mirror the
  bundled layout one-for-one.
- **Should `wiki doctor` show installed sideload packages?**
  *Author's lean:* yes — committed in §(5). Spec follow-on picks
  the exact column shape.
- **Should the kit ship one reference sideload package as a worked
  example?** *Author's lean:* yes, as a docs artifact under
  `docs/guides/explanation/extending-the-kit.md`, not as a published
  PyPI package. The CONTRIBUTING.md's sideload walkthrough cites a
  worked example checked into the kit's docs tree.
- **Recipe authoring against sideload primitives — does the kit
  ship a "recipe with sideloads" example?** *Author's lean:* no,
  but document the pattern. A user writing `recipes/my-vault.yaml`
  references sideloaded primitives by name the same way they
  reference bundled ones; the recipe doesn't care about the source.
  The CONTRIBUTING.md names this explicitly so contributors don't
  think they need a different recipe shape.
- **`CONTRIBUTING.md` location: repo root or
  `docs/CONTRIBUTING.md`?** *Author's lean:* repo root. GitHub
  auto-surfaces a root-level `CONTRIBUTING.md` on issue and PR
  pages.
- **What about kit version-compatibility on sideload packages?**
  A sideload package depends on a specific `primitive.yaml` schema
  version (per §(3)) but may also depend on specific kit behaviors
  (a `safe_write` signature, an `install` pipeline shape). *Author's
  lean:* defer to the follow-on spec. Schema versioning is committed
  in §(3); behavioral compatibility likely falls out of standard
  pip dependency ranges (`llm-wiki-kit>=2.1,<3` in the sideload's
  `pyproject.toml`).

## Follow-on artifacts

Filled in when the RFC is accepted. Anticipated:

- Spec: `docs/specs/primitive-sideload/spec.md` — pins the loader
  change, the package-layout contract, the additive-only collision
  policy mechanics, the `wiki doctor` check, the `wiki outcomes`
  decoration, the slash-stub header line, and the regular-wheel
  install requirement. Includes a worked example package and
  acceptance tests against a fixture sideload. Also amends
  `docs/specs/starter-seed-coverage/spec.md` so `RECIPE_TARGETS` is
  the load-bearing anchor for "starter input."
- New top-level `CONTRIBUTING.md` — the decision tree inlined in
  §(1), plus the upstream-PR walkthrough and sideload walkthrough.
- Guide: `docs/guides/explanation/extending-the-kit.md` — the
  architectural framing (why hybrid, what each path costs, when
  each is right). Diátaxis "explanation" quadrant.
- Guide: `docs/guides/how-to/add-a-primitive.md` — the step-by-step
  for the upstream PR path (paired with CONTRIBUTING.md's
  walkthrough, but with full file-tree examples).
- Roadmap edit: one paragraph in `docs/ROADMAP.md` naming the
  hybrid model and pointing at this RFC. Sits alongside the Tier-2
  starter section (lines 60–86 of today's roadmap) as the
  *kit-extension* counterpart to RFC-0006's *vault-distribution*
  direction.
