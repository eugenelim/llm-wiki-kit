"""Shared fixtures for the eval suite (RFC-0001 Task 20).

Per-family `tmp_path_factory` factories that build session-scoped seed
vaults via the real kit CLI, then function-scoped wrappers that copy
the seed into a per-test ``tmp_path`` so each scenario gets a clean
mutable target. Spec ``§Inputs"From the fixture vaults"`` pins this
shape.

The fixtures are intentionally pytest-only — they import the kit's
runtime modules (``cli``, ``write_helper``) but never the harness
(``evalkit``). Tests that need the harness import it directly.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.write_helper import safe_write

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Builder helpers — also called directly from `tests/integration/test_eval_fixtures.py`
# ---------------------------------------------------------------------------


def build_eval_kit(parent: Path) -> Path:
    """Build a tmp kit with the real ``core/`` + ``templates/`` + a minimal recipe.

    The recipes/ directory ships exactly one recipe (``minimal``)
    because every eval factory installs primitives via ``wiki add``
    rather than via a full-fat recipe — that keeps the per-family
    diff between factories small and obvious.
    """

    kit = parent / "eval-kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    shutil.copytree(REPO_ROOT / "templates", kit / "templates")
    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: Core only — primitives added via wiki add per eval family.\n"
        "primitives: []\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


def build_vault(kit_root: Path, parent: Path, *adds: str) -> Path:
    """Init a vault under ``parent`` and ``wiki add`` the listed primitives.

    ``wiki add`` reads ``cwd`` to find the vault; we use
    ``contextlib.chdir`` (Python 3.11+) to scope the cwd change to
    the add sequence so this helper is safe to call from
    session-scoped fixtures without leaking cwd into other tests.

    ``--no-git`` is passed because (a) the eval suite is testing
    skill outcomes, not git semantics, and (b) this helper runs from
    session-scoped fixtures that fire before any function-scoped
    autouse ``GIT_AUTHOR_*`` fixture activates, so a default git-init
    would hit the missing-identity failure on a hermetic CI runner.
    """

    vault = parent / "vault"
    assert cli.main(["init", str(vault), "--recipe", "minimal", "--no-git"], kit_root=kit_root) == 0
    if adds:
        with contextlib.chdir(vault):
            for primitive in adds:
                assert cli.main(["add", primitive], kit_root=kit_root) == 0, (
                    f"wiki add {primitive!r} failed"
                )
    return vault


def build_weekly_digest_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for outcome evals: meeting + weekly-digest + one fixture meeting."""

    vault = build_vault(
        kit_root,
        parent,
        "content-type:meeting",
        "operation:weekly-digest",
    )
    sample_src = (
        REPO_ROOT / "templates" / "operations" / "weekly-digest" / "fixtures" / "sample-meeting.md"
    )
    meetings_dir = vault / "meetings"
    meetings_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(sample_src, meetings_dir / "2026-05-12-q2-planning-kickoff.md")
    return vault


def build_meal_planning_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for the `plan-meals` outcome-verb trigger eval.

    Installs the family-subset needed to surface the
    `meal-planning` operation: the `recipe` content-type
    (which transitively pulls in the `food` ontology) plus
    the `meal-planning` operation itself. Matches the
    `weekly-digest` seed's shape — explicit content-type
    plus explicit operation — so a maintainer scanning the
    factories sees the same pattern per family.
    """

    return build_vault(
        kit_root,
        parent,
        "content-type:recipe",
        "operation:meal-planning",
    )


def build_stakeholder_map_refresh_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for the `refresh-stakeholders` outcome-verb trigger eval.

    Installs the work-os subset needed to surface the
    `stakeholder-map-refresh` operation: the
    `stakeholder-update` content-type (which transitively
    pulls in the `people` and `projects` ontologies) plus
    the operation itself.
    """

    return build_vault(
        kit_root,
        parent,
        "content-type:stakeholder-update",
        "operation:stakeholder-map-refresh",
    )


RESEARCH_CITED_DOC = """\
---
provider: perplexity
model: sonar-pro
query: how does llm-wiki-kit handle deployment
fetched_at: '2026-05-18T12:00:00+00:00'
citations:
- https://example.invalid/deployment-guide
- https://example.invalid/runtime-deps
---

The kit ships as a pip-installable Python package. Runtime deps are
pyyaml and pydantic, plus stdlib. Per ADR-0001 the kit deliberately
keeps the dep surface small so end users (non-engineers) can install
it without fighting the Python ecosystem.
"""


