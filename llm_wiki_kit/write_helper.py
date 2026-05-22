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
import os
import tempfile
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from llm_wiki_kit import journal, managed_regions
from llm_wiki_kit.errors import ManagedRegionError, WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    Event,
    ManagedRegionAdoptedEvent,
    ManagedRegionWriteEvent,
    PageAdoptedEvent,
    PageConflictResolvedEvent,
    PageProposalEvent,
    PageWriteEvent,
)

OBSIDIAN_IGNORE_PROPOSED_PATTERN = r"\.proposed$"

# Load-bearing pin for the ``.obsidianignore`` non-journaled bypass.
# Anywhere that touches ``_ensure_obsidianignore`` cites this constant by
# name; ``grep OBSIDIANIGNORE_BYPASS_DOC`` surfaces every dependency.
# A paraphrase of the docstring no longer silently shifts the contract —
# only changing this constant's value does, and that's grep-discoverable.
# See ``docs/specs/safe-write-ordering/spec.md`` §Non-goals "Why
# .obsidianignore is not journaled" and ADR-0004 §Negative.
OBSIDIANIGNORE_BYPASS_DOC = "docs/specs/safe-write-ordering/spec.md"


def _now() -> datetime:
    """Wall-clock seam.

    Mirrors ``doctor._now``. Tests monkeypatch ``write_helper._now`` to
    pin the timestamp recompute in the adopt fast-path (spec §Behavior
    "Adopt fast-path" step 3); production callers never override it.
    """

    return datetime.now(UTC)


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

    Event-before-disk: the journal entry (``PageWriteEvent`` on the direct
    path, ``PageProposalEvent`` on drift) is appended and ``fsync``'d
    before the target file or sidecar is opened for writing. A crash
    between the event and the disk write leaves a recoverable gap that
    ``wiki doctor`` surfaces as ``missing`` (event durable, file absent)
    or ``page-drift`` (event durable, on-disk hash diverges). See
    ``docs/specs/safe-write-ordering/spec.md`` for the full contract.

    Five branches by ``(latest_kind, baseline_hash, file_present, on_disk_hash)``:

    1. **Adopt-match no-rewrite** — latest baseline is
       :class:`PageAdoptedEvent` and ``new_hash == baseline_hash ==
       on_disk_hash``. Supersedes the adopt baseline with a fresh
       :class:`PageWriteEvent` and does NOT touch the file (inode +
       mtime preserved). ADR-0008 §Decision sub-choice 3 disjunct 1.
    2. **Adopt-differ proposal** — latest baseline is
       :class:`PageAdoptedEvent` and the kit's content differs from
       the adopted baseline (or the on-disk bytes have moved off
       baseline since the adopt walk). Routes to the proposal branch
       even when ``on_disk_hash == baseline_hash`` — the silent
       overwrite this disjunct exists to prevent. ADR-0008 §Decision
       sub-choice 3 disjunct 2.
    3. **Direct write** — no history and no file (fresh path), or
       history with a matching on-disk hash (no drift), or history
       with the file absent (crash-recovery retry). Suppressed when
       the latest baseline is an adopt event (see disjunct 2).
    4. **Adopt fast-path** — no history, file exists, bytes already
       match. Re-reads the file once to shrink the adopt-then-not
       race window, then journals the baseline without touching the
       file (preserves inode for Obsidian / inotify consumers). Only
       reachable when no journaled baseline exists (otherwise
       ``no_history`` is False); the journaled-adopt analogue is
       covered by disjunct 1 above.
    5. **Proposal** — everything else: a user-edited file diverging
       from the journaled baseline (classic drift), or a user file
       the kit has never seen whose bytes differ from the kit's
       proposed content (the qC6 case the spec inverted), or the
       fall-through from disjunct 2.
    """

    vault_root = _vault_root(journal_path)
    abs_path = path if path.is_absolute() else (vault_root / path)
    relative_path = _relative_to_vault(abs_path, vault_root)

    new_bytes = content.encode("utf-8")
    new_hash = _hash(new_bytes)
    on_disk_hash = _hash(abs_path.read_bytes()) if abs_path.exists() else None
    # One journal walk for both the latest baseline class AND its hash:
    # outside the cache scope, every ``_read_events_cached`` call hits
    # disk, so two separate walks would double the read count per
    # ``safe_write`` and break the qC4 cache-scope contract pin in
    # ``test_safe_write_outside_cache_scope_unchanged``.
    latest_kind, baseline_hash = _latest_page_baseline(journal_path, relative_path)
    # Single timestamp by design — direct-write and proposal are one
    # logical decision at call entry. Only the adopt fast-path
    # recomputes (see below), because the re-read shrinks the race
    # window and the timestamp should reflect the *adoption* decision.
    now = _now()

    no_history = baseline_hash is None
    file_present = abs_path.exists()
    bytes_match = on_disk_hash == new_hash

    # ADR-0008 §Decision sub-choice 3 disjunct 1: adopt-match no-rewrite.
    # When the latest baseline event for the path is a PageAdoptedEvent
    # and the kit's content matches both the adopted bytes AND the
    # current on-disk bytes, supersede the adopt baseline with a fresh
    # PageWriteEvent and leave the file alone (inode + mtime preserved).
    if latest_kind == "adopted" and new_hash == baseline_hash and on_disk_hash == baseline_hash:
        append_event(
            journal_path,
            PageWriteEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
        )
        return WriteResult.WRITTEN

    # ADR-0008 §Decision sub-choice 3 disjunct 2: adopt-differ proposal.
    # When the latest baseline is a PageAdoptedEvent and the kit's
    # content differs from the adopted baseline (or the user has edited
    # on-disk away from the baseline since the walk), force the proposal
    # branch — the existing "no drift" direct-write disjunct below would
    # otherwise silently overwrite the user's adopted bytes.
    adopt_force_proposal = latest_kind == "adopted"

    # ``adopt_force_proposal`` suppresses every disjunct below for an
    # adopt-baseline path; the crash-recovery sub-case (file_absent +
    # journaled baseline) does NOT fire when the baseline is an adopt
    # event. Once the kit has claimed user bytes as a baseline, a
    # subsequent disappearance is treated as drift, not as fresh-write
    # recovery. This is the conservative read of ADR-0008 §Decision
    # sub-choice 3 disjunct 2 ("any on_disk_hash") plus the
    # wiki-init-adopt spec §Edge cases "TOCTOU between adoption walk
    # and render-phase writes" — both consistent with the no-silent-
    # overwrites invariant. Pinned by
    # ``test_safe_write_after_page_adopted_file_absent_routes_to_proposal``.
    direct_write = not adopt_force_proposal and (
        (no_history and not file_present)  # fresh path
        or (not no_history and on_disk_hash == baseline_hash)  # no drift
        or (not no_history and not file_present)  # crash-recovery (spec §Edge cases sub-case 1)
    )
    if direct_write:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        append_event(
            journal_path,
            PageWriteEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
        )
        abs_path.write_bytes(new_bytes)
        return WriteResult.WRITTEN

    if no_history and file_present and bytes_match:
        # Adopt fast-path. Re-read to shrink the race: an editor that
        # wrote between the first ``read_bytes`` above and this point
        # would otherwise let us journal a hash no longer on disk.
        # If the re-read diverges, abandon the fast-path — control
        # falls through to the proposal branch below, which uses the
        # kit's ``new_hash`` (no predicate re-evaluation; the top-of-
        # function ``on_disk_hash`` snapshot is stale by construction).
        # See spec §Behavior "Adopt fast-path" step 2.
        #
        # Decision pinned by ADR-0008 §Decision sub-choice 4: rejected
        # a ``reason: Literal["fresh","adopt","recovery"]`` field on
        # ``PageWriteEvent`` in favor of dedicated ``PageAdoptedEvent``
        # / ``ManagedRegionAdoptedEvent`` classes. See
        # ``docs/specs/wiki-init-adopt/spec.md`` for the shipped contract.
        reread_hash = _hash(abs_path.read_bytes())
        if reread_hash == new_hash:
            # Spec §Behavior "Adopt fast-path" step 3: recompute ``now``
            # so the journaled timestamp reflects the adoption decision,
            # not the call entry.
            append_event(
                journal_path,
                PageWriteEvent(
                    timestamp=_now(),
                    by=by,
                    path=relative_path,
                    hash=new_hash,
                ),
            )
            return WriteResult.WRITTEN

    proposed_abs = abs_path.with_name(abs_path.name + ".proposed")
    proposed_abs.parent.mkdir(parents=True, exist_ok=True)
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
    proposed_abs.write_bytes(new_bytes)
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

    Event-before-disk: every journal event this function emits — the
    ``PageWriteEvent``, the ``PageConflictResolvedEvent``, and any
    re-baseline ``ManagedRegionWriteEvent``s for known regions — is
    appended and ``fsync``'d *before* the target file is rewritten and
    the sidecar is deleted. A crash between the events and the disk
    write surfaces via ``wiki doctor`` as ``page-drift`` or ``missing``;
    re-running ``wiki-conflict`` reads both ``path`` and ``path.proposed``
    (the sidecar is still on disk) and produces an idempotent retry.
    See ``docs/specs/safe-write-ordering/spec.md`` §Edge cases sub-case 3.
    """

    vault_root = _vault_root(journal_path)
    abs_path = path if path.is_absolute() else (vault_root / path)
    relative_path = _relative_to_vault(abs_path, vault_root)

    new_bytes = content.encode("utf-8")
    new_hash = _hash(new_bytes)
    now = _now()

    append_event(
        journal_path,
        PageWriteEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
    )
    append_event(
        journal_path,
        PageConflictResolvedEvent(timestamp=now, by=by, path=relative_path, hash=new_hash),
    )

    # Retro-review #F-B1: if this file has managed-region history, the
    # ``PageWriteEvent`` alone doesn't re-baseline ``safe_write_region``'s
    # region-scoped lookup. Emit a fresh ``ManagedRegionWriteEvent`` per
    # known region so the next ``safe_write_region`` writes in place
    # instead of re-proposing forever (ADR-0004 §Mechanics step 6 for
    # managed regions). The region events also land *before* the disk
    # write per the event-before-disk invariant.
    known_regions = _known_regions_for_file(journal_path, relative_path)
    if known_regions:
        try:
            resolved_regions = managed_regions.parse(content)
        except ManagedRegionError:
            # The user's resolution destroyed markers. Region writes are
            # now broken for this file; surfacing happens via
            # ``safe_write_region`` raising on the next attempt. Don't
            # silently invent ``ManagedRegionWriteEvent``s for missing
            # regions. The page-level events above are still durable;
            # the disk write below still has to land so the user sees
            # their merged content.
            resolved_regions = None
        if resolved_regions is not None:
            for region in known_regions:
                body = resolved_regions.get(region)
                if body is None:
                    continue
                # Canonicalize before hashing — keeps the resolve-path
                # baseline hash in lockstep with what
                # ``safe_write_region`` recomputes on the next aggregator
                # pass. Without this, a re-aggregate after resolve would
                # see spurious drift the same way Task 19's
                # multi-contributor aggregation would have.
                append_event(
                    journal_path,
                    ManagedRegionWriteEvent(
                        timestamp=now,
                        by=by,
                        file=relative_path,
                        region=region,
                        content_hash=_hash(managed_regions.canonical_region_body(body)),
                    ),
                )

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(new_bytes)

    sidecar = abs_path.with_name(abs_path.name + ".proposed")
    if sidecar.exists():
        sidecar.unlink()


