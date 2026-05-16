"""The single sanctioned write path for files inside a user vault.

ADR-0004 names ``safe_write`` as the only function in the kit that calls
``Path.write_text`` against a vault path. It is drift-aware: every write
goes through a hash-compare against the most recent ``PageWrite`` event
for the same path in the journal. On a match (or when there is no prior
event for the path), it writes the file directly and appends a
``PageWrite`` event. On a mismatch, it writes a ``<path>.proposed``
sidecar instead, appends a ``PageProposal`` event, and adds a
``\\.proposed$`` pattern to the vault's ``.obsidianignore`` so Obsidian
does not index conflict files. The user's vault-side ``wiki-conflict``
skill then helps them merge.

``resolve_proposal`` is the documented bypass added by the ADR-0004
2026-05-15 revision: after the user has reviewed both versions via the
``wiki-conflict`` skill, it writes the confirmed merge directly,
deletes the sidecar, and emits a ``PageWrite`` (new baseline) plus a
``PageConflictResolved`` (audit). Nothing else in the kit bypasses the
drift check.

``WriteResult`` is a plain ``enum.Enum`` per ADR-0005: it doesn't cross
disk, so Pydantic would buy nothing here.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    PageConflictResolvedEvent,
    PageProposalEvent,
    PageWriteEvent,
)

OBSIDIAN_IGNORE_PROPOSED_PATTERN = r"\.proposed$"


class WriteResult(Enum):
    """Whether ``safe_write`` wrote the target file or a proposal sidecar."""

    WRITTEN = "written"
    PROPOSAL = "proposal"


def safe_write(
    path: Path,
    content: str,
    by: str,
    journal_path: Path,
) -> WriteResult:
    """Write ``content`` to ``path``, falling through to a proposal on drift.

    ``path`` must be inside the vault rooted at ``journal_path.parent.parent``
    (the canonical layout ADR-0002 names). Paths are journaled relative to
    that root so a moved or renamed vault keeps its history intact.

    ``by`` is the primitive or operation name responsible for the write —
    ``"core"``, ``"meeting"``, ``"weekly-digest"``, etc. It surfaces in
    ``wiki journal tail`` so a user (or Claude) can attribute every line.
    """

    vault_root = _vault_root(journal_path)
    abs_path = path if path.is_absolute() else (vault_root / path)
    relative_path = _relative_to_vault(abs_path, vault_root)

    new_bytes = content.encode("utf-8")
    new_hash = _hash(new_bytes)
    on_disk_hash = _hash(abs_path.read_bytes()) if abs_path.exists() else None
    baseline_hash = _baseline_hash(journal_path, relative_path)
    now = datetime.now(UTC)

    if baseline_hash is None or on_disk_hash == baseline_hash:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(new_bytes)
        append_event(
            journal_path,
            PageWriteEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
        )
        return WriteResult.WRITTEN

    proposed_abs = abs_path.with_name(abs_path.name + ".proposed")
    proposed_abs.parent.mkdir(parents=True, exist_ok=True)
    proposed_abs.write_bytes(new_bytes)
    append_event(
        journal_path,
        PageProposalEvent(
            timestamp=now,
            by=by,
            path=relative_path,
            proposed_path=_relative_to_vault(proposed_abs, vault_root),
            hash=new_hash,
        ),
    )
    _ensure_obsidianignore(vault_root)
    return WriteResult.PROPOSAL


def resolve_proposal(
    path: Path,
    content: str,
    by: str,
    journal_path: Path,
) -> None:
    """Commit a user-mediated merge — the documented ``safe_write`` bypass.

    The vault-side ``wiki-conflict`` skill calls this after helping the
    user reconcile a ``.proposed`` sidecar with their on-disk edits.
    ``content`` is the user's confirmed final version, which may be the
    sidecar's content, the user's edits, or a third merged version —
    ``resolve_proposal`` doesn't care which.

    Writes ``content`` directly to ``path`` (bypassing the drift check
    that ``safe_write`` enforces, per ADR-0004 §Mechanics step 6),
    deletes ``<path>.proposed`` if present, and appends two journal
    events: a ``PageWrite`` with the merged hash (the new baseline,
    so subsequent ``safe_write`` calls see no drift) and a
    ``PageConflictResolved`` for audit.
    """

    vault_root = _vault_root(journal_path)
    abs_path = path if path.is_absolute() else (vault_root / path)
    relative_path = _relative_to_vault(abs_path, vault_root)

    new_bytes = content.encode("utf-8")
    new_hash = _hash(new_bytes)
    now = datetime.now(UTC)

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(new_bytes)

    sidecar = abs_path.with_name(abs_path.name + ".proposed")
    if sidecar.exists():
        sidecar.unlink()

    append_event(
        journal_path,
        PageWriteEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
    )
    append_event(
        journal_path,
        PageConflictResolvedEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
    )


def _vault_root(journal_path: Path) -> Path:
    # Canonical layout is `<vault_root>/.wiki.journal/journal.jsonl`.
    return journal_path.parent.parent


def _relative_to_vault(abs_path: Path, vault_root: Path) -> str:
    return abs_path.relative_to(vault_root).as_posix()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _baseline_hash(journal_path: Path, relative_path: str) -> str | None:
    """Return the hash of the most recent ``PageWrite`` event for the path.

    ``PageConflictResolved`` is audit-only here; ``resolve_proposal``
    re-establishes the baseline by emitting its own ``PageWrite``
    alongside the audit event (ADR-0004 §Mechanics step 6).
    """

    for event in reversed(read_events(journal_path)):
        if isinstance(event, PageWriteEvent) and event.path == relative_path:
            return event.hash
    return None


def _ensure_obsidianignore(vault_root: Path) -> None:
    ignore = vault_root / ".obsidianignore"
    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if OBSIDIAN_IGNORE_PROPOSED_PATTERN in existing.splitlines():
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    ignore.write_text(existing + OBSIDIAN_IGNORE_PROPOSED_PATTERN + "\n", encoding="utf-8")
