# Changelog

All notable changes to `llm-wiki-kit` are documented in this file.

The format follows the spirit of
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) —
an `[Unreleased]` section at the top, Added / Changed / Removed
categories, and compare links at release time — with two deviations:
category headers carry an RFC phase suffix
(`### Added — Phase A: Foundation …`), and the `Added` category is
split into one subsection per RFC phase rather than one flat block.
Naive `grep '^### Added$'` tooling will not find any matches. The
project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Project state and direction lives in [`docs/ROADMAP.md`](docs/ROADMAP.md); this
file is the shipped-work record. Decisions behind shipped work live in
[`docs/adr/`](docs/adr/); migration sequence and task-by-task progress live in
[`docs/rfc/0001-v2-architecture.md`](docs/rfc/0001-v2-architecture.md).

## [Unreleased]

The v2.0.0 line, in flight on the working branch. v2 replaces v1's three
hand-edited template variants (`vault-templates/{family,work,personal}/`)
with a common core, a catalog of droppable primitives, and recipes that
compose primitives for an audience. See
[RFC-0001](docs/rfc/0001-v2-architecture.md) for the full plan and
task-by-task progress; phase headings below match its
§"Migration sequence".

Tasks 1–20 plus Phase F Task 27 have shipped (alongside the four
cross-cutting specs below). Task 21 (example vaults and tutorials)
remains in Phase E, and Phase F's remaining Tasks 23–26 — a sweep
of v2.0.0 contract-completion bugs added during the pre-tag audit —
also remain. Task 22 (README, ROADMAP, tag) blocks on Phase F
completing. The release-cut at Task 22 promotes this `[Unreleased]`
section to `## [2.0.0] — <date>`.

### Added — Phase A: Foundation (Tasks 1–5)

- Charter, RFC-0001, ADRs 0001–0005, and the kit-side `AGENTS.md`
  scaffolding (Task 1).
- Python package skeleton: `pyproject.toml`, the `wiki` CLI entry point
  with stubbed subcommands, and the CI workflow (Task 2).
- Pydantic v2 models (`models.py`) for `Primitive`, `Recipe`, the
  discriminated `Event` union, and `OperationContract`, plus `errors.py`
  (Task 3).
- Journal module (`journal.py`) with append / read / replay over the
  validated event union (Task 4).
- Write helper (`write_helper.py`) with `safe_write` and the proposal
  sidecar flow that backs ADR-0004's drift-detection contract (Task 5).

### Added — Phase B: Render and load (Tasks 6–10)

- Managed-region parser (`managed_regions.py`) and `safe_write_region`
  integration so multiple primitives can contribute to one file
  (Task 6).
- Render module (`render.py`) with `SafeDict` and the
  `INTERPOLATED_FILES` allowlist; everything else copies byte-for-byte
  per ADR-0001 (Task 7).
- Primitive loader and the first real primitive (`core`) with all
  baseline skills (Task 8).
- Recipe loader (`recipes.py`) and the three initial recipe files —
  `family`, `work-os`, `personal` (Task 9).
- `wiki init` end-to-end: the first working command, producing a vault
  with only the `core` primitive (Task 10). `--adopt` deferred to a
  follow-on.

### Added — Phase C: Primitives (Tasks 11–15)

- Three end-to-end primitives — `people` (ontology), `meeting`
  (content-type), `weekly-digest` (operation) — proving the primitive
  model. Surfaced ADR-0006 (additive managed-region contributions)
  (Task 11).
- `wiki add` and `wiki doctor` lifecycle commands (Task 12).
- Family-recipe primitives: `food`, `medical`, `trips`, `vendors`
  ontologies; `recipe`, `medical-record`, `trip-doc`, `receipt`,
  `tax-document`, `action-item` content-types; `meal-planning`,
  `trip-prep`, `follow-up-tracker`, `medical-summary` operations
  (Task 13).
- Work-os-recipe primitives: `projects`, `domains`, `customers`
  ontologies; `stakeholder-update`, `vendor-contract`,
  `customer-feedback`, `interview`, `decision` content-types;
  `stakeholder-map-refresh`, `action-item-rollup`,
  `renewal-reminders`, `onboarding-pack`, `status-synthesis`
  operations (Task 14).
