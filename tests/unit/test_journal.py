"""Tests for ``llm_wiki_kit.journal``.

ADR-0002 names the contract: an append-only JSONL file is the source of truth
for vault state, ``append_event`` validates and appends one line at a time,
``read_events`` parses every line through the discriminated ``Event`` union
and raises ``JournalCorruptError(line=N)`` on the first malformed line, and
``replay_state`` derives a ``VaultState`` from an ordered iterable of events.

These tests pin those four behaviors plus the ADR's acceptance criterion of
replaying 1000 events in under 100ms.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llm_wiki_kit.errors import JournalCorruptError
from llm_wiki_kit.journal import append_event, read_events, replay_state
from llm_wiki_kit.models import (
    ConfigSetEvent,
    Event,
    LintRunEvent,
    ManagedRegionWriteEvent,
    OperationRunEvent,
    PageConflictResolvedEvent,
    PageProposalEvent,
    PageWriteEvent,
    PrimitiveInstallEvent,
    PrimitiveRemoveEvent,
    PrimitiveUpgradeEvent,
    ResearchQueryEvent,
    SourceIngestEvent,
    VaultInitEvent,
)

NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------


def test_append_event_creates_file_and_parent_dir(tmp_path: Path) -> None:
    journal = tmp_path / ".wiki.journal" / "journal.jsonl"
    assert not journal.exists()
    append_event(
        journal,
        VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
    )
    assert journal.exists()
    assert journal.parent.is_dir()


def test_append_event_appends_one_json_line_with_trailing_newline(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    append_event(
        journal,
        PrimitiveInstallEvent(
            timestamp=NOW, by="recipe:family", primitive="people", version="0.1.0"
        ),
    )
    text = journal.read_text()
    assert text.endswith("\n")
    assert text.count("\n") == 1
    parsed = json.loads(text)
    assert parsed["type"] == "primitive.install"
    assert parsed["primitive"] == "people"


def test_append_event_accumulates_multiple_lines_in_order(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    append_event(
        journal, VaultInitEvent(timestamp=_at(0), by="core", vault_name="home", recipe="family")
    )
    append_event(
        journal,
        PrimitiveInstallEvent(timestamp=_at(1), by="core", primitive="core", version="0.1.0"),
    )
    append_event(
        journal,
        PrimitiveInstallEvent(timestamp=_at(2), by="core", primitive="people", version="0.1.0"),
    )

    lines = journal.read_text().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["type"] == "vault.init"
    assert json.loads(lines[1])["primitive"] == "core"
    assert json.loads(lines[2])["primitive"] == "people"


def test_append_event_round_trips_through_read_events(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    events: list[Event] = [
        VaultInitEvent(timestamp=_at(0), by="core", vault_name="home", recipe="family"),
        PrimitiveInstallEvent(timestamp=_at(1), by="core", primitive="meeting", version="0.1.0"),
        PageWriteEvent(
            timestamp=_at(2), by="meeting", path="meetings/2026-05-15.md", hash="a" * 64
        ),
    ]
    for e in events:
        append_event(journal, e)

    loaded = read_events(journal)
    assert loaded == events


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------


def test_read_events_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert read_events(tmp_path / "absent.jsonl") == []


def test_read_events_returns_empty_when_file_empty(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    journal.write_text("")
    assert read_events(journal) == []


def test_read_events_skips_blank_lines(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    append_event(
        journal, VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family")
    )
    # Trailing blank line is normal for an append-only file.
    with journal.open("a") as fh:
        fh.write("\n")
    events = read_events(journal)
    assert len(events) == 1
    assert isinstance(events[0], VaultInitEvent)


def test_read_events_raises_on_malformed_json_with_line_number(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    append_event(
        journal, VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family")
    )
    with journal.open("a") as fh:
        fh.write("{not json\n")
        fh.write(
            '{"type": "page.write", "timestamp": "2026-05-15T12:00:00+00:00",'
            ' "by": "x", "path": "p", "hash": "a"}\n'
        )

    with pytest.raises(JournalCorruptError) as excinfo:
        read_events(journal)
    assert excinfo.value.line == 2


def test_read_events_raises_on_unknown_event_type_with_line_number(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    append_event(
        journal, VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family")
    )
    append_event(
        journal, PrimitiveInstallEvent(timestamp=NOW, by="core", primitive="core", version="0.1.0")
    )
    with journal.open("a") as fh:
        fh.write('{"type": "made.up", "timestamp": "2026-05-15T12:00:00+00:00", "by": "core"}\n')

    with pytest.raises(JournalCorruptError) as excinfo:
        read_events(journal)
    assert excinfo.value.line == 3


def test_read_events_raises_on_missing_required_field(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    with journal.open("w") as fh:
        # page.write missing required `hash`
        fh.write(
            '{"type": "page.write", "timestamp": "2026-05-15T12:00:00+00:00",'
            ' "by": "x", "path": "p"}\n'
        )

    with pytest.raises(JournalCorruptError) as excinfo:
        read_events(journal)
    assert excinfo.value.line == 1


# ---------------------------------------------------------------------------
# replay_state
# ---------------------------------------------------------------------------


def test_replay_empty_returns_default_vault_state() -> None:
    state = replay_state([])
    assert state.vault_name is None
    assert state.recipe is None
    assert state.installed_primitives == {}
    assert state.page_writes == {}
    assert state.pending_proposals == {}
    assert state.ingested_sources == {}
    assert state.recent_operations == {}
    assert state.recent_research == []


def test_replay_vault_init_sets_name_and_recipe() -> None:
    state = replay_state(
        [VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family")]
    )
    assert state.vault_name == "home"
    assert state.recipe == "family"


def test_replay_primitive_install_adds_to_installed() -> None:
    state = replay_state(
        [
            PrimitiveInstallEvent(timestamp=_at(0), by="core", primitive="core", version="0.1.0"),
            PrimitiveInstallEvent(timestamp=_at(1), by="core", primitive="people", version="0.2.0"),
        ]
    )
    assert state.installed_primitives == {"core": "0.1.0", "people": "0.2.0"}


def test_replay_primitive_upgrade_changes_version() -> None:
    state = replay_state(
        [
            PrimitiveInstallEvent(timestamp=_at(0), by="core", primitive="people", version="0.1.0"),
            PrimitiveUpgradeEvent(
                timestamp=_at(1),
                by="core",
                primitive="people",
                from_version="0.1.0",
                to_version="0.2.0",
            ),
        ]
    )
    assert state.installed_primitives == {"people": "0.2.0"}


def test_replay_primitive_remove_drops_it() -> None:
    state = replay_state(
        [
            PrimitiveInstallEvent(timestamp=_at(0), by="core", primitive="people", version="0.1.0"),
            PrimitiveRemoveEvent(timestamp=_at(1), by="core", primitive="people"),
        ]
    )
    assert state.installed_primitives == {}


def test_replay_page_write_tracks_most_recent_per_path() -> None:
    earlier = PageWriteEvent(timestamp=_at(0), by="meeting", path="p.md", hash="a" * 64)
    later = PageWriteEvent(timestamp=_at(1), by="meeting", path="p.md", hash="b" * 64)
    state = replay_state([earlier, later])
    assert state.page_writes == {"p.md": later}


def test_replay_page_proposal_records_pending() -> None:
    proposal = PageProposalEvent(
        timestamp=_at(0),
        by="meeting",
        path="p.md",
        proposed_path="p.md.proposed",
        hash="a" * 64,
    )
    state = replay_state([proposal])
    assert state.pending_proposals == {"p.md": proposal}


def test_replay_page_write_clears_matching_pending_proposal() -> None:
    proposal = PageProposalEvent(
        timestamp=_at(0),
        by="meeting",
        path="p.md",
        proposed_path="p.md.proposed",
        hash="a" * 64,
    )
    resolved = PageWriteEvent(timestamp=_at(1), by="meeting", path="p.md", hash="b" * 64)
    state = replay_state([proposal, resolved])
    assert state.pending_proposals == {}
    assert state.page_writes == {"p.md": resolved}


def test_replay_conflict_resolved_clears_pending_proposal() -> None:
    proposal = PageProposalEvent(
        timestamp=_at(0),
        by="meeting",
        path="p.md",
        proposed_path="p.md.proposed",
        hash="a" * 64,
    )
    resolved = PageConflictResolvedEvent(timestamp=_at(1), by="user", path="p.md", hash="c" * 64)
    state = replay_state([proposal, resolved])
    assert state.pending_proposals == {}


def test_replay_source_ingest_indexes_by_source() -> None:
    ingest = SourceIngestEvent(
        timestamp=NOW,
        by="meeting",
        source="/tmp/t.txt",
        source_hash="h" * 64,
        content_type="meeting",
    )
    state = replay_state([ingest])
    assert state.ingested_sources == {"/tmp/t.txt": ingest}


def test_replay_operation_run_keeps_most_recent_per_operation() -> None:
    first = OperationRunEvent(
        timestamp=_at(0), by="core", operation="weekly-digest", status="success"
    )
    second = OperationRunEvent(
        timestamp=_at(1), by="core", operation="weekly-digest", status="success"
    )
    state = replay_state([first, second])
    assert state.recent_operations == {"weekly-digest": second}


def test_replay_research_query_accumulates_in_order() -> None:
    q1 = ResearchQueryEvent(timestamp=_at(0), by="user", query="a", provider="perplexity")
    q2 = ResearchQueryEvent(timestamp=_at(1), by="user", query="b", provider="gemini")
    state = replay_state([q1, q2])
    assert state.recent_research == [q1, q2]


def test_replay_ignores_events_that_dont_affect_state() -> None:
    state = replay_state(
        [
            ManagedRegionWriteEvent(
                timestamp=NOW, by="core", file="AGENTS.md", region="x", content_hash="a" * 64
            ),
            LintRunEvent(timestamp=NOW, by="core", status="ok"),
            ConfigSetEvent(timestamp=NOW, by="user", key="k", value="v"),
        ]
    )
    # No crash, no state contribution.
    assert state.installed_primitives == {}
    assert state.page_writes == {}


# ---------------------------------------------------------------------------
# Performance: ADR-0002 acceptance criterion
# ---------------------------------------------------------------------------


def test_replay_1000_events_under_100ms() -> None:
    events: list[Event] = [
        PageWriteEvent(
            timestamp=_at(i),
            by="meeting",
            path=f"pages/{i % 50}.md",
            hash=f"{i:064x}",
        )
        for i in range(1000)
    ]
    start = time.perf_counter()
    state = replay_state(events)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"replay of 1000 events took {elapsed * 1000:.1f}ms (budget: 100ms)"
    assert len(state.page_writes) == 50