def _read_events_cached(journal_path: Path) -> list[Event]:
    """Read events, consulting the active ``JournalReader`` if one is installed.

    Falls through to ``read_events(journal_path)`` when no cache scope
    is active (per `journal.use_journal_cache`) or when the active
    reader tracks a different journal. The fall-through path keeps
    today's "always fresh read" semantics for callers outside the
    scope — tests calling ``safe_write`` directly retain identical
    behavior. See ``docs/specs/journal-reader-cache/spec.md``.
    """

    reader = journal._CURRENT_READER.get()
    if reader is not None and reader.journal_path == journal_path.resolve():
        return reader.events()
    # Route through ``journal.read_events`` (not the import-time binding)
    # so a test that monkeypatches ``journal.read_events`` still sees
    # the call here. The two paths must agree on observability.
    return journal.read_events(journal_path)


def _known_regions_for_file(journal_path: Path, relative_file: str) -> list[str]:
    """Return the set of region ids ever journaled for ``relative_file``.

    Walks ``ManagedRegionWriteEvent`` AND ``ManagedRegionAdoptedEvent``
    (ADR-0008 §Decision sub-choice 3). Adoption seeds a region just
    like a write, so a host whose only history is adopt events still
    surfaces its regions here — without this, ``resolve_proposal``
    against an adopted-then-proposed host emits zero region writes and
    the region-level sticky-adopt baselines never clear, looping on
    every subsequent aggregator pass (spec AC16b).

    Preserves first-seen order so the emitted ``ManagedRegionWriteEvent``
    sequence is stable across runs.
    """

    seen: list[str] = []
    for event in _read_events_cached(journal_path):
        if (
            isinstance(event, ManagedRegionWriteEvent | ManagedRegionAdoptedEvent)
            and event.file == relative_file
            and event.region not in seen
        ):
            seen.append(event.region)
    return seen


