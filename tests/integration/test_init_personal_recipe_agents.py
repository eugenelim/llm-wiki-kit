"""End-to-end ``wiki init --recipe personal`` installs the two default
personal agents (PR-7 of RFC-0004 wiki-agents).

Pins, against the live shipped catalog:

- ``personal-coordinator/AGENT.md`` lands byte-identical to the catalog
  source.
- ``decision-companion/AGENT.md`` lands byte-identical *too* — it ships
  installed-but-unbound per spec §"Default agent catalog" (in
  ``personal.yaml``'s ``primitives:`` closure but with no entry in the
  recipe's ``agents:`` block).
- ``wiki agents`` reports ``decision-companion`` with ``OPERATIONS=—``
  per spec §Outputs ``wiki agents`` (the empty-OPERATIONS render).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_CATALOG = REPO_ROOT / "templates" / "agents"


def _catalog_agent_md(name: str) -> Path:
    return AGENTS_CATALOG / name / "files" / ".claude" / "agents" / name / "AGENT.md"


def test_init_personal_recipe_installs_two_default_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki init --recipe personal`` lands both personal agents
    byte-identical; ``wiki agents`` reports ``personal-coordinator``
    bound and ``decision-companion`` installed-but-unbound."""

    vault = tmp_path / "personal-vault"
    assert main(["init", str(vault), "--recipe", "personal"]) == 0

    # Both ship via personal.yaml's `primitives:` closure (one bound,
    # one unbound), both write their AGENT.md.
    for agent_name in ("personal-coordinator", "decision-companion"):
        installed = vault / ".claude" / "agents" / agent_name / "AGENT.md"
        catalog_source = _catalog_agent_md(agent_name)
        assert installed.is_file(), f"missing vault-side {installed}"
        assert installed.read_bytes() == catalog_source.read_bytes(), (
            f"{installed} drifted from catalog source {catalog_source}"
        )

    monkeypatch.chdir(vault)
    capsys.readouterr()
    assert main(["agents"]) == 0
    stdout = capsys.readouterr().out
    lines = stdout.splitlines()
    assert lines[0] == "NAME\tRECIPES\tOPERATIONS"

    rows = {line.split("\t")[0]: line.split("\t") for line in lines[1:]}
    assert set(rows) == {"personal-coordinator", "decision-companion"}, (
        f"`wiki agents` did not list both personal agents; got: {sorted(rows)}"
    )

    # Spec §"Default agent catalog": personal-coordinator runs three ops.
    assert rows["personal-coordinator"][2] == "follow-up-tracker, meal-planning, weekly-digest"
    # decision-companion ships unbound; OPERATIONS renders as `—` (U+2014).
    decision_ops = rows["decision-companion"][2]
    assert decision_ops == "—", (
        f"decision-companion OPERATIONS should render as `—` (U+2014); got {decision_ops!r}"
    )

    for name in rows:
        assert "personal" in rows[name][1].split(", "), (
            f"`{name}` RECIPES column missing 'personal': {rows[name][1]!r}"
        )
