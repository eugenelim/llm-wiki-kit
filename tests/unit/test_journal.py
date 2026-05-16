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

import errno
import fcntl
import json
import logging
import multiprocessing
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from llm_wiki_kit.errors import JournalCorruptError
from llm_wiki_kit.journal import append_event, read_events, replay_state
from llm_wiki_kit.models import (
    ConfigSetEvent,
    Event,
    HeldLock,
    LintRunEvent,
    LockAcquiredEvent,
    LockReleasedEvent,
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
# Multiprocessing workers for the flock-around-append_event tests (plan step 3)
#
# Workers must live at module top level so ``multiprocessing`` with the
# ``spawn`` start method can pickle and re-import them in the child process.
# ``spawn`` is the macOS default and the safer cross-platform choice — ``fork``
# would copy pytest's monkeypatched state into the child, which is exactly the
# kind of cross-process leakage these tests are meant to falsify.
# ---------------------------------------------------------------------------


def _appender_worker(journal_str: str, by: str, count: int) -> None:
    """Append ``count`` distinguishable ``VaultInitEvent``s as one subprocess."""

    from llm_wiki_kit.journal import append_event as _append_event
    from llm_wiki_kit.models import VaultInitEvent as _VaultInitEvent

    journal = Path(journal_str)
    for i in range(count):
        _append_event(
            journal,
            _VaultInitEvent(
                timestamp=NOW,
                by=by,
                vault_name=f"{by}-{i:03d}",
                recipe="family",
            ),
        )


def _flock_holder_worker(
    journal_str: str,
    ready_event: Any,
    release_event: Any,
) -> None:
    """Open the journal, take ``LOCK_EX``, signal ready, wait for release.

    Mirrors ``append_event``'s open/flock pattern so a second process's
    ``append_event`` is forced to block in the kernel until this fd closes.
    The lock is released implicitly at the ``with`` block exit; we never
    write to the journal here, so the file's line count is governed entirely
    by what the other process does.

    Note: ``open("a", encoding="utf-8")`` mirrors ``append_event`` exactly
    on purpose. Do not "simplify" to ``open(journal, "rb")`` — the lock
    semantics are tied to the open mode and the test power depends on the
    holder taking the same kind of fd ``append_event`` will try to take.
    """

    journal = Path(journal_str)
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        ready_event.set()
        # 30s is well over any plausible test scheduling delay; if the
        # release signal never arrives the test has already failed elsewhere
        # and we just want the holder to exit cleanly so pytest can collect
        # the report rather than hang.
        release_event.wait(timeout=30)


def _blocked_appender_worker(
    journal_str: str,
    started_event: Any,
    done_event: Any,
) -> None:
    """Signal ``started``, call ``append_event``, signal ``done``."""

    from llm_wiki_kit.journal import append_event as _append_event
    from llm_wiki_kit.models import VaultInitEvent as _VaultInitEvent

    started_event.set()
    _append_event(
        Path(journal_str),
        _VaultInitEvent(
            timestamp=NOW,
            by="blocked-appender",
            vault_name="home",
            recipe="family",
        ),
    )
    done_event.set()


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


def test_append_event_fsyncs_before_returning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spec invariant (docs/specs/journal-locking/spec.md §Durability, qB1):
    # the line is durable on disk before ``append_event`` returns. The
    # test intercepts ``os.fsync`` and, from inside the interceptor,
    # confirms (a) the write+flush has already propagated — a separate
    # reader can see the line — and (b) the counter ticks exactly once.
    # The order assertion is what makes this a contract test rather than
    # a "fsync was called" mock-shape check.
    journal = tmp_path / "journal.jsonl"
    line_type_at_fsync: list[str | None] = []
    real_fsync = os.fsync

    def counting_fsync(fd: int) -> None:
        # ``fh.flush()`` already ran; a separate reader can see the
        # line via the page cache without waiting for the kernel commit.
        if journal.exists():
            text = journal.read_text()
            line_type_at_fsync.append(json.loads(text.splitlines()[0])["type"] if text else None)
        else:
            line_type_at_fsync.append(None)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)
    append_event(
        journal,
        VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
    )
    assert len(line_type_at_fsync) == 1, (
        f"expected exactly one fsync, got {len(line_type_at_fsync)}"
    )
    assert line_type_at_fsync == ["vault.init"], "fsync ran before the line was on disk"


