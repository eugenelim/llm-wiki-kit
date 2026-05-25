"""Canonical wiki-bootstrap prompt tables — leaf module, no heavy imports.

Imported by ``test_wiki_bootstrap_trigger.py`` (the eval) and by
``tests/unit/test_wiki_bootstrap_artifacts.py``'s
``test_trigger_phrases_unique_across_existing_skills`` meta-check
(via the spec-pinned list, not this module, since the unit test
hard-codes the same set as a safety duplicate — duplication is
deliberate so the unit lane doesn't depend on the eval lane's
prompt module). Splitting the table into its own leaf keeps the
unit lane's collection cost bounded.

Each entry pins a canonical natural-language prompt from
``docs/specs/wiki-bootstrap/spec.md`` §Inputs §2 (canonical trigger
phrases) and AC 5 (trigger eval) / AC 6 (flow eval).
"""

from __future__ import annotations

from typing import NamedTuple


class BootstrapTriggerPhrase(NamedTuple):
    """One parametrize row for the trigger-loads-skill eval (AC 5)."""

    phrase: str


class BootstrapRecipePrompt(NamedTuple):
    """One parametrize row for the recipe-appropriate-verbs eval (AC 6)."""

    recipe: str
    fixture_name: str
    prompt: str


# Five canonical trigger phrases — wording pinned by spec AC 5.
BOOTSTRAP_TRIGGER_PHRASES: tuple[BootstrapTriggerPhrase, ...] = (
    BootstrapTriggerPhrase("I just made a new vault, help me get started."),
    BootstrapTriggerPhrase("This is my first time using this vault — what should I do?"),
    BootstrapTriggerPhrase("Walk me through this vault."),
    BootstrapTriggerPhrase("What should I do first in this vault?"),
    BootstrapTriggerPhrase("Help me get started with this wiki."),
)


# Flow-eval recipes. `family` is dropped at v1 because it ships the
# same verb set as `personal` (``{digest, plan-meals}``); the
# exact-equality assertion is identical between them. Discriminating
# power lives on `work-os` (whose ``{refresh-stakeholders}`` set is
# unique). Re-add `family` when it ships a unique verb.
BOOTSTRAP_RECIPE_PROMPTS: tuple[BootstrapRecipePrompt, ...] = (
    BootstrapRecipePrompt(
        recipe="personal",
        fixture_name="personal_vault",
        prompt="I just made a new vault, help me get started.",
    ),
    BootstrapRecipePrompt(
        recipe="work-os",
        fixture_name="work_os_vault",
        prompt="I just made a new vault, help me get started.",
    ),
)
