# Spec: wiki-upgrade-force-render

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft
- **Owner:** `llm_wiki_kit/upgrade.py`, `llm_wiki_kit/cli.py:_cmd_upgrade`
- **Related:** [ADR-0008](../../adr/0008-init-adopt-ownership-policy.md)
  §6 (the drift-aware re-render semantics this spec pins);
  [`docs/specs/wiki-upgrade/spec.md`](../wiki-upgrade/spec.md) (the
  short-circuit this spec lifts behind a flag);
  [`docs/specs/wiki-init-adopt/spec.md`](../wiki-init-adopt/spec.md)
  (the `PageAdoptedEvent` / `ManagedRegionAdoptedEvent` baselines the
  re-render walks); ADR-0002 (journal as state truth); ADR-0004 (no
  silent overwrites on drift);
  [`docs/specs/safe-write-ordering/spec.md`](../safe-write-ordering/spec.md)
  (event-before-disk for every write the re-render emits);
  [`docs/specs/wiki-upgrade-force-render/plan.md`](plan.md);
  `docs/ROADMAP.md` §"Post-PR-C follow-ups" (the entry that names
  this gap).
- **Constrained by:** ADR-0008 §Decision sub-choice 3 (adopt-aware
  `safe_write` predicate — the re-render relies on it for its drift
  semantics and does not reimplement it); ADR-0004 (no silent
  overwrites of user-edited files); the wiki-upgrade spec's invariants
  (this spec adds one flag and one event class; everything else inside
  `upgrade.py` keeps shape); RFC-0001 §"Runtime constraints" (no new
  runtime deps without a new ADR); AGENTS.md §"Check before acting"
  (every vault write through `safe_write`; tests use `tmp_path` or
  fixture vaults).

## What this is

`wiki upgrade --force-render` re-renders the installed primitive
closure unconditionally — that is, regardless of whether any
installed primitive's `installed_version != catalog_version`. It
exists to close the partial-install recovery gap named in ADR-0008 §6
and `wiki-init-adopt`'s spec §Edge cases: when a crash inside the
install pipeline (after one or more `PrimitiveInstallEvent`s land)
leaves a vault with some adopt baselines journaled but the
corresponding files unwritten, today's `wiki upgrade` short-circuits
on the matching-version no-op and the user has no productive
automated recovery beyond a destructive `rm -rf .wiki.journal`.

The flag lifts `plan_upgrade`'s matching-version short-circuit
behind an explicit opt-in. The runner then re-walks every installed
primitive's `files/` tree through `render_tree` and runs the
managed-region aggregator over `plan.all_installed` — the same two
passes `wiki upgrade` already uses on a version bump. The drift
surface is whatever the existing adopt-aware `safe_write` /
`safe_write_region` predicates produce (ADR-0008 §Decision sub-choice
3): byte-identical files against the journaled baseline take the
no-rewrite branch; differing-content files land as `.proposed`
sidecars. **The flag does not bypass drift detection. It only lifts
the planner's no-op short-circuit.**

`--force-render` is a recovery tool. It refuses to enter the runner
when the vault is clean — that is, when `doctor.check_missing` and
`doctor.check_managed_region_drift` both report empty issue lists.
This makes the scope guard load-bearing: the flag's job is to close
the partial-install gap, not to re-render an already-complete vault.
Idempotence — running `--force-render` twice in a row is a no-op on
the second invocation — emerges structurally from this guard: the
first invocation heals the gap, the second sees a clean vault and
short-circuits.

## Inputs

CLI invocation: `wiki upgrade --force-render [--primitive <name>]`.

- `--force-render` — required for this surface. A boolean flag whose
  only effect is to flip `plan_upgrade`'s matching-version
  short-circuit and toggle the runner to emit
  `PrimitiveForceRenderEvent` rather than `PrimitiveUpgradeEvent`
  (since there is no version transition to record).
