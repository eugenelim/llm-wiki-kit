# Spec: starter-seed-coverage

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft
- **Owner:** `starters/check_coverage.py` (kit-author tooling, sits next
  to `starters/regenerate.py` — outside `llm_wiki_kit/` per RFC-0006's
  same-as-regenerator placement).
- **Related:** RFC-0006 (`docs/rfc/0006-promote-examples-to-starters.md`)
  established the projection invariant and the `regenerate.py --check`
  byte-divergence gate; this spec adds the complementary semantic-coverage
  gate. RFC-0005 (`docs/rfc/0005-charter-narrow-mission-to-the-author.md`)
  named the maintainer as the primary audience whose fix path this spec
  describes. `docs/specs/task-21-examples-tutorials/spec.md` AC6 covers
  the journal-normalization rules `regenerate.py` already encodes.
- **Constrained by:** Charter Principle 1 (honesty over capability —
  the check's false-positive shape is named in §Behavior, not papered
  over); Charter Principle 3 (no new runtime dependency — the check
  uses stdlib `pathlib` + the existing `pyyaml` already in
  `regenerate.py`'s import set); Charter Principle 5 (library-not-
  application — the check is maintainer infrastructure; it does **not**
  add a `wiki <verb>` to the wheel surface and does **not** load
  inside any user-facing kit command). RFC-0006's projection invariant
  (a starter is the deterministic output of recipe + seeds + the kit) —
  this spec checks the *input side* (do the seeds cover the recipe?)
  while `regenerate.py --check` already verifies the output side.

## What this is

`starter-seed-coverage` is a mechanical check that detects when a
starter's hand-authored seed pages no longer demonstrate every
content-type and ontology primitive the starter's recipe ships. It is
the semantic complement to `starters/regenerate.py --check`:
`regenerate.py` catches byte divergence between the committed starter
and a fresh kit-render (output drift); this check catches the case
where the kit added a new content-type or ontology and the starter's
seed pages should have grown a page demonstrating it but didn't
(input drift).

The check is a single Python script under `starters/` that loads each
shipped recipe, walks its primitive closure, and for every content-
type and ontology primitive verifies that at least one matching
hand-authored page exists under `starters/_seed/<recipe>/wiki/`. Other
primitive kinds (`operation`, `agent`, `infrastructure`) are
deliberately out of scope (see §Non-goals). The check produces a
maintainer-facing report; it does **not** auto-fix, does **not** add
a CLI verb, and does **not** ship inside the kit's wheel.

The check answers exactly one question: *given the kit's current
primitive catalog and the starter's current recipe, is every content-
type / ontology the user will see installed actually exemplified by a
real page they can read?* If the answer is no, the starter is
semantically stale and a starter user will open an empty folder where
they expected an example.

## Inputs

- `recipes/<name>.yaml` for each recipe that maps to a starter via
  `starters/regenerate.py`'s `RECIPE_TARGETS` (today: `family`,
  `work-os`; not `personal` — the conflict-pending vault is
  documentation infrastructure under
  `docs/guides/how-to/_examples/` and is deliberately not scored,
  per §Non-goals).
- The primitive catalog under `templates/{ontologies,content-types,
  operations,infrastructure,agents}/` and `core/`. Loaded via the
  existing `llm_wiki_kit.primitives.discover_primitives` /
  `load_primitive` helpers — the script imports them the same way
  `starters/regenerate.py` already imports `cli` (sibling import via
  `sys.path.insert`; the script is not on the wheel).
- `starters/_seed/<recipe>/wiki/**/*.md` — the hand-authored seed
  pages whose frontmatter and folder placement provide the mechanical
  coverage signal.
- Command-line: `python starters/check_coverage.py`. No user-facing
  flags at v1 (see §Non-goals on `--strict` and `--recipe <name>`).
  The script exposes a callable entry point (e.g. `check_coverage(
  kit_root: Path) -> list[Finding]`) alongside the CLI so the tests
  named in §"Acceptance criteria" can drive it against a fixture
  catalog without going through `subprocess`. The callable is part
  of the contract; its exact name is editable in the implementation
  PR.

## Outputs

- **Stdout, on clean coverage:** a single-line summary `coverage clean
  — <N> primitive(s) across <M> starter(s) covered` and exit code 0.
