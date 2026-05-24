"""End-to-end ``wiki init --recipe family`` installs the three default
family agents (PR-7 of RFC-0004 wiki-agents).

Pins, against the live shipped catalog:

- ``<vault>/.claude/agents/{household-manager,trip-planner,care-coordinator}/AGENT.md``
  each land byte-identical to the catalog source under
  ``templates/agents/<name>/files/.claude/agents/<name>/AGENT.md``
  (covers the PR-2 drift-watch — four sites would shift in lockstep
  if the source path layout drifts).
- ``wiki agents`` on the resulting vault prints exactly the three
  family agents with their spec §"Default agent catalog" bindings
  in the OPERATIONS column.
- The spec's plan §"Verification gate" end-to-end claim — that
  ``wiki schedule install weekly-digest`` against the
  family-initialized vault journals ``agent="household-manager"``
  resolved from the recipe's live ``agents:`` block, and that the
  OS-side artifact's ``exec_command`` embeds ``--agent
  household-manager`` — is exercised here by joining the live
  ``schedule.install(...)`` path against the freshly-initialized
  vault. Per-PR fixture tests (PR-4 CT-9) prove the resolution
  *logic*; this test proves the live ``recipes/family.yaml``
  feeds the same logic the same way.
- ``wiki doctor`` is clean on the freshly-initialized family vault
  (zero warnings, zero failures, exit 0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from llm_wiki_kit import schedule
from llm_wiki_kit.cli import main
from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import ScheduleInstalledEvent
from llm_wiki_kit.schedule._emitter import InspectResult
from llm_wiki_kit.schedule.dsl import ResolvedCadence


@dataclass
class _StubEmitter:
    """Minimal emitter for ``schedule.install`` integration use.

    Mirrors the test seam in ``tests/unit/test_schedule_install_agent.py``;
    inlined here rather than imported because the unit-test module
    isn't part of the kit's public surface. The integration test cares
    only about the ``exec_command`` shape passed to ``render_artifact``
    and that ``inspect`` returns a sane status post-install.
    """

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
            {"operation": operation, "exec_command": list(exec_command)}
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


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_CATALOG = REPO_ROOT / "templates" / "agents"


def _catalog_agent_md(name: str) -> Path:
    return AGENTS_CATALOG / name / "files" / ".claude" / "agents" / name / "AGENT.md"


def test_init_family_recipe_installs_three_default_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki init --recipe family`` lands the three family agents
    byte-identical to the catalog source; ``wiki agents`` reports
    them with their spec-pinned OPERATIONS bindings."""

    vault = tmp_path / "household"
    assert main(["init", str(vault), "--recipe", "family"]) == 0

    # Per spec §"Default agent catalog" — three family agents.
    for agent_name in ("household-manager", "trip-planner", "care-coordinator"):
        installed_md = vault / ".claude" / "agents" / agent_name / "AGENT.md"
        catalog_source = _catalog_agent_md(agent_name)
        assert installed_md.is_file(), f"missing vault-side {installed_md}"
        # Byte-identical; drift detection's whole point.
        assert installed_md.read_bytes() == catalog_source.read_bytes(), (
            f"{installed_md} drifted from catalog source {catalog_source}"
        )

    # `wiki agents` shape on the family-initialized vault.
    monkeypatch.chdir(vault)
    capsys.readouterr()  # discard any prior captured output
    assert main(["agents"]) == 0
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    assert lines[0] == "NAME\tRECIPES\tOPERATIONS", f"header line drift: {lines[0]!r}"

    # Parse rows into a map for assertion. The family recipe binds
    # three agents per spec §"Default agent catalog".
    rows = {line.split("\t")[0]: line.split("\t") for line in lines[1:]}
    assert set(rows) == {"household-manager", "trip-planner", "care-coordinator"}, (
        f"`wiki agents` did not list the three family agents exactly; got: {sorted(rows)}"
    )

    # OPERATIONS column is sorted alphabetically per spec §Outputs.
    assert rows["household-manager"][2] == "follow-up-tracker, meal-planning, weekly-digest"
    assert rows["trip-planner"][2] == "trip-prep"
    assert rows["care-coordinator"][2] == "medical-summary"

    # RECIPES column contains "family" for each (the family-shipped agents).
    for name in rows:
        assert "family" in rows[name][1].split(", "), (
            f"`{name}` RECIPES column missing 'family': {rows[name][1]!r}"
        )

    # Spec plan §"Verification gate" — the live family recipe's
    # ``agents:`` block resolves to ``household-manager`` for
    # ``weekly-digest`` end-to-end. Per-PR tests (PR-4 CT-9) prove
    # the resolution logic on synthetic recipes; this test joins
    # the live ``recipes/family.yaml`` to ``schedule.install(...)``
    # to catch any drift between the shipped YAML and the resolver.
    stub_emitter = _StubEmitter(base_dir=tmp_path / "stub-artifacts")
    monkeypatch.setattr("llm_wiki_kit.schedule._resolve_emitter", lambda: stub_emitter)

    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    schedule.install(
        "weekly-digest",
        at=None,
        machine="this-box",
        vault_root=vault,
        kit_root=REPO_ROOT,
        journal_path=journal_path,
        now=datetime(2026, 5, 24, 9, 0, 0, tzinfo=UTC),
    )

    events_after = read_events(journal_path)
    install_events = [e for e in events_after if isinstance(e, ScheduleInstalledEvent)]
    assert len(install_events) == 1, (
        f"expected one ScheduleInstalledEvent; got {len(install_events)} "
        f"(family-recipe `agents:` block may have drifted)"
    )
    install_event = install_events[0]
    assert install_event.agent == "household-manager", (
        f"family recipe's `agents:` block should resolve weekly-digest "
        f"to household-manager; got agent={install_event.agent!r}"
    )
    assert install_event.exec_command[-2:] == ["--agent", "household-manager"], (
        f"OS artifact's exec_command should embed `--agent household-manager`; "
        f"got: {install_event.exec_command!r}"
    )
    assert any(
        call["exec_command"][-2:] == ["--agent", "household-manager"]
        for call in stub_emitter.render_artifact_calls
    ), "stub emitter saw no render_artifact call with the agent flag"

    # Spec plan §"Verification gate" — doctor is clean on a freshly
    # initialized vault even after the schedule install above. The
    # schedule binds `household-manager` and the AGENT.md is present
    # (installed by `wiki init`), so the bindings check finds nothing
    # to warn about. A regression in `_check_agents` that falsely
    # fires on the shipped catalog would be invisible to per-PR
    # tests (which use synthetic vaults); this assertion catches it.
    capsys.readouterr()
    assert main(["doctor"]) == 0
    doctor_out = capsys.readouterr().out
    # The agent-binding-missing warning (PR-6 / `doctor.py:AGENT_BINDING_MISSING`)
    # mentions `agent` and `AGENT.md missing`; assert neither phrase
    # appears on the clean-vault stdout. Stays robust to future
    # additions to doctor's section headers (which may legitimately
    # carry the word "agent" without being a warning).
    assert "AGENT.md missing" not in doctor_out, (
        f"doctor surfaced an unexpected agent-binding warning on a clean vault: {doctor_out!r}"
    )
    assert "upgraded" not in doctor_out, (
        f"doctor surfaced an unexpected agent version-drift warning on a "
        f"clean vault: {doctor_out!r}"
    )
