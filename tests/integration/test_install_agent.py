"""End-to-end ``wiki add agent:<name>`` integration test (CT-2).

Pins that the existing primitive-install pipeline carries ``kind:
agent`` primitives without a new install discriminator — the install
runs through the same ``PrimitiveInstallEvent`` shape ontology,
content-type, and operation primitives use, and the catalog's
``files/.claude/agents/<name>/AGENT.md`` lands at the corresponding
vault-relative path via ``render.render_tree``'s verbatim copy.

Uses the same kit-root threading pattern as ``test_wiki_add.py``:
a tmp kit holds the real ``core`` and a single synthetic agent
primitive, plus a minimal recipe that resolves to core-only so
``wiki init`` lays down the baseline before ``wiki add`` runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import PageWriteEvent, PrimitiveInstallEvent

REPO_ROOT = Path(__file__).resolve().parents[2]

_AGENT_MD_BODY = """---
name: household-manager
description: Test fixture agent for PR-2 integration.
audience: family
role: planner
tone: warm
knows: []
---

# Household manager (fixture)

Test body — the kit reads zero bytes of this file at runtime.
"""


def _install_kit(tmp_path: Path) -> Path:
    """Build a fixture kit_root with core + one synthetic agent primitive."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    agent_root = kit / "templates" / "agents" / "household-manager"
    agent_root.mkdir(parents=True)
    (agent_root / "primitive.yaml").write_text(
        "name: household-manager\nkind: agent\nversion: 0.1.0\ndescription: Test fixture agent.\n",
        encoding="utf-8",
    )
    agent_md_path = agent_root / "files" / ".claude" / "agents" / "household-manager" / "AGENT.md"
    agent_md_path.parent.mkdir(parents=True)
    agent_md_path.write_text(_AGENT_MD_BODY, encoding="utf-8")

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: Core-only recipe for agent install tests.\n"
        "primitives:\n"
        "  - core\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    return _install_kit(tmp_path)


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _init_vault(tmp_path: Path, kit_root: Path) -> Path:
    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal"], kit_root=kit_root) == 0
    return vault


def test_wiki_add_agent_installs_via_existing_primitive_event(
    tmp_path: Path, kit_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-2: ``wiki add agent:household-manager`` appends one
    ``PrimitiveInstallEvent`` (no new discriminator) and lands the
    AGENT.md byte-identical at the expected vault path."""

    vault = _init_vault(tmp_path, kit_root)
    monkeypatch.chdir(vault)
    events_before = read_events(_journal_path(vault))

    assert cli.main(["add", "agent:household-manager"], kit_root=kit_root) == 0

    events_after = read_events(_journal_path(vault))
    new_events = events_after[len(events_before) :]

    install_events = [e for e in new_events if isinstance(e, PrimitiveInstallEvent)]
    assert [(e.primitive, e.version, e.by) for e in install_events] == [
        ("household-manager", "0.1.0", "wiki-add"),
    ]

    agent_md = vault / ".claude" / "agents" / "household-manager" / "AGENT.md"
    assert agent_md.is_file()
    # Byte-exact (CT-2's "byte-identical to the catalog source"); a future
    # non-ASCII fixture entry stays honest under read_bytes where read_text
    # would silently re-encode.
    assert agent_md.read_bytes() == _AGENT_MD_BODY.encode("utf-8")

    page_writes = [e for e in new_events if isinstance(e, PageWriteEvent)]
    assert any(ev.path == ".claude/agents/household-manager/AGENT.md" for ev in page_writes), (
        f"expected AGENT.md PageWriteEvent, got paths: {[ev.path for ev in page_writes]}"
    )

    state = replay_state(events_after)
    assert state.installed_primitives.get("household-manager") == "0.1.0"
