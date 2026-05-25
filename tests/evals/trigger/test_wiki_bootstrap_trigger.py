"""Trigger eval: onboarding phrases load ``wiki-bootstrap`` first.

Spec: ``docs/specs/wiki-bootstrap/spec.md``
Plan: ``docs/specs/wiki-bootstrap/plan.md`` § T6

Covers ACs 5, 6, 7 across 8 eval cases:

- ``test_trigger_phrase_loads_wiki_bootstrap`` — 5 trigger phrases by
  1 ``personal`` vault. Asserts ``wiki-bootstrap`` is the first
  SKILL Claude reads (AC 5).
- ``test_wizard_surfaces_recipe_appropriate_verbs`` — 1 prompt by 2
  recipes (`personal`, `work-os`). Asserts the set of verbs the
  transcript names equals the set ``wiki outcomes`` returns for
  that recipe (AC 6). Discriminating power lives on `work-os`
  (whose ``{refresh-stakeholders}`` set is unique); `family` is
  dropped at v1 because its verb set is identical to `personal`'s.
- ``test_post_bootstrap_short_circuits`` — 1 prompt against a
  vault that already has the marker. Asserts the SKILL loads but
  the response stays under the ≤ 6-non-blank-line short-circuit
  bound (AC 7).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llm_wiki_kit.recipes import installed_outcome_verbs
from tests import evalkit
from tests.evals.trigger._wiki_bootstrap_prompts import (
    BOOTSTRAP_RECIPE_PROMPTS,
    BOOTSTRAP_TRIGGER_PHRASES,
    BootstrapRecipePrompt,
    BootstrapTriggerPhrase,
)

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[3]

ALLOWED_NO_OP: list[str] = ["Read", "Glob"]
ALLOWED_FULL_FLOW: list[str] = [
    "Read",
    "Glob",
    "Bash(wiki outcomes)",
    "Bash(rm -f *)",
    "Write",
]


def _skip_guard() -> None:
    evalkit.skip_if_env_unset("ANTHROPIC_API_KEY")
    evalkit.skip_if_no_claude()


def _run_or_fail(
    prompt: str, vault: Path, allowed_tools: list[str], *, timeout_s: float = 180.0
) -> evalkit.ClaudeRunResult:
    result = evalkit.run_claude(
        prompt=prompt,
        vault=vault,
        allowed_tools=allowed_tools,
        timeout_s=timeout_s,
    )
    if result.timed_out:
        pytest.fail(f"claude timed out: {evalkit.redact(result.stderr[:400])}")
    if result.decode_failures:
        pytest.fail(
            f"transcript had {result.decode_failures} undecodable lines; "
            f"first-touch SKILL assertions cannot be trusted"
        )
    return result


@pytest.mark.parametrize(
    "case",
    BOOTSTRAP_TRIGGER_PHRASES,
    ids=[case.phrase.split(",", 1)[0] for case in BOOTSTRAP_TRIGGER_PHRASES],
)
def test_trigger_phrase_loads_wiki_bootstrap(
    case: BootstrapTriggerPhrase, personal_vault: Path
) -> None:
    """AC 5 — each canonical trigger phrase loads wiki-bootstrap first.

    "First" is measured against the first SKILL surface Claude
    touches — either a literal ``Read`` of ``skills/wiki-bootstrap/SKILL.md``
    or a ``Skill(skill="wiki-bootstrap")`` tool_use. Other SKILLs
    appearing later in the transcript are not a failure; another
    SKILL appearing *first* is.
    """

    _skip_guard()

    result = _run_or_fail(case.phrase, personal_vault, ALLOWED_NO_OP)

    first = evalkit.first_skill_touched(result)
    assert first is not None, (
        f"AC 5: no SKILL touched; stdout[:400]={evalkit.redact(result.stdout[:400])!r}"
    )
    assert first == "wiki-bootstrap", (
        f"AC 5: first SKILL touched was {first!r}, expected 'wiki-bootstrap'"
    )


@pytest.mark.parametrize(
    "case",
    BOOTSTRAP_RECIPE_PROMPTS,
    ids=[case.recipe for case in BOOTSTRAP_RECIPE_PROMPTS],
)
def test_wizard_surfaces_recipe_appropriate_verbs(
    case: BootstrapRecipePrompt, request: pytest.FixtureRequest
) -> None:
    """AC 6 — wizard names exactly the verbs ``wiki outcomes`` returns.

    Exact-equality assertion discriminates a wizard that hard-codes
    verbs from one that derives them from ``wiki outcomes``.
    """

    _skip_guard()

    vault: Path = request.getfixturevalue(case.fixture_name)
    expected_verbs = set(installed_outcome_verbs(vault, REPO_ROOT).keys())
    assert expected_verbs, (
        f"AC 6 precondition: `{case.recipe}` recipe ships no outcome verbs; "
        f"the eval has nothing to assert on"
    )

    result = _run_or_fail(case.prompt, vault, ALLOWED_FULL_FLOW)

    # Spec AC 6 reads "the set of verbs the transcript names equals" —
    # the verb walk-through and the closing recap appear in separate
    # assistant turns, so we aggregate every text block, not just
    # the terminal one.
    response_text = evalkit.all_assistant_text(result)
    verb_alternation = "|".join(re.escape(v) for v in expected_verbs)
    # Require backtick wrapping. The worked examples in the spec
    # (§"Three concrete worked examples") show the wizard rendering
    # each verb as ``- `verb` — gloss`` in the walk-through; pinning
    # the backticks discriminates "named the verb as a verb" from
    # "happened to mention the word in prose" (e.g. "you can `digest`
    # a meeting log" filler that would false-pass a bare-word match).
    verb_re = re.compile(rf"`(?P<verb>{verb_alternation})`")
    found = {match.group("verb") for match in verb_re.finditer(response_text)}
    assert found == expected_verbs, (
        f"AC 6: wizard's verb set differs from `wiki outcomes`. "
        f"Expected {expected_verbs!r}, surfaced {found!r}. "
        f"transcript[:400]={response_text[:400]!r}"
    )

    # Wizard reaching the marker write is implicit in the AC ("the
    # wizard walks the verb table" presupposes the full flow). Assert
    # it directly so a wizard that bails out mid-walkthrough surfaces
    # as a marker-missing failure rather than masquerading as a
    # verb-set mismatch.
    assert (vault / ".wiki.bootstrap").is_file(), (
        "AC 6: wizard did not reach the marker-write step; transcript may have truncated"
    )


def test_post_bootstrap_short_circuits(bootstrapped_personal_vault: Path) -> None:
    """AC 7 — re-trigger after marker: SKILL loads, response stays short."""

    _skip_guard()

    result = _run_or_fail(
        "I just made a new vault, help me get started.",
        bootstrapped_personal_vault,
        ALLOWED_NO_OP,
    )

    # Spec AC 7 reads "transcript whose first SKILL load is
    # `wiki-bootstrap`" — preserve the first-touch order check, but
    # accept both surfaces (Skill tool_use *or* Read of the SKILL.md).
    # ``ordered_skill_reads`` alone would false-fail when Claude
    # auto-discovered the SKILL via the Skill tool.
    first = evalkit.first_skill_touched(result)
    assert first == "wiki-bootstrap", (
        f"AC 7: first SKILL touched on re-trigger was {first!r}, expected 'wiki-bootstrap'"
    )

    # Pin the SKILL's "zero tool calls beyond Read on the marker"
    # contract directly — a wizard that lazily re-walks the journal
    # or re-fetches the verb table on the re-run path still loads
    # the SKILL first and may produce a short response, so the
    # negative evidence is what catches that regression class.
    tool_calls = evalkit.ordered_tool_calls(result)
    for tu in tool_calls:
        if tu.name == "Bash":
            command = tu.input.get("command", "")
            assert "wiki outcomes" not in command, (
                f"AC 7: wizard called `wiki outcomes` on the re-run path: {command!r}"
            )
        if tu.name == "Read":
            file_path = tu.input.get("file_path", "")
            assert "journal.jsonl" not in file_path, (
                f"AC 7: wizard re-Read the journal on the re-run path: {file_path!r}"
            )

    response_lines = evalkit.count_non_blank_lines(evalkit.final_assistant_text(result))
    assert response_lines <= 6, (
        f"AC 7: post-bootstrap re-run should short-circuit (≤ 6 non-blank lines); "
        f"got {response_lines} lines"
    )
