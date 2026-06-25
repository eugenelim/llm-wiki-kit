# Plan: projection-port

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

One new module, `llm_wiki_kit/projection.py`, holds the closed/mechanical
projection chain as small pure functions plus one orchestrator. It sits one
layer above `write_helper` (it calls `safe_write`) and depends on `journal`,
`write_helper`, `errors`, and stdlib `yaml`. A thin `wiki project` CLI verb in
`cli.py` is the only entry point. The riskiest part is schema validation, which
is net-new (no Python validates faceted frontmatter today) and is the
vault-protecting boundary — it gets TDD'd first, in isolation, before anything
touches disk. Destination routing is a fixed `genre` → role-folder table plus
the existing `_resolve_out_path` traversal-safety pattern. The orchestrator
wires parse → validate → resolve → `safe_write`; the verb adds argument parsing
and one-line output. Last, the vault-side `ingest` SKILL prose is re-pointed
from "write via `safe_write`" to "write via `wiki project`".

## Constraints

- **RFC-0010** — the port is the single sanctioned mechanical write path; it owns
  the closed half (validate/resolve/write/journal) and not the open/reasoning
  half (scope, contradiction, fact propagation, changelog).
- **RFC-0009 / `role-folders-and-containers`** — four fixed role folders; kind is
  `subtype`, never a folder. Routing is `genre` → role folder.
- **ADR-0004** — `safe_write` is the only write path; the port must not bypass it.
- **ADR-0002** — the journal is state truth; the `PageWrite`/`PageProposal` event
  `safe_write` appends is the projection's journal record.
- **ADR-0011** — the `genre`/`subtype` facet split the validator enforces.

## Construction tests

**Integration tests:** `tests/integration/test_project.py` — `wiki project`
against a seeded `tmp_path` vault: happy-path write under the routed role folder
+ one `PageWrite`; `--at` override; drift collision → `.proposed` + `PageProposal`;
each rejection path (bad genre, unknown subtype, missing facet, malformed/absent
frontmatter, escaping `--at`, missing role folder) exits non-zero and leaves the
vault byte-unchanged with no new event.

**Manual verification:** run `wiki project` once by hand on a fixture vault
through its happy path; record stdout, exit code, the written file, and the
appended journal line.

## Design (LLD)

### Design decisions

- **One module, pure-core + thin orchestrator.** `projection.py` keeps parsing,
  validation, and routing as pure functions (TDD-friendly, no I/O) and a single
  `project()` that performs I/O only via `safe_write`. Rejected: putting the
  logic in `cli.py` (untestable without argparse) or in `write_helper.py`
  (would couple the low-level write primitive to schema knowledge). Traces to:
  all ACs · contracts/: none.
- **`genre` → role-folder routing, not `subtype` → path.** A nine-entry constant
  maps each genre to one of the four role folders. Rejected: a `subtype`→folder
  table (violates `role-folders-and-containers` §Never do) and a vault-resident
  routing config (the four roles are fixed kit structure, not user config).
  Traces to: AC1, AC9 · contracts/: none.
- **One shared confinement helper for both path branches.** `_resolve_out_path`
  moves from `cli.py` to `projection.py` as `resolve_vault_path(raw, vault_root,
  *, label)`; both the `--at` branch and the genre-routed `wiki/<role>/<basename>`
  candidate (basename reduced to `Path(artifact).name` first) pass through it, and
  `_cmd_research` is re-pointed to it so confinement has exactly one
  implementation. Rejected: reimplementing the check in `projection.py` (the
  rolled-its-own confinement trap — one copy hardens, the other drifts). Traces
  to: AC3 · contracts/: none.
- **`--as` override re-serializes only the frontmatter block; the body is
  verbatim.** Absent `--as`, the artifact is written byte-for-byte. On override,
  `yaml.safe_dump(..., sort_keys=False)` preserves key order and every non-`subtype`
  key/value. Rejected: always re-serializing (reformats user frontmatter in the
  common case). Traces to: AC4 · contracts/: none.

### Interfaces & contracts

The public surface is the CLI verb and the module's `project()` function:

```
wiki project <artifact.md> [--at <dest>] [--as <subtype>] [--by <name>]

projection.project(
    artifact_path: Path, vault_root: Path, journal_path: Path,
    *, at: str | None, subtype: str | None, by: str | None,
) -> ProjectResult        # (result: WriteResult, dest_rel: str, dest_abs: Path)
```

No `contracts/` artifact — the verb is an internal CLI surface, exercised by
integration + manual QA (Testing Strategy). Traces to: AC1–AC12.

### Data & schema

Reads `<vault_root>/frontmatter.schema.yaml` (already rendered into every vault)
via `yaml.safe_load`: `required` (list), `genres` (fixed enum list), `subtypes`
(managed-region list; the `# BEGIN/END MANAGED` markers are YAML comments, so
`safe_load` yields the plain list), `statuses`, `provenance`. No schema change; no
new model. Traces to: AC5, AC6.