def safe_write_region(
    file_path: Path,
    region_id: str,
    new_content: str,
    by: str,
    journal_path: Path,
) -> WriteResult:
    """Write ``new_content`` into a kit-owned managed region of a shared file.

    ADR-0003 names this as the write path for shared infra files like
    ``AGENTS.md``, ``frontmatter.schema.yaml``, ``.gitignore``, and
    ``.claude/research-providers.yaml`` — files multiple primitives
    contribute to via `<!-- BEGIN MANAGED: id -->` (or `# BEGIN MANAGED: id`)
    delimiters.

    Drift detection is region-scoped, not file-scoped. The kit looks up
    the most recent ``managed_region.write`` event for ``(file, region)``
    and compares its ``content_hash`` to the hash of the region's current
    on-disk body. On match (or with no prior event), the region is
    rewritten in place, the rest of the file is preserved verbatim
    (including user edits to unmanaged content — which are invisible to
    the kit by design, per ADR-0003 §Decision), and a
    ``ManagedRegionWriteEvent`` is appended.

    Event-before-disk: the ``ManagedRegionWriteEvent`` (happy path) or
    ``PageProposalEvent`` (drift path) is appended and ``fsync``'d
    before the target file is rewritten — per
    ``docs/specs/safe-write-ordering/spec.md``. A crash between the
    event and the disk write surfaces via ``wiki doctor`` as
    ``managed-region-drift``; recovery routes through the proposal flow
    (see spec §Edge cases sub-case 2). The no-prior-event-direct-write
    case is preserved by design — the install pipeline's
    ``aggregate_region_contributions`` depends on it (spec §Non-goals
    "Why qC6 is page-scoped").

    On intra-region drift, the kit doesn't touch ``file_path``. Instead
    it writes ``<file_path>.proposed`` containing the file as it would
    look after applying the region update (so the unmanaged user edits
    flow through, but the user can inspect just the region delta), emits
    a ``PageProposalEvent`` for the shared file, and updates
    ``.obsidianignore``. The user resolves via the vault-side
    ``wiki-conflict`` skill and the same
    :func:`resolve_proposal` bypass as page proposals.

    Raises :class:`FileNotFoundError` if ``file_path`` does not exist —
    shared files are seeded by ``wiki init`` and the kit relies on their
    presence to find the region markers. Raises
    :class:`llm_wiki_kit.errors.ManagedRegionError` if ``region_id`` is
    not present in the file.
    """

    vault_root = _vault_root(journal_path)
    abs_path = file_path if file_path.is_absolute() else (vault_root / file_path)
    relative_path = _relative_to_vault(abs_path, vault_root)

    on_disk_text = abs_path.read_text(encoding="utf-8")
    current_regions = managed_regions.parse(on_disk_text)
    if region_id not in current_regions:
        raise ManagedRegionError(f"file '{relative_path}' has no managed region '{region_id}'")

    # ``_normalise_snippet`` writes each contributor's snippet with a
    # trailing newline; ``managed_regions.parse`` strips it when
    # reading back (the body is "between markers", terminator excluded).
    # The two forms differ by exactly one byte for any non-empty body,
    # which would cause a spurious drift event the first time a second
    # contributor lands in the same region. Canonicalize both sides
    # before hashing — append a single trailing newline if non-empty,
    # matching the form ``_normalise_snippet`` writes. Pre-existing
    # ``ManagedRegionWriteEvent`` baseline hashes were computed against
    # the with-trailing-newline form (the aggregator's ``new_content``
    # is already in that form), so this canonicalization keeps the
    # baseline comparison valid for Task 18 vaults.
    current_region_hash = _hash(managed_regions.canonical_region_body(current_regions[region_id]))
    # One journal walk for both the latest region baseline class AND its
    # hash — mirrors the page-level pin in ``safe_write``; outside the
    # cache scope, two walks would double the read count per call and
    # break the cache-scope contract for ``safe_write_region``.
    latest_kind, baseline_hash = _latest_managed_region_baseline(
        journal_path, relative_path, region_id
    )
    new_region_hash = _hash(managed_regions.canonical_region_body(new_content))
    rewritten = managed_regions.update(on_disk_text, region_id, new_content)
    now = _now()

    # ADR-0008 §Decision sub-choice 3 (region equivalent): adopt-match
    # no-rewrite. When the latest baseline for ``(file, region)`` is a
    # ManagedRegionAdoptedEvent and the kit's region body matches both
    # the adopt baseline AND the current on-disk region body, supersede
    # the adopt baseline with a fresh ManagedRegionWriteEvent and leave
    # the host file's bytes alone — preserves unmanaged user content
    # byte-for-byte and the host's inode + mtime.
    if (
        latest_kind == "adopted"
        and new_region_hash == baseline_hash
        and current_region_hash == baseline_hash
    ):
        append_event(
            journal_path,
            ManagedRegionWriteEvent(
                timestamp=now,
                by=by,
                file=relative_path,
                region=region_id,
                content_hash=new_region_hash,
            ),
        )
        return WriteResult.WRITTEN

    # ADR-0008 §Decision sub-choice 3 (region equivalent): adopt-differ
    # proposal. When the latest baseline is a
    # ManagedRegionAdoptedEvent and the kit's body differs (or the
    # on-disk body has moved off baseline since the walk), force the
    # proposal branch — the existing "no prior event OR current matches
    # baseline" direct-write disjunct below would otherwise silently
    # overwrite the user's adopted region body.
    adopt_force_proposal = latest_kind == "adopted"

    if not adopt_force_proposal and (baseline_hash is None or current_region_hash == baseline_hash):
        append_event(
            journal_path,
            ManagedRegionWriteEvent(
                timestamp=now,
                by=by,
                file=relative_path,
                region=region_id,
                content_hash=new_region_hash,
            ),
        )
        abs_path.write_text(rewritten, encoding="utf-8")
        return WriteResult.WRITTEN

    proposed_abs = abs_path.with_name(abs_path.name + ".proposed")
    proposed_abs.parent.mkdir(parents=True, exist_ok=True)
    append_event(
        journal_path,
        PageProposalEvent(
            timestamp=now,
            by=by,
            path=relative_path,
            proposed_path=_relative_to_vault(proposed_abs, vault_root),
            hash=_hash(rewritten.encode("utf-8")),
        ),
    )
    proposed_abs.write_text(rewritten, encoding="utf-8")
    _ensure_obsidianignore(vault_root)
    return WriteResult.PROPOSAL


