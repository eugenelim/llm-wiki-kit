"""End-to-end integration tests for the Task-15 ``personal`` recipe.

Task 15 (RFC-0001) expanded ``recipes/personal.yaml`` past the
core-only shape into a deliberate composition of Task 11, Task 13, and
Task 14 primitives plus the new ``identity`` ontology. The recipe is
*composition* — these tests pin the closure shape and the one piece of
new behaviour (interpolation of the seeded ``identity.md``) so a future
"add medical to personal" or "drop trips from personal" change has to
update the closure expectation and the comment block in lockstep.

Like the Task-13 and Task-14 suites, this runs against the real shipped
catalog via ``cli._kit_paths()`` rather than fixtures-on-disk — the
recipe-as-shipped is the contract.
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki_kit.cli import main
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import PrimitiveInstallEvent, VaultInitEvent

RECIPE = "personal"

# Full transitive closure of the personal recipe's ``primitives:`` list.
# ``core`` is always installed; ``food`` and ``trips`` are pulled in via
# ``recipe`` / ``trip-doc`` respectively (the recipe also lists them
# directly for readability). Nothing in this set is work-OS or
# household shaped — see the comment block in ``recipes/personal.yaml``
# for why.
EXPECTED_PRIMITIVES = {
    "action-item",
    # RFC-0008 workspace lenses (personal-recipe-workspaces follow-on).
    # ``content-studio`` is a membership lens; ``planning`` is a
    # cross-cutting (empty-scope) lens. Both reference the existing
    # ``personal-coordinator`` agent and surface operations the closure
    # already installs — no new content-type/operation enters here.
    "content-studio",
    "core",
    "decision",
    # PR-7 / RFC-0004 — installed-but-unbound; reserved for a future
    # ``decision-review`` operation. ``personal.yaml``'s ``primitives:``
    # lists it directly, so the install closure picks it up.
    "decision-companion",
    "follow-up-tracker",
    # RFC-0009 role folders: atlas/library/efforts listed explicitly; the
    # food ontology is gone (a recipe is a genre:reference capture in
    # library/).
    "atlas",
    "library",
    "efforts",
    "identity",
    "meal-planning",
    "meeting",
    "people",
    # PR-7 / RFC-0004 — bound to ``weekly-digest``,
    # ``follow-up-tracker``, ``meal-planning`` in ``personal.yaml``'s
    # ``agents:`` block.
    "personal-coordinator",
    "planning",
    "recipe",
    "trip-doc",
    "trip-prep",
    "trips",
    "weekly-digest",
}


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def test_personal_init_installs_expected_closure(tmp_path: Path) -> None:
    """``wiki init --recipe personal`` resolves the recipe's full closure."""

    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    events = read_events(_journal_path(vault))

    assert isinstance(events[0], VaultInitEvent)
    assert events[0].recipe == RECIPE

    install_events = [e for e in events if isinstance(e, PrimitiveInstallEvent)]
    installed = {e.primitive for e in install_events}
    assert installed == EXPECTED_PRIMITIVES

    state = replay_state(events)
    assert state.recipe == RECIPE
    assert set(state.installed_primitives) == EXPECTED_PRIMITIVES
    assert state.installed_primitives["core"] == "0.1.0"
    assert state.installed_primitives["identity"] == "0.1.0"


def test_personal_init_excludes_household_and_work_os_primitives(tmp_path: Path) -> None:
    """The recipe deliberately omits medical / vendors / work-OS primitives.

    The comment block in ``recipes/personal.yaml`` is the contract for
    these omissions; this test pins it so a future "let's add medical to
    personal" change has to update the comment block too.
    """

    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    state = replay_state(read_events(_journal_path(vault)))
    installed = set(state.installed_primitives)

    forbidden = {
        # Household-shape content-types/operations + the `cases` registry
        # they pull (the medical/vendors entity-kind ontologies no longer
        # exist post RFC-0009).
        "medical-record",
        "medical-summary",
        "cases",
        "receipt",
        "tax-document",
        # Work-OS shape (Task 14). ``projects`` is now a container registry,
        # still excluded from the personal closure.
        "customer-feedback",
        "interview",
        "onboarding-pack",
        "projects",
        "renewal-reminders",
        "stakeholder-map-refresh",
        "stakeholder-update",
        "status-synthesis",
        "action-item-rollup",
        "vendor-contract",
    }
    leaked = forbidden & installed
    assert not leaked, f"personal closure should not include: {sorted(leaked)}"


def test_personal_init_seeds_identity_page(tmp_path: Path) -> None:
    """The new ``identity`` ontology seeds ``identity.md`` at the vault root.

    The page is on the ``INTERPOLATED_FILES`` allowlist, so the four
    ``{owner_*}`` tokens get substituted from the recipe's
    ``variables:`` defaults. With the recipe shipping empty-string
    defaults, the tokens render as visibly empty rather than as raw
    ``{owner_name}`` placeholders.
    """

    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    identity = vault / "identity.md"
    assert identity.is_file()

    body = identity.read_text(encoding="utf-8")

    # The tokens themselves must not survive (otherwise interpolation broke).
    for token in ("{owner_name}", "{owner_pronouns}", "{owner_role}", "{owner_timezone}"):
        assert token not in body, f"identity.md still contains raw token {token!r}"

    # The empty-string defaults render as `Field: ` lines.
    assert "- **Name:** \n" in body
    assert "- **Pronouns:** \n" in body
    assert "- **Role:** \n" in body
    assert "- **Timezone:** \n" in body

    # Companion README explains the page's purpose.
    assert (vault / "wiki" / "identity" / "README.md").is_file()


def test_personal_init_seeds_the_role_folders(tmp_path: Path) -> None:
    """The personal vault renders the four role folders + its trips registry.

    RFC-0009 §C/§D: the folder set is `people/`, `efforts/`, `library/`,
    `atlas/`, with the `trips` container registry under `efforts/`. The
    `identity` ontology still seeds its own `wiki/identity/` companion folder.
    """

    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    for role in ("people", "efforts", "library", "atlas", "identity"):
        readme = vault / "wiki" / role / "README.md"
        assert readme.is_file(), f"missing wiki/{role}/README.md"
    assert (vault / "wiki" / "efforts" / "trips" / "README.md").is_file()


def test_personal_init_installs_operation_skills(tmp_path: Path) -> None:
    """The three personal operations each ship a SKILL.md under ``skills/``."""

    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    for operation in ("meal-planning", "trip-prep", "follow-up-tracker", "weekly-digest"):
        assert (vault / "skills" / operation / "SKILL.md").is_file()
