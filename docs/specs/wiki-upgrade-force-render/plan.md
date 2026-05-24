# Plan: wiki-upgrade-force-render

> **Implementation plan paired with `spec.md`.** The spec says *what*; the
> plan says *how, in what order, with what verification*.

- **Status:** Drafting
- **Spec:** `docs/specs/wiki-upgrade-force-render/spec.md`
- **Owner:** maintainer

## Approach

One landing PR. The surface area is small — one new event class, two
new keyword args on `upgrade.py`'s entry points, one new `argparse`
flag on `_cmd_upgrade`, one new module-private helper
`_unrendered_closure_paths` in `cli.py`, and one new pre-flight call
sequence (the scope guard). The dependency arrow inside the PR is:
`PrimitiveForceRenderEvent` + replay no-op dispatch → `upgrade.py`
keyword args + event-swap branch → shared `partial_install` fixture
builder → `_cmd_upgrade` flag + scope guard + conflict check.

TDD-first throughout. The contract pin lives at the integration
layer: a fixture vault produced by a SHARED helper
(`tests/fixtures/partial_install.py:make_partial_install_vault`)
that drops every journal event after a chosen `cut_after_primitive`,
drive `wiki upgrade --force-render`, assert the closure heals. Unit
tests pin the Pydantic round-trip, the `replay_state` no-op (with
an explicit dispatch branch grep-able in `journal.py`), the
`plan_upgrade(force_render=True)` planner output, the
`upgrade_primitives` event-swap behavior, and
`_unrendered_closure_paths`'s closure-presence semantics.

### Declined patterns (commitments for REVIEW)

- **Tempted to add a `reason: Literal["upgrade","force_render"]`
  field on `PrimitiveUpgradeEvent`** instead of a new
  `PrimitiveForceRenderEvent` class. Declined per spec §Constraints
  "No new event field on `PageWriteEvent` / `ManagedRegionWriteEvent`"
  and ADR-0008 §Decision sub-choice 4 (one-class-per-event convention,
  rejected `reason` field on `PageWriteEvent` for the same audit-
  vs-dispatch reason). Discriminator dispatch is the kit's standard
  shape.
- **Tempted to suppress `PageWriteEvent` on byte-match in
  force-render mode.** Declined per spec §Non-goals "No suppression
  of `PageWriteEvent` on byte-match." The kit's established
  `safe_write` contract
  (`test_no_op_write_of_identical_content_still_records_event`)
  records every write attempt; force-render inherits the convention.
  Branching `safe_write` on a force-render flag would split the
  load-bearing predicate and complicate every future write
  invariant.