def _managed_region_baseline_hash(
    journal_path: Path, relative_file: str, region_id: str
) -> str | None:
    """Return the latest region-level baseline ``content_hash`` for ``(relative_file, region_id)``.

    Delegates to :func:`_latest_managed_region_baseline` so the
    walk-both-classes invariant (ADR-0008 §Decision sub-choice 3) is
    single-sourced; PR-A's tests for this helper now pin the shared
    walker indirectly. Adoption seeds a region baseline just like a
    write, so an aggregator pass over a host whose only history is an
    adopt answers "no drift" when the canonicalised on-disk region
    body still matches.
    """

    return _latest_managed_region_baseline(journal_path, relative_file, region_id)[1]


def _vault_root(journal_path: Path) -> Path:
    # Canonical layout is `<vault_root>/.wiki.journal/journal.jsonl`.
    return journal_path.parent.parent


def _relative_to_vault(abs_path: Path, vault_root: Path) -> str:
    """Return ``abs_path`` as a POSIX path relative to ``vault_root``.

    Resolves both sides so ``..`` segments and symlinks point at the
    same canonical file (retro-review qC9). Drift detection keys off
    the journaled vault-relative path; a symlinked-in route would
    otherwise journal under one key and check under another, silently
    splitting baselines.

    Rejects symlink escape: a path that lives inside ``vault_root``
    lexically but resolves to a target outside it raises
    :class:`WikiError`. The journal must not record a path that
    escapes the vault — the next ``safe_write`` against the same
    lexical path would diverge from the resolved target.

    Bare ``ValueError`` from :meth:`Path.relative_to` is wrapped as
    :class:`WikiError` (retro-review qB3) so the CLI boundary renders
    one line instead of a Python traceback, per ADR-0005.
    """

    resolved_path = abs_path.resolve()
    resolved_root = vault_root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        # Include both lexical and resolved forms when they differ —
        # the resolved path is the actionable detail in the symlink-
        # escape case ("but `linked/leaked.md` is under `vault/`!").
        if resolved_path != abs_path or resolved_root != vault_root:
            detail = (
                f"path '{abs_path}' resolves to '{resolved_path}', "
                f"which is not inside the vault rooted at '{vault_root}' "
                f"(resolved: '{resolved_root}')"
            )
        else:
            detail = f"path '{abs_path}' is not inside the vault rooted at '{vault_root}'"
        raise WikiError(detail) from exc


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _latest_page_baseline(
    journal_path: Path, relative_path: str
) -> tuple[Literal["write", "adopted", "none"], str | None]:
    """Return ``(kind, hash)`` of the latest page-level baseline event for ``relative_path``.

    Single walk over ``reversed(_read_events_cached(journal_path))``:
    on the first :class:`PageWriteEvent` whose path matches, returns
    ``("write", event.hash)``; on the first :class:`PageAdoptedEvent`
    whose path matches, returns ``("adopted", event.hash)``; otherwise
    ``("none", None)``.

    Single source of truth for the walk-both-classes invariant
    (ADR-0008 §Decision sub-choice 3). ``safe_write`` calls this once
    per invocation and uses the kind for predicate dispatch and the
    hash for drift comparison from one read, satisfying the
    once-per-call read budget pinned by
    ``test_safe_write_outside_cache_scope_unchanged``.
    :func:`_latest_baseline_event_kind` (the ADR-named API) and
    :func:`_baseline_hash` (retained for PR-A's test-contract surface)
    both delegate here so a future change to "which event classes count
    as a baseline" lands in one place.

    ``PageConflictResolvedEvent`` is audit-only and never returned
    here; ``resolve_proposal`` emits a fresh :class:`PageWriteEvent`
    alongside the audit event so the next ``safe_write`` call sees
    ``"write"``, clearing any sticky-adopt state (spec AC16).
    """

    for event in reversed(_read_events_cached(journal_path)):
        if isinstance(event, PageWriteEvent) and event.path == relative_path:
            return "write", event.hash
        if isinstance(event, PageAdoptedEvent) and event.path == relative_path:
            return "adopted", event.hash
    return "none", None