### Failure, edge cases & resilience

Every validation/resolution failure raises `WikiError` with a one-line message
**before** any `safe_write` call, so a rejected projection leaves the vault and
journal byte-unchanged (no partial write). Drift on the resolved destination is
*not* a failure — it is the existing `safe_write` `.proposed` path (AC8). Missing
role folder (AC9) and a path-confinement escape on either branch (AC3) are
rejections, not folder creation. `safe_write`'s event-before-disk ordering means
the port needs no transaction wrapper (single event per call). Traces to: AC3,
AC6–AC9.

### Quality attributes (NFRs)

Security posture: untrusted foreign frontmatter, an untrusted `--at`, **and an
untrusted artifact basename** cross the boundary. Both path branches route through
the one shared `resolve_vault_path` confinement (canonicalize-then-verify-prefix);
all YAML parsing is `yaml.safe_load`; frontmatter is validated against closed enums
before any write. No new dep keeps the install closure unchanged. Traces to: AC3,
AC5.

## Tasks

### T1: Strict frontmatter parse + schema load + facet validation

**Depends on:** none

**Tests:** (TDD — `tests/unit/test_projection_validate.py`)
- `parse_frontmatter` splits a `---`-delimited block into `(dict, body)`; body
  preserved verbatim including trailing content.
- Missing frontmatter block → `WikiError`; opening `---` with no closing `---` →
  `WikiError`; malformed YAML inside the block → `WikiError` (not silent `{}`) (AC7).
- A frontmatter carrying `!!python/object` (or any non-safe tag) → `WikiError`, not
  a deserialized object — parsing is `yaml.safe_load` (AC5).
- `load_schema` parses a rendered `frontmatter.schema.yaml` into
  `{required, genres, subtypes, statuses, provenance}` via `yaml.safe_load`; the
  `subtypes` managed-region comments do not leak into the list (AC6).
- `validate_frontmatter` passes a fully-valid faceted frontmatter; each rejection
  raises `WikiError` naming the offending facet: a missing required facet, `genre`
  outside `genres`, `status`/`provenance` outside enum, `subtype` not in
  `subtypes` (AC6).

**Approach:**
- New `llm_wiki_kit/projection.py`. `parse_frontmatter(text) -> tuple[dict, str]`
  modeled on the strict half of `search.py:_read_page` but raising (and using
  `yaml.safe_load`) instead of returning `{}`.
- `load_schema(vault_root) -> SchemaFacets` (a small frozen dataclass or dict).
- `validate_frontmatter(frontmatter, schema) -> None` checks presence then
  membership, raising `WikiError` on the first failure.

**Done when:** `pytest tests/unit/test_projection_validate.py` green; AC5, AC6, AC7
branches covered.

### T2: Single confinement helper + `genre` → role-folder resolution

**Depends on:** none

**Tests:** (TDD — `tests/unit/test_projection_resolve.py`)
- `ROLE_FOLDERS` maps all nine genres: `profile`→`people`, `moc`→`atlas`, the
  other seven →`library` (AC1).
- `resolve_destination(genre, basename, at=None, vault_root=...)` →
  `wiki/<role>/<basename>` when the role folder exists (AC1).
- `at="<rel>"` overrides routing and resolves vault-relative (AC2).
- **Confinement of both branches (AC3):** `--at` of `..`, an absolute path, and a
  **symlinked parent directory** pointing outside the vault each raise `WikiError`;
  *and* a crafted artifact basename containing path separators / `..` is reduced to
  `Path(name).name` and still cannot escape `wiki/<role>/` — assert both branches
  call `resolve_vault_path`.
- Unknown genre (not in `ROLE_FOLDERS`) and a routed-to role folder absent on disk
  each raise `WikiError` naming the problem (AC9).
- A degenerate basename (`.`, empty, trailing-slash) raises `WikiError` rather than
  resolving to the role folder itself (robustness — not an escape, but a bad slug).

**Approach:**
- Move `_resolve_out_path` from `cli.py` into `projection.py` as
  `resolve_vault_path(raw, vault_root, *, label) -> tuple[str, Path]` (the one
  confinement implementation); re-point `_cmd_research` to it (passing
  `label="--out"`).
- `ROLE_FOLDERS: dict[str, str]` constant.
- `resolve_destination(...) -> tuple[str, Path]`: `--at` branch → `resolve_vault_path`
  with `label="--at"`; routing branch builds `wiki/<role>/<Path(basename).name>`,
  asserts the role-folder parent dir exists, then passes the candidate through
  `resolve_vault_path` (defense-in-depth) with `label="destination"`.

**Done when:** `pytest tests/unit/test_projection_resolve.py` green; AC1, AC2, AC3,
AC9 path branches covered; `_cmd_research` still green via the moved helper.

### T3: `project()` orchestrator writes through `safe_write`

**Depends on:** T1, T2

