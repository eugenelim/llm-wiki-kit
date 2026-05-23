"""``wiki schedule`` orchestration — install / uninstall / list_schedules.

Top-level wiring for the schedule verb. Dispatches platform-specific
work to the three per-OS emitters via the ``_Emitter`` Protocol in
``schedule/_emitter.py``; writes OS-side artifacts via
``write_helper.write_os_artifact()`` (the blessed out-of-vault writer);
journals one event per state transition through
``journal.transaction()``.

The install sequence is **write companions → write primary → activate
→ journal** under one transaction (spec §"install happy path" step 8).
Activation failure best-effort-unlinks the *primary* artifact and
skips the journal append; companions are left on disk as harmless
orphans (spec §Invariants: "install writes one file (or two on
Linux)" — uninstall doesn't delete companions either).

The idempotent dup-cadence short-circuit runs *before*
``journal.transaction()`` opens, so the no-op path emits zero events
of any type (no ``lock.acquired`` / ``lock.released`` pair) — spec
§Invariants "Idempotent-no-op emits zero events of any type."

PR-7's deferred design question (whether
``format_activation_instruction`` / ``format_deactivation_instruction``
should lift onto the ``_Emitter`` Protocol or stay as Windows-only
module-level helpers) is resolved here in favour of the lift: the
Protocol gains ``install_instruction(artifact_path) -> str | None``
and ``uninstall_instruction(artifact_path) -> str | None``, with
``None``-default impls on launchd/systemd and Windows delegating to
the existing module-level helpers. Names are deliberately
``*_instruction`` not ``post_*_instruction`` so they read as "return
the user-facing instruction string for the stdout summary" rather
than "run after install." The same lift applies to
``companion_artifacts(...) -> list[tuple[Path, str | bytes]]`` for
systemd's ``.service`` companion — every per-OS asymmetry is now a
Protocol method with a sensible default and the orchestrator has no
``isinstance`` branches.

Contract pinned in ``docs/specs/wiki-schedule/spec.md``. Construction
tests live in ``tests/unit/test_schedule_install.py``,
``tests/unit/test_schedule_uninstall.py``,
``tests/unit/test_schedule_list.py``, and
``tests/integration/test_cli_schedule.py``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event, read_events, replay_state, transaction
from llm_wiki_kit.models import (
    Event,
    ScheduleInstalledEvent,
    ScheduleUninstalledEvent,
)
from llm_wiki_kit.operations import _load_contract, _resolve_operation_kind
from llm_wiki_kit.schedule._emitter import InspectResult, _Emitter
from llm_wiki_kit.schedule.dsl import (
    ResolvedCadence,
)
from llm_wiki_kit.schedule.dsl import (
    parse as _parse_dsl,
)
from llm_wiki_kit.schedule.dsl import (
    resolve_default as _resolve_default_cadence,
)
from llm_wiki_kit.schedule.launchd import LaunchdEmitter
from llm_wiki_kit.schedule.systemd import SystemdEmitter
from llm_wiki_kit.schedule.taskscheduler import TaskSchedulerEmitter
from llm_wiki_kit.write_helper import write_os_artifact

# Vehicle name recorded on every event this module emits. Pinned by
# spec §Outputs ("by: wiki-schedule"); cross-task ``by`` values are
# how ``wiki doctor`` and ``journal grep`` attribute actions to the
# actor that produced them.
SCHEDULE_VEHICLE = "wiki-schedule"

# Platform → emitter dispatch table. Keyed by ``platform.system()``
# return values. Refused with WikiError on any other platform per
# spec §"Edge cases / Running on an unsupported OS." Tests
# monkeypatch ``_resolve_emitter`` to inject stub emitters.
_EMITTERS: dict[str, _Emitter] = {
    "Darwin": LaunchdEmitter(),
    "Linux": SystemdEmitter(),
    "Windows": TaskSchedulerEmitter(),
}

# Canonical day tokens (SUN..SAT) — index matches ``ResolvedCadence.day_of_week``.
_DAYS: tuple[str, ...] = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")


def _resolve_emitter() -> _Emitter:
    """Return the emitter for the current platform.

    Tests monkeypatch this function to inject stub emitters without
    touching ``platform.system()``. Refused with WikiError on any
    platform not in ``_EMITTERS``.
    """

    name = platform.system()
    emitter = _EMITTERS.get(name)
    if emitter is None:
        raise WikiError(f"scheduling is not supported on {name}; see RFC-0003 §'OS coverage'")
    return emitter


def _vault_id(vault_root: Path) -> str:
    """First 12 hex chars of SHA-256(absolute vault path).

    Spec §Invariants — deterministic for the same vault on the same
    machine; collision-probability ~1 in 16M between two vaults on
    the same host, acceptable for v1's one-user audience.
    """

    digest = hashlib.sha256(str(vault_root.resolve()).encode("utf-8")).hexdigest()
    return digest[:12]


def _resolve_exec_command(operation: str) -> list[str]:
    """Compute the argv the OS-side artifact runs.

    Resolution order per spec §Invariants:
    1. ``shutil.which("wiki")`` if it returns a non-None path.
    2. ``sys.argv[0]`` resolved to an absolute path (must exist).
    3. Raise WikiError.

    Stored as ``list[str]``; ``[1:]`` is always
    ``["run", "--exec", <operation>]``.
    """

    binary = shutil.which("wiki")
    if binary is None:
        argv0 = Path(sys.argv[0]).resolve()
        # The fallback must produce an actually-executable path — the
        # OS scheduler can't `exec()` a .py file at 3am. ``is_file()``
        # alone passes for source-tree invocations like ``python -m
        # llm_wiki_kit`` where argv0 is ``…/__main__.py``; gate on
        # ``os.access(..., X_OK)`` to refuse that case.
        if argv0.is_file() and os.access(argv0, os.X_OK):
            binary = str(argv0)
    if binary is None:
        raise WikiError("cannot resolve 'wiki' binary path; install via pipx or pass --wiki-binary")
    return [binary, "run", "--exec", operation]


def _canonicalize_cadence(cadence: ResolvedCadence) -> str:
    """Re-render a parsed cadence into its canonical DSL string form.

    ``parse("tue 18:00")`` → ``ResolvedCadence(period="weekly", ...)``
    → ``"TUE 18:00"`` (day token uppercased, time zero-padded). Spec
    CT-2 pins this canonical form on the journaled ``cadence_dsl``.
    """

    time = f"{cadence.hour:02d}:{cadence.minute:02d}"
    if cadence.period == "daily":
        return f"daily {time}"
    if cadence.period == "weekly":
        assert cadence.day_of_week is not None
        return f"{_DAYS[cadence.day_of_week]} {time}"
    if cadence.period == "monthly":
        assert cadence.day_of_month is not None
        return f"monthly {cadence.day_of_month} {time}"
    # quarterly
    assert cadence.day_of_month is not None
    return f"quarterly {cadence.day_of_month} {time}"


def _next_run(cadence: ResolvedCadence, now: datetime) -> datetime:
    """Advisory next-run time. Not promised to match the OS scheduler exactly.

    Spec §Outputs documents this as advisory — DST transitions, system
    sleep, and other quirks of the OS scheduler are not modelled here.
    Simple algorithm: snap ``now`` to ``cadence.hour:cadence.minute``,
    then advance by the period until strictly after ``now``.
    """

    target = now.replace(hour=cadence.hour, minute=cadence.minute, second=0, microsecond=0)
    if cadence.period == "daily":
        if target <= now:
            target += timedelta(days=1)
        return target
    if cadence.period == "weekly":
        assert cadence.day_of_week is not None
        # Our day_of_week: 0=Sun..6=Sat. Python's datetime.weekday(): 0=Mon..6=Sun.
        target_py = (cadence.day_of_week + 6) % 7
        days_ahead = (target_py - now.weekday()) % 7
        if days_ahead == 0 and target <= now:
            days_ahead = 7
        return target + timedelta(days=days_ahead)
    if cadence.period == "monthly":
        assert cadence.day_of_month is not None
        target = target.replace(day=cadence.day_of_month)
        if target <= now:
            month = target.month + 1 if target.month < 12 else 1
            year = target.year if target.month < 12 else target.year + 1
            target = target.replace(year=year, month=month)
        return target
    # quarterly — fire on day_of_month in Jan/Apr/Jul/Oct.
    assert cadence.day_of_month is not None
    candidates: list[datetime] = []
    for month in (1, 4, 7, 10):
        candidate = target.replace(month=month, day=cadence.day_of_month)
        if candidate > now:
            candidates.append(candidate)
        # And the same month next year, in case all of this year's quarter starts are past.
        candidates.append(candidate.replace(year=candidate.year + 1))
    return min(c for c in candidates if c > now)


def _latest_install(
    events: list[Event], operation: str, machine_id: str
) -> ScheduleInstalledEvent | None:
    """Most recent ``ScheduleInstalledEvent`` for ``(operation, machine_id)``.

    Returns ``None`` when no install event exists OR when the most
    recent install is masked by a later ``ScheduleUninstalledEvent``
    on the same ``(operation, machine_id)`` pair. Used by ``install``
    (idempotent / changed-cadence checks) and ``uninstall`` — both
    the pre-transaction early-refusal and the in-transaction
    race-loss re-check on the foreign-machine branch route through
    this helper.
    """

    latest: ScheduleInstalledEvent | None = None
    for event in events:
        if (
            isinstance(event, ScheduleInstalledEvent)
            and event.operation == operation
            and event.machine_id == machine_id
        ):
            latest = event
        elif (
            isinstance(event, ScheduleUninstalledEvent)
            and event.operation == operation
            and event.machine_id == machine_id
        ):
            latest = None
    return latest


def _require_vault(journal_path: Path, vault_root: Path) -> None:
    """Raise WikiError with the standard ``not a wiki vault`` message."""

    if not journal_path.is_file():
        raise WikiError(
            f"not a wiki vault: {vault_root} has no .wiki.journal/journal.jsonl. "
            "Run `wiki init <path> --recipe <name>` first."
        )


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallResult:
    """Return value from :func:`install`.

    ``already_installed`` is True on the idempotent no-op path (zero
    events appended); ``install_instruction`` carries the Windows
    ``schtasks /Create /XML`` line when the emitter provides one, or
    ``None`` on macOS/Linux. ``next_run`` is advisory per spec
    §Outputs.
    """

    operation: str
    machine_id: str
    cadence_dsl: str
    os_artifact_path: Path
    exec_command: list[str]
    next_run: datetime
    already_installed: bool = False
    install_instruction: str | None = None


@dataclass(frozen=True)
class UninstallResult:
    """Return value from :func:`uninstall`.

    ``foreign_machine`` is True when the journaled ``machine_id``
    differs from ``socket.gethostname()``; the OS-side deactivation
    is skipped and a stderr warning is rendered by the CLI handler.
    ``os_artifact_path`` carries the journaled path of the artifact —
    the foreign-machine warning needs it so the user knows what to
    delete on the other host (spec §"uninstall happy path" step 4).
    """

    operation: str
    machine_id: str
    removed_artifact: bool
    os_artifact_path: str
    foreign_machine: bool = False
    uninstall_instruction: str | None = None


@dataclass(frozen=True)
class ScheduleStatus:
    """One row of :func:`list_schedules`.

    ``status`` mirrors spec §Outputs §list: ``ok`` (event + artifact
    agree), ``drift:missing-file`` (event present, file absent),
    ``drift:disabled`` (file present but OS reports disabled —
    macOS/Linux only), ``unknown`` (foreign machine; can't inspect).
    """

    operation: str
    machine_id: str
    cadence_dsl: str
    os_artifact_path: str
    status: Literal["ok", "drift:missing-file", "drift:disabled", "unknown"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def install(
    operation: str,
    *,
    at: str | None,
    machine: str | None,
    vault_root: Path,
    kit_root: Path,
    journal_path: Path,
    now: datetime,
) -> InstallResult:
    """Install (or idempotent re-install) a schedule for ``operation``.

    See ``docs/specs/wiki-schedule/spec.md`` §"install happy path"
    for the canonical sequence. The sequence under
    ``journal.transaction()`` is **write companions → write primary
    → activate → journal**; activation failure best-effort-unlinks
    the primary and skips the journal append. The idempotent
    dup-cadence short-circuit runs *before* the transaction opens,
    so the no-op path emits zero events of any type.
    """

    _require_vault(journal_path, vault_root)

    events = list(read_events(journal_path))
    state = replay_state(events)
    _resolve_operation_kind(
        operation,
        kit_root=kit_root,
        installed_primitive_names=set(state.installed_primitives),
    )

    contract = _load_contract(operation, kit_root)

    # Spec §"install happy path" step 4 puts the period gate BEFORE
    # the cadence-resolution step, so `--at` cannot bypass it. An
    # operation that declared no cadence (period: None or "on-demand")
    # is never schedulable, regardless of whether the user supplied a
    # DSL override.
    if contract.period in (None, "on-demand"):
        raise WikiError(
            f"operation '{operation}' declared no cadence "
            f"(period={contract.period!r}); not schedulable"
        )

    if at is not None:
        try:
            cadence = _parse_dsl(at)
        except WikiError as exc:
            raise WikiError(f"--at: {exc}") from exc
    else:
        cadence = _resolve_default_cadence(contract)
    cadence_dsl = _canonicalize_cadence(cadence)

    machine_id = machine if machine is not None else socket.gethostname()

    emitter = _resolve_emitter()
    vault_id = _vault_id(vault_root)
    artifact_path = emitter.artifact_path(vault_id, operation)

    # Idempotent / changed-cadence check runs BEFORE the transaction
    # opens, so the no-op path emits zero events (spec §Invariants).
    prior = _latest_install(events, operation, machine_id)
    if prior is not None:
        if prior.cadence_dsl == cadence_dsl:
            return InstallResult(
                operation=operation,
                machine_id=machine_id,
                cadence_dsl=cadence_dsl,
                os_artifact_path=Path(prior.os_artifact_path),
                exec_command=list(prior.exec_command),
                next_run=_next_run(cadence, now),
                already_installed=True,
                install_instruction=None,
            )
        raise WikiError(
            f"schedule already installed for {operation} on {machine_id} "
            f"with cadence {prior.cadence_dsl!r}; uninstall first or pass --at to change"
        )

    exec_command = _resolve_exec_command(operation)

    companions = emitter.companion_artifacts(
        operation=operation,
        vault_root=vault_root,
        vault_id=vault_id,
        cadence=cadence,
        exec_command=exec_command,
    )
    primary_body = emitter.render_artifact(
        operation=operation,
        vault_root=vault_root,
        vault_id=vault_id,
        cadence=cadence,
        exec_command=exec_command,
    )

    race_winner: ScheduleInstalledEvent | None = None
    with transaction(journal_path, by=SCHEDULE_VEHICLE, reason=f"install {operation}"):
        # TOCTOU race re-check: the pre-transaction scan above ran
        # without the flock; a competing `wiki schedule install` could
        # have landed between then and now. Re-read events under the
        # lock and re-evaluate so we don't journal a duplicate event
        # (spec §Invariants "at most one ScheduleInstalledEvent" /
        # §Risks "Race between two `wiki schedule install` calls").
        prior_in_tx = _latest_install(list(read_events(journal_path)), operation, machine_id)
        if prior_in_tx is not None:
            if prior_in_tx.cadence_dsl != cadence_dsl:
                raise WikiError(
                    f"schedule already installed for {operation} on "
                    f"{machine_id} with cadence {prior_in_tx.cadence_dsl!r} "
                    f"(installed concurrently by another process); "
                    f"uninstall first or pass --at to change"
                )
            # Concurrent winner had the same cadence — race-induced
            # idempotent. Skip the writes/activate/journal append and
            # return as the no-op variant. The enclosing transaction
            # still emits its lock-pair; we accept that noise as the
            # cost of race-safety (spec §"install happy path" step 8
            # calls out lock-pair-without-payload as the journal-grep
            # signal for a failed install, and a race-induced no-op
            # is a benign sub-case of that signal).
            race_winner = prior_in_tx
        else:
            for companion_path, companion_body in companions:
                write_os_artifact(companion_path, companion_body, vault_root=vault_root)
            write_os_artifact(artifact_path, primary_body, vault_root=vault_root)
            try:
                emitter.activate(artifact_path)
            except Exception:
                # Best-effort unlink the primary artifact. Companions
                # are NOT unlinked — they're harmless orphans (spec
                # §Invariants "install writes one file (or two on
                # Linux)"; uninstall doesn't delete them either).
                try:
                    artifact_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            append_event(
                journal_path,
                ScheduleInstalledEvent(
                    timestamp=now,
                    by=SCHEDULE_VEHICLE,
                    operation=operation,
                    machine_id=machine_id,
                    cadence_dsl=cadence_dsl,
                    os_artifact_path=str(artifact_path),
                    exec_command=exec_command,
                ),
            )

    if race_winner is not None:
        # Mirror the pre-transaction idempotent return: pull the
        # artifact path and exec_command from the winner's journaled
        # event, mark `already_installed=True` so the CLI prints the
        # "no change" line rather than a misleading "Installed
        # schedule … activation: …" block.
        return InstallResult(
            operation=operation,
            machine_id=machine_id,
            cadence_dsl=cadence_dsl,
            os_artifact_path=Path(race_winner.os_artifact_path),
            exec_command=list(race_winner.exec_command),
            next_run=_next_run(cadence, now),
            already_installed=True,
            install_instruction=None,
        )

    return InstallResult(
        operation=operation,
        machine_id=machine_id,
        cadence_dsl=cadence_dsl,
        os_artifact_path=artifact_path,
        exec_command=exec_command,
        next_run=_next_run(cadence, now),
        install_instruction=emitter.install_instruction(artifact_path),
    )


def uninstall(
    operation: str,
    *,
    machine: str | None,
    vault_root: Path,
    journal_path: Path,
    now: datetime,
) -> UninstallResult:
    """Uninstall a schedule for ``operation``.

    See ``docs/specs/wiki-schedule/spec.md`` §"uninstall happy path".
    Current-host uninstall runs **deactivate → delete → journal**
    inside ``journal.transaction()``; foreign-machine uninstall
    (``machine`` differs from ``socket.gethostname()``) skips the
    OS-side calls, journals ``removed_artifact=False``, and lets the
    CLI render a stderr warning.
    """

    _require_vault(journal_path, vault_root)

    machine_id = machine if machine is not None else socket.gethostname()
    events = list(read_events(journal_path))
    prior = _latest_install(events, operation, machine_id)
    if prior is None:
        raise WikiError(f"no schedule installed for {operation} on {machine_id}")

    artifact_path = Path(prior.os_artifact_path)
    current_host = socket.gethostname()
    foreign = machine_id != current_host

    if foreign:
        # No OS-side access. Journal the user's intent + let the CLI
        # render the "remove the artifact manually on that host"
        # warning. Crucially, the artifact at the journaled path is
        # NOT touched on the local filesystem — even if a file
        # happens to exist there (vault-id collision, shared home),
        # the foreign-machine branch must not unlink it.
        #
        # The append runs under `journal.transaction()` so the
        # pre-read above + the append are serialized against a
        # competing `wiki schedule uninstall` for the same
        # `(operation, machine_id)` pair landing between them (spec
        # §"uninstall happy path" step 4 "Foreign machine";
        # §Invariants "Either both happen or neither does" extended
        # to cover this single-append case). The pre-transaction
        # read is retained as the cheap early-refusal path so a
        # clearly-missing schedule does not pay the lock-pair cost
        # (CT-9 invariant: zero events on refusal). Not extracted
        # into a shared helper with the current-host branch below:
        # that branch interleaves `emitter.deactivate()` and
        # `artifact_path.unlink()` inside the same transaction, so
        # the shared surface would be the two-line read+re-check
        # — not worth the helper's parameter shape.
        try:
            emitter: _Emitter | None = _resolve_emitter()
        except WikiError:
            # Unsupported OS: spec §"Edge cases / Running on an
            # unsupported OS" says uninstall still works (journal
            # append). No instruction to print.
            emitter = None
        with transaction(journal_path, by=SCHEDULE_VEHICLE, reason=f"uninstall {operation}"):
            # TOCTOU re-check under the flock: a competing uninstall
            # may have landed between the pre-read above and this
            # acquire. Mirrors install()'s in-transaction re-read.
            prior_locked = _latest_install(list(read_events(journal_path)), operation, machine_id)
            if prior_locked is None:
                # Discriminator on the message so a user-reported refusal
                # can be classified at command time without journal grep —
                # this branch only fires on the rare race; the pre-read
                # refusal at line ~529 uses the bare message.
                raise WikiError(
                    f"no schedule installed for {operation} on {machine_id} "
                    f"(concurrent uninstall observed under lock; "
                    f"re-check the journal)"
                )
            # Source the result payload from the locked view rather than
            # the lockless pre-read; today the two events agree (no event
            # type rewrites os_artifact_path in place), but tracking the
            # under-lock confirmation future-proofs the coupling.
            prior = prior_locked
            append_event(
                journal_path,
                ScheduleUninstalledEvent(
                    timestamp=now,
                    by=SCHEDULE_VEHICLE,
                    operation=operation,
                    machine_id=machine_id,
                    removed_artifact=False,
                ),
            )
        return UninstallResult(
            operation=operation,
            machine_id=machine_id,
            removed_artifact=False,
            os_artifact_path=prior.os_artifact_path,
            foreign_machine=True,
            uninstall_instruction=(
                emitter.uninstall_instruction(artifact_path) if emitter is not None else None
            ),
        )

    emitter = _resolve_emitter()
    with transaction(journal_path, by=SCHEDULE_VEHICLE, reason=f"uninstall {operation}"):
        # Deactivate is best-effort (spec §"uninstall happy path"):
        # non-zero exit is logged by the emitter but does not raise.
        emitter.deactivate(artifact_path)
        removed = False
        try:
            if artifact_path.is_file():
                artifact_path.unlink()
                removed = True
        except OSError as exc:
            # Unlink failed (permission, etc.) — record as not-removed
            # and proceed; the journal event still records the user's
            # intent. Surface the failure on stderr so the user sees
            # it at command time (`wiki doctor` will also flag the
            # stale artifact later).
            print(
                f"wiki schedule: warning: failed to remove artifact at {artifact_path} "
                f"for {operation} on {machine_id}: {exc}",
                file=sys.stderr,
            )
            removed = False
        append_event(
            journal_path,
            ScheduleUninstalledEvent(
                timestamp=now,
                by=SCHEDULE_VEHICLE,
                operation=operation,
                machine_id=machine_id,
                removed_artifact=removed,
            ),
        )

    return UninstallResult(
        operation=operation,
        machine_id=machine_id,
        removed_artifact=removed,
        os_artifact_path=prior.os_artifact_path,
        foreign_machine=False,
        uninstall_instruction=emitter.uninstall_instruction(artifact_path),
    )


def list_schedules(
    *,
    machine: str | None,
    all_machines: bool,
    vault_root: Path,
    journal_path: Path,
) -> list[ScheduleStatus]:
    """Read-only: replay journal + compare against OS-side reality.

    Returns a list of :class:`ScheduleStatus` rows, one per live
    ``(operation, machine_id)`` pair. Live = the most recent
    ``ScheduleInstalledEvent`` for that pair has no later
    ``ScheduleUninstalledEvent`` masking it. Foreign-machine entries
    are included only when ``all_machines=True``; the ``machine``
    filter (if set) restricts to a single machine.
    """

    _require_vault(journal_path, vault_root)

    current_host = socket.gethostname()
    events = list(read_events(journal_path))

    # Aggregate per (operation, machine_id): the most recent install
    # that isn't masked by a later uninstall.
    live: dict[tuple[str, str], ScheduleInstalledEvent] = {}
    for event in events:
        if isinstance(event, ScheduleInstalledEvent):
            live[(event.operation, event.machine_id)] = event
        elif isinstance(event, ScheduleUninstalledEvent):
            live.pop((event.operation, event.machine_id), None)

    emitter: _Emitter | None
    try:
        emitter = _resolve_emitter()
    except WikiError:
        # On unsupported OS, list still works for journal-side readout
        # (spec §"Edge cases / Running on an unsupported OS"). The
        # emitter is only needed for the OS-side `inspect` call on
        # current-host rows.
        emitter = None

    rows: list[ScheduleStatus] = []
    for (operation, machine_id), event in sorted(live.items()):
        if machine is not None and machine_id != machine:
            continue
        if machine_id != current_host and not all_machines and machine is None:
            continue
        artifact_path = Path(event.os_artifact_path)
        status: Literal["ok", "drift:missing-file", "drift:disabled", "unknown"]
        if machine_id != current_host:
            status = "unknown"
        elif emitter is None:
            status = "unknown"
        else:
            inspect_result: InspectResult = emitter.inspect(artifact_path)
            if inspect_result == "missing-file":
                status = "drift:missing-file"
            elif inspect_result == "loaded":
                status = "ok"
            elif inspect_result == "not-loaded":
                status = "drift:disabled"
            else:
                # "not-inspectable" — Windows v1; treat file-present as ok.
                status = "ok"
        rows.append(
            ScheduleStatus(
                operation=operation,
                machine_id=machine_id,
                cadence_dsl=event.cadence_dsl,
                os_artifact_path=event.os_artifact_path,
                status=status,
            )
        )
    return rows
