"""Unit tests for the Schedules section of ``wiki doctor`` (PR-8 of wiki-schedule).

Covers the checks documented in
``docs/specs/wiki-schedule/spec.md`` §"Doctor integration":

* CT-15 — schedule installed + plist removed out of band; doctor exits ``0``
  and surfaces the operation name + fix command on stdout.
* CT-17 — hostname rename surfaces an old/new-name one-liner with the
  ``--machine <old>`` migration hint; exit ``0``; no journal write.
* Three drift modes for current-host schedules: ``missing-file``,
  ``disabled``, ``unknown`` (foreign machine — no missing-file/disabled
  warning).
* Exec-failure backlog: count of ``OperationExecFailedEvent``\\ s in the
  last 7 days filtered to ``reason in {non-zero-exit, timeout}``, grouped
  by operation. Five scenarios pin the filter + window edges.

Tests drive the real journal pipeline (``read_events_lenient`` +
``replay_state``) against ``tmp_path`` vaults with a hand-rolled
``journal.jsonl`` so the integration with ``models.py`` is exercised.
The emitter's ``inspect()`` and ``socket.gethostname()`` are
monkeypatched; the wall-clock seam is ``doctor._now``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest

from llm_wiki_kit import cli, doctor
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    LockAcquiredEvent,
    OperationExecFailedEvent,
    ScheduleInstalledEvent,
    ScheduleUninstalledEvent,
)
from llm_wiki_kit.schedule._emitter import InspectResult

_ExecFailureReason = Literal[
    "non-zero-exit",
    "timeout",
    "conflict-refused",
    "binary-missing",
    "skill-missing",
]

NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _vault(tmp_path: Path) -> Path:
    """Create a minimal vault with an empty journal file.

    The journal file must exist (not just the directory) — ``_cmd_doctor``
    raises ``WikiError`` on a directory without ``journal.jsonl``. Tests
    that need events on the journal use ``append_event`` to fill it.
    """

    (tmp_path / ".wiki.journal").mkdir()
    (tmp_path / ".wiki.journal" / "journal.jsonl").touch()
    return tmp_path


def _journal(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


class _StubEmitter:
    """Test double for ``_Emitter`` with a programmable ``inspect`` result.

    Only the method ``_check_schedules`` actually calls is implemented.
    Returns the configured ``InspectResult`` verbatim regardless of
    filesystem state — tests that want ``"missing-file"`` should also
    not create the artifact, but the stub doesn't enforce that linkage
    (kept simple so each test owns its setup explicitly).
    """

    def __init__(self, inspect_result: InspectResult) -> None:
        self._inspect_result = inspect_result

    def inspect(self, artifact_path: Path) -> InspectResult:
        del artifact_path
        return self._inspect_result


def _install_event(
    *,
    operation: str,
    machine_id: str,
    artifact_path: Path,
    cadence_dsl: str = "SUN 09:00",
    timestamp: datetime | None = None,
) -> ScheduleInstalledEvent:
    return ScheduleInstalledEvent(
        timestamp=timestamp or NOW,
        by="wiki-schedule",
        operation=operation,
        machine_id=machine_id,
        cadence_dsl=cadence_dsl,
        os_artifact_path=str(artifact_path),
        exec_command=["/usr/local/bin/wiki", "run", "--exec", operation],
    )


def _exec_failed_event(
    *,
    operation: str,
    reason: _ExecFailureReason,
    timestamp: datetime,
) -> OperationExecFailedEvent:
    return OperationExecFailedEvent(
        timestamp=timestamp,
        by="wiki-run-exec",
        operation=operation,
        dispatch_event_id="dispatch-xyz",
        exit_code=1 if reason == "non-zero-exit" else -2,
        reason=reason,
        stderr_tail="",
        log_path=None,
        conflict_sidecars=[],
    )


@pytest.fixture
def patch_emitter(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a helper that pins ``doctor._resolve_emitter`` to a stub."""

    def _set(inspect_result: InspectResult) -> _StubEmitter:
        stub = _StubEmitter(inspect_result)
        monkeypatch.setattr(doctor, "_resolve_emitter", lambda: stub)
        return stub

    return _set


