# Plan: starter-seed-coverage

> **Implementation plan paired with `spec.md`.** The spec says *what*;
> this plan says *how, in what order, with what verification*.

- **Status:** Done
- **Spec:** `docs/specs/starter-seed-coverage/spec.md`
- **Owner:** the implementer for this PR; long-term ownership is the
  maintainer per the spec's §Owner clause.

## Approach

Ship a single Python script `starters/check_coverage.py` next to the
existing `regenerate.py`, plus three test files covering the spec's 10
ACs. The script's shape mirrors `regenerate.py`: free functions, a
single `main(argv)` entry point, the same `sys.path.insert(REPO_ROOT)`
trick to import the kit. **`from starters import regenerate` is
imported lazily inside the one helper that needs `RECIPE_TARGETS`** —
not at module-top — so the script's import surface stays honest (the
top-of-file import list says "this script depends on these modules"
in a way the AC8 AST scan can verify), and `regenerate.safe_write` is
never reachable as a module-level alias inside `check_coverage.py`.
No new abstractions — no `Checker` class, no plugin layer, no per-kind
dispatch table beyond an `if`/`elif`.

The script exposes a callable `check_coverage(kit_root: Path) ->
list[Finding]` that the tests drive directly without going through
`subprocess`. This is the primary testability seam.

`main()` takes an optional keyword-only `kit_root: Path | None`
parameter; when `None`, it falls back to the module-level `REPO_ROOT`
computed from `__file__`. This is the secondary testability seam,
matching the callable's shape — a parameter, not a flag (it is not in
`argv`, not in `--help`, not user-facing). It exists to satisfy AC9
without introducing a CLI flag (which the spec explicitly rejects in
§Non-goals 4) or an env var (which would be a second, parallel test
seam — and the reviewer-flagged trap that test-only env vars become
de-facto contracts over time).

**AC9 interpretation.** The spec AC9 says "Asserted via
`subprocess.run` against fixture inputs." The script's CLI wrapper is
`raise SystemExit(main(...))`, which makes `main()`'s integer return
*equal to* the process exit code. Asserting `main([], kit_root=fixture)
== 1` exercises the same contract as `subprocess.run([sys.executable,
"starters/check_coverage.py"]).returncode == 1` would, without
introducing the env-var seam. The in-process test is cheaper and pins
the same property. This plan resolves AC9 via in-process `main()`
calls; if a future reviewer judges the deviation unacceptable, swap
in a small `subprocess.run` wrapper *plus* a `python -c` shim that
monkeypatches `REPO_ROOT` before calling `main()` — no script change
required.

**CI integration: pytest-shape.** The integration test
`tests/integration/test_starter_seed_coverage.py::
test_starter_seed_coverage_clean` asserts `check_coverage(REPO_ROOT)
== []`. A finding fails the test, which fails CI, which blocks merge.
Defense:

1. **Mirrors the existing pattern.** `test_regenerate_check_mode_clean`
   already covers `regenerate.py --check` in the same shape; using the
   same shape keeps the starter-machinery tests cohesive and avoids
   inventing a new "starter health" CI surface.
2. **We treat starter staleness as a correctness bug.** RFC-0006
   elevated starters from "preview artifacts" to "Tier 2 distribution
   surface"; a starter user cloning `starters/family/` is the
   audience RFC-0005 explicitly committed the kit to serving via the
   starter path. The spec §"How CI surfaces this" names pytest-shape
   as the right pick "if the project decides starter coverage is a
   correctness gate" — this plan asserts that decision. The
   alternative (treat staleness as a maintenance reminder) is named
   in §Out-of-scope as the escape hatch for a future demotion PR if
   blocking turns out to be too sharp in practice.
3. **Mechanically simplest.** No `.github/workflows/ci.yml` edit; the
   existing pytest job picks up the new test file automatically.
4. **Cost the spec acknowledged.** "Every primitive-catalog-touching
   PR also authors a seed page" is the cost. The spec named it; the
   plan accepts it. Demotion path: change the test to print warnings
   to stdout and `pytest.skip()` instead of `assert` — small workflow
   edit, not a redesign.

### What I considered and declined

- **Tempted to add a `--kit-root` flag for testability.** Declining —
  the callable entry point covers the in-process tests and `main()`'s
  keyword-only `kit_root` parameter covers the exit-code tests; the
  spec's "no flags at v1" is a load-bearing constraint that even an
  internal/hidden flag would erode.
