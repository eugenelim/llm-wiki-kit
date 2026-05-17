# Architecture Overview

> The map of this repo. Read this first when exploring. Updated whenever
> the directory layout, modules, or major dependencies change.

## What this repo produces

Two things, in one Python package:

1. **A CLI tool** (`wiki`) installed via `pip install llm-wiki-kit`. Users run
   it against a folder to create or extend an Obsidian-compatible markdown
   vault.
1. **A template catalog** the CLI reads from. Most “work” in this repo is
   authoring templates (primitives and recipes), not writing Python.

Together these let a non-engineer install the kit and get a vault shaped to
their life or work, with skills and schemas already wired up for Claude (or
any agent that reads `AGENTS.md` and SKILL.md files) to maintain.

## Layout

```
.
├── AGENTS.md                  # canonical agent context (CLAUDE.md is a symlink)
├── CLAUDE.md                  # → AGENTS.md (symlink)
├── README.md                  # user-facing intro
├── pyproject.toml             # pip-installable package
├── llm_wiki_kit/              # Python package: the tooling
│   ├── __init__.py
│   ├── cli.py                 # `wiki` entry point
│   ├── models.py              # Pydantic models (Primitive, Recipe, Event, Contract)
│   ├── errors.py              # WikiError base + ValidationError wrapper
│   ├── journal.py             # journal read/write + replay
│   ├── render.py              # stdlib str.format_map + region renderers
│   ├── primitives.py          # primitive discovery, loading, dep resolution
│   ├── recipes.py             # recipe loader + composition
│   ├── write_helper.py        # drift detection + proposal sidecar flow
│   ├── managed_regions.py     # region parsing + merging
│   ├── doctor.py              # vault state validation
│   ├── ingest.py              # `wiki ingest` routing logic
│   └── install.py             # region-contribution aggregator (used by init/add)
├── core/                      # the common-core primitive (always installed)
│   ├── primitive.yaml
│   └── files/                 # rendered into every vault
│       ├── AGENTS.md
│       ├── CORE.md
│       ├── frontmatter.schema.yaml
│       ├── .gitignore
│       └── skills/{ingest,wiki-search,wiki-lock,wiki-lint,wiki-conflict,wiki-doctor}/
├── templates/                 # the primitive catalog
│   ├── ontologies/            # folder shapes + seed files
│   ├── content-types/         # ingester + page template + frontmatter contribution
│   ├── operations/            # contract + skill + eval fixture
│   └── infrastructure/        # cross-cutting (research, search backends, etc.)
├── recipes/                   # YAML recipes composing primitives
│   ├── family.yaml
│   ├── work-os.yaml
│   └── personal.yaml
├── examples/                  # demo vaults (browsable before installing)
│   ├── family-mini/
│   └── work-os-mini/
├── tests/
│   ├── unit/                  # Python unit tests
│   ├── fixtures/              # seed vaults for integration + evals
│   └── evals/                 # Claude-driven eval suite
├── docs/
│   ├── CHARTER.md             # mission, scope, principles (one page)
│   ├── CONVENTIONS.md         # how we work
│   ├── ROADMAP.md             # bigger picture
│   ├── adr/                   # architecture decisions (frozen history)
│   ├── rfc/                   # proposals (governance)
│   ├── specs/                 # spec + plan per feature when needed
│   ├── architecture/          # this directory — current code structure
│   ├── concepts/              # Diátaxis: explanation
│   ├── how-to/                # Diátaxis: how-to
│   ├── reference/             # Diátaxis: reference
│   ├── tutorials/             # Diátaxis: tutorials
│   └── _templates/            # templates for adr / rfc / spec / plan
└── .github/                   # CI workflows, issue/PR templates
```

## The Python package

`llm_wiki_kit/` is small on purpose — one job per module, each independently
testable.

The kit bundles `recipes/`, `core/`, and `templates/` into the wheel via
a hatchling `force-include` relocation (see
[`docs/specs/wheel-bundled-assets/spec.md`](../specs/wheel-bundled-assets/spec.md)).
The source tree keeps them at the top level for catalog-editing ergonomics;
the wheel relocates them under `llm_wiki_kit/_assets/`. `cli._kit_root()`
resolves the right location for both install modes (wheel via
`importlib.resources`, editable / source-checkout via the package's
parent directory). Production code reads the resolved root through
`cli._kit_paths()` or accepts an explicit override via
`cli.main(argv, kit_root=...)`; the module-level `_KIT_ROOT` attribute
is the lazy cache, never read directly from outside the resolver block.

The dependency graph is intentionally a shallow DAG. `models.py` has no
internal imports; `journal.py` depends only on `models.py`; `write_helper.py`
depends on `journal.py` and `models.py`; everything else depends on the bottom
three. CLI is the only module with side effects beyond filesystem writes
inside `safe_write()`.