- **Stdout, on findings:** a per-recipe block listing each uncovered
  primitive, the kind that would have covered it (frontmatter `type:`
  match or folder presence), and the suggested fix path (a relative
  seed-page path the maintainer can create). Exit code **1**. The
  per-recipe blocks are sorted alphabetically by recipe, then by
  primitive name, so reruns produce stable byte-equal output.
- **Stderr:** internal errors only (catalog won't parse, recipe file
  missing). Exit code **2**, reserved for the same class of internal
  errors as `wiki doctor` (`WikiError`-shaped failures).
- **Exit-code meaning is the contract.** A local maintainer runs the
  check and gets a real signal: 0 means clean, 1 means there are
  findings to look at, 2 means the check itself broke. The spec does
  **not** prescribe whether CI gates on this exit code or merely
  surfaces it — that policy belongs to the workflow file authored
  in the implementation PR, not to this spec. See §"How CI surfaces
  this" for the considered options.
- **No file writes.** The check is read-only — it does not create
  stub seed pages, does not edit `primitive.yaml`, does not touch the
  journal. The maintainer authors the missing seed pages by hand.
- **No journal events.** Starters are not vaults the kit owns; the
  journal is a vault-side concept. The check runs over repo state,
  not vault state.

## Behavior

### Happy path

1. Resolve the set of starter recipes from
   `starters.regenerate.RECIPE_TARGETS`, filtered to recipes whose
   parent directory is `starters/` (i.e. not the conflict-pending
   worked example). At v1 this set is `{family, work-os}`.
1. For each recipe:
   1. Load `recipes/<name>.yaml` via the existing `recipes` loader.
   1. Walk the recipe's `primitives:` list transitively through
      each primitive's `requires:` to get the resolved closure
      (`recipes.resolve_recipe_primitives`; the check imports it
      rather than re-implementing).
   1. Partition the closure by `PrimitiveKind`:
      - **Content-types** and **ontologies** → scored.
      - **Operations**, **agents**, **infrastructure**, **core** →
        skipped (see §Non-goals for the rationale per kind).
   1. For each content-type primitive `<ct>`: scan
      `starters/_seed/<recipe>/wiki/**/*.md`. The primitive is
      *covered* iff at least one seed page parses as YAML
      frontmatter with `type: <ct>`. A page whose frontmatter is
      missing, malformed, or absent of a `type:` key contributes
      nothing toward coverage of any content-type but does not
      itself raise — frontmatter validation is a separate concern
      (`docs/specs/wiki-init-adopt/spec.md` already names the
      validator). The check uses the kit's existing frontmatter
      reader; see §Contracts.
   1. For each ontology primitive `<ont>`: the primitive is
      *covered* iff `starters/_seed/<recipe>/wiki/<ont>/` exists
      and contains at least one `.md` file. The ontology's
      rendered folder name equals the primitive name by
      convention today (every shipped ontology renders under
      `files/wiki/<ont>/`). The check assumes this convention; if
      a future ontology breaks it the check will silently
      miscount that primitive. That is acceptable here because
      enforcing the convention is a primitive-shape concern
      (better placed in the primitive validator or `wiki doctor`)
      and miscounting one primitive does not corrupt the rest of
      the report. A one-line `(templates/ontologies/<ont>/files/
      wiki/<ont>/).is_dir()` sanity check at run-start is welcome
      but not load-bearing.
1. Print the report and exit per §Outputs.

### Edge cases

- **A recipe ships a content-type the seed deliberately should not
  demonstrate.** Today there is no such case (every shipped content-
  type in `family.yaml` and `work-os.yaml` is seed-covered). If a
  future recipe ships, say, `customer-feedback` in a starter where
  a seed example of customer-feedback would be inappropriate (legal,
  privacy, taste), the check has no carve-out at v1 and will report
  it as uncovered. The maintainer either authors a seed page or
  files an RFC to add an exclusion mechanism (a per-recipe
  `.starter-coverage-ignore` file, listing primitive names with a
  one-line reason; deferred to a follow-up because no current
  primitive needs it — designing the carve-out without a concrete
  case would just be guessing at the shape).
- **A seed page declares `type: <X>` where `<X>` is not in any
  installed content-type primitive.** The check ignores the page for
  coverage purposes (it cannot cover any installed primitive) and
  does **not** raise — a seed page with a typo'd `type:` is a
  separate quality problem, and `regenerate.py --check` would catch
  any rendering consequences. The check does not own frontmatter
  validity.
