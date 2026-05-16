"""Unit tests for the pure checks behind ``wiki doctor``.

Each test pins one issue-kind contract from the Task-12 spec:

* ``page-drift`` — on-disk hash diverges, no pending proposal.
* ``managed-region-drift`` — region body diverges from the latest event.
* ``pending-proposal`` — the proposed sidecar surfaces by its path.
* ``orphan`` — kit-owned paths with no journal event are flagged;
  user-owned territory is invisible.
* ``missing`` — a journaled write whose file is gone.
* ``primitive-missing`` — a recorded install the catalog no longer has.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit.doctor import (
    Issue,
    check_managed_region_drift,
    check_missing,
    check_orphans,
    check_page_drift,
    check_pending_proposals,
    check_primitive_missing,
    format_issue,
    run_doctor,
)
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    ManagedRegionWriteEvent,
    PageProposalEvent,
    PageWriteEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
    VaultState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


NOW = datetime(2026, 5, 16, tzinfo=UTC)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _state_with_page(path: str, content: str) -> VaultState:
    event = PageWriteEvent(timestamp=NOW, by="core", path=path, hash=_hash(content))
    return VaultState(page_writes={path: event})


def _vault(tmp_path: Path) -> Path:
    (tmp_path / ".wiki.journal").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# format_issue
# ---------------------------------------------------------------------------


def test_format_issue_without_detail_omits_parentheses() -> None:
    assert format_issue(Issue("page-drift", "AGENTS.md")) == "page-drift: AGENTS.md"


def test_format_issue_with_detail_renders_parens() -> None:
    issue = Issue("managed-region-drift", "x.yaml:fields", "region missing")
    assert format_issue(issue) == "managed-region-drift: x.yaml:fields (region missing)"


# ---------------------------------------------------------------------------
# check_page_drift
# ---------------------------------------------------------------------------


def test_page_drift_clean_match(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "AGENTS.md").write_text("hello", encoding="utf-8")
    state = _state_with_page("AGENTS.md", "hello")

    assert check_page_drift(state, vault) == []


def test_page_drift_reports_edited_file(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "AGENTS.md").write_text("user edit", encoding="utf-8")
    state = _state_with_page("AGENTS.md", "hello")

    assert check_page_drift(state, vault) == [Issue("page-drift", "AGENTS.md")]


def test_page_drift_skipped_when_proposal_pending(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "AGENTS.md").write_text("user edit", encoding="utf-8")
    write_event = PageWriteEvent(timestamp=NOW, by="core", path="AGENTS.md", hash=_hash("hello"))
    proposal_event = PageProposalEvent(
        timestamp=NOW,
        by="core",
        path="AGENTS.md",
        proposed_path="AGENTS.md.proposed",
        hash=_hash("kit version"),
    )
    state = VaultState(
        page_writes={"AGENTS.md": write_event},
        pending_proposals={"AGENTS.md": proposal_event},
    )

    # Page-drift defers to the pending-proposal check; one issue per path, not two.
    assert check_page_drift(state, vault) == []


def test_page_drift_skips_missing_files(tmp_path: Path) -> None:
    # check_missing owns "file is gone"; page-drift should not double-report.
    vault = _vault(tmp_path)
    state = _state_with_page("AGENTS.md", "hello")

    assert check_page_drift(state, vault) == []


# ---------------------------------------------------------------------------
# check_managed_region_drift
# ---------------------------------------------------------------------------


SCHEMA_TEMPLATE = "types:\n  # BEGIN MANAGED: types\n{types_body}  # END MANAGED: types\n"


def test_managed_region_drift_clean_match(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    body = "  - meeting\n"
    schema = SCHEMA_TEMPLATE.format(types_body=body)
    (vault / "frontmatter.schema.yaml").write_text(schema, encoding="utf-8")

    event = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-init",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - meeting"),  # parse strips the trailing newline
    )

    assert check_managed_region_drift([event], vault, VaultState()) == []


def test_managed_region_drift_reports_edited_body(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    schema = SCHEMA_TEMPLATE.format(types_body="  - meeting\n  - injected\n")
    (vault / "frontmatter.schema.yaml").write_text(schema, encoding="utf-8")

    event = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-init",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - meeting"),
    )

    issues = check_managed_region_drift([event], vault, VaultState())
    assert issues == [Issue("managed-region-drift", "frontmatter.schema.yaml:types")]


def test_managed_region_drift_reports_removed_region(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "frontmatter.schema.yaml").write_text("types: []\n", encoding="utf-8")

    event = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-init",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - meeting"),
    )

    issues = check_managed_region_drift([event], vault, VaultState())
    assert issues == [
        Issue("managed-region-drift", "frontmatter.schema.yaml:types", "region missing")
    ]


def test_managed_region_drift_uses_latest_event_per_region(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    schema = SCHEMA_TEMPLATE.format(types_body="  - meeting\n")
    (vault / "frontmatter.schema.yaml").write_text(schema, encoding="utf-8")

    stale = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-init",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - obsolete"),
    )
    latest = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-add",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - meeting"),
    )

    # The second event shadows the first — no drift.
    assert check_managed_region_drift([stale, latest], vault, VaultState()) == []


def test_managed_region_drift_skips_files_with_pending_proposal(tmp_path: Path) -> None:
    """Retro-review #B6: a file with an open ``.proposed`` sidecar has
    already been flagged as ``pending-proposal``; reporting it again as
    ``managed-region-drift`` is double-counting the same user-actionable
    state. Pairs with #F-B1's resolve fix.
    """

    from llm_wiki_kit.models import PageProposalEvent

    vault = _vault(tmp_path)
    schema = SCHEMA_TEMPLATE.format(types_body="  - injected by the user\n")
    (vault / "frontmatter.schema.yaml").write_text(schema, encoding="utf-8")

    event = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="wiki-init",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_hash("  - meeting"),
    )
    proposal = PageProposalEvent(
        timestamp=NOW,
        by="core",
        path="frontmatter.schema.yaml",
        proposed_path="frontmatter.schema.yaml.proposed",
        hash=_hash("anything"),
    )
    state = VaultState(pending_proposals={"frontmatter.schema.yaml": proposal})

    assert check_managed_region_drift([event], vault, state) == []


# ---------------------------------------------------------------------------
# check_pending_proposals
# ---------------------------------------------------------------------------


def test_pending_proposals_surfaces_sidecar_paths() -> None:
    proposal = PageProposalEvent(
        timestamp=NOW,
        by="core",
        path="AGENTS.md",
        proposed_path="AGENTS.md.proposed",
        hash=_hash("kit version"),
    )
    state = VaultState(pending_proposals={"AGENTS.md": proposal})

    assert check_pending_proposals(state) == [Issue("pending-proposal", "AGENTS.md.proposed")]


def test_pending_proposals_empty_state() -> None:
    assert check_pending_proposals(VaultState()) == []


# ---------------------------------------------------------------------------
# check_orphans
# ---------------------------------------------------------------------------


def test_orphan_reports_file_under_kit_path_with_no_event(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    skills = vault / "skills" / "ingest"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("stray", encoding="utf-8")

    issues = check_orphans(VaultState(), vault)
    assert issues == [Issue("orphan", "skills/ingest/SKILL.md")]


def test_orphan_ignores_user_owned_paths(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "personal").mkdir()
    (vault / "personal" / "notes.md").write_text("my notes", encoding="utf-8")

    assert check_orphans(VaultState(), vault) == []


def test_orphan_ignores_proposed_sidecars(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "AGENTS.md").write_text("baseline", encoding="utf-8")
    (vault / "AGENTS.md.proposed").write_text("kit version", encoding="utf-8")

    proposal = PageProposalEvent(
        timestamp=NOW,
        by="core",
        path="AGENTS.md",
        proposed_path="AGENTS.md.proposed",
        hash=_hash("kit version"),
    )
    state = VaultState(
        page_writes={
            "AGENTS.md": PageWriteEvent(
                timestamp=NOW, by="core", path="AGENTS.md", hash=_hash("baseline")
            )
        },
        pending_proposals={"AGENTS.md": proposal},
    )

    # AGENTS.md is journaled; AGENTS.md.proposed surfaces via pending-proposal,
    # not orphan, even though no event names ``proposed_path`` directly.
    assert check_orphans(state, vault) == []


# ---------------------------------------------------------------------------
# check_missing
# ---------------------------------------------------------------------------


def test_missing_reports_vanished_file(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    state = _state_with_page("AGENTS.md", "hello")

    assert check_missing(state, vault) == [Issue("missing", "AGENTS.md")]


def test_missing_silent_when_file_present(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "AGENTS.md").write_text("hello", encoding="utf-8")
    state = _state_with_page("AGENTS.md", "hello")

    assert check_missing(state, vault) == []


# ---------------------------------------------------------------------------
# check_primitive_missing
# ---------------------------------------------------------------------------


def test_primitive_missing_when_catalog_lacks_recorded_install(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    (kit / "core").mkdir(parents=True)
    (kit / "core" / "primitive.yaml").write_text(
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: Core primitive.\n",
        encoding="utf-8",
    )

    state = VaultState(installed_primitives={"core": "0.1.0", "ghost": "0.1.0"})

    assert check_primitive_missing(state, kit) == [Issue("primitive-missing", "ghost")]


def test_primitive_missing_silent_when_catalog_carries_everything(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    (kit / "core").mkdir(parents=True)
    (kit / "core" / "primitive.yaml").write_text(
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: Core primitive.\n",
        encoding="utf-8",
    )

    state = VaultState(installed_primitives={"core": "0.1.0"})

    assert check_primitive_missing(state, kit) == []


# ---------------------------------------------------------------------------
# run_doctor
# ---------------------------------------------------------------------------


def test_run_doctor_returns_sorted_issues(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    journal = vault / ".wiki.journal" / "journal.jsonl"
    # A barely-valid vault: init + core install, but no page writes.
    append_event(
        journal,
        VaultInitEvent(timestamp=NOW, by="wiki-init", vault_name="v", recipe="family"),
    )
    append_event(
        journal,
        PrimitiveInstallEvent(timestamp=NOW, by="wiki-init", primitive="core", version="0.1.0"),
    )

    # Add a stray under skills/ so the orphan check fires.
    (vault / "skills").mkdir()
    (vault / "skills" / "stray.md").write_text("stray", encoding="utf-8")

    # And an empty kit so the primitive-missing check fires for ``core``.
    kit = tmp_path / "kit"
    kit.mkdir()

    issues = run_doctor(vault, kit)
    kinds = [issue.kind for issue in issues]
    # Sorted: orphan, primitive-missing (alphabetical on kind).
    assert kinds == sorted(kinds)
    assert Issue("orphan", "skills/stray.md") in issues
    assert Issue("primitive-missing", "core") in issues
