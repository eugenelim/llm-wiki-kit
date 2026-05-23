"""Tests for ``llm_wiki_kit.schedule.install``.

Spec coverage: CT-1, CT-2, CT-3, CT-4, CT-5, CT-6, CT-12, CT-18. The
CT → test-name mapping is in ``docs/specs/wiki-schedule/plan.md`` step
5. Most tests inject a stub ``_Emitter`` via monkeypatching
``llm_wiki_kit.schedule._resolve_emitter``; a small set use the real
``SystemdEmitter`` to pin the dual-write companion-then-primary
ordering against a regression to a hard-coded ``isinstance`` branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from llm_wiki_kit import schedule
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    PrimitiveInstallEvent,
    ScheduleInstalledEvent,
    VaultInitEvent,
)
from llm_wiki_kit.schedule._emitter import InspectResult
from llm_wiki_kit.schedule.dsl import ResolvedCadence
from llm_wiki_kit.schedule.systemd import SystemdEmitter, service_path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Test fixtures + stub emitter
# ---------------------------------------------------------------------------


@dataclass
class _StubEmitter:
    """Configurable stub ``_Emitter`` for orchestrator tests.

    Records every Protocol method call so tests can assert
    invocation counts and orderings. ``activate_raises`` triggers
    the CT-12 activation-failure path; ``activate_pre_assert``
    runs at the top of ``activate()`` and lets CT-12 pin the
    "write happened before activate" ordering invariant.
    """

    base_dir: Path
    activate_raises: WikiError | None = None
    activate_pre_assert: Any = None
    install_instruction_text: str | None = None
    uninstall_instruction_text: str | None = None
    render_artifact_calls: list[dict[str, Any]] = field(default_factory=list)
    activate_calls: list[Path] = field(default_factory=list)
    deactivate_calls: list[Path] = field(default_factory=list)
    companion_artifacts_calls: list[dict[str, Any]] = field(default_factory=list)

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        return self.base_dir / f"{vault_id}.{operation}.stub"

    def render_artifact(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> bytes:
        self.render_artifact_calls.append(
            {
                "operation": operation,
                "vault_root": vault_root,
                "vault_id": vault_id,
                "cadence": cadence,
                "exec_command": exec_command,
            }
        )
        return f"stub artifact {operation} {cadence}".encode()

    def companion_artifacts(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> list[tuple[Path, str | bytes]]:
        self.companion_artifacts_calls.append(
            {
                "operation": operation,
                "vault_root": vault_root,
                "vault_id": vault_id,
                "cadence": cadence,
                "exec_command": exec_command,
            }
        )
        return []

    def install_instruction(self, artifact_path: Path) -> str | None:
        return self.install_instruction_text

    def uninstall_instruction(self, artifact_path: Path) -> str | None:
        return self.uninstall_instruction_text

    def activate(self, artifact_path: Path) -> None:
        self.activate_calls.append(artifact_path)
        if self.activate_pre_assert is not None:
            self.activate_pre_assert(artifact_path)
        if self.activate_raises is not None:
            raise self.activate_raises

    def deactivate(self, artifact_path: Path) -> None:
        self.deactivate_calls.append(artifact_path)

    def inspect(self, artifact_path: Path) -> InspectResult:
        if not artifact_path.exists():
            return "missing-file"
        return "loaded"


def _make_vault(tmp_path: Path, operation: str = "weekly-digest") -> tuple[Path, Path]:
    """Build a minimal vault with the operation marked as installed."""

    vault = tmp_path / "vault"
    vault.mkdir()
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir()
    journal_path = journal_dir / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=NOW,
            by="wiki-init",
            vault_name="test-vault",
            recipe="minimal",
        ),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW,
            by="wiki-init",
            primitive=operation,
            version="0.1.0",
        ),
    )
    return vault, journal_path


@pytest.fixture
def stub_emitter(tmp_path: Path) -> _StubEmitter:
    return _StubEmitter(base_dir=tmp_path / "stub-artifacts")


@pytest.fixture
def install_with_stub(stub_emitter: _StubEmitter, monkeypatch: pytest.MonkeyPatch) -> _StubEmitter:
    """Force `_resolve_emitter` to return the stub for the duration of the test."""
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: stub_emitter)
    return stub_emitter


# ---------------------------------------------------------------------------
# CT-1: install happy path
# ---------------------------------------------------------------------------


def test_install_journals_event_writes_artifact_and_prints_summary(
    tmp_path: Path,
    install_with_stub: _StubEmitter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    # Exactly one ScheduleInstalledEvent.
    events = list(read_events(journal_path))
    install_events = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert len(install_events) == 1
    event = install_events[0]
    assert event.operation == "weekly-digest"
    assert event.machine_id == "this-box"
    assert event.cadence_dsl == "SUN 09:00"  # weekly default per spec table.
    assert event.exec_command[1:] == ["run", "--exec", "weekly-digest"]

    # Artifact file exists at the journaled path.
    assert result.os_artifact_path.exists()

    # Result carries the journaled fields back to the caller.
    assert result.machine_id == "this-box"
    assert result.cadence_dsl == "SUN 09:00"
    assert result.already_installed is False
    assert result.install_instruction is None  # stub returned None


# ---------------------------------------------------------------------------
# CT-2: --at override → canonical DSL
# ---------------------------------------------------------------------------


def test_install_with_at_override_records_canonical_dsl(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    schedule.install(
        "weekly-digest",
        at="tue 18:00",  # lowercase input
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    events = list(read_events(journal_path))
    install_events = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert len(install_events) == 1
    assert install_events[0].cadence_dsl == "TUE 18:00"  # canonical uppercase

    # The cadence handed to the emitter has day_of_week=2 (TUE), hour=18, minute=0.
    assert len(install_with_stub.render_artifact_calls) == 1
    cadence = install_with_stub.render_artifact_calls[0]["cadence"]
    assert cadence.period == "weekly"
    assert cadence.day_of_week == 2
    assert cadence.hour == 18
    assert cadence.minute == 0


# ---------------------------------------------------------------------------
# CT-3: refuse on-demand period
# ---------------------------------------------------------------------------


def test_install_refuses_on_demand_period(tmp_path: Path, install_with_stub: _StubEmitter) -> None:
    vault, journal_path = _make_vault(tmp_path, operation="onboarding-pack")
    with pytest.raises(WikiError, match="on-demand"):
        schedule.install(
            "onboarding-pack",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )
    # No install event journaled.
    events = list(read_events(journal_path))
    assert not any(isinstance(e, ScheduleInstalledEvent) for e in events)


def test_install_refuses_on_demand_period_even_with_at_override(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    """Spec §"install happy path" step 4 puts the period gate BEFORE the
    DSL-resolution step, so ``--at`` cannot rescue an operation that
    declared no cadence."""
    vault, journal_path = _make_vault(tmp_path, operation="onboarding-pack")
    with pytest.raises(WikiError, match="on-demand"):
        schedule.install(
            "onboarding-pack",
            at="daily 09:00",
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )
    events = list(read_events(journal_path))
    assert not any(isinstance(e, ScheduleInstalledEvent) for e in events)


# ---------------------------------------------------------------------------
# CT-4: refuse cron strings via --at
# ---------------------------------------------------------------------------


def test_install_refuses_cron_string_via_at_flag(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    with pytest.raises(WikiError, match="unrecognised cadence DSL"):
        schedule.install(
            "weekly-digest",
            at="0 9 * * 0",
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )
    events = list(read_events(journal_path))
    assert not any(isinstance(e, ScheduleInstalledEvent) for e in events)


# ---------------------------------------------------------------------------
# CT-5: idempotent re-install on identical cadence — zero new events
# ---------------------------------------------------------------------------


def test_install_idempotent_on_identical_cadence(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )
    lines_after_first = journal_path.read_text(encoding="utf-8").splitlines()

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    # Snapshot the full journal-line count: zero new events of any
    # type (no lock-pair either; spec §Invariants
    # "Idempotent-no-op emits zero events of any type").
    lines_after_second = journal_path.read_text(encoding="utf-8").splitlines()
    assert lines_after_second == lines_after_first
    assert result.already_installed is True


# ---------------------------------------------------------------------------
# CT-6: refuse re-install on different cadence
# ---------------------------------------------------------------------------


def test_install_refuses_changed_cadence_without_uninstall(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )
    with pytest.raises(WikiError, match="uninstall first"):
        schedule.install(
            "weekly-digest",
            at="MON 09:00",
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )

    # Only one install event survives.
    events = list(read_events(journal_path))
    install_events = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert len(install_events) == 1
    assert install_events[0].cadence_dsl == "SUN 09:00"


# ---------------------------------------------------------------------------
# CT-12: activation failure leaves no install event; primary unlinked
# ---------------------------------------------------------------------------


def test_install_does_not_journal_when_activation_fails(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)

    captured_path_state: dict[str, bool] = {}

    def _assert_artifact_exists_on_entry(artifact_path: Path) -> None:
        # Pins the "write → activate" ordering: the primary artifact
        # must exist on disk by the time activate() runs.
        captured_path_state["exists_on_activate"] = artifact_path.exists()

    install_with_stub.activate_pre_assert = _assert_artifact_exists_on_entry
    install_with_stub.activate_raises = WikiError("simulated activation failure")

    with pytest.raises(WikiError, match="simulated"):
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )

    # The artifact existed at the moment activate() was called.
    assert captured_path_state["exists_on_activate"] is True

    events = list(read_events(journal_path))
    # No install event.
    assert not any(isinstance(e, ScheduleInstalledEvent) for e in events)
    # Lock pair is present (the transaction still ran).
    event_types = [e.type for e in events]
    assert "lock.acquired" in event_types
    assert "lock.released" in event_types
    # The primary artifact was unlinked on best-effort cleanup.
    artifact_path = install_with_stub.artifact_path(schedule._vault_id(vault), "weekly-digest")
    assert not artifact_path.exists()


# ---------------------------------------------------------------------------
# Systemd activation-failure leaves the .service companion on disk
# (pins CT-12's systemd-specific clause)
# ---------------------------------------------------------------------------


def test_install_systemd_activation_failure_leaves_service_companion_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    emitter = SystemdEmitter()
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: emitter)

    def _raise(self: SystemdEmitter, timer_path: Path) -> None:
        raise WikiError("simulated systemctl failure")

    monkeypatch.setattr(SystemdEmitter, "activate", _raise)

    with pytest.raises(WikiError, match="simulated"):
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=journal_path,
            now=NOW,
        )

    timer_path = emitter.artifact_path(schedule._vault_id(vault), "weekly-digest")
    sp = service_path(timer_path)
    # Primary (.timer) unlinked on cleanup; companion (.service)
    # left on disk as harmless orphan.
    assert not timer_path.exists()
    assert sp.exists()
    # No install event.
    events = list(read_events(journal_path))
    assert not any(isinstance(e, ScheduleInstalledEvent) for e in events)


# ---------------------------------------------------------------------------
# Systemd ordering: write companions → write primary → activate
# (also pins that the orchestrator routes through `companion_artifacts`
# rather than a hard-coded systemd-specific branch — the recorded call
# log includes BOTH companion + primary writes from one `_Emitter`
# instance's Protocol surface)
# ---------------------------------------------------------------------------


def test_install_systemd_writes_companion_then_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    emitter = SystemdEmitter()
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: emitter)

    calls: list[tuple[str, Path]] = []

    from llm_wiki_kit.write_helper import write_os_artifact as _real_write

    def _spy_write(path: Path, content: str | bytes, *, vault_root: Path) -> None:
        calls.append(("write", path))
        _real_write(path, content, vault_root=vault_root)

    monkeypatch.setattr("llm_wiki_kit.schedule.write_os_artifact", _spy_write)

    def _activate_recorder(self: SystemdEmitter, timer_path: Path) -> None:
        calls.append(("activate", timer_path))

    monkeypatch.setattr(SystemdEmitter, "activate", _activate_recorder)

    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    timer_path = emitter.artifact_path(schedule._vault_id(vault), "weekly-digest")
    sp = service_path(timer_path)
    assert calls == [("write", sp), ("write", timer_path), ("activate", timer_path)]
    assert sp.exists()
    assert timer_path.exists()


# ---------------------------------------------------------------------------
# CT-18: exec_command resolution prefers shutil.which over sys.argv[0]
# ---------------------------------------------------------------------------


def test_install_exec_command_prefers_shutil_which_over_argv0(
    tmp_path: Path, install_with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wiki_stub = bin_dir / "wiki"
    wiki_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wiki_stub.chmod(0o755)

    # Restrict PATH so shutil.which deterministically returns our stub.
    monkeypatch.setenv("PATH", str(bin_dir))

    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    events = list(read_events(journal_path))
    install_events = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert install_events[0].exec_command[0] == str(wiki_stub)
    assert install_events[0].exec_command[1:] == ["run", "--exec", "weekly-digest"]


# ---------------------------------------------------------------------------
# Windows install_instruction lifts into the result
# ---------------------------------------------------------------------------


def test_install_result_carries_install_instruction_from_emitter(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    install_with_stub.install_instruction_text = (
        'schtasks /Create /XML "/tmp/x.xml" /TN "stub-task"'
    )
    vault, journal_path = _make_vault(tmp_path)
    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )
    assert result.install_instruction is not None
    assert "schtasks /Create /XML" in result.install_instruction


# ---------------------------------------------------------------------------
# Vault check
# ---------------------------------------------------------------------------


def test_install_refuses_non_vault_directory(
    tmp_path: Path, install_with_stub: _StubEmitter
) -> None:
    vault = tmp_path / "not-a-vault"
    vault.mkdir()
    with pytest.raises(WikiError, match="not a wiki vault"):
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=REPO_ROOT,
            journal_path=vault / ".wiki.journal" / "journal.jsonl",
            now=NOW,
        )
