# Plan: wiki-upgrade-force-render

> **Implementation plan paired with `spec.md`.** The spec says *what*; the
> plan says *how, in what order, with what verification*.

- **Status:** Drafting
- **Spec:** `docs/specs/wiki-upgrade-force-render/spec.md`
- **Owner:** maintainer

## Approach

One landing PR. The surface area is small — one new event class, two
new keyword args on `upgrade.py`'s entry points, one new `argparse`
flag on `_cmd_upgrade`, and one new pre-flight call sequence (the
scope guard). The dependency arrow inside the PR is:
`PrimitiveForceRenderEvent` + replay no-op dispatch → `upgrade.py`
keyword args + event-swap branch → `_cmd_upgrade` flag + scope guard
+ conflict check.

TDD-first throughout. The contract pin lives at the integration
layer: a fixture vault with a simulated partial install (truncate the
journal mid-`PrimitiveInstallEvent` so the closure's files are
missing on disk), drive `wiki upgrade --force-render`, assert the
closure heals. Unit tests pin the Pydantic round-trip, the
`replay_state` no-op, the `plan_upgrade(force_render=True)` planner
output, and the `upgrade_primitives` event-swap behavior.

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
- `llm_wiki_kit/doctor.py` exposes `check_missing` and
  `check_managed_region_drift` as importable functions (verify
  before drafting the CLI handler; if either is a method on a
  class, the plan grows one refactor task to lift the predicate).
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
   threads it into the runner.**
   - **Tests** (extend `tests/integration/test_wiki_upgrade.py` or
     a new `tests/integration/test_wiki_upgrade_force_render.py`):
     - `test_wiki_upgrade_force_render_flag_recognised` — smoke:
       `wiki upgrade --force-render --help` returns 0 and the
       help text mentions the flag.
     - `test_wiki_upgrade_force_render_threads_to_planner` — pin
       via a counting monkeypatch on `plan_upgrade` that the CLI
       calls it with `force_render=True` when the flag is set,
       and `force_render=False` otherwise.
   - **Verify (red):** unknown flag.
   - **Implementation:** add the `argparse` flag to
     `_cmd_upgrade`'s subparser (`upgrade_parser.add_argument(
     "--force-render", action="store_true", help="Re-render the
     installed primitive closure to recover from a partial
     install. See docs/specs/wiki-upgrade-force-render.")`).
     Thread `args.force_render` through to `plan_upgrade` and
     `upgrade_primitives`.
   - **Verify (green):** tests pass.
