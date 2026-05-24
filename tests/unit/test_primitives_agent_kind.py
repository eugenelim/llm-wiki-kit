"""PR-2 catalog-discovery tests for RFC-0004 wiki-agents.

Covers the discovery + helper surface that lands in PR-2 of
``docs/specs/wiki-agents/plan.md``:

- CT-1: ``discover_primitives`` recognises a ``kind: agent`` primitive
  under ``templates/agents/<name>/``.
- CT-26: ``discover_primitives`` tolerates a missing ``templates/agents/``
  directory the same way it tolerates other missing kind directories.
- ``is_installed_agent`` two-condition logic (name installed AND
  catalog declares ``kind: agent``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit.journal import replay_state
from llm_wiki_kit.models import (
    PrimitiveInstallEvent,
    PrimitiveKind,
    VaultState,
)
from llm_wiki_kit.primitives import discover_primitives, is_installed_agent

NOW = datetime(2026, 5, 24, 0, 0, 0, tzinfo=UTC)


def _write_primitive(
    root: Path,
    name: str,
    *,
    kind: str,
    version: str = "0.1.0",
    description: str = "Test primitive.",
) -> Path:
    """Write a minimal ``primitive.yaml`` and return the primitive dir."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "primitive.yaml").write_text(
        f"name: {name}\nkind: {kind}\nversion: {version}\ndescription: {description}\n",
        encoding="utf-8",
    )
    return root


def test_discover_primitives_recognizes_agent_kind_directory(tmp_path: Path) -> None:
    """CT-1 happy path: a ``templates/agents/<name>/primitive.yaml`` with
    ``kind: agent`` is enumerated and the returned primitive carries
    ``kind == PrimitiveKind.AGENT``."""

    _write_primitive(
        tmp_path / "agents" / "household-manager",
        name="household-manager",
        kind="agent",
    )
    found = discover_primitives(tmp_path)
    assert [p.name for p in found] == ["household-manager"]
    assert found[0].kind is PrimitiveKind.AGENT


def test_discover_primitives_tolerates_missing_agents_catalog_dir(tmp_path: Path) -> None:
    """CT-26: ``discover_primitives`` returns successfully (no exception)
    and yields zero ``PrimitiveKind.AGENT`` entries when ``templates/``
    contains non-agent kind directories but no ``templates/agents/``.

    Mirrors ``recipes.discover_recipes``'s absent-directory return
    (``recipes.py:112-113``) and ``discover_primitives``'s own
    permissive iteration over ``_CATALOG_DIRS``.
    """

    _write_primitive(
        tmp_path / "operations" / "weekly-digest",
        name="weekly-digest",
        kind="operation",
    )
    assert not (tmp_path / "agents").exists()

    found = discover_primitives(tmp_path)
    assert {p.kind for p in found} == {PrimitiveKind.OPERATION}
    assert not any(p.kind is PrimitiveKind.AGENT for p in found)


def test_is_installed_agent_returns_true_after_install_event(tmp_path: Path) -> None:
    """A ``PrimitiveInstallEvent`` paired with a ``kind: agent`` catalog
    entry resolves to ``True``."""

    _write_primitive(
        tmp_path / "templates" / "agents" / "household-manager",
        name="household-manager",
        kind="agent",
    )
    state = replay_state(
        [
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-add",
                primitive="household-manager",
                version="0.1.0",
            )
        ]
    )

    assert is_installed_agent("household-manager", state, kit_root=tmp_path) is True


def test_is_installed_agent_returns_false_for_non_agent_kind(tmp_path: Path) -> None:
    """The two-condition check fails when the name is installed but the
    catalog entry's kind is not ``agent``."""

    _write_primitive(
        tmp_path / "templates" / "operations" / "weekly-digest",
        name="weekly-digest",
        kind="operation",
    )
    state = replay_state(
        [
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-add",
                primitive="weekly-digest",
                version="0.1.0",
            )
        ]
    )

    assert is_installed_agent("weekly-digest", state, kit_root=tmp_path) is False


def test_is_installed_agent_returns_false_for_uninstalled_name(tmp_path: Path) -> None:
    """The two-condition check fails when the catalog declares the
    primitive as ``kind: agent`` but no ``PrimitiveInstallEvent`` has
    landed."""

    _write_primitive(
        tmp_path / "templates" / "agents" / "household-manager",
        name="household-manager",
        kind="agent",
    )
    state = VaultState()

    assert is_installed_agent("household-manager", state, kit_root=tmp_path) is False


def test_is_installed_agent_returns_false_when_catalog_absent(tmp_path: Path) -> None:
    """A vault state that thinks the primitive is installed but no
    catalog exists to confirm the kind resolves to ``False``.

    Pins the helper's behavior when ``kit_root`` doesn't carry a
    matching ``templates/`` (``discover_primitives`` returns ``[]``).
    """

    state = replay_state(
        [
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-add",
                primitive="household-manager",
                version="0.1.0",
            )
        ]
    )

    # No templates/ tree exists under tmp_path.
    assert is_installed_agent("household-manager", state, kit_root=tmp_path) is False