def _latest_baseline_event_kind(
    journal_path: Path, relative_path: str
) -> Literal["write", "adopted", "none"]:
    """Return the discriminator of the latest page-level baseline event for ``relative_path``.

    Thin wrapper around :func:`_latest_page_baseline` — exists so the
    ADR-0008 §Decision sub-choice 3 contract ("dispatch on the literal
    returned by ``_latest_baseline_event_kind``") names a function with
    that signature. ``safe_write`` calls :func:`_latest_page_baseline`
    directly so the single walk also yields the baseline hash without
    a second journal read.
    """

    return _latest_page_baseline(journal_path, relative_path)[0]


def _latest_managed_region_baseline(
    journal_path: Path, relative_file: str, region_id: str
) -> tuple[Literal["write", "adopted", "none"], str | None]:
    """Return ``(kind, hash)`` of the latest region-level baseline event.

    Region-scoped equivalent of :func:`_latest_page_baseline`. Same
    single-walk-shares-with-hash-lookup rationale; the qC4 cache-scope
    contract for ``safe_write_region`` would otherwise see twice the
    reads per call.
    """

    for event in reversed(_read_events_cached(journal_path)):
        if (
            isinstance(event, ManagedRegionWriteEvent)
            and event.file == relative_file
            and event.region == region_id
        ):
            return "write", event.content_hash
        if (
            isinstance(event, ManagedRegionAdoptedEvent)
            and event.file == relative_file
            and event.region == region_id
        ):
            return "adopted", event.content_hash
    return "none", None


