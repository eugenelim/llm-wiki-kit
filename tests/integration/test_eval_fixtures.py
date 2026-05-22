"""Integration tests for the eval-suite seed-vault factories (RFC-0001 Task 20).

Each test exercises one per-family factory and asserts the resulting
vault is in the state the eval scenarios expect. Runs in the fast
lane (``pytest -m 'not slow and not eval'``) — no LLM involved.

The factory builders live in ``tests/evals/conftest.py``; we import
them as plain functions rather than using pytest fixtures so the
fast-lane integration tests aren't gated on the eval marker's
collection rules.

Spec: docs/specs/task-20-eval-harness/spec.md §AC6 + §"Fixture vaults"
Plan: docs/specs/task-20-eval-harness/plan.md Step 4
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import (
    PageProposalEvent,
    PrimitiveInstallEvent,
)
from tests.evals.conftest import (
    CONFLICT_FIXTURE_PATH,
    build_conflict_pending_vault,
    build_eval_kit,
    build_meal_planning_vault,
    build_research_cited_vault,
    build_research_dispatch_vault,
    build_stakeholder_map_refresh_vault,
    build_vault,
    build_weekly_digest_vault,
)


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    return build_eval_kit(tmp_path)


def _installed_primitives(vault: Path) -> set[str]:
    journal = vault / ".wiki.journal" / "journal.jsonl"
    return {ev.primitive for ev in read_events(journal) if isinstance(ev, PrimitiveInstallEvent)}


def test_minimal_seed_installs_core(tmp_path: Path, kit_root: Path) -> None:
    vault = build_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert installed == {"core"}


def test_weekly_digest_seed_has_meeting_and_operation(tmp_path: Path, kit_root: Path) -> None:
    vault = build_weekly_digest_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert {"core", "meeting", "weekly-digest"} <= installed
    # Fixture meeting page exists inside the W20 window.
    meeting = vault / "meetings" / "2026-05-12-q2-planning-kickoff.md"
    assert meeting.is_file()
    # The digest output does NOT exist yet — the outcome eval pins this.
    digest = vault / "outputs" / "digests" / "2026-W20.md"
    assert not digest.exists()
    # The `digest` outcome-verb trigger eval relies on a peer
    # SKILL existing alongside the `weekly-digest` operation SKILL
    # (the set-membership relaxation in
    # `tests/evals/trigger/test_outcome_verbs_trigger.py` is
    # load-bearing on this). The `meeting` content-type ships an
    # `ingest-meeting` SKILL — pin both directories so a refactor
    # that drops the peer fails this test loudly rather than
    # silently weakening the eval.
    assert _operation_skill_dir(vault, "weekly-digest").is_dir()
    assert _operation_skill_dir(vault, "ingest-meeting").is_dir()


def test_research_cited_seed_installs_research_stack(tmp_path: Path, kit_root: Path) -> None:
    vault = build_research_cited_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert {"core", "meeting", "research", "research-perplexity"} <= installed
    # The shared infrastructure config file lands at vault root per ADR-0007.
    assert (vault / "research-providers.yaml").is_file()
    # Pre-populated research page (the "research result" side of
    # provenance) — the eval reads its citations and propagates them.
    deployment = vault / "research" / "deployment.md"
    assert deployment.is_file()
    body = deployment.read_text(encoding="utf-8")
    assert "citations:" in body
    assert "https://example.invalid" in body


def test_conflict_pending_seed_has_real_proposal_event(tmp_path: Path, kit_root: Path) -> None:
    """Drift-replay produced a journaled PageProposalEvent + .proposed sidecar.

    Spec §"From the fixture vaults" pins this — a hand-authored
    sidecar without a matching event would be invisible to
    `wiki-conflict` (per the SKILL's documented failure mode).
    """

    vault = build_conflict_pending_vault(kit_root, tmp_path)
    journal = vault / ".wiki.journal" / "journal.jsonl"
    events = read_events(journal)
    proposals = [
        ev
        for ev in events
        if isinstance(ev, PageProposalEvent) and ev.path == CONFLICT_FIXTURE_PATH
    ]
    assert proposals, "drift replay did not emit a PageProposalEvent"

    sidecar = vault / (CONFLICT_FIXTURE_PATH + ".proposed")
    assert sidecar.is_file(), "drift replay did not leave a .proposed sidecar"


def test_research_dispatch_seed_installs_research_stack(tmp_path: Path, kit_root: Path) -> None:
    vault = build_research_dispatch_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert {"core", "research", "research-perplexity"} <= installed
    assert (vault / "research-providers.yaml").is_file()


def _operation_skill_dir(vault: Path, name: str) -> Path:
    return vault / "skills" / name


def test_meal_planning_seed_ships_operation_and_peer_ingest_skills(
    tmp_path: Path, kit_root: Path
) -> None:
    """Outcome-verb trigger eval depends on a peer ingest SKILL existing.

    The eval's set-membership assertion (matching SKILL was loaded
    at some point, not first-touch) is justified by the fact the
    vault carries peer SKILLs. This integration test pins that
    invariant: if a future refactor changes the seeded primitive
    set to install only the operation, the trigger eval's
    relaxation is no longer load-bearing — and this test fails
    loudly so the prompt-table docstring contract stays honest.
    """

    vault = build_meal_planning_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert {"core", "recipe", "meal-planning"} <= installed
    # `recipe` ships an ingester skill alongside the `meal-planning`
    # operation skill — confirms peer SKILLs exist for the eval.
    assert _operation_skill_dir(vault, "meal-planning").is_dir()
    assert _operation_skill_dir(vault, "ingest-recipe").is_dir()


def test_stakeholder_map_refresh_seed_ships_operation_and_peer_ingest_skills(
    tmp_path: Path, kit_root: Path
) -> None:
    vault = build_stakeholder_map_refresh_vault(kit_root, tmp_path)
    installed = _installed_primitives(vault)
    assert {"core", "stakeholder-update", "stakeholder-map-refresh"} <= installed
    assert _operation_skill_dir(vault, "stakeholder-map-refresh").is_dir()
    assert _operation_skill_dir(vault, "ingest-stakeholder-update").is_dir()
