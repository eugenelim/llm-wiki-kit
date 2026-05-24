"""Tests for ``schedule.install``'s agent resolution chain (RFC-0004 PR-4).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-8: CLI ``--agent`` flag wins over recipe + contract.
- CT-9: Recipe binding wins over contract ``preferred_agent``.
- CT-10: Contract ``preferred_agent`` used when recipe has no binding.
- CT-11: Resolution returns ``None`` when nothing declares.
- CT-12: Missing CLI agent name → ``WikiError`` pre-transaction (zero events).
- CT-13: Contract names an uninstalled agent → silent skip (no warning).
- CT-24b: Pre-RFC-4 ``schedule.installed`` line lacking ``agent`` replays
  with ``agent is None``.
- Artifact ``exec_command`` pins: two-token append when agent resolves;
  unchanged four-token shape when none does (CT-11 corollary).

Test seam follows the ``test_schedule_install.py`` pattern: a stub
``_Emitter`` is injected via monkeypatching
``llm_wiki_kit.schedule._resolve_emitter`` so the OS-side
``activate()`` is a no-op. The ``kit_root`` is a per-test fixture
directory built under ``tmp_path`` so the recipe + agent + operation
catalogs are isolated from the repo's live catalog.
"""

from __future__ import annotations

import json
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

NOW = datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Stub emitter (mirrors test_schedule_install.py's shape)
# ---------------------------------------------------------------------------


@dataclass
class _StubEmitter:
    base_dir: Path
    render_artifact_calls: list[dict[str, Any]] = field(default_factory=list)

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
                "exec_command": list(exec_command),
            }
        )
        return f"stub {operation}".encode()

    def companion_artifacts(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> list[tuple[Path, str | bytes]]:
        return []

    def install_instruction(self, artifact_path: Path) -> str | None:
        return None

    def uninstall_instruction(self, artifact_path: Path) -> str | None:
        return None

    def activate(self, artifact_path: Path) -> None:
        return None

    def deactivate(self, artifact_path: Path) -> None:
        return None

    def inspect(self, artifact_path: Path) -> InspectResult:
        return "loaded" if artifact_path.exists() else "missing-file"


# ---------------------------------------------------------------------------
# Fixture catalog builder
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _build_kit_root(
    tmp_path: Path,
    *,
    recipe_agents_block: str = "agents: {}\n",
    contract_preferred_agent: str | None = None,
    agent_names: tuple[str, ...] = (),
    recipe_name: str = "test-recipe",
) -> Path:
    """Build a minimal kit_root with operations + agents + a recipe.

    The recipe lists ``weekly-digest`` plus every name in
    ``agent_names`` so the closure is closed; the recipe's
    ``agents:`` block is whatever ``recipe_agents_block`` literal
    yields (so the caller controls the binding shape).

    A ``core`` infrastructure primitive is always shipped because
    ``recipes.resolve_recipe_primitives`` requires it for the
    always-include-core policy.
    """

    kit_root = tmp_path / "kit-root"

    # Core (infrastructure primitive — required by the recipe loader).
    _write_yaml(
        kit_root / "core" / "primitive.yaml",
        ("name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core infra primitive.\n"),
    )

    # weekly-digest operation primitive + contract.
    _write_yaml(
        kit_root / "templates" / "operations" / "weekly-digest" / "primitive.yaml",
        (
            "name: weekly-digest\nkind: operation\nversion: 0.1.0\n"
            "description: weekly digest operation.\n"
        ),
    )
    contract_body = (
        "name: weekly-digest\ndescription: Weekly digest.\nperiod: weekly\nskill: weekly-digest\n"
    )
    if contract_preferred_agent is not None:
        contract_body += f"preferred_agent: {contract_preferred_agent}\n"
    _write_yaml(
        kit_root / "templates" / "operations" / "weekly-digest" / "contract.yaml",
        contract_body,
    )

    # Each agent primitive ships an empty AGENT.md (kit reads zero bytes
    # of it at runtime — we ship a stub so the catalog walk finds the
    # primitive directory).
    for name in agent_names:
        _write_yaml(
            kit_root / "templates" / "agents" / name / "primitive.yaml",
            (f"name: {name}\nkind: agent\nversion: 0.1.0\ndescription: {name} agent.\n"),
        )
        # AGENT.md content is not read by the kit; presence-or-absence
        # doesn't matter for these resolution-chain tests.

    # Recipe lists every shipped primitive so the closure is closed.
    primitives_list = ["weekly-digest", *agent_names]
    primitives_yaml = "\n".join(f"  - {name}" for name in primitives_list)
    _write_yaml(
        kit_root / "recipes" / f"{recipe_name}.yaml",
        (
            f"name: {recipe_name}\n"
            "version: 0.1.0\n"
            "description: test recipe.\n"
            "primitives:\n"
            f"{primitives_yaml}\n"
            f"{recipe_agents_block}"
        ),
    )

    return kit_root


def _make_vault(
    tmp_path: Path,
    *,
    recipe_name: str = "test-recipe",
    installed_agents: tuple[str, ...] = (),
    operation: str = "weekly-digest",
) -> tuple[Path, Path]:
    """Build a minimal vault + journal recording the operation + agents installed."""

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
            recipe=recipe_name,
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
    for agent_name in installed_agents:
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-init",
                primitive=agent_name,
                version="0.1.0",
            ),
        )
    return vault, journal_path