def _latest_managed_region_event_kind(
    journal_path: Path, relative_file: str, region_id: str
) -> Literal["write", "adopted", "none"]:
    """Return the discriminator of the latest region-level baseline event.

    Thin wrapper around :func:`_latest_managed_region_baseline` — same
    rationale as :func:`_latest_baseline_event_kind` versus
    :func:`_latest_page_baseline`.
    """

    return _latest_managed_region_baseline(journal_path, relative_file, region_id)[0]


def _baseline_hash(journal_path: Path, relative_path: str) -> str | None:
    """Return the hash of the most recent page-level baseline event for ``relative_path``.

    Delegates to :func:`_latest_page_baseline` so the walk-both-classes
    invariant (ADR-0008 §Decision sub-choice 3) is single-sourced.
    Adoption seeds a baseline just like a write, so a journal whose
    latest event for the path is an adopt answers "no drift" for
    byte-identical on-disk content. ``PageConflictResolvedEvent``
    remains audit-only here; ``resolve_proposal`` re-establishes the
    baseline by emitting its own ``PageWriteEvent`` alongside the audit
    event (ADR-0004 §Mechanics step 6).

    Returning the hash regardless of class is correct because PR-A's
    contract is just "what hash should I compare new content against?"
    The adopt-aware predicate landed in PR-B dispatches on the latest
    baseline's *class* via :func:`_latest_baseline_event_kind` to route
    differing-content writes to the proposal branch — see
    ``docs/specs/wiki-init-adopt/spec.md`` AC13/AC14.
    """

    return _latest_page_baseline(journal_path, relative_path)[1]