def test_append_event_fsync_fileno_is_journal_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Plan acceptance criterion: the call passes the journal fd
    # specifically, not an unrelated fd. ``fstat(fd).st_ino`` is a
    # same-inode proof — sufficient today because ``append_event`` opens
    # exactly one handle per call; revisit when step 4's ``transaction``
    # introduces fd reuse via a ContextVar and a second handle on the
    # same file becomes plausible.
    journal = tmp_path / "journal.jsonl"
    captured_inodes: list[int] = []
    real_fsync = os.fsync

    def capturing_fsync(fd: int) -> None:
        captured_inodes.append(os.fstat(fd).st_ino)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", capturing_fsync)
    append_event(
        journal,
        VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
    )
    assert captured_inodes == [os.stat(journal).st_ino]


def test_append_event_propagates_oserror_on_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spec §Error cases (docs/specs/journal-locking/spec.md):
    # "``fsync`` failure (EIO) propagates as ``OSError``. Caller's
    # ``WikiError`` handler catches ``WikiError``, not ``OSError``; the
    # traceback surfaces — disk errors are not user-fixable through the
    # CLI." This test pins that contract: a future ``except OSError``
    # silently swallowing the failure would otherwise pass green.
    journal = tmp_path / "journal.jsonl"

    def failing_fsync(fd: int) -> None:
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(OSError) as excinfo:
        append_event(
            journal,
            VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
        )
    assert excinfo.value.errno == errno.EIO
    # The write+flush ran before fsync; the bytes are kernel-side even
    # though fsync failed. The spec's "last successful line is fully
    # durable" claim is about *previous* events (each fsync'd before
    # returning); this event's durability is what failed.
    assert journal.exists()
    assert "vault.init" in journal.read_text()


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
# Lock event replay (journal-locking spec, plan step 1)
# ---------------------------------------------------------------------------


def test_replay_state_tracks_held_lock() -> None:
    """``LockAcquiredEvent`` snapshots the holder; ``LockReleasedEvent`` clears it."""

    acquired = LockAcquiredEvent(
        timestamp=_at(0),
        by="weekly-digest",
        reason="2026-W20 digest",
    )
    state = replay_state([acquired])
    assert state.held_lock == HeldLock(
        by="weekly-digest",
        acquired_at=_at(0),
        reason="2026-W20 digest",
    )

    released = LockReleasedEvent(timestamp=_at(1), by="weekly-digest")
    state = replay_state([acquired, released])
    assert state.held_lock is None


def test_replay_state_last_acquire_wins_when_release_is_missing() -> None:
    """Two ``LockAcquiredEvent``s without a release: replay records the latest holder.

    The stale-lock detection (spec step 6) catches the missing release;
    replay itself is permissive so a hand-edited journal doesn't make the
    kit unrunnable.
    """

    first = LockAcquiredEvent(timestamp=_at(0), by="weekly-digest")
    second = LockAcquiredEvent(timestamp=_at(1), by="bulk-ingest", reason="inbox")
    state = replay_state([first, second])
    assert state.held_lock is not None
    assert state.held_lock.by == "bulk-ingest"
    assert state.held_lock.reason == "inbox"


def test_replay_state_release_without_prior_acquire_keeps_lock_none() -> None:
    """A ``LockReleasedEvent`` against an unheld lock is harmless (matches SKILL.md)."""

    state = replay_state([LockReleasedEvent(timestamp=_at(0), by="weekly-digest")])
    assert state.held_lock is None


def test_replay_state_release_clears_holder_even_when_by_differs() -> None:
    """Mismatched-``by`` release clears the holder unconditionally.

    Pins the contract the spec's stale-lock-reclaim path (Edge cases)
    and the CLI's ``release --force`` flag (step 5) both depend on:
    replay treats every ``LockReleasedEvent`` as a clear, regardless of
    who held the lock. Step 4's ``transaction()`` and step 6's doctor
    will lean on this rule; pinning it now means rediscovery doesn't
    surface as a regression later.
    """

    acquired = LockAcquiredEvent(timestamp=_at(0), by="weekly-digest")
    released_by_other = LockReleasedEvent(timestamp=_at(1), by="wiki-doctor")
    state = replay_state([acquired, released_by_other])
    assert state.held_lock is None


def test_held_lock_acquired_at_is_the_acquire_events_timestamp() -> None:
    """``HeldLock.acquired_at`` carries the acquire event's wall-clock timestamp.

    Step 6's stale-lock check compares ``acquired_at`` against
    ``datetime.now() - WIKI_LOCK_STALE_HOURS``; pin the source-of-truth
    here so a refactor that re-derives ``acquired_at`` from "time replay
    ran" silently breaks the stale-lock semantics.
    """

    acquire_at = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    state = replay_state([LockAcquiredEvent(timestamp=acquire_at, by="weekly-digest")])
    assert state.held_lock is not None
    assert state.held_lock.acquired_at == acquire_at