1. **Scope guard short-circuits on a clean vault (AC1, AC4, AC16).**
   - **Tests** (same integration file):
     - `test_wiki_upgrade_force_render_clean_vault_short_circuits`
       (AC1) — initialize a vault with `wiki init --recipe core`
       (no partial install). Run `wiki upgrade --force-render`.
       Assert exit 0, stdout contains `no recovery needed (vault
       is clean).`, the journal byte-content is unchanged from
       the pre-call snapshot.
     - `test_wiki_upgrade_force_render_pending_proposal_alone_does_not_trigger`
       (AC16) — initialize a vault with `--adopt` over content
       that produces one `.proposed` sidecar; run `wiki upgrade
       --force-render`. Assert short-circuit fires (zero new
       events; the sidecar is still on disk; stdout contains
       `no recovery needed`).
     - `test_wiki_upgrade_force_render_idempotent_across_invocations`
       (AC4) — run `--force-render` against a partial-install
       fixture (constructed in step 7's test below); after it
       heals, run `--force-render` again. Assert zero new events,
       exit 0, stdout `no recovery needed`.
   - **Verify (red):** the scope guard does not yet exist.
   - **Implementation:** in `_cmd_upgrade`, after `state` load and
     catalog resolve, when `args.force_render`:
     ```python
     missing = doctor.check_missing(state, vault_root)
     region_drift = doctor.check_managed_region_drift(state, vault_root)
     if not missing and not region_drift:
         print("wiki upgrade --force-render: no recovery needed (vault is clean).")
         return 0
     ```
     This sits BEFORE `validate_contributions` so a clean vault
     short-circuits without paying the pre-flight cost.
   - **Verify (green):** all three tests pass.
1. **Partial-install recovery heals the missing-files gap (AC2,
   AC11, AC15).**
   - **Tests** (same integration file):
     - `test_wiki_upgrade_force_render_recovers_missing_files`
       (AC2) — fixture builder:
       ```python
       def make_partial_install_vault(tmp_path, recipe="core"):
           # Init with --adopt over a small pre-existing set
           # (one byte-identical, one byte-differing).
           # Then truncate the journal at byte-offset chosen to
           # cut mid-PrimitiveInstallEvent so half the closure's
           # files are missing on disk.
           ...
       ```
       Run `wiki upgrade --force-render`. Assert:
       (a) every missing kit-owned file is now on disk;
       (b) journal contains one `PrimitiveForceRenderEvent` per
           primitive in the closure;
       (c) the byte-identical adopted file's bytes + inode are
           unchanged (adopt-match no-rewrite branch);
       (d) the byte-differing adopted file has a `.proposed`
           sidecar (adopt-differ proposal branch); the original
           file is unchanged;
       (e) `wiki doctor` post-run reports zero `missing` /
           `managed-region-drift`; only `pending-proposal` for
           the differing file (AC15).
     - `test_wiki_upgrade_force_render_by_attribution` (AC11) —
       same fixture, assert each event's `by` matches spec
       §Invariants bullet 6.
   - **Verify (red):** scope guard short-circuits everywhere
     (because the runner isn't wired to honour
     `force_render=True` yet — wait, it IS wired by step 4, but
     the `_cmd_upgrade` thread-through in step 5 didn't yet pass
     the flag past the scope guard. Wire that in this step too).
   - **Implementation:** thread `force_render=args.force_render`
     into both `plan_upgrade(...)` and `upgrade_primitives(...)`
     in `_cmd_upgrade` (the call sites already exist; the new
     keyword needs to be passed). Also: ensure the totals row
     is the `--force-render` variant when the flag is set
     (`wiki upgrade --force-render: re-rendered N primitive(s).`
     vs. the standard `wiki upgrade: upgraded N primitive(s).`).
   - **Verify (green):** AC2 + AC11 + AC15 pass.
1. **`--force-render --primitive <name>` restricts scope (AC5).**
   - **Tests** (same integration file):
     - `test_wiki_upgrade_force_render_primitive_restricts_event_count`
       — construct a fixture with two primitives both partially
       rendered. Run `wiki upgrade --force-render --primitive
       people`. Assert: (a) one
       `PrimitiveForceRenderEvent(primitive="people")` and zero
       for any other primitive; (b) the aggregator pass still
       walked `plan.all_installed` (assert via a region whose
       composed body includes the other primitive's contribution
       even though the other primitive was not force-rendered);
       (c) the other primitive's missing files remain missing.
   - **Verify (red):** the scope guard short-circuits unless
     `check_missing` returns non-empty — which it will for the
     two-primitive partial fixture; the test fails because
     `_cmd_upgrade` doesn't yet handle the `--primitive` narrow
     scope under `force_render`. Step 4 wired the planner; step
     5 wired the CLI; this step validates the integration.
   - **Implementation:** confirm no implementation change beyond
     step 5's threading; the test exists to pin the spec's
     "scope-narrowing under force-render" behavior.
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
       — construct a fixture by running `wiki init` (no
       `--adopt`) and truncating the journal mid-render. Run
       `wiki upgrade --force-render`. Assert (a) missing files
       are written; (b) zero `PageProposalEvent`s (no adopt
       baselines); (c) `wiki doctor` reports clean.
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
1. **Cache discipline (AC13).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_runs_inside_journal_cache`
       — counting monkeypatch on `journal.read_events` observes
       the same one-cache-load shape `wiki upgrade` enforces.
   - **Implementation:** the CLI already wraps `_cmd_upgrade`'s
     runner call in `journal.use_journal_cache`; the
     `--force-render` path inherits the scope. Confirm via the
     test.
   - **Verify (green):** test passes.
1. **Vault-boundary refusal (AC14).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_outside_vault_exits_2` —
       run `wiki upgrade --force-render` from a directory with
       no `.wiki.journal/journal.jsonl`. Assert exit 2, stderr
       contains `not a wiki vault`, zero new journal events.
   - **Implementation:** the existing vault-boundary check
     fires before any `--force-render` logic.
   - **Verify (green):** test passes.
1. **Pre-flight `validate_contributions` (AC17).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_validates_contributions_over_all_installed`
       — construct a fixture where an unchanged-version
       primitive's `contributes_to` snippet is missing on disk
       (the kit got into a broken state via a partial pip
       upgrade). Run `wiki upgrade --force-render`. Assert exit
       2 with `PrimitiveError`, zero `PrimitiveForceRenderEvent`s
       in the journal.
   - **Implementation:** the existing `validate_contributions`
     call in `_cmd_upgrade` already runs over
     `plan.all_installed`; the `--force-render` path inherits
     it (after the scope guard fires; the guard's
     `check_missing` will report the missing snippet as a
     `missing` issue or the primitive's downstream files won't
     be reachable, so the scope guard passes through to the
     pre-flight).
   - **Verify (green):** test passes.
1. **Drift on force-rendered file (AC3).**
   - **Tests:**
     - `test_wiki_upgrade_force_render_drift_produces_proposal_not_silent_overwrite`
       — construct a vault with a `PageAdoptedEvent(hash=h_user)`
       baseline whose kit-would-render content hashes to
       `h_kit != h_user`. Pre-place the file on disk with bytes
       hashing to `h_user`. Truncate the journal to make the
       file's `PrimitiveInstallEvent` durable but the
       corresponding `PageWriteEvent` absent (simulating a
       partial install AFTER the install event landed).
       Run `wiki upgrade --force-render`. Assert: (a) original
       file is byte-identical to pre-call; (b)
       `<path>.proposed` exists with `h_kit` content; (c)
       `PageProposalEvent(path)` is journaled; (d) stdout
       contains the `Wrote ... drift detected on ...` line.
   - **Implementation:** no code change — the adopt-aware
     `safe_write` predicate (already shipped) handles this case.
   - **Verify (green):** test passes.
1. **Doc sweep and CHANGELOG.**
   - `docs/ROADMAP.md`: keep §"Post-PR-C follow-ups" pointer
     intact for this PR (per user instruction); the entry gets
     updated when the spec is accepted (separate PR).
   - `docs/specs/wiki-init-adopt/spec.md`: amend §Edge cases
     "Crash inside the install pipeline" to point at
     `docs/specs/wiki-upgrade-force-render/spec.md` as the
     recovery surface (replace the "deferred to a follow-on
     spec" wording with a forward pointer). One-line edit; not a
     contract change.
   - `docs/specs/wiki-init-adopt/plan.md`: PR-C step 13
     "DEFERRED RATIONALE" — update the follow-on tracking
     pointer to name the now-existing spec (link
     `docs/specs/wiki-upgrade-force-render/`).
   - `CHANGELOG.md` `[Unreleased]` section: add a `### Added`
     entry `wiki upgrade --force-render — re-render the installed
     primitive closure to recover from a partial install. See
     docs/specs/wiki-upgrade-force-render/.` This lands with the
     implementation PR, not the spec PR.
   - **Verify:** `git grep -n "wiki upgrade --force-render"
     docs llm_wiki_kit` returns the spec, the wiki-init-adopt
     pointers, and (post-implementation) the CLI help text and
     CHANGELOG entry.
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
