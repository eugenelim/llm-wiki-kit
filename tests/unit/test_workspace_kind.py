"""T1 tests for ``PrimitiveKind.WORKSPACE`` wiring (workspace-primitive spec).

Two contracts, both goal-based per the plan:

1. **Discovery + ``wiki add`` resolution.** A ``kind: workspace`` primitive
   written into a ``tmp_path`` catalog dir is returned by
   :func:`discover_primitives`, and ``_parse_primitive_spec`` resolves the
   ``workspace:<name>`` argument to ``(PrimitiveKind.WORKSPACE, <name>)``.
   (Uses a temp catalog so T1 does not depend on the T5 example existing.)

2. **Enumerated audit.** For a ``kind: workspace`` primitive, the exclusive
   ``PrimitiveKind`` guard sites still *exclude* it: it is not a content-type
   (so ingest routing rejects it), it is not mistaken for an agent or
   operation, and it does not surface in ``list_agents``. There are no
   ``match`` statements on ``PrimitiveKind`` — every site is an ``is`` /
   ``is not`` guard — so ``mypy`` exhaustiveness cannot catch a missed site;
   the audit must be an explicit behavioral test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.cli import _parse_primitive_spec
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.ingest import route
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    Primitive,
    PrimitiveInstallEvent,
    PrimitiveKind,
    VaultInitEvent,
)
from llm_wiki_kit.primitives import discover_primitives, list_agents

NOW = datetime(2026, 6, 14, 9, 0, 0, tzinfo=UTC)


def _make_primitive(name: str, *, kind: str) -> Primitive:
    return Primitive.model_validate(
        {
            "name": name,
            "kind": kind,
            "version": "0.1.0",
            "description": f"{name} primitive.",
        }
    )


# ---------------------------------------------------------------------------
# Contract 1 — enum, discovery, and ``wiki add`` resolution
# ---------------------------------------------------------------------------


def test_workspace_kind_enum_value_exists() -> None:
    """``PrimitiveKind.WORKSPACE`` exists and stringifies to ``"workspace"``."""

    assert PrimitiveKind.WORKSPACE.value == "workspace"
    assert PrimitiveKind("workspace") is PrimitiveKind.WORKSPACE


def test_parse_primitive_spec_resolves_workspace() -> None:
    """``wiki add workspace:<name>`` resolves the kind via ``_parse_primitive_spec``."""

    assert _parse_primitive_spec("workspace:content-studio") == (
        PrimitiveKind.WORKSPACE,
        "content-studio",
    )


def test_discover_primitives_finds_workspace_in_catalog(tmp_path: Path) -> None:
    """A ``kind: workspace`` primitive under ``templates/workspaces/`` is discovered."""

    templates = tmp_path / "templates"
    ws_dir = templates / "workspaces" / "content-studio"
    ws_dir.mkdir(parents=True)
    (ws_dir / "primitive.yaml").write_text(
        "name: content-studio\n"
        "kind: workspace\n"
        "version: 0.1.0\n"
        "description: A content-studio lens.\n",
        encoding="utf-8",
    )

    catalog = discover_primitives(templates)
    by_name = {p.name: p for p in catalog}
    assert "content-studio" in by_name
    assert by_name["content-studio"].kind is PrimitiveKind.WORKSPACE


# ---------------------------------------------------------------------------
# Contract 2 — enumerated audit: the exclusive filters still exclude workspaces
# ---------------------------------------------------------------------------


def test_workspace_excluded_from_ingest_routing() -> None:
    """``route --as <workspace>`` rejects a workspace as a non-content-type.

    Pins the ``ingest.py`` exclusive content-type filters: a workspace
    name passed to ``--as`` is refused exactly like any other non-content
    -type primitive, never silently accepted as a route target.
    """

    ws = _make_primitive("content-studio", kind="workspace")
    with pytest.raises(WikiError) as excinfo:
        route("notes.md", [ws], as_override="content-studio")
    assert "not 'content-type'" in str(excinfo.value)


def test_workspace_excluded_from_list_agents(tmp_path: Path) -> None:
    """An installed workspace never surfaces as a row in ``list_agents``.

    Pins the ``primitives.list_agents`` ``kind is AGENT`` gate: a vault
    with a workspace installed (and no agents) yields ``[]``.
    """

    kit_root = tmp_path / "kit"
    # ``resolve_recipe_primitives`` / ``list_agents`` require a ``core``.
    core_dir = kit_root / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "primitive.yaml").write_text(
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
        encoding="utf-8",
    )
    ws_dir = kit_root / "templates" / "workspaces" / "content-studio"
    ws_dir.mkdir(parents=True)
    (ws_dir / "primitive.yaml").write_text(
        "name: content-studio\n"
        "kind: workspace\n"
        "version: 0.1.0\n"
        "description: A content-studio lens.\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir(parents=True)
    journal_path = journal_dir / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="minimal"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW, by="wiki-init", primitive="content-studio", version="0.1.0"
        ),
    )

    assert list_agents(vault, kit_root) == []