- `--primitive <name>` — optional, unchanged from `wiki upgrade`. When
  given, restricts the re-render to that one installed primitive's
  `files/` tree. The aggregator still runs over
  `plan.all_installed` (the existing wiki-upgrade invariant — see
  wiki-upgrade spec §Invariants bullet 5).
- Vault root: `Path.cwd().resolve()`. Same boundary checks
  `wiki upgrade` performs (vault journal present, contains
  `VaultInitEvent`, recipe loadable, kit catalog resolvable).

Pre-conditions checked at the CLI boundary, in this order, are
identical to `wiki upgrade`'s except for one addition: AFTER state
load + catalog resolve, AND BEFORE entering the runner, the CLI
calls `doctor.check_missing(state, vault_root)` and
`doctor.check_managed_region_drift(state, vault_root)`. If both
return empty issue lists, the runner is short-circuited (see
§Behavior "Happy path — clean vault").

## Outputs

### Journal events

- **`PrimitiveForceRenderEvent`** — new event class.
  - Payload: `primitive: str`, `version: str` (the installed
    version, unchanged across the run), `by: Literal["wiki-upgrade"]
    = "wiki-upgrade"`.
  - Discriminator: `type: Literal["primitive.force_render"] =
    "primitive.force_render"`.
  - One event per primitive in `plan.to_upgrade` (which, for
    `--force-render`, equals `plan.all_installed` filtered to the
    `--primitive <name>` target when set, else the full set).
  - Appended *before* any `safe_write` for that primitive's
    `files/` tree (event-before-disk; same ordering invariant
    `PrimitiveUpgradeEvent` satisfies).
- **`PageWriteEvent` / `PageProposalEvent`** — emitted per file the
  renderer touches. No new event class. The adopt-aware
  `safe_write` predicate (ADR-0008 §Decision sub-choice 3) routes
  each write through one of:
  - **No-rewrite** when `new_hash == baseline_hash == on_disk_hash`
    against either a `PageWriteEvent` or `PageAdoptedEvent`
    baseline: one fresh `PageWriteEvent` (consistent with
    `wiki upgrade`'s existing
    `test_no_op_write_of_identical_content_still_records_event`
    contract); the file's bytes and inode are preserved.
  - **Proposal** when the kit's new content differs from the
    baseline: `.proposed` sidecar lands, original file untouched,
    `PageProposalEvent` journaled. Drift line goes to stdout.
- **`ManagedRegionWriteEvent` / `PageProposalEvent`** — emitted by
  `aggregate_region_contributions` over `plan.all_installed`. Same
  shape `wiki upgrade` produces today. `by="wiki-upgrade"`.
- **No `PrimitiveUpgradeEvent`.** A force-render is not a version
  transition; emitting `PrimitiveUpgradeEvent(from_version=X,
  to_version=X)` would muddle the audit story for grep
  (`primitive.upgrade` rows would mix actual catalog bumps with
  re-renders). `PrimitiveForceRenderEvent` is the grep-able
  discriminator for "we walked the closure to heal the partial
  install."

### Stdout

