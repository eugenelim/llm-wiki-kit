"""Tests for ``wiki doctor`` agent checks (RFC-0004 wiki-agents PR-6).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-21: ``wiki doctor`` warns on missing AGENT.md for a schedule whose
  bound agent name still references the file on the current host.
- CT-22: ``wiki doctor`` warns when an agent was upgraded since the last
  ``OperationRunByAgentEvent`` (or with no run-by-agent at all).
- Negative path: zero warnings when no schedule references an agent and
  no upgrade has happened.

The two checks share a single journal walk in ``doctor._check_agents``;
the tests assert the *warning shape* (`is_warning=True`, kind prefix
``agent-``, exit code 0 from the CLI), not the internal split.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.doctor import (
    AGENT_BINDING_MISSING,
    AGENT_VERSION_DRIFT,
    _check_agents,
    run_doctor,
)
from llm_wiki_kit.journal import append_event, read_events, replay_state
from llm_wiki_kit.models import (
    OperationRunByAgentEvent,
    PrimitiveInstallEvent,
    PrimitiveUpgradeEvent,
    ScheduleInstalledEvent,
    VaultInitEvent,
)

NOW = datetime(2026, 5, 24, 9, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 5, 25, 9, 0, 0, tzinfo=UTC)
EARLIER = datetime(2026, 5, 23, 9, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixture builders (same shape as test_cmd_agents)
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _build_kit_root(
    tmp_path: Path,
    *,
    operations: tuple[str, ...] = ("weekly-digest",),
    agents: tuple[str, ...] = ("household-manager",),
) -> Path:
    kit_root = tmp_path / "kit-root"
    _write_yaml(
        kit_root / "core" / "primitive.yaml",
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
    )
    for op_name in operations:
        _write_yaml(
            kit_root / "templates" / "operations" / op_name / "primitive.yaml",
            f"name: {op_name}\nkind: operation\nversion: 0.1.0\ndescription: {op_name}.\n",
        )
        _write_yaml(
            kit_root / "templates" / "operations" / op_name / "contract.yaml",
            f"name: {op_name}\ndescription: {op_name}.\nperiod: weekly\nskill: {op_name}\n",
        )
    for agent_name in agents:
        _write_yaml(
            kit_root / "templates" / "agents" / agent_name / "primitive.yaml",
            f"name: {agent_name}\nkind: agent\nversion: 0.1.0\ndescription: {agent_name}.\n",
        )
    return kit_root


def _seed_vault(tmp_path: Path) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir()
    return vault, journal_dir / "journal.jsonl"


def _write_agent_md(vault: Path, agent_name: str) -> Path:
    path = vault / ".claude" / "agents" / agent_name / "AGENT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {agent_name}\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CT-21 — bindings warning when AGENT.md is missing
# ---------------------------------------------------------------------------


def test_doctor_warns_on_missing_agent_md_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-21: schedule bound to ``household-manager`` + AGENT.md deleted
    out-of-band → one ``agent-binding-missing`` warning, exit 0.

    Pins the spec contract that ``wiki doctor`` reads zero bytes of
    AGENT.md — only ``path.is_file()`` is consulted. The test deletes
    the file (never reads it) and asserts the warning fires.
    """

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)

    # Vault-init + primitive installs + schedule install bound to the agent.
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="vault", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    # AGENT.md is intentionally absent — never written.

    issues = run_doctor(vault, kit_root)
    bindings = [i for i in issues if i.kind == AGENT_BINDING_MISSING]
    assert len(bindings) == 1
    only = bindings[0]
    assert only.is_warning is True
    assert "household-manager" in only.detail
    assert "wiki add agent:household-manager" in only.detail
    assert str(vault / ".claude" / "agents" / "household-manager" / "AGENT.md") in only.detail


def test_doctor_silent_when_agent_md_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative path: AGENT.md present → no ``agent-binding-missing`` warning."""

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    _write_agent_md(vault, "household-manager")

    issues = run_doctor(vault, kit_root)
    assert [i for i in issues if i.kind == AGENT_BINDING_MISSING] == []


def test_doctor_bindings_skipped_on_other_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bindings check only fires on the current host (machine_id match).

    Pins spec §Outputs ``wiki doctor`` — "for each schedule entry with
    ``agent`` set and ``machine_id == socket.gethostname()``". A
    schedule from a different host doesn't surface as a bindings
    warning (it surfaces via the hostname-rename check, which is the
    Schedules section's job).
    """

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="other-box",  # different host
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    issues = run_doctor(vault, kit_root)
    assert [i for i in issues if i.kind == AGENT_BINDING_MISSING] == []