@pytest.fixture
def stub_emitter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _StubEmitter:
    emitter = _StubEmitter(base_dir=tmp_path / "stub-artifacts")
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: emitter)
    return emitter


# ---------------------------------------------------------------------------
# CT-8: CLI --agent wins over recipe + contract
# ---------------------------------------------------------------------------


def test_schedule_install_cli_agent_flag_wins_resolution(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-8: CLI flag wins over recipe binding AND contract preferred_agent."""

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block=("agents:\n  household-manager:\n    runs:\n      - weekly-digest\n"),
        contract_preferred_agent="household-manager",
        agent_names=("household-manager", "trip-planner"),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("household-manager", "trip-planner"),
    )

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
        agent="trip-planner",
    )

    assert result.agent == "trip-planner"
    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert len(installed) == 1
    assert installed[0].agent == "trip-planner"
    # OS-side artifact's exec_command embeds the agent.
    assert installed[0].exec_command[-2:] == ["--agent", "trip-planner"]


# ---------------------------------------------------------------------------
# CT-9: Recipe binding wins over contract
# ---------------------------------------------------------------------------


def test_schedule_install_recipe_binding_wins_over_contract_preferred(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-9: with no CLI flag, the recipe binding beats the contract suggestion."""

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block=("agents:\n  household-manager:\n    runs:\n      - weekly-digest\n"),
        contract_preferred_agent="care-coordinator",
        agent_names=("household-manager", "care-coordinator"),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("household-manager", "care-coordinator"),
    )

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )

    assert result.agent == "household-manager"
    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert installed[0].agent == "household-manager"


# ---------------------------------------------------------------------------
# CT-10: Contract preferred_agent used when recipe has no binding
# ---------------------------------------------------------------------------


def test_schedule_install_contract_preferred_agent_used_when_recipe_silent(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-10: empty recipe agents block + contract preferred_agent → contract wins."""

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent="personal-coordinator",
        agent_names=("personal-coordinator",),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("personal-coordinator",),
    )

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )

    assert result.agent == "personal-coordinator"
    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert installed[0].agent == "personal-coordinator"


# ---------------------------------------------------------------------------
# CT-11: All branches None → no agent on event, four-token exec_command
# ---------------------------------------------------------------------------


def test_schedule_install_resolves_to_none_when_nothing_declares(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-11: no CLI flag, empty recipe agents, no contract preferred_agent → None."""

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=(),
    )
    vault, journal_path = _make_vault(tmp_path)

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )

    assert result.agent is None
    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert installed[0].agent is None
    # exec_command keeps the existing four-token shape.
    assert installed[0].exec_command[1:] == ["run", "--exec", "weekly-digest"]
    assert "--agent" not in installed[0].exec_command


# ---------------------------------------------------------------------------
# CT-12: CLI --agent for an uninstalled name → WikiError pre-transaction
# ---------------------------------------------------------------------------


