"""Meta-check: every shipped outcome verb has an eval prompt fixture.

Spec: ``docs/specs/outcome-named-entry-points/spec.md`` §Acceptance
criterion "Eval trigger" — "New verbs added to the catalog must add a
matching prompt fixture in the same PR." Plan: PR-9 §1.

Walks every ``templates/operations/*/contract.yaml``; for each
contract that declares one or more ``outcomes:``, asserts the
corresponding entry exists in
:data:`tests.evals.trigger._outcome_verb_prompts.OUTCOME_VERB_PROMPTS`.

Lives in ``tests/unit/`` (not ``tests/evals/``) so a missing fixture
trips the default ``pytest -m 'not slow and not eval'`` lane in CI —
the eval suite runs on a separate workflow that may not gate merges.
This is the mechanical safety-net the spec contracts for ratcheting
the catalog forward.

Imports from the leaf module
``tests.evals.trigger._outcome_verb_prompts`` rather than the eval
test file itself so the unit lane's collection cost doesn't pull in
``tests.evalkit`` and ``yaml`` (the eval harness side).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llm_wiki_kit.primitives import load_operation_contract
from tests.evals.trigger._outcome_verb_prompts import (
    OUTCOME_VERB_PROMPTS,
    OutcomeVerbPrompt,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS_DIR = REPO_ROOT / "templates" / "operations"


def _declared_outcome_verbs() -> dict[str, str]:
    """Return ``{verb: operation_name}`` from every shipped contract."""

    verbs: dict[str, str] = {}
    for op_dir in sorted(OPERATIONS_DIR.iterdir()):
        if not op_dir.is_dir():
            continue
        contract = load_operation_contract(op_dir)
        if contract is None:
            continue
        for verb in contract.outcomes:
            verbs[verb] = contract.name
    return verbs


def test_every_shipped_outcome_verb_has_eval_prompt() -> None:
    declared = _declared_outcome_verbs()
    covered = {case.verb for case in OUTCOME_VERB_PROMPTS}

    missing = sorted(set(declared) - covered)
    assert not missing, (
        f"shipped outcome verbs lack an eval prompt fixture: "
        f"{[(v, declared[v]) for v in missing]}. Add an entry to "
        f"OUTCOME_VERB_PROMPTS in "
        f"tests/evals/trigger/_outcome_verb_prompts.py with the "
        f"canonical natural-language prompt the spec's Acceptance "
        f"criterion 'Eval trigger' requires."
    )


def test_eval_prompt_table_has_no_stale_verbs() -> None:
    """Reject prompt entries for verbs no operation declares.

    Catches the symmetric drift: a verb removed from a contract whose
    eval prompt was left behind. Without this, a stale prompt could
    paper over a regression that broke the verb's actual surface.
    """

    declared = set(_declared_outcome_verbs())
    covered = {case.verb for case in OUTCOME_VERB_PROMPTS}

    stale = sorted(covered - declared)
    assert not stale, (
        f"OUTCOME_VERB_PROMPTS references verbs that no shipped "
        f"contract declares: {stale}. Remove the entry or restore "
        f"the missing `outcomes:` declaration in the matching "
        f"templates/operations/<op>/contract.yaml."
    )


@pytest.mark.parametrize(
    "case",
    OUTCOME_VERB_PROMPTS,
    ids=[case.verb for case in OUTCOME_VERB_PROMPTS],
)
def test_outcome_verb_prompt_entry_is_well_shaped(case: OutcomeVerbPrompt) -> None:
    """Each entry's fields are non-empty and obey the discovery-by-description contract.

    Cheap structural pin so a typo (empty string, swapped fields)
    surfaces in the fast lane rather than in the slow eval workflow.
    """

    assert case.verb, "verb must be non-empty"
    assert case.prompt, f"prompt for {case.verb!r} must be non-empty"
    # Spec §Acceptance "Eval trigger": prompt MUST NOT name the
    # SKILL path or the `wiki run` command. Pin both literal
    # references — the verb word itself is allowed (canonical
    # English; the eval tests discovery by description, not by
    # token-suppression).
    lowered = case.prompt.lower()
    assert "wiki run" not in lowered, (
        f"prompt for {case.verb!r} mentions `wiki run`; the eval must "
        f"test discovery by description (spec §Acceptance 'Eval "
        f"trigger'). Got: {case.prompt!r}"
    )
    # Whole-word check, not substring: a future verb whose
    # skill dir happens to share a common English root with the
    # prompt (e.g. ``skill_dir_name="meal"``) shouldn't trip this
    # rule. The contract is "do not literally name the SKILL dir,"
    # not "do not share any character sequence with it."
    #
    # Loose-boundary caveat (mirrors the wheel-acceptance test's
    # comment): Python's ``\b`` fires at hyphen-to-letter
    # transitions, so a substring like ``pre-meal-planning`` would
    # match ``\bmeal-planning\b``. In this meta-check that's
    # conservative — over-flag is fine, under-flag is what we
    # care about. A future spec amendment can tighten to
    # ``(?<![\w-])`` / ``(?![\w-])`` in both places if needed.
    # whole-word, not substring — see docstring caveat above.
    assert re.search(rf"\b{re.escape(case.skill_dir_name)}\b", case.prompt) is None, (
        f"prompt for {case.verb!r} names the SKILL dir "
        f"{case.skill_dir_name!r} as a whole word; the eval must "
        f"test discovery by description, not by direct instruction. "
        f"Got: {case.prompt!r}"
    )
    assert case.fixture_name, f"fixture_name for {case.verb!r} must be non-empty"
    assert case.skill_dir_name, f"skill_dir_name for {case.verb!r} must be non-empty"