# ---------------------------------------------------------------------------
# CT-22 — version-drift warning
# ---------------------------------------------------------------------------


def test_doctor_warns_on_agent_upgrade_since_last_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-22: ``PrimitiveUpgradeEvent`` after the most recent
    ``OperationRunByAgentEvent`` → one ``agent-version-drift`` warning
    containing old/new versions and bound operations."""

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)

    append_event(
        journal_path,
        VaultInitEvent(timestamp=EARLIER, by="wiki-init", vault_name="v", recipe="family"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="weekly-digest", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="household-manager", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=EARLIER,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    # AGENT.md present so the bindings check stays quiet — we want
    # to assert ONLY the drift warning here.
    _write_agent_md(vault, "household-manager")

    # One run-by-agent, then an upgrade after it.
    append_event(
        journal_path,
        OperationRunByAgentEvent(
            timestamp=NOW,
            by="wiki-run",
            operation="weekly-digest",
            agent="household-manager",
            event_id="abc123abc123",
        ),
    )
    append_event(
        journal_path,
        PrimitiveUpgradeEvent(
            timestamp=LATER,
            by="wiki-upgrade",
            primitive="household-manager",
            from_version="0.1.0",
            to_version="0.2.0",
        ),
    )

    issues = run_doctor(vault, kit_root)
    drifts = [i for i in issues if i.kind == AGENT_VERSION_DRIFT]
    assert len(drifts) == 1
    only = drifts[0]
    assert only.is_warning is True
    assert "household-manager" in only.detail
    assert "0.1.0" in only.detail
    assert "0.2.0" in only.detail
    assert "weekly-digest" in only.detail  # bound operations


def test_doctor_drift_silent_when_run_after_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run-by-agent AFTER the upgrade → no drift warning."""

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=EARLIER, by="wiki-init", vault_name="v", recipe="family"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="weekly-digest", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="household-manager", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=EARLIER,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    _write_agent_md(vault, "household-manager")
    # Upgrade first, then a fresh run-by-agent — caller has acknowledged.
    append_event(
        journal_path,
        PrimitiveUpgradeEvent(
            timestamp=NOW,
            by="wiki-upgrade",
            primitive="household-manager",
            from_version="0.1.0",
            to_version="0.2.0",
        ),
    )
    append_event(
        journal_path,
        OperationRunByAgentEvent(
            timestamp=LATER,
            by="wiki-run",
            operation="weekly-digest",
            agent="household-manager",
            event_id="abc123abc123",
        ),
    )

    issues = run_doctor(vault, kit_root)
    assert [i for i in issues if i.kind == AGENT_VERSION_DRIFT] == []


def test_doctor_drift_warns_when_no_run_after_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upgrade present + zero run-by-agent events → drift fires."""

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=EARLIER, by="wiki-init", vault_name="v", recipe="family"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="weekly-digest", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=EARLIER, by="wiki-init", primitive="household-manager", version="0.1.0"
        ),
    )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=EARLIER,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    _write_agent_md(vault, "household-manager")
    append_event(
        journal_path,
        PrimitiveUpgradeEvent(
            timestamp=LATER,
            by="wiki-upgrade",
            primitive="household-manager",
            from_version="0.1.0",
            to_version="0.2.0",
        ),
    )

    issues = run_doctor(vault, kit_root)
    drifts = [i for i in issues if i.kind == AGENT_VERSION_DRIFT]
    assert len(drifts) == 1
    assert "0.1.0" in drifts[0].detail
    assert "0.2.0" in drifts[0].detail


# ---------------------------------------------------------------------------
# Negative path — agent never bound + never upgraded → silent
# ---------------------------------------------------------------------------


def test_doctor_silent_when_no_agents_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed agent primitive that's never been bound to a
    schedule or produced a run-by-agent → zero agent warnings.

    Pins spec §Outputs ``wiki doctor`` — "Suppressed when the agent
    has never been bound to a still-active schedule or run."
    """

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    # Even an upgrade with no run-by-agent stays silent when no schedule
    # binds the agent — the agent isn't in use.
    append_event(
        journal_path,
        PrimitiveUpgradeEvent(
            timestamp=LATER,
            by="wiki-upgrade",
            primitive="household-manager",
            from_version="0.1.0",
            to_version="0.2.0",
        ),
    )

    issues = run_doctor(vault, kit_root)
    agent_warnings = [i for i in issues if i.kind.startswith("agent-")]
    assert agent_warnings == []


