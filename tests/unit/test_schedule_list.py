"""Tests for ``llm_wiki_kit.schedule.list_schedules``.

Spec coverage: CT-10, CT-11, CT-13. Lists are read-only — no journal
writes; assertions are on the returned ``ScheduleStatus`` rows.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from llm_wiki_kit import schedule
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import PrimitiveInstallEvent, VaultInitEvent
from llm_wiki_kit.schedule._emitter import InspectResult

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC)


class _StubEmitter:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        return self.base_dir / f"{vault_id}.{operation}.stub"

    def render_artifact(self, **kwargs: Any) -> bytes:
        return b"stub"

    def companion_artifacts(self, **kwargs: Any) -> list[tuple[Path, str | bytes]]:
        return []

    def install_instruction(self, artifact_path: Path) -> str | None:
        return None

    def uninstall_instruction(self, artifact_path: Path) -> str | None:
        return None

    def activate(self, artifact_path: Path) -> None:
        pass

    def deactivate(self, artifact_path: Path) -> None:
        pass

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


# ---------------------------------------------------------------------------
# CT-10: list reflects journal + disk
# ---------------------------------------------------------------------------


def test_list_ok_then_drift_after_artifact_rm(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-host",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    rows = schedule.list_schedules(
        machine=None,
        all_machines=False,
        vault_root=vault,
        journal_path=journal_path,
    )
    assert len(rows) == 1
    assert rows[0].operation == "weekly-digest"
    assert rows[0].machine_id == "this-host"
    assert rows[0].status == "ok"

    # Out-of-band rm of the artifact.
    artifact = with_stub.artifact_path(schedule._vault_id(vault), "weekly-digest")
    artifact.unlink()

    rows_after = schedule.list_schedules(
        machine=None,
        all_machines=False,
        vault_root=vault,
        journal_path=journal_path,
    )
    assert len(rows_after) == 1
    assert rows_after[0].status == "drift:missing-file"


# ---------------------------------------------------------------------------
# CT-11: list on a non-vault directory raises
# ---------------------------------------------------------------------------


def test_list_refuses_non_vault_directory(tmp_path: Path, with_stub: _StubEmitter) -> None:
    not_a_vault = tmp_path / "not-a-vault"
    not_a_vault.mkdir()
    with pytest.raises(WikiError, match="not a wiki vault"):
        schedule.list_schedules(
            machine=None,
            all_machines=False,
            vault_root=not_a_vault,
            journal_path=not_a_vault / ".wiki.journal" / "journal.jsonl",
        )


# ---------------------------------------------------------------------------
# CT-13: machine_id propagation + --all-machines filter
# ---------------------------------------------------------------------------


def test_list_machine_filter_and_all_machines_flag(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    schedule.install(
        "weekly-digest",
        at=None,
        machine="other-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=NOW,
    )

    # Default: current host only — foreign-machine row hidden.
    rows_default = schedule.list_schedules(
        machine=None,
        all_machines=False,
        vault_root=vault,
        journal_path=journal_path,
    )
    assert rows_default == []

    # --all-machines: foreign row appears with STATUS=unknown.
    rows_all = schedule.list_schedules(
        machine=None,
        all_machines=True,
        vault_root=vault,
        journal_path=journal_path,
    )
    assert len(rows_all) == 1
    assert rows_all[0].machine_id == "other-box"
    assert rows_all[0].status == "unknown"


# ---------------------------------------------------------------------------
# CT-20: list rows carry the journaled agent so the CLI can render the column
# ---------------------------------------------------------------------------


def test_schedule_list_renders_agent_column(
    tmp_path: Path, with_stub: _StubEmitter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-20: two installed schedules, one with agent + one without.

    The ``ScheduleStatus`` rows carry the journaled ``agent`` so the
    CLI's stdout renderer can put ``household-manager`` in the AGENT
    column for the first row and ``—`` for the second.
    """

    from llm_wiki_kit.models import ScheduleInstalledEvent

    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")

    # Hand-write two install events to bypass the resolution chain
    # (this test pins read-side surfacing, not resolution).
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW, by="wiki-init", primitive="meal-planning", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-host",
            cadence_dsl="SUN 09:00",
            os_artifact_path=str(with_stub.artifact_path("vid", "weekly-digest")),
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent=None,
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="meal-planning",
            machine_id="this-host",
            cadence_dsl="SUN 10:00",
            os_artifact_path=str(with_stub.artifact_path("vid", "meal-planning")),
            exec_command=[
                "/usr/local/bin/wiki",
                "run",
                "--exec",
                "meal-planning",
                "--agent",
                "household-manager",
            ],
            agent="household-manager",
        ),
    )

    rows = schedule.list_schedules(
        machine=None,
        all_machines=False,
        vault_root=vault,
        journal_path=journal_path,
    )

    by_op = {row.operation: row for row in rows}
    assert by_op["weekly-digest"].agent is None
    assert by_op["meal-planning"].agent == "household-manager"


def test_cli_schedule_list_renders_agent_column_with_em_dash(
    tmp_path: Path,
    with_stub: _StubEmitter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CT-20 rendered: the AGENT column appears between CADENCE and ARTIFACT;
    ``—`` (U+2014) renders for ``None``, the agent name renders otherwise.

    Pins the CLI's stdout TSV layout — column header, em-dash sentinel,
    and ordering. The data-layer test
    (``test_schedule_list_renders_agent_column``) covers the
    ``ScheduleStatus.agent`` field; this one covers the rendered table.
    """

    from llm_wiki_kit import cli
    from llm_wiki_kit.models import ScheduleInstalledEvent

    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW, by="wiki-init", primitive="meal-planning", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-host",
            cadence_dsl="SUN 09:00",
            os_artifact_path=str(with_stub.artifact_path("vid", "weekly-digest")),
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent=None,
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="meal-planning",
            machine_id="this-host",
            cadence_dsl="SUN 10:00",
            os_artifact_path=str(with_stub.artifact_path("vid", "meal-planning")),
            exec_command=[
                "/usr/local/bin/wiki",
                "run",
                "--exec",
                "meal-planning",
                "--agent",
                "household-manager",
            ],
            agent="household-manager",
        ),
    )

    monkeypatch.chdir(vault)
    exit_code = cli.main(["schedule", "list"], kit_root=REPO_ROOT)
    assert exit_code == 0

    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    # Header carries the new AGENT column between CADENCE and ARTIFACT.
    assert lines[0] == "OPERATION\tMACHINE\tCADENCE\tAGENT\tARTIFACT\tSTATUS"

    rows_by_op = {line.split("\t")[0]: line.split("\t") for line in lines[1:]}
    # meal-planning row has the agent name in column index 3.
    assert rows_by_op["meal-planning"][3] == "household-manager"
    # weekly-digest row renders the em-dash sentinel.
    assert rows_by_op["weekly-digest"][3] == "—"  # U+2014 em-dash