- **A seed page has no frontmatter at all.** Ignored for coverage,
  no raise. The page contributes to the starter's content but not
  to coverage scoring.
- **An ontology primitive ships an empty `wiki/<ont>/` directory in
  its rendered output** (today every ontology ships a `README.md`).
  The check measures the *seed* folder, not the rendered folder;
  the rendered README is produced by the kit on every `--apply` and
  is therefore tautologically present. Coverage requires a *seed*
  page under `wiki/<ont>/` — i.e. a real hand-authored example of
  the ontology's intended content, not just the kit's README.
- **A content-type primitive's name does not equal any seed folder
  name** (e.g. `recipe` → `food/sourdough-bread.md`). Folder
  placement is irrelevant to content-type coverage; only the
  frontmatter `type:` value matters. The folder convention is
  ontology-shaped, not content-type-shaped — content-types live
  inside ontology folders (`food/sheet-pan-fajitas.md` has
  `type: recipe`).
- **A seed page declares `type: <X>` where `<X>` is the singular
  of an ontology folder but no `<X>` content-type primitive is
  installed.** The live `vendor`/`vendors` shape on `main`
  illustrates this: `starters/_seed/family/wiki/vendors/anna-
  piano-studio.md` carries `type: vendor`, but the `family`
  recipe's closure installs the `vendors` ontology (folder) and
  no `vendor` content-type. The check silently ignores the page
  for coverage (no installed content-type matches `vendor`) and
  scores the `vendors` ontology as covered (the folder is non-
  empty). This is the correct outcome — the page contributes to
  the *ontology*'s population, not to any content-type — but
  it's worth showing the live case because a reader will hit it
  on day one.
- **Two recipes share a primitive and one is covered while the
  other isn't.** Coverage is computed per-recipe, so the uncovered
  one reports an uncovered primitive even though the other recipe's
  seed exercises it. This is intentional — a starter user only
  sees their starter's seed pages.
- **The recipe loader raises on a malformed recipe**
  (`recipes.RecipeError`, `WikiError`, `ValidationError`). The
  check exits with code 2 and the original exception's message on
  stderr. The starter coverage check is not a recipe-validity
  check; recipe validity is enforced elsewhere.
- **A primitive is in the recipe's listed `primitives:` but not in
  the catalog** (missing primitive directory under `templates/`).
  The existing `recipes` loader already raises on this; the check
  inherits that behavior and exits 2.

### Error cases

- Internal errors (catalog won't parse, recipe file missing, ontology
  folder convention violated): `WikiError`-shaped raise, exit code 2,
  no partial report.
- Missing or empty `starters/_seed/<recipe>/wiki/` directory: the
  check reports every content-type and ontology in the closure as
  uncovered (one block per recipe), exit code 1. This is the
  expected behavior on a hypothetical brand-new starter before any
  seed pages are authored.
- A `RECIPE_TARGETS` entry whose committed starter directory under
  `starters/<recipe>/` does not exist: skipped with a note to stderr
  (`recipe <name> in RECIPE_TARGETS but starters/<name>/ absent —
  skipping`) and not counted toward findings. This avoids a
  spurious failure on a checkout where a starter was deleted but
  `RECIPE_TARGETS` wasn't updated in the same commit.

## Invariants

- **Read-only.** The check never writes a file, never creates a
  directory, never touches the journal or the kit's installed
  state. Reruns are idempotent and produce byte-equal output for
  identical repo state.
- **Library-boundary clean.** The check imports from
  `llm_wiki_kit` (for `discover_primitives`, `load_primitive`, the
  recipe loader) but does **not** add anything *to*
  `llm_wiki_kit`. There is no new module under `llm_wiki_kit/`,
  no new CLI verb, no new public function. The wheel surface is
  unchanged.
- **No LLM call, no agent inference.** Coverage is decided by
  literal frontmatter parsing and literal directory listings.
  Nothing in this check is probabilistic.
- **No new runtime dependency.** The check uses only stdlib +
  `pyyaml` (already imported by `starters/regenerate.py`) +
  `llm_wiki_kit` (already imported by `starters/regenerate.py`).
- **No new top-level directory.** The check ships as a single
  Python file under the existing `starters/` directory (added in
  RFC-0006).
- **Exit-code contract is stable.** `0` clean, `1` findings, `2`
  internal error. Matches `wiki doctor` so a CI workflow can use
  the same exit-code partitioning.