def test_schedule_install_refuses_missing_agent_name_via_cli_flag(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-12: --agent ghost where no kind: agent primitive 'ghost' is installed.

    Refusal aborts BEFORE ``journal.transaction()`` opens, so zero
    events of any type (including ``lock.acquired`` / ``lock.released``)
    are appended. Extends the existing schedule pre-load refusal
    invariant.
    """

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=(),
    )
    vault, journal_path = _make_vault(tmp_path)

    # Snapshot the journal byte length so we can confirm zero events landed.
    events_before = list(read_events(journal_path))

    with pytest.raises(WikiError) as excinfo:
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
            agent="ghost",
        )

    assert "agent 'ghost' is not installed" in str(excinfo.value)
    events_after = list(read_events(journal_path))
    assert events_after == events_before  # zero events of any type


# ---------------------------------------------------------------------------
# CT-13: Contract preferred_agent for uninstalled agent → silent skip
# ---------------------------------------------------------------------------


def test_schedule_install_idempotent_when_recipe_drifts_post_install(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """Idempotent re-install survives recipe-binds-to-uninstalled-agent drift.

    Spec wiki-agents §"Edge cases / Recipe edits during a live vault":
    "The journaled agent is frozen at install time. A recipe edit ...
    does not retroactively rebind existing schedules." The
    resolution-chain only runs on a fresh install; a same-cadence
    re-install must remain a no-op even when the current recipe binds
    to an agent the vault has since removed.
    """

    # First install with a recipe that binds household-manager.
    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block=("agents:\n  household-manager:\n    runs:\n      - weekly-digest\n"),
        contract_preferred_agent=None,
        agent_names=("household-manager",),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("household-manager",),
    )

    first = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )
    assert first.agent == "household-manager"
    events_after_first = list(read_events(journal_path))

    # Simulate post-install drift: the agent primitive is no longer
    # installed (user ran ``wiki remove agent:household-manager`` or
    # equivalent). Recipe still binds the operation to it.
    # We rebuild a vault that does NOT carry the agent install event.
    drifted_vault = tmp_path / "drifted-vault"
    drifted_vault.mkdir()
    drifted_journal_dir = drifted_vault / ".wiki.journal"
    drifted_journal_dir.mkdir()
    drifted_journal_path = drifted_journal_dir / "journal.jsonl"
    # Copy events except the agent's PrimitiveInstallEvent.
    from llm_wiki_kit.models import PrimitiveInstallEvent as P

    for event in events_after_first:
        if isinstance(event, P) and event.primitive == "household-manager":
            continue
        append_event(drifted_journal_path, event)

    # Same-cadence re-install: must be idempotent, not raise on the
    # recipe's bound-to-uninstalled-agent drift.
    second = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=drifted_vault,
        kit_root=kit_root,
        journal_path=drifted_journal_path,
        now=NOW,
    )
    assert second.already_installed is True
    assert second.agent == "household-manager"  # frozen from prior journal entry


def test_schedule_install_refuses_when_recipe_binds_uninstalled_agent(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """Recipe binds an operation to an agent name the vault hasn't installed.

    Pins the load-bearing choice made by ``_resolve_agent``: recipe-resolved
    names go through strict validation (like CLI-flag names per CT-12), not
    silent skip (only the contract step does that, per CT-13). Without this
    test a future contributor could "simplify" the recipe branch to skip
    silently and pass every other test.
    """

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block=("agents:\n  household-manager:\n    runs:\n      - weekly-digest\n"),
        contract_preferred_agent=None,
        agent_names=("household-manager",),  # primitive exists in catalog…
    )
    # …but is NOT installed in the vault (installed_agents=()).
    vault, journal_path = _make_vault(tmp_path)

    events_before = list(read_events(journal_path))

    with pytest.raises(WikiError) as excinfo:
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
        )

    msg = str(excinfo.value)
    assert "household-manager" in msg
    assert "test-recipe" in msg
    assert "weekly-digest" in msg
    assert "is not installed" in msg

    events_after = list(read_events(journal_path))
    assert events_after == events_before  # zero events


def test_schedule_install_refuses_silent_agent_reconfiguration(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """Same-cadence re-install with a different ``--agent`` must refuse.

    Spec wiki-schedule §"Idempotent re-install" allows same-cadence
    no-ops but explicitly disallows silent reconfiguration. A reinstall
    that resolves to a different agent than the journaled one would
    silently drop the user's new intent, so the kit refuses with a
    ``WikiError`` and zero new events. Compare to the analogous
    cadence-mismatch refusal already pinned by
    ``test_schedule_install.py``.
    """

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=("household-manager", "care-coordinator"),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("household-manager", "care-coordinator"),
    )

    # First install with --agent household-manager.
    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
        agent="household-manager",
    )
    events_after_first = list(read_events(journal_path))

    # Second install with the SAME cadence but a different --agent
    # would silently re-bind. Refuse.
    with pytest.raises(WikiError) as excinfo:
        schedule.install(
            "weekly-digest",
            at=None,
            machine="this-box",
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
            agent="care-coordinator",
        )

    msg = str(excinfo.value)
    assert "household-manager" in msg
    assert "uninstall first" in msg

    # Zero new events: the second call refused before any append.
    events_after_second = list(read_events(journal_path))
    assert events_after_second == events_after_first


def test_schedule_install_skips_uninstalled_contract_preferred_silently(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """CT-13: contract suggests an agent not installed in this vault → resolved to None.

    No WikiError, no warning, no failure — the contract author's
    suggestion just doesn't apply to this vault. Compare to CT-12
    (CLI flag), which raises in the same situation.
    """

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent="not-installed",
        agent_names=("not-installed",),  # exists in catalog but not in vault
    )
    # Note: ``installed_agents=()`` — the agent primitive is in the
    # catalog but NOT in ``state.installed_primitives``.
    vault, journal_path = _make_vault(tmp_path)

    result = schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )

    assert result.agent is None
    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert installed[0].agent is None


# ---------------------------------------------------------------------------
# Artifact exec_command — pin the two-token append on the OS-side body
# ---------------------------------------------------------------------------


def test_schedule_install_artifact_exec_command_includes_agent_flag(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """The exec_command passed to ``emitter.render_artifact`` carries the agent flag.

    The OS-side artifact body is the authoritative carrier of the
    frozen agent name — spec §Invariants. This test pins that the
    two-token append lands in the body's render input (and therefore
    in the OS scheduler's argv at fire time).
    """

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=("household-manager",),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("household-manager",),
    )

    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
        agent="household-manager",
    )

    assert len(stub_emitter.render_artifact_calls) == 1
    exec_command = stub_emitter.render_artifact_calls[0]["exec_command"]
    assert exec_command[-2:] == ["--agent", "household-manager"]


def test_schedule_install_artifact_exec_command_omits_agent_flag_when_none(
    tmp_path: Path, stub_emitter: _StubEmitter
) -> None:
    """No agent resolved → no --agent tokens in the rendered artifact."""

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=(),
    )
    vault, journal_path = _make_vault(tmp_path)

    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )

    assert len(stub_emitter.render_artifact_calls) == 1
    exec_command = stub_emitter.render_artifact_calls[0]["exec_command"]
    assert "--agent" not in exec_command


# ---------------------------------------------------------------------------
# CLI-level tests — pin argparse wiring + stdout summary rendering
# ---------------------------------------------------------------------------


def test_cli_schedule_install_threads_agent_flag_and_emits_stdout_line(
    tmp_path: Path,
    stub_emitter: _StubEmitter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end CLI: ``--agent`` reaches install + stdout ``agent:`` line between summary rows.

    Pins three contracts in one shot:
    - argparse's ``--agent`` is wired to ``schedule.install(agent=...)`` (a
      rename or typo on the kwarg name would fail here);
    - the journaled ``ScheduleInstalledEvent.agent`` reflects the flag;
    - stdout shows ``\\n  cadence: ...\\n  agent: trip-planner\\n  artifact: ...\\n``
      in that order (spec §Outputs wiki-schedule + wiki-agents).
    """

    from llm_wiki_kit import cli

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=("trip-planner",),
    )
    vault, journal_path = _make_vault(
        tmp_path,
        installed_agents=("trip-planner",),
    )

    monkeypatch.chdir(vault)
    argv = [
        "schedule",
        "install",
        "weekly-digest",
        "--machine",
        "this-box",
        "--agent",
        "trip-planner",
    ]
    exit_code = cli.main(argv, kit_root=kit_root)
    assert exit_code == 0

    stdout = capsys.readouterr().out
    # Ordering: cadence → agent → artifact, all two-space indented.
    cadence_idx = stdout.index("\n  cadence: ")
    agent_idx = stdout.index("\n  agent: trip-planner")
    artifact_idx = stdout.index("\n  artifact: ")
    assert cadence_idx < agent_idx < artifact_idx

    events = list(read_events(journal_path))
    installed = [e for e in events if isinstance(e, ScheduleInstalledEvent)]
    assert installed[0].agent == "trip-planner"


