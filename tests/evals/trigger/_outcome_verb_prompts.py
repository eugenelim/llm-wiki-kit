"""Canonical outcome-verb prompt table — leaf module, no heavy imports.

Imported by both ``test_outcome_verbs_trigger.py`` (the eval suite,
which adds ``tests.evalkit`` + ``yaml``) and
``tests/unit/test_eval_fixture_completeness.py`` (the fast-lane
meta-check, which must collect without dragging the eval harness in).
Splitting the constant into its own leaf keeps the unit lane's
collection cost bounded.

Each entry pins the canonical natural-language prompt from
``docs/specs/outcome-named-entry-points/spec.md`` §Acceptance
criterion "Eval trigger". The fixture-name field names the
``tests/evals/conftest.py`` fixture that yields the seeded vault;
the skill-dir-name field names the on-disk directory under
``<vault>/skills/`` whose ``SKILL.md`` the eval expects Claude to
read.
"""

from __future__ import annotations

from typing import NamedTuple


class OutcomeVerbPrompt(NamedTuple):
    """One parametrize row for the outcome-verb trigger eval."""

    verb: str
    prompt: str
    fixture_name: str
    skill_dir_name: str


OUTCOME_VERB_PROMPTS: tuple[OutcomeVerbPrompt, ...] = (
    OutcomeVerbPrompt(
        verb="digest",
        prompt="Give me last week's digest.",
        fixture_name="weekly_digest_vault",
        skill_dir_name="weekly-digest",
    ),
    OutcomeVerbPrompt(
        verb="plan-meals",
        prompt="Help me plan our meals for next week.",
        fixture_name="meal_planning_vault",
        skill_dir_name="meal-planning",
    ),
    OutcomeVerbPrompt(
        verb="refresh-stakeholders",
        prompt="Refresh the stakeholder map for the pluto project.",
        fixture_name="stakeholder_map_refresh_vault",
        skill_dir_name="stakeholder-map-refresh",
    ),
)