def build_research_cited_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for provenance evals: meeting + research + perplexity provider.

    Pre-populates ``research/deployment.md`` (the "research result"
    side of provenance) so the eval can test propagation — Claude
    reads the citations and writes a consuming note that cites them.
    A pytest monkeypatch cannot reach across process boundaries into
    the subprocess that ``claude`` would spawn for ``wiki research``,
    so the eval doesn't invoke that command; 5e and 5f cover the
    dispatch path directly.
    """

    vault = build_vault(
        kit_root,
        parent,
        "content-type:meeting",
        "infrastructure:research",
        "infrastructure:research-perplexity",
    )
    research_dir = vault / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "deployment.md").write_text(RESEARCH_CITED_DOC, encoding="utf-8")
    return vault


def build_research_dispatch_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for research evals (5e + 5f): research + perplexity provider."""

    return build_vault(
        kit_root,
        parent,
        "infrastructure:research",
        "infrastructure:research-perplexity",
    )


def build_conflict_pending_vault(kit_root: Path, parent: Path) -> Path:
    """Seed for conflict evals: real drift state with PageProposalEvent."""

    vault = build_vault(kit_root, parent)
    _drive_drift(vault)
    return vault


# ---------------------------------------------------------------------------
# Tmp kit shared across the whole eval session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def eval_kit_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_eval_kit(tmp_path_factory.mktemp("kit"))


# ---------------------------------------------------------------------------
# Family 1: minimal (trigger evals — core only)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_minimal(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_vault(eval_kit_root, tmp_path_factory.mktemp("seed-minimal"))


