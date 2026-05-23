# Plan: wiki-schedule

> **Implementation plan paired with `spec.md`.** The spec says *what*;
> the plan says *how, in what order, with what verification*.

- **Status:** Done
- **Spec:** [`docs/specs/wiki-schedule/spec.md`](spec.md)
- **Owner:** maintainer

## Approach

Eight PRs land the `wiki schedule` verb top-down: the new `write_helper`
helper that paves over the non-vault-path constraint, the journal-event
vocabulary, the platform-agnostic module skeleton, then the three per-OS
emitters in dependency order (launchd → systemd → Task Scheduler), then
`wiki doctor` integration. Each PR is one Claude Code session.
Post-v2.0 commits use the
[conventional-commits format from `docs/CONVENTIONS.md` § Commit messages](../../CONVENTIONS.md#commit-messages)
(`feat(schedule):`, `fix(schedule):`, etc.).

**Steps 2 and 3 ship bundled** as one PR (`feat(schedule): events +
default_time + DSL + emitter Protocol (PR-2+3 of 8)`). PR-3 directly
consumes PR-2's `OperationContract.default_time` field, and the same PR
hoists the `_Emitter` Protocol into `schedule/_emitter.py` so the three
per-OS emitter PRs (steps 4, 6, 7) can import it without colliding on
shared init-module state. Steps 4, 6, and 7 shipped as #89, #90, #91
respectively from a parallel round-3 supervisor view; this section is
now historical context.

Why this order: every per-OS emitter consumes the DSL parser, the
module API, and the new `write_helper` exemption, so those land first;
macOS is the only end-to-end testable target, so it sets the
integration-test shape that systemd and Windows inherit at the
file-emission layer.

The companion spec [`wiki-run-exec`](../wiki-run-exec/spec.md) lands
in parallel — it has no module-level dependency on this work (the
`exec_command` string this plan writes into artifacts is just text;
the OS invokes it independently of how it was authored).

## Pre-conditions

- [RFC-0003](../../rfc/0003-scheduling-and-autonomous-execution.md)
  Accepted — done.
- `journal.transaction()` available — done (`journal-locking` spec).
- Reviewer agreement on the `write_os_artifact()` exemption pattern
  (parallel to `_ensure_obsidianignore`). Step 1 is where this lands.

## Steps

1. **`write_helper.write_os_artifact()` exists and refuses in-vault paths.**
   - **Depends on:** none.
   - **Tests:** new `tests/unit/test_write_os_artifact.py`:
     - happy-path: writes a file under a `tmp_path` simulating
       `~/Library/LaunchAgents/`, content round-trips byte-for-byte;
     - post-condition replace: writing to an existing path produces
       a file whose final bytes match the new content and leaves no
       `.tmp*` siblings in the directory (atomicity-of-`os.replace`
       is a stdlib guarantee on POSIX and on Windows when the
       destination exists; the test asserts the observable
       post-condition, not a racy mid-write check);
     - in-vault refusal: `write_os_artifact(vault_root / "x.plist",
       …, vault_root=vault_root)` raises `WikiError` with a clear
       "route through safe_write instead" message;
     - permission failures bubble as `OSError` (the helper does not
       swallow them).
   - **Approach:** add `write_os_artifact(path: Path, content: str |
     bytes, *, vault_root: Path) -> None` to
     `llm_wiki_kit/write_helper.py`. Uses `tempfile.NamedTemporaryFile`
     in the artifact's parent directory + `os.replace()` for the
     atomic swap. Documented as the second blessed exemption from
     `safe_write` (the first is `_ensure_obsidianignore`), citing
     [`safe-write-ordering`](../safe-write-ordering/spec.md) §"Documented
     exceptions" — spec amendment in the same PR if a third exemption
     needs a new ADR.

2. **`ScheduleInstalledEvent` + `ScheduleUninstalledEvent` +
   `OperationContract.default_time` field round-trip.**
   - **Depends on:** none.
   - **Tests:** new `tests/unit/test_models_schedule_events.py`:
     - both event types round-trip through `model_validate_json` →
       `model_dump_json` (mirrors spec CT-14);
     - a literal pre-v3 journal line with no `schedule.*` events
       replays to the same `VaultState` as before;
     - every existing `templates/operations/*/contract.yaml` validates
       under the extended `OperationContract` (no behavior change);
     - `default_time` accepts `"07:00"`, rejects `"7:00"`, `"7"`,
       `"25:00"`.
   - **Approach:** extend `llm_wiki_kit/models.py` with the two new
     event classes and the new contract field; update the
     discriminated `Event` union.

3. **DSL parser + default-fill table.**
   - **Depends on:** Step 2.
   - **Tests:** new `tests/unit/test_schedule_dsl.py`:
     - happy-path parse for each of `daily`, `<DAY>`, `monthly`,
       `quarterly`;
     - day-of-week case-insensitive;
     - rejection of cron strings (canary inputs from spec CT-4);
     - rejection of seconds and other malformed forms;
     - `resolve_default()` matches the §Inputs table for each
       `period:` value — pinned against a single named constant
       `DEFAULT_TIME_BY_PERIOD`;
     - refusal on `period: on-demand` (mirrors spec CT-3);
     - refusal on absent/other periods.
   - **Approach:** new module `llm_wiki_kit/schedule/dsl.py`. Public
     surface: `parse(dsl: str) -> ResolvedCadence`,
     `resolve_default(contract: OperationContract) -> ResolvedCadence`,
     `to_systemd_oncalendar(cadence: ResolvedCadence) -> str`,
     `to_launchd_calendar_interval(cadence: ResolvedCadence) ->
     list[dict[str, int]]` (list so the launchd emitter can hand a
     quarterly cadence's four-month fan-out straight to plistlib
     without re-computing it),
     `to_task_scheduler_trigger(cadence: ResolvedCadence) -> ET.Element`.

4. **macOS launchd emitter — file emission + activation.**
   - **Depends on:** PR-1 (`write_helper.write_os_artifact()`) and the
     bundled PR-2+3 (events + `default_time` + DSL + `_Emitter`
     Protocol). Once both have merged, this step is `Depends on: none`
     from the round-3 supervisor's POV.
   - **Tests:** new `tests/unit/test_schedule_launchd.py`:
     - `render_plist()` golden-string assertions for each cadence
       kind (CT-2 derivable from these);
     - **for a `quarterly` cadence, the rendered plist's
       `StartCalendarInterval` value is a four-element array of dicts
       whose `Month` keys are `(1, 4, 7, 10)`** (pins that the
       emitter handed the full `to_launchd_calendar_interval(...)`
       list to `plistlib`, not just `intervals[0]`);
     - argv-block contents pin `wiki run --exec <op>` shape;
     - `inspect()` returns each of the four states given fixture
       `launchctl print` outputs (mocked via subprocess monkeypatch).
   - And an opt-in `@pytest.mark.slow`
     `tests/integration/test_schedule_launchd_macos.py` (gated on
     `platform.system() == "Darwin"`): installs a no-op plist that
     `echo`'s on fire, calls real `launchctl bootstrap`, verifies
     `inspect()` returns `loaded`, then `bootout`'s.
   - **Approach:** new module `llm_wiki_kit/schedule/launchd.py`
     implementing the `_Emitter` Protocol from `spec.md` §"Contracts
     with other modules". Plist rendering via stdlib `plistlib`.

5. **Module orchestration: `schedule.install`, `schedule.uninstall`,
   `schedule.list_schedules`.**
   - **Depends on:** Step 1, Step 2, Step 3, Step 4 (launchd),
     **Step 6 (systemd)**, **Step 7 (taskscheduler)**. PR-5 imports
     `SystemdEmitter` and `TaskSchedulerEmitter` into the dispatch
     table and into the systemd-ordering construction test, so all
     three emitter modules must have landed first. The earlier
     "parallel with PR-6 and PR-7" framing only applied while
     PR-5/PR-6/PR-7 were in flight from a single round-3 supervisor;
     post-merge of PR-6 (#90) and PR-7 (#91) this step is a strict
     follow-on.
   - **CT → construction test map:**

     |Spec CT|Construction test                                                                           |File                                  |
     |-------|--------------------------------------------------------------------------------------------|--------------------------------------|
     |CT-1   |`test_install_journals_event_writes_artifact_and_prints_summary` + integration `test_cli_*`|`test_schedule_install.py` + `test_cli_schedule.py`|
     |CT-2   |`test_install_with_at_override_records_canonical_dsl`                                       |`test_schedule_install.py`            |
     |CT-3   |`test_install_refuses_on_demand_period`                                                     |`test_schedule_install.py`            |
     |CT-4   |`test_install_refuses_cron_string_via_at_flag`                                              |`test_schedule_install.py`            |
     |CT-5   |`test_install_idempotent_on_identical_cadence`                                              |`test_schedule_install.py`            |
     |CT-6   |`test_install_refuses_changed_cadence_without_uninstall`                                    |`test_schedule_install.py`            |
     |CT-7   |`test_uninstall_deletes_artifact_and_journals_event`                                        |`test_schedule_uninstall.py`          |
     |CT-8   |`test_uninstall_succeeds_when_artifact_already_missing`                                     |`test_schedule_uninstall.py`          |
     |CT-9   |`test_uninstall_refuses_when_no_install_event_exists` + `test_uninstall_twice_refuses_second_call`|`test_schedule_uninstall.py`     |
     |CT-10  |`test_list_ok_then_drift_after_artifact_rm`                                                 |`test_schedule_list.py`               |
     |CT-11  |`test_list_refuses_non_vault_directory`                                                     |`test_schedule_list.py`               |
     |CT-12  |`test_install_does_not_journal_when_activation_fails`                                       |`test_schedule_install.py`            |
     |CT-13  |`test_list_machine_filter_and_all_machines_flag`                                            |`test_schedule_list.py`               |
     |CT-14  |Already covered by PR-2+3's `test_models_schedule_events.py`.                              |(not in PR-5)                         |
     |CT-15  |PR-8's doctor section.                                                                      |(not in PR-5)                         |
     |CT-16  |`test_uninstall_foreign_machine_skips_os_deactivation`                                      |`test_schedule_uninstall.py`          |
     |CT-17  |PR-8's doctor section.                                                                      |(not in PR-5)                         |
     |CT-18  |`test_install_exec_command_prefers_shutil_which_over_argv0`                                 |`test_schedule_install.py`            |

   - **Tests (construction):**
     - `tests/unit/test_schedule_install.py`:
       - `test_install_journals_event_writes_artifact_and_prints_summary` —
         CT-1: stub `_Emitter` whose `artifact_path()` returns a
         `tmp_path` file; one `ScheduleInstalledEvent`, artifact file
         exists, stdout summary present.
       - `test_install_with_at_override_records_canonical_dsl` — CT-2:
         `at="tue 18:00"` resolves to `cadence_dsl="TUE 18:00"`; the
         stub captures the `cadence` passed to `render_artifact` and we
         assert `day_of_week=2, hour=18, minute=0`.
       - `test_install_refuses_on_demand_period` — CT-3.
       - `test_install_refuses_cron_string_via_at_flag` — CT-4.
       - `test_install_idempotent_on_identical_cadence` — CT-5. The
         dup-cadence short-circuit runs **before** `journal.transaction()`
         opens (spec §"install happy path" step 7 precedes step 8), so
         the idempotent path emits zero events of any type — not just
         zero `ScheduleInstalledEvent`s. The test snapshots the journal
         line-count before and after the second call and asserts
         equality.
       - `test_install_refuses_changed_cadence_without_uninstall` — CT-6.
       - `test_install_does_not_journal_when_activation_fails` — CT-12.
         The stub's `activate()` **asserts `artifact_path.exists()` on
         entry** (pinning the spec's "write → activate" ordering —
         the write must have run before the activation attempt), then
         raises `WikiError`. Post-call assertions in the test
         fixture's controlled `tmp_path` directory (where unlink
         always succeeds): no `schedule.installed` event, artifact
         file is gone, `lock.acquired` / `lock.released` pair present,
         non-zero return. The "best-effort unlink may fail in
         production" caveat from spec §"OS-side activation" is
         documentation about real-world disk-error paths and is not in
         tension with this test's assertion — the test runs in a
         fixture where unlink succeeds, exercising the happy
         cleanup path.
       - `test_install_systemd_activation_failure_leaves_service_companion_on_disk`
         — pins CT-12's systemd-specific clause. Setup: monkeypatch
         `_resolve_emitter` to a real `SystemdEmitter()`; monkeypatch
         `Path.home` to `tmp_path`; monkeypatch `SystemdEmitter.activate`
         to raise `WikiError("simulated")`. Run `install`. Assert
         (a) `not timer_path.exists()` (primary unlinked on
         best-effort cleanup), (b) `service_path(timer_path).exists()`
         (companion left on disk as harmless orphan), (c) zero
         `ScheduleInstalledEvent`s in the journal, (d) `lock.acquired`
         / `lock.released` pair present.
       - `test_install_systemd_calls_companion_artifacts_protocol_method`
         — pins that the orchestrator invokes
         `emitter.companion_artifacts(...)` exactly once (rather than
         hard-coding the systemd-specific dual-write via an
         `isinstance` branch). Monkeypatch `SystemdEmitter.companion_artifacts`
         to a spy; run `install`; assert the spy was called exactly
         once with `cadence` and `exec_command` matching the install
         inputs. The spy then delegates to the real implementation
         (via `original.companion_artifacts(...)`) so the rest of
         install completes normally. Companion to
         `test_install_systemd_writes_companion_then_primary` below
         (which observes the side-effect; this one observes the
         invocation).
       - `test_systemd_emitter_companion_artifacts_returns_service_pair_for_timer`
         — unit-tests the new `SystemdEmitter.companion_artifacts`
         method in isolation. Pure-function assertion: for a daily
         cadence + `(operation, vault_id, vault_root, exec_command)`
         tuple, the returned list has exactly one entry, the path
         equals `service_path(timer_path)` (where `timer_path` is
         what `artifact_path(vault_id, operation)` returns), and the
         body equals `render_service(operation=..., vault_root=...,
         vault_id=..., exec_command=...)` byte-for-byte. Lives in
         `tests/unit/test_schedule_systemd.py` (PR-6's file, amended
         by PR-5) rather than `test_schedule_install.py` because the
         method belongs to the systemd module.
       - `test_install_systemd_writes_companion_then_primary` — pins
         the Linux dual-write the orchestrator performs via the
         lifted Protocol method
         `emitter.companion_artifacts(...)`. Setup: monkeypatch
         `llm_wiki_kit.schedule._resolve_emitter` to return a real
         `SystemdEmitter()` so the systemd code path is exercised
         regardless of host OS; monkeypatch `Path.home` to `tmp_path`
         so the artifact paths land under the fixture; monkeypatch
         `SystemdEmitter.activate` to a no-op recorder; monkeypatch
         `llm_wiki_kit.schedule.write_os_artifact` (the name the
         orchestrator resolves at call time, *not*
         `llm_wiki_kit.write_helper.write_os_artifact`) to a spy that
         appends each call into a shared `calls: list[tuple[str,
         Path]]` log. The `activate` no-op also appends
         `("activate", timer_path)`. Assertions: (a) both `.service`
         and `.timer` files exist after install, (b) the recorded
         call order is `[("write", service_path), ("write",
         timer_path), ("activate", timer_path)]` — pinning the full
         spec'd ordering (`render → companion_artifacts → write
         companions → write primary → activate`).
       - `test_install_windows_summary_includes_schtasks_instruction` —
         pins the `install_instruction()` Protocol lift. Stub emitter
         whose `install_instruction()` returns
         `"schtasks /Create /XML /tmp/x.xml /TN foo"`; assert captured
         stdout contains that string. Symmetric assertion in
         `test_uninstall_windows_summary_includes_schtasks_instruction`
         under `test_schedule_uninstall.py`.
       - `test_install_exec_command_prefers_shutil_which_over_argv0` —
         CT-18. Setup: `(tmp_path / "bin").mkdir()`, write
         `tmp_path / "bin" / "wiki"` with a shebang stub,
         `wiki_path.chmod(0o755)`, `monkeypatch.setenv("PATH", str(tmp_path / "bin"))`.
         Assert the journaled `exec_command[0]` equals
         `str(tmp_path / "bin" / "wiki")` (matches `shutil.which("wiki")`
         after the PATH stub). `shutil.which` reads `os.environ["PATH"]`
         fresh per call — no `lru_cache` to clear.
     - `tests/unit/test_schedule_uninstall.py`:
       - `test_uninstall_deletes_artifact_and_journals_event` — CT-7.
       - `test_uninstall_succeeds_when_artifact_already_missing` — CT-8.
       - `test_uninstall_refuses_when_no_install_event_exists` — CT-9.
       - `test_uninstall_twice_refuses_second_call` — second uninstall
         hits CT-9's "no schedule installed" path because the later
         `ScheduleUninstalledEvent` masks the earlier
         `ScheduleInstalledEvent`. Exactly one
         `ScheduleUninstalledEvent` total across the two calls.
       - `test_uninstall_foreign_machine_skips_os_deactivation` —
         CT-16: stub emitter records `deactivate()` calls; assert no
         call, event has `removed_artifact=False`, stderr warning.
         **Also pre-create a file at the journaled `os_artifact_path`
         under `tmp_path` and assert it is untouched** (the foreign-
         machine branch must not unlink local files).
       - `test_uninstall_windows_summary_includes_schtasks_instruction`
         — symmetric to the install variant above.
     - `tests/unit/test_schedule_list.py`:
       - `test_list_ok_then_drift_after_artifact_rm` — CT-10.
       - `test_list_refuses_non_vault_directory` — CT-11.
       - `test_list_machine_filter_and_all_machines_flag` — CT-13.
     - `tests/integration/test_cli_schedule.py`:
       - `test_cli_schedule_install_journals_event_and_writes_artifact`
         — drive `python -m llm_wiki_kit schedule install …` against a
         real `tmp_path` vault; assert stdout, journal, and artifact
         file on disk.
   - **Approach:** new `llm_wiki_kit/schedule/__init__.py` wiring DSL
     + emitter + journal + state-replay together. Install sequence
     **write companions → write primary → activate → journal** per
     spec §"install happy path" step 8 (no rollback; activation
     failure unlinks the primary artifact and skips the journal
     append; companions are *not* unlinked — they're harmless orphans
     on the failure path, consistent with spec §Invariants "uninstall
     deletes one file"). The dup-cadence idempotent check runs
     **before** `journal.transaction()` opens, so the no-op path
     emits zero events of any type (no `lock.acquired` /
     `lock.released` pair) — spec §Invariants now pins this
     explicitly. Platform dispatch via a module-level
     `_EMITTERS: dict[str, _Emitter]` table keyed by
     `platform.system()`; tests inject behavior by monkeypatching
     `_resolve_emitter`. **Import shape pinned:**
     `schedule/__init__.py` does `from llm_wiki_kit.write_helper
     import write_os_artifact` so the function is bound in the
     `llm_wiki_kit.schedule` namespace; tests monkeypatch at that
     call-site name so the spy actually intercepts. Resolves PR-7's
     deferred design question by **lifting
     `install_instruction(artifact_path) -> str | None` and
     `uninstall_instruction(artifact_path) -> str | None` onto
     `_Emitter`** with `None`-default impls on launchd/systemd; the
     Windows emitter's methods delegate to the existing module-level
     `format_activation_instruction` / `format_deactivation_instruction`
     helpers (PR-7's tests stay green). Names are deliberately
     `*_instruction` not `post_*_instruction` to read as "return the
     user-facing instruction string for the stdout summary" rather
     than "run after install"; the docstring pins "never spawn a
     subprocess." **Also lifts
     `companion_artifacts(...) -> list[tuple[Path, str | bytes]]`
     onto `_Emitter`** with default `[]` on launchd/taskscheduler;
     the Linux `SystemdEmitter` returns
     `[(service_path(timer_path), service_body)]`. Rationale: removes
     both the Windows-only and Linux-only branches from the
     orchestrator and keeps `_Emitter` as the single place a future
     OS implementor learns the contract — every per-OS asymmetry is
     now a Protocol method with a sensible default. Also extracts
     `run._resolve_operation_kind`, `_load_contract`, and
     `_operation_contract_path` to a new
     `llm_wiki_kit/operations.py` module so `schedule.install`
     reuses the same installed-primitive + kind check + contract
     loader `wiki run` uses; spec §"Contracts with other modules"
     amended to enumerate the three extracted names. Refactor is
     pure; `run.py` imports the extracted names and behavior is
     byte-identical.

6. **Linux systemd emitter — file emission only.**
   - **Depends on:** PR-1 (`write_helper.write_os_artifact()`) and the
     bundled PR-2+3 (events + `default_time` + DSL + `_Emitter`
     Protocol). Once both have merged, this step is `Depends on: none`
     from the round-3 supervisor's POV.
   - **Tests:** new `tests/unit/test_schedule_systemd.py`:
     - golden-string assertions for `.service` + `.timer` per cadence
       kind, including the OnCalendar string;
     - `inspect()` returns each state given fixture `systemctl --user
       is-enabled` outputs (mocked).
   - And an opt-in `@pytest.mark.slow` integration test (gated on
     `platform.system() == "Linux"` *and* `systemd-run --user`
     available) — no CI gate; documented in spec §"OS coverage".
   - **Approach:** new module `llm_wiki_kit/schedule/systemd.py`
     implementing the `_Emitter` Protocol. Renders `.service` +
     `.timer` as plain strings (systemd's INI dialect doesn't
     round-trip cleanly through stdlib `configparser`).

7. **Windows Task Scheduler emitter — file emission only.**
   - **Depends on:** PR-1 (`write_helper.write_os_artifact()`) and the
     bundled PR-2+3 (events + `default_time` + DSL + `_Emitter`
     Protocol). Once both have merged, this step is `Depends on: none`
     from the round-3 supervisor's POV.
   - **Tests:** new `tests/unit/test_schedule_taskscheduler.py`:
     - golden-XML assertions per cadence kind;
     - the XML round-trips through `xml.etree.ElementTree` parsing
       without diff;
     - `activate()` prints (does not invoke) the expected
       `schtasks /Create /XML` command.
   - **Approach:** new module
     `llm_wiki_kit/schedule/taskscheduler.py` implementing
     `_Emitter`. XML rendering via stdlib `ElementTree`.

8. **`wiki doctor` schedule section.**
   - **Depends on:** Step 5, Step 6, Step 7, **and** the
     `OperationExecFailedEvent` model from
     [`wiki-run-exec`](../wiki-run-exec/spec.md) — that model is
     defined in the sibling spec's plan, not in this one. Step 8's
     exec-failure-backlog test cannot run until that PR series
     lands the model in `models.py`. The two plans land in
     parallel (per §Approach); coordinate the merge order so this
     step is last.
   - **Tests:** new `tests/unit/test_doctor_schedules.py` covering:
     - spec CT-15 (drift surfaces as warning, exit 0, stdout
       carries operation name + fix command);
     - CT-17 (hostname rename produces the `--machine <old>` hint);
     - the three drift modes (`missing-file`, `disabled`, `unknown`);
     - exec-failure backlog filters on `reason in {"non-zero-exit",
       "timeout"}` per spec §"Doctor integration".
   - **Approach:** extend `llm_wiki_kit/doctor.py` with
     `_check_schedules(state, journal_path)`. Reuses each
     `_Emitter.inspect()` for OS-side liveness. Output formatting
     mirrors the existing doctor warning shape.

## Verification gate

Each PR runs the standard gate sequence per
[`AGENTS.md` § Commands you'll need](../../../AGENTS.md#commands-youll-need):

```
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

The final PR (Step 8) additionally runs `pytest -m slow` on macOS so
the launchd integration test executes. CI does not gate on
`pytest -m slow`; the maintainer runs it locally.

End-to-end verification (post Step 8):

- All 18 contract tests from `spec.md` pass.
- `wiki schedule install <op>` on a fresh family-recipe vault on
  macOS produces a working launchd plist that, when manually
  kicked via `launchctl kickstart`, invokes `wiki run --exec <op>`
  and writes the expected `OperationRunEvent`. (`--exec` itself
  ships from [`wiki-run-exec`](../wiki-run-exec/spec.md); this
  plan's verification stops at the `wiki run` invocation.)
- `wiki doctor` on the same vault reports the schedule as `ok`,
  flips to `drift:missing-file` after `rm <plist>`, and flips back
  to `ok` after `wiki schedule install <op>`.

## Risks

- **`write_os_artifact()` exemption is precedent-light.** Only one
  prior exemption (`_ensure_obsidianignore`) exists. Reviewer push-
  back would land in Step 1's PR; the spec absorbs the amendment in
  the same PR rather than backing out the design.
- **`socket.gethostname()` is non-stable across DHCP renews.**
  Mitigated by exposing `--machine` and surfacing rename-detection
  in `wiki doctor` (spec §"Edge cases / Hostname rename" + CT-17).
  Migration to stable machine-id (`/etc/machine-id`,
  `IOPlatformUUID`, `MachineGuid`) deferred to a future ADR.
- **systemd `OnCalendar=` syntax has corner cases.** Mitigated by
  running real `systemd-analyze calendar` against the rendered
  string in Step 6's golden tests when systemd is available.
- **launchd `bootstrap`/`bootout` semantics differ across macOS
  versions.** `bootstrap` (10.10+) covers the kit's Python ≥3.11
  floor. Spec is silent on the deprecated `launchctl load`
  fallback — intentional.
- **Vault path with non-ASCII / spaces.** Mitigated by computing
  `<vault-id>` from the path's SHA-256 — the artifact label is
  always ASCII-safe.
- **Race between two `wiki schedule install` calls.** Mitigated by
  `journal.transaction()`'s flock. Cross-vault races out of scope
  (different locks).

## Out of scope

- Vault-side `wiki-schedule` SKILL.md (RFC-0003 §"Migration path"
  task 8). Ships in a follow-up after this plan completes.
- `wiki schedule edit`. Pinned in spec §"Non-goals".
- `wiki doctor --fix` re-materialising schedules. Future doctor-fix
  RFC.
- End-to-end CI for systemd / Windows. RFC-0003 §"OS coverage".
- Cron-string DSL acceptance. RFC-0003 §"Cadence vocabulary".
- Migration to stable machine-id. Future ADR.
