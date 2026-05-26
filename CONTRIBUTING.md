# Contributing

Thanks for thinking about contributing. The kit ships a small core
plus a catalog of droppable primitives, and contributions follow a
**hybrid model**: most generic primitives belong upstream in the kit
itself; niche, audience-narrow, or pre-publication primitives belong
in a separate Python package that the kit discovers via the
`wiki-primitive` entry-point group (a "sideload" package).

Pick a path using the decision tree below, then follow the matching
walkthrough.

## Decision tree — upstream PR or sideload?

**Answer all three. Yes to all three → upstream PR.
No to any one → sideload.**

1. **Could any of the kit's three shipped recipes (`family`,
   `work-os`, `personal`) bind this primitive without surprising a
   typical user of that recipe?** A hypothetical `ingest-podcast`
   content-type is plausibly bound in `personal` and `family` —
   anyone might want to clip a podcast. A new
   `ingest-dnd-session-notes` content-type is not — no shipped recipe
   should bind it by default.

2. **Does this primitive's vocabulary apply outside one audience's
   mental model?** "Meeting", "recipe", "trip", "stakeholder" — every
   author understands what these mean. "DnD session", "EHR followup",
   "competitor brief" — domain-narrow. If you have to explain the
   vocabulary before the primitive name makes sense, the primitive
   belongs in a sideload package that targets the audience that
   already knows it.

3. **Are you willing to write the starter-seed demonstration the
   upstream path requires?** Per
   [`docs/specs/starter-seed-coverage/spec.md`](docs/specs/starter-seed-coverage/spec.md),
   every upstream content-type or ontology must be demoed by at least
   one seed page in `starters/_seed/<recipe>/wiki/`. If you cannot
   produce a credible seed page (because the primitive's audience has
   no seed-shaped example among the bundled recipes), the primitive
   belongs in a sideload package.

### Spec-or-PR threshold

Most primitives ship via a plain PR (one ingest skill, one
content-type, one operation). Specs under `docs/specs/` are required
for:

- A new primitive *kind* (RFC, not just a spec).
- A new infrastructure primitive that changes catalog-load semantics.
- An operation introducing a new outcome-verb stem (see
  [`docs/specs/outcome-named-entry-points/spec.md`](docs/specs/outcome-named-entry-points/spec.md)).

When in doubt, draft a spec and ask in the PR description.

## Walkthrough 1 — upstream PR (most cases)

1. Fork the repo and create a branch. Local development:
   `pip install -e '.[dev]'`.

2. Drop your primitive under `templates/<kind>/<name>/` matching one
   of the five kinds (`content-types/`, `ontologies/`, `operations/`,
   `infrastructure/`, `agents/`). Mirror the shape of a similar
   bundled primitive (e.g. `templates/content-types/meeting/`) as
   your starting point.

3. Write at least one seed page under
   `starters/_seed/<recipe>/wiki/` so
   `python starters/check_coverage.py` reports clean.

4. Run the gates locally:
   ```
   ruff check llm_wiki_kit tests
   ruff format --check llm_wiki_kit tests
   mypy llm_wiki_kit tests
   pytest -m 'not slow'
   ```
   CI runs the same gates.

5. If your primitive changes byte-output for a bundled recipe, run
   `python starters/regenerate.py --apply` and commit the diff. The
   starter trees are committed alongside the kit's code.

6. Open the PR. Maintainers may ask for additional seed coverage or
   a small spec amendment; that's expected.

## Walkthrough 2 — sideload package

A sideload package is a separate Python package you publish (or
install locally) that the kit reads at runtime. The kit reads the
`wiki-primitive` entry-point group via `importlib.metadata` to find
sideload packages installed in the active Python environment.

### Package skeleton

```
your-pkg/
  pyproject.toml
  src/your_pkg/
    __init__.py
    templates/
      content-types/your-thing/primitive.yaml
      content-types/your-thing/files/...      # optional
      content-types/your-thing/regions/...    # optional
      operations/your-op/primitive.yaml       # if shipping an op
      operations/your-op/contract.yaml        # required for outcomes
      operations/your-op/files/skills/your-skill/SKILL.md
```

The kit MUST be able to use `importlib.resources.files("your_pkg") /
"templates"` to reach your `templates/` tree — so a regular wheel
install (not a zipped wheel or zipapp) is required. The kit raises a
`PrimitiveError` naming your package at the first filesystem operation
if the layout cannot be traversed.

### `pyproject.toml` entry-point declaration

```toml
[project.entry-points."wiki-primitive"]
your-pkg = "your_pkg"
```

The kit reads `entry_points(group="wiki-primitive")` at every CLI
invocation. The entry-point value is the importable Python module name
of your package; the kit resolves
`importlib.resources.files("<that name>") / "templates"` and walks the
tree the same way it walks its own bundled `templates/`.

### What changes for sideload primitives (vs. bundled)

- **Schema laxity.** Sideloaded primitives load with Pydantic
  `extra='ignore'` — unknown fields are dropped, not rejected. Bundled
  primitives still load with `extra='forbid'`. `wiki doctor` reports
  any dropped field by package + primitive so the looseness stays
  visible.
- **Provenance decoration.** `wiki outcomes` adds a `Source` column
  showing `sideload:<your-pkg>`; the generated slash-stub at
  `.claude/commands/<verb>.md` carries a managed-region block naming
  your package and version; `wiki doctor` lists installed sideload
  packages with their primitives.
- **Collision policy is additive-only.** Your package cannot ship a
  primitive named the same as a bundled primitive, cannot duplicate a
  bundled outcome verb, cannot ship the same `files/skills/<name>/`
  directory, and cannot contribute to a managed region already owned
  by a bundled primitive. All four collisions raise at load time with
  a specific error message — if you actually want to *override*
  bundled behavior, that's a fork-the-kit or upstream-PR decision.

### Testing locally without publishing

In your sideload package's repo:

```
pip install -e .
pip install llm-wiki-kit
wiki doctor  # should show your package under "Sideload primitives:"
```

The kit's `wiki doctor` output is the loop you'll iterate against —
mistakes (missing `templates/`, bad SKILL.md descriptions, name
collisions) surface as clear load-time errors there.

### Versioning and compatibility

The kit pins `primitive.yaml schema_version: 1` today. Your package
should depend on `llm-wiki-kit>=2.1,<3` (or the equivalent range your
sideload targets). The kit treats `schema_version: 2` as a hard
failure today; a future RFC may introduce schema v2 with a stated
deprecation window.

## Further reading

- [`docs/specs/primitive-sideload/spec.md`](docs/specs/primitive-sideload/spec.md)
  — the contract for what a sideload package ships and how the kit
  loads it.
- [`docs/rfc/0007-primitive-contribution-model.md`](docs/rfc/0007-primitive-contribution-model.md)
  — the policy decision the hybrid model rests on.
- [`docs/guides/explanation/extending-the-kit.md`](docs/guides/explanation/extending-the-kit.md)
  — architectural framing: why hybrid, what each path costs, when
  each is right.
- [`docs/guides/how-to/add-a-primitive.md`](docs/guides/how-to/add-a-primitive.md)
  — step-by-step for the upstream PR path with file-tree examples.