## Contracts with other modules

- **`llm_wiki_kit.primitives`** — the check imports
  `discover_primitives`, `load_primitive`, `PrimitiveKind`. These
  are already part of the catalog-load surface used by
  `starters/regenerate.py` via `cli`. No change to the importer's
  surface.
- **`llm_wiki_kit.recipes`** — the check imports the recipe-loading
  helper (`recipes.load_recipe`) and the closure walker
  (`recipes.resolve_recipe_primitives`). The implementer reuses the
  existing closure walker rather than open-coding a parallel one —
  the closure algorithm has tests and edge cases (cycles, missing
  requires) that should not be re-derived. If either name moves
  between this spec landing and implementation, the spec is
  updated in the same PR as the rename.
- **`starters/regenerate.py`** — the check reads `RECIPE_TARGETS`
  to know which recipes map to starters and where each starter's
  seed directory lives. The two scripts share the constant but do
  **not** share execution: the check does not invoke
  `regenerate.py`, and `regenerate.py --check` does not invoke
  the coverage check. They are independently runnable.
- **Frontmatter reader** — the check parses YAML frontmatter from
  a markdown file (`---\n...\n---\n` block at the head of the
  file). Contract: malformed frontmatter is treated as "no `type:`
  declared"; the reader never raises on a seed page. The
  *implementation choice* between reusing an existing kit helper
  and inlining a small PyYAML reader is plan.md territory and is
  out of scope for this spec.
- **CI** — the check's contract is the exit code in §Outputs. How
  CI consumes that exit code (gating step vs. annotation-only
  step) is the implementation PR's call. See §"How CI surfaces
  this" below.

### How CI surfaces this

The check's *contract* is the exit code described in §Outputs. CI
*policy* — whether to gate merges on a finding, annotate the PR,
or both — is decided by the workflow file the implementation PR
authors, not by this spec.

For context: `starters/regenerate.py --check` runs today through
the pytest integration test
`tests/integration/test_starters_regenerable.py::
test_regenerate_check_mode_clean`, not as a dedicated workflow
step. The implementation PR for this spec is free to mirror that
pattern (a pytest integration test that asserts `check_coverage(
repo_root) == []`) or add a dedicated step in
`.github/workflows/ci.yml`. The trade between the two is:

- **Pytest-shaped (mirrors `regenerate.py --check` today).**
  Blocking by default — a finding fails the test, which fails CI,
  which blocks merge. Pulls every primitive-catalog-touching PR
  into authoring a seed page; appropriate if the project decides
  starter coverage is a correctness gate.
- **Dedicated CLI step with annotations + `continue-on-error:
  true`.** Non-blocking by construction. Findings surface as
  GitHub Actions `::warning::` annotations on the PR diff so the
  maintainer sees them without reading the workflow log; the
  exit-code-1 signal still works for local runs and any other CI
  surface that wants to gate on it. Appropriate if the project
  treats starter coverage as a maintenance reminder.

The implementation PR picks one and defends the pick in its PR
description. Either choice keeps the check's contract honest:
exit 0 means clean, exit 1 means findings. What policy treats the
exit code as is downstream of the contract, not part of it.

### What the maintainer does when the check fires

1. Reads the report. Each finding names a recipe, a primitive, the
   kind, and a suggested seed-page path.
1. For a content-type finding (`X uncovered — author a page with
   type: X under starters/_seed/<recipe>/wiki/<some-folder>/`):
   create the seed page under the appropriate ontology folder, set
   `type: X` in frontmatter, fill in plausible example content.
1. For an ontology finding (`Y uncovered — author at least one
   .md file under starters/_seed/<recipe>/wiki/<Y>/`): create the
   directory and one seed page.
1. Run `python starters/regenerate.py --apply` to materialize the
   new seed into the committed starter.
1. Run `python starters/check_coverage.py` to confirm clean.
1. Commit the seed page(s), the regenerated starter, in one PR.

The check does **not** automate steps 2-3 (authoring) by design —
authored seed content is editorial, not mechanical. The check's job
is to make a missing demo visible the moment it goes missing, not to
hallucinate one.

### Honesty about false positives and false negatives

Named explicitly so a reviewer can decide whether the v1 cost is
worth the v1 signal.

**False positives** (the check reports a primitive uncovered when
the seed pages legitimately should not demo it):

