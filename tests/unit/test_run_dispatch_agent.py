"""Tests for ``wiki run`` (dispatch-only) agent handling (RFC-0004 PR-5).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-17: dispatch-only mode only honors the CLI ``--agent`` flag.
  Recipe binding and contract ``preferred_agent`` are **not** walked
  (spec §"Resolution chain (at ``wiki run`` dispatch-only time)" —
  only step 1 applies). With ``--agent`` passed, the kit journals
  both ``OperationRunEvent`` and ``OperationRunByAgentEvent`` paired
  under one transaction; without ``--agent``, today's single-append
  ``OperationRunEvent`` shape is preserved even when a recipe
  binding would resolve under ``--exec``.

A dispatch-only invocation never invokes ``claude``; the kit just
records the dispatch. So we drive ``dispatch`` directly (no subprocess
stub needed) and assert on the journal slice.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    OperationRunByAgentEvent,
    OperationRunEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
)
from llm_wiki_kit.run import dispatch

NOW = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[2]


_WEEKLY_DIGEST_CONTRACT = """\
name: weekly-digest
description: Weekly digest test contract.
period: weekly
skill: weekly-digest
inputs:
  window:
    type: iso_week
outputs:
  digest:
    type: page
    path_pattern: outputs/digests/{window}.md
"""


_RECIPE_WITH_BINDING = """\
name: test-recipe
version: 0.1.0
description: Test recipe binding weekly-digest to household-manager.
primitives:
  - weekly-digest
  - household-manager
agents:
  household-manager:
    runs:
      - weekly-digest
"""


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    """A kit_root with weekly-digest, two agents, and a recipe binding."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    templates = kit / "templates"
    templates.mkdir()

    # weekly-digest operation primitive.
    op_dir = templates / "operations" / "weekly-digest"
    op_dir.mkdir(parents=True)
    (op_dir / "contract.yaml").write_text(_WEEKLY_DIGEST_CONTRACT, encoding="utf-8")
    (op_dir / "primitive.yaml").write_text(
        "name: weekly-digest\nkind: operation\nversion: 0.1.0\n"
        "description: weekly-digest test primitive.\n",
        encoding="utf-8",
    )
    (op_dir / "files").mkdir()

    # Two agent primitives — both installed in the vault below.
    for name in ("household-manager", "trip-planner"):
        agent_dir = templates / "agents" / name
        agent_dir.mkdir(parents=True)
        (agent_dir / "primitive.yaml").write_text(
            f"name: {name}\nkind: agent\nversion: 0.1.0\ndescription: {name} test agent.\n",
            encoding="utf-8",
        )

    # Recipe binding weekly-digest to household-manager. Lives at
    # kit/recipes/test-recipe.yaml so VaultInitEvent.recipe="test-recipe"
    # resolves to it. The recipe is **not** consulted in dispatch-only
    # mode — its presence here is the load-bearing negative half of
    # CT-17 ("the chain does not walk").
    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "test-recipe.yaml").write_text(_RECIPE_WITH_BINDING, encoding="utf-8")

    return kit


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A vault on the test-recipe with both agents installed."""

    v = tmp_path / "vault"
    (v / ".wiki.journal").mkdir(parents=True)
    journal_path = v / ".wiki.journal" / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=NOW,
            by="wiki-init",
            vault_name="test-vault",
            recipe="test-recipe",
        ),
    )
    for primitive in ("weekly-digest", "household-manager", "trip-planner"):
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-init",
                primitive=primitive,
                version="0.1.0",
            ),
        )
    return v


def _journal_events(vault: Path) -> list[object]:
    return list(read_events(vault / ".wiki.journal" / "journal.jsonl"))


def test_run_dispatch_only_honors_cli_agent_flag_without_chain_walk(
    vault: Path, kit_root: Path
) -> None:
    """CT-17: dispatch-only only walks step 1; recipe binding is ignored.

    Two halves:

    1. ``wiki run weekly-digest`` (no ``--agent``, no ``--exec``)
       — even though the recipe binds ``weekly-digest`` to
       ``household-manager``, the chain is **not** walked in
       dispatch-only mode (spec §"Resolution chain (at wiki run
       dispatch-only time)"). Journal contains exactly one
       ``OperationRunEvent`` and zero ``OperationRunByAgentEvent``.
    2. ``wiki run weekly-digest --agent trip-planner`` — the
       explicit CLI flag overrides; the chain still doesn't walk
       (no recipe inference). Journal contains both events paired
       under one transaction with ``agent="trip-planner"`` (NOT
       ``"household-manager"`` from the recipe).
    """

    journal_path = vault / ".wiki.journal" / "journal.jsonl"

    # ----- Half 1: no --agent → no chain walk, single append -----
    events_before = _journal_events(vault)
    baseline = len(events_before)

    result_no_agent = dispatch(
        "weekly-digest",
        ["--window=2026-W20"],
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
    )
    assert result_no_agent.status == "dispatched"
    assert result_no_agent.agent is None

    after_first = _journal_events(vault)
    new_events_1 = after_first[baseline:]
    op_events_1 = [e for e in new_events_1 if isinstance(e, OperationRunEvent)]
    by_agent_events_1 = [e for e in new_events_1 if isinstance(e, OperationRunByAgentEvent)]
    assert len(op_events_1) == 1
    assert by_agent_events_1 == []
    # And no transaction lock-pair fires for the no-agent path —
    # only the single ``append_event`` call's own per-line flock.
    assert op_events_1[0].operation == "weekly-digest"

    # ----- Half 2: --agent overrides; chain still doesn't walk -----
    result_with_agent = dispatch(
        "weekly-digest",
        ["--window=2026-W21"],
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
        agent="trip-planner",
    )
    assert result_with_agent.status == "dispatched"
    # The explicit flag wins — NOT the recipe's ``household-manager``.
    # This is the load-bearing assertion: the recipe binding is
    # invisible to dispatch-only mode.
    assert result_with_agent.agent == "trip-planner"

    after_second = _journal_events(vault)
    new_events_2 = after_second[len(after_first) :]
    op_events_2 = [e for e in new_events_2 if isinstance(e, OperationRunEvent)]
    by_agent_events_2 = [e for e in new_events_2 if isinstance(e, OperationRunByAgentEvent)]
    assert len(op_events_2) == 1
    assert len(by_agent_events_2) == 1
    assert by_agent_events_2[0].agent == "trip-planner"
    # Same event_id pairing as CT-16.
    assert op_events_2[0].event_id is not None
    assert op_events_2[0].event_id == by_agent_events_2[0].event_id


def test_run_dispatch_only_refuses_unknown_agent_with_no_journal_write(
    vault: Path, kit_root: Path
) -> None:
    """Dispatch-only ``--agent ghost`` → WikiError, zero journal events.

    Companion to CT-17: pins the spec line 506 contract that
    dispatch-only argv-shape errors abort at the CLI boundary with
    no journal write. Distinct from --exec mode (CT-15), which DOES
    journal one ``OperationExecFailedEvent``. The pre-transaction
    validation path makes "zero events" achievable; an in-transaction
    refusal would leak a lock-pair into the journal.
    """

    from llm_wiki_kit.errors import WikiError

    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    baseline = len(_journal_events(vault))

    with pytest.raises(WikiError) as excinfo:
        dispatch(
            "weekly-digest",
            ["--window=2026-W20"],
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
            agent="ghost",
        )
    # Dispatch-only message form (spec line 192).
    assert str(excinfo.value).startswith("agent 'ghost' is not installed")
    # Zero journal writes: not even a lock-pair.
    after = _journal_events(vault)
    assert len(after) == baseline
