# How to add a primitive (upstream PR path)

Walks through adding a new primitive to the kit's bundled catalog
via an upstream PR. For the *why* behind upstream vs. sideload, see
[`docs/guides/explanation/extending-the-kit.md`](../explanation/extending-the-kit.md).
For sideload mechanics, see
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) §"Walkthrough 2 —
sideload package."

This walkthrough assumes a content-type primitive — the most common
shape. Operation and ontology primitives follow the same skeleton; the
extra files for an operation (`contract.yaml`,
`files/skills/<name>/SKILL.md`) are called out at the end.

## Step 1 — confirm the decision tree

Open [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) §"Decision tree."
Answer all three questions. If any answer is no, your primitive
belongs in a sideload package, not upstream. If all three are yes,
continue here.

## Step 2 — pick a name and a kind

`name:` must match `^[a-z][a-z0-9-]*$` and not collide with any
existing primitive (run
`ls templates/{content-types,operations,ontologies,infrastructure,agents}/`
to check). Kebab-case, lowercase.

`kind:` is one of:

- `content-type` — a per-page schema (e.g. `meeting`, `recipe`).
- `ontology` — a folder of related content-types and seed pages
  (e.g. `dnd-campaign`).
- `operation` — a periodic or on-demand task (e.g. `weekly-digest`).
- `infrastructure` — a shared config primitive that contributes to a
  managed region of a shared file (e.g. `research-perplexity`).
- `agent` — a kit-resolvable agent persona (e.g.
  `personal-coordinator`).

This walkthrough uses a `briefing-doc` content-type as the running
example.

## Step 3 — write `primitive.yaml`

```
templates/content-types/briefing-doc/primitive.yaml
```

```yaml
name: briefing-doc
kind: content-type
version: 0.1.0
description: >-
  A page describing one topic in enough depth to brief a colleague who
  has never heard of it before.
requires: []
contributes_to:
  - file: frontmatter.schema.yaml
    region: types
```

If your primitive contributes to a shared file (the
`contributes_to:` entry above), you also need a snippet file under
`regions/` whose filename is `<file>.<region>`:

```
templates/content-types/briefing-doc/regions/frontmatter.schema.yaml.types
```

```yaml
- type: briefing-doc
  required: [type, title]
  optional: [audience, prerequisites]
```

The snippet file holds the bytes the kit concatenates into the
shared file's managed region. ADR-0006 §Mechanics is the source of
truth for that pipeline.

## Step 4 — optional `files/` tree

If your primitive ships any vault-resident page (template, SKILL,
seed file), drop it under `files/`. The directory's structure
relative to `files/` becomes its path inside the vault.

For `briefing-doc`, the kit's standard pattern is to ship a template
the user can copy:

```
templates/content-types/briefing-doc/files/_templates/briefing-doc.md
```

```markdown
---
type: briefing-doc
title: ""
---

# {{title}}

Audience:
Prerequisites:
```

## Step 5 — write seed coverage

The `starter-seed-coverage` check requires at least one seed page
demonstrating every content-type and ontology shipped by any
upstream recipe. Drop a seed page into the recipes that will bind
your primitive:

```
starters/_seed/family/wiki/briefings/example-brief.md
```

```markdown
---
type: briefing-doc
title: "Why we picked SQLite"
audience: engineering
prerequisites: none
---

We picked SQLite over Postgres for v1 because…
```

Repeat for every recipe whose closure includes your primitive.

## Step 6 — gates

Run locally before opening the PR:

```bash
pip install -e '.[dev]'
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
python starters/check_coverage.py
```

CI runs the same gates plus the `starters/regenerate.py --check`
byte-equivalence guard. If your primitive changes byte output for a
bundled recipe (e.g. a new region contribution affects
`frontmatter.schema.yaml`), regenerate the committed starters:

```bash
python starters/regenerate.py --apply
git add starters/
```

This commits the regenerated trees alongside your primitive — the
projection invariant (`docs/architecture/starters.md`) keeps them
deterministic.

## Step 7 — for operation primitives, also write `contract.yaml`

```
templates/operations/your-op/contract.yaml
```

```yaml
name: your-op
description: One-line description of the operation.
period: weekly
skill: your-op
outcomes:
  - <some-verb>
inputs:
  some-input:
    type: string
outputs:
  pages: list
```

The `outcomes:` list registers verbs the kit exposes through
`wiki outcomes`, the slash-stub at
`.claude/commands/<verb>.md`, and the SKILL-trigger fragment. Every
verb must match the shape pinned in
[`docs/specs/outcome-named-entry-points/spec.md`](../../specs/outcome-named-entry-points/spec.md).

The matching SKILL.md description must contain each declared verb as
a whole word:

```
templates/operations/your-op/files/skills/your-op/SKILL.md
```

```markdown
---
description: Your-op runs <some-verb> on the vault.
---
```

If the description omits the verb, `wiki init` / `wiki add` refuse
to install the primitive — that's the SKILL-fragment gate firing.

## Step 8 — open the PR

Reference the contribution model and the decision-tree question you
answered "yes" to in your PR description. The maintainer reviews
seed coverage, naming, and the bundled-recipe binding — if any of
those needs work, you'll hear about it in review.

If your primitive introduces a new outcome-verb stem (a verb shape
not already in
[`templates/operations/.../contract.yaml::outcomes`](../../../templates/operations/)),
extend `OUTCOME_VERB_STEMS` in `llm_wiki_kit/primitives.py` in the
same PR. The constant is documented in the outcome-named-entry-points
spec.

## Further reading

- [`docs/specs/primitive-sideload/spec.md`](../../specs/primitive-sideload/spec.md)
  — what changes when a primitive lives in a sideload package.
- [`docs/adr/0005-pydantic-for-disk-bound-schemas.md`](../../adr/0005-pydantic-for-disk-bound-schemas.md)
  — why every primitive ships a Pydantic-validated `primitive.yaml`.
- [`docs/adr/0006-additive-managed-region-contributions.md`](../../adr/0006-additive-managed-region-contributions.md)
  — the managed-region pipeline `contributes_to:` flows into.
