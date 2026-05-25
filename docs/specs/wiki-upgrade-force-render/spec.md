# Spec: wiki-upgrade-force-render

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Implemented
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
  fixture vaults); `wiki-init-adopt` spec §Edge cases "Crash inside
  the install pipeline" (the deferred recovery path this spec
  delivers — a corrigendum to that spec's `check_missing` overclaim
  lands in the same PR).

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
when the vault's installed-primitive closure is fully present on
disk — that is, when no path that `enumerate_rendered_paths(
installed_primitives, sources)` would produce is absent from
`vault_root`, AND `doctor.check_managed_region_drift` reports no
on-disk divergence. This makes the scope guard load-bearing: the
flag's job is to close the partial-install gap, not to re-render an
already-complete vault. Idempotence — running `--force-render` twice
in a row is a no-op on the second invocation — emerges structurally
from this guard: the first invocation writes every closure path,
the second sees a complete closure and short-circuits.

**Why not `doctor.check_missing`?** `check_missing` walks
`state.page_writes` only (see `doctor.py:281-288`). The exact
failure mode this spec exists to recover — a crash mid-render
where `PrimitiveInstallEvent` is durable but `PageWriteEvent` for
the un-reached paths was never appended — leaves those paths
outside `state.page_writes`, so `check_missing` returns `[]`
exactly when the runner is most needed. The wiki-init-adopt spec
§Edge cases "Crash inside the install pipeline" overclaimed this
surface (it said `wiki doctor` reports `missing` for "any kit-owned
path the renderer didn't reach"); the doc-sweep step in the plan
corrects that overclaim. The scope guard here uses a stricter
closure-presence predicate (defined in §Contracts below as
`_unrendered_closure_paths`) that derives the expected path set
from `state.installed_primitives × enumerate_rendered_paths` and
asserts file presence on disk — catching the journal-vs-disk gap
`check_missing` cannot see.

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
computes `_unrendered_closure_paths(state, vault_root, catalog,
sources)` (defined in §Contracts) and calls
`doctor.check_managed_region_drift(events, vault_root, state)`. If
both return empty lists, the runner is short-circuited (see
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
- **Per-file attribution to a force-render run.** Per-file events
  (`PageWriteEvent`, `PageProposalEvent`,
  `ManagedRegionWriteEvent`) emitted during force-render carry
  the same `by` they carry for a regular `wiki upgrade` run
  (`<primitive name>` for page writes, `"wiki-upgrade"` for the
  aggregator), so a single per-file event cannot be attributed
  to "this force-render run" by `by` alone. The audit interface
  is a pair of journal-index bracket queries:
  - **Page-scope events** (`PageWriteEvent`, OR `PageProposalEvent`
    whose `event.by != "wiki-upgrade"` — i.e. attributed to a
    primitive name by the renderer): attributable to the
    `PrimitiveForceRenderEvent` whose `primitive` equals the
    per-file event's `by` field AND is the most recent
    `Primitive*Event` for that primitive at a lower index.
  - **Region-scope events** (`ManagedRegionWriteEvent`, OR
    `PageProposalEvent` whose `event.by == "wiki-upgrade"` —
    i.e. attributed to the install vehicle by the aggregator):
    the aggregator runs once per force-render run, so these are
    attributed by *index position alone* — every aggregator-
    attributed event in the slice `[k, end_of_run)` where `k` is
    the LAST `PrimitiveForceRenderEvent` index in the run
    belongs to that run. No per-primitive bracket applies
    (region events have no primitive field; multi-contributor
    host files have no single owning primitive).

  The `by`-based partition is reliable: per-primitive renders
  always attribute to a primitive name (`render.py:166`); the
  aggregator always attributes to `"wiki-upgrade"`
  (`install.py:295-301` callers, this spec's
  §Contracts.upgrade_primitives). Path-based discrimination
  would misclassify a host file shipped in BOTH a primitive's
  `files/` tree AND `contributes_to` (a legal shape per
  `adopt.py:171`'s union).

  AC19 pins both queries; a future `wiki journal grep
  --force-render` UX can consume them without payload changes.

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
  - When the runner was short-circuited (closure complete — see
    Behavior):
    `wiki upgrade --force-render: no recovery needed (closure is
    complete).`

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
5. **Scope guard.** Compute
   `unrendered = _unrendered_closure_paths(state, vault_root,
   catalog, sources)` (§Contracts) and `region_drift =
   doctor.check_managed_region_drift(events, vault_root, state)`.
   When both are empty, take the clean-closure branch
   (§"Happy path — clean closure"). Otherwise proceed.
6. `validate_contributions` runs over `plan.all_installed`. Same
   widened pre-flight `wiki upgrade` performs (wiki-upgrade spec
   §Invariants bullet 8). Failure exits 2 before any event lands.
   This pre-flight runs AFTER the scope guard so a clean-closure
   invocation does not pay its cost; AC17 below pins its
   reachability under a non-clean closure.
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

### Happy path — clean closure

When step 5's `unrendered` and `region_drift` lists are both empty,
the CLI short-circuits BEFORE entering the runner:

1. Print `wiki upgrade --force-render: no recovery needed (closure
   is complete).` on stdout.
2. Append zero journal events. Touch zero files.
3. Return 0.

When `state.installed_primitives == {}` (degenerate — a vault with
`VaultInitEvent` but no installed primitives), additionally print
on stderr: `note: this vault has no installed primitives; if init
was interrupted, run 'wiki init --adopt' to resume.` and still
return 0 — `--force-render` is the wrong tool for the
init-in-progress recovery slot.

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
- Step 5's scope guard still applies: if `_unrendered_closure_paths`
  and `check_managed_region_drift` both report empty, short-
  circuit with `no recovery needed (closure is complete)`. A user
  who believes one primitive is partially-rendered but the scope
  guard reports clean should re-derive the diagnostic by hand
  (compare `enumerate_rendered_paths` against vault contents);
  a divergence between the user's belief and the predicate is
  either a stale belief or a predicate bug — neither of which a
  re-render papers over.

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
  Short-circuits per §Happy path — clean closure.
- **`--force-render` against a vault where ONLY pending-proposal
  sidecars exist** (closure complete, no `managed-region-drift`).
  The scope guard short-circuits — pending proposals are the user's
  to merge via `wiki-conflict`, not the re-render's. A user who
  wants to force-render anyway resolves the proposals first, which
  clears the sidecars; if the vault is now also missing closure
  paths (a separate gap), force-render proceeds.
- **`--force-render` produces drift on a file that was clean on
  disk before the run.** Impossible by construction of the adopt-
  aware predicate: a file whose `on_disk_hash == baseline_hash`
  takes the no-rewrite branch. If the user's bytes drifted between
  the scope-guard probe (step 5) and the renderer's write attempt
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
  --force-render` re-enters at step 5 — `_unrendered_closure_paths`
  still reports non-empty (the un-walked primitive's `files/` tree
  still has missing closure paths), so the runner re-walks the
  closure, idempotently re-baselining via the adopt-aware
  predicate.
- **`--force-render` on a vault whose journal has zero installed
  primitives** (degenerate — `state.installed_primitives == {}`).
  `_unrendered_closure_paths` returns `[]` (no installed primitives
  ⇒ empty closure ⇒ nothing missing) and the scope guard fires.
  The CLI prints the `no recovery needed` line on stdout plus the
  init-in-progress hint on stderr (see §Happy path — clean
  closure). Returns 0.

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
4. **The scope guard refuses on a complete closure.** When
   `_unrendered_closure_paths` returns `[]` AND
   `doctor.check_managed_region_drift` returns `[]`, the runner is
   not entered, zero events are appended, zero files are touched
   (no `.proposed` sidecars created, no journal mtime change), the
   CLI prints `no recovery needed (closure is complete).` and
   returns 0. This is structural (the CLI short-circuit, not a
   runner-internal early-return). The scope guard runs BEFORE
   `validate_contributions` so a clean-closure invocation does not
   pay the pre-flight cost.
5. **Idempotence via the scope guard.** Two consecutive `wiki upgrade
   --force-render` invocations produce a journal whose
   `read_events(journal_path)` returns a list value-equal to the
   list returned after the first invocation: the first invocation
   walks the closure and writes every missing path (clearing
   `_unrendered_closure_paths`), the second sees a complete closure
   and short-circuits with zero new events. This is the byte-
   equivalent form `wiki upgrade` AC7 already pins (see
   `tests/integration/test_wiki_upgrade.py`'s idempotence test).
6. **`by` attribution.** `PrimitiveForceRenderEvent.by ==
   "wiki-upgrade"`. Per-primitive `PageWriteEvent.by == <primitive
   name>`. `ManagedRegionWriteEvent.by == "wiki-upgrade"`. Matches
   `wiki upgrade`'s attribution; the CLI vehicle string does not
   distinguish version-bump upgrades from force-renders — the event
   class discriminator does.
7. **Pre-flight validates every contributing primitive when the
   runner is entered.** When the scope guard does NOT short-
   circuit (i.e., when `_unrendered_closure_paths` or
   `check_managed_region_drift` is non-empty),
   `validate_contributions` runs over `plan.all_installed` before
   any `PrimitiveForceRenderEvent` is appended (same widened
   scope `wiki upgrade` uses per its §Invariants bullet 8). When
   the scope guard short-circuits, pre-flight does NOT run — AC1
   pins this carve-out. The invariant's "before any
   `PrimitiveForceRenderEvent` is appended" wording is vacuously
   true under short-circuit (no events appended at all), but the
   explicit carve-out exists so a future maintainer doesn't
   reorganise the CLI handler in a way that drops the
   no-pre-flight-cost-on-clean-closure guarantee.
8. **No new module boundary.** `--force-render` extends
   `plan_upgrade` (one new keyword arg) and `upgrade_primitives`
   (one new keyword arg + the
   `PrimitiveForceRenderEvent`-vs-`PrimitiveUpgradeEvent` branch);
   the CLI handler `_cmd_upgrade` gains one new `argparse` flag,
   one new helper (`_unrendered_closure_paths`, co-located with
   `_cmd_upgrade` in `cli.py`; not lifted into `doctor.py` because
   it's a CLI-level scope-guard predicate, not a user-facing
   diagnostic — see §Risks "Doctor doesn't surface this state"),
   and one new pre-flight call sequence. No new file under
   `llm_wiki_kit/`.
9. **No `--force-render` without an explicit user invocation.** The
   flag is never auto-set by another code path (e.g., `wiki upgrade`
   on a missing file does NOT silently engage force-render). A user
   who wants the recovery surface types the flag.

## Contracts with other modules

- **`llm_wiki_kit.cli`** — `_cmd_upgrade` gains:
  - one new `argparse` flag (`--force-render`, `action="store_true"`),
  - one new module-private helper `_unrendered_closure_paths(state:
    VaultState, vault_root: Path, catalog: Sequence[Primitive],
    sources: Mapping[str, Path]) -> list[str]`. Walks
    `state.installed_primitives`, filters to primitives present in
    `catalog`, computes the closure as
    `enumerate_rendered_paths([primitive], sources) |
    set(compute_required_regions([primitive]))` per primitive —
    the same union `compute_adoption_set` uses at `adopt.py:171`
    so a host file whose only kit claim is `contributes_to` is
    included in the closure. Returns the sorted list of vault-
    relative POSIX paths where `(vault_root / path).is_file()`
    is False. Pure function; no I/O outside the file-existence
    probe. Primitives whose installed name is absent from the
    catalog are skipped (the closure is undefined when the kit
    doesn't ship the primitive anymore; `wiki doctor`'s
    `primitive-missing` check is the surfacing mechanism for
    that state). The `_required_regions` helper is currently
    module-private to `adopt.py`; this spec lifts it to a public
    name `compute_required_regions` (the `compute_` prefix
    avoids the local-variable name `required_regions` that
    `compute_adoption_set` uses at `adopt.py:161`),
  - one new scope-guard call sequence (compute `unrendered =
    _unrendered_closure_paths(...)` + call
    `doctor.check_managed_region_drift(events, vault_root, state)`;
    short-circuit when both lists are empty),
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
    clean-closure case at the CLI layer).

    **`to_upgrade` is overloaded by mode.** Under `force_render=
    False` (the existing `wiki upgrade` contract) the field names
    primitives whose `installed_version != catalog_version` — a
    version-transition set. Under `force_render=True` it names
    primitives whose closure the runner will re-walk — a re-render
    set, with no version transition implied. The runner's per-
    primitive event-emit branch (see `upgrade_primitives`) is the
    sole consumer that cares about the distinction; downstream
    code (CLI totals, drift collection) reads the field
    uniformly. A future field renaming to disambiguate is in
    §Risks "to_upgrade overload."
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
- **`llm_wiki_kit.doctor`** — `check_managed_region_drift` is
  imported by `_cmd_upgrade` and called as a predicate (return
  value inspected for emptiness; the CLI does not render the
  issues as doctor would). No change to its signature. **Note:
  `check_missing` is intentionally NOT used by the scope guard**
  — it walks `state.page_writes` only and misses paths the
  renderer never reached (the exact failure mode this spec
  recovers). `_unrendered_closure_paths` (in `cli.py`) is the
  closure-presence predicate.
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

- [ ] **AC1 — Clean closure short-circuits with zero disk side
  effects.** Against a vault where `_unrendered_closure_paths` and
  `doctor.check_managed_region_drift` both return `[]`,
  `wiki upgrade --force-render` exits 0 with zero new journal
  events, zero `.proposed` sidecars created, the journal file's
  mtime unchanged, stdout contains `wiki upgrade --force-render: no
  recovery needed (closure is complete).`, AND
  `validate_contributions` is NOT called (verified by a counting
  monkeypatch on `install.validate_contributions` — a presence-
  vs-absence pin, not an interface assertion; the function's
  no-op outcome on the clean-closure path is observable only
  via call count, and AC17's broken-kit behavioral test is the
  complementary contract pin for the same invariant). Pins
  Invariant 4's "no pre-flight cost on a clean closure" clause.
- [ ] **AC2 — Partial-install recovery heals the missing-files gap.**
  Build the fixture using the shared helper
  `tests/fixtures/partial_install.py:make_partial_install_vault(
  tmp_path, *, with_adopt, primitives, cut_after_primitive,
  adopted_paths)` (see plan step 7 for the helper contract).
  Construct a vault with `with_adopt=True`, two installed
  primitives `[core, people]`, `cut_after_primitive="core"`
  (drop every event after `core`'s `PrimitiveInstallEvent`; in
  particular, `people`'s `PrimitiveInstallEvent` and renders are
  absent), and `adopted_paths = {byte_identical_path: <kit-render
  bytes>, byte_differing_path: <user bytes>}` chosen so both adopted
  paths lie under `core`'s `files/` tree (the primitive that does
  appear in `state.installed_primitives` post-truncation; the
  adopted-baseline events survive because they were appended before
  any install event, see wiki-init-adopt spec §Outputs Journal
  events). Run `wiki upgrade --force-render`. Assert: (a) every
  path in the original closure of `state.installed_primitives` post-
  truncation that was missing pre-call is on disk post-call;
  (b) the journal contains exactly one
  `PrimitiveForceRenderEvent(primitive=p.name)` per primitive in
  `state.installed_primitives` post-truncation (so: one for `core`;
  none for `people` because `people` is not in
  `state.installed_primitives`); (c) the byte-identical adopted
  path's `target.stat().st_ino` is unchanged across the call AND
  its bytes match the pre-call snapshot (adopt-match no-rewrite
  branch fired); (d) the byte-differing adopted path has a
  `.proposed` sidecar with the kit's would-render content, the
  original file's bytes and inode are unchanged (adopt-differ
  proposal branch fired); (e) post-run,
  `_unrendered_closure_paths` returns `[]` AND
  `doctor.check_managed_region_drift` returns `[]`;
  `pending-proposal` and `orphan` issues from `wiki doctor` may
  remain as the underlying user content warrants; (f) stdout
  contains `wiki upgrade --force-render: re-rendered 1
  primitive.` (matches §Outputs.Stdout totals wording for `N
  == 1`; pins the count-aware singular vs. plural).
- [ ] **AC3 — Drift on a force-rendered file produces a `.proposed`
  sidecar, never a silent overwrite.** Use the AC2 fixture builder
  with `with_adopt=True`, `cut_after_primitive=<primitive whose
  files/ tree includes the adopted path>`, and an `adopted_paths`
  entry whose user bytes hash to `h_user` while the kit's would-
  render hash is `h_kit != h_user`. The scope-guard precondition
  is non-empty by construction (closure paths under the cut
  primitive are missing). Run `wiki upgrade --force-render`.
  Assert: (a) the original file is byte-identical (bytes AND inode)
  to its pre-call content; (b) `<path>.proposed` exists with the
  kit's would-render content; (c) the journal contains a
  `PageProposalEvent` for the path; (d) stdout printed the drift
  line; (e) the new-events slice contains at least one
  `PrimitiveForceRenderEvent` row (proves the runner was entered;
  the test does not pass via short-circuit).
- [ ] **AC4 — `--force-render` is idempotent across two consecutive
  invocations.** After AC2's scenario completes, snapshot
  `events_first = read_events(journal_path)`. Run `wiki upgrade
  --force-render` a second time. Assert: `read_events(journal_path)
  == events_first` (value-equal list, not just same length),
  exit 0, stdout contains `no recovery needed (closure is
  complete).`, every `.proposed` sidecar from the first invocation
  is on disk untouched (the second invocation does not re-render
  and does not re-propose), AND
  `_unrendered_closure_paths(post_state, vault_root, catalog,
  sources)` returns `[]` (the structural precondition that makes
  the short-circuit fire). Pins Invariant 5 byte-equivalently.
- [ ] **AC5 — `--force-render --primitive <name>` restricts the
  re-render scope.** Use the AC2 fixture builder with
  `primitives=[core, people]`, `cut_after_primitive=<chosen so
  both primitives have missing closure paths post-truncation>`.
  Run `wiki upgrade --force-render --primitive people`. Assert:
  (a) exactly one `PrimitiveForceRenderEvent(primitive="people")`
  row and zero rows for any other primitive in the new-events
  slice; (b) zero `PageWriteEvent.by == "core"` (or any non-
  `people` primitive name) rows in the new-events slice — pins
  the planner-narrowing directly rather than via "files still
  missing" inference; (c) the aggregator still ran over
  `plan.all_installed` (assert via a region whose composed body
  includes a contribution from `core` even though `core` was not
  re-rendered).
- [ ] **AC6 — `--force-render` refuses when a `--primitive` target
  has a pending catalog version bump.** Construct a vault where
  `state.installed_primitives["core"] == "0.1.0"` and the catalog
  ships `core@0.2.0`. Run `wiki upgrade --force-render --primitive
  core`. Assert exit 2, stderr contains `--force-render conflicts
  with a pending upgrade for 'core'`, stdout does NOT contain `no
  recovery needed` (catches a misordering where the scope guard
  fires before the conflict check), zero new journal events.
- [ ] **AC7 — `--force-render` against a vault initialized without
  `--adopt`** (no `PageAdoptedEvent`s, partial install). Use the AC2
  fixture builder with `with_adopt=False` and
  `adopted_paths={}`. Run `wiki upgrade --force-render`. Assert:
  (a) every path in `_unrendered_closure_paths(pre_state, ...)` is
  on disk post-call; (b) zero `PageProposalEvent` rows in the
  new-events slice (no adopt baselines to disagree with;
  `safe_write`'s standard direct-write branch fires); (c) post-run
  `_unrendered_closure_paths` returns `[]`.
- [ ] **AC8 — `PrimitiveForceRenderEvent` round-trips through
  Pydantic with stable JSON; the discriminated `Event` union
  dispatches the row through `read_events`.**
- [ ] **AC9 — `replay_state` populates no new field for
  `PrimitiveForceRenderEvent`.** Pin both the behavior and the
  structural intent: (a) a journal containing a
  `PrimitiveForceRenderEvent` replays to a `VaultState` whose
  `.model_dump()` is byte-equal to replaying the same journal with
  the row removed (effect pin); (b) `journal.py`'s `replay_state`
  body contains an explicit dispatch case (a `match`/`case
  PrimitiveForceRenderEvent():` branch or equivalent named handler,
  verified by `grep PrimitiveForceRenderEvent
  llm_wiki_kit/journal.py`) so the no-op intent is recorded, not
  delivered by silent fallthrough.
- [ ] **AC10 — Aggregator pass runs after per-primitive force
  renders.** Mirrors `wiki upgrade`'s AC9 verbatim, with a
  `by`-based two-phase classification: an *aggregator-phase*
  event is any `ManagedRegionWriteEvent` OR any
  `PageProposalEvent` whose `event.by == "wiki-upgrade"` (the
  aggregator attributes its writes to the vehicle name; the
  per-primitive renderer attributes to `<primitive name>` per
  `render.py:166`). A *per-primitive-phase* event is any
  `PageWriteEvent` OR `PageProposalEvent` whose `event.by` is
  a primitive name (not `"wiki-upgrade"`). Every aggregator-
  phase event's index in the new-events slice is greater than
  every per-primitive-phase event's index attributed to a
  primitive in `plan.to_upgrade`.
- [ ] **AC11 — `by` attribution.**
  `PrimitiveForceRenderEvent.by == "wiki-upgrade"`. Per-primitive
  `PageWriteEvent.by == <primitive name>`.
  `ManagedRegionWriteEvent.by == "wiki-upgrade"`.
- [ ] **AC12 — Event ordering: force-render event before its
  primitive's renders.** Within the slice for any one primitive `p`
  in `to_upgrade`, the `PrimitiveForceRenderEvent(primitive=p.name)`
  index is less than every `PageWriteEvent.by == p.name` index AND
  every `PageProposalEvent.by == p.name` index (per-primitive-phase
  proposals only — aggregator-phase proposals attributed to
  `"wiki-upgrade"` are covered by AC10's strict-after ordering).
- [ ] **AC13 — Cache discipline inherited.** `--force-render`
  reuses `upgrade_primitives` which already runs inside
  `journal.use_journal_cache(journal_path)`. No new call sites
  outside that scope. The structural pin is a grep:
  `_cmd_upgrade`'s force-render branch threads the runner call
  through the same `with use_journal_cache(...)` block the
  existing upgrade path uses. (The `wiki upgrade` spec's AC14
  already exercises the cache-load count via a counting
  monkeypatch; this spec inherits that test unchanged.)
- [ ] **AC14 — Outside a vault, exits 2 with `not a wiki vault` on
  stderr; no journal events anywhere.**
- [ ] **AC15 — After a successful force-render the scope-guard
  predicate is clean.** Post-AC2-scenario,
  `_unrendered_closure_paths` returns `[]` AND
  `doctor.check_managed_region_drift` returns `[]`. `wiki doctor`
  may still report `pending-proposal` (for adopt-differ sidecars
  AC2(d) produced) and `orphan` (for user-territory files under
  kit-owned dirs) — those are inherited from the pre-call user
  content, not introduced by force-render.
- [ ] **AC16 — Scope guard scoping: `pending-proposal` alone does
  NOT trigger the runner.** Construct a vault by initializing with
  `--adopt` over content that produces exactly one `.proposed`
  sidecar (one byte-differing adopted path) and zero missing
  closure paths. Verify the precondition holds: pre-call,
  `_unrendered_closure_paths` returns `[]`,
  `check_managed_region_drift` returns `[]`, and `wiki doctor`
  reports exactly one `pending-proposal` and zero of every other
  issue type (catches a fixture that vacuously satisfies the AC
  for the wrong reason). Run `wiki upgrade --force-render`.
  Assert: scope guard fires; stdout contains `no recovery needed
  (closure is complete).`; zero new events; the sidecar is
  byte-identical to its pre-call content.
- [ ] **AC17 — `validate_contributions` pre-flights on the
  non-clean-closure path.** Construct a fixture where (i) the
  scope-guard predicate is non-empty (use the AC2 builder) AND
  (ii) an unchanged-version primitive's contribution shape is
  invalid in the kit (e.g., a declared `contributes_to` snippet
  missing on disk). Run `wiki upgrade --force-render`. Assert exit
  2 with `PrimitiveError`, zero new `PrimitiveForceRenderEvent`s
  in the journal. The clean-closure path does NOT trigger
  `validate_contributions` (pinned by AC1); a broken-kit state
  combined with a clean closure surfaces no `--force-render`
  error here — the user is recommended to run `wiki doctor`,
  which surfaces the broken contribution via its existing
  channels.
- [ ] **AC18 — Empty-installed init-in-progress hint.** Construct
  a vault with `VaultInitEvent` but no `PrimitiveInstallEvent` (the
  `wiki init --adopt` post-adopt-pre-install crash state). Run
  `wiki upgrade --force-render`. Assert: exit 0, stdout contains
  `no recovery needed (closure is complete).`, stderr contains
  `note: this vault has no installed primitives; if init was
  interrupted, run 'wiki init --adopt' to resume.`, zero new
  journal events. Points users at the right recovery slot
  (per §Happy path — clean closure's stderr hint).
- [ ] **AC19 — Force-render-event payload audit completeness.**
  Pin that each `PrimitiveForceRenderEvent` carries enough payload
  to reconstruct what was re-rendered from the journal alone:
  `primitive` (the name), `version` (the version-at-the-time-of-
  run, since the catalog could bump between recovery and a later
  audit), `by="wiki-upgrade"`, `timestamp` (inherited from
  `_EventBase`). Per-file attribution to "this force-render run"
  is via two query shapes:
  - **Page-scope events** (`PageWriteEvent`, OR
    `PageProposalEvent` whose `event.by != "wiki-upgrade"`): the
    per-file event at journal index `i` is attributable to the
    `PrimitiveForceRenderEvent` at index `j < i` where (a) `j`
    is the maximum such index whose `primitive` field equals
    the per-file event's `by` field AND (b) no other
    `Primitive*Event` for that primitive sits between `j` and
    `i` (i.e., a later `PrimitiveInstallEvent` /
    `PrimitiveUpgradeEvent` for the same primitive interrupts
    the bracket).
  - **Region-scope events** (`ManagedRegionWriteEvent`, OR
    `PageProposalEvent` whose `event.by == "wiki-upgrade"`):
    the aggregator pass runs once per force-render run;
    region-scope events are attributable to a run by *index
    position alone* — every region-scope event whose index
    lies in the slice `[k, k')` where `k` is the LAST
    `PrimitiveForceRenderEvent` index in the new-events
    slice and `k'` is the next non-aggregator-emitted
    `Primitive*Event` (or end of journal) belongs to that run.
    There is no per-primitive bracket for region-scope events
    because their `by == "wiki-upgrade"` carries no primitive
    name, and a host file can have contributions from multiple
    primitives — "the host file's owning primitive" is
    undefined.
  Document both queries in §Outputs.Journal events so a
  maintainer reading the tail knows the rule. (No new payload
  field; the bracket queries are the documented audit
  interface.)
- [ ] **AC20 — Shared-host-file partial recovery.** Construct
  a fixture where primitive A (e.g., `core`) ships
  `frontmatter.schema.yaml` in its `files/` tree AND primitive B
  (e.g., `content-types`) contributes to it via
  `contributes_to`. Use the step 7
  `make_two_primitive_partial_install_vault` helper with
  `primitives=["core", "content-types"]` so BOTH
  `PrimitiveInstallEvent` rows are durable post-truncation
  (state.installed_primitives contains both) but
  `frontmatter.schema.yaml`'s `PageWriteEvent` is absent on
  disk. The two-cut helper is required, NOT the single-cut
  variant: a single-cut `cut_after_primitive="core"` would
  drop content-types's install event, removing it from
  `state.installed_primitives`, and the aggregator pass over
  `plan.all_installed == [core]` would never compose
  content-types's region contribution. Pre-call: assert
  `_unrendered_closure_paths` returns `frontmatter.schema.yaml`
  (caught via `core`'s `enumerate_rendered_paths`). Run
  `wiki upgrade --force-render`. Assert: (a) the host file is
  on disk post-call with `core`'s base body PLUS `content-types`'s
  region contribution composed in; (b) the journal contains one
  `PrimitiveForceRenderEvent` per primitive in
  `state.installed_primitives` (i.e., both `core` and
  `content-types`), a `PageWriteEvent(path=
  "frontmatter.schema.yaml", by="core")` from the per-primitive
  render, and at least one `ManagedRegionWriteEvent` from the
  aggregator pass (with `by == "wiki-upgrade"`);
  (c) post-run, `_unrendered_closure_paths == []`. Pins the
  end-to-end shared-host-file recovery shape.

  **Note on the `compute_required_regions` union in
  `_unrendered_closure_paths`.** The union with
  `set(compute_required_regions([p]))` is defense-in-depth: in
  today's
  kit, every host file referenced by `contributes_to` is also
  shipped by some primitive's `files/` tree (the aggregator's
  pre-condition at `install.py:280-283` requires the file
  exist on disk before the aggregator runs; `safe_write_region`
  raises `FileNotFoundError` otherwise). So a "host file
  reachable ONLY via `contributes_to`" is a degenerate state
  the kit cannot currently produce. The union ensures that if
  the kit ever evolves to allow it, the closure helper handles
  the case without a downstream regression. Pinned at the
  unit level by plan step 6's
  `test_unrendered_closure_paths_includes_host_file_only_contributions`
  test, NOT by an integration AC (an integration test would
  crash inside the aggregator's `safe_write_region`, not heal
  the vault).

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

## Risks

- **Doctor doesn't surface this state to users.** The scope-guard
  predicate `_unrendered_closure_paths` lives in `cli.py` because
  it's a CLI-level decision, not a `wiki doctor` diagnostic. A
  user inspecting a vault with `wiki doctor` after a crashed install
  sees `missing` issues only for paths that previously had
  `PageWriteEvent`s (the existing `check_missing` semantics) — NOT
  the un-rendered closure paths this spec recovers. Mitigation: a
  sibling spec can lift `_unrendered_closure_paths` into
  `doctor.check_unrendered_closure` (or widen `check_missing` to
  walk `state.installed_primitives × enumerate_rendered_paths`)
  once the recovery surface has shipped and we know the diagnostic
  shape users want. Until then the recommended user workflow is:
  run `wiki upgrade --force-render`; if the scope guard fires
  with "no recovery needed", the closure is complete. The spec's
  doc sweep (plan step 16) lands a corrigendum in `wiki-init-adopt`
  spec §Edge cases that overclaims `check_missing`'s coverage.
- **`UpgradePlan.to_upgrade` is overloaded by mode.** Under
  `force_render=False` (today's `wiki upgrade`), `to_upgrade` names
  primitives with `installed_version != catalog_version` — a
  version-transition set. Under `force_render=True`, it names
  primitives whose closure to re-walk — a re-render set, with no
  version transition implied. The field carries different semantics
  by hidden flag. Mitigation: documented explicitly in §Contracts
  `plan_upgrade`; AC8 + AC12 pin the event-class discriminator so
  downstream readers can tell which mode produced a journal row. A
  future field renaming (e.g. add `to_render: list[Primitive]`)
  is a candidate for the sibling-spec refactor when the
  `wiki upgrade` and force-render code paths diverge further.
- **Scope-guard false negative** (`_unrendered_closure_paths` misses
  a real partial-install shape). A primitive's `files/` tree has a
  conditional template that produces zero files for a given
  recipe context; the closure-presence check expects no file and
  reports clean even when a partial install left other files
  missing. Mitigation: AC2's fixture exercises the standard
  truncate-mid-`PrimitiveInstallEvent` shape and pins the predicate
  against the realistic failure mode. Conditional-empty templates
  are a sibling concern for `enumerate_rendered_paths` to handle
  consistently (the wiki-init-adopt spec already pins
  `test_enumerate_rendered_paths_matches_render_tree_output` as
  the equivalence check).
- **Scope-guard false positive** (a clean vault returns non-empty
  from `_unrendered_closure_paths` because the user deleted a
  kit-owned file). Acceptable behavior: the journal claims the
  closure expects the file (`PrimitiveInstallEvent` for the
  owning primitive is journaled), the file is absent, the kit
  re-renders it. Users who want to permanently remove a kit-owned
  file resolve via a future `wiki primitive remove` (out of scope
  for this spec) or by editing the journal manually (always
  out of scope).
- **Conflict-check vs. recovery overlap.** AC6 refuses
  `--force-render --primitive <name>` when the catalog and
  installed versions differ. The user's recovery path becomes the
  two-step `wiki upgrade --primitive <name>` then re-evaluate. But
  `wiki upgrade --primitive <name>` over a partially-installed
  vault is itself a recovery operation `wiki upgrade`'s spec
  declines to handle (its §Edge cases "Crash between events and
  disk writes" defers to `wiki doctor`). Mitigation: a user in this
  state is genuinely on a frontier — the recommended path is run
  `wiki upgrade --primitive <name>` first (which lands a
  `PrimitiveUpgradeEvent` and the new version's renders, healing
  the partial install incidentally), then run `wiki upgrade
  --force-render` if any closure paths remain absent. The spec
  does not auto-bundle these — the user types the two commands.
- **TOCTOU between scope-guard probe and runner write.** The user
  edits a file between step 5's file-existence probe and step
  8's `render_tree` call. The adopt-aware predicate routes a
  differing-bytes file to proposal exactly as it would for
  `wiki upgrade`. Honest outcome; documented in §Edge cases.

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
- **No new `wiki doctor` check.** The scope guard's closure-presence
  predicate lives in `cli.py` as a module-private helper, not in
  `doctor.py`. Lifting it into doctor is a sibling-spec decision
  (see §Risks "Doctor doesn't surface this state").
- **No vault-side SKILL.** Force-render is kit-side recovery;
  vault-side workflow uses the existing `wiki-conflict` skill for
  any sidecars the run produces.
- **No structural refactor of `upgrade.py`.** The change is two
  keyword args + one new branch (the event-class swap). The runner's
  control flow, journal-slice collection, and aggregator call site
  are unchanged.
