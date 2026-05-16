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
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

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


@dataclass(frozen=True)
class _HeldFd:
    """In-process snapshot of an open, lock-held journal fd.

    Owned by ``transaction()`` and read by ``append_event``. The resolved
    path is the key — two ``Path`` spellings (symlink, relative-vs-
    absolute) of the same journal collapse to one held-fd identity so
    nested ``append_event(<other-spelling>)`` reuses the fd as the
    caller intended. The fd is the open file handle the transaction is
    serving.
    """

    resolved_path: Path
    fh: IO[str]


# ContextVar so the held-fd lookup is per-task (asyncio) and per-thread
# friendly: a future runner that fans out two transactions across two
# tasks won't have one task's held fd leak into the other's
# ``append_event`` calls. Default ``None`` means "no transaction is
# active in this context", which is the per-event-lock path
# ``append_event`` has always taken.
_HELD_FD: ContextVar[_HeldFd | None] = ContextVar("_HELD_FD", default=None)

# Module-level stash for fds left open by ``transaction(persist=True)``'s
# clean exit. Keyed on resolved journal path. Without this, the fd opened
# inside ``transaction`` is a generator-frame local: once the generator
# returns, refcount drops to zero, CPython closes the fd, and the OS-level
# ``flock`` is released — defeating spec §Behavior lines 127-128 ("future
# ``fcntl.flock`` attempts from other processes block until ``wiki lock
# release`` runs"). The stash keeps the fd reachable until process exit
# (or until step 5's ``wiki lock release`` calls ``_release_persisted_fd``).
# At process exit Python closes every open fd; the OS releases the lock.
_PERSISTED_FDS: dict[Path, IO[str]] = {}


def _release_persisted_fd(journal_path: Path) -> None:
    """Close the fd left open by a prior ``transaction(persist=True)`` clean exit.

    Step 5's ``wiki lock release`` calls this to drop the OS-level lock
    the matching ``wiki lock acquire`` left holding. A missing entry is
    a no-op — spec §Outputs makes ``release`` on an unheld lock a silent
    success. The journal is only opened/closed here; the
    ``LockReleasedEvent`` append and holder-file deletion are step 5's
    work, not this module's.
    """

    resolved = journal_path.resolve()
    fh = _PERSISTED_FDS.pop(resolved, None)
    if fh is not None:
        fh.close()


def _take_exclusive_lock(fh: IO[str], journal_path: Path) -> None:
    """Take ``LOCK_EX`` on ``fh``; fall back warn-once on unsupported FS.

    Single source of truth for the lock-or-fallback decision so
    ``append_event`` (per-call locking) and ``transaction`` (lock once,
    hold across many events) can't drift on which errno set counts as
    "filesystem unsupported." Other ``OSError``s propagate — including
    ``EINTR``, which PEP 475 auto-retries on CPython but a userspace
    mock must surface so the fallback boundary stays narrow.
    """

    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    except OSError as exc:
        if exc.errno not in _LOCK_UNSUPPORTED_ERRNOS:
            raise
        _warn_lock_fallback_once(journal_path, exc)


def _lock_holder_path(journal_path: Path) -> Path:
    """Sibling ``lock`` file next to the journal.

    Spec §Behavior "Claude-session manual hold" names this path: a
    one-line text marker the ``wiki lock`` CLI writes on ``acquire`` and
    deletes on ``release``. The kit treats it as advisory — the
    OS-level ``flock`` is the real lock; the holder file is what
    survives a process exit so a second ``wiki lock acquire`` can see
    who held it last.
    """

    return journal_path.parent / "lock"


def _write_holder_file(
    path: Path,
    *,
    by: str,
    reason: str | None,
    acquired_at: datetime,
) -> None:
    """Write the ``.wiki.journal/lock`` holder-file in the format step 5 expects.

    Lines, in order: ``<by>``, ``<iso-timestamp>``, and ``<reason>`` only
    when a reason was given. Two-line vs three-line lets step 5's
    parser distinguish "no reason recorded" from "empty-string reason"
    without a sentinel. The parent directory is the caller's
    responsibility (every caller in this module creates ``journal_path.parent``
    on entry; one ``mkdir`` is enough).
    """

    lines = [by, acquired_at.isoformat()]
    if reason is not None:
        lines.append(reason)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    When called from inside an open ``transaction()`` for the *same*
    journal (matched by resolved path), this function reuses the
    already-held fd instead of opening a new one: a multi-event
    operation takes ``LOCK_EX`` once on enter, not once per nested
    event (plan step 4 §Verification). The fsync still runs per call
    so durability stays per-event. Path comparison is on
    ``.resolve()`` so two ``Path`` spellings of the same file collapse
    to one held-fd identity.

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

    held = _HELD_FD.get()
    if held is not None and held.resolved_path == journal_path.resolve():
        # Inside an open transaction for this journal: reuse the held fd,
        # skip per-call open + flock. The outer transaction took LOCK_EX
        # once; re-flocking here would be a no-op at best (the kernel
        # allows re-locking from the same fd) and a wasted syscall at
        # worst. fsync stays per-event so durability matches the
        # unlocked path.
        held.fh.write(line)
        held.fh.flush()
        os.fsync(held.fh.fileno())
        return

    with journal_path.open("a", encoding="utf-8") as fh:
        _take_exclusive_lock(fh, journal_path)
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