**Tests:** (TDD — `tests/unit/test_projection_project.py`, `tmp_path` vault)
- A valid artifact projects to the routed dest and returns
  `ProjectResult(WRITTEN, rel, abs)`; exactly one `PageWrite` in the journal,
  attributed to `wiki-project` by default (AC1, AC10).
- `--by` overrides attribution (AC10).
- `--as` on an artifact that already declares `subtype` overrides it; on an
  artifact that omits `subtype` it sets it (AC4). In both cases the written
  frontmatter carries the new subtype, **every other frontmatter key/value is
  preserved** (assert the full parsed dict minus `subtype` is unchanged), and the
  body is byte-identical to the input body (AC4).
- An artifact omitting `subtype` with no `--as` → AC6 rejection (missing required
  facet).
- A drifted existing destination yields `ProjectResult(PROPOSAL, …)`, a
  `.proposed` sidecar, and a `PageProposal` event — no overwrite (AC8).
- A validation failure raises before `safe_write`: no file written, no event
  appended (AC6 — assert journal length unchanged).

**Approach:**
- `project(artifact_path, vault_root, journal_path, *, at, subtype, by)`:
  read text → `parse_frontmatter` → apply `subtype` override (re-serialize the
  frontmatter block with `yaml.safe_dump(sort_keys=False)`, keep body verbatim)
  → `load_schema` → `validate_frontmatter` → `resolve_destination` →
  `by = by or PROJECT_VEHICLE` (`"wiki-project"`) →
  `safe_write(dest_abs, full_text, by, journal_path)` → return `ProjectResult`.
- `ProjectResult` plain dataclass (not disk-bound, so no Pydantic per ADR-0005).
- `PROJECT_VEHICLE = "wiki-project"` module constant (mirrors `RESEARCH_VEHICLE`).

**Done when:** `pytest tests/unit/test_projection_project.py` green; AC1, AC4, AC6,
AC8, AC10 hold against `tmp_path`.

### T4: `wiki project` CLI verb

**Depends on:** T3

**Tests:** (goal-based + manual QA — `tests/integration/test_project.py`)
- Cross-cutting integration suite (see Construction tests) against a seeded
  `tmp_path` vault: happy path, `--at`, drift→proposal, and every rejection path
  (bad genre, unknown subtype, missing facet, malformed/absent frontmatter,
  non-safe YAML tag, escaping `--at` or basename, missing role folder) exits
  non-zero and leaves the vault byte-unchanged with no new event (AC1–AC9).
- Manual QA: run `wiki project` by hand once; record stdout, exit code, written
  file, journal line.

**Approach:**
- `_cmd_project(args)` in `cli.py`: resolve `vault_root = Path.cwd().resolve()`,
  `journal_path`, reject non-vault dirs (mirror `_cmd_search`); call
  `projection.project`; print one line (`wrote <rel>` / `proposal at <rel>.proposed`);
  return 0. `WikiError` propagates to `main`'s handler (non-zero exit).
- Register the `project` subparser with positional `artifact`, `--at`, `--as`,
  `--by`; wire to `_cmd_project`.

**Done when:** `tests/integration/test_project.py` green; the manual run is
recorded in the PR; `wiki project --help` lists the flags.

### T5: `ingest` SKILL prose points at the port

**Depends on:** T4

**Tests:** (goal-based)
- `grep` over `core/files/skills/ingest/SKILL.md`: the shared-flow write step and
  the anti-pattern reference `wiki project`; no remaining instruction to call
  `safe_write` directly from the skill (AC11).

**Approach:**
- Edit the shared-flow "Write" step (lines ~134–139) and the anti-pattern (line
  ~183) to name `wiki project <artifact> --as <subtype>` as the sanctioned write
  path, preserving the scope/contradiction/fact/changelog reasoning steps as the
  skill's own (they stay; only the write mechanism changes).

**Done when:** the grep passes; the SKILL still describes the reasoning half as
skill-owned (the Never-do boundary holds).

## Rollout

Pure additive change: a new verb and a doc edit, no infra, no migration, fully
reversible by removing the module + verb. No deployment sequencing.

## Risks

- **Schema-shape coupling.** The validator reads keys (`genres`, `subtypes`, …)
  from `frontmatter.schema.yaml`; a future schema-format change would break it.
  Mitigation: `load_schema` is one small function with its own tests; the format
  is fixed by RFC-0009 / ADR-0011.
- **`--as` re-serialization reformats frontmatter.** Only on override, and only
  the frontmatter block (body verbatim); documented in the verb help.

## Changelog

- 2026-06-24: initial plan.
- 2026-06-24: spec-review r1 — (security Blocker) confine both path branches
  through one shared `resolve_vault_path` (moved from `cli._resolve_out_path`),
  reduce basename to `Path(name).name`; pin `yaml.safe_load`; (adversarial) default
  `by` to the `wiki-project` vehicle not the page subtype; specify `--as`
  frontmatter-fidelity round-trip; flag the genre-vs-subtype RFC divergence and the
  container-pages-need-`--at` rule. AC count 10 → 12; task AC refs re-numbered.
