"""Append-only journal at ``.wiki.journal/journal.jsonl``.

ADR-0002 names this module the source of truth for vault state. Four
operations cover its surface:

- ``append_event`` validates a Pydantic ``Event`` and appends one JSON line.
- ``read_events`` parses every line through the discriminated ``Event``
  union and raises ``JournalCorruptError(line=N)`` on the first malformed
  line. We fail loudly — corrupted state is the user's signal.
- ``read_events_lenient`` returns ``(events, Corruption | None)`` instead
  of raising. Only ``wiki doctor`` consumes this shape (it has to keep
  reporting the *other* checks even when the journal is partially
  corrupt); every other caller stays on strict ``read_events`` because
  silently swallowing corruption is exactly the bug ADR-0002 forbids.
- ``replay_state`` walks an ordered iterable of events and returns the
  derived ``VaultState`` (installed primitives, latest page writes per
  path, outstanding proposals, ingested sources, most recent operation
  per name, research history).

The module depends only on ``models`` and ``errors`` (see
``docs/architecture/overview.md``).
"""

from __future__ import annotations

import errno
import fcntl
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import JournalCorruptError
from llm_wiki_kit.models import (
    ConfigSetEvent,
    Event,
    HeldLock,
    IngestRoutedEvent,
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
    VaultState,
)

_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)

_logger = logging.getLogger(__name__)

# Errno set that signals "this filesystem doesn't support advisory locking" —
# the documented fallback population in spec §Edge cases (iCloud Drive, SMB,
# some NFS configurations). POSIX is loose here: macOS and Linux disagree on
# which constant fires (``EOPNOTSUPP`` vs ``ENOTSUP``), and an NFS mount
# without ``lockd`` returns ``ENOLCK``. We catch the explicit set and let
# every other ``OSError`` propagate, matching the spec's "advisory locking
# is best-effort on synced filesystems" contract. ``EINTR`` is *not* in the
# set — PEP 475 auto-retries it on CPython for syscall-style ``fcntl``
# calls, and a userspace mock that raises it must propagate so step 4 (and
# beyond) can't silently relax the boundary.
_LOCK_UNSUPPORTED_ERRNOS = frozenset({errno.EOPNOTSUPP, errno.ENOTSUP, errno.ENOLCK})

# Suppress the "filesystem does not support locking" warning after the first
# emission per *resolved* journal path in this process. A ``wiki run``
# operation emits dozens of events; one warning is informative, thirty is
# noise. Keyed on the resolved path so two different ``Path`` spellings
# (symlink, relative-vs-absolute) to the same file collapse to one warning.
# Cleared only on process exit (we don't persist the suppression).
_LOCK_FALLBACK_WARNED: set[Path] = set()


def _warn_lock_fallback_once(journal_path: Path, exc: OSError) -> None:
    """Emit one ``WARNING`` per resolved journal path for an unsupported-flock OSError.

    Owns the ``_LOCK_FALLBACK_WARNED`` suppression set so callers don't
    reach into it directly. ``journal_path.resolve()`` collapses symlinks
    and relative-vs-absolute spellings to a single key — the spec
    invariant is "once per *journal path*", not "once per ``Path``
    object identity".
    """

    resolved = journal_path.resolve()
    if resolved in _LOCK_FALLBACK_WARNED:
        return
    _LOCK_FALLBACK_WARNED.add(resolved)
    errno_value = exc.errno if exc.errno is not None else 0
    _logger.warning(
        "advisory locking is unsupported on this filesystem (%s, errno=%d); "
        "concurrent writers to %s are not serialized — see ADR-0002 "
        "(journal as state truth) and docs/specs/journal-locking/spec.md "
        "§Edge cases",
        errno.errorcode.get(errno_value, "unknown"),
        errno_value,
        resolved,
    )


@dataclass(frozen=True)
class Corruption:
    """One bad line found by ``read_events_lenient``.

    Mirrors ``JournalCorruptError(line, reason)`` so the two corruption
    surfaces — the strict-mode exception and the lenient-mode return
    value — carry the same information shape. Frozen because doctor
    treats it as a value, not an aggregate.
    """

    line: int
    reason: str