- **Tempted to add a `WIKI_STARTER_KIT_ROOT` env var as a subprocess
  test seam.** Declining — an env-var test seam categorized as
  test-only is the kind of "invisible second contract" that grows
  into a de-facto user-facing knob over time. The `main(kit_root=…)`
  kwarg seam plus the in-process AC9 interpretation above avoids the
  env var entirely.
- **Tempted to add a `Finding` Pydantic model.** Declining — ADR-0005
  reserves Pydantic for disk-bound types. The `Finding` dataclass
  never crosses disk; a frozen dataclass with `order=True` is the
  right shape, matching `Issue` in `llm_wiki_kit/doctor.py`.
- **Tempted to extract a `_starters_common.py` helper module to share
  `RECIPE_TARGETS` cleanly between `regenerate.py` and
  `check_coverage.py`.** Declining — the spec says "share the constant"
  by direct import (`from starters import regenerate`), the import is
  side-effect-free (regenerate.py defines constants and helpers but
  does no I/O at import time), and a shared module would itself be a
  new file with its own boundary. Refactor once a third caller appears.
- **Tempted to add `--strict` and `--recipe <name>` flags.** Declining
  — explicitly rejected in spec §Non-goals.
- **Tempted to refactor `regenerate.py`'s `RECIPE_TARGETS` into a
  computed-from-`kit_root` shape so the check can reuse paths
  directly.** Declining — that's a behavior-changing edit to a shipped
  script outside this spec's scope. Instead, the check pulls
  *recipe names* from `RECIPE_TARGETS` (filtered to those whose parent
  basename is `"starters"`, which excludes the `personal` /
  conflict-pending entry) and computes paths anchored at `kit_root`.
  The basename lookup (`RECIPE_TARGETS[recipe][0]`) is used to map
  recipe name → committed-dir name; for the two starters today, that
  basename equals the recipe name.
