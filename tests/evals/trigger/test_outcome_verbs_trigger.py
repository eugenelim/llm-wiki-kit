"""Trigger eval: outcome-shaped NL prompts load the matching operation SKILL.

Spec: ``docs/specs/outcome-named-entry-points/spec.md`` §Acceptance
criterion "Eval trigger" pins the canonical prompts. Plan: PR-9 §1.

Parametrized over the three shipped outcome verbs. Each case drives
Claude Code via subprocess against a per-verb fixture vault built by
``tests/evals/conftest.py`` and asserts the matching operation SKILL
gets loaded. The prompts deliberately do NOT name the SKILL or the
``wiki run`` command — naming the path would reduce the eval to
"does Claude follow direct instructions", a tautology against the
spec's discovery-by-description contract.

Unlike ``test_wiki_conflict_trigger.py`` / ``test_wiki_research_trigger.py``,
this eval does NOT pin "first SKILL read" ordering. Outcome-verb
vaults ship peer SKILLs by construction (every ``wiki add
content-type:<x>`` installs an ``ingest-<x>`` SKILL alongside the
operation SKILL — pinned by
``tests/integration/test_eval_fixtures.py``), and the spec criterion
is "the matching SKILL loads" — not "no other SKILL is read first."
A future amendment can tighten if a regression motivates it.

The parametrize table lives in
:mod:`tests.evals.trigger._outcome_verb_prompts` so the fast-lane
meta-check (``tests/unit/test_eval_fixture_completeness.py``) can
import it without dragging the eval harness (``tests.evalkit``) and
``yaml`` into the unit-lane collection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import evalkit
from tests.evals.trigger._outcome_verb_prompts import (
    OUTCOME_VERB_PROMPTS,
    OutcomeVerbPrompt,
)

pytestmark = pytest.mark.eval


@pytest.mark.parametrize(
    "case",
    OUTCOME_VERB_PROMPTS,
    ids=[case.verb for case in OUTCOME_VERB_PROMPTS],
)
def test_outcome_verb_prompt_loads_matching_skill(
    case: OutcomeVerbPrompt,
    request: pytest.FixtureRequest,
) -> None:
    # Two-layer guard. The module-level ``pytestmark = pytest.mark.eval``
    # already deselects this test in the default lane (CI runs
    # ``pytest -m 'not slow and not eval'``); the explicit skip
    # calls below cover the eval workflow when credentials or the
    # ``claude`` binary aren't on the box. Either layer alone leaves
    # a hole — keep both.
    evalkit.skip_if_env_unset("ANTHROPIC_API_KEY")
    evalkit.skip_if_no_claude()

    vault: Path = request.getfixturevalue(case.fixture_name)

    # The prompt is the spec's canonical phrasing (Acceptance
    # criterion "Eval trigger") — it names neither the SKILL nor
    # ``wiki run``. The eval verifies the discovery path the spec
    # advertises in Outputs §3 (the SKILL description fragment).
    result = evalkit.run_claude(
        prompt=case.prompt,
        vault=vault,
        allowed_tools=["Read", "Glob"],
        timeout_s=180.0,
    )
    if result.timed_out:
        pytest.fail(f"claude timed out: {evalkit.redact(result.stderr[:400])}")
    if result.decode_failures:
        pytest.fail(
            f"transcript had {result.decode_failures} undecodable lines; "
            f"SKILL-loaded assertion is not trustworthy"
        )

    # Spec criterion: "the matching SKILL loads." Peer ingest SKILLs
    # are not wrong answers — they belong to the content-type the
    # ``wiki add`` chain installed transitively. So we assert set
    # membership (matching SKILL touched at some point) rather than
    # first-touch ordering.
    #
    # ``assert_skill_loaded`` matches by the on-disk directory name
    # — which is what ``OutcomeVerbPrompt.skill_dir_name`` carries.
    # A future SKILL.md whose frontmatter ``name:`` diverges from
    # its directory is a harness-level concern, not a per-test one.
    evalkit.assert_skill_loaded(result, case.skill_dir_name)