@pytest.fixture
def minimal_vault(tmp_path: Path, _seed_minimal: Path) -> Path:
    """Function-scoped copy of the minimal seed."""

    dest = tmp_path / "vault"
    shutil.copytree(_seed_minimal, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 2: weekly-digest (outcome evals — core + meeting + weekly-digest)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_weekly_digest(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_weekly_digest_vault(eval_kit_root, tmp_path_factory.mktemp("seed-weekly-digest"))


@pytest.fixture
def weekly_digest_vault(tmp_path: Path, _seed_weekly_digest: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_weekly_digest, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 3: research-cited (provenance evals)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_research_cited(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_research_cited_vault(eval_kit_root, tmp_path_factory.mktemp("seed-research-cited"))


@pytest.fixture
def research_cited_vault(tmp_path: Path, _seed_research_cited: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_research_cited, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 4: conflict-pending (drift replay → real PageProposalEvent)
# ---------------------------------------------------------------------------


CONFLICT_FIXTURE_PATH = "meetings/2026-05-12-q2.md"
CONFLICT_BASELINE = "# Q2 planning\n\nBaseline content the kit last wrote.\n"
CONFLICT_USER_EDIT = "# Q2 planning\n\nUser's hand-edited body.\n"
CONFLICT_PROPOSED = "# Q2 planning\n\nKit's proposed update.\n"


def _drive_drift(vault: Path) -> None:
    """Replay a real drift: baseline → user-edits-on-disk → proposed-write → sidecar.

    The middle ``Path.write_text`` is a deliberate fixture carve-out
    that simulates a user opening their editor — the AGENTS.md
    "every kit write goes through safe_write" rule applies to *kit*
    writes, not to test fixtures simulating user behavior. Plan §4
    documents the carve-out.
    """

    journal = vault / ".wiki.journal" / "journal.jsonl"
    target = vault / CONFLICT_FIXTURE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    # Step 1: baseline write via safe_write — emits PageWriteEvent.
    safe_write(target, CONFLICT_BASELINE, by="core", journal_path=journal)
    # Step 2: simulated user edit — bypasses the kit.
    target.write_text(CONFLICT_USER_EDIT, encoding="utf-8")
    # Step 3: kit tries to update; drift detected; sidecar dropped
    # and PageProposalEvent emitted.
    safe_write(target, CONFLICT_PROPOSED, by="core", journal_path=journal)
    sidecar = target.with_name(target.name + ".proposed")
    assert sidecar.is_file(), "drift replay failed: no .proposed sidecar"


@pytest.fixture(scope="session")
def _seed_conflict_pending(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_conflict_pending_vault(
        eval_kit_root, tmp_path_factory.mktemp("seed-conflict-pending")
    )


@pytest.fixture
def conflict_pending_vault(tmp_path: Path, _seed_conflict_pending: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_conflict_pending, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 5: research-dispatch (5e dispatch-contract + 5f live Perplexity)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_research_dispatch(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_research_dispatch_vault(
        eval_kit_root, tmp_path_factory.mktemp("seed-research-dispatch")
    )


@pytest.fixture
def research_dispatch_vault(tmp_path: Path, _seed_research_dispatch: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_research_dispatch, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 6: meal-planning (outcome-verb trigger eval — `plan-meals`)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_meal_planning(tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path) -> Path:
    return build_meal_planning_vault(eval_kit_root, tmp_path_factory.mktemp("seed-meal-planning"))


@pytest.fixture
def meal_planning_vault(tmp_path: Path, _seed_meal_planning: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_meal_planning, dest)
    return dest


# ---------------------------------------------------------------------------
# Family 7: stakeholder-map-refresh (outcome-verb trigger eval — `refresh-stakeholders`)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _seed_stakeholder_map_refresh(
    tmp_path_factory: pytest.TempPathFactory, eval_kit_root: Path
) -> Path:
    return build_stakeholder_map_refresh_vault(
        eval_kit_root, tmp_path_factory.mktemp("seed-stakeholder-map-refresh")
    )


@pytest.fixture
def stakeholder_map_refresh_vault(tmp_path: Path, _seed_stakeholder_map_refresh: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_stakeholder_map_refresh, dest)
    return dest


# ---------------------------------------------------------------------------
# Recipe-level vault builders (wiki-bootstrap evals)
# ---------------------------------------------------------------------------
#
# Unlike the families above, these init from a *real* shipped recipe
# (personal / family / work-os) against the repo's `recipes/` directory.
# We therefore use the real REPO_ROOT as the kit root, not the tmp
# `eval_kit_root` (which only ships the `minimal` recipe).


def _build_recipe_vault(parent: Path, recipe: str) -> Path:
    """``wiki init <parent>/<recipe>-vault --recipe <recipe> --no-git``.

    ``--no-git`` is used for the same reason the seed builders above
    use it: session-scoped fixtures fire before the function-scoped
    autouse ``GIT_AUTHOR_*`` env fixture, so a default git-init would
    hit a missing-identity failure on a hermetic CI runner. See
    ``build_weekly_digest_vault`` for the canonical rationale.
    """

    vault = parent / f"{recipe}-vault"
    assert cli.main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0, (
        f"`wiki init --recipe {recipe}` failed"
    )
    return vault


def build_personal_vault(parent: Path) -> Path:
    """Seed for wiki-bootstrap evals: full `personal` recipe install.

    Unlike the other ``build_*_vault`` factories in this file, the
    personal/family/work-os recipes are shipped *inside the repo*
    and resolved against the default kit root — they do not need
    the tmp ``eval_kit_root`` that the ``minimal``-based families
    require. No ``kit_root`` parameter for that reason.
    """

    return _build_recipe_vault(parent, "personal")


def build_family_vault(parent: Path) -> Path:
    """Seed for wiki-bootstrap evals: full `family` recipe install.

    See :func:`build_personal_vault` for the kit-root rationale.
    """

    return _build_recipe_vault(parent, "family")


def build_work_os_vault(parent: Path) -> Path:
    """Seed for wiki-bootstrap evals: full `work-os` recipe install.

    See :func:`build_personal_vault` for the kit-root rationale.
    """

    return _build_recipe_vault(parent, "work-os")


# Pinned timestamp used by ``bootstrapped_personal_vault`` so the
# marker is deterministic across runs. Format matches the SKILL's
# write contract (ISO-8601 UTC, single line, trailing newline).
_BOOTSTRAP_MARKER_TIMESTAMP = "2026-01-01T00:00:00Z\n"


@pytest.fixture(scope="session")
def _seed_personal(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_personal_vault(tmp_path_factory.mktemp("seed-personal"))


@pytest.fixture
def personal_vault(tmp_path: Path, _seed_personal: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_personal, dest)
    return dest


@pytest.fixture(scope="session")
def _seed_family(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_family_vault(tmp_path_factory.mktemp("seed-family"))


@pytest.fixture
def family_vault(tmp_path: Path, _seed_family: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_family, dest)
    return dest


@pytest.fixture(scope="session")
def _seed_work_os(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_work_os_vault(tmp_path_factory.mktemp("seed-work-os"))


@pytest.fixture
def work_os_vault(tmp_path: Path, _seed_work_os: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(_seed_work_os, dest)
    return dest


@pytest.fixture
def bootstrapped_personal_vault(personal_vault: Path) -> Path:
    """Personal vault with a valid marker file.

    Used by T5.2 (``test_idempotent_rerun_writes_nothing``) and T6.3
    (``test_post_bootstrap_short_circuits``) for short-circuit
    re-run testing. Do NOT use for replacement-flow coverage — T5.6
    (``test_unreadable_marker_*``) writes its own mode-0o000 marker
    inline.
    """

    (personal_vault / ".wiki.bootstrap").write_text(_BOOTSTRAP_MARKER_TIMESTAMP, encoding="utf-8")
    return personal_vault


@pytest.fixture
def no_verbs_vault(minimal_vault: Path) -> Path:
    """Minimal vault with zero installed outcome verbs.

    The `minimal` recipe installs no primitives; every eval family
    above adds primitives explicitly via `wiki add`. A `minimal`
    vault therefore has `wiki outcomes` returning an empty set,
    which is exactly the AC 13 condition (``test_no_verbs_degradation``).
    """

    return minimal_vault