def _ensure_obsidianignore(vault_root: Path) -> None:
    """Append the ``\\.proposed$`` pattern to ``.obsidianignore`` if absent.

    **Documented non-journaled bypass** — the only one in the kit
    alongside ``resolve_proposal`` (which IS journaled but bypasses the
    drift check). See ``OBSIDIANIGNORE_BYPASS_DOC`` §Non-goals "Why
    ``.obsidianignore`` is not journaled" and ADR-0004 §Negative for
    the rationale. Three reasons, cumulatively:

    1. Every user edit to ``.obsidianignore`` (adding their own
       scratch-dir ignore) would register as ``page-drift`` in
       ``wiki doctor`` — wrong UX for a file users are expected to edit.
    2. Routing through ``safe_write`` proper would produce
       ``.obsidianignore.proposed`` on user drift, which Obsidian then
       indexes (because ``.obsidianignore`` itself no longer carries
       the proposed-pattern) — a self-defeating bootstrap.
    3. Special-casing ``check_page_drift`` to skip ``.obsidianignore``
       re-introduces the bypass the spec is supposed to remove.

    Adding a third bypass requires amending
    ``OBSIDIANIGNORE_BYPASS_DOC`` first; the journaling story is
    load-bearing.
    """

    ignore = vault_root / ".obsidianignore"
    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if OBSIDIAN_IGNORE_PROPOSED_PATTERN in existing.splitlines():
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    ignore.write_text(existing + OBSIDIAN_IGNORE_PROPOSED_PATTERN + "\n", encoding="utf-8")


