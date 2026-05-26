"""End-to-end ``wiki outcomes`` integration tests for the PR-8 catalog rollout.

Pins spec §"Three concrete worked examples" against the real shipped
catalog: each recipe's outcome verbs surface in ``wiki outcomes`` after
``wiki init``. Run against the bundled kit assets (no kit_root override)
because PR-8 is the rollout for the *shipped* catalog — fixture-only
tests would not catch a regression in the real contract YAMLs.

**Test-shape note (intentional overlap).** This file ships both a
parametrized test (``test_wiki_init_recipe_surfaces_declared_outcome_verbs``)
and three plan-named per-recipe tests. The parametrized covers
"the verb *set* surfaces correctly for each recipe"; the named tests
cover "each row's `(verb, operation, skill)` tuple is exact". The
two shapes catch different regression classes: a parametrized-only
suite would miss a stale-skill-column bug for one recipe; a
named-only suite would not surface verb-set drift in a uniform
shape. Both are kept for grep-readability per plan §PR-8 step 1
naming. Each recipe install runs twice as a result — acceptable
because `wiki init --recipe <name>` is sub-second against the
bundled in-memory catalog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main


@pytest.mark.parametrize(
    ("recipe", "expected_verbs", "vault_dir"),
    [
        # Personal recipe installs weekly-digest + meal-planning.
        ("personal", ["digest", "plan-meals"], "personal-vault"),
        # Family recipe installs both as well (same operation set
        # at the verb-declaring slice).
        ("family", ["digest", "plan-meals"], "family-vault"),
        # Work-OS recipe installs stakeholder-map-refresh only;
        # does NOT install weekly-digest or meal-planning (see
        # recipes/work-os.yaml). Spec §"Three concrete worked
        # examples" reads "every recipe that installs
        # `weekly-digest` (today: `family` and `personal`)" —
        # `work-os` does not. Amended in this PR; see
        # spec.md §"Three concrete worked examples".
        ("work-os", ["refresh-stakeholders"], "work-os-vault"),
    ],
    ids=["personal", "family", "work-os"],
)
def test_wiki_init_recipe_surfaces_declared_outcome_verbs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    recipe: str,
    expected_verbs: list[str],
    vault_dir: str,
) -> None:
    """Each recipe's outcome verbs surface in ``wiki outcomes`` post-init."""

    vault = tmp_path / vault_dir
    rc = main(["init", str(vault), "--no-git", "--recipe", recipe])
    assert rc == 0, f"`wiki init --recipe {recipe}` should succeed"

    # Discard init stdout/stderr before capturing outcomes output so the
    # per-recipe assertions below see only the table we asked for.
    capsys.readouterr()

    monkeypatch.chdir(vault)
    rc_outcomes = main(["outcomes"])
    captured = capsys.readouterr()
    assert rc_outcomes == 0

    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    surfaced_verbs = [ln.split()[0] for ln in lines]

    assert sorted(surfaced_verbs) == sorted(expected_verbs), (
        f"recipe={recipe}: expected outcome verbs {sorted(expected_verbs)}, "
        f"got {sorted(surfaced_verbs)}"
    )


def test_wiki_init_personal_recipe_shows_digest_in_outcomes_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Plan §PR-8 step 1 — the personal recipe surfaces ``digest``."""

    vault = tmp_path / "personal-vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "personal"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(vault)
    assert main(["outcomes"]) == 0
    captured = capsys.readouterr()
    # Each row starts with the verb; assert the digest row exists
    # AND maps to the correct (operation, skill) pair.
    digest_rows = [
        ln for ln in captured.out.splitlines() if ln.split() and ln.split()[0] == "digest"
    ]
    assert len(digest_rows) == 1, "`digest` row missing from `wiki outcomes`"
    columns = digest_rows[0].split()
    # Four columns: verb, source, operation, skill (Source column added
    # per ``docs/specs/primitive-sideload/spec.md`` §"Outputs ``wiki
    # outcomes`` provenance column"; always-present, ``bundled`` for
    # bundled operations).
    assert columns == ["digest", "bundled", "weekly-digest", "weekly-digest"]


def test_wiki_init_family_recipe_shows_plan_meals_and_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Plan §PR-8 step 2 — the family recipe surfaces both ``digest`` and ``plan-meals``."""

    vault = tmp_path / "family-vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "family"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(vault)
    assert main(["outcomes"]) == 0
    captured = capsys.readouterr()
    verbs_to_row = {ln.split()[0]: ln.split() for ln in captured.out.splitlines() if ln.split()}
    assert "digest" in verbs_to_row
    assert "plan-meals" in verbs_to_row
    assert verbs_to_row["digest"] == ["digest", "bundled", "weekly-digest", "weekly-digest"]
    assert verbs_to_row["plan-meals"] == [
        "plan-meals",
        "bundled",
        "meal-planning",
        "meal-planning",
    ]


def test_wiki_init_work_os_recipe_shows_refresh_stakeholders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Plan §PR-8 step 3 — the work-os recipe surfaces ``refresh-stakeholders``.

    Renamed for accuracy — the shipped ``recipes/work-os.yaml``
    installs neither ``weekly-digest`` nor ``meal-planning``; the
    spec was amended in this PR to match (see
    ``spec.md`` §"Three concrete worked examples").
    """

    vault = tmp_path / "work-os-vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "work-os"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(vault)
    assert main(["outcomes"]) == 0
    captured = capsys.readouterr()
    verbs_to_row = {ln.split()[0]: ln.split() for ln in captured.out.splitlines() if ln.split()}
    assert "refresh-stakeholders" in verbs_to_row
    assert verbs_to_row["refresh-stakeholders"] == [
        "refresh-stakeholders",
        "bundled",
        "stakeholder-map-refresh",
        "stakeholder-map-refresh",
    ]
