"""Append-only journal at ``.wiki.journal/journal.jsonl``.

ADR-0002 names this module the source of truth for vault state. Three
operations cover its surface:

- ``append_event`` validates a Pydantic ``Event`` and appends one JSON line.
- ``read_events`` parses every line through the discriminated ``Event``
  union and raises ``JournalCorruptError(line=N)`` on the first malformed
  line. We fail loudly — corrupted state is the user's signal.
- ``replay_state`` walks an ordered iterable of events and returns the
  derived ``VaultState`` (installed primitives, latest page writes per
  path, outstanding proposals, ingested sources, most recent operation
  per name, research history).

The module depends only on ``models`` and ``errors`` (see
``docs/architecture/overview.md``).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
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

    After the line is written, ``fh.flush()`` drains Python's buffer and
    ``os.fsync()`` forces the kernel to commit the journal file to disk —
    so a crash after ``append_event`` returns cannot lose the line
    (``docs/specs/journal-locking/spec.md`` §Durability, qB1). An
    ``fsync`` failure (EIO) propagates as ``OSError`` to the caller.
    ADR-0002's "Concurrent writers are not safe" note will be amended to
    point at this spec in plan step 7.
    """

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    line = _EVENT_ADAPTER.dump_json(event).decode() + "\n"
    with journal_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


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
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise JournalCorruptError(
                    line=line_number, reason=f"invalid JSON: {exc.msg}"
                ) from exc
            try:
                events.append(_EVENT_ADAPTER.validate_python(payload))
            except PydanticValidationError as exc:
                raise JournalCorruptError(line=line_number, reason=_summarize(exc)) from exc

    return events


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