- **A content-type the recipe ships but the maintainer
  deliberately does not seed.** No current case (every content-
  type in `family.yaml` and `work-os.yaml` is seeded). Plausible
  for a future `incident-report` content-type a maintainer judges
  too sensitive to seed with a synthetic example. At v1 the
  check has no carve-out; the maintainer either authors a seed
  (the default outcome) or files an RFC to add a per-recipe
  exclusion file (a `.starter-coverage-ignore` listing primitive
  names with a one-line reason).
- **An ontology reported uncovered when its content-types are
  intentionally housed in a different folder.** Today every
  content-type's seed page lives inside the ontology folder named
  by its `requires:` (e.g. `recipe` requires `food`, and recipe
  seed pages live under `food/`). If a future seed places, say, a
  `meeting` page outside `wiki/people/` for editorial reasons,
  the `people` ontology folder may end up empty while the
  `meeting` content-type still scores covered. The check
  reports the ontology as uncovered — accurate by its own
  signal, but the maintainer may judge the ontology's *intent*
  is met. No carve-out at v1; the maintainer authors a one-line
  seed page under the ontology folder (a `README.md` already
  ships there from the renderer, but it does not satisfy
  coverage because the check measures *seed* contents — see
  §"Edge cases").

**False negatives** (the check passes a primitive that is, in
spirit, not really demoed):

- **A seed page covers a content-type via frontmatter but the
  page itself is empty or near-empty.** A user opening the page
  sees no example content. The check counts it because the
  structural signal is present.
- **A seed page covers a content-type with wildly inappropriate
  body content** (a `type: meeting` page whose body is actually
  demonstrating action-item linking, narrative cohesion etc.).
  Same — the structural signal is present.
- **A seed page declares `type: <X>` inside a fenced code block
  on a how-to-style page** (documentation pages illustrating the
  schema rather than acting as content). The frontmatter reader
  only inspects the document's leading `---\n...\n---\n` block,
  so this is *not* a false negative for the check as specified
  — but worth naming because a reader might assume the check
  also scans body text.

The check's design accepts these false negatives because the
alternative is either (a) a primitive-author-declared
`example_in_starters` field — which moves the staleness from "the
seed doesn't demo X" to "the field doesn't track which seed demos
X", and that field also drifts; (b) a coverage metric tied to
seed-page word count or some richer signal, which is a research
project rather than a maintenance reminder; (c) an LLM call to
score "does this page genuinely demonstrate the primitive," which
crosses the library boundary explicitly forbidden by Constraints.

## Acceptance criteria

These translate into tests for the implementation PR. Most ACs
exercise a fixture catalog under `tests/fixtures/starter-seed-
coverage/` rather than the live `templates/` + `recipes/` +
`starters/` trees; the fixture mirrors the kit's catalog shape but
is hand-curated so the test is reproducible across `main`
movement. AC1 is the one AC that asserts against the live tree,
and it is the spec's baseline-cleanliness statement — if a future
catalog/recipe edit lands a new content-type without a seed, AC1
turns red and the implementation PR's author fixes it before
merge. The implementation PR partitions these into unit /
integration / static-check tests in its `plan.md`.

- [ ] **AC1.** A run of the callable entry point with
      `kit_root=<repo root>` returns an empty findings list against
      the repo state at the time the implementation PR opens. This
      is the spec's baseline-clean claim, asserted live so a new
      uncovered primitive that lands between this spec's commit and
      the implementation PR cannot sneak through. The AC1 test
      binds to whatever name the callable lands with; if that name
      moves later, the spec is updated in the same PR as the
      rename.
- [ ] **AC2.** Against a fixture catalog where the `recipe`
      content-type primitive is installed but no seed page carries
      `type: recipe`, the check exits 1 with exactly one finding
      naming `recipe`. Adding one seed page with `type: recipe`
      frontmatter to the fixture seed tree makes the check pass.
- [ ] **AC3.** Against a fixture where the `people` ontology is
      installed but `starters/_seed/<recipe>/wiki/people/` is
      absent, the check reports the `people` ontology as uncovered.
      Report ordering is stable: recipes outer-sorted
      alphabetically, primitives inner-sorted alphabetically;
      reruns produce byte-identical stdout.
