"""Tests for ``llm_wiki_kit.schedule.uninstall``.

Spec coverage: CT-7, CT-8, CT-9, CT-16, plus the idempotent-double-
uninstall and Windows uninstall-instruction lift cases pinned in
``docs/specs/wiki-schedule/plan.md`` step 5.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from llm_wiki_kit import schedule
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    PrimitiveInstallEvent,
    ScheduleUninstalledEvent,
    VaultInitEvent,
)
from llm_wiki_kit.schedule._emitter import InspectResult

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC)


class _StubEmitter:
    """Same shape as the install-test stub; recorded here for symmetry."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.activate_calls: list[Path] = []
        self.deactivate_calls: list[Path] = []
        self.install_instruction_text: str | None = None
        self.uninstall_instruction_text: str | None = None

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        return self.base_dir / f"{vault_id}.{operation}.stub"

    def render_artifact(self, **kwargs: Any) -> bytes:
        return b"stub"

    def companion_artifacts(self, **kwargs: Any) -> list[tuple[Path, str | bytes]]:
        return []

    def install_instruction(self, artifact_path: Path) -> str | None:
        return self.install_instruction_text

    def uninstall_instruction(self, artifact_path: Path) -> str | None:
        return self.uninstall_instruction_text

    def activate(self, artifact_path: Path) -> None:
        self.activate_calls.append(artifact_path)

    def deactivate(self, artifact_path: Path) -> None:
        self.deactivate_calls.append(artifact_path)

    def inspect(self, artifact_path: Path) -> InspectResult:
        if not artifact_path.exists():
            return "missing-file"
        return "loaded"


def _make_vault(tmp_path: Path) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir()
    journal_path = journal_dir / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="test-vault", recipe="minimal"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW, by="wiki-init", primitive="weekly-digest", version="0.1.0"
        ),
    )
    return vault, journal_path


@pytest.fixture
def stub_emitter(tmp_path: Path) -> _StubEmitter:
    return _StubEmitter(base_dir=tmp_path / "stub-artifacts")


@pytest.fixture
def with_stub(stub_emitter: _StubEmitter, monkeypatch: pytest.MonkeyPatch) -> _StubEmitter:
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: stub_emitter)
    return stub_emitter


def _install_first(vault: Path, journal_path: Path, machine: str = "this-host") -> None:
    schedule.install(
        "weekly-digest",
        at=None,
        machine=machine,
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )


# ---------------------------------------------------------------------------
# CT-7: uninstall removes file + journals event
# ---------------------------------------------------------------------------