def write_os_artifact(
    path: Path,
    content: str | bytes,
    *,
    vault_root: Path,
) -> None:
    """Atomically write a kit-owned artifact to a path *outside* the vault.

    The schedule module's ``_Emitter`` implementations materialise files
    in OS-managed directories — launchd plists under
    ``~/Library/LaunchAgents/``, systemd units under
    ``~/.config/systemd/user/``, Task Scheduler XML under
    ``%LOCALAPPDATA%/llm-wiki-kit/schedules/``. Those paths are outside
    the vault by design (the OS scheduler reads them), so :func:`safe_write`
    refuses them via :func:`_relative_to_vault`. ``write_os_artifact`` is
    the kit's blessed out-of-vault writer for that case.

    The artifact has no journal baseline — it is wholly kit-owned and
    lives outside the vault, so user edits aren't the kit's concern.
    Recovery from out-of-band deletion goes through
    ``wiki schedule install`` + ``wiki doctor``, not through drift
    detection.

    **Documented exemption from the safe-write rule.** The kit-side
    write rule (``AGENTS.md`` §"Check before acting") covers in-vault
    writes: ``resolve_proposal`` and ``_ensure_obsidianignore`` are its
    two named bypasses, both writing inside the vault. This helper is a
    third blessed channel for kit writes — but for paths *outside* the
    vault, where ``safe_write`` does not apply. AGENTS.md names it in
    the same carve-out for discoverability.

    The write is atomic on POSIX (and on Windows when the destination
    exists): the helper opens a ``NamedTemporaryFile`` in ``path.parent``,
    writes the content, fsyncs, closes, then ``os.replace``\\ s the
    tempfile into place. A crash mid-write leaves either the previous
    file (if any) or no file — never partial bytes. **Overwrite is
    intentional**: a re-install with the same cadence must produce the
    same artifact byte-identical (``schedule.install`` enforces the
    journal-side "no-op when already installed" check before calling
    here, per ``docs/specs/wiki-schedule/spec.md`` §"install happy path"
    and §Invariants).

    Refuses, raising :class:`WikiError`, when ``path`` resolves inside
    ``vault_root``. The caller should route in-vault writes through
    :func:`safe_write` instead. The check resolves both sides
    (``Path.resolve`` defaults to non-strict, so the artifact's
    not-yet-existing final component is fine) and catches a ``..``
    lexical escape that lands back in the vault.

    Filesystem errors (permission denied on the artifact directory, disk
    full, etc.) propagate as :class:`OSError`. The helper does not
    swallow them — ``schedule.install`` relies on the exception to abort
    the install before journaling. On any failure between tempfile open
    and ``os.replace``, the helper unlinks the tempfile before
    re-raising so retry loops do not accumulate ``.tmp`` debris in
    OS-managed directories.
    """

    resolved_vault = vault_root.resolve()
    # ``Path.resolve`` defaults to non-strict, so the artifact's
    # not-yet-existing final component resolves fine; intermediate
    # directories still resolve symlinks normally.
    resolved_path = path.resolve()
    if resolved_path == resolved_vault or resolved_vault in resolved_path.parents:
        raise WikiError(
            f"write_os_artifact refuses in-vault path {path!s} "
            f"(vault_root={vault_root!s}); route through safe_write instead"
        )

    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    data: bytes = content.encode("utf-8") if isinstance(content, str) else content

    # ``delete=False`` so the success path can ``os.replace`` the
    # tempfile into place; the failure path explicitly unlinks before
    # re-raising so a retry loop does not accumulate ``.<name>.<rand>.tmp``
    # debris next to the artifact.
    tmp_handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=resolved_path.parent,
        prefix=f".{resolved_path.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(tmp_handle.name)
    try:
        with tmp_handle as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, resolved_path)
    except BaseException:
        # ``missing_ok=True`` is defensive: today, no code path raises
        # between ``os.replace`` succeeding and the function returning,
        # so on a successful replace the tempfile is already gone.
        # Future code added between replace and return must not orphan
        # a tempfile here.
        tmp_path.unlink(missing_ok=True)
        raise