def test_old_journal_without_lock_events_replays_cleanly(tmp_path: Path) -> None:
    """A journal written before this spec lands replays without raising.

    Acceptance criterion from journal-locking spec §"Schema evolution":
    additive schema changes must leave old journals readable.
    """

    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        '{"type":"vault.init","timestamp":"2026-05-01T00:00:00Z","by":"wiki-init",'
        '"vault_name":"home","recipe":"family","schema_version":1}\n'
        '{"type":"primitive.install","timestamp":"2026-05-01T00:00:00Z","by":"wiki-init",'
        '"primitive":"core","version":"0.1.0"}\n'
        '{"type":"page.write","timestamp":"2026-05-01T00:00:01Z","by":"core",'
        '"path":"AGENTS.md","hash":"' + "a" * 64 + '"}\n',
        encoding="utf-8",
    )
    events = read_events(journal)
    state = replay_state(events)
    assert state.held_lock is None
    assert state.vault_name == "home"
    assert state.installed_primitives == {"core": "0.1.0"}
    assert "AGENTS.md" in state.page_writes


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


# ---------------------------------------------------------------------------
# Mutual exclusion: fcntl.flock around append_event (journal-locking plan
# step 3 / spec §Mutual exclusion / qB2)
# ---------------------------------------------------------------------------