@pytest.fixture
def patch_hostname(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a helper that pins ``socket.gethostname()`` as seen by doctor."""

    def _set(hostname: str) -> None:
        monkeypatch.setattr(doctor, "gethostname", lambda: hostname)

    return _set


@pytest.fixture
def patch_now(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a helper that pins ``doctor._now()`` to a fixed datetime."""

    def _set(now: datetime) -> None:
        monkeypatch.setattr(doctor, "_now", lambda: now)

    return _set


@pytest.fixture
def patch_platform(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a helper that pins ``platform.system()`` for the disabled-hint branch."""

    def _set(system: str) -> None:
        monkeypatch.setattr(doctor, "_platform_system", lambda: system)

    return _set


# ---------------------------------------------------------------------------
# CT-15 — missing-file drift surfaces as a warning, exit 0
# ---------------------------------------------------------------------------


def test_ct15_doctor_reports_schedule_drift_as_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """Spec CT-15: schedule installed + plist removed → exit 0 + stdout has op + fix command."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    # Artifact path that does NOT exist on disk — simulates the user
    # having rm'd the plist out of band after the install was journaled.
    artifact_path = tmp_path / "fake-LaunchAgents" / "com.llm-wiki-kit.deadbeef.weekly-digest.plist"

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("missing-file")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    # The fix command embeds the operation name, so a single substring
    # assertion covers both "operation present" and "fix command present".
    assert "wiki schedule install weekly-digest" in captured.out
    # CT-15 explicitly: "Stderr is empty."
    assert captured.err == ""


# ---------------------------------------------------------------------------
# CT-17 — hostname rename produces the --machine <old> hint
# ---------------------------------------------------------------------------


def test_ct17_hostname_rename_surfaces_in_doctor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """Spec CT-17: machine_id='old-name' + gethostname='new-name' → exit 0 + both names + hint."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake-LaunchAgents" / "com.llm-wiki-kit.deadbeef.weekly-digest.plist"

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="old-name",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("new-name")
    # No current-host schedule, so emitter.inspect is never called; stub anyway.
    patch_emitter("loaded")

    journal_size_before = journal_path.stat().st_size

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "old-name" in captured.out
    assert "new-name" in captured.out
    assert "--machine old-name" in captured.out
    # Schedule warnings render to stdout, not stderr — spec
    # §"Doctor integration" pins the channel.
    assert captured.err == ""
    # CT-17 explicitly says "no journal write".
    assert journal_path.stat().st_size == journal_size_before


def test_ct17_emits_one_warning_per_distinct_old_hostname(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """Two schedules on the same old hostname collapse to one rename warning."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact = tmp_path / "fake" / "x.plist"

    append_event(
        journal_path,
        _install_event(operation="weekly-digest", machine_id="old-name", artifact_path=artifact),
    )
    append_event(
        journal_path,
        _install_event(operation="meal-planning", machine_id="old-name", artifact_path=artifact),
    )

    patch_hostname("new-name")
    patch_emitter("loaded")

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    # One rename warning total (collapsed by distinct old hostname),
    # not one per schedule.
    assert captured.out.count("--machine old-name") == 1


# ---------------------------------------------------------------------------
# Drift modes
# ---------------------------------------------------------------------------


def test_drift_disabled_macos_includes_launchctl_bootstrap_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_platform: Any,
) -> None:
    """``inspect`` returning 'not-loaded' on Darwin → warning naming launchctl bootstrap."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "com.llm-wiki-kit.deadbeef.weekly-digest.plist"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("<plist/>", encoding="utf-8")

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("not-loaded")
    patch_platform("Darwin")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "weekly-digest" in captured.out
    assert "launchctl bootstrap" in captured.out


def test_drift_disabled_linux_includes_systemctl_enable_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_platform: Any,
) -> None:
    """``inspect`` returning 'not-loaded' on Linux → warning naming systemctl --user enable."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "llm-wiki-kit-deadbeef-weekly-digest.timer"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("[Timer]\n", encoding="utf-8")

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("not-loaded")
    patch_platform("Linux")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "weekly-digest" in captured.out
    assert "systemctl --user enable" in captured.out


def test_drift_unknown_foreign_machine_emits_no_missing_or_disabled_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """A schedule with machine_id != current host does not trigger missing-file/disabled warnings.

    The ``unknown`` drift mode is the foreign-machine case: doctor can't
    introspect the other host. The hostname-rename warning (CT-17) still
    fires by spec — that's the one warning the foreign-machine path can
    produce. This test pins the *absence* of the per-host drift warnings,
    not the absence of the rename warning.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    foreign_artifact = tmp_path / "fake" / "other-box.plist"
    # Deliberately do NOT create the file — if doctor were checking
    # presence for foreign-machine schedules, this test would fail.

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="other-box",
            artifact_path=foreign_artifact,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("missing-file")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    # The "missing artifact at" + fix-command shape is the per-host
    # drift warning; it must NOT fire for a foreign-machine schedule.
    assert "missing artifact at" not in captured.out
    assert "wiki schedule install weekly-digest" not in captured.out


def test_uninstalled_schedule_emits_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """A schedule that was installed and then uninstalled emits no doctor warning.

    Pins the spec §"Doctor integration" filter: ``ScheduleInstalledEvent``
    "with no later ``ScheduleUninstalledEvent``" — a masked install
    drops out of the live set entirely.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "x.plist"

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )
    append_event(
        journal_path,
        ScheduleUninstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            removed_artifact=True,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("missing-file")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "weekly-digest" not in captured.out


# ---------------------------------------------------------------------------
# Exec-failure backlog
# ---------------------------------------------------------------------------


def test_exec_failure_backlog_no_events_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """Zero ``OperationExecFailedEvent``\\ s → no exec-failure-backlog warning."""

    vault = _vault(tmp_path)
    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "scheduled-exec failures" not in captured.out


def test_exec_failure_backlog_in_window_non_zero_exit_emits_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """One in-window ``non-zero-exit`` → one warning naming op + count + sidecar dir."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=2),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "weekly-digest" in captured.out
    assert "1 recent scheduled-exec failures" in captured.out
    assert "inbox/scheduled-failures/" in captured.out


def test_exec_failure_backlog_filters_out_binary_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """``reason='binary-missing'`` is filtered out — only non-zero-exit + timeout count."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason="binary-missing",
            timestamp=NOW - timedelta(days=1),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "scheduled-exec failures" not in captured.out


def test_exec_failure_backlog_filters_out_off_window_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """Events older than 7 days are filtered out."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=8),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "scheduled-exec failures" not in captured.out


def test_exec_failure_backlog_mixed_counts_in_window_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """3 non-zero-exit + 2 timeout in-window + 1 out-of-window → count is 5."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    for i in range(3):
        append_event(
            journal_path,
            _exec_failed_event(
                operation="weekly-digest",
                reason="non-zero-exit",
                timestamp=NOW - timedelta(days=i + 1),
            ),
        )
    for i in range(2):
        append_event(
            journal_path,
            _exec_failed_event(
                operation="weekly-digest",
                reason="timeout",
                timestamp=NOW - timedelta(days=i + 1),
            ),
        )
    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=10),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "5 recent scheduled-exec failures" in captured.out
    assert "weekly-digest" in captured.out