- `identity` ontology (net new) and finalized `personal` recipe,
  which composes from Tasks 11/13/14 primitives plus `identity`
  (Task 15). (The `recipes/personal.yaml` file itself was first
  added in Task 9; Task 15 finalized its contents.)

### Added — Phase D: Runtime (Tasks 16–19)

- `wiki ingest` and the routing orchestrator — content-type
  detection via filename glob, file extension, URL host, URL path;
  `--as <name>` override (Task 16).
- `wiki run` and operation execution — contract-driven dispatch via
  `llm_wiki_kit.run`; `OperationRunEvent` records every attempt with
  status `dispatched` or `invalid_args` (Task 17).
- Research dispatch and the Perplexity provider — in-process
  dispatcher in `llm_wiki_kit/research/` using stdlib
  `urllib.request` (no new runtime deps); two opt-in infrastructure
  primitives (`research` and `research-perplexity`);
  `journal.transaction` wrap on `--out`; surfaced ADR-0007 codifying
  vault-root placement for the shared config file (Task 18).
- Gemini Deep Research and Semantic Scholar providers, completing
  the research-provider trio. All three are opt-in (Task 19).

### Added — Phase E: Quality and ship — Task 20 (Tasks 21–22 remain)

- Eval harness — `trigger/`, `outcome/`, `provenance/`, `conflict/`,
  `research/` suites driving Claude Code via subprocess against
  fixture vaults; runs in its own CI workflow (Task 20).

### Added — Phase F: Contract-completion bugs — Task 27 (Tasks 23–26 remain)

The pre-tag audit (2026-05-20) added a sweep of v2.0.0
contract-completion bugs as RFC-0001 Phase F. Task 27 ships in
this entry; Tasks 23–26 are upcoming.

- `CHANGELOG.md` at repo root — fills the `docs/CHARTER.md:113`
  reference to "current project state" sources (Task 27, this PR).

### Added — Cross-cutting specs landed mid-flight

These surfaced during v2 task work and ship as living specs under
`docs/specs/`:

- [`journal-locking`](docs/specs/journal-locking/spec.md) — `fcntl.flock`
  serialization around journal append, `journal.transaction()`
  brackets, `wiki lock acquire|release`, doctor stale-lock check.
- [`journal-reader-cache`](docs/specs/journal-reader-cache/spec.md) —
  `JournalReader` cache for install-pipeline baseline lookups.
- [`safe-write-ordering`](docs/specs/safe-write-ordering/spec.md) —
  event-before-disk ordering and fast-path adoption; ADR-0004
  §Revisions.
- [`wheel-bundled-assets`](docs/specs/wheel-bundled-assets/spec.md) —
  ship template assets inside the wheel and thread `kit_root`
  through `cli.main` so `pipx install` works without a checkout.

### Added — Foundational ADRs (referenced above)

- [ADR-0001](docs/adr/0001-stdlib-rendering-not-jinja.md) — stdlib
  `str.format_map` for interpolation; byte-for-byte copy otherwise.
- [ADR-0002](docs/adr/0002-journal-as-state-truth.md) — single
  append-only JSONL is the vault state of truth.
- [ADR-0003](docs/adr/0003-managed-regions-for-shared-files.md) —
  `<!-- BEGIN MANAGED: id -->` markers for multi-primitive
  contributions to shared files.
- [ADR-0004](docs/adr/0004-drift-detection-and-proposal-flow.md) —
  every kit write goes through `safe_write`; drift produces a
  `.proposed` sidecar.
- [ADR-0005](docs/adr/0005-pydantic-for-disk-bound-schemas.md) —
  every type that crosses disk is a Pydantic v2 model.
- [ADR-0006](docs/adr/0006-additive-managed-region-contributions.md) —
  additive snippet aggregation in topological install order
  (surfaced by Task 11).
- [ADR-0007](docs/adr/0007-shared-infra-config-files-at-vault-root.md)
  — shared infra config files land at the vault root (surfaced by
  Task 18).

### Removed

- v1 sync scripts (`scripts/sync-shared.sh`, `scripts/check-sync.sh`)
  and the `.github/workflows/check-sync.yml` workflow that ran them.
  No v2 code path invokes them. (RFC-0001 §"Pre-flight" describes a
  broader v1-tree removal; the rest — `vault-templates/`, `shared/` —
  is unfinished cleanup tracked for Task 22's release-cut and is
  intentionally not claimed here.)