|Module              |Responsibility                                                                                                                                                                                                                                                |
|--------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`models.py`         |Pydantic v2 models for everything that crosses disk: primitives, recipes, journal events (discriminated union), operation contracts. The kit’s type contracts live here.                                                                                      |
|`errors.py`         |`WikiError` base + `ValidationError` wrapper that formats Pydantic errors into human-readable CLI output.                                                                                                                                                     |
|`journal.py`        |Append/read/replay over `.wiki.journal/journal.jsonl`. `read_events()` validates every line via the discriminated `Event` union and raises `JournalCorruptError(line=N)` on the first bad line. `replay_state()` returns a `VaultState`.                      |
|`write_helper.py`   |`safe_write(path, content, by, journal)` — the *only* sanctioned way for the kit to write to a vault file. Drift-aware: hashes on-disk, compares to last `PageWrite` event, falls through to `.proposed` sidecar on mismatch.                                 |
|`managed_regions.py`|Parse, update, and merge `<!-- BEGIN MANAGED: id --> ... <!-- END MANAGED: id -->` blocks in shared infrastructure files. Used for `AGENTS.md`, `frontmatter.schema.yaml`, `.claude/research-providers.yaml`.                                                 |
|`render.py`         |Stdlib `str.format_map` over `SafeDict`. Renders the ~5 files in `INTERPOLATED_FILES` with the build context; copies everything else verbatim. Region renderers (`render_ontologies_region`, etc.) generate managed-region content programmatically. No Jinja.|
|`primitives.py`     |`load_primitive(path) -> Primitive`, `discover_primitives(templates_dir)`, `resolve_dependencies()` for transitive `requires:` resolution.                                                                                                                    |
|`recipes.py`        |`load_recipe(path) -> Recipe`, `resolve_recipe_primitives()`. Validates that every primitive a recipe references exists.                                                                                                                                      |
|`doctor.py`         |Replays the journal, computes expected vault state, diffs against disk, reports drift in managed regions, orphan files, missing files.                                                                                                                        |
|`ingest.py`         |`wiki ingest` routing: classifies a source via per-primitive `routing:` signals (extension, filename glob, URL host/path) and records the decision as an `IngestRoutedEvent`. Pure string parsing — no I/O, no LLM.                                            |
|`install.py`        |Region-contribution aggregator used by `wiki init` and `wiki add`. Validates `contributes_to` against on-disk snippet files, groups by `(file, region)`, concatenates in install order, and writes each region once via `safe_write_region`.                  |
|`cli.py`            |Argparse-based entry point. Thin wrappers around `init`, `add`, `upgrade`, `doctor`, `ingest`, `run`, `research`, `search`, `journal`. (Phase D/E subcommands are stubs in v2.0.0.dev.)                                                                       |

## The template catalog

Everything under `templates/` is a primitive. A primitive is a directory with
this shape:

```
templates/<kind>/<name>/
├── primitive.yaml             # name, kind, version, description, requires, contributes_to, config
├── files/                     # copied verbatim into the vault
│   └── ...                    # may include _templates/, skills/, scripts/, etc.
├── regions/                   # contributions to shared files (managed-region inserts)
│   └── <target-file>.<region-id>
└── fixtures/                  # for evals
    ├── sample-input.*
    └── expected-output.*
```

Four primitive kinds, each with a distinct role:

- **`ontology`** — folder shapes plus seed files. Defines *where* something
  lives (`projects/`, `people/`, `food/`, etc.).
- **`content-type`** — a Claude-driven ingester (SKILL.md), a page template,
  and a contribution to `frontmatter.schema.yaml`. Defines *what* a kind of
  page looks like and how to create one from a source.
- **`operation`** — a `contract.yaml` (Pydantic-validated `OperationContract`),
  a SKILL.md, and fixtures. Defines a recurring action over the vault
  (`weekly-digest`, `meal-planning`, etc.).
- **`infrastructure`** — cross-cutting capabilities: `research` dispatch and
  its provider sub-primitives, search backends, source-ingest delta tracker.

Recipes (`recipes/*.yaml`) compose primitives into audience-specific bundles
— `family`, `work-os`, `personal`. Recipes don’t extend each other in
v2.0; if recipe inheritance becomes useful, it ships as a Tier 3 roadmap item.

## The journal (`.wiki.journal/journal.jsonl`)

The journal is the single source of truth for vault state. Every state-changing
operation appends one event before touching disk. Reading the journal back
gives you the complete history; replaying it computes current state.

Event types live in `models.py` as a discriminated Pydantic union. The current
event types are documented in `docs/reference/journal-events.md`. They group
into: `vault.*`, `primitive.*`, `managed_region.*`, `source.*`, `page.*`,
`operation.*`, `research.*`, `lint.*`, `config.*`.

The journal exists so the kit can answer four questions confidently:

1. **What’s installed?** → walk `primitive.install` / `primitive.remove` events.
1. **Has this source already been ingested?** → look up `source.ingest`.
1. **Did the user edit this file since I last wrote it?** → compare on-disk
   hash to the latest `page.write` event for that path. This is layer 1 of
   the write-safety design.
1. **Did this operation already run today?** → look up `operation.run` events
   for the current period.

There is no separate manifest, lockfile, or state cache. If something isn’t in
the journal, it didn’t happen.

## Three layers of write safety

The kit never writes to a user’s vault without one of three paths:

1. **No prior knowledge** → write directly (new file, append `page.write`).
1. **Prior knowledge + no drift** → write directly (hash matches the last
   `page.write` event for this path).
1. **Prior knowledge + drift detected** → write to `<path>.proposed` sidecar,
   append `page.proposal`, surface to user via the vault-side `wiki-conflict`
   skill.

For shared infrastructure files with multiple primitive contributors
(`AGENTS.md`, `frontmatter.schema.yaml`, `.claude/research-providers.yaml`),
a fourth layer applies: managed regions. The kit only writes inside its
declared `<!-- BEGIN MANAGED: id --> ... <!-- END MANAGED: id -->` block.
User edits outside the block survive untouched; user edits inside the block
trigger the proposal flow.

This whole subsystem is implemented in `write_helper.py` and
`managed_regions.py`. `safe_write()` is the only sanctioned write path —
nothing else in the kit calls `Path.write_text()` against a user’s vault.

## Rendering: stdlib, not Jinja

The kit uses Python’s stdlib `str.format_map` for the handful of files that
need string interpolation. Most files in `templates/*/files/` are copied
byte-for-byte into the vault.

The set of interpolated files is small and enumerable:

```python
INTERPOLATED_FILES = {
    "AGENTS.md", "CORE.md", "identity.md",
    "frontmatter.schema.yaml", ".gitignore",
}
```

The build context is a flat dict of ~10 known string variables (`vault_name`,
`recipe_name`, `rendered_ontologies`, etc.). Unknown keys pass through
untouched via a `SafeDict` subclass.

This means Obsidian Templater’s `{{date}}` and `{{title}}` syntax in page
templates passes through completely unchanged — there’s no delimiter
collision because the kit only interpolates `{single_brace}` references and
only inside the allowlist. ADR-0001 covers why we landed here instead of on
Jinja.

## The kit-vs-vault distinction

This repo contains both **the kit’s own code and docs** (what you read when
working on the kit) and **the templates that get rendered into a user’s
vault** (what their Claude reads inside their vault). The two contexts must
not bleed into each other.

|Kit-side                       |Vault-side                                                                       |
|-------------------------------|---------------------------------------------------------------------------------|
|`AGENTS.md` at repo root       |`core/files/AGENTS.md` (renders into the user’s vault)                           |
|`docs/CHARTER.md`              |`core/files/CORE.md` (the vault’s equivalent — what the LLM-maintained wiki *is*)|
|`docs/architecture/overview.md`|None — vaults don’t need one                                                     |
|`tests/`                       |None — vaults are user-owned, not test-instrumented                              |
|Python in `llm_wiki_kit/`      |Markdown in `core/files/skills/` and `templates/*/files/skills/`                 |

When in doubt: anything under `core/` or `templates/` is vault-side. Anything
else is kit-side.

## Where to start

- **Working on a migration task?** Read `docs/rfc/0001-v2-architecture.md`
  for the full plan, find your task, follow the workflow in `AGENTS.md`.
- **Authoring a new primitive?** Read `docs/how-to/author-a-primitive.md`,
  then look at `templates/content-types/meeting/` for a worked example.
- **Authoring a new recipe?** Read `docs/reference/recipe-schema.md`, then
  look at `recipes/family.yaml`.
- **Touching the journal or write helper?** Read ADR-0002 (journal as state
  truth), ADR-0003 (managed regions), ADR-0004 (drift detection) first.
- **Touching the data models?** Read ADR-0005 (Pydantic for disk-bound
  schemas) first.

## Conventions you’ll see across modules

- **`safe_write()` is the only write path.** Nothing else calls `write_text()`
  on a user-vault file. Tests can use `Path.write_text()` against `tmp_path`
  freely.
- **Pydantic models for anything that crosses disk.** In-memory plumbing uses
  plain dataclasses or function signatures with type hints. ADR-0005 has the
  reasoning.
- **Errors raise `WikiError` subclasses, not bare `ValueError`.** The CLI
  catches `WikiError` and prints human-readable messages; bare exceptions
  produce tracebacks.
- **Tests live next to the code they cover** (`tests/unit/test_<module>.py`)
  for unit tests, `tests/integration/test_<command>.py` for CLI integration.
  Evals live in `tests/evals/` and run in a separate CI workflow.
