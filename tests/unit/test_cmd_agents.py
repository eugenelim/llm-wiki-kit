"""Tests for ``wiki agents`` (RFC-0004 wiki-agents PR-6).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-18: ``wiki agents`` reports installed agents with NAME / RECIPES /
  OPERATIONS populated; empty vault prints only the header.
- CT-19: RECIPES column is the union of two relations — recipe
  ``agents:`` block membership OR ``primitives:`` closure membership.
  Exercised via a fixture kit_root under ``tmp_path`` (no
  ``tests/fixtures/repo/`` static dependency) because the v1 shipped
  catalog doesn't naturally exercise rule (b) (every default agent's
  RECIPES matches its ``agents:`` block).

The tests build a minimal kit_root with two recipes that together
exercise both contribution rules, plus an empty-vault sanity check
pinning the header-only output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import PrimitiveInstallEvent, VaultInitEvent
from llm_wiki_kit.primitives import AgentRow, list_agents

NOW = datetime(2026, 5, 24, 9, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixture kit_root builder
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _build_kit_root(
    tmp_path: Path,
    *,
    operations: tuple[tuple[str, str | None], ...] = (),
    agents: tuple[str, ...] = (),
    recipes: tuple[tuple[str, tuple[str, ...], str], ...] = (),
) -> Path:
    """Build a minimal kit_root with a core + operations + agents + recipes.

    ``operations`` is a tuple of ``(name, preferred_agent_or_None)``;
    ``agents`` lists agent primitive names to ship; ``recipes`` is a
    tuple of ``(recipe_name, primitives_tuple, agents_block_yaml)``
    where ``agents_block_yaml`` is the literal YAML for the recipe's
    ``agents:`` block (e.g. ``"agents:\\n  X:\\n    runs:\\n      -
    op1\\n"`` or ``"agents: {}\\n"``).
    """

    kit_root = tmp_path / "kit-root"

    # Core primitive — required by ``recipes.resolve_recipe_primitives``.
    _write_yaml(
        kit_root / "core" / "primitive.yaml",
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
    )

    for op_name, preferred in operations:
        _write_yaml(
            kit_root / "templates" / "operations" / op_name / "primitive.yaml",
            f"name: {op_name}\nkind: operation\nversion: 0.1.0\ndescription: {op_name}.\n",
        )
        contract_body = (
            f"name: {op_name}\ndescription: {op_name}.\nperiod: weekly\nskill: {op_name}\n"
        )
        if preferred is not None:
            contract_body += f"preferred_agent: {preferred}\n"
        _write_yaml(
            kit_root / "templates" / "operations" / op_name / "contract.yaml",
            contract_body,
        )

    for agent_name in agents:
        _write_yaml(
            kit_root / "templates" / "agents" / agent_name / "primitive.yaml",
            f"name: {agent_name}\nkind: agent\nversion: 0.1.0\ndescription: {agent_name}.\n",
        )

    for recipe_name, primitives_list, agents_block in recipes:
        primitives_yaml = "\n".join(f"  - {p}" for p in primitives_list)
        _write_yaml(
            kit_root / "recipes" / f"{recipe_name}.yaml",
            (
                f"name: {recipe_name}\n"
                "version: 0.1.0\n"
                f"description: {recipe_name} recipe.\n"
                "primitives:\n"
                f"{primitives_yaml}\n"
                f"{agents_block}"
            ),
        )

    return kit_root


def _seed_vault(
    tmp_path: Path,
    *,
    recipe_name: str,
    installed: tuple[str, ...],
) -> Path:
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
    for primitive_name in installed:
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-init",
                primitive=primitive_name,
                version="0.1.0",
            ),
        )
    return vault


# ---------------------------------------------------------------------------
# CT-18 — three installed agents under a single recipe; unbound renders as `—`
# ---------------------------------------------------------------------------


def test_agents_lists_installed_with_recipes_and_operations(tmp_path: Path) -> None:
    """CT-18: family-recipe-like fixture with three bound agents + one unbound.

    Pins:
    - bound agents render with comma-sorted operations;
    - an installed-but-unbound agent renders with ``OPERATIONS`` as
      the empty list (CLI surfaces ``—``);
    - row order is alphabetical by NAME.
    """

    kit_root = _build_kit_root(
        tmp_path,
        operations=(
            ("weekly-digest", None),
            ("meal-planning", None),
            ("trip-prep", None),
            ("medical-summary", None),
        ),
        agents=(
            "household-manager",
            "trip-planner",
            "care-coordinator",
            "decision-companion",  # installed but unbound (CT-18 contract)
        ),
        recipes=(
            (
                "family",
                (
                    "weekly-digest",
                    "meal-planning",
                    "trip-prep",
                    "medical-summary",
                    "household-manager",
                    "trip-planner",
                    "care-coordinator",
                    "decision-companion",
                ),
                (
                    "agents:\n"
                    "  household-manager:\n"
                    "    runs:\n"
                    "      - weekly-digest\n"
                    "      - meal-planning\n"
                    "  trip-planner:\n"
                    "    runs:\n"
                    "      - trip-prep\n"
                    "  care-coordinator:\n"
                    "    runs:\n"
                    "      - medical-summary\n"
                ),
            ),
        ),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="family",
        installed=(
            "weekly-digest",
            "meal-planning",
            "trip-prep",
            "medical-summary",
            "household-manager",
            "trip-planner",
            "care-coordinator",
            "decision-companion",
        ),
    )

    rows = list_agents(vault, kit_root)

    assert [row.name for row in rows] == [
        "care-coordinator",
        "decision-companion",
        "household-manager",
        "trip-planner",
    ]
    by_name = {row.name: row for row in rows}
    assert by_name["household-manager"].operations == ["meal-planning", "weekly-digest"]
    assert by_name["household-manager"].recipes == ["family"]
    assert by_name["trip-planner"].operations == ["trip-prep"]
    assert by_name["care-coordinator"].operations == ["medical-summary"]
    # decision-companion: installed via the recipe closure, no `agents:`
    # binding, no `preferred_agent` — OPERATIONS is the empty list.
    # RECIPES is non-empty because the closure includes it (rule b).
    assert by_name["decision-companion"].operations == []
    assert by_name["decision-companion"].recipes == ["family"]


# ---------------------------------------------------------------------------
# CT-19 — RECIPES is the union of `agents:` block + `primitives:` closure
# ---------------------------------------------------------------------------


def test_agents_unions_recipes_via_block_and_closure(tmp_path: Path) -> None:
    """CT-19: a recipe contributes when EITHER (a) its agents: block names
    the agent, OR (b) the agent is in its primitives: closure (unbound).

    The fixture ships two recipes:
    - ``personal``: binds ``personal-coordinator`` via ``agents:``.
    - ``family``: lists ``personal-coordinator`` in ``primitives:`` but
      has no ``agents:`` entry for it.

    The expected RECIPES column for ``personal-coordinator`` is the
    sorted union ``["family", "personal"]``; OPERATIONS surfaces only
    the binding-carrying recipe's ``runs:`` list (``weekly-digest``).
    """

    kit_root = _build_kit_root(
        tmp_path,
        operations=(("weekly-digest", None),),
        agents=("personal-coordinator",),
        recipes=(
            (
                "personal",
                ("weekly-digest", "personal-coordinator"),
                ("agents:\n  personal-coordinator:\n    runs:\n      - weekly-digest\n"),
            ),
            (
                "family",
                ("weekly-digest", "personal-coordinator"),
                "agents: {}\n",
            ),
        ),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="personal",
        installed=("weekly-digest", "personal-coordinator"),
    )

    rows = list_agents(vault, kit_root)

    assert rows == [
        AgentRow(
            name="personal-coordinator",
            recipes=["family", "personal"],
            operations=["weekly-digest"],
        )
    ]


def test_agents_unions_operations_via_runs_and_preferred_agent(tmp_path: Path) -> None:
    """OPERATIONS is the union of ``agents.<name>.runs`` + ``preferred_agent``.

    Pins spec §Outputs ``wiki agents`` rule for the OPERATIONS column
    when both relations contribute distinct operations to the same agent.
    """

    kit_root = _build_kit_root(
        tmp_path,
        operations=(
            ("weekly-digest", None),
            ("decision-review", "decision-companion"),
        ),
        agents=("decision-companion",),
        recipes=(
            (
                "personal",
                ("weekly-digest", "decision-review", "decision-companion"),
                ("agents:\n  decision-companion:\n    runs:\n      - weekly-digest\n"),
            ),
        ),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="personal",
        installed=("weekly-digest", "decision-review", "decision-companion"),
    )

    rows = list_agents(vault, kit_root)
    assert len(rows) == 1
    assert rows[0].name == "decision-companion"
    assert rows[0].operations == ["decision-review", "weekly-digest"]


# ---------------------------------------------------------------------------
# Empty-vault path — only the header line emitted
# ---------------------------------------------------------------------------


def test_agents_empty_vault_returns_empty_list(tmp_path: Path) -> None:
    """A vault with no installed agents returns ``[]``.

    The CLI's ``_cmd_agents`` then prints only the header line and
    exits ``0`` (verified at the CLI layer below).
    """

    kit_root = _build_kit_root(
        tmp_path,
        operations=(("weekly-digest", None),),
        agents=(),
        recipes=(("test", ("weekly-digest",), "agents: {}\n"),),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="test",
        installed=("weekly-digest",),
    )

    assert list_agents(vault, kit_root) == []


def test_agents_no_journal_returns_empty_list(tmp_path: Path) -> None:
    """A vault directory with no journal returns ``[]`` (matches
    ``installed_outcome_verbs`` precedent — the helper is pure; the
    "not a vault" message is the CLI's boundary)."""

    vault = tmp_path / "vault"
    vault.mkdir()
    kit_root = _build_kit_root(tmp_path)
    assert list_agents(vault, kit_root) == []


# ---------------------------------------------------------------------------
# CLI integration — header-only on empty vault; TSV on populated
# ---------------------------------------------------------------------------


def test_cmd_agents_empty_vault_prints_only_header(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-18 corollary: empty vault prints only ``NAME\\tRECIPES\\tOPERATIONS``."""

    import argparse

    from llm_wiki_kit.cli import _cmd_agents

    kit_root = _build_kit_root(
        tmp_path,
        operations=(("weekly-digest", None),),
        agents=(),
        recipes=(("test", ("weekly-digest",), "agents: {}\n"),),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="test",
        installed=("weekly-digest",),
    )
    monkeypatch.chdir(vault)

    args = argparse.Namespace(kit_root=kit_root)
    rc = _cmd_agents(args)
    assert rc == 0

    captured = capsys.readouterr()
    assert captured.out == "NAME\tRECIPES\tOPERATIONS\n"


def test_cmd_agents_populated_vault_emits_tsv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Populated vault: TSV header + one row per installed agent, em-dash for empty."""

    import argparse

    from llm_wiki_kit.cli import _cmd_agents

    kit_root = _build_kit_root(
        tmp_path,
        operations=(("weekly-digest", None),),
        agents=("household-manager", "decision-companion"),
        recipes=(
            (
                "personal",
                ("weekly-digest", "household-manager", "decision-companion"),
                ("agents:\n  household-manager:\n    runs:\n      - weekly-digest\n"),
            ),
        ),
    )
    vault = _seed_vault(
        tmp_path,
        recipe_name="personal",
        installed=("weekly-digest", "household-manager", "decision-companion"),
    )
    monkeypatch.chdir(vault)

    args = argparse.Namespace(kit_root=kit_root)
    rc = _cmd_agents(args)
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "NAME\tRECIPES\tOPERATIONS"
    # Alphabetical: decision-companion < household-manager
    assert out[1] == "decision-companion\tpersonal\t—"
    assert out[2] == "household-manager\tpersonal\tweekly-digest"
