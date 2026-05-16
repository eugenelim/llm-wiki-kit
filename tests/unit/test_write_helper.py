"""Tests for ``llm_wiki_kit.write_helper``.

ADR-0004 names the contract: ``safe_write`` is the only sanctioned write path
for files inside a user vault. It hashes on-disk content, compares to the
most recent ``PageWrite`` event for that path in the journal, writes directly
on a match (or when there's no prior knowledge) and emits a ``PageWrite``
event, or writes a ``<path>.proposed`` sidecar and emits a ``PageProposal``
event when the hashes diverge. The sidecar flow also adds a ``\\.proposed$``
pattern to ``.obsidianignore`` so Obsidian doesn't index conflict files.

These tests pin every numbered step from ADR-0004 §Mechanics.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import (
    PageProposalEvent,
    PageWriteEvent,
)
from llm_wiki_kit.write_helper import (
    OBSIDIAN_IGNORE_PROPOSED_PATTERN,
    WriteResult,
    safe_write,
)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A vault root with the canonical journal path beneath it."""
    (tmp_path / ".wiki.journal").mkdir()
    return tmp_path


@pytest.fixture
def journal(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


# ---------------------------------------------------------------------------
# WriteResult
# ---------------------------------------------------------------------------


def test_write_result_has_written_and_proposal_members() -> None:
    assert {member.name for member in WriteResult} == {"WRITTEN", "PROPOSAL"}


# ---------------------------------------------------------------------------
# Direct write path: no prior knowledge / matching baseline
# ---------------------------------------------------------------------------


def test_first_write_creates_file_and_returns_written(vault: Path, journal: Path) -> None:
    target = vault / "meetings" / "2026-05-15.md"
    result = safe_write(target, "hello\n", by="meeting", journal_path=journal)
    assert result is WriteResult.WRITTEN
    assert target.read_text() == "hello\n"


def test_first_write_creates_parent_directories(vault: Path, journal: Path) -> None:
    target = vault / "a" / "b" / "c" / "page.md"
    safe_write(target, "x", by="core", journal_path=journal)
    assert target.exists()


def test_first_write_emits_page_write_event_with_sha256(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "hello", by="core", journal_path=journal)
    events = read_events(journal)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PageWriteEvent)
    assert event.hash == _sha256("hello")
    assert event.hash_algo == "sha256"
    assert event.by == "core"


def test_first_write_stores_path_relative_to_vault(vault: Path, journal: Path) -> None:
    target = vault / "meetings" / "2026-05-15.md"
    safe_write(target, "x", by="meeting", journal_path=journal)
    events = read_events(journal)
    assert isinstance(events[0], PageWriteEvent)
    assert events[0].path == "meetings/2026-05-15.md"


def test_first_write_overwrites_existing_file_without_journal_entry(
    vault: Path, journal: Path
) -> None:
    """ADR-0004 §Mechanics step 2: no prior PageWrite → direct write.

    The mitigation against silent clobbering is at the ``wiki init`` layer
    (refuse non-empty folders unless ``--adopt`` is passed), not here.
    """
    target = vault / "page.md"
    target.write_text("user's pre-existing content")
    result = safe_write(target, "kit content", by="core", journal_path=journal)
    assert result is WriteResult.WRITTEN
    assert target.read_text() == "kit content"


def test_repeated_write_with_no_drift_overwrites_and_appends_new_event(
    vault: Path, journal: Path
) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    result = safe_write(target, "v2", by="core", journal_path=journal)
    assert result is WriteResult.WRITTEN
    assert target.read_text() == "v2"
    events = read_events(journal)
    assert len(events) == 2
    assert all(isinstance(e, PageWriteEvent) for e in events)
    page_writes = [e for e in events if isinstance(e, PageWriteEvent)]
    assert page_writes[-1].hash == _sha256("v2")


def test_no_op_write_of_identical_content_still_records_event(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "same", by="core", journal_path=journal)
    safe_write(target, "same", by="core", journal_path=journal)
    events = read_events(journal)
    assert len(events) == 2  # journal records every kit write attempt


# ---------------------------------------------------------------------------
# Drift path: sidecar + proposal event + .obsidianignore
# ---------------------------------------------------------------------------


def test_drift_writes_sidecar_and_leaves_original_untouched(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")  # simulate the user editing the file
    result = safe_write(target, "v2 from kit", by="core", journal_path=journal)
    assert result is WriteResult.PROPOSAL
    assert target.read_text() == "user edits"
    assert (vault / "page.md.proposed").read_text() == "v2 from kit"


def test_drift_emits_page_proposal_event(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="weekly-digest", journal_path=journal)

    events = read_events(journal)
    proposal = events[-1]
    assert isinstance(proposal, PageProposalEvent)
    assert proposal.path == "page.md"
    assert proposal.proposed_path == "page.md.proposed"
    assert proposal.hash == _sha256("v2")
    assert proposal.by == "weekly-digest"


def test_drift_creates_obsidianignore_with_proposed_pattern(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="core", journal_path=journal)

    ignore = (vault / ".obsidianignore").read_text()
    assert OBSIDIAN_IGNORE_PROPOSED_PATTERN in ignore.splitlines()


def test_drift_does_not_duplicate_obsidianignore_pattern(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="core", journal_path=journal)
    safe_write(target, "v3", by="core", journal_path=journal)

    lines = (vault / ".obsidianignore").read_text().splitlines()
    assert lines.count(OBSIDIAN_IGNORE_PROPOSED_PATTERN) == 1


def test_drift_appends_to_existing_obsidianignore(vault: Path, journal: Path) -> None:
    (vault / ".obsidianignore").write_text("# user patterns\nscratch/\n")
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="core", journal_path=journal)

    text = (vault / ".obsidianignore").read_text()
    assert "# user patterns" in text
    assert "scratch/" in text
    assert OBSIDIAN_IGNORE_PROPOSED_PATTERN in text.splitlines()


def test_drift_twice_overwrites_proposed_file_and_logs_new_event(
    vault: Path, journal: Path
) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="core", journal_path=journal)
    safe_write(target, "v3", by="core", journal_path=journal)

    assert (vault / "page.md.proposed").read_text() == "v3"
    proposals = [e for e in read_events(journal) if isinstance(e, PageProposalEvent)]
    assert len(proposals) == 2
    assert proposals[-1].hash == _sha256("v3")


def test_drift_does_not_emit_a_page_write_event(vault: Path, journal: Path) -> None:
    target = vault / "page.md"
    safe_write(target, "v1", by="core", journal_path=journal)
    target.write_text("user edits")
    safe_write(target, "v2", by="core", journal_path=journal)

    page_writes = [e for e in read_events(journal) if isinstance(e, PageWriteEvent)]
    assert len(page_writes) == 1  # only the original; the drifted write is a proposal