def test_append_event_takes_lock_ex_on_journal_fd_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``append_event`` calls ``fcntl.flock(LOCK_EX)`` on the journal fd
    before writing.

    Discriminating test for plan step 3: the load-style concurrent test
    above can pass even when locking is broken on macOS APFS with small
    lines (single-syscall atomic writes), and the standalone-holder test
    only asserts behavior under a *foreign* lock. A future refactor that
    skipped ``flock`` under some condition (e.g. step 4's planned
    ``ContextVar`` reuse) could regress per-call locking without either
    test failing. This counter-style probe pins "every ``append_event``
    call takes ``LOCK_EX`` on the journal fd it just opened" — the same
    pattern used by ``test_append_event_fsyncs_before_returning`` for
    fsync. Matched-inode check is the same proof shape as the fsync-fd
    test (``os.fstat(fd).st_ino``).
    """

    journal = tmp_path / "journal.jsonl"
    calls: list[tuple[int, int]] = []
    real_flock = fcntl.flock

    def capturing_flock(fd: int, operation: int) -> None:
        calls.append((os.fstat(fd).st_ino, operation))
        real_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", capturing_flock)
    append_event(
        journal,
        VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
    )

    journal_inode = os.stat(journal).st_ino
    assert calls == [(journal_inode, fcntl.LOCK_EX)], (
        f"expected exactly one flock(LOCK_EX) on the journal fd; got {calls}"
    )


def test_concurrent_append_does_not_interleave_lines(tmp_path: Path) -> None:
    """Two processes appending 100 events each produce 200 valid JSONL lines.

    Spec invariant (``docs/specs/journal-locking/spec.md`` §Mutual
    exclusion, qB2): two simultaneous ``append_event`` calls in different
    processes cannot interleave bytes within a single line. Order across
    processes is not asserted — only well-formedness, count, and that
    each process contributed its full 100.

    Note on test power: small JSONL lines on macOS/Linux APFS+ext4 happen
    to land in a single atomic ``os.write()`` syscall even without flock,
    so this test alone wouldn't catch a regression that dropped flock on
    this platform with these line sizes. It catches gross interleaving
    (multi-syscall lines, future longer events, looser-semantic
    filesystems) and pins the parses-to-200 invariant for the rest of
    the suite to rely on; the discriminating test for "flock is actually
    called" is ``test_append_event_blocks_when_another_process_holds_lock``
    below, which would fail under a no-op flock.
    """

    journal = tmp_path / "journal.jsonl"
    ctx = multiprocessing.get_context("spawn")
    p1 = ctx.Process(target=_appender_worker, args=(str(journal), "proc-a", 100))
    p2 = ctx.Process(target=_appender_worker, args=(str(journal), "proc-b", 100))
    p1.start()
    p2.start()
    p1.join(timeout=60)
    p2.join(timeout=60)
    assert p1.exitcode == 0, f"proc-a exited with {p1.exitcode}"
    assert p2.exitcode == 0, f"proc-b exited with {p2.exitcode}"

    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200, f"expected 200 lines, got {len(lines)}"
    counts = {"proc-a": 0, "proc-b": 0}
    for n, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"line {n} is not valid JSON (interleaved?): {exc}; line head={line[:80]!r}"
            )
        assert payload["type"] == "vault.init", f"line {n} unexpected type: {payload}"
        counts[payload["by"]] = counts.get(payload["by"], 0) + 1
    assert counts == {"proc-a": 100, "proc-b": 100}, f"per-process counts wrong: {counts}"


def test_append_event_blocks_when_another_process_holds_lock(tmp_path: Path) -> None:
    """``append_event`` returns only after a foreign ``LOCK_EX`` holder releases.

    Standalone-holder fixture (plan step 3 §Verification): a helper
    subprocess opens the journal, takes ``fcntl.flock(LOCK_EX)``, signals
    ``ready``, then waits on a ``multiprocessing.Event`` to release. A
    second subprocess calls ``append_event`` — it must remain blocked
    until the holder releases. We assert ordering through Events rather
    than a minimum-block wall-clock window (plan §Risks calls out the
    latter as CI-flaky): ``done`` must be unset before ``release`` fires
    and set within a generous timeout after.
    """

    journal = tmp_path / "journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    started = ctx.Event()
    done = ctx.Event()

    holder = ctx.Process(
        target=_flock_holder_worker,
        args=(str(journal), ready, release),
    )
    appender = ctx.Process(
        target=_blocked_appender_worker,
        args=(str(journal), started, done),
    )

    holder.start()
    try:
        try:
            assert ready.wait(timeout=10), "holder did not signal ready"
            appender.start()
            assert started.wait(timeout=10), "appender did not start"
            # The appender signaled ``started`` and is now inside
            # ``append_event``, blocked on ``fcntl.flock``. A 500ms grace
            # window is far more than enough for a JSON-line write + fsync
            # if the lock were broken; ``done`` firing in that window
            # means locking failed open. The check is generous on purpose
            # — we are not asserting a *minimum* block duration (the
            # flaky pattern), we are asserting that ``done`` never
            # precedes ``release``.
            assert not done.wait(timeout=0.5), (
                "appender completed before holder released its lock — flock is not blocking"
            )
            release.set()
            assert done.wait(timeout=10), "appender did not complete after holder released"
        finally:
            # Idempotent — guarantees the appender unblocks regardless of
            # which assert above failed, including assertions reached
            # before ``appender.start()`` (in which case ``pid`` is None
            # and there's nothing to join).
            release.set()
            if appender.pid is not None:
                appender.join(timeout=10)
                if appender.is_alive():
                    appender.kill()
                    appender.join(timeout=5)
        # After inner ``finally`` the appender has been joined; exitcode
        # is now meaningful. On any inner-try failure we never reach
        # here (the exception has already propagated through the inner
        # finally), so this only runs on the happy path.
        assert appender.exitcode == 0, f"appender exited with {appender.exitcode}"
    finally:
        release.set()
        holder.join(timeout=10)
        if holder.is_alive():
            # Wedged holder — kill so a subsequent test inheriting this
            # process tree doesn't see an orphaned flock holder.
            holder.kill()
            holder.join(timeout=5)

    # Sanity: the appender's line is the only line — the holder never wrote.
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["by"] == "blocked-appender"


def test_append_event_falls_back_when_flock_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``EOPNOTSUPP`` from ``fcntl.flock`` logs a warning and writes anyway.

    Spec §Edge cases ("NFS / iCloud Drive / SMB"): on a filesystem that
    rejects advisory locking the kit falls back to pre-spec behavior —
    no concurrent-writer protection, but the journal still gets written.
    Plan §Risks names this fallback explicitly and points at ADR-0002 as
    the contract the warning should cite, so a user reading logs has a
    pointer to "why locking is not in effect here".
    """

    journal = tmp_path / "journal.jsonl"

    calls: list[int] = []

    def failing_flock(fd: int, operation: int) -> None:
        calls.append(operation)
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr(fcntl, "flock", failing_flock)

    with caplog.at_level(logging.WARNING, logger="llm_wiki_kit.journal"):
        append_event(
            journal,
            VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
        )

    assert calls, "fcntl.flock was not called"
    assert calls[0] == fcntl.LOCK_EX, f"expected LOCK_EX, got operation={calls[0]}"
    assert journal.exists()
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["type"] == "vault.init"

    warning_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ADR-0002" in msg for msg in warning_msgs), (
        f"expected a warning mentioning ADR-0002, got: {warning_msgs}"
    )


