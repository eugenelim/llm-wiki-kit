"""End-to-end ``wiki init`` test for the Task-14 ``work-os`` recipe.

Task 14 (RFC-0001) expanded ``recipes/work-os.yaml`` past the
core-only shape: three ontologies (``projects``, ``domains``,
``customers``), five content-types (``stakeholder-update``,
``vendor-contract``, ``customer-feedback``, ``interview``,
``decision``), and five operations (``stakeholder-map-refresh``,
``action-item-rollup``, ``renewal-reminders``, ``onboarding-pack``,
``status-synthesis``), plus ``people`` and ``meeting`` pulled in
transitively via ``requires:``.

These tests run against the *real* shipped catalog (the kit's
``recipes/``, ``core/``, ``templates/`` siblings of the editable
install), the same on-disk assets an end user would render at install
time. The Task-11 suite's monkeypatched custom-recipe pattern is the
right tool for testing primitive shape in isolation; here we test that
the recipe as shipped composes correctly.
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

RECIPE = "work-os"

# Full transitive closure of the work-os recipe's ``primitives:`` list.
# ``people`` is pulled in by stakeholder-update / customer-feedback /
# interview; ``meeting`` by action-item-rollup. Every other primitive
# is either named directly in the recipe or has no further requires.
EXPECTED_PRIMITIVES = {
    "action-item-rollup",
    "core",
    # PR-7 / RFC-0004 — default agent bindings per spec §Default
    # agent catalog; the three names land via ``work-os.yaml``'s
    # ``primitives:`` listing.
    "customer-listener",
    "renewals-watch",
    "stakeholder-steward",
    "customer-feedback",
    "customers",
    "decision",
    "domains",
    "interview",
    "meeting",
    "onboarding-pack",
    "people",
    "projects",
    "renewal-reminders",
    "stakeholder-map-refresh",
    "stakeholder-update",
    "status-synthesis",
    "vendor-contract",
}

# The crosswalk ``subtype`` value each installed content-type contributes to
# the managed ``subtype`` region (genre is a fixed baseline enum, not
# contributed). decision -> decision-record, stakeholder-update -> stakeholder,
# vendor-contract -> vendor; the rest map name-for-name.
EXPECTED_SUBTYPES_IN_SCHEMA = {
    "customer-feedback",
    "decision-record",
    "interview",
    "meeting",
    "stakeholder",
    "vendor",
}


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def test_work_os_init_renders_ontology_folders(tmp_path: Path) -> None:
    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    # The three new ontology folders each ship a README.
    for ontology in ("projects", "domains", "customers"):
        readme = vault / "wiki" / ontology / "README.md"
        assert readme.is_file(), f"expected wiki/{ontology}/README.md"

    # ``people`` and ``meetings`` are pulled in transitively and seed
    # their own folders too.
    assert (vault / "wiki" / "people" / "README.md").is_file()
    assert (vault / "wiki" / "meetings" / "README.md").is_file()


def test_work_os_init_renders_content_type_assets(tmp_path: Path) -> None:
    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    content_types = (
        "stakeholder-update",
        "vendor-contract",
        "customer-feedback",
        "interview",
        "decision",
    )
    # Each content-type ships a wiki directory README, a page template,
    # and an ingester skill.
    wiki_dir_for = {
        "stakeholder-update": "stakeholder-updates",
        "vendor-contract": "vendor-contracts",
        "customer-feedback": "customer-feedback",
        "interview": "interviews",
        "decision": "decisions",
    }
    for content_type in content_types:
        assert (vault / "wiki" / wiki_dir_for[content_type] / "README.md").is_file()
        assert (vault / "_templates" / f"{content_type}.md").is_file()
        assert (vault / "skills" / f"ingest-{content_type}" / "SKILL.md").is_file()


def test_work_os_init_renders_operation_skills(tmp_path: Path) -> None:
    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    for operation in (
        "stakeholder-map-refresh",
        "action-item-rollup",
        "renewal-reminders",
        "onboarding-pack",
        "status-synthesis",
    ):
        assert (vault / "skills" / operation / "SKILL.md").is_file()


def test_work_os_init_schema_regions_include_every_content_type(tmp_path: Path) -> None:
    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    schema = (vault / "frontmatter.schema.yaml").read_text(encoding="utf-8")

    subtype_block = schema.split("# BEGIN MANAGED: subtype\n", 1)[1].split(
        "  # END MANAGED: subtype", 1
    )[0]
    for subtype_name in EXPECTED_SUBTYPES_IN_SCHEMA:
        assert f"- {subtype_name}\n" in subtype_block, (
            f"subtype '{subtype_name}' missing from managed subtype region"
        )
    # The seed body is fully replaced by the composed contributions.
    assert "Populated by content-type primitives" not in subtype_block

    fields_block = schema.split("# BEGIN MANAGED: fields\n", 1)[1].split(
        "  # END MANAGED: fields", 1
    )[0]
    # Representative scoped fields from each content-type land in the
    # composed body. One field per type is enough; full-shape checks
    # belong with the per-primitive unit tests.
    for sentinel in (
        "meeting_date:",
        "update_date:",
        "contract_vendor:",
        "feedback_date:",
        "interview_date:",
        "decision_date:",
    ):
        assert sentinel in fields_block, f"sentinel '{sentinel}' missing from fields region"


def test_work_os_init_journal_state_matches_closure(tmp_path: Path) -> None:
    vault = tmp_path / "v"

    assert main(["init", str(vault), "--recipe", RECIPE]) == 0

    events = read_events(_journal_path(vault))

    assert isinstance(events[0], VaultInitEvent)
    assert events[0].recipe == RECIPE

    install_events = [e for e in events if isinstance(e, PrimitiveInstallEvent)]
    installed = {e.primitive for e in install_events}
    assert installed == EXPECTED_PRIMITIVES

    # Two region writes per ADR-0006 bucket order (alphabetical by
    # ``(file, region)``): ``fields`` then ``subtype`` on
    # ``frontmatter.schema.yaml``.
    region_events = [e for e in events if isinstance(e, ManagedRegionWriteEvent)]
    assert [(e.file, e.region) for e in region_events] == [
        ("frontmatter.schema.yaml", "fields"),
        ("frontmatter.schema.yaml", "subtype"),
    ]

    state = replay_state(events)
    assert state.recipe == RECIPE
    assert set(state.installed_primitives) == EXPECTED_PRIMITIVES
