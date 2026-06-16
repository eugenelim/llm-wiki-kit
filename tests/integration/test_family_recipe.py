"""End-to-end integration tests for the expanded ``family`` recipe.

Task 13 grew the family recipe from a core-only listing into the full
ontology / content-type / operation closure for the household audience.
The Task-10 integration suite (`test_wiki_init.py`) keeps the core-only
parameterized assertions running against `work-os` and `personal`; the
family-specific assertions live here so they stay readable as the
recipe evolves.

These tests run against the bundled kit assets via ``cli._kit_paths()``
just like the Task-10 suite does — no fixtures-on-disk, no
monkeypatching. The family recipe is the source of truth for the
expected primitive set, so the assertions compute the closure from the
on-disk recipe rather than hard-coding a list. That keeps a future
addition to ``recipes/family.yaml`` from breaking this test without
also breaking what it asserts.
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki_kit.cli import main
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import (
    ManagedRegionWriteEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
)
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import load_recipe, resolve_recipe_primitives

REPO_ROOT = Path(__file__).resolve().parents[2]


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _expected_family_closure() -> list[str]:
    """Return the install-ordered names of every primitive the family recipe pulls in."""

    recipe = load_recipe(REPO_ROOT / "recipes" / "family.yaml")
    catalog = [load_primitive(REPO_ROOT / "core")]
    catalog.extend(discover_primitives(REPO_ROOT / "templates"))
    return [primitive.name for primitive in resolve_recipe_primitives(recipe, catalog)]


def test_family_recipe_lists_every_household_primitive() -> None:
    """Sanity-check: the recipe file references the household primitive set.

    Post RFC-0009 the household pages live over the four role folders: the
    entity-kind ontologies (`food`/`medical`/`vendors`) are gone and their
    pages are `subtype`s in `library/`/`people/`; `atlas`/`library`/`efforts`
    are listed explicitly so the four-role floor holds. The recipe loader
    resolves `requires:` transitively, so listing each leaf is enough.
    """

    recipe = load_recipe(REPO_ROOT / "recipes" / "family.yaml")
    listed = set(recipe.primitives)

    expected_minimum = {
        # Role folders + container registry (RFC-0009 §C/§D).
        "people",
        "library",
        "atlas",
        "efforts",
        "trips",
        # Content-types.
        "recipe",
        "medical-record",
        "trip-doc",
        "receipt",
        "tax-document",
        "action-item",
        "meeting",
        # Operations.
        "meal-planning",
        "trip-prep",
        "follow-up-tracker",
        "medical-summary",
    }
    missing = expected_minimum - listed
    assert not missing, f"family recipe is missing household primitives: {sorted(missing)}"


def test_family_init_installs_full_closure(tmp_path: Path) -> None:
    """``wiki init --recipe family`` installs the recipe's full closure."""

    vault = tmp_path / "household"

    assert main(["init", str(vault), "--recipe", "family"]) == 0

    state = replay_state(read_events(_journal_path(vault)))
    expected = set(_expected_family_closure())
    assert set(state.installed_primitives) == expected
    assert state.installed_primitives["core"] == "0.1.0"


def test_family_init_creates_the_four_role_folders(tmp_path: Path) -> None:
    """The family vault renders the four role folders + its container registries.

    RFC-0009 §C/§D: a household locates pages by role, not by kind. The
    folder set is exactly `people/`, `efforts/`, `library/`, `atlas/`, with
    `trips`/`cases` container registries nested under `efforts/`.
    """

    vault = tmp_path / "household"
    assert main(["init", str(vault), "--recipe", "family"]) == 0

    for role in ("people", "efforts", "library", "atlas"):
        readme = vault / "wiki" / role / "README.md"
        assert readme.is_file(), f"missing wiki/{role}/README.md"
    for reg in ("trips", "cases"):
        readme = vault / "wiki" / "efforts" / reg / "README.md"
        assert readme.is_file(), f"missing wiki/efforts/{reg}/README.md"


def test_family_init_aggregates_every_content_type_into_schema(tmp_path: Path) -> None:
    """Every Task-13 content-type contributes to the schema's regions."""

    vault = tmp_path / "household"
    assert main(["init", str(vault), "--recipe", "family"]) == 0

    schema = (vault / "frontmatter.schema.yaml").read_text(encoding="utf-8")

    # The ``subtype`` region holds every content-type's crosswalk subtype in
    # install order. ``install_order`` for content-types under the family
    # recipe is alphabetical among independent peers and topological for the
    # ones that ``require:`` each other; we assert membership rather than
    # ordering here so the test stays robust to ``requires:`` rewrites.
    # (``medical-record`` -> ``medical``, ``trip-doc`` -> ``trip``; the rest
    # map name-for-name per the crosswalk.)
    subtype_block = schema.split("# BEGIN MANAGED: subtype\n", 1)[1].split(
        "  # END MANAGED: subtype", 1
    )[0]
    for subtype in (
        "action-item",
        "medical",
        "meeting",
        "receipt",
        "recipe",
        "tax",
        "trip",
    ):
        assert f"- {subtype}\n" in subtype_block, (
            f"subtype region missing `- {subtype}`; got: {subtype_block!r}"
        )

    # The ``fields`` region holds the type-scoped field declarations
    # from each content-type's snippet.
    fields_block = schema.split("# BEGIN MANAGED: fields\n", 1)[1].split(
        "  # END MANAGED: fields", 1
    )[0]
    for field_marker in (
        "recipe_servings:",
        "medical_record_person:",
        "trip_destination:",
        "receipt_vendor:",
        "tax_document_year:",
        "action_item_owner:",
        "meeting_date:",
    ):
        assert field_marker in fields_block, (
            f"fields region missing {field_marker}; got: {fields_block!r}"
        )


def test_family_init_installs_every_operation_skill(tmp_path: Path) -> None:
    """Each Task-13 operation ships a SKILL.md that lands under `skills/`."""

    vault = tmp_path / "household"
    assert main(["init", str(vault), "--recipe", "family"]) == 0

    for operation in (
        "meal-planning",
        "trip-prep",
        "follow-up-tracker",
        "medical-summary",
        # Task 11's operation ships through the family closure too.
        "weekly-digest",
    ):
        skill = vault / "skills" / operation / "SKILL.md"
        assert skill.is_file(), f"missing skills/{operation}/SKILL.md"


def test_family_init_journal_shape(tmp_path: Path) -> None:
    """The journal opens with VaultInit + PrimitiveInstall(core); region writes come last."""

    vault = tmp_path / "household"
    assert main(["init", str(vault), "--recipe", "family"]) == 0

    events = read_events(_journal_path(vault))

    assert isinstance(events[0], VaultInitEvent)
    assert events[0].recipe == "family"

    install_events = [e for e in events if isinstance(e, PrimitiveInstallEvent)]
    assert [e.primitive for e in install_events] == _expected_family_closure()
    # Topological sort with alphabetical tiebreaker places ``core`` after
    # primitives that come alphabetically before it (e.g. ``action-item``);
    # we only assert that it's present in the install order — its exact
    # position is whatever ``resolve_dependencies`` produces.
    assert "core" in {e.primitive for e in install_events}

    # Region writes happen after every primitive's files/ tree is on
    # disk (ADR-0006 §Mechanics step 5). The two managed regions in the
    # schema — `fields` and `subtype` — are written in alphabetical
    # bucket order.
    region_events = [e for e in events if isinstance(e, ManagedRegionWriteEvent)]
    assert [(e.file, e.region) for e in region_events] == [
        ("frontmatter.schema.yaml", "fields"),
        ("frontmatter.schema.yaml", "subtype"),
    ]
