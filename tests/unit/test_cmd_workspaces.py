"""T6 tests for ``wiki workspaces`` (workspace-primitive spec).

Mirrors ``wiki agents``' *structure and behavior* (vault-scoped, read-only,
header-then-rows, empty→header-only→exit 0, non-vault→standard error) but
defines its own NAME/SCOPE/AGENT/OPERATIONS columns backed by a new
``WorkspaceRow`` type (not ``AgentRow``).
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.cli import _cmd_workspaces
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import PrimitiveInstallEvent, VaultInitEvent
from llm_wiki_kit.primitives import WorkspaceRow, list_workspaces

NOW = datetime(2026, 6, 14, 9, 0, 0, tzinfo=UTC)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _build_kit_root(tmp_path: Path) -> Path:
    """Kit with core, a referenced agent, and two workspaces (scoped + cross-cutting)."""

    kit_root = tmp_path / "kit-root"
    _write(
        kit_root / "core" / "primitive.yaml",
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
    )
    _write(
        kit_root / "templates" / "agents" / "personal-coordinator" / "primitive.yaml",
        "name: personal-coordinator\nkind: agent\nversion: 0.1.0\ndescription: pc.\n",
    )
    _write(
        kit_root / "templates" / "workspaces" / "content-studio" / "primitive.yaml",
        "name: content-studio\n"
        "kind: workspace\n"
        "version: 0.1.0\n"
        "description: studio lens.\n"
        "scope:\n  workspaces:\n    - content-studio\n"
        "agent: personal-coordinator\n",
    )
    # A cross-cutting lens: empty/absent scope ⇒ covers all notes.
    _write(
        kit_root / "templates" / "workspaces" / "planning" / "primitive.yaml",
        "name: planning\nkind: workspace\nversion: 0.1.0\ndescription: planning lens.\n",
    )
    # A multi-membership lens with multiple operations — exercises the
    # comma-join + sort render branches for both SCOPE and OPERATIONS.
    _write(
        kit_root / "templates" / "workspaces" / "research-desk" / "primitive.yaml",
        "name: research-desk\n"
        "kind: workspace\n"
        "version: 0.1.0\n"
        "description: research lens.\n"
        "scope:\n  workspaces:\n    - research\n    - content-studio\n"
        "operations:\n  - weekly-digest\n  - meal-planning\n",
    )
    return kit_root


def _seed_vault(tmp_path: Path, *, installed: tuple[str, ...]) -> Path:
    vault = tmp_path / "vault"
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir(parents=True)
    journal_path = journal_dir / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="r"),
    )
    for name in installed:
        append_event(
            journal_path,
            PrimitiveInstallEvent(timestamp=NOW, by="wiki-init", primitive=name, version="0.1.0"),
        )
    return vault


# ---------------------------------------------------------------------------
# list_workspaces — rows for installed workspaces; scoped + cross-cutting
# ---------------------------------------------------------------------------


def test_list_workspaces_returns_rows_for_installed_workspaces(tmp_path: Path) -> None:
    kit_root = _build_kit_root(tmp_path)
    vault = _seed_vault(tmp_path, installed=("personal-coordinator", "content-studio", "planning"))

    rows = list_workspaces(vault, kit_root)

    assert rows == [
        WorkspaceRow(
            name="content-studio",
            scope=["content-studio"],
            agent="personal-coordinator",
            operations=[],
        ),
        WorkspaceRow(name="planning", scope=[], agent=None, operations=[]),
    ]


def test_list_workspaces_empty_vault_returns_empty_list(tmp_path: Path) -> None:
    kit_root = _build_kit_root(tmp_path)
    vault = _seed_vault(tmp_path, installed=("personal-coordinator",))
    assert list_workspaces(vault, kit_root) == []


def test_list_workspaces_no_journal_returns_empty_list(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    kit_root = _build_kit_root(tmp_path)
    assert list_workspaces(vault, kit_root) == []


# ---------------------------------------------------------------------------
# CLI — header-only on empty, full table on populated, error outside a vault
# ---------------------------------------------------------------------------


def test_cmd_workspaces_empty_vault_prints_only_header(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    kit_root = _build_kit_root(tmp_path)
    vault = _seed_vault(tmp_path, installed=("personal-coordinator",))
    monkeypatch.chdir(vault)

    rc = _cmd_workspaces(argparse.Namespace(kit_root=kit_root))
    assert rc == 0
    assert capsys.readouterr().out == "NAME\tSCOPE\tAGENT\tOPERATIONS\n"


def test_cmd_workspaces_populated_vault_emits_tsv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    kit_root = _build_kit_root(tmp_path)
    vault = _seed_vault(tmp_path, installed=("personal-coordinator", "content-studio", "planning"))
    monkeypatch.chdir(vault)

    rc = _cmd_workspaces(argparse.Namespace(kit_root=kit_root))
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "NAME\tSCOPE\tAGENT\tOPERATIONS"
    # Alphabetical by NAME: content-studio < planning.
    assert out[1] == "content-studio\tcontent-studio\tpersonal-coordinator\t—"
    # Cross-cutting lens (empty scope) renders "(all notes)"; no agent ⇒ em-dash.
    assert out[2] == "planning\t(all notes)\t—\t—"


def test_workspaces_render_multi_tag_scope_and_operations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multi-membership scope + multiple operations render sorted, comma-joined.

    Exercises the ``", ".join`` + sort branches of both the SCOPE and
    OPERATIONS columns — the single-element/empty fixtures above only reach
    the one-element and em-dash branches. Asserts at both layers: the
    ``WorkspaceRow`` value (sorted lists) and the rendered TSV cell.
    """

    kit_root = _build_kit_root(tmp_path)
    vault = _seed_vault(tmp_path, installed=("research-desk",))

    rows = list_workspaces(vault, kit_root)
    assert rows == [
        WorkspaceRow(
            name="research-desk",
            scope=["content-studio", "research"],
            agent=None,
            operations=["meal-planning", "weekly-digest"],
        )
    ]

    monkeypatch.chdir(vault)
    assert _cmd_workspaces(argparse.Namespace(kit_root=kit_root)) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "NAME\tSCOPE\tAGENT\tOPERATIONS"
    assert out[1] == "research-desk\tcontent-studio, research\t—\tmeal-planning, weekly-digest"


def test_cmd_workspaces_outside_vault_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit_root = _build_kit_root(tmp_path)
    empty = tmp_path / "not-a-vault"
    empty.mkdir()
    monkeypatch.chdir(empty)
    with pytest.raises(WikiError) as excinfo:
        _cmd_workspaces(argparse.Namespace(kit_root=kit_root))
    assert "not a wiki vault" in str(excinfo.value)
