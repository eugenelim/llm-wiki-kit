"""Vault-state validator behind ``wiki doctor``.

Replays the journal, compares to disk, and reports eight kinds of issue:

* ``page-drift`` — a journaled ``page.write`` whose on-disk hash no
  longer matches, with no outstanding ``page.proposal`` to explain it.
* ``managed-region-drift`` — a journaled ``managed_region.write``
  whose on-disk region body no longer matches.
* ``pending-proposal`` — a ``.proposed`` sidecar awaiting resolution.
* ``orphan`` — a file under a kit-owned path with no journal event.
* ``missing`` — a journaled ``page.write`` whose file is gone.
* ``primitive-missing`` — a journal-recorded primitive that the kit's
  catalog no longer carries (e.g. after a kit downgrade).
* ``stale-lock`` — a ``lock.acquired`` event older than
  ``WIKI_LOCK_STALE_HOURS`` (default 24) with no matching release
  (``journal-locking`` spec §Doctor).
* ``journal-corrupt`` — a malformed journal line; surfaced once with
  the offending line number, then the remaining checks run against
  the valid-events prefix instead of crashing the whole pass
  (``journal-locking`` spec §Recovery).

Doctor only reports. Auto-fix lives in a future ``wiki doctor --fix``
task. The CLI surface maps a non-empty report to exit code 1; ``2`` is
reserved for internal errors raised through :class:`WikiError`.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from socket import gethostname

from llm_wiki_kit import managed_regions
from llm_wiki_kit import primitives as _primitives_module
from llm_wiki_kit.errors import JournalCorruptError, ManagedRegionError, WikiError
from llm_wiki_kit.journal import read_events_lenient, replay_state
from llm_wiki_kit.models import (
    Event,
    ManagedRegionWriteEvent,
    OperationExecFailedEvent,
    OperationRunByAgentEvent,
    PageWriteEvent,
    PrimitiveInstallEvent,
    PrimitiveKind,
    PrimitiveUpgradeEvent,
    ScheduleInstalledEvent,
    ScheduleUninstalledEvent,
    VaultState,
)
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import installed_outcome_verbs
from llm_wiki_kit.schedule import _resolve_emitter
from llm_wiki_kit.schedule._emitter import InspectResult, _Emitter, default_disabled_hint

# Issue kinds (also serve as the line prefix in the CLI output).
PAGE_DRIFT = "page-drift"
MANAGED_REGION_DRIFT = "managed-region-drift"
PENDING_PROPOSAL = "pending-proposal"
ORPHAN = "orphan"
MISSING = "missing"
PRIMITIVE_MISSING = "primitive-missing"
STALE_LOCK = "stale-lock"
JOURNAL_CORRUPT = "journal-corrupt"

# Schedule-section warning kinds. These are *warnings*, not failures:
# spec §"Doctor integration" — ``wiki doctor`` exits 0 when only schedule
# warnings are present. Warnings carry ``is_warning=True`` on :class:`Issue`
# so the CLI can partition them out of the exit-code calculation; the
# kind itself is retained for sort stability and for tests that want to
# pin a specific drift mode.
# Agents-section warning kinds (RFC-0004 wiki-agents PR-6). Same warning
# convention as the Schedules section — ``wiki doctor`` exits 0 when only
# agent warnings remain (``docs/specs/wiki-agents/spec.md`` §Outputs
# ``wiki doctor``). Distinct ``agent-*`` prefixes let the CLI partition
# warnings into the right output section (Agents vs. Schedules).
AGENT_BINDING_MISSING = "agent-binding-missing"
AGENT_VERSION_DRIFT = "agent-version-drift"

SCHEDULE_MISSING_FILE = "schedule-missing-file"
SCHEDULE_DISABLED = "schedule-disabled"
# The kind name predates the spec rephrasing — the rendered warning
# (``detail``) is neutral between a true rename and a legitimate
# multi-host vault, but the kind is retained for journal-grep
# compatibility and for tests that pin a specific drift mode.
SCHEDULE_HOSTNAME_RENAME = "schedule-hostname-rename"
SCHEDULE_EXEC_FAILURES = "schedule-exec-failures"

# Spec §"Doctor integration" — exec-failure backlog filters to the two
# reasons the user can act on. ``conflict-refused`` already surfaces via
# the ``.proposed`` sidecar (pending-proposal); ``binary-missing`` and
# ``skill-missing`` are reserved-but-not-emitted at v1 per
# ``docs/specs/wiki-run-exec/spec.md`` §"Contracts with other modules".
_EXEC_FAILURE_REASONS_TO_SURFACE = frozenset({"non-zero-exit", "timeout"})

# Spec §"Doctor integration": "the last 7 days". Pinned here so a future
# change (e.g. configurable via env var) lands in one place.
_EXEC_FAILURE_WINDOW = timedelta(days=7)

# Default stale-lock threshold per ``journal-locking`` spec §Invariants.
# Doctor reads ``WIKI_LOCK_STALE_HOURS`` on each run; this default applies
# when the env var is absent, blank, or unparseable.
_DEFAULT_STALE_HOURS = 24

# Kit-owned vault paths are derived from ``state.page_writes`` rather
# than enumerated as a static tuple (retro-review qC10 + C6). The kit
# claims territory by writing it; an empty vault claims nothing, and
# the orphan check stays silent until ``wiki init`` (or a later
# ``safe_write``) has journaled at least one path. ADR-0004: the kit
# never touches user territory.


@dataclass(frozen=True)
class Issue:
    """One finding from ``run_doctor``.

    Not a Pydantic model because :class:`Issue` never crosses disk —
    ADR-0005 reserves Pydantic for the disk-bound schemas. ``detail``
    is optional context (e.g. "region missing"); empty string by default
    so the rendered line stays compact.

    Most issue kinds put a vault-relative filesystem path in ``path``
    (``AGENTS.md``, ``skills/rogue/SKILL.md``). The one shim today is
    ``journal-corrupt``, where ``path`` carries the 1-based line number
    of the offending journal row as a string — there is no vault file
    that "owns" a torn JSONL line, and the plan
    (``docs/specs/journal-locking/plan.md`` §Steps step 6) makes this
    the explicit contract. A future ``Issue`` refactor that splits
    ``path`` into ``path | line`` should update both call sites at
    once — including ``run_doctor``'s ``(kind, path, detail)`` sort
    key, which would order ``journal-corrupt: 10`` before
    ``journal-corrupt: 2`` (lexicographic on the line-number string)
    the moment ``read_events_lenient`` learns to surface more than one
    ``Corruption`` per pass. Today only one corruption is reported, so
    the bug is latent.
    """

    kind: str
    path: str
    detail: str = ""
    is_warning: bool = False


def format_issue(issue: Issue) -> str:
    """Render an :class:`Issue` as one CLI line.

    Failure issues render as ``kind: path`` (or ``kind: path (detail)``).
    Warnings (``is_warning=True``) render as a bare natural-text message
    pulled from ``detail`` — the Schedules section emits one
    full-sentence warning per finding rather than the ``kind: path``
    shape, per ``docs/specs/wiki-schedule/spec.md`` §"Doctor integration".
    """

    if issue.is_warning:
        return issue.detail
    if issue.detail:
        return f"{issue.kind}: {issue.path} ({issue.detail})"
    return f"{issue.kind}: {issue.path}"


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_page_drift(state: VaultState, vault_root: Path, events: list[Event]) -> list[Issue]:
    """Pages whose on-disk hash diverges from the latest ``page.write``.

    A path with an outstanding ``page.proposal`` is reported as
    ``pending-proposal``, not ``page-drift`` — the user already knows
    the kit wanted to write something there.

    A path whose latest event for that file is a
    ``ManagedRegionWriteEvent`` (post-Task-19) is also skipped — the
    install pipeline's aggregator rewrites managed-region files in
    place via :func:`write_helper.safe_write_region` *after* the seed
    primitive's ``safe_write`` lands the empty-region seed bytes, so
    the original ``PageWriteEvent`` baseline goes stale by design.
    Region-level drift is what :func:`check_managed_region_drift`
    exists to catch; double-reporting at the page level would surface
    every managed-region file as drifted after every install.
    """

    files_with_later_region_writes = _files_with_managed_region_write_after_page_write(events)

    issues: list[Issue] = []
    for relative, event in state.page_writes.items():
        if relative in state.pending_proposals:
            continue
        if relative in files_with_later_region_writes:
            continue
        abs_path = vault_root / relative
        if not abs_path.exists():
            continue  # surfaces via check_missing
        if _hash(abs_path.read_bytes()) != event.hash:
            issues.append(Issue(PAGE_DRIFT, relative))
    return issues


def _files_with_managed_region_write_after_page_write(events: list[Event]) -> set[str]:
    """Return paths whose latest write event is a region write, not a page write.

    Used by :func:`check_page_drift` to skip files the install
    pipeline has rewritten via the managed-region path after the
    initial seed. The order matters — a future page write would
    re-baseline and bring the file back under page-level drift
    detection.
    """

    latest_write_kind: dict[str, str] = {}
    for event in events:
        if isinstance(event, PageWriteEvent):
            latest_write_kind[event.path] = "page"
        elif isinstance(event, ManagedRegionWriteEvent):
            latest_write_kind[event.file] = "region"
    return {path for path, kind in latest_write_kind.items() if kind == "region"}


def check_managed_region_drift(
    events: list[Event], vault_root: Path, state: VaultState
) -> list[Issue]:
    """Managed regions whose on-disk body diverges from the latest write.

    Walks ``events`` (not the replayed state) because
    ``managed_region.write`` events aren't projected into
    :class:`VaultState`. Per-region "latest" is the last event for
    ``(file, region)`` in journal order.

    A file with an outstanding ``page.proposal`` is skipped — the
    proposal already explains every region inside it, and reporting
    both ``pending-proposal`` and ``managed-region-drift`` for the
    same file is double-counting (retro-review #B6, pairs with
    ``write_helper.resolve_proposal``'s region re-baseline fix #F-B1).
    """

    latest: dict[tuple[str, str], ManagedRegionWriteEvent] = {}
    for event in events:
        if isinstance(event, ManagedRegionWriteEvent):
            latest[(event.file, event.region)] = event

    file_cache: dict[str, dict[str, str] | None] = {}
    issues: list[Issue] = []
    for (file_path, region), event in latest.items():
        if file_path in state.pending_proposals:
            continue
        abs_file = vault_root / file_path
        if not abs_file.exists():
            continue  # surfaces via check_missing
        if file_path not in file_cache:
            try:
                file_cache[file_path] = managed_regions.parse(abs_file.read_text(encoding="utf-8"))
            except ManagedRegionError:
                file_cache[file_path] = None
        parsed = file_cache[file_path]
        target = f"{file_path}:{region}"
        if parsed is None:
            issues.append(Issue(MANAGED_REGION_DRIFT, target, "markers malformed"))
            continue
        body = parsed.get(region)
        if body is None:
            issues.append(Issue(MANAGED_REGION_DRIFT, target, "region missing"))
            continue
        if _hash(managed_regions.canonical_region_body(body)) != event.content_hash:
            issues.append(Issue(MANAGED_REGION_DRIFT, target))
    return issues


def check_pending_proposals(state: VaultState) -> list[Issue]:
    """One issue per unresolved ``.proposed`` sidecar.

    Surfaces the sidecar's vault-relative path so the user can hand it
    to the vault-side ``wiki-conflict`` skill.
    """

    return [
        Issue(PENDING_PROPOSAL, event.proposed_path) for event in state.pending_proposals.values()
    ]


def check_missing(state: VaultState, vault_root: Path) -> list[Issue]:
    """Journal-recorded pages whose file is no longer on disk."""

    return [
        Issue(MISSING, relative)
        for relative in state.page_writes
        if not (vault_root / relative).exists()
    ]


def check_orphans(state: VaultState, vault_root: Path) -> list[Issue]:
    """Files under kit-owned paths with no corresponding journal event.

    Kit-owned territory is derived from ``state.page_writes`` AND
    ``state.adopted_pages`` (retro-review qC10 + C6; ADR-0008 §Decision
    sub-choice 3): every path the kit has ever recorded a ``page.write``
    OR ``page.adopted`` for contributes. The top-level directory of
    every such path is treated as kit territory; journaled top-level
    filenames are watched directly. Skips ``.proposed`` sidecars
    (those surface as pending-proposal) and any path outside the
    derived territory (user-owned by default).

    Doctrine: only ``page.write`` AND ``page.adopted`` events extend
    territory. ``ManagedRegionWriteEvent``s always reference a file
    that was seeded earlier via ``safe_write`` (which emits a
    ``PageWriteEvent``), so the shared-file case is already covered
    by the page-writes fold-in. ``ManagedRegionAdoptedEvent``s likewise
    reference a host file that already carries a ``PageAdoptedEvent``
    in the adopt-phase journal sequence (spec §Outputs Journal events
    bullet 2 names the interleave). ``SourceIngestEvent.produced_pages``
    is a forward-looking record; the actual page writes the vault-side
    ingester performs flow through ``safe_write`` and emit their own
    ``PageWriteEvent``s. Folding any of those event types in would
    double-count territory without expanding what the kit actually owns.

    Transition note: an empty journal claims no territory. The orphan
    check fires only after the kit has journaled at least one write —
    which the install pipeline does on every ``wiki init``. A user
    adding files under a top-level dir before the kit has touched
    that dir gets a silent pass; once the kit journals anything under
    that dir, those files surface as orphans. The same was true under
    the previous static tuples for ``skills/``, ``_templates/``, and
    ``wiki/`` (categorically kit-owned), so the user-visible UX change
    is bounded to the pre-init window.
    """

    journaled = set(state.page_writes) | set(state.adopted_pages)
    proposal_sidecars = {e.proposed_path for e in state.pending_proposals.values()}

    owned_files: set[str] = set()
    owned_dirs: set[str] = set()
    for journaled_path in journaled:
        parts = Path(journaled_path).parts
        if not parts:
            continue
        if len(parts) == 1:
            owned_files.add(parts[0])
        else:
            owned_dirs.add(parts[0])

    candidates: list[str] = []
    for name in owned_files:
        if (vault_root / name).is_file():
            candidates.append(name)
    for dir_name in owned_dirs:
        directory = vault_root / dir_name
        if not directory.is_dir():
            continue
        for entry in directory.rglob("*"):
            if entry.is_file():
                candidates.append(entry.relative_to(vault_root).as_posix())

    # ``.claude/commands/*.md`` files are handled by
    # ``_check_outcome_orphan_stubs``, which has precise kit-vs-user
    # awareness (only flags files the kit previously wrote via
    # ``safe_write``). Excluding them here prevents ``check_orphans``'s
    # broad directory-ownership heuristic from flagging user-created
    # slash commands as orphans (spec §Non-goal 9; plan §PR-7).
    _outcome_stub_prefix = ".claude/commands/"

    issues: list[Issue] = []
    for relative in candidates:
        if relative.endswith(".proposed"):
            continue
        if relative in proposal_sidecars:
            continue
        if relative.startswith(_outcome_stub_prefix) and relative.endswith(".md"):
            continue
        if relative not in journaled:
            issues.append(Issue(ORPHAN, relative))
    return issues


def _now() -> datetime:
    """Wall-clock seam.

    Lives in this module so tests can monkeypatch ``doctor._now`` to pin
    "now" against a fixed datetime — sleeping in tests would be both
    slow and flaky. Production callers never override it.
    """

    return datetime.now(UTC)


def _stale_threshold_hours() -> int:
    """Read ``WIKI_LOCK_STALE_HOURS`` or fall back to the 24-hour default.

    Blank, unparseable, zero, or negative values fall back rather than
    raising — ``wiki doctor`` is the diagnostic command of last resort,
    so it must not refuse to run because an env var was mistyped.
    Malformed values emit one warning to stderr so the user knows their
    config was ignored.
    """

    raw = os.environ.get("WIKI_LOCK_STALE_HOURS")
    if raw is None or raw == "":
        return _DEFAULT_STALE_HOURS
    try:
        hours = int(raw)
    except ValueError:
        print(
            f"wiki doctor: WIKI_LOCK_STALE_HOURS={raw!r} is not an integer; "
            f"using default {_DEFAULT_STALE_HOURS}",
            file=sys.stderr,
        )
        return _DEFAULT_STALE_HOURS
    if hours <= 0:
        print(
            f"wiki doctor: WIKI_LOCK_STALE_HOURS={raw!r} is not positive; "
            f"using default {_DEFAULT_STALE_HOURS}",
            file=sys.stderr,
        )
        return _DEFAULT_STALE_HOURS
    return hours


def check_stale_lock(state: VaultState, threshold_hours: int) -> list[Issue]:
    """Surface a ``stale-lock`` issue if the latest acquire has no release.

    Reads ``state.held_lock`` rather than re-deriving from events: the
    "last-acquire-wins, any-release-clears" semantics already live in
    ``replay_state`` (``journal.py``), and a parallel walk here would
    be a second source of truth waiting to drift. Pattern-matches the
    rest of the doctor checks (``check_page_drift``,
    ``check_pending_proposals``, ``check_orphans``,
    ``check_missing``, ``check_primitive_missing``) which all consume
    the replayed ``VaultState`` directly.

    Precondition: ``threshold_hours`` must be a positive integer. The
    only in-kit caller routes through ``_stale_threshold_hours()`` which
    clamps; a direct caller passing zero or a negative value gets
    "everything is stale" semantics by arithmetic, which is the caller's
    bug to fix.

    Naive (tz-less) ``HeldLock.acquired_at`` values are coerced to UTC
    before the age subtraction. The kit's own writers always emit
    tz-aware timestamps, but a hand-edited or externally produced
    journal line may carry a naive one — and ``wiki doctor`` must not
    crash on a journal it was specifically built to inspect.
    """

    holder = state.held_lock
    if holder is None:
        return []

    acquired_at = holder.acquired_at
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=UTC)
    age = _now() - acquired_at
    if age.total_seconds() < threshold_hours * 3600:
        return []

    return [Issue(STALE_LOCK, holder.by, f"acquired {acquired_at.isoformat()}")]


def check_primitive_missing(state: VaultState, events: list[Event], kit_root: Path) -> list[Issue]:
    """Installed primitives the current kit catalog no longer ships.

    Useful when a user downgrades the kit underneath a vault — the
    journal still references primitives the new install can't render or
    upgrade. Names are surfaced verbatim; the user (or the kit's future
    ``wiki upgrade`` step) decides what to do.

    For primitives whose latest install event recorded a
    ``source="sideload:<package>"`` attribution (``docs/specs/primitive-
    sideload/spec.md`` AC17), the finding's ``detail`` carries a hint
    naming the previously-installed package so the user can either
    ``pip install`` it again or remove the primitive from the recipe.
    Older journal lines without the ``source`` field are unchanged.
    """

    catalog_names: set[str] = set()
    core_dir = kit_root / "core"
    if (core_dir / "primitive.yaml").is_file():
        catalog_names.add(load_primitive(core_dir).name)
    for primitive in discover_primitives(kit_root / "templates"):
        catalog_names.add(primitive.name)

    # Build per-primitive source attribution from the latest install
    # event so missing-primitive findings can hint at a previously
    # installed sideload package.
    latest_install_source: dict[str, str | None] = {}
    for event in events:
        if isinstance(event, PrimitiveInstallEvent):
            latest_install_source[event.primitive] = event.source

    issues: list[Issue] = []
    for name in state.installed_primitives:
        if name in catalog_names:
            continue
        source = latest_install_source.get(name)
        if source is not None and source.startswith("sideload:"):
            package = source.split(":", 1)[1]
            detail = (
                f"previously provided by sideload package '{package}'; "
                "the package may have been uninstalled — `pip install` "
                "it again or remove the primitive from the recipe"
            )
            issues.append(Issue(PRIMITIVE_MISSING, name, detail))
        else:
            issues.append(Issue(PRIMITIVE_MISSING, name))
    return issues


def _check_outcome_orphan_stubs(state: VaultState, vault_root: Path, kit_root: Path) -> list[Issue]:
    """Slash-stub files whose verb is no longer in the installed-verb set.

    Lists ``.claude/commands/*.md`` files on disk. For each file:

    1. Derives the verb from the filename stem.
    2. Checks whether the path is in ``state.page_writes`` — only files
       the kit previously wrote are candidates. User-created files in
       ``.claude/commands/`` (spec §Non-goal 9) are silently skipped.
    3. Checks whether the verb is still in the installed-verb set via
       :func:`recipes.installed_outcome_verbs`. If the verb is absent,
       emits an ``ORPHAN`` issue naming the file and the dropped verb.

    Calls :func:`recipes.installed_outcome_verbs`, which performs an
    independent strict journal read; ``wiki doctor`` is interactive
    and runs once per invocation, so the duplicate IO against the
    journal that ``run_doctor`` already parsed via
    :func:`journal.read_events_lenient` is accepted rather than
    threaded as injected state. The helper returns ``{}``
    when the journal is missing (never the case here —
    ``run_doctor`` already opened it) and raises
    :class:`JournalCorruptError` on mid-journal corruption, which the
    ``except`` clause below swallows so the orphan check degrades
    gracefully against the corruption ``run_doctor`` already surfaced
    as a ``journal-corrupt`` issue.

    The check uses ``installed_outcome_verbs`` rather than reading the
    current verb set directly from the catalog, so it correctly handles
    the case where an operation was removed from the journal entirely
    (``PrimitiveRemoveEvent``) or the operation's ``outcomes:`` list
    was shrunk — both collapse to "verb absent from the returned map".
    """

    commands_dir = vault_root / ".claude" / "commands"
    if not commands_dir.is_dir():
        return []

    try:
        installed = installed_outcome_verbs(vault_root, kit_root)
    except JournalCorruptError:
        # ``run_doctor`` already surfaced the corruption as a
        # ``journal-corrupt`` issue; skip the orphan check gracefully
        # rather than masking the existing issue. Other exceptions
        # (e.g. malformed ``contract.yaml``) are propagated — a
        # silent-swallow would mask programming errors.
        return []

    issues: list[Issue] = []
    for stub_path in sorted(commands_dir.glob("*.md")):
        relative = stub_path.relative_to(vault_root).as_posix()
        # Only flag files the kit previously wrote (PageWriteEvent present).
        if relative not in state.page_writes:
            continue
        verb = stub_path.stem
        if verb not in installed:
            issues.append(
                Issue(
                    ORPHAN,
                    relative,
                    f"dropped verb '{verb}' — operation no longer installed"
                    " or no longer declares this outcome",
                )
            )
    return issues


def _live_schedules(events: list[Event]) -> list[ScheduleInstalledEvent]:
    """Most recent ``ScheduleInstalledEvent`` per ``(operation, machine_id)``.

    A schedule is "live" when its most recent install event has no later
    ``ScheduleUninstalledEvent`` masking it on the same pair. Mirrors
    the same fold used by ``schedule.list_schedules`` so the two views
    agree on what's installed.
    """

    live: dict[tuple[str, str], ScheduleInstalledEvent] = {}
    for event in events:
        if isinstance(event, ScheduleInstalledEvent):
            live[(event.operation, event.machine_id)] = event
        elif isinstance(event, ScheduleUninstalledEvent):
            live.pop((event.operation, event.machine_id), None)
    # Stable order keyed by (operation, machine_id) so warning output is
    # deterministic across runs.
    return [live[key] for key in sorted(live.keys())]


def _check_schedules(events: list[Event]) -> list[Issue]:
    """Spec §"Doctor integration" — drift + hostname-rename + exec-failure backlog.

    Returns warning-flavored :class:`Issue`\\ s (``is_warning=True``); the
    CLI partitions them out of the exit-code calculation so a stale
    schedule never fails the doctor pass.

    Three families of warning:

    1. **Current-host artifact drift** — for each live schedule with
       ``machine_id == socket.gethostname()``, call the platform emitter's
       ``inspect()`` and emit ``schedule-missing-file`` /
       ``schedule-disabled`` warnings as appropriate. Windows v1 only
       reports file presence (emitter returns ``not-inspectable``).
    2. **Hostname rename** — one warning per distinct journaled
       ``machine_id`` that differs from the current host. Doctor cannot
       distinguish a renamed host from a legitimate multi-host vault;
       both produce the neutral ``--machine <old>`` operate-on-them
       hint per spec §Edge cases.
    3. **Exec-failure backlog** — ``OperationExecFailedEvent``\\ s in
       the last 7 days where ``reason in {non-zero-exit, timeout}``,
       grouped by operation. Other reasons are filtered out at the
       source — see ``_EXEC_FAILURE_REASONS_TO_SURFACE``.
    """

    issues: list[Issue] = []
    current_host = gethostname()
    live = _live_schedules(events)

    emitter: _Emitter | None
    try:
        emitter = _resolve_emitter()
    except WikiError:
        # Unsupported OS: file-presence is still checkable via stdlib,
        # but the per-OS subprocess probes aren't. The current-host
        # drift branch below degrades gracefully.
        emitter = None

    # 1. Current-host artifact drift.
    for event in live:
        if event.machine_id != current_host:
            continue
        artifact_path = Path(event.os_artifact_path)
        if emitter is None:
            # Fall back to bare file presence on unsupported OSes.
            result: InspectResult = "missing-file" if not artifact_path.exists() else "loaded"
        else:
            result = emitter.inspect(artifact_path)
        if result == "missing-file":
            issues.append(
                Issue(
                    kind=SCHEDULE_MISSING_FILE,
                    path=event.operation,
                    detail=(
                        f"schedule for {event.operation} missing artifact at "
                        f"{artifact_path}; reinstall with "
                        f"'wiki schedule install {event.operation}'"
                    ),
                    is_warning=True,
                )
            )
        elif result == "not-loaded":
            if emitter is not None:
                hint = emitter.disabled_hint(artifact_path)
            else:
                # Unreachable today — the ``emitter is None`` branch
                # above narrows ``result`` to ``"missing-file"`` /
                # ``"loaded"``. Reuse the Protocol-default helper so a
                # future broadening of either path doesn't drift two
                # copies of the fallback string.
                hint = default_disabled_hint(artifact_path)
            issues.append(
                Issue(
                    kind=SCHEDULE_DISABLED,
                    path=event.operation,
                    detail=(
                        f"schedule for {event.operation} exists on disk but is not loaded; '{hint}'"
                    ),
                    is_warning=True,
                )
            )
        # ``loaded`` and ``not-inspectable`` (Windows v1) emit no warning.

    # 2. Hostname rename — one warning per distinct foreign machine_id.
    foreign_hosts = sorted({event.machine_id for event in live if event.machine_id != current_host})
    for old in foreign_hosts:
        issues.append(
            Issue(
                kind=SCHEDULE_HOSTNAME_RENAME,
                path=old,
                detail=(
                    f"current hostname '{current_host}', journaled schedules for "
                    f"'{old}' (either a rename or a schedule on another host); "
                    f"pass '--machine {old}' to operate on them"
                ),
                is_warning=True,
            )
        )

    # 3. Exec-failure backlog — last 7 days, filter by reason, group by op.
    cutoff = _now() - _EXEC_FAILURE_WINDOW
    counts: dict[str, int] = defaultdict(int)
    for exec_event in events:
        if not isinstance(exec_event, OperationExecFailedEvent):
            continue
        if exec_event.reason not in _EXEC_FAILURE_REASONS_TO_SURFACE:
            continue
        # Tz-aware compare: the journal carries tz-aware timestamps in
        # production, but a hand-edited line may be naive — coerce to
        # UTC the same way ``check_stale_lock`` does so doctor never
        # crashes on the journal it was built to inspect.
        ts = exec_event.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < cutoff:
            continue
        counts[exec_event.operation] += 1
    for operation in sorted(counts):
        n = counts[operation]
        issues.append(
            Issue(
                kind=SCHEDULE_EXEC_FAILURES,
                path=operation,
                detail=(
                    f"{n} recent scheduled-exec failures for {operation}; "
                    f"see inbox/scheduled-failures/"
                ),
                is_warning=True,
            )
        )

    return issues


def _check_agents(
    state: VaultState, events: list[Event], vault_root: Path, kit_root: Path
) -> list[Issue]:
    """RFC-0004 wiki-agents spec §Outputs ``wiki doctor`` — Agents section.

    Two warning families (both ``is_warning=True``; ``wiki doctor`` exits
    ``0`` when only agent warnings remain — same convention as the
    Schedules section):

    1. **Bindings.** For each live schedule with ``agent`` set and
       ``machine_id == socket.gethostname()``, verify
       ``<vault>/.claude/agents/<agent>/AGENT.md`` exists. The check
       reads zero bytes of the file — only ``path.is_file()`` per spec
       §Constraints ("No kit-side reading or parsing of AGENT.md
       bodies").
    2. **Version drift.** For each installed ``kind: agent`` primitive
       that is bound to a still-active schedule **or** has ever
       produced an ``OperationRunByAgentEvent``, compare the most
       recent ``PrimitiveUpgradeEvent`` for the agent against the most
       recent ``OperationRunByAgentEvent`` referencing it. If the
       upgrade is newer (or no run-by-agent event has happened since),
       warn — the next firing will see a different voice.

    This function walks ``events`` **once** to collect its two
    per-agent indices (latest upgrade timestamp; latest run-by-agent
    timestamp) and the live-schedule view once via :func:`_live_schedules`.
    The catalog is walked once via :func:`discover_primitives` to
    recover each installed primitive's kind. Doctor performance is
    a recurring concern — see PR-6's drift-watch note in
    ``docs/specs/wiki-agents/plan.md`` §Risks; the function is
    O(events + catalog), not O(events * agents).

    The "single walk" promise is scoped to this function's internal
    indices. The broader ``run_doctor`` pass walks ``events`` once
    per check function (``_check_schedules``, ``_check_agents``, and
    each of the page-/managed-region-level checks); a future "walk
    once across all checks" refactor would consolidate them.
    """

    issues: list[Issue] = []
    current_host = gethostname()
    live = _live_schedules(events)

    # 1. Bindings — AGENT.md presence on the current host.
    for schedule_event in live:
        if schedule_event.agent is None:
            continue
        if schedule_event.machine_id != current_host:
            continue
        agent_md = vault_root / ".claude" / "agents" / schedule_event.agent / "AGENT.md"
        if agent_md.is_file():
            continue
        issues.append(
            Issue(
                kind=AGENT_BINDING_MISSING,
                path=schedule_event.operation,
                detail=(
                    f"schedule for {schedule_event.operation} bound to agent "
                    f"'{schedule_event.agent}' but AGENT.md missing at "
                    f"{agent_md}; run 'wiki add agent:{schedule_event.agent}' "
                    f"or re-run 'wiki init'"
                ),
                is_warning=True,
            )
        )

    # 2. Version drift — single journal walk to gather both indices.
    latest_upgrade: dict[str, PrimitiveUpgradeEvent] = {}
    latest_run_by_agent: dict[str, datetime] = {}
    for event in events:
        if isinstance(event, PrimitiveUpgradeEvent):
            latest_upgrade[event.primitive] = event
        elif isinstance(event, OperationRunByAgentEvent):
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            previous = latest_run_by_agent.get(event.agent)
            if previous is None or ts > previous:
                latest_run_by_agent[event.agent] = ts

    # Agents bound to a still-active schedule or any run-by-agent event.
    # Spec §Outputs: "Suppressed when the agent has never been bound to
    # a still-active schedule or run."
    bound_agents: set[str] = {ev.agent for ev in live if ev.agent is not None}
    bound_agents.update(latest_run_by_agent.keys())

    # Recover kind per installed primitive via a single catalog walk.
    catalog = discover_primitives(kit_root / "templates")
    kind_by_name: dict[str, PrimitiveKind] = {p.name: p.kind for p in catalog}

    for agent_name in sorted(state.installed_primitives):
        if kind_by_name.get(agent_name) is not PrimitiveKind.AGENT:
            continue
        if agent_name not in bound_agents:
            continue
        upgrade = latest_upgrade.get(agent_name)
        if upgrade is None:
            continue
        upgrade_ts = upgrade.timestamp
        if upgrade_ts.tzinfo is None:
            upgrade_ts = upgrade_ts.replace(tzinfo=UTC)
        last_run = latest_run_by_agent.get(agent_name)
        # Strict ``>`` so equal-timestamp ties resolve in favor of the
        # warning. The next-firing nudge is non-blocking; a false
        # positive on a tie is cheaper than a false negative.
        if last_run is not None and last_run > upgrade_ts:
            continue
        bound_ops = sorted({ev.operation for ev in live if ev.agent == agent_name})
        operations_clause = (
            f"bound operations: {', '.join(bound_ops)}"
            if bound_ops
            else "no active scheduled operations"
        )
        agent_md = vault_root / ".claude" / "agents" / agent_name / "AGENT.md"
        issues.append(
            Issue(
                kind=AGENT_VERSION_DRIFT,
                path=agent_name,
                detail=(
                    f"agent '{agent_name}' was upgraded {upgrade.from_version} → "
                    f"{upgrade.to_version} since the last scheduled run; review "
                    f"'{agent_md}' before the next firing changes voice "
                    f"({operations_clause})"
                ),
                is_warning=True,
            )
        )

    return issues


@dataclass(frozen=True)
class SideloadPrimitiveListing:
    """One ``(package, version, kind, name)`` row of the installed-sideload table.

    Frozen value type. The sort key is ``(package, kind, name)`` so the
    rendered section groups primitives by package and lists them in
    catalog-style kind-then-name order.
    """

    package: str
    version: str
    kind: str
    name: str


@dataclass(frozen=True)
class SideloadDoctorInfo:
    """Doctor's structural view of the installed sideload set.

    Returned by :func:`gather_sideload_info`. Three independent payloads
    drive separate render sections in ``_cmd_doctor`` per ``docs/specs/
    primitive-sideload/spec.md`` §Outputs:

    * :attr:`primitives` — one ``SideloadPrimitiveListing`` per
      sideloaded primitive in the merged catalog. Populates the
      "Sideload primitives:" section.
    * :attr:`dropped_fields` — ``(package, primitive_name, fields)``
      tuples for any sideloaded primitive whose
      ``_dropped_fields`` is non-empty. Populates the
      "Sideload primitives with dropped unknown fields:" subsection.
    * :attr:`package_recipes_warnings` — ``(package, recipes_path)``
      tuples for sideload packages that ship a ``recipes/`` directory
      at the package root (silently inert per spec §Edge cases).
      Populates a soft warning line per package naming both the
      package and the dropped path so the user can act on it.

    All three lists are empty when no sideload packages are installed,
    matching the spec's "absent section" contract for the no-sideload
    case.
    """

    primitives: list[SideloadPrimitiveListing]
    dropped_fields: list[tuple[str, str, tuple[str, ...]]]
    package_recipes_warnings: list[tuple[str, Path]]


def gather_sideload_info(kit_root: Path) -> SideloadDoctorInfo:
    """Return the doctor's structural view of installed sideload packages.

    Drives the doctor's "Sideload primitives:" section and the
    associated soft-warning subsections. Pure read-only helper: enumerates
    the ``wiki-primitive`` entry-point group, walks each package's
    ``templates/`` tree via the merged-catalog discovery surface, and
    returns the listing + dropped-field surface + recipes-at-package-root
    warning per ``docs/specs/primitive-sideload/spec.md`` §"Edge cases".
    """

    triples = _primitives_module._discover_sideloaded_template_dirs()
    if not triples:
        return SideloadDoctorInfo(primitives=[], dropped_fields=[], package_recipes_warnings=[])

    package_versions = {pkg: version for pkg, version, _path in triples}
    package_recipes: list[tuple[str, Path]] = []
    for package, _version, templates_path in triples:
        # ``templates/`` lives inside the package; ``recipes/`` lives at
        # the package root (sibling to ``templates/``).
        package_root = templates_path.parent
        recipes_dir = package_root / "recipes"
        if recipes_dir.is_dir():
            package_recipes.append((package, recipes_dir))

    # Walk the merged catalog once via the kit's own ``discover_primitives``
    # surface so this helper sees primitives through the same
    # validation pipeline ``wiki init`` / ``wiki add`` see — including
    # the ``_dropped_fields`` PrivateAttr the sideload loader records.
    merged = discover_primitives(kit_root / "templates")

    listings: list[SideloadPrimitiveListing] = []
    dropped_field_findings: list[tuple[str, str, tuple[str, ...]]] = []
    for primitive in merged:
        if not primitive.source.startswith("sideload:"):
            continue
        package = primitive.source.split(":", 1)[1]
        listings.append(
            SideloadPrimitiveListing(
                package=package,
                version=package_versions.get(package, "unknown"),
                kind=primitive.kind.value,
                name=primitive.name,
            )
        )
        if primitive._dropped_fields:
            dropped_field_findings.append((package, primitive.name, primitive._dropped_fields))

    listings.sort(key=lambda row: (row.package, row.kind, row.name))
    dropped_field_findings.sort(key=lambda row: (row[0], row[1]))
    package_recipes.sort()

    return SideloadDoctorInfo(
        primitives=listings,
        dropped_fields=dropped_field_findings,
        package_recipes_warnings=package_recipes,
    )


def run_doctor(vault_root: Path, kit_root: Path) -> list[Issue]:
    """Replay the journal and return issues: failures first, then schedule warnings.

    Failures are sorted by ``(kind, path, detail)``; schedule warnings
    (``is_warning=True``) are appended last in family-grouped order
    (drift → hostname-rename → exec-failure backlog).

    Uses ``read_events_lenient`` so a malformed line surfaces as a
    ``journal-corrupt`` issue while the remaining checks run against the
    valid-events prefix. Strict ``read_events`` would have raised and
    hidden every other problem in the vault — the opposite of what
    ``wiki doctor`` is for.

    Schedule findings are appended last and tagged ``is_warning=True`` on
    the returned :class:`Issue`\\ s — callers that care about exit codes
    (e.g. ``_cmd_doctor``) partition them out so ``wiki doctor`` exits
    ``0`` when only schedule warnings remain.
    """

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    events, corruption = read_events_lenient(journal_path)
    state = replay_state(events)

    issues: list[Issue] = []
    if corruption is not None:
        issues.append(Issue(JOURNAL_CORRUPT, str(corruption.line), corruption.reason))
    issues.extend(check_page_drift(state, vault_root, events))
    issues.extend(check_managed_region_drift(events, vault_root, state))
    issues.extend(check_pending_proposals(state))
    issues.extend(check_orphans(state, vault_root))
    issues.extend(check_missing(state, vault_root))
    issues.extend(check_primitive_missing(state, events, kit_root))
    issues.extend(check_stale_lock(state, _stale_threshold_hours()))
    issues.extend(_check_outcome_orphan_stubs(state, vault_root, kit_root))
    # Sort failures by (kind, path, detail) only. Schedule warnings are
    # appended after the sort so the "Schedules section after the
    # Primitives section" ordering in spec §"Doctor integration" holds;
    # warnings stay in the family-grouped order ``_check_schedules``
    # produces (drift → hostname-rename → exec-failure backlog), which
    # is more readable than re-sorting them alphabetically by kind.
    issues.sort(key=lambda issue: (issue.kind, issue.path, issue.detail))
    issues.extend(_check_schedules(events))
    issues.extend(_check_agents(state, events, vault_root, kit_root))
    return issues