@contextmanager
def transaction(
    journal_path: Path,
    by: str,
    reason: str | None = None,
    persist: bool = False,
) -> Iterator[None]:
    """Bracket a multi-event sequence with one ``LOCK_EX`` and one acquire/release pair.

    Spec §Behavior "happy path — multi-event operation": the operation
    runner enters this context manager, calls ``append_event`` N times
    inside the block, and the manager emits a ``LockAcquiredEvent`` on
    enter and a ``LockReleasedEvent`` on exit. While the block is open,
    nested ``append_event`` calls on this journal reuse the held fd
    (via :data:`_HELD_FD`) — the OS-level ``flock`` is non-recursive,
    so per-event re-locking would either no-op or risk deadlock; the
    ContextVar guard is the in-process invariant that keeps the bracket
    coherent.

    On exception inside the block: ``LockReleasedEvent`` is still
    appended (in ``finally``), the exception re-raises, and the lock
    releases when the fd closes. The pair-completeness invariant
    (§Invariants) holds except on a hard crash that bypasses Python's
    cleanup, which is what ``wiki doctor``'s stale-lock check exists
    to catch.

    ``persist=True`` is the plumbing for ``wiki lock acquire`` (plan
    step 5): on clean exit the fd is *stashed* in
    :data:`_PERSISTED_FDS` so it stays open until process exit (or
    until step 5 explicitly closes it via
    :func:`_release_persisted_fd`). Without the stash, the fd is a
    generator-frame local; once this function returns CPython would
    close it and the OS-level lock would die, violating spec
    §Behavior lines 127-128 ("future ``fcntl.flock`` attempts from
    other processes block until ``wiki lock release`` runs"). The
    ``.wiki.journal/lock`` holder file is written on enter so a second
    ``wiki lock acquire`` can read the holder name without parsing
    the journal. Exception inside a ``persist=True`` block rolls
    back: the holder file is deleted, ``LockReleasedEvent`` is
    emitted, and the fd closes — a half-acquired persist must not
    leave a phantom holder.

    Note on stale-holder reclaim: spec §Edge cases ("Lock held by a
    dead PID") names a flow where ``persist=True`` over a
    pre-existing holder file should append a
    ``LockReleasedEvent(by="wiki-doctor", reason="stale lock
    reclaimed")`` before its own acquire. That reclaim is step 5/6
    work (CLI orchestration + doctor surface); step 4 unconditionally
    overwrites the holder file as the plumbing path, leaving the
    higher-level reclaim audit to its proper home.

    Non-recursive: entering ``transaction`` while another is already
    active in this context raises ``RuntimeError``. The ``by`` and
    ``reason`` of a nested call would be silently discarded under any
    "reuse the outer fd" semantics; raising forces the caller to
    refactor rather than emit a half-bracketed journal.

    Cross-task / threaded callers: the ContextVar guard is per
    ``contextvars.Context``, so two asyncio tasks (or threads) that
    each ``copy_context().run(transaction, ...)`` won't see each
    other's held fd and the in-process re-entry guard above won't
    fire. The OS-level ``flock`` is the only remaining serializer,
    and its same-process semantics across distinct fds are
    platform-dependent (Linux ``fcntl.flock`` is per-OFD; macOS
    BSD-flock is per-file). The kit's current callers are CLI
    handlers — strictly serial. Future async / parallel runners must
    serialize at the caller; this contract will be tightened when
    such a runner ships.
    """

    if _HELD_FD.get() is not None:
        raise RuntimeError(
            "journal.transaction() is non-recursive: a transaction is already "
            "active in this context. fcntl.flock is non-recursive at the OS "
            "level and nested entries would have ambiguous "
            "LockAcquiredEvent/LockReleasedEvent semantics."
        )

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = journal_path.resolve()

    # Same-process ``persist=True`` re-entry on the same journal would
    # silently leak the prior stashed fd (dict-overwrite) and then
    # deadlock on its own ``flock`` call (BSD-flock is exclusive across
    # all fds-to-same-file regardless of process). Refuse loudly so a
    # programmatic caller — step 5 once it lands, or a future
    # runner — sees the problem at the boundary rather than a hung
    # process. The released-then-reacquired flow goes through
    # ``_release_persisted_fd`` first.
    if persist and resolved in _PERSISTED_FDS:
        raise RuntimeError(
            f"transaction(persist=True) re-entered for {resolved} without an "
            f"intervening _release_persisted_fd; would leak the prior fd and "
            f"deadlock on flock(LOCK_EX)"
        )
    holder_path = _lock_holder_path(journal_path)
    enter_time = datetime.now(tz=UTC)

    fh = journal_path.open("a", encoding="utf-8")
    token: Token[_HeldFd | None] | None = None
    holder_written = False
    detach = False  # set on persist=True clean exit so finally skips cleanup
    try:
        _take_exclusive_lock(fh, journal_path)
        if persist:
            _write_holder_file(
                holder_path,
                by=by,
                reason=reason,
                acquired_at=enter_time,
            )
            holder_written = True
        token = _HELD_FD.set(_HeldFd(resolved_path=resolved, fh=fh))
        # ContextVar is set, so this append reuses ``fh`` (no second flock).
        # If the acquire-event append itself fails (e.g. fsync EIO), emit a
        # best-effort release event before re-raising so the journal doesn't
        # carry a lone ``LockAcquiredEvent`` for the stale-lock check to
        # flag on next ``wiki doctor`` run.
        try:
            append_event(
                journal_path,
                LockAcquiredEvent(timestamp=enter_time, by=by, reason=reason),
            )
        except BaseException:
            try:
                append_event(
                    journal_path,
                    LockReleasedEvent(timestamp=datetime.now(tz=UTC), by=by),
                )
            except Exception:
                _logger.exception("LockReleasedEvent append failed after a failed acquire append")
            raise
        try:
            yield
        except BaseException:
            # Body raised. Emit LockReleasedEvent best-effort under the
            # still-held lock, then re-raise. The outer finally handles
            # ContextVar reset, holder-file cleanup, and fd close.
            try:
                append_event(
                    journal_path,
                    LockReleasedEvent(timestamp=datetime.now(tz=UTC), by=by),
                )
            except Exception:
                # Don't mask the body's exception. The release event
                # failing is itself surfaced via the stale-lock check on
                # next ``wiki doctor`` run; logging here gives the
                # operator a pointer.
                _logger.exception("LockReleasedEvent append failed during transaction unwind")
            raise
        else:
            if persist:
                # Persist mode, clean exit: stash the fd module-level so
                # it survives past this generator's return (otherwise the
                # local goes out of scope, refcount drops to zero, and
                # CPython closes the fd — releasing the OS lock the
                # spec promises will outlive ``__exit__``). Reset only
                # the ContextVar so a subsequent ``append_event`` in this
                # context returns to per-call locking.
                _PERSISTED_FDS[resolved] = fh
                detach = True
            else:
                # Same best-effort contract as the body-exception and
                # failed-acquire paths above: a release-event append that
                # fails (e.g. fsync EIO) is logged, not raised. The three
                # paths share one rule — release is best-effort, the
                # stale-lock doctor check catches what gets lost. Raising
                # here would surface a transient EIO to a caller whose
                # body succeeded, conflating "your work failed" with
                # "the audit trail's tail is incomplete."
                try:
                    append_event(
                        journal_path,
                        LockReleasedEvent(timestamp=datetime.now(tz=UTC), by=by),
                    )
                except Exception:
                    _logger.exception("LockReleasedEvent append failed on clean transaction exit")
    finally:
        if token is not None:
            _HELD_FD.reset(token)
        if not detach:
            if holder_written:
                try:
                    holder_path.unlink()
                except FileNotFoundError:
                    # Already gone — desired end-state.
                    pass
                except OSError as exc:
                    # Permissions, read-only FS, etc. We don't re-raise
                    # (that would mask a body exception currently
                    # unwinding) but operators need to know — the holder
                    # file accumulates across runs and stale-lock
                    # detection will flag the wrong holder name on next
                    # ``wiki doctor`` run. Warn instead of debug so the
                    # signal survives default log levels.
                    errno_value = exc.errno if exc.errno is not None else 0
                    _logger.warning(
                        "could not remove holder file %s (%s, errno=%d); "
                        "next stale-lock check may see a phantom holder",
                        holder_path,
                        errno.errorcode.get(errno_value, "unknown"),
                        errno_value,
                    )
            fh.close()


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
