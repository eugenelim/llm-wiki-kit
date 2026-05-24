"""End-to-end ``wiki init --recipe work-os`` installs the three default
work-os agents (PR-7 of RFC-0004 wiki-agents).

Mirrors ``test_init_family_recipe_agents.py``; see that file's docstring
for the rationale. The work-os bindings ship in
``recipes/work-os.yaml``'s ``agents:`` block.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_CATALOG = REPO_ROOT / "templates" / "agents"


def _catalog_agent_md(name: str) -> Path:
    return AGENTS_CATALOG / name / "files" / ".claude" / "agents" / name / "AGENT.md"


def test_init_work_os_recipe_installs_three_default_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki init --recipe work-os`` lands the three work-os agents
    byte-identical to the catalog source; ``wiki agents`` reports
    them with their spec-pinned OPERATIONS bindings."""

    vault = tmp_path / "work-os-vault"
    assert main(["init", str(vault), "--recipe", "work-os"]) == 0

    for agent_name in ("stakeholder-steward", "renewals-watch", "customer-listener"):
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
    assert set(rows) == {"stakeholder-steward", "renewals-watch", "customer-listener"}, (
        f"`wiki agents` did not list the three work-os agents exactly; got: {sorted(rows)}"
    )

    # Per spec §"Default agent catalog":
    assert rows["stakeholder-steward"][2] == "stakeholder-map-refresh, status-synthesis"
    assert rows["renewals-watch"][2] == "renewal-reminders"
    assert rows["customer-listener"][2] == "action-item-rollup"

    for name in rows:
        assert "work-os" in rows[name][1].split(", "), (
            f"`{name}` RECIPES column missing 'work-os': {rows[name][1]!r}"
        )