def test_append_event_warns_once_per_journal_path_on_unsupported_flock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Repeated unsupported-FS appends emit one warning, not one per event.

    Spec §Edge cases pins the once-per-path-per-process gate so a
    ``wiki run`` on iCloud doesn't spam the same paragraph dozens of
    times. Without the gate (and without this test) a future refactor
    that dropped the suppression would slip through both prior tests:
    ``test_append_event_falls_back_when_flock_unsupported`` only
    exercises the first call.
    """

    # ``_LOCK_FALLBACK_WARNED`` is module-global and not cleared between
    # tests by design — tmp_path gives a unique journal per test, so
    # cross-test contamination doesn't happen in practice. Still, reset
    # it here so the second-call assertion is unambiguous when the test
    # is run with ``--count`` or under ``pytest-repeat``.
    import llm_wiki_kit.journal as _journal_mod

    monkeypatch.setattr(_journal_mod, "_LOCK_FALLBACK_WARNED", set())

    journal = tmp_path / "journal.jsonl"

    def failing_flock(fd: int, operation: int) -> None:
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr(fcntl, "flock", failing_flock)

    with caplog.at_level(logging.WARNING, logger="llm_wiki_kit.journal"):
        for i in range(3):
            append_event(
                journal,
                VaultInitEvent(timestamp=NOW, by="core", vault_name=f"home-{i}", recipe="family"),
            )

    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3, "all three events should still be written despite no locking"

    adr_warnings = [
        r for r in caplog.records if r.levelno == logging.WARNING and "ADR-0002" in r.getMessage()
    ]
    assert len(adr_warnings) == 1, (
        f"expected exactly one ADR-0002 warning across three appends; got {len(adr_warnings)}"
    )


def test_append_event_fallback_warns_once_across_path_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Two ``Path`` spellings of the same on-disk journal collapse to one warning.

    Spec §Edge cases keys the once-per-path gate on the resolved path, not
    on ``Path``-object identity. A caller invoking ``append_event`` once
    via a symlinked directory and once via the real directory points at
    the same file with different ``Path`` instances; the suppression must
    collapse them. Without ``.resolve()`` keying the set, each spelling
    would hash to a different key and the warning would re-fire — exactly
    the per-event noise the gate exists to prevent.
    """

    import llm_wiki_kit.journal as _journal_mod

    monkeypatch.setattr(_journal_mod, "_LOCK_FALLBACK_WARNED", set())

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    journal_via_real = real_dir / "journal.jsonl"
    journal_via_link = link_dir / "journal.jsonl"
    assert journal_via_real != journal_via_link, "test setup: paths should not be == as objects"
    assert journal_via_real.resolve() == journal_via_link.resolve(), (
        "test setup: paths should resolve to the same file"
    )

    def failing_flock(fd: int, operation: int) -> None:
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr(fcntl, "flock", failing_flock)

    with caplog.at_level(logging.WARNING, logger="llm_wiki_kit.journal"):
        append_event(
            journal_via_real,
            VaultInitEvent(timestamp=NOW, by="core", vault_name="home-1", recipe="family"),
        )
        append_event(
            journal_via_link,
            VaultInitEvent(timestamp=NOW, by="core", vault_name="home-2", recipe="family"),
        )

    adr_warnings = [
        r for r in caplog.records if r.levelno == logging.WARNING and "ADR-0002" in r.getMessage()
    ]
    assert len(adr_warnings) == 1, (
        f"expected one warning across two spellings of the same file; got {len(adr_warnings)}"
    )


def test_append_event_propagates_oserror_eintr_from_flock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``OSError(EINTR)`` from ``fcntl.flock`` propagates — not in the fallback set.

    PEP 475 auto-retries ``EINTR`` on CPython for native ``fcntl`` calls,
    so in production the caller never sees it. This test injects ``EINTR``
    through a monkeypatched ``fcntl.flock`` to pin the *userspace* boundary:
    a future refactor (e.g. step 4) that broadens the fallback errno set
    must not silently swallow ``EINTR`` as "filesystem unsupported".
    """

    journal = tmp_path / "journal.jsonl"

    def eintr_flock(fd: int, operation: int) -> None:
        raise OSError(errno.EINTR, "Interrupted system call")

    monkeypatch.setattr(fcntl, "flock", eintr_flock)

    with pytest.raises(OSError) as excinfo:
        append_event(
            journal,
            VaultInitEvent(timestamp=NOW, by="core", vault_name="home", recipe="family"),
        )
    assert excinfo.value.errno == errno.EINTR