- One `force-rendered <primitive> @ <version>` line per primitive in
  `plan.to_upgrade` (mirrors `wiki upgrade`'s `upgraded <name> <from>
  → <to>` shape).
- One `Wrote <path>.proposed (drift detected on <path>); run the
  wiki-conflict skill to merge.` line per `.proposed` sidecar
  produced during the run (matches `wiki upgrade`'s existing line).
- Totals:
  - When at least one primitive was force-rendered:
    `wiki upgrade --force-render: re-rendered N primitive.` for
    `N == 1`; `... N primitives.` otherwise.
  - When the runner was short-circuited (vault clean — see
    Behavior):
    `wiki upgrade --force-render: no recovery needed (vault is
    clean).`

### Stderr

Boundary errors only (same `WikiError` surface `wiki upgrade` uses),
plus one new shape:

- **`--force-render` combined with a `--primitive <name>` whose
  catalog version differs from the installed version.** Refuse with
  `WikiError("--force-render conflicts with a pending upgrade for
  '<name>' (catalog ships <V_catalog>, installed at <V_installed>);
  run 'wiki upgrade --primitive <name>' first")`. Exit 2.
  Rationale: forcing a re-render at the OLD version when the kit
  ships a NEW version is almost never what the user means; gate the
  combination behind an explicit two-step.

The existing "one installed primitive missing from catalog" stderr
hint is unchanged.

## Behavior

### Happy path — partial install (the recovery case)

1. CLI boundary checks identical to `wiki upgrade` (vault present,
   `VaultInitEvent` present, recipe loadable, catalog resolvable,
   `--primitive` shape valid).
2. State load: `state = replay_state(read_events(journal_path))`.
3. Catalog resolve (`core` + `discover_primitives(templates_dir)`).
4. **Conflict check.** When `args.primitive` is set, compare the
   catalog version to `state.installed_primitives[args.primitive]`
   and refuse with the "conflicts with a pending upgrade" message if
   they differ (see §Outputs Stderr).
5. **Scope guard.** Call `doctor.check_missing(state, vault_root)`
   and `doctor.check_managed_region_drift(state, vault_root)`. When
   both return empty issue lists, take the clean-vault branch
   (§"Happy path — clean vault"). Otherwise proceed.
6. `validate_contributions` runs over `plan.all_installed`. Same
   widened pre-flight `wiki upgrade` performs (wiki-upgrade spec
   §Invariants bullet 8). Failure exits 2 before any event lands.
7. `plan = plan_upgrade(state, catalog, only=args.primitive,
   force_render=True)`. The new `force_render=True` argument
   bypasses the matching-version short-circuit: `to_upgrade =
   plan.all_installed` (when `args.primitive` is unset) or
   `[catalog_by_name[args.primitive]]` (when set).
8. Inside `journal.use_journal_cache(journal_path)`:
   1. For each primitive `p` in `plan.to_upgrade`:
      1. `append_event(journal_path,
         PrimitiveForceRenderEvent(timestamp=now, by="wiki-upgrade",
         primitive=p.name, version=p.version))`.
      2. `render_tree(sources[p.name] / "files", vault_root, context,
         journal_path, by=p.name)` — writes route through
         `safe_write` and the adopt-aware predicate produces the
         drift surface ADR-0008 §Decision sub-choice 3 names.
   2. `aggregate_region_contributions(plan.all_installed, sources,
      journal_path, by="wiki-upgrade")` — same aggregator
      `wiki upgrade` uses.
   3. `write_outcome_slash_stubs(primitives=plan.all_installed, ...)`
      — same call `wiki upgrade` makes (the outcome-named-entry-
      points spec's idempotent stub refresh is needed for
      force-render too; a partial install can leave the stubs
      missing on disk).
9. Print one `force-rendered <name> @ <version>` per primitive in
   `to_upgrade`, one drift line per `PageProposalEvent` collected
   from the new-events slice, then the totals row. Return 0.

### Happy path — clean vault

When step 5's diagnostic checks both report empty issue lists, the
CLI short-circuits BEFORE entering the runner:

1. Print `wiki upgrade --force-render: no recovery needed (vault is
   clean).` on stdout.
2. Append zero journal events. Touch zero files.
3. Return 0.

This is the structural source of the idempotence guarantee
(§Acceptance criteria AC4 below).

### Happy path — `--force-render --primitive <name>`

Same as the partial-install path, with two differences:

- The conflict check in step 4 fires if the catalog and installed
  versions differ; user resolves with `wiki upgrade --primitive
  <name>` first.
- Step 7's plan restricts `to_upgrade` to `[catalog_by_name[name]]`.
  The aggregator still runs over `plan.all_installed` (existing
  invariant).
- Step 5's scope guard still applies: if the diagnostic check
  reports no `missing` or `managed-region-drift` issues, short-
  circuit with `no recovery needed`. A user who knows one primitive
  is partially-rendered but `wiki doctor` reports clean has a kit
  bug to file — not a `--force-render` invocation to make.

### Edge cases

- **`--force-render` on a vault initialized without `--adopt`** (no
  `PageAdoptedEvent`s, only `PageWriteEvent`s). Proceeds normally —
  the adopt-aware predicate degrades to the standard
  `PageWriteEvent`-only path (ADR-0008 §Decision sub-choice 3
  reduces to the existing direct-write / proposal disjuncts when
  no adopt baselines are present). Use case is rare (a non-adopt
  init that crashed mid-install pipeline) but the predicate handles
  it without special-casing.
- **`--force-render` re-emits region contributions from
  unchanged-version primitives.** Expected. The aggregator pass over
  `plan.all_installed` is what makes multi-contributor regions
  survive (wiki-upgrade spec §Invariants bullet 5 / Task-12 footgun
  callout).
- **`--force-render` against a fully-rendered, fully-healthy vault.**
  Short-circuits per §Happy path — clean vault.
- **`--force-render` against a vault where ONLY pending-proposal
  issues exist** (no `missing`, no `managed-region-drift`). The
  scope guard short-circuits — pending proposals are the user's
  to merge via `wiki-conflict`, not the re-render's. A user who
  wants to force-render anyway resolves the proposals first, which
  clears the sidecars; if the vault is now also missing files (a
  separate gap), force-render proceeds.
- **`--force-render` produces drift on a file that was clean on
  disk before the run.** Impossible by construction of the adopt-
  aware predicate: a file whose `on_disk_hash == baseline_hash`
  takes the no-rewrite branch. If the user's bytes drifted between
  the diagnostic check (step 5) and the renderer's write attempt
  (step 8), `safe_write` produces a `.proposed` sidecar (the
  standard TOCTOU outcome ADR-0004 already pins). The journal
  records the proposal honestly.
- **`--force-render` invoked outside a vault.** Same `not a wiki
  vault` exit 2 as `wiki upgrade`.
- **`--force-render` combined with `--primitive` for an
  uninstalled primitive name.** Same `primitive '<name>' is not
  installed` error `wiki upgrade --primitive` raises.
- **Crash mid-`--force-render`.** Locally durable in the same way
  `wiki upgrade` is durable mid-run: prior primitives' force-render
  events + their renders are journaled and on disk; the raising
  primitive's `PrimitiveForceRenderEvent` is durable
  (event-before-disk); later primitives are skipped; the
  aggregator pass does not run. Re-running `wiki upgrade
  --force-render` re-enters at step 5 — the scope guard still
  reports issues (the run wasn't complete), so the runner re-walks
  the closure, idempotently re-baselining via the adopt-aware
  predicate.
- **`--force-render` on a vault whose journal has zero installed
  primitives** (degenerate — `state.installed_primitives == {}`).
  `plan.to_upgrade` is empty; the runner is not entered; the CLI
  prints `wiki upgrade --force-render: no recovery needed (vault
  is clean).` (the scope guard short-circuits before reaching the
  empty-plan check, since `check_missing` finds no journaled
  paths and reports empty). Returns 0.

### Error cases

- `not a wiki vault: ...` — exit 2 (same as `wiki upgrade`).
- `vault at <root> has no vault.init event; ...` — exit 2.
- `--primitive must be a bare primitive name, not <kind>:<name>` —
  exit 2.
- `primitive '<name>' is not installed; ...` — exit 2.
- `--force-render conflicts with a pending upgrade for '<name>'
  (catalog ships <V_catalog>, installed at <V_installed>); run
  'wiki upgrade --primitive <name>' first` — exit 2. The new error
  shape this spec adds.
- `PrimitiveError` from `validate_contributions` propagates as
  `WikiError`; exit 2.
- `RecipeError` from `load_recipe` propagates; exit 2.

## Invariants

1. **Every vault write goes through `safe_write` or
   `safe_write_region`.** No new write path. The renderer + aggregator
   are the only modules that touch disk; both already route through
   the safe-write helpers. `--force-render` adds no exception.
2. **Event-before-disk holds.** Every `PrimitiveForceRenderEvent` is
   appended and `fsync`'d before the corresponding `render_tree` call
   opens any file. The downstream `PageWriteEvent` /
   `PageProposalEvent` / `ManagedRegionWriteEvent` ordering is
   preserved by the safe-write helpers themselves.
3. **No silent overwrites of user-edited files.** ADR-0004's drift
   contract is unchanged. `--force-render` does not bypass it — the
   adopt-aware predicate (ADR-0008 §Decision sub-choice 3) is the
   sole arbiter of "rewrite vs. propose."
4. **The scope guard refuses on clean vaults.** When
   `doctor.check_missing` and `doctor.check_managed_region_drift`
   both return empty issue lists, the runner is not entered, zero
   events are appended, the CLI prints `no recovery needed (vault is
   clean).` and returns 0. This is structural (the CLI short-circuit,
   not a runner-internal early-return).
5. **Idempotence via the scope guard.** Two consecutive `wiki upgrade
   --force-render` invocations produce zero new events on the second
   invocation: the first invocation heals the partial install, the
   second sees a clean vault, the scope guard short-circuits.
6. **`by` attribution.** `PrimitiveForceRenderEvent.by ==
   "wiki-upgrade"`. Per-primitive `PageWriteEvent.by == <primitive
   name>`. `ManagedRegionWriteEvent.by == "wiki-upgrade"`. Matches
   `wiki upgrade`'s attribution; the CLI vehicle string does not
   distinguish version-bump upgrades from force-renders — the event
   class discriminator does.
7. **Pre-flight validates every contributing primitive.**
   `validate_contributions` runs over `plan.all_installed` before any
   `PrimitiveForceRenderEvent` is appended (same widened scope
   `wiki upgrade` uses per its §Invariants bullet 8).
8. **No new module boundary.** `--force-render` extends
   `plan_upgrade` (one new keyword arg) and `upgrade_primitives`
   (one new keyword arg + the
   `PrimitiveForceRenderEvent`-vs-`PrimitiveUpgradeEvent` branch);
   the CLI handler `_cmd_upgrade` gains one new `argparse` flag and
   one new pre-flight call (`doctor.check_missing` +
   `doctor.check_managed_region_drift`). No new file under
   `llm_wiki_kit/`.
9. **No `--force-render` without an explicit user invocation.** The
   flag is never auto-set by another code path (e.g., `wiki upgrade`
   on a missing file does NOT silently engage force-render). A user
   who wants the recovery surface types the flag.

## Contracts with other modules

- **`llm_wiki_kit.cli`** — `_cmd_upgrade` gains:
  - one new `argparse` flag (`--force-render`, `action="store_true"`),
  - one new pre-flight call sequence (the scope guard:
    `doctor.check_missing(state, vault_root)` +
    `doctor.check_managed_region_drift(state, vault_root)`; short-
    circuit when both lists are empty),
  - one new conflict-check branch (the `--primitive` + version-
    mismatch refusal),
  - threading of `force_render=args.force_render` into
    `plan_upgrade` and `upgrade_primitives`.

  Stdout / stderr line shapes are listed in §Outputs.
- **`llm_wiki_kit.upgrade`** — public surface gains one keyword arg
  on each entry point:
  - `plan_upgrade(state, catalog, *, only, force_render=False) ->
    UpgradePlan` — when `force_render=True`, the matching-version
    short-circuit is lifted: `to_upgrade = all_installed` (or
    `[catalog_by_name[only]]` when `only` is set), and
    `no_op_target` is always `None` (the louder no-op message is
    not used in the force-render path; the scope guard handles the
    clean-vault case at the CLI layer).
  - `upgrade_primitives(*, plan, sources, journal_path, context,
    state_versions, now, force_render=False) -> list[tuple[str,
    str]]` — when `force_render=True`, the per-primitive event
    append is `PrimitiveForceRenderEvent(primitive=p.name,
    version=state_versions[p.name])` instead of
    `PrimitiveUpgradeEvent(from_version=..., to_version=...)`. The
    rest of the runner (render loop, aggregator pass, outcome stub
    refresh, proposal collection) is unchanged.
- **`llm_wiki_kit.models`** — adds `PrimitiveForceRenderEvent` to the
  discriminated `Event` union. `VaultState` is unchanged (no new
  replay field — force-render does not seed baselines and does not
  participate in the `installed_primitives` map; it is an audit row
  only).
- **`llm_wiki_kit.doctor`** — `check_missing` and
  `check_managed_region_drift` are imported by `_cmd_upgrade` and
  called as predicates (their return values are inspected for
  emptiness; the CLI does not render them as doctor would). No
  change to either function's signature.
- **`llm_wiki_kit.install`** — `validate_contributions`,
  `aggregate_region_contributions`, `write_outcome_slash_stubs`, and
  `_warn_if_install_pipeline_uncached` are reused unchanged.
- **`llm_wiki_kit.render`** — `render_tree` is reused unchanged.
- **`llm_wiki_kit.write_helper`** — `safe_write` and
  `safe_write_region` are reused unchanged; the adopt-aware predicate
  added by `wiki-init-adopt`'s PR-B is the sole arbiter of drift
  outcomes for the re-render.
- **`llm_wiki_kit.journal`** — `append_event` and
  `use_journal_cache` are reused unchanged. `replay_state` gains one
  no-op dispatch branch for the new event class (the event is purely
  audit; it does not mutate `VaultState`).
- **`llm_wiki_kit.errors.WikiError`** — re-used; no new exception
  type.

## Acceptance criteria

- [ ] **AC1 — Clean vault short-circuits.** Against a vault where
  `doctor.check_missing` and `doctor.check_managed_region_drift` both
  return `[]`, `wiki upgrade --force-render` exits 0 with zero new
  journal events; stdout contains `wiki upgrade --force-render: no
  recovery needed (vault is clean).`
- [ ] **AC2 — Partial-install recovery heals the missing-files gap.**
  Construct a fixture vault by initializing with `--adopt`, then
  truncating the journal mid-render so half the primitive closure's
  `PrimitiveInstallEvent` rows are journaled but the corresponding
  rendered files are absent on disk. Run `wiki upgrade
  --force-render`. Assert: (a) every missing kit-owned file is now
  on disk; (b) the journal contains one `PrimitiveForceRenderEvent`
  per primitive in the closure; (c) byte-identical adopted files
  remained byte-identical (adopt-match no-rewrite branch fired);
  (d) byte-differing adopted files surfaced as `.proposed` sidecars
  (adopt-differ proposal branch fired); (e) `wiki doctor` post-run
  reports zero `missing` and zero `managed-region-drift` issues
  (only `pending-proposal` remains for the differing files).
- [ ] **AC3 — Drift on a force-rendered file produces a `.proposed`
  sidecar, never a silent overwrite.** Construct a vault with a
  `PageAdoptedEvent(hash=h_user)` baseline and a kit-would-render
  whose hash differs from `h_user`. Pre-place a file with bytes
  hashing to `h_user`. Run `wiki upgrade --force-render`. Assert:
  (a) the original file is byte-identical to its pre-call content;
  (b) a `<path>.proposed` sidecar exists with the kit's would-render
  content; (c) the journal contains a `PageProposalEvent` for the
  path; (d) stdout printed the drift line.
- [ ] **AC4 — `--force-render` is idempotent across two consecutive
  invocations.** After AC2's scenario completes, run `wiki upgrade
  --force-render` a second time. Assert: zero new journal events,
  exit 0, stdout contains `no recovery needed (vault is clean).`,
  every `.proposed` sidecar from the first invocation is still on
  disk untouched (the second invocation does not re-render and does
  not re-propose).
- [ ] **AC5 — `--force-render --primitive <name>` restricts the
  re-render scope.** Construct a fixture with two primitives both
  partially rendered. Run `wiki upgrade --force-render --primitive
  people`. Assert: (a) exactly one `PrimitiveForceRenderEvent` for
  `people`, none for any other primitive; (b) the aggregator still
  ran over `plan.all_installed` (managed-region contributions from
  every installed primitive survive into the composed region body);
  (c) the other primitive's missing files are still missing (the
  scope guard's clean-vault check is computed AT THE START — it does
  not re-run after `--primitive`'s narrow render).
- [ ] **AC6 — `--force-render` refuses when a `--primitive` target
  has a pending catalog version bump.** Construct a vault where
  `state.installed_primitives["core"] == "0.1.0"` and the catalog
  ships `core@0.2.0`. Run `wiki upgrade --force-render --primitive
  core`. Assert exit 2, stderr contains `--force-render conflicts
  with a pending upgrade for 'core'`, zero new journal events.
- [ ] **AC7 — `--force-render` against a vault initialized without
  `--adopt`** (no `PageAdoptedEvent`s, partial install). Construct a
  fixture by truncating a non-adopt-initialized vault's journal
  mid-`PrimitiveInstallEvent`. Run `wiki upgrade --force-render`.
  Assert: (a) missing files are written; (b) zero
  `PageProposalEvent`s (no adopt baselines to disagree with;
  `safe_write`'s standard direct-write branch fires); (c) `wiki
  doctor` reports clean post-run.
- [ ] **AC8 — `PrimitiveForceRenderEvent` round-trips through
  Pydantic with stable JSON; the discriminated `Event` union
  dispatches the row through `read_events`.**
- [ ] **AC9 — `replay_state` populates no new field for
  `PrimitiveForceRenderEvent`.** Pin: a journal containing a
  `PrimitiveForceRenderEvent` replays to a `VaultState` whose
  `installed_primitives` and other fields are unchanged from the
  state computed by replaying the same journal with the
  force-render row removed. The event is audit-only.
- [ ] **AC10 — Aggregator pass runs after per-primitive force
  renders.** Mirrors `wiki upgrade`'s AC9: every
  `ManagedRegionWriteEvent` index in the new-events slice is greater
  than every per-primitive `PageWriteEvent` /
  `PageProposalEvent` index.
- [ ] **AC11 — `by` attribution.**
  `PrimitiveForceRenderEvent.by == "wiki-upgrade"`. Per-primitive
  `PageWriteEvent.by == <primitive name>`.
  `ManagedRegionWriteEvent.by == "wiki-upgrade"`.
- [ ] **AC12 — Event ordering: force-render event before its
  primitive's renders.** Within the slice for any one primitive `p`
  in `to_upgrade`, the `PrimitiveForceRenderEvent(primitive=p.name)`
  index is less than every `PageWriteEvent.by == p.name` and
  `PageProposalEvent` index for paths under `p`'s `files/` tree.
- [ ] **AC13 — `--force-render` runs inside
  `journal.use_journal_cache(journal_path)`** (same qC4 contract
  every install vehicle observes). A counting monkeypatch on
  `journal.read_events` observes the same one-cache-load shape
  `wiki upgrade` already pins.
- [ ] **AC14 — Outside a vault, exits 2 with `not a wiki vault` on
  stderr; no journal events anywhere.**
- [ ] **AC15 — `wiki doctor` after a successful force-render reports
  no `missing` or `managed-region-drift` issues** (only
  `pending-proposal` and `orphan`, as the pre-existing user content
  warrants).
- [ ] **AC16 — Scope guard scoping: `pending-proposal` alone does
  NOT trigger the runner.** Construct a vault with one
  `PageProposalEvent` (a `.proposed` sidecar present) but no
  `missing` and no `managed-region-drift` issues. Run `wiki upgrade
  --force-render`. Assert: short-circuit fires; stdout contains `no
  recovery needed (vault is clean).`; zero new events; the sidecar
  is still on disk.
- [ ] **AC17 — `validate_contributions` is pre-flighted over
  `all_installed`.** Pin: when an unchanged-version primitive's
  contribution shape becomes invalid in the kit, `wiki upgrade
  --force-render` exits with `PrimitiveError` and zero new
  `PrimitiveForceRenderEvent`s are appended.

## Non-goals

- **Not a general "wipe and reinstall."** `--force-render` does not
  delete files, does not reset baselines, does not bypass the
  drift-detection predicate. A vault whose user edited a kit-owned
  file (post-adopt drift) gets a `.proposed` sidecar from
  `--force-render`, exactly as it would from a catalog-bump
  `wiki upgrade`. Users who want a clean-slate reinstall remove the
  vault directory and run `wiki init`.
- **Not a way to bypass drift detection in non-recovery scenarios.**
  `safe_write`'s adopt-aware predicate (ADR-0008 §Decision
  sub-choice 3) is the sole arbiter of "rewrite vs. propose."
  `--force-render` does not pass any override or hint into the
  predicate. ADR-0004's "no silent overwrites of user-edited files"
  invariant is preserved end-to-end. A user who wants to "win" a
  drift conflict resolves the resulting `.proposed` sidecar via
  `wiki-conflict`; the flag does not give them a shortcut.
- **Not a `--force-render` for a single file.** The flag operates on
  the primitive closure (`--primitive <name>` narrows to one
  primitive's `files/` tree + the full aggregator pass). A per-file
  recovery surface would duplicate `wiki-conflict`'s resolve flow
  for a marginal use case.
- **Not a replacement for `wiki upgrade` on catalog bumps.** When the
  catalog ships a newer version, the user runs `wiki upgrade`
  (without `--force-render`) and gets `PrimitiveUpgradeEvent`s
  recording the transition. `--force-render` is for the
  same-version recovery case.
- **Not an auto-recovery hook.** `wiki doctor` does not silently
  invoke `--force-render` when it sees `missing` issues. The flag is
  an explicit user opt-in; the diagnostic remains the diagnostic.
- **No `--dry-run`.** A preview would duplicate the
  `plan_upgrade(force_render=True)` data; the user can already
  predict the closure by reading `state.installed_primitives` and
  the catalog. Add later if real demand surfaces.
- **No new schedule-installable agent.** `--force-render` is a
  user-invoked recovery tool. Wiring it into `wiki schedule install`
  would auto-recover vaults without consent — out of scope.
- **No suppression of `PageWriteEvent` on byte-match.** The kit's
  established `safe_write` contract
  (`test_no_op_write_of_identical_content_still_records_event`)
  records every write attempt the runner makes. Force-render
  inherits the convention.

## Constraints

- **No new module under `llm_wiki_kit/`.** The flag extends
  `upgrade.py` and `cli.py` only. The new event class lands in
  `models.py` (existing module).
- **No new runtime dependency.** Stdlib + `pyyaml` + `pydantic`.
- **No new top-level CLI verb.** The flag is a subordinate option on
  the existing `wiki upgrade` parser.
- **No new event field on `PageWriteEvent` /
  `ManagedRegionWriteEvent`** (e.g., no `reason: Literal["upgrade",
  "force_render"]`). The audit discriminator is the marker event
  (`PrimitiveForceRenderEvent`), consistent with the kit's
  one-class-per-event convention (ADR-0005, ADR-0008 §Decision
  sub-choice 4).
- **No bypass of `safe_write` / `safe_write_region`.** The runner
  reuses `render_tree` and `aggregate_region_contributions`
  unchanged.
- **No new `wiki doctor` check.** The scope guard reuses
  `check_missing` and `check_managed_region_drift` verbatim.
- **No vault-side SKILL.** Force-render is kit-side recovery;
  vault-side workflow uses the existing `wiki-conflict` skill for
  any sidecars the run produces.
- **No structural refactor of `upgrade.py`.** The change is two
  keyword args + one new branch (the event-class swap). The runner's
  control flow, journal-slice collection, and aggregator call site
  are unchanged.