- [ ] **AC4.** Against a fixture catalog that installs a content-
      type primitive whose name does not appear in any seed page's
      `type:` frontmatter, the check exits 1 with one finding for
      that primitive. Adding a seed page anywhere under the
      fixture's seed tree with the matching `type:` value makes
      the check pass. The fixture is assembled under `tmp_path`
      (the AC's "add a primitive, add a seed page" mutations are
      procedural, not curated, so an ephemeral tree is the right
      shape). The test must not mutate the real `templates/` or
      `recipes/` directories.
- [ ] **AC5.** A seed page with malformed YAML frontmatter
      (unterminated `---`, invalid YAML) does not crash the check;
      it is silently ignored for coverage purposes and contributes
      nothing toward any primitive. Asserted against a fixture
      with a deliberately malformed page.
- [ ] **AC6.** Operation, agent, and infrastructure primitives
      installed in a fixture recipe never appear in the findings
      list, even when no seed page references them. Asserted by
      pinning the expected findings list against a fixture
      catalog that includes an unseeded `weekly-digest` operation
      and an unseeded `household-manager` agent.
- [ ] **AC7.** The check writes nothing to disk: file count and
      mtime fingerprint of the fixture catalog directory are
      unchanged before and after a run. Spot-checks the read-only
      invariant.
- [ ] **AC8.** Asserted by a static check (AST scan) that the
      file `starters/check_coverage.py`:
      (a) does not import `llm_wiki_kit.write_helper`,
      `llm_wiki_kit.journal`, or anything matching
      `llm_wiki_kit.*safe_write*`;
      (b) contains no `subprocess` invocation whose first argv
      element is `wiki`;
      (c) contains no `cli.main([...])` call whose first list
      element is in the disallowed-verb set `{"init", "add",
      "adopt", "ingest", "run", "doctor", "upgrade", "resolve",
      "schedule"}` — every verb in that set implies a user vault
      the check does not own (whether the verb mutates it or
      merely reads it). The check is allowed to *import* `cli`
      (the same pattern `regenerate.py` uses) so the import alone
      is not a violation; in-process invocation of a vault-bound
      subcommand is. The point is a test that fails if a future
      refactor crosses the boundary via any of these three
      vectors, not to rely on code review.
- [ ] **AC9.** Exit codes: 0 on clean, 1 on findings, 2 on
      internal error. Asserted via `subprocess.run` against
      fixture inputs: clean fixture (exit 0), fixture with a
      deletion that produces a finding (exit 1), and fixture
      where a recipe in `RECIPE_TARGETS` causes the loader to
      raise (`RecipeError` / `WikiError` / `ValidationError` —
      bind the test to "loader raises", not to a specific
      error class or to the file-absent shape, so a future
      loader change does not break the AC). The `starters/<recipe>/`
      absent case is *not* in AC9 — that is the skip-with-note
      edge case under §"Error cases" and yields exit 0, not
      exit 2.
- [ ] **AC10.** Report format is stable across runs and across OS
      (the file walk uses `sorted()` per `_iter_vault_files` in
      `regenerate.py`). Asserted by running twice in the same
      test and comparing stdout byte-for-byte.

## Non-goals

What this check explicitly does **not** do, in case anyone asks.

1. **Does not score operations, agents, or infrastructure
   primitives.** These three kinds carry no natural structural
   signal a seed page could carry. A seed page does not "demo" an
   operation — an operation is *invoked* and writes outputs; a
   convincing demonstration would be a *runtime artifact* (a
   journaled `OperationRunEvent` plus the page the operation
   produced under `outputs/`), not a hand-authored seed. The same
   holds for agents (a real demonstration is an
   `OperationRunByAgentEvent` and the artifact the agent wrote)
   and infrastructure (rendered configuration, not demoed by
   anything user-facing). The kit's renderer already produces the
   declarative *definitions* of all three into the committed
   starter (`.claude/agents/<name>/AGENT.md` for agents, SKILL.md
   stubs and CLI bindings for operations, configuration files for
   infrastructure); `regenerate.py --check` already byte-verifies
   that those definitions match what the catalog would produce.
   What's missing is *invocation* demonstration — that is a
   separate, harder problem (the starter would need to ship a
   pre-replayed journal with operation runs), is out of scope
   here, and is named so a future RFC can pick it up if needed.
   In short: this check covers the kinds where a mechanical
   structural signal exists; it does not pretend to cover the
   kinds where it doesn't.
1. **Does not score the `personal` recipe / conflict-pending
   vault.** Per RFC-0006, `personal` renders to
   `docs/guides/how-to/_examples/conflict-pending/` and is
   documentation infrastructure, not a starter. A user does not
   clone it; coverage is the wrong question to ask about it.