# ---------------------------------------------------------------------------
# Lightweight unit test for the partition function itself
# ---------------------------------------------------------------------------


def test_check_agents_returns_only_agent_kind_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_check_agents`` returns only ``agent-*`` warnings."""

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )

    events = list(read_events(journal_path))
    state = replay_state(events)
    issues = _check_agents(state, events, vault, kit_root)
    assert all(i.kind in {AGENT_BINDING_MISSING, AGENT_VERSION_DRIFT} for i in issues)
    assert all(i.is_warning for i in issues)


# ---------------------------------------------------------------------------
# CLI integration — pin CT-21 "Stderr is empty" + section-order shape
# (Schedules:` precedes `Agents:` when both render in the same invocation).
# ---------------------------------------------------------------------------


def _seed_full_vault_with_one_each(
    tmp_path: Path,
) -> tuple[Path, Path]:
    """Vault that triggers exactly one Schedules warning and one Agents warning.

    Schedules: schedule install on a foreign machine_id → hostname-rename.
    Agents: schedule install on the current host with a missing AGENT.md →
    agent-binding-missing.
    """

    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    # Schedule 1: bound to the current host but AGENT.md missing → agent warning.
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    # Schedule 2: on a foreign machine_id → schedule-hostname-rename warning.
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="other-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/other.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
        ),
    )
    return vault, kit_root


def test_cmd_doctor_stderr_empty_on_agent_warning_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CT-21 last sentence: when only an agent warning fires, stderr is empty."""

    import argparse

    from llm_wiki_kit.cli import _cmd_doctor

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    for primitive_name in ("weekly-digest", "household-manager"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW, by="wiki-init", primitive=primitive_name, version="0.1.0"
            ),
        )
    append_event(
        journal_path,
        ScheduleInstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="this-box",
            cadence_dsl="SUN 09:00",
            os_artifact_path="/tmp/x.plist",
            exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
            agent="household-manager",
        ),
    )
    monkeypatch.chdir(vault)
    args = argparse.Namespace(kit_root=kit_root)
    rc = _cmd_doctor(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert "household-manager" in captured.out
    assert "Agents:" in captured.out


def test_cmd_doctor_schedules_section_precedes_agents_section(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §Outputs ``wiki doctor`` — the Agents section renders *after* Schedules.

    Pins the section-order contract end-to-end: both ``Schedules:`` and
    ``Agents:`` headers appear and the schedules header offset is
    strictly less than the agents header offset.
    """

    import argparse

    from llm_wiki_kit.cli import _cmd_doctor

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    vault, kit_root = _seed_full_vault_with_one_each(tmp_path)
    monkeypatch.chdir(vault)
    args = argparse.Namespace(kit_root=kit_root)
    rc = _cmd_doctor(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    schedules_idx = captured.out.find("Schedules:")
    agents_idx = captured.out.find("Agents:")
    assert schedules_idx != -1, captured.out
    assert agents_idx != -1, captured.out
    assert schedules_idx < agents_idx, captured.out


def test_cmd_doctor_orphan_warning_kind_renders_under_fallback_section(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warning whose kind doesn't match a known prefix renders under
    a generic ``Warnings:`` section rather than disappearing.

    Pins the partition's fallback bucket in ``cli._cmd_doctor``: a
    future check that emits a warning with a fresh kind prefix
    (`primitive-*`, `git-*`, etc.) is surfaced rather than silently
    dropped. Drives the CLI by stubbing ``run_doctor`` to return one
    orphan warning.
    """

    import argparse

    from llm_wiki_kit.cli import _cmd_doctor
    from llm_wiki_kit.doctor import Issue

    monkeypatch.setattr("llm_wiki_kit.doctor.gethostname", lambda: "this-box")
    kit_root = _build_kit_root(tmp_path)
    vault, journal_path = _seed_vault(tmp_path)
    # Minimal journal so the vault-check in ``_cmd_doctor`` passes.
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )

    def fake_run_doctor(_: Path, __: Path) -> list[Issue]:
        return [
            Issue(
                kind="future-feature-warning",
                path="x",
                detail="future warning shape; should not disappear",
                is_warning=True,
            )
        ]

    monkeypatch.setattr("llm_wiki_kit.cli.run_doctor", fake_run_doctor)
    monkeypatch.chdir(vault)
    rc = _cmd_doctor(argparse.Namespace(kit_root=kit_root))

    captured = capsys.readouterr()
    assert rc == 0
    assert "Warnings:" in captured.out
    assert "future warning shape" in captured.out