def _summarize(exc: PydanticValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "validation failed"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = first.get("msg", "validation failed")
    return f"{loc}: {msg}" if loc else msg


def append_event(journal_path: Path, event: Event) -> None:
    """Append one validated event as a single JSON line, durable before returning.

    The write block is serialized by ``fcntl.flock(LOCK_EX)`` on the
    journal file descriptor so two concurrent ``append_event`` calls in
    different processes cannot interleave bytes within a single line
    (``docs/specs/journal-locking/spec.md`` §Mutual exclusion, qB2). The
    lock releases when the ``with`` block closes the fd — on normal
    return, on any exception propagating from the ``write`` / ``flush`` /
    ``fsync`` calls, or on a hard crash inside the block — so the lock
    can never outlive the process.

    On filesystems that don't support advisory locking — iCloud Drive,
    SMB, some NFS configurations — ``fcntl.flock`` raises one of
    ``OSError(EOPNOTSUPP | ENOTSUP | ENOLCK)`` (the set differs by
    platform and mount). The kit logs a ``WARNING`` once per resolved
    journal path naming ADR-0002 and continues without locking,
    matching pre-spec behavior; this is the documented fallback in the
    spec's Edge cases section. Any other ``OSError`` from ``flock``
    propagates — including ``EINTR`` (PEP 475 auto-retries it on
    CPython, so callers should not see it in practice).

    After the line is written, ``fh.flush()`` drains Python's buffer and
    ``os.fsync()`` forces the kernel to commit the journal file to disk
    so a crash after ``append_event`` returns cannot lose the line
    (§Durability, qB1). An ``fsync`` failure (EIO) propagates as
    ``OSError`` to the caller. ADR-0002's "Concurrent writers are not
    safe" note will be amended to point at this spec in plan step 7.
    """

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    line = _EVENT_ADAPTER.dump_json(event).decode() + "\n"
    with journal_path.open("a", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            if exc.errno not in _LOCK_UNSUPPORTED_ERRNOS:
                raise
            _warn_lock_fallback_once(journal_path, exc)
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def _parse_line(line_number: int, raw: str) -> Event | None:
    """Parse one journal line.

    Returns ``None`` for a blank line (trailing newline on an append-only
    file is normal). Raises ``JournalCorruptError`` with the 1-based
    ``line_number`` on malformed JSON or a payload that fails Pydantic
    validation. Shared between ``read_events`` and ``read_events_lenient``
    so the two paths can't drift on what counts as "bad".
    """

    stripped = raw.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise JournalCorruptError(line=line_number, reason=f"invalid JSON: {exc.msg}") from exc
    try:
        return _EVENT_ADAPTER.validate_python(payload)
    except PydanticValidationError as exc:
        raise JournalCorruptError(line=line_number, reason=_summarize(exc)) from exc


def read_events(journal_path: Path) -> list[Event]:
    """Parse and validate every line in the journal.

    Returns an empty list when the file does not exist (a fresh vault has
    no journal yet). Blank lines are skipped because a trailing newline is
    normal for an append-only file. The first line that fails to parse as
    JSON or to validate against the ``Event`` union raises
    ``JournalCorruptError(line=N)`` with a 1-based line number.
    """

    if not journal_path.exists():
        return []

    events: list[Event] = []
    with journal_path.open("r", encoding="utf-8") as fh:
        for line_number, raw in enumerate(fh, start=1):
            event = _parse_line(line_number, raw)
            if event is not None:
                events.append(event)

    return events


def read_events_lenient(journal_path: Path) -> tuple[list[Event], Corruption | None]:
    """Strict ``read_events``'s sibling for the recovery path.

    Returns ``(events, None)`` on a clean journal — the same list strict
    would have returned. On the first malformed line, returns
    ``(events_before, Corruption(line, reason))`` instead of raising:
    every event before the bad line is parsed and handed back, and the
    rest of the file is left unread.

    Stopping at the first bad line is a conservative convention, not a
    claim that the kit knows the tail is torn: a hand-edited bogus row
    surrounded by valid ones is a real shape (it shows up in this
    module's own corruption tests). Surfacing one corruption row per
    pass keeps the doctor's output digestible and forces the user (or
    Claude) to repair the journal before re-running rather than chasing
    a cascade of half-overlapping reports.

    Only ``wiki doctor`` consumes this — see ``journal-locking`` spec
    §Recovery. Every other caller stays on strict ``read_events`` so a
    silent corruption-swallow can't ship through the back door.
    """

    if not journal_path.exists():
        return [], None

    events: list[Event] = []
    with journal_path.open("r", encoding="utf-8") as fh:
        for line_number, raw in enumerate(fh, start=1):
            try:
                event = _parse_line(line_number, raw)
            except JournalCorruptError as exc:
                return events, Corruption(line=exc.line, reason=exc.reason)
            if event is not None:
                events.append(event)

    return events, None


def replay_state(events: Iterable[Event]) -> VaultState:
    """Derive ``VaultState`` from an ordered iterable of events.

    Order matters: ``primitive.install`` followed by ``primitive.remove``
    leaves the primitive uninstalled. The state dicts keep only the most
    recent event per natural key (page path, source identifier, operation
    name); ``recent_research`` is an ordered list because the natural key
    is the query itself and duplicates carry information.
    """

    state = VaultState()
    for event in events:
        if isinstance(event, VaultInitEvent):
            state.vault_name = event.vault_name
            state.recipe = event.recipe
        elif isinstance(event, PrimitiveInstallEvent):
            state.installed_primitives[event.primitive] = event.version
        elif isinstance(event, PrimitiveUpgradeEvent):
            state.installed_primitives[event.primitive] = event.to_version
        elif isinstance(event, PrimitiveRemoveEvent):
            state.installed_primitives.pop(event.primitive, None)
        elif isinstance(event, PageWriteEvent):
            state.page_writes[event.path] = event
            state.pending_proposals.pop(event.path, None)
        elif isinstance(event, PageProposalEvent):
            state.pending_proposals[event.path] = event
        elif isinstance(event, PageConflictResolvedEvent):
            state.pending_proposals.pop(event.path, None)
        elif isinstance(event, SourceIngestEvent):
            state.ingested_sources[event.source] = event
        elif isinstance(event, OperationRunEvent):
            state.recent_operations[event.operation] = event
        elif isinstance(event, ResearchQueryEvent):
            state.recent_research.append(event)
        elif isinstance(event, LockAcquiredEvent):
            # Last write wins: a second acquire without an intervening
            # release overwrites the holder. The stale-lock check in
            # ``wiki doctor`` (journal-locking spec plan step 6) catches
            # the missing-release case; replay itself stays permissive so
            # a hand-edited journal doesn't make the kit unrunnable.
            state.held_lock = HeldLock(
                by=event.by,
                acquired_at=event.timestamp,
                reason=event.reason,
            )
        elif isinstance(event, LockReleasedEvent):
            state.held_lock = None
        elif isinstance(
            event,
            ManagedRegionWriteEvent | LintRunEvent | ConfigSetEvent | IngestRoutedEvent,
        ):
            # Recorded for audit; no contribution to derived state today.
            # ``IngestRoutedEvent`` is consumed directly by future
            # ``journal explain`` rather than aggregated into ``VaultState``.
            continue
    return state