1. **Does not auto-fix.** The check reports; the maintainer
   authors seed pages by hand. An auto-stub mode would be an LLM
   call (to pick example content) or a template stamp (which would
   degenerate to an empty `type: X\n` frontmatter file, technically
   covering but visually useless). Either crosses the library
   boundary or is dishonest about what was demonstrated.
1. **Does not ship as a `wiki` CLI subcommand.** Starters are not
   vaults the kit owns. A `wiki starters check` verb would put
   maintainer-only tooling on the wheel surface end users
   install, which violates AGENTS.md's "Two scopes, one repo"
   rule. The check lives at `starters/check_coverage.py` for the
   same reason `starters/regenerate.py` lives there: it is repo-
   author tooling, not kit-user surface.
1. **Does not add an `example_in_starters` field to primitive.yaml.**
   The check uses *existing* mechanical signals (frontmatter `type:`
   for content-types, folder presence for ontologies) so no
   primitive.yaml schema change and no downstream-rollout PR is
   required. A future RFC may revisit this if a primitive author
   needs to declare "this content-type is intentionally unseeded"
   without using the carve-out file proposed in §Edge cases.
1. **Does not, by itself, prescribe CI gating.** The check's exit
   code is honest (0 clean, 1 findings, 2 internal error). The
   spec is deliberately silent on whether CI treats exit 1 as a
   blocker or annotates and continues — that policy is the
   implementation PR's choice. The spec keeps the contract; the
   workflow keeps the policy.
1. **Does not enforce seed-page quality** (no body text, plausible
   content, narrative consistency across pages). Editorial concerns
   are code-review concerns; this check is mechanical.
1. **Does not validate frontmatter schemas.** Whether a
   `type: meeting` page actually carries all the meeting-required
   fields is a separate concern (frontmatter schema validation,
   covered by `frontmatter.schema.yaml` and the schema-checking
   path in `wiki doctor` and `wiki init --adopt`). The check only
   asks whether a `type:` key with the expected value exists.
1. **Does not check for stale seed pages** (a content-type was
   removed but its seed pages remain). Removing a content-type
   from a recipe is rare and the leftover pages would still
   render — they just wouldn't be installed-as-content-type. A
   future ROADMAP item if it becomes a real problem.
1. **Does not propose changes to `wiki doctor`.** `wiki doctor`
   is vault-aware (it reads a journal). Starters are pre-rendered
   distributions, not vaults the user owns; the journal-replay
   model that doctor uses does not apply. The two checks are in
   different scopes by design.

## Constraints

What implementation strategies are off the table for this spec.

- **No new module under `llm_wiki_kit/`.** The check is a single
  script under `starters/`, matching the placement of
  `regenerate.py`. The `pyproject.toml` `packages = ["llm_wiki_kit"]`
  setting keeps it off the wheel surface; this constraint preserves
  that property.
- **No new public CLI verb.** `wiki starters check` is explicitly
  rejected per Non-goal 4. The check is invoked as
  `python starters/check_coverage.py`, full stop.
- **No new runtime dependency.** Per Charter Principle 3, runtime
  deps are intentionally minimal. The check uses only stdlib +
  `pyyaml` (already imported by `regenerate.py`) + the existing
  `llm_wiki_kit` import. Dev dependencies (`pytest`, `ruff`,
  `mypy`) for the tests are fine; runtime deps would require an
  ADR.
- **No bypass of the existing primitive / recipe loaders.** The
  check reuses `llm_wiki_kit.primitives.discover_primitives`,
  `load_primitive`, and the recipe closure walker. Re-implementing
  the closure walk in the check would be a second source of truth
  waiting to drift — the same anti-pattern `doctor.check_stale_lock`
  rejects for `state.held_lock`.
- **No new top-level directory.** The check ships under the
  existing `starters/` directory (added in RFC-0006). Adding a
  sibling directory (e.g. `tools/`, `scripts/`) would itself need
  an RFC per AGENTS.md.
- **No edit to `starters/regenerate.py`'s `--check` mode.** The
  byte-divergence check stays exactly as it is. Folding coverage
  into it would entangle two contracts that are honest to keep
  separate (output drift vs. input drift).