def test_cli_schedule_install_omits_agent_line_when_none(
    tmp_path: Path,
    stub_emitter: _StubEmitter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No agent resolved → stdout omits the ``  agent:`` line entirely.

    The line is conditional per spec; a regression that printed
    ``agent: None`` or ``agent: (none)`` would fail this test.
    """

    from llm_wiki_kit import cli

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=(),
    )
    vault, _ = _make_vault(tmp_path)
    monkeypatch.chdir(vault)

    exit_code = cli.main(
        ["schedule", "install", "weekly-digest", "--machine", "this-box"],
        kit_root=kit_root,
    )
    assert exit_code == 0

    stdout = capsys.readouterr().out
    assert "agent:" not in stdout


def test_cli_schedule_install_refuses_unknown_agent_via_main(
    tmp_path: Path,
    stub_emitter: _StubEmitter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CT-12 via the CLI: ``--agent ghost`` exits non-zero, journals nothing, surfaces the message.

    Complements the data-layer CT-12 test by exercising the full
    argparse → handler → ``schedule.install(...)`` → top-level error
    handler → stderr translation. Asserting on stderr catches a
    regression in the WikiError-to-stderr translation that the
    data-layer test would not see.
    """

    from llm_wiki_kit import cli

    kit_root = _build_kit_root(
        tmp_path,
        recipe_agents_block="agents: {}\n",
        contract_preferred_agent=None,
        agent_names=(),
    )
    vault, journal_path = _make_vault(tmp_path)
    monkeypatch.chdir(vault)

    events_before = list(read_events(journal_path))
    exit_code = cli.main(
        ["schedule", "install", "weekly-digest", "--machine", "this-box", "--agent", "ghost"],
        kit_root=kit_root,
    )
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "agent 'ghost' is not installed" in captured.err
    events_after = list(read_events(journal_path))
    assert events_after == events_before  # zero events appended


# ---------------------------------------------------------------------------
# CT-24b: pre-RFC-4 schedule.installed without ``agent`` field replays clean
# ---------------------------------------------------------------------------


def test_pre_rfc4_schedule_installed_event_without_agent_field_replays(
    tmp_path: Path,
) -> None:
    """CT-24b: a literal pre-RFC-4 JSON line lacking ``agent`` replays with ``agent is None``.

    Pins ADR-0002 §Negative's additive-schema rule: every new field on
    a journal event must have a default so older lines keep parsing.
    Uses a literal JSON line rather than ``model_dump_json()`` so the
    test would catch a regression that made ``agent`` required.
    """

    from llm_wiki_kit.models import ScheduleInstalledEvent as Event

    pre_rfc4_payload = {
        "type": "schedule.installed",
        "timestamp": NOW.isoformat(),
        "by": "wiki-schedule",
        "operation": "weekly-digest",
        "machine_id": "this-box",
        "cadence_dsl": "SUN 09:00",
        "os_artifact_path": "/tmp/artifact.plist",
        "exec_command": ["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
    }
    parsed = Event.model_validate_json(json.dumps(pre_rfc4_payload))
    assert parsed.agent is None
    # Round-trip via the discriminated union too — the parser path
    # ``read_events`` uses.
    from pydantic import TypeAdapter

    from llm_wiki_kit.models import Event as EventUnion

    adapter: TypeAdapter[EventUnion] = TypeAdapter(EventUnion)
    via_union = adapter.validate_python(pre_rfc4_payload)
    assert isinstance(via_union, Event)
    assert via_union.agent is None