def test_exec_failure_backlog_groups_by_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """Different operations get separate warnings, each with its own count."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=1),
        ),
    )
    append_event(
        journal_path,
        _exec_failed_event(
            operation="meal-planning",
            reason="timeout",
            timestamp=NOW - timedelta(days=1),
        ),
    )
    append_event(
        journal_path,
        _exec_failed_event(
            operation="meal-planning",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=1),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "1 recent scheduled-exec failures for weekly-digest" in captured.out
    assert "2 recent scheduled-exec failures for meal-planning" in captured.out


@pytest.mark.parametrize("reason", ["conflict-refused", "skill-missing", "binary-missing"])
def test_exec_failure_backlog_filters_all_non_actionable_reasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
    reason: _ExecFailureReason,
) -> None:
    """Spec §"Doctor integration" — only ``non-zero-exit`` and ``timeout`` surface.

    ``conflict-refused`` is user-visible via the ``.proposed`` sidecar;
    ``binary-missing`` / ``skill-missing`` are reserved-but-not-emitted
    at v1. None of the three should produce an exec-failure-backlog
    warning even when they appear in-window on the journal.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="weekly-digest",
            reason=reason,
            timestamp=NOW - timedelta(days=1),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "scheduled-exec failures" not in captured.out


def test_exec_failure_backlog_at_window_boundary_inclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
    patch_now: Any,
) -> None:
    """Boundary: ``timestamp == NOW - 7 days`` is kept; one-second older drops.

    Pins the inclusive/exclusive boundary on the 7-day window so a
    future ``<`` / ``<=`` swap surfaces in CI rather than as a silent
    off-by-one. Implementation uses ``ts < cutoff`` so the exact-cutoff
    event is kept.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)

    append_event(
        journal_path,
        _exec_failed_event(
            operation="at-edge",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=7),
        ),
    )
    append_event(
        journal_path,
        _exec_failed_event(
            operation="just-past-edge",
            reason="non-zero-exit",
            timestamp=NOW - timedelta(days=7, seconds=1),
        ),
    )

    patch_hostname("this-box")
    patch_emitter("loaded")
    patch_now(NOW)

    monkeypatch.chdir(vault)
    cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert "1 recent scheduled-exec failures for at-edge" in captured.out
    assert "just-past-edge" not in captured.out


# ---------------------------------------------------------------------------
# Windows / unsupported-OS branches
# ---------------------------------------------------------------------------


def test_drift_not_inspectable_windows_emits_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """Windows v1: ``inspect`` returns ``not-inspectable`` → no warning.

    Spec §"Doctor integration" — Windows skips liveness, file-presence
    is the only signal at v1. The ``not-inspectable`` arm must NOT
    produce a ``schedule-disabled`` or ``schedule-missing-file`` warning
    when the artifact is on disk.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "win.xml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("<Task/>", encoding="utf-8")

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("not-inspectable")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "missing artifact" not in captured.out
    assert "not loaded" not in captured.out