- **No use of file mtimes, git history, or last-modified
  heuristics.** Per the §Behavior pick: time-based heuristics
  (option (b) in the prompt) are explicitly rejected as too
  brittle for a check whose value depends on near-zero false
  positives. The check is purely structural.

## Why this detection mechanism (over the alternatives)

The prompt named three candidate detection mechanisms; this section
records the choice and the cost of the rejected alternatives so a
future reviewer can revisit if the situation changes. If "no
`example_in_starters` field on primitive.yaml" becomes a constraint
future RFCs need to cite (e.g. when somebody proposes adding it
later), promote this section into a dedicated ADR; until then,
keeping the rationale next to the spec it justifies is the cheaper
shape.

### Picked: structural signals on existing seed-page shape

For each content-type primitive, coverage = ∃ a seed page with
`type: <name>` in YAML frontmatter. For each ontology primitive,
coverage = ∃ a `.md` file under `starters/_seed/<recipe>/wiki/<name>/`.

- Mechanical, near-zero false positives, no schema change.
- Uses signals the seed pages already carry (`type:` is load-bearing
  for the kit's renderer and frontmatter validator — drift between
  this check and reality is structurally bounded).
- No primitive-author burden, no downstream rollout PR adding
  `example_in_starters:` to N existing primitives.
- Honest false-positive surface (see §"Honesty about false
  positives") is named in the spec rather than hidden.

### Rejected: each primitive declares `example_in_starters` (prompt option (a))

A primitive.yaml field listing seed-page paths that are expected to
demonstrate the primitive. Check verifies each listed path exists
and carries the expected frontmatter.

- **Pros:** explicit author intent; no folder-name convention dependency.
- **Cons:** requires a Pydantic model change (`Primitive` uses
  `extra="forbid"`) and a downstream rollout PR adding the field to
  every existing primitive. The field itself becomes a thing to
  forget — a primitive author who ships without the field is no
  better off than the staleness this spec exists to detect.
  Moves the drift surface from "seed doesn't demo primitive" to
  "field doesn't track which seed demos primitive". The structural
  signal already exists in the seed pages and is itself load-bearing
  for the renderer — using it is cheaper than adding a parallel
  signal.

### Rejected: time-since-last-touch heuristic (prompt option (b))

Compare mtime of `starters/_seed/<recipe>/` against mtime of each
primitive's directory; flag if the primitive is newer.

- **Pros:** zero schema change, zero seed-shape dependency.
- **Cons:** brittle in both directions. A seed page touched for a
  typo fix has a fresh mtime but still doesn't demo a new primitive;
  a primitive touched only to fix a `description:` typo has a fresh
  mtime but didn't need a seed update. False positives and false
  negatives both rampant. mtime is the wrong tool for "does X
  demonstrate Y."

### Rejected: % coverage metric with threshold (prompt option (c))

Score each starter's seed pages against the recipe's full primitive
closure; flag if < N% covered.

- **Pros:** scales to a richer notion of coverage (depth, variety).
- **Cons:** threshold-tuning is judgmental, not mechanical. A
  threshold of 80% would flag a starter at 79% (and the maintainer
  argues with CI about whether 1 missing primitive matters);
  100% threshold collapses to the picked approach. The richer
  signal the threshold would unlock (e.g. "how thoroughly is the
  primitive demonstrated") is exactly the editorial concern this
  spec already declares out of scope. The picked approach is
  effectively coverage at 100% with a binary signal per primitive,
  which is the same outcome without the threshold knob.

## What "the maintainer will notice" already catches

A legitimate adversarial concern: maintainer review, today, already
notices when a primitive ships without a starter demo. This spec
trades non-zero implementation cost for *not* relying on that
noticing. The trade is justified by:

- Maintainer attention is a scarce, fallible resource; a mechanical
  reminder is a free check that compounds over time.
- The kit's audience (per RFC-0005) explicitly relies on starters
  being usable distributions, not preview artifacts. A starter
  with a missing demo page is a regression the maintainer paid the
  cost of writing the primitive for but no Tier 2 user benefits
  from.
- The cost is bounded: a single Python script, no schema change,
  no CLI verb, no wheel-surface impact, no test-suite slowdown
  (the check runs once in CI and once on demand).

If a future reviewer concludes the maintainer-noticing baseline is
sufficient and the check is overhead, the spec is cheap to
deprecate — delete the script, drop the CI job, mark this spec
`Deprecated`. The infrastructure footprint is intentionally small
so the reversal is cheap.