- **Tempted to make the scope guard configurable
  (`--force-render --even-if-clean`).** Declined: the spec's
  idempotence guarantee (AC4) relies on the guard being
  unconditional. A user who wants to re-render a clean vault has
  no recovery to do; they want a different feature (one that
  doesn't exist yet). Defer until real demand surfaces.
- **Tempted to lift `_unrendered_closure_paths` into
  `doctor.check_unrendered_closure` in this PR.** Declined: the
  scope guard is the CLI's decision about whether to enter the
  runner — co-located with `_cmd_upgrade` it's grep-locatable
  from one place. Lifting into doctor surfaces it as a user-facing
  diagnostic, which is the right shape ONLY if `wiki doctor` is
  going to report it — and that's a sibling-spec design decision
  (does doctor add a new `Issue` kind? does it widen `MISSING`?
  what's the user message?). Doing both in one PR mixes the
  recovery-tool contract with a diagnostic contract. The spec's
  §Risks "Doctor doesn't surface this state" names the sibling
  spec; this PR doesn't pre-empt it.
- **Tempted to fork a `force_render.py` module rather than extend
  `upgrade.py`.** Declined per spec §Constraints "No new module
  under `llm_wiki_kit/`." The change is two keyword args + one
  branch; a new module would be ceremony for one new event class.
- **Tempted to widen the scope guard to include `pending-proposal`
  issues.** Declined per spec §Edge cases bullet 4: pending
  proposals are the user's to merge via `wiki-conflict`, not the
  re-render's. Including them would re-emit `PageProposalEvent`s
  for already-known drifts and clutter the journal.
- **Tempted to make `--force-render` imply `--primitive=<all>` and
  surface a `--all` flag.** Declined: `wiki upgrade`'s default
  scope is already "all installed primitives"; `--primitive` is the
  narrowing surface. `--force-render` inherits the same default and
  the same narrowing flag.
- **Tempted to auto-engage `--force-render` from `wiki doctor`'s
  remediation hint.** Declined per spec §Invariants bullet 9: the
  flag is never auto-set. The recovery is an explicit user choice.

## Pre-conditions

- ADR-0008 is accepted and PR-A/PR-B/PR-C of `wiki-init-adopt` have
  shipped (the adopt-aware `safe_write` predicate this spec relies
  on is in place).
- `llm_wiki_kit/upgrade.py` carries `plan_upgrade` and
  `upgrade_primitives` in their current shape.
- `llm_wiki_kit/doctor.py` exposes `check_managed_region_drift` as
  an importable function with signature `(events: list[Event],
  vault_root: Path, state: VaultState) -> list[Issue]` (verified
  at `doctor.py:220-222`).
- `llm_wiki_kit/install.py` exposes `enumerate_rendered_paths` as
  an importable function (verified — it landed in
  `wiki-init-adopt`'s PR-C).
- `llm_wiki_kit/models.py`'s discriminated `Event` union accepts
  one new class via the `Annotated[... | NewClass, Field(
  discriminator="type")]` shape (the wiki-init-adopt PR-A change
  established the pattern).
- No conflicting work in flight on `upgrade.py`, `cli.py`'s
  `_cmd_upgrade`, or `models.py`'s `Event` union.

## Steps

> **Verification mode.** Every step is TDD: the construction tests
> land first (red), then the implementation makes them green. The
> contract tests in `spec.md` §Acceptance criteria are the
> end-of-PR gate.

1. **`PrimitiveForceRenderEvent` round-trips through Pydantic and
   dispatches through the discriminated `Event` union.**
   - **Tests** (new file
     `tests/unit/test_primitive_force_render_event.py`):
     - `test_primitive_force_render_event_round_trips` — construct,
       dump via `dump_event_json`, parse via `parse_event_line`,
       assert structural equality.
     - `test_primitive_force_render_event_in_discriminated_union_dispatch`
       — append via `append_event` to a tmp journal, read via
       `read_events`, assert the row is parsed into
       `PrimitiveForceRenderEvent` via the `type` discriminator
       (`"primitive.force_render"`).
     - `test_primitive_force_render_event_by_attribution_pinned` —
       assert `event.by == "wiki-upgrade"` matches spec
       §Invariants bullet 6.
   - **Verify (red):** `pytest
     tests/unit/test_primitive_force_render_event.py` fails at
     import — `PrimitiveForceRenderEvent` does not exist yet.
   - **Implementation:** add the class to `models.py`:
     ```
     class PrimitiveForceRenderEvent(_EventBase):
         type: Literal["primitive.force_render"] = "primitive.force_render"
         primitive: str
         version: str
     ```
     Append to the `Event` discriminated union.
   - **Verify (green):** the new test file passes.
1. **`replay_state` treats `PrimitiveForceRenderEvent` as a no-op
   (AC9).**
   - **Tests** (extend `tests/unit/test_journal.py`):
     - `test_replay_state_force_render_event_is_audit_only` —
       seed a journal with a `VaultInitEvent`, one
       `PrimitiveInstallEvent`, then a
       `PrimitiveForceRenderEvent` for the same primitive at the
       same version; replay; assert the resulting `VaultState` is
       byte-equal (via `.model_dump()`) to the state of replaying
       the same journal without the force-render row.
     - `test_replay_state_legacy_journal_unaffected_by_force_render_dispatch`
       — replay an `wiki upgrade`-shape journal containing zero
       force-render events; assert no regressions in
       `state.installed_primitives`.
   - **Verify (red):** test passes accidentally if `replay_state`
     ignores unknown event types — but the dispatch in
     `replay_state` is a `match` over known classes (verify
     before drafting; if it raises on unknown classes, the test
     goes red until step 1 is wired). Add an explicit `case
     PrimitiveForceRenderEvent(): pass` branch to make the no-op
     intent grep-able even if it would have been a default.
   - **Implementation:** the explicit no-op branch in
     `replay_state`.
   - **Verify (green):** test passes; existing replay tests
     unaffected.
1. **`plan_upgrade(force_render=True)` returns `to_upgrade =
   all_installed`.**
   - **Tests** (extend `tests/unit/test_upgrade.py`):
     - `test_plan_upgrade_force_render_lifts_short_circuit` —
       construct a `VaultState` whose `installed_primitives` match
       the catalog versions exactly (the no-op case `wiki upgrade`
       short-circuits on). Call `plan_upgrade(state, catalog,
       only=None, force_render=True)`. Assert `plan.to_upgrade ==
       plan.all_installed` and `plan.no_op_target is None`.
     - `test_plan_upgrade_force_render_with_only_returns_single_primitive`
       — same setup, `only="core"`. Assert `plan.to_upgrade ==
       [catalog_by_name["core"]]` and `plan.all_installed`
       still the full installed set.
     - `test_plan_upgrade_force_render_with_only_uninstalled_raises`
       — `only="nope"` (not installed); assert `WikiError`. Same
       behavior as today's `wiki upgrade`.
     - `test_plan_upgrade_force_render_default_false_unchanged` —
       pin that `force_render=False` (the default) reproduces
       today's behavior bit-for-bit on a fixture state +
       catalog pair (a no-op state plus a one-bump state).
   - **Verify (red):** the new keyword arg is unknown to
     `plan_upgrade`; tests fail with `TypeError`.
   - **Implementation:** add `force_render: bool = False` to
     `plan_upgrade`'s signature. Under `force_render=True`:
     - When `only is None`: `to_upgrade = list(all_installed)`.
     - When `only` is set and installed and in catalog:
       `to_upgrade = [catalog_by_name[only]]`.
     - `no_op_target = None` always (the CLI handles the
       clean-vault case at the layer above).
   - **Verify (green):** new tests pass; existing
     `test_upgrade.py` tests stay green.
1. **`upgrade_primitives(force_render=True)` emits
   `PrimitiveForceRenderEvent` instead of `PrimitiveUpgradeEvent`.**
   - **Tests** (extend `tests/unit/test_upgrade.py`):
     - `test_upgrade_primitives_force_render_emits_force_render_event`
       — construct a plan with one primitive in `to_upgrade`; call
       `upgrade_primitives(plan=..., force_render=True, ...)`.
       Assert the new-events slice contains exactly one
       `PrimitiveForceRenderEvent(primitive=p.name,
       version=state_versions[p.name])` and zero
       `PrimitiveUpgradeEvent`s.
     - `test_upgrade_primitives_force_render_preserves_aggregator_pass`
       — same setup, `plan.all_installed` has TWO primitives both
       contributing to the same `(file, region)` bucket;
       force-render one. Assert the resulting region body
       contains both contributors' snippets (the aggregator pass
       still runs over `all_installed`).
     - `test_upgrade_primitives_force_render_emits_event_before_render`
       — pin event-before-disk for the new class: monkeypatch
       `render_tree` to assert that
       `read_events(journal_path)[-1]` is a
       `PrimitiveForceRenderEvent` for the current primitive
       before any file write happens.
     - `test_upgrade_primitives_force_render_false_unchanged` —
       run with `force_render=False`; assert the emitted event is
       still `PrimitiveUpgradeEvent` and the existing wiki-upgrade
       suite stays green.
   - **Verify (red):** signature mismatch.
   - **Implementation:** add `force_render: bool = False` to
     `upgrade_primitives`'s signature. Inside the per-primitive
     loop, swap the event constructor:
     ```python
     if force_render:
         append_event(journal_path, PrimitiveForceRenderEvent(
             timestamp=now, by=UPGRADE_VEHICLE,
             primitive=primitive.name,
             version=state_versions[primitive.name],
         ))
     else:
         append_event(journal_path, PrimitiveUpgradeEvent(
             timestamp=now, by=UPGRADE_VEHICLE,
             primitive=primitive.name,
             from_version=state_versions[primitive.name],
             to_version=primitive.version,
         ))
     ```
   - **Verify (green):** new tests pass.
1. **`_cmd_upgrade` recognises the `--force-render` flag and
   threads it into the runner end-to-end.**
   - **Tests** (new file
     `tests/integration/test_wiki_upgrade_force_render.py`):
     - `test_wiki_upgrade_force_render_flag_recognised` — smoke:
       `wiki upgrade --force-render --help` returns 0 and the
       help text mentions the flag.
   - **Verify (red):** unknown flag.
   - **Implementation:** add the `argparse` flag to
     `_cmd_upgrade`'s subparser (`upgrade_parser.add_argument(
     "--force-render", action="store_true", help="Re-render the
     installed primitive closure to recover from a partial
     install. See docs/specs/wiki-upgrade-force-render.")`).
     Thread `args.force_render` through to `plan_upgrade` and
     `upgrade_primitives`. (No wiring of the scope guard yet —
     that lands in step 6 atop step 7's fixture; this step's
     contract is "the flag passes through to the runner without
     a TypeError.")
   - **Verify (green):** the smoke test passes. Note: the
     behavior contract (planner narrowing, event-swap) is
     pinned by step 3 + step 4's unit tests; this step is the
     wiring smoke only. We do NOT add a "counting monkeypatch on
     `plan_upgrade` asserts force_render=True was passed" test
     — that would pin the implementation rather than the
     contract (the planner narrowing is already pinned at the
     unit level).
1. **`_unrendered_closure_paths` returns the vault-relative paths
   missing from the installed-primitive closure on disk.**
   - **Tests** (new file `tests/unit/test_unrendered_closure_paths.py`):
     - `test_unrendered_closure_paths_empty_when_all_present` —
       seed a `VaultState` with `installed_primitives={"core":
       "0.1.0"}`; pre-place every path
       `enumerate_rendered_paths([core], sources)` would produce
       on disk; assert the helper returns `[]`.
     - `test_unrendered_closure_paths_lists_missing_paths_sorted` —
       same seed; delete two paths from disk; assert the helper
       returns them in sorted order (vault-relative POSIX).
     - `test_unrendered_closure_paths_skips_primitive_missing_from_catalog`
       — `installed_primitives={"gone": "0.0.1"}` with `gone`
       absent from `catalog`; assert the helper returns `[]`
       (the kit can't enumerate paths for a primitive it
       doesn't ship).
     - `test_unrendered_closure_paths_empty_when_no_installed_primitives`
       — `installed_primitives={}`; assert `[]` regardless of
       on-disk content.
     - `test_unrendered_closure_paths_is_pure_no_journal_writes`
       — call the helper against a tmp-path vault; assert the
       journal file's mtime is unchanged (no I/O outside the
       file-existence probe).
   - **Verify (red):** the helper doesn't exist.
   - **Implementation:** add `_unrendered_closure_paths(state,
     vault_root, catalog, sources)` to `cli.py` (module-private):
     ```python
     def _unrendered_closure_paths(state, vault_root, catalog, sources):
         catalog_by_name = {p.name: p for p in catalog}
         missing: list[str] = []
         for name in state.installed_primitives:
             if name not in catalog_by_name:
                 continue
             p = catalog_by_name[name]
             for rel in enumerate_rendered_paths([p], sources):
                 if not (vault_root / rel).is_file():
                     missing.append(rel)
         return sorted(missing)
     ```
   - **Verify (green):** the unit-test file passes.
1. **Shared partial-install fixture builder (used by AC2, AC3,
   AC5, AC7, AC10, AC12, AC15, AC17).**
   - **Tests** (new file
     `tests/fixtures/test_partial_install.py` — the
     self-tests that pin the helper's contract):
     - `test_make_partial_install_vault_cuts_after_named_primitive`
       — call the helper with two primitives and
       `cut_after_primitive="core"`; assert
       `read_events(journal_path)[-1]` is the
       `PrimitiveInstallEvent` whose `primitive == "core"`; the
       second primitive's `PrimitiveInstallEvent` and renders
       are absent.
     - `test_make_partial_install_vault_with_adopt_preserves_adopt_events`
       — `with_adopt=True`, `adopted_paths={path: bytes}`;
       assert the journal contains exactly one
       `PageAdoptedEvent(path=...)` per entry, in the
       interleaved order wiki-init-adopt spec §Outputs Journal
       events names, BEFORE any `PrimitiveInstallEvent`.
     - `test_make_partial_install_vault_no_adopt_emits_no_adopted_events`
       — `with_adopt=False`, `adopted_paths={}`; assert zero
       `PageAdoptedEvent` rows in the journal.
     - `test_make_partial_install_vault_unrendered_closure_non_empty`
       — pin the postcondition: after the helper builds the
       vault, `_unrendered_closure_paths(state, vault_root,
       catalog, sources)` returns a NON-empty list (the helper's
       contract is "produce a vault where the scope guard
       won't short-circuit"). Without this pin, every downstream
       AC that relies on the runner being entered could pass
       vacuously via short-circuit.
     - `test_make_partial_install_vault_cut_inside_primitive_files_tree`
       — pin that the `cut_after_primitive` argument cuts the
       journal AFTER the named primitive's
       `PrimitiveInstallEvent` but BEFORE that primitive's
       page writes — i.e., the named primitive has its install
       event durable but partial-or-zero file renders. The
       helper's contract: `cut_after_primitive=X` produces a
       state where X is in `state.installed_primitives` but
       X's `files/` tree is partially or wholly missing on disk.
   - **Implementation:** new module
     `tests/fixtures/partial_install.py`:
     ```python
     @dataclass(frozen=True)
     class PartialInstallVault:
         vault_root: Path
         journal_path: Path
         pre_call_journal_bytes: bytes
         pre_call_unrendered: list[str]
         adopted_path_inodes: dict[str, int]  # for AC2(c) inode pin

     def make_partial_install_vault(
         tmp_path: Path,
         *,
         with_adopt: bool,
         primitives: list[str],
         cut_after_primitive: str,
         adopted_paths: dict[str, bytes] = {},
         recipe: str = "core",
     ) -> PartialInstallVault:
         # 1. Run `wiki init [--adopt]` over tmp_path with the named
         #    recipe (constructed inline to include `primitives`).
         # 2. Truncate the journal: read events, find the index of
         #    the `PrimitiveInstallEvent` whose `primitive ==
         #    cut_after_primitive`, drop every event after it.
         #    Delete on-disk files corresponding to events that were
         #    dropped (so disk state matches the truncated journal).
         # 3. Snapshot journal bytes, compute pre_call_unrendered,
         #    capture inodes for adopted_paths.
         ...
     ```
     Lives under `tests/fixtures/` because it's test-only and not
     shipped to users. The helper is the single source of truth
     for "what does a partial install look like" — sibling specs
     can reuse it.
   - **Verify (green):** the self-test module passes.
1. **Scope guard short-circuits on a clean closure (AC1, AC4,
   AC16, AC18).**
   - **Tests** (the new integration file from step 5):
     - `test_wiki_upgrade_force_render_clean_closure_short_circuits`
       (AC1) — initialize a vault with `wiki init --recipe core`
       (no partial install). Pre-call: snapshot journal bytes;
       assert `_unrendered_closure_paths` returns `[]` and
       `check_managed_region_drift` returns `[]`. Count-monkeypatch
       on `install.validate_contributions` to confirm it is NOT
       called. Run `wiki upgrade --force-render`. Assert exit 0,
       stdout `no recovery needed (closure is complete).`,
       journal bytes unchanged, zero `.proposed` sidecars under
       `vault_root`, `validate_contributions` call count == 0.
     - `test_wiki_upgrade_force_render_pending_proposal_alone_does_not_trigger`
       (AC16) — initialize a vault with `--adopt` over content
       that produces EXACTLY ONE `.proposed` sidecar AND ZERO
       missing closure paths. Pre-call assertions:
       `_unrendered_closure_paths == []`,
       `check_managed_region_drift == []`, `wiki doctor` reports
       exactly one `pending-proposal` and zero of every other
       issue type (catches a vacuously-passing fixture). Run
       `wiki upgrade --force-render`. Assert short-circuit
       (zero new events, exit 0, sidecar bytes unchanged,
       stdout `no recovery needed (closure is complete).`).
     - `test_wiki_upgrade_force_render_idempotent_across_invocations`
       (AC4) — drive the partial-install fixture from step 6's
       builder, run `--force-render` (the heal); snapshot
       `events_first = read_events(journal_path)`; run
       `--force-render` again. Assert
       `read_events(journal_path) == events_first` (value-equal
       list), exit 0, stdout `no recovery needed (closure is
       complete).`, every `.proposed` sidecar from the first
       invocation byte-identical, `_unrendered_closure_paths
       == []` post-second-run.
     - `test_wiki_upgrade_force_render_empty_installed_primitives_hint`
       (AC18) — hand-seed a journal containing only
       `VaultInitEvent` (no `PrimitiveInstallEvent`s). Run
       `wiki upgrade --force-render`. Assert exit 0, stdout
       contains `no recovery needed (closure is complete).`,
       stderr contains `note: this vault has no installed
       primitives; if init was interrupted, run 'wiki init
       --adopt' to resume.`, zero new journal events.
   - **Implementation:** in `_cmd_upgrade`, after `state` load and
     catalog resolve, when `args.force_render`:
     ```python
     unrendered = _unrendered_closure_paths(
         state, vault_root, catalog, sources)
     region_drift = doctor.check_managed_region_drift(
         events, vault_root, state)
     if not unrendered and not region_drift:
         print("wiki upgrade --force-render: no recovery needed "
               "(closure is complete).")
         if not state.installed_primitives:
             print(
                 "note: this vault has no installed primitives; "
                 "if init was interrupted, run 'wiki init --adopt' "
                 "to resume.",
                 file=sys.stderr,
             )
         return 0
     ```
     This sits BEFORE `validate_contributions` so a clean-closure
     invocation does not pay the pre-flight cost (AC1).
   - **Verify (green):** all four tests pass.
1. **Partial-install recovery heals the missing-files gap (AC2,
   AC11, AC15).**
   - **Tests** (the integration file):
     - `test_wiki_upgrade_force_render_recovers_missing_files`
       (AC2) — use the step 6 fixture builder with
       `with_adopt=True`, `primitives=["core", "people"]`,
       `cut_after_primitive="core"`, and
       `adopted_paths={byte_identical_rel: <kit-render bytes>,
       byte_differing_rel: <user bytes>}` where both rel paths
       lie under `core`'s `files/` tree (the primitive that
       survives in `state.installed_primitives`
       post-truncation). Pre-call: capture
       `target.stat().st_ino` for the byte-identical path,
       snapshot pre-call bytes for both paths,
       `pre_unrendered = _unrendered_closure_paths(...)`
       (asserted non-empty by step 6's fixture-self-test).
       Run `wiki upgrade --force-render`. Assert:
       (a) every path in `pre_unrendered` is on disk post-call;
       (b) journal contains EXACTLY ONE
           `PrimitiveForceRenderEvent(primitive=p.name)` per
           primitive in `state.installed_primitives`
           post-truncation (i.e., one for `core`; none for
           `people` because `people`'s install event was dropped
           by the cut);
       (c) byte-identical adopted path: bytes unchanged AND
           `target.stat().st_ino` unchanged (adopt-match
           no-rewrite branch fired — wiki-init-adopt AC14's
           inode-preservation pin replicated here);
       (d) byte-differing adopted path: original bytes AND inode
           unchanged; `<path>.proposed` exists with the kit's
           would-render content; `PageProposalEvent(path)` is
           the latest event for the path;
       (e) post-run, `_unrendered_closure_paths(post_state, ...)
           == []` AND `check_managed_region_drift == []`. `wiki
           doctor` may report `pending-proposal` (for AC2(d))
           and `orphan` (for user-territory files in kit-owned
           dirs); those issue kinds are inherited from user
           content, not introduced by force-render.
     - `test_wiki_upgrade_force_render_by_attribution` (AC11) —
       same fixture, assert each event's `by` matches spec
       §Invariants bullet 6.
   - **Implementation:** in `_cmd_upgrade`, after the scope-guard
     short-circuit doesn't fire, call `validate_contributions`
     over `plan.all_installed`, then
     `plan_upgrade(state, catalog, only=args.primitive,
     force_render=args.force_render)`, then
     `upgrade_primitives(plan=..., ..., force_render=
     args.force_render, ...)`. Ensure the totals row is the
     `--force-render` variant when the flag is set
     (`wiki upgrade --force-render: re-rendered N primitive(s).`
     vs. the standard `wiki upgrade: upgraded N primitive(s).`).
   - **Verify (green):** AC2 + AC11 + AC15 pass.
1. **`--force-render --primitive <name>` restricts scope (AC5).**
   - **Tests** (same integration file):
     - `test_wiki_upgrade_force_render_primitive_restricts_event_count`
       — use the step 6 fixture builder with
       `primitives=["core", "people"]` and
       `cut_after_primitive` chosen so BOTH primitives have
       missing closure paths (truncate further back than AC2 to
       drop both `PrimitiveInstallEvent`s — actually, the
       fixture's contract is `cut_after_primitive=X` means "X
       is in installed_primitives, X's renders partial"; to
       cover BOTH, the builder needs a second invocation or a
       different shape — pin in the fixture self-tests: an
       extra fixture method `make_two_primitive_partial_install`
       that ensures both primitives are in
       `state.installed_primitives` AND both have missing
       closure paths). Run `wiki upgrade --force-render
       --primitive people`. Assert: (a) EXACTLY ONE
       `PrimitiveForceRenderEvent(primitive="people")` row in
       the new-events slice and ZERO `PrimitiveForceRenderEvent`
       rows for any other primitive; (b) ZERO
       `PageWriteEvent.by == "core"` (or any non-`people`
       primitive name) rows in the new-events slice — pins the
       planner-narrowing contract directly rather than via
       "files still missing" inference; (c) the aggregator pass
       walked `plan.all_installed` (assert via a region whose
       composed body includes `core`'s snippet contribution
       even though `core` was not re-rendered).
   - **Implementation:** confirm no implementation change beyond
     step 5's threading. Add a second helper to step 6's
     fixture module: `make_two_primitive_partial_install_vault(
     tmp_path, *, primitives, ...)` that produces a vault where
     BOTH named primitives are in `state.installed_primitives`
     but both have missing closure paths. The helper achieves
     this by truncating AFTER both install events but BEFORE
     both primitives' render-phase `PageWriteEvent`s.
   - **Verify (green):** test passes.
1. **`--force-render --primitive <name>` refuses on pending
   catalog version bump (AC6).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_primitive_with_version_mismatch_refuses`
       — construct a vault at `core@0.1.0` and a catalog shipping
       `core@0.2.0`. Run `wiki upgrade --force-render --primitive
       core`. Assert exit 2, stderr contains `--force-render
       conflicts with a pending upgrade for 'core'`, zero new
       journal events.
   - **Implementation:** in `_cmd_upgrade`, when both
     `args.force_render` and `args.primitive` are set, compare
     `state.installed_primitives[args.primitive]` to
     `catalog_by_name[args.primitive].version`; raise the new
     `WikiError` shape on mismatch.
   - **Verify (green):** test passes.
1. **`--force-render` works on a non-adopt-initialized partial
   install (AC7).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_recovers_non_adopt_init`
       — use the step 6 fixture builder with `with_adopt=False`,
       `adopted_paths={}`, `primitives=["core"]`,
       `cut_after_primitive="core"`. Run `wiki upgrade
       --force-render`. Assert: (a) every path in pre-call
       `_unrendered_closure_paths` is on disk post-call;
       (b) ZERO `PageProposalEvent` rows in the new-events
       slice (no adopt baselines to disagree with); (c) post-run
       `_unrendered_closure_paths == []` AND
       `check_managed_region_drift == []`.
   - **Implementation:** no code change beyond the existing
     wiring — the adopt-aware predicate degrades gracefully when
     no `PageAdoptedEvent`s are present.
   - **Verify (green):** test passes.
1. **Event ordering invariants (AC10, AC12).**
   - **Tests** (extend the integration suite):
     - `test_wiki_upgrade_force_render_event_ordering_within_primitive`
       (AC12) — fixture with a partial install; run
       `--force-render`; assert that within the slice for each
       primitive `p`, the `PrimitiveForceRenderEvent(primitive=
       p.name)` index is less than every `PageWriteEvent.by ==
       p.name` and `PageProposalEvent` index for paths under
       `p`'s `files/` tree.
     - `test_wiki_upgrade_force_render_aggregator_pass_after_per_primitive`
       (AC10) — mirrors `wiki upgrade`'s AC9 test: every
       `ManagedRegionWriteEvent` index in the new-events slice
       is greater than every per-primitive `PageWriteEvent` /
       `PageProposalEvent` index.
   - **Implementation:** no code change beyond what step 4 +
     step 7 wire.
   - **Verify (green):** tests pass.
1. **Cache discipline inherited (AC13).**
   - **Tests:** none new at the runtime level — the existing
     `wiki upgrade` AC14 test in
     `tests/integration/test_wiki_upgrade.py` already exercises
     the one-cache-load shape via a counting monkeypatch on
     `journal.read_events`. The `--force-render` path reuses
     `upgrade_primitives` unchanged, so it inherits the cache
     scope.
   - **Structural pin** (one assertion in the integration
     suite): `test_wiki_upgrade_force_render_uses_journal_cache_scope`
     — `inspect.getsource(_cmd_upgrade)` contains
     `use_journal_cache` and the `--force-render` branch's
     runner call sits inside that `with` block (grep-by-AST
     check, NOT a runtime count). Cheap, structural, robust to
     future runner refactors.
   - **Implementation:** none beyond step 5's wiring.
   - **Verify (green):** structural pin passes.
1. **Vault-boundary refusal (AC14).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_outside_vault_exits_2` —
       run `wiki upgrade --force-render` from a directory with
       no `.wiki.journal/journal.jsonl`. Assert exit 2, stderr
       contains `not a wiki vault`, zero new journal events.
   - **Implementation:** the existing vault-boundary check
     fires before any `--force-render` logic.
   - **Verify (green):** test passes.
1. **Pre-flight `validate_contributions` on the non-clean-closure
   path (AC17).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_validates_contributions_when_closure_partial`
       — combine the step 6 fixture builder (a partial install,
       so `_unrendered_closure_paths` is non-empty AND the scope
       guard passes through) with a kit-side breakage: an
       unchanged-version primitive's `contributes_to` snippet
       file is removed from the kit's templates directory before
       the call. Run `wiki upgrade --force-render`. Assert exit
       2 with `PrimitiveError`, ZERO `PrimitiveForceRenderEvent`
       rows in the new-events slice.
     - `test_wiki_upgrade_force_render_does_not_validate_when_closure_clean`
       — clean-closure fixture (an empty closure, e.g.,
       `wiki init --recipe core`) PLUS the same kit-side
       breakage. Pre-call: monkeypatch
       `install.validate_contributions` with a counter. Run
       `wiki upgrade --force-render`. Assert exit 0, stdout
       `no recovery needed (closure is complete).`,
       `validate_contributions` call count == 0 (the scope
       guard short-circuited before pre-flight could discover
       the broken kit). The user is recommended to run
       `wiki doctor` for the kit-side problem — that's the
       diagnostic surface, not `--force-render`'s.
   - **Implementation:** the existing `validate_contributions`
     call in `_cmd_upgrade` already runs over
     `plan.all_installed`; the `--force-render` path enters that
     pre-flight ONLY when the scope guard does NOT short-circuit
     (step 6's CLI structure pins this ordering).
   - **Verify (green):** both tests pass.
1. **Per-file audit attribution via journal-index bracket (AC19).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_per_file_events_attributable_to_run_via_bracket`
       — use the step 6 fixture builder; capture
       `events_pre = read_events(journal_path)`. Run
       `wiki upgrade --force-render`. Capture
       `events_post = read_events(journal_path)`. For each
       `PageWriteEvent` / `PageProposalEvent` / `ManagedRegion
       WriteEvent` in `events_post[len(events_pre):]`,
       implement the documented bracket query — find the most
       recent `PrimitiveForceRenderEvent` whose `primitive`
       matches the per-file event's owning primitive (the page
       event's `by` field for `PageWriteEvent`; the host file's
       owning primitive for region events) — and assert that
       row exists in `events_post[len(events_pre):]` (i.e.,
       every per-file event in the new-events slice is
       attributable to a `PrimitiveForceRenderEvent` in the
       same slice). Pins the §Outputs.Journal events
       "per-file attribution" query shape.
   - **Implementation:** none beyond existing wiring — the test
     is a consumer of the spec's documented query shape.
   - **Verify (green):** test passes.
1. **Drift on force-rendered file (AC3).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_drift_produces_proposal_not_silent_overwrite`
       — use the step 6 fixture builder with
       `with_adopt=True`, `primitives=["core"]`,
       `cut_after_primitive="core"`,
       `adopted_paths={drift_path: <user bytes hashing to
       h_user>}` where `drift_path` lies under `core`'s
       `files/` tree AND the kit's would-render bytes for
       `drift_path` hash to `h_kit != h_user`. Capture
       pre-call `target.stat().st_ino` and bytes. Run
       `wiki upgrade --force-render`. Assert: (a) original
       file bytes AND inode unchanged across the call; (b)
       `<path>.proposed` exists with `h_kit` content; (c)
       `PageProposalEvent(path)` is journaled with `path ==
       drift_path`; (d) stdout contains the `Wrote ... drift
       detected on ...` line; (e) the new-events slice
       contains at least one `PrimitiveForceRenderEvent` row
       (proves the runner was entered; the test does not pass
       via short-circuit — pinned per spec AC3(e)).
   - **Implementation:** no code change — the adopt-aware
     `safe_write` predicate (already shipped) handles this case.
   - **Verify (green):** test passes.
1. **Doc sweep and CHANGELOG.**
   - `docs/ROADMAP.md`: keep §"Post-PR-C follow-ups" pointer
     intact for this PR (per user instruction); the entry gets
     updated when the spec is accepted (separate PR).
   - `docs/specs/wiki-init-adopt/spec.md` §Edge cases "Crash
     inside the install pipeline":
     (a) amend the deferral pointer to name the now-existing
     spec at `docs/specs/wiki-upgrade-force-render/`;
     (b) **corrigendum** — the current wording overclaims that
     "`wiki doctor` surfaces `missing` for any kit-owned path
     the renderer didn't reach." That's only true for paths
     with prior `PageWriteEvent`s; paths the renderer never
     reached are NOT in `state.page_writes` and `check_missing`
     does not surface them. Fix: replace the overclaiming
     sentence with "`wiki doctor`'s `check_missing` walks
     `state.page_writes` only and will not surface paths the
     renderer never reached; the recovery surface for
     un-rendered closure paths is `wiki upgrade --force-render`
     (see `docs/specs/wiki-upgrade-force-render/`)." This is a
     scope-adjacent correction landing in the same PR per
     AGENTS.md "Fix small scope-adjacent gaps in-session"
     guidance.
   - `docs/specs/wiki-init-adopt/plan.md` PR-C step 13
     "DEFERRED RATIONALE": update the follow-on tracking pointer
     to name the now-existing spec.
   - `CHANGELOG.md` `[Unreleased]` section: add a `### Added`
     entry `wiki upgrade --force-render — re-render the installed
     primitive closure to recover from a partial install. See
     docs/specs/wiki-upgrade-force-render/.` This lands with the
     implementation PR, not the spec PR.
   - **Verify:** `git grep -n "wiki upgrade --force-render"
     docs llm_wiki_kit` returns the spec, the wiki-init-adopt
     pointers, and (post-implementation) the CLI help text and
     CHANGELOG entry. `git grep -n "for any kit-owned path the
     renderer didn't reach" docs` returns zero matches (the
     overclaim is gone).
1. **Patterns capture.**
   - Append one entry to `docs/knowledge/patterns.jsonl` (when
     the implementation PR lands; not in this spec-only PR)
     capturing the decision tree: "force-render is a recovery
     tool gated by the scope guard; the adopt-aware
     `safe_write` predicate is the sole arbiter of drift; never
     bypass it." Body length follows the existing corpus.
   - **Verify:** `python -m json.tool < docs/knowledge/patterns.jsonl`
     parses every line; `id` is unique.

## Verification gate

```
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

All four green. The integration suite at
`tests/integration/test_wiki_upgrade_force_render.py` is green
specifically. Smoke: a representative partial-install fixture
(`wiki init --adopt` over a mixed-content target, journal
truncated mid-install) heals to `wiki doctor` clean after one
`wiki upgrade --force-render`, with `.proposed` sidecars present
only for the byte-differing adopted files.

## Risks

- **Scope-guard false negative**: `doctor.check_missing` /
  `doctor.check_managed_region_drift` miss a real partial-install
  shape, and `--force-render` short-circuits on a vault that
  actually needs recovery. Mitigation: AC2's fixture exercises
  the most common partial-install shape (truncated journal
  mid-install pipeline) and asserts the diagnostic surface
  catches it. Edge cases that the diagnostics miss are doctor
  bugs to fix in doctor, not workarounds in `--force-render`.
- **Scope-guard false positive**: `check_missing` reports a
  `missing` for a file the user deliberately deleted (not a
  partial install), and `--force-render` re-creates it. This is
  acceptable behavior — the journal claims the file exists
  (`PageWriteEvent` / `PageAdoptedEvent` baseline), the file is
  absent, the kit re-renders it. Users who want to permanently
  remove a kit-owned file resolve the situation via `wiki
  primitive remove` (future spec) or a manual journal edit (out
  of scope for the kit).
- **`PrimitiveForceRenderEvent` audit noise on routine recovery**:
  a vault that crashes mid-install every few months accumulates
  audit rows. Acceptable — the rows are sparse, grep-able, and
  document the recovery. The kit's journal-tail UX already
  filters by event type.
- **Conflict-check edge case**: `--force-render --primitive
  <name>` where the catalog ships a NEWER version than installed
  is the obvious case the spec pins (AC6). The OLDER case
  (catalog ships an older version than installed) is the
  downgrade-via-pinned-pipx scenario — same conflict-check
  behaviour applies (the versions differ, the user gets the
  refusal, runs `wiki upgrade --primitive <name>` first which
  records the downgrade honestly per the wiki-upgrade spec).
- **TOCTOU between scope-guard diagnostic and runner write**:
  the user edits a file between step 5's check_missing call and
  step 8's render_tree call. The runner sees the new on-disk
  bytes; the adopt-aware predicate routes a differing-bytes file
  to proposal exactly as it would in `wiki upgrade`. Honest
  outcome; documented in spec §Edge cases.

## Out of scope

- `--force-render --even-if-clean` flag (Non-goal; the scope
  guard is unconditional).
- Per-file `--force-render <path>` surface (Non-goal; the flag
  operates on the primitive closure).
- Auto-engaging `--force-render` from `wiki doctor`'s remediation
  output (Invariant 9; the flag is an explicit user opt-in).
- A new `wiki doctor` check that reports "partial install
  detected" (the existing `missing` + `managed-region-drift`
  checks already surface the symptom).
- Schedule-installable force-render (Non-goal; recovery is
  user-invoked).
- `PrimitiveForceRenderEvent` rolling up multiple primitives
  into a single audit row (Non-goal; one event per primitive
  matches the kit's per-primitive-event convention).
- Vault-side SKILL for force-render (Non-goal; kit-side recovery
  surface).