def test_unsupported_os_fallback_still_detects_missing_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_hostname: Any,
) -> None:
    """When ``_resolve_emitter`` raises ``WikiError``, file-presence still surfaces drift.

    Doctor must degrade gracefully on an unsupported platform — see
    ``_check_schedules`` docstring + spec §"Edge cases / Running on
    an unsupported OS". File-only check still detects the missing
    artifact.
    """

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "missing.xml"
    # Deliberately do NOT create the file.

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")

    def _raise() -> Any:
        raise WikiError("scheduling is not supported on FreeBSD; see RFC-0003")

    monkeypatch.setattr(doctor, "_resolve_emitter", _raise)

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "wiki schedule install weekly-digest" in captured.out


# ---------------------------------------------------------------------------
# Mixed failure + warning: ordering + exit-code partition
# ---------------------------------------------------------------------------


def test_failure_plus_warning_renders_warnings_under_schedules_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """A non-schedule failure renders first; schedule warnings appear under ``Schedules:``."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "drift.plist"

    # Stale lock = non-schedule failure. ``LockAcquiredEvent`` is enough —
    # ``replay_state`` projects it into ``state.held_lock`` and the
    # subsequent ``check_stale_lock`` reads ``HeldLock.acquired_at``.
    append_event(
        journal_path,
        LockAcquiredEvent(
            timestamp=NOW - timedelta(hours=48),
            by="wiki-add",
            reason="long-gone",
        ),
    )
    # Schedule warning.
    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("missing-file")
    monkeypatch.setattr(doctor, "_now", lambda: NOW)

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    # Non-schedule failure still fails the doctor pass.
    assert exit_code == cli.DOCTOR_ISSUES_EXIT
    # Failure rendered first (stale-lock kind).
    stale_idx = captured.out.find("stale-lock")
    schedules_idx = captured.out.find("Schedules:")
    warning_idx = captured.out.find("wiki schedule install weekly-digest")
    assert stale_idx != -1
    assert schedules_idx != -1
    assert warning_idx != -1
    # Section header precedes the warning, and both come after the failure.
    assert stale_idx < schedules_idx < warning_idx


def test_only_warnings_exits_zero_with_schedules_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patch_emitter: Any,
    patch_hostname: Any,
) -> None:
    """No failures, only a schedule warning: exit 0 with ``Schedules:`` section."""

    vault = _vault(tmp_path)
    journal_path = _journal(vault)
    artifact_path = tmp_path / "fake" / "missing.plist"

    append_event(
        journal_path,
        _install_event(
            operation="weekly-digest",
            machine_id="this-box",
            artifact_path=artifact_path,
        ),
    )

    patch_hostname("this-box")
    patch_emitter("missing-file")

    monkeypatch.chdir(vault)
    exit_code = cli.main(["doctor"], kit_root=_minimal_kit(tmp_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Schedules:" in captured.out
    assert "wiki schedule install weekly-digest" in captured.out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_kit(tmp_path: Path) -> Path:
    """Create a minimum viable kit_root for doctor's primitive-missing check.

    Doctor's ``check_primitive_missing`` reads ``kit_root / "core"`` and
    ``kit_root / "templates"``. Tests for the Schedules section don't
    install primitives, so the smallest kit that doesn't trip
    primitive-missing is one whose ``core/primitive.yaml`` exists but
    isn't referenced by any journal event.
    """

    kit = tmp_path / "kit"
    if kit.exists():
        return kit
    (kit / "core").mkdir(parents=True)
    (kit / "core" / "primitive.yaml").write_text(
        "name: core\nversion: 0.0.0\nkind: infrastructure\ndescription: test\n",
        encoding="utf-8",
    )
    (kit / "templates").mkdir()
    return kit