- **Tempted to add a coverage helper to `wiki doctor`.** Declining —
  explicitly rejected in spec §Non-goals (doctor is vault-aware;
  starters aren't vaults).

## Pre-conditions

- `docs/specs/starter-seed-coverage/spec.md` is committed at its
  current shape. (PR #116; this implementation PR may land stacked on
  the spec PR until that PR merges to main.)
- `starters/regenerate.py` defines `RECIPE_TARGETS`,
  `STARTERS_DIR`, and the lazy-import idiom that
  `tests/integration/test_starters_regenerable.py::_import_regenerate`
  also uses.
- `llm_wiki_kit.recipes.resolve_recipe_primitives` is the canonical
  closure walker (verified at `llm_wiki_kit/recipes.py:127`).
- `llm_wiki_kit.primitives.discover_primitives` walks
  `templates/<kind>/<name>/primitive.yaml` and returns
  `list[Primitive]`; `load_primitive` loads a single one (for
  `core/primitive.yaml`).
- No new runtime dep: the check uses `yaml` (already in
  `pyproject.toml` as `pyyaml>=6`) and stdlib only.

## Steps

Each step is one verifiable goal. Tests drive each step in
red-green-refactor (TDD mode for steps 2–6; goal-based for steps 1, 8;
manual gate-run for step 7).

### 1. `check_coverage.py` skeleton imports and runs (returning exit 2)

Create `starters/check_coverage.py` with:

- Module docstring linking the spec.
- `REPO_ROOT` + `sys.path.insert` shim.
- Top-level imports: `argparse`, `os`, `sys`, `dataclasses`,
  `pathlib`, `yaml` (already a runtime dep);
  `llm_wiki_kit.errors.RecipeError`, `WikiError`, `ValidationError`;
  `llm_wiki_kit.primitives` (`Primitive`, `PrimitiveKind`,
  `discover_primitives`, `load_primitive`);
  `llm_wiki_kit.recipes` (`load_recipe`, `resolve_recipe_primitives`).
  **No top-level `from starters import regenerate`** — that import
  is lazy, inside the one helper that needs `RECIPE_TARGETS`. The
  script does not import `ast`; AC8's AST scan lives in the test
  module.
- The frozen `Finding` dataclass (`recipe`, `primitive`, `kind`,
  `hint`; `order=True` so sorting is mechanical).
- A `main()` stub that prints `"starter-seed-coverage: not yet
  implemented\n"` to stderr and returns **2** (the spec's
  internal-error code). This is the deliberate transient state for
  the duration of steps 1–4 — any premature invocation surfaces as
  a non-zero exit with an explanatory message rather than a silent
  false-clean. Step 5 replaces the stub with the real main.

**Verification (goal-based):** `python starters/check_coverage.py`
exits 2 with `"not yet implemented"` on stderr;
`python -c "from starters import check_coverage"` imports clean.

### 2. Frontmatter `type:` reader handles every malformed shape gracefully (AC5)

Add `_read_frontmatter_type(path: Path) -> str | None`. Returns `None`
on every shape that isn't "valid `---`-delimited YAML mapping with a
string `type:` key" — file unreadable, no `---\n` opener,
unterminated frontmatter, invalid YAML, non-mapping top level,
missing `type:`, non-string `type:`. Never raises.

**Verification (TDD):** `tests/unit/test_starter_seed_coverage.py::
test_frontmatter_reader_handles_*` — one test per malformed shape:

- `test_frontmatter_reader_unterminated_returns_none`
- `test_frontmatter_reader_invalid_yaml_returns_none`
- `test_frontmatter_reader_no_type_key_returns_none`
- `test_frontmatter_reader_non_string_type_returns_none`
- `test_frontmatter_reader_no_frontmatter_block_returns_none`
- `test_frontmatter_reader_happy_path_returns_type` (sanity)

These tests are the AC5 contract: malformed pages contribute nothing
to coverage and never crash the check.

### 3. Content-type and ontology scoring against a fixture catalog (AC2, AC4, AC6)

Implement `check_coverage(kit_root: Path) -> list[Finding]` with:

- `_load_recipe_targets() -> dict[str, tuple[str, Path]]`: lazy
  import — inside this function only, `from starters import
  regenerate; return regenerate.RECIPE_TARGETS`. Single point of
  contact with `regenerate.py`.
- `_starter_recipe_names() -> list[str]`: returns `sorted(name for
  name, (_, parent) in _load_recipe_targets().items() if parent.name
  == "starters")` — the names of recipes that map to `starters/`,
  not to `docs/.../_examples/`.
- `_committed_starter_path(kit_root, recipe)`: returns `kit_root /
  "starters" / _load_recipe_targets()[recipe][0]`. Used for the
  "missing committed starter → skip with note" edge case.
- `_seed_dir(kit_root, recipe)`: returns
  `kit_root / "starters" / "_seed" / recipe`.
- `_load_catalog(kit_root)`: union of `discover_primitives(kit_root /
  "templates")` and `load_primitive(kit_root / "core")` (when the
  core primitive exists).
- Main loop in `check_coverage`:
  ```
  catalog = _load_catalog(kit_root)
  findings: list[Finding] = []
  for recipe_name in _starter_recipe_names():
      committed = _committed_starter_path(kit_root, recipe_name)
      if not committed.is_dir():
          # Skip-with-note edge case (spec §"Error cases" 3).
          sys.stderr.write(
              f"recipe {recipe_name} in RECIPE_TARGETS but {committed} "
              "absent — skipping\n"
          )
          continue
      recipe_path = kit_root / "recipes" / f"{recipe_name}.yaml"
      recipe_obj = load_recipe(recipe_path)            # Recipe object
      closure = resolve_recipe_primitives(recipe_obj, catalog)  # list[Primitive]
      seed_dir = _seed_dir(kit_root, recipe_name)
      type_index: set[str] = (
          {t for p in sorted(seed_dir.rglob("*.md"))
           if (t := _read_frontmatter_type(p)) is not None}
          if seed_dir.is_dir() else set()
      )
      for primitive in closure:
          if primitive.kind is PrimitiveKind.CONTENT_TYPE:
              if primitive.name not in type_index:
                  findings.append(Finding(...))
          elif primitive.kind is PrimitiveKind.ONTOLOGY:
              ontology_dir = seed_dir / "wiki" / primitive.name
              if not ontology_dir.is_dir() or not any(ontology_dir.rglob("*.md")):
                  findings.append(Finding(...))
          # else: skip OPERATION, AGENT, INFRASTRUCTURE
  return sorted(findings)  # dataclass(order=True) handles tiebreak
  ```
  Use `is` for `PrimitiveKind` membership comparison (matching kit
  convention at `primitives.py:403`, `:468`, `:588`), not `==`.
  The pseudocode above pins three load-bearing variable-naming
  distinctions for the implementer: `recipe_name: str` (from
  RECIPE_TARGETS keys), `recipe_obj: Recipe` (Pydantic model from
  `load_recipe`), and `primitive: Primitive` (from the closure
  walker). `resolve_recipe_primitives` takes the **Recipe object**,
  not the name — pinned here because the spec wrapper text could be
  read either way.

**Verification (TDD):**

- `test_content_type_uncovered_emits_finding` — fixture catalog
  installs a content-type whose name appears in no seed page's
  frontmatter; assert `len(findings) == 1` and the finding's kind is
  `"content-type"`. (Spec AC2 / AC4 shape.)
- `test_content_type_covered_emits_no_finding` — same fixture but
  with one seed page carrying matching `type:`; assert
  `findings == []`. (Inverse of AC2.)
- `test_ontology_folder_missing_emits_finding` — fixture installs an
  ontology whose seed folder doesn't exist; assert finding's kind is
  `"ontology"`. (Spec AC3 shape.)
- `test_ontology_folder_empty_emits_finding` — folder exists, no
  `.md` inside; assert finding emitted. (Spec edge-case.)
- `test_ontology_folder_with_md_emits_no_finding` — folder has one
  `.md`; assert `findings == []`. (Inverse of AC3.)
- `test_skipped_kinds_never_in_findings` — fixture installs an
  operation, an agent, and an infrastructure primitive with no
  matching seed; assert none appear in findings. (Spec AC6.)

The fixture builder is committed to **a module-local function
inside `tests/unit/test_starter_seed_coverage.py`** with this
signature:

```python
def _build_fixture_kit(
    tmp_path: Path,
    *,
    recipe_primitives: list[dict],
    seed_pages: list[tuple[str, str]],
    recipe_yaml_override: str | None = None,
    omit_starter_dir: bool = False,
) -> Path: ...
```

The two optional kwargs cover edge-case fixtures the simpler
"valid recipe + valid seed" signature can't express:

- `recipe_yaml_override` — when set, the builder writes this raw
  string as `recipes/<name>.yaml` instead of synthesizing a Recipe
  YAML from `recipe_primitives`. Used by AC9's loader-raise
  fixture (`recipe_yaml_override="primitives: not-a-list"` or a
  truncated `"{"`).
- `omit_starter_dir` — when `True`, the builder skips creating
  `<tmp>/starters/<name>/`. Used by step 4's
  `test_missing_committed_starter_dir_skips_with_note`.

Shared by every AC2–AC6 + AC9 + AC10 test in that module. (The
integration tests in `tests/integration/` do not need the fixture
builder — they run against the live tree.) `recipe_primitives` is
a list of `{name, kind, requires}` dicts the builder converts to
`primitive.yaml` files under `templates/<kind>/<name>/`;
`seed_pages` is a list of `(relative-path-under-wiki, content)`
tuples. The builder writes:

- `<tmp>/recipes/<name>.yaml` — minimal Recipe YAML using one of the
  real starter names (`family` or `work-os`) so RECIPE_TARGETS'
  starter-name filter accepts it.
- `<tmp>/core/primitive.yaml` — minimal core primitive (kind:
  `infrastructure`, requires: []).
- `<tmp>/templates/<kind>/<name>/primitive.yaml` — minimal primitive
  manifests for whatever the test needs to install.
- `<tmp>/starters/<name>/` — empty directory (so the "missing
  committed starter" skip-with-note doesn't fire).
- `<tmp>/starters/_seed/<name>/wiki/...` — seed pages as the test
  requires.

### 4. Empty/missing seed dir reports every scored primitive (edge case)

The spec's §Edge cases names: "Missing or empty
`starters/_seed/<recipe>/wiki/` directory: the check reports every
content-type and ontology in the closure as uncovered."

**Verification (TDD):**

- `test_missing_seed_dir_reports_every_scored_primitive` — fixture
  has the recipe with N content-types + M ontologies in closure,
  no `_seed/<recipe>/` directory at all; assert
  `len(findings) == N + M` and each is correctly classified.
- `test_missing_committed_starter_dir_skips_with_note` — fixture
  has a recipe but no `<tmp>/starters/<name>/` directory; assert
  `findings == []` and an explanatory note went to `sys.stderr`
  via `capsys.readouterr().err`.

### 5. Report rendering, exit codes, `main(kit_root)`, determinism (AC9, AC10)

The shipped split (replacing the original `render_report(findings,
kit_root)` shape this plan first sketched) is **one** walk that
yields findings *and* counts:

- `_walk_coverage(kit_root) -> tuple[list[Finding], int, int]`:
  internal helper. Walks the catalog and recipes once; returns
  `(findings, scored_count, starter_count)`. This is the only place
  coverage logic lives.
- `check_coverage(kit_root) -> list[Finding]`: thin back-compat
  wrapper over `_walk_coverage` for callers that only need findings.
- `render_report(findings, scored, starters) -> str`: **pure**
  function — no I/O. Takes the counts so the summary line and the
  findings list cannot disagree, and an exception raised by
  rendering can never escape `main()`'s `try/except WikiError`.

`main` calls `_walk_coverage` directly under `try/except WikiError`,
then `render_report` on the resulting tuple. Tests that need the
rendering path call `_walk_coverage` and pass the tuple's counts
into `render_report` — see the AC1 integration test for the
canonical shape.

- Clean: `"coverage clean — {N} primitive(s) across {M} starter(s)
  covered\n"`. `N` is total of CONTENT_TYPE + ONTOLOGY across all
  scored starters; `M` is the number of starters.
- With findings: per-recipe block `"=== <recipe> ===\n  <kind>:
  <name> uncovered — <hint>\n..."`. Recipes sorted alphabetically;
  findings within sorted by primitive name.
- `main(argv: list[str] | None = None, *, kit_root: Path | None =
  None) -> int`: when `kit_root` is `None`, falls back to module-
  level `REPO_ROOT`. The kwarg is the test seam (see §Approach
  AC9 interpretation); it is not a CLI flag.
- Exit 0 on no findings; exit 1 on findings; exit 2 on `WikiError`-
  shaped raise (`main` wraps `check_coverage` in `try/except
  WikiError`, writes the error to stderr, returns 2). Other
  exceptions propagate to surface as a real traceback.

**Verification (TDD):**

- `test_clean_run_prints_single_line_summary` — fixture catalog
  fully covered; assert stdout matches the single-line shape and
  `main([], kit_root=fixture)` returns 0.
- `test_findings_render_grouped_by_recipe_alphabetically` — fixture
  with multiple uncovered primitives across two recipes; assert
  report text matches expected per-recipe grouping.
- `test_determinism_same_input_byte_equal_output` — run the callable
  twice over the same fixture; assert
  `render_report(...) == render_report(...)`. (Spec AC10.)
- `test_main_exit_codes` — three `main([], kit_root=…)` invocations
  against fixture trees:
  - clean fixture → returns 0
  - fixture with one finding → returns 1
  - fixture where `load_recipe` raises → returns 2. The
    loader-raise fixture writes `recipes/family.yaml` as
    structurally malformed YAML — e.g. `primitives: not-a-list`
    (the Recipe model requires `primitives: list[str]`) or
    `{` (truncated mapping). The test asserts only the integer
    return value, **not** the specific error class — per spec
    AC9's "bind to loader-raises, not to a specific error class
    or to the file-absent shape." The script's CLI wrapper
    `raise SystemExit(main(...))` makes `main()`'s integer return
    equal to the process exit code, satisfying AC9's "via
    subprocess.run" language without introducing an env-var seam.
  (Spec AC9.)

### 6. Read-only invariant spot-checked against the live tree (AC7)

Add `tests/integration/test_starter_seed_coverage.py`. Tests:

- `test_starter_seed_coverage_clean_against_live_tree` — calls
  `check_coverage(REPO_ROOT)` and asserts `[]`. (Spec AC1 — the
  baseline-clean claim.) The contract this test pins is "the live
  repo's coverage is clean"; the test mechanism (pytest assertion
  vs. a goal-based CI step running `python starters/check_coverage.py`
  and checking exit 0) is interchangeable. If a future PR demotes
  this to a workflow-level goal-based check, that is a workflow
  swap, not a test-suite excision — the contract is the same.
- `test_check_is_read_only` — snapshot file count + mtime fingerprint
  of `starters/`, `recipes/`, `templates/`, `core/` before and after
  a call; assert identical. (Spec AC7.)

The first test is the load-bearing CI gate. It runs in
`pytest -m 'not slow'`, so it executes on every PR. The fixture-
driven exit-code tests for AC9 stay in
`tests/unit/test_starter_seed_coverage.py` per step 5 — they need
the same `_build_fixture_kit` helper as AC2–AC6.

### 7. AC8 static AST scan asserts the library boundary

Add `tests/unit/test_starter_seed_coverage_boundary.py` with one
test: `test_check_coverage_respects_library_boundary`. The test:

1. Parses `starters/check_coverage.py` with `ast.parse`.
2. Walks the AST once to build an **import alias table**: a
   `dict[str, str]` mapping every locally-bound name to its source
   module (e.g. `subprocess`, `llm_wiki_kit.cli`). Both
   `import X` and `from M import N as A` populate the table; star
   imports (`from M import *`) populate a separate "star-source"
   set the test asserts is empty (no star imports allowed in this
   file). The star-import assertion fails with
   `"check_coverage.py uses 'from X import *'; AC8 requires explicit
   imports"` so the diagnostic stays uniform with (a)/(b)/(c).
3. Walks the AST a second time and asserts:
   - **(a)** No `Import` / `ImportFrom` node whose dotted source
     module contains `"write_helper"`, `"journal"`, or matches
     `"*safe_write*"`. Import-level only (not name references) —
     a `"journal"` string in a docstring is fine; an `import
     journal` is not. This file-local scan is **intentionally
     narrow**: it does not chase transitive imports (e.g.
     `regenerate.safe_write` reachable via `from starters import
     regenerate` is not a violation at this layer, both because
     §Approach commits to lazy-importing `regenerate` inside one
     helper and because the boundary the spec protects is
     "what this script *uses*", not "what it could reach by
     attribute access."
   - **(b)** No `Call` node where the function resolves (via the
     alias table) to anything in the `subprocess` module **and**
     whose first positional argument is a list literal starting
     with `"wiki"` (or a bare string literal `"wiki"` in the same
     position). Catches `subprocess.run(["wiki", …])`,
     `subprocess.Popen(["wiki", …])`, and aliased forms
     (`from subprocess import run as r; r(["wiki", …])`).
   - **(c)** No `Call` node where the function resolves to
     `cli.main` (the `cli` name in the alias table bound to
     `llm_wiki_kit.cli`, attribute access `main`) **or** any
     re-aliased equivalent (e.g. `from llm_wiki_kit import cli as
     c; c.main([…])`), with first positional argument a list
     literal starting with a string in `{"init", "add", "adopt",
     "ingest", "run", "doctor", "upgrade", "resolve",
     "schedule"}`.

The test message names the specific violation when it fails so a
future refactor's failure is immediately diagnosable. Known floor
of detection (named in R3 below): dynamically-built argv
(`["wi" + "ki", …]`) and `getattr`-style indirection
(`getattr(cli, "main")(…)`) are out of scope — the AC is a
tripwire, not a fence.

### 8. Mechanical gates green; declared-done check

Run, in order:

```
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

Note the gate command **includes `tests/`** for both `ruff check`
and `mypy` per the standing memory rule. `ruff format --check` is
a separate CI gate; passing `ruff check` does not imply formatter-
clean.

The check script itself lives under `starters/`, not
`llm_wiki_kit/`, so it is **excluded** from `ruff check llm_wiki_kit
tests` and `mypy llm_wiki_kit tests` by command scope. This is
intentional — `regenerate.py` is the same way (it's repo-author
tooling, not wheel content). The script must still be lint/type-clean
on its own merits, verified by running `ruff check starters/` and
`mypy starters/` manually before commit.

## Verification gate

Every spec AC has a test owner:

| AC  | Test                                                                                                      | Type        |
| --- | --------------------------------------------------------------------------------------------------------- | ----------- |
| AC1 | `test_starter_seed_coverage_clean_against_live_tree`                                                      | integration |
| AC2 | `test_content_type_uncovered_emits_finding`                                                               | unit        |
| AC3 | `test_ontology_folder_missing_emits_finding` + `test_ontology_folder_empty_emits_finding`                 | unit        |
| AC4 | `test_content_type_uncovered_emits_finding` + `test_content_type_covered_emits_no_finding` (round-trip)   | unit        |
| AC5 | `test_frontmatter_reader_handles_*` (six tests)                                                           | unit        |
| AC6 | `test_skipped_kinds_never_in_findings`                                                                    | unit        |
| AC7 | `test_check_is_read_only`                                                                                 | integration |
| AC8 | `test_check_coverage_respects_library_boundary`                                                           | static AST  |
| AC9 | `test_main_exit_codes` (in-process; see §Approach AC9 interpretation)                                     | unit        |
| AC10 | `test_determinism_same_input_byte_equal_output`                                                          | unit        |

Plus the four mechanical gates from step 8.

## Risks

- **R1: `from starters import regenerate` import side effects.** The
  module-level code in `regenerate.py` does
  `sys.path.insert(0, str(REPO_ROOT))` and then imports
  `llm_wiki_kit.cli`. Importing it from
  `check_coverage.py`'s top level may cause an import cycle if
  `check_coverage.py` also imports `cli` (which it doesn't today)
  or if a future kit refactor makes `cli` import-time fragile.
  Mitigation: the import is `from starters import regenerate` to
  pull `RECIPE_TARGETS` only; if cycle issues surface, switch to a
  lazy local import inside the helper function that needs it
  (matching `_import_regenerate` in the existing test file).
- **R2: AC9 in-process `main(kit_root=…)` test passes even though
  the kwarg is no-op.** If a future refactor stops threading
  `kit_root` through to `check_coverage` (e.g. someone hardcodes
  `REPO_ROOT` inside the function), the test might still pass
  because it controls fixture content but `main()` operates on the
  real repo. Mitigation: AC9's tests assert on output naming the
  fixture's recipe names (e.g. `"family"`) but the loader-raise case
  also asserts the *fixture's* malformed YAML is the one being
  read — a kwarg-ignored regression surfaces as "loader raised on
  the real repo's well-formed YAML, returncode is 0, not 2."
- **R3: Static AST scan false-negatives.** A determined contributor
  could use `getattr(cli, "main")(...)` to bypass AC8(c)'s direct
  `cli.main` check. Mitigation: the AC's intent is a tripwire, not
  a fence — if a future refactor needs that obfuscation, the
  reviewer will see it in code review. Don't paper over the
  detection; document the boundary.
- **R4: AC1 turns red after a future primitive lands without a
  seed.** That is the test working as designed — the test failure
  is the prompt to author the seed page in the same PR as the
  primitive. Mitigation: the PR author follows the spec's "what
  the maintainer does when the check fires" walkthrough.
- **R5: `pyyaml` upgrade reclassifies a frontmatter shape we
  currently accept.** The frontmatter reader is designed to return
  `None` on every YAML failure mode (parse error, non-mapping top
  level, non-string `type:`); it never re-raises. A stricter
  `pyyaml` release can therefore only *reduce* coverage scoring
  (some pages that previously contributed now return `None`),
  never crash CI. This is a design property of the reader, not a
  property of `yaml.safe_load`. Mitigation: keep the reader's
  every-failure-returns-`None` contract intact across any future
  edit; the test suite in step 2 pins it.

## Out of scope

- **Adding `--strict`, `--recipe <name>`, or any user-facing flag.**
  Explicitly rejected in spec §Non-goals.
- **Adding an `example_in_starters` field to `primitive.yaml`.** The
  spec picks structural signals over per-primitive declarations.
  Future RFC if needed.
- **Refactoring `regenerate.py` to share constants via a new helper
  module.** Direct import is sufficient for two callers; refactor
  when a third appears.
- **Promoting the AC1 integration test to a dedicated CI step with
  `continue-on-error: true` and `::warning::` annotations.** The
  spec acknowledges this as the alternative CI policy; this plan
  picks pytest-blocking. A future PR can demote if blocking proves
  too sharp.
- **A `wiki starters check` CLI verb.** Spec §Non-goals 4 — the
  check lives off-wheel by design.
- **A `.starter-coverage-ignore` carve-out file for deliberately
  unseeded primitives.** Spec §Edge cases names this as deferred
  until a real case appears. None exists today.
- **Coverage of operation/agent/infrastructure primitives.** Spec
  §Non-goals 1; invocation-style demonstration is a separate, harder
  problem.