def test_uninstall_deletes_artifact_and_journals_event(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    # Pretend we're on the host we install for.
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    _install_first(vault, journal_path, machine="this-host")

    artifact_path = with_stub.artifact_path(schedule._vault_id(vault), "weekly-digest")
    assert artifact_path.exists()

    result = schedule.uninstall(
        "weekly-digest",
        machine="this-host",
        vault_root=vault,
        journal_path=journal_path,
        now=NOW,
    )

    assert not artifact_path.exists()
    assert result.removed_artifact is True
    assert result.foreign_machine is False
    # The emitter's deactivate was invoked (current host).
    assert with_stub.deactivate_calls == [artifact_path]

    events = list(read_events(journal_path))
    uninstall_events = [e for e in events if isinstance(e, ScheduleUninstalledEvent)]
    assert len(uninstall_events) == 1
    assert uninstall_events[0].removed_artifact is True


# ---------------------------------------------------------------------------
# CT-8: uninstall succeeds when file already missing (drift)
# ---------------------------------------------------------------------------


def test_uninstall_succeeds_when_artifact_already_missing(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    _install_first(vault, journal_path, machine="this-host")
    artifact_path = with_stub.artifact_path(schedule._vault_id(vault), "weekly-digest")
    artifact_path.unlink()  # out-of-band rm
    assert not artifact_path.exists()

    result = schedule.uninstall(
        "weekly-digest",
        machine="this-host",
        vault_root=vault,
        journal_path=journal_path,
        now=NOW,
    )
    assert result.removed_artifact is False

    events = list(read_events(journal_path))
    uninstall_events = [e for e in events if isinstance(e, ScheduleUninstalledEvent)]
    assert len(uninstall_events) == 1
    assert uninstall_events[0].removed_artifact is False


# ---------------------------------------------------------------------------
# CT-9: uninstall refuses when no install event exists
# ---------------------------------------------------------------------------


def test_uninstall_refuses_when_no_install_event_exists(
    tmp_path: Path, with_stub: _StubEmitter
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    with pytest.raises(WikiError, match="no schedule installed"):
        schedule.uninstall(
            "weekly-digest",
            machine="this-host",
            vault_root=vault,
            journal_path=journal_path,
            now=NOW,
        )
    events = list(read_events(journal_path))
    assert not any(isinstance(e, ScheduleUninstalledEvent) for e in events)


# ---------------------------------------------------------------------------
# Double-uninstall (idempotent refusal via masking ScheduleUninstalledEvent)
# ---------------------------------------------------------------------------


def test_uninstall_twice_refuses_second_call(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    _install_first(vault, journal_path, machine="this-host")
    schedule.uninstall(
        "weekly-digest",
        machine="this-host",
        vault_root=vault,
        journal_path=journal_path,
        now=NOW,
    )
    with pytest.raises(WikiError, match="no schedule installed"):
        schedule.uninstall(
            "weekly-digest",
            machine="this-host",
            vault_root=vault,
            journal_path=journal_path,
            now=NOW,
        )
    # Exactly one ScheduleUninstalledEvent across the pair.
    events = list(read_events(journal_path))
    uninstall_events = [e for e in events if isinstance(e, ScheduleUninstalledEvent)]
    assert len(uninstall_events) == 1


# ---------------------------------------------------------------------------
# CT-16: foreign-machine uninstall skips OS-side calls
# ---------------------------------------------------------------------------


def test_uninstall_foreign_machine_skips_os_deactivation(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    # Install on a foreign machine.
    monkeypatch.setattr(socket, "gethostname", lambda: "other-box")
    _install_first(vault, journal_path, machine="other-box")
    # The install above wrote the stub artifact at this-host's filesystem
    # because the stub uses the same base_dir regardless of machine. Pre-
    # create a sentinel file at the journaled path (it already exists from
    # install) — assert it stays untouched after a foreign-machine uninstall.
    artifact_path = with_stub.artifact_path(schedule._vault_id(vault), "weekly-digest")
    assert artifact_path.exists()
    sentinel_bytes = artifact_path.read_bytes()

    # Now flip the host back: from this-host, run uninstall --machine other-box.
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    with_stub.deactivate_calls.clear()

    result = schedule.uninstall(
        "weekly-digest",
        machine="other-box",
        vault_root=vault,
        journal_path=journal_path,
        now=NOW,
    )

    assert result.foreign_machine is True
    assert result.removed_artifact is False
    # Local emitter never called.
    assert with_stub.deactivate_calls == []
    # Artifact at journaled path is untouched.
    assert artifact_path.exists()
    assert artifact_path.read_bytes() == sentinel_bytes

    events = list(read_events(journal_path))
    uninstall_events = [e for e in events if isinstance(e, ScheduleUninstalledEvent)]
    assert len(uninstall_events) == 1
    assert uninstall_events[0].machine_id == "other-box"
    assert uninstall_events[0].removed_artifact is False


# ---------------------------------------------------------------------------
# Windows uninstall_instruction lifts into the result
# ---------------------------------------------------------------------------


def test_uninstall_result_carries_uninstall_instruction_from_emitter(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    _install_first(vault, journal_path, machine="this-host")
    with_stub.uninstall_instruction_text = 'schtasks /Delete /TN "stub-task" /F'

    result = schedule.uninstall(
        "weekly-digest",
        machine="this-host",
        vault_root=vault,
        journal_path=journal_path,
        now=NOW,
    )
    assert result.uninstall_instruction is not None
    assert "schtasks /Delete" in result.uninstall_instruction
