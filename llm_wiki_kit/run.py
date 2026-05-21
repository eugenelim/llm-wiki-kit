"""Contract-driven dispatch for ``wiki run`` (RFC-0001 Task 17).

The kit ships no LLM (charter principle: library-not-application), so
``wiki run`` is not the actor that performs the operation. It is the
deterministic **dispatch boundary**: validate the user-supplied
arguments against the operation primitive's ``contract.yaml``, record
one ``OperationRunEvent`` in the journal, print a one-liner pointing
the user's Claude session at the corresponding SKILL.md, exit. The
SKILL is what reads vault pages, synthesises the digest, and writes
the result via ``safe_write``.

Behavior, edge cases, invariants, and acceptance tests live in
``docs/specs/task-17-wiki-run/spec.md``. The plan is in
``docs/specs/task-17-wiki-run/plan.md``. Don't reason about this
module without reading those.

Module contract: one public function, :func:`dispatch`. The inner
helpers (:func:`_parse_op_args`, :func:`_coerce_input`,
:func:`_load_contract`, :func:`_resolve_operation_kind`) are pure
and tested directly under ``tests/unit/test_run*.py``.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event, read_events, replay_state
from llm_wiki_kit.models import (
    OperationContract,
    OperationInputSpec,
    OperationRunEvent,
    Primitive,
    PrimitiveKind,
)

# Hex pattern for ``dispatch_event_id`` shape validation. 12 lowercase
# hex chars — first 12 of ``uuid.uuid4().hex``. See
# ``docs/specs/wiki-run-exec/spec.md`` §"Event identity".
_EVENT_ID_RE = re.compile(r"^[0-9a-f]{12}$")
from llm_wiki_kit.primitives import discover_primitives, load_primitive

# Vehicle name recorded on every ``OperationRunEvent`` this module emits.
# Pinned by the spec — cross-task ``by`` values are how ``wiki doctor``
# and ``journal grep`` attribute actions to the actor that produced
# them.
RUN_VEHICLE = "wiki-run"

# Truthy / falsy spellings accepted for ``type: boolean``. Inlined here
# rather than imported from ``cli._WIKI_DEBUG_TRUTHY``: the two domains
# are independent (one is a CLI debug-mode toggle, the other is a
# contract-input vocabulary) and pulling them together would couple
# unrelated concerns.
_BOOL_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSY: frozenset[str] = frozenset({"0", "false", "no", "off"})

# ISO 8601 week-date format, bounded to legal week numbers (W01-W53).
# Calendar-validity (does year X actually have W53?) is intentionally
# out of scope — see spec §Non-goals.
_ISO_WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")


# ---------------------------------------------------------------------------
# Pure helpers — argument parsing
# ---------------------------------------------------------------------------


class ArgCoercionError(Exception):
    """Raised by :func:`_coerce_input` when a value fails type coercion.

    Internal to :mod:`llm_wiki_kit.run`; :func:`dispatch` catches it and
    translates to the user-facing one-line error message. Not a
    :class:`WikiError` because it doesn't ride the CLI boundary
    directly — every invocation that produces an ``ArgCoercionError``
    still journals an ``OperationRunEvent(status="invalid_args")``.
    """

    def __init__(self, value: str, expected: str) -> None:
        self.value = value
        self.expected = expected
        super().__init__(f"expected {expected}, got {value!r}")


def _normalise_name(name: str) -> str:
    """Lower-case + kebab→snake. Pinned by spec §Inputs."""

    return name.lower().replace("-", "_")


def _parse_op_args(tokens: list[str]) -> dict[str, str]:
    """Parse raw CLI tokens into a name→value dict.

    Each token must match ``--<name>=<value>`` or ``--<name>`` (the
    latter records the sentinel string ``"true"``). Names are
    normalised via :func:`_normalise_name` before becoming dict keys
    so kebab and snake spellings collapse onto the same field. Last
    write to a given name wins on value, but the name's iteration
    position is set by its first occurrence — see spec §Behavior
    step 7 §"Error-precedence rule".

    Raises :class:`WikiError` on shape failures (positional token,
    bare ``--``, empty-name ``--=value``). Shape failures abort the
    parse before any journal write so no event is recorded for a
    malformed argv.
    """

    result: dict[str, str] = {}
    for token in tokens:
        if not token.startswith("--"):
            raise WikiError(f"malformed argument: {token!r}: expected --name=value")
        body = token[2:]
        if not body:
            raise WikiError(f"malformed argument: {token!r}: expected --name=value")
        if "=" in body:
            name, _, value = body.partition("=")
        else:
            name = body
            value = "true"
        if not name:
            raise WikiError(f"malformed argument: {token!r}: empty name")
        result[_normalise_name(name)] = value
    return result


def _coerce_input(raw_value: str, spec: OperationInputSpec) -> object:
    """Coerce a raw user string against an :class:`OperationInputSpec`.

    Type tags handled: ``string``, ``integer``/``int``, ``boolean``,
    ``iso_week``, ``list``. Anything else falls through as ``str``
    — forward-compat for new tags (e.g. ``page`` in ``trip-prep``)
    before the kit grows dedicated coercions. Raises
    :class:`ArgCoercionError` on type-mismatch.
    """

    type_ = spec.type
    if type_ == "string":
        return raw_value
    if type_ in ("integer", "int"):
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ArgCoercionError(raw_value, "integer") from exc
    if type_ == "boolean":
        lowered = raw_value.lower()
        if lowered in _BOOL_TRUTHY:
            return True
        if lowered in _BOOL_FALSY:
            return False
        raise ArgCoercionError(raw_value, "boolean (true/false/yes/no/1/0/on/off)")
    if type_ == "iso_week":
        if _ISO_WEEK_RE.fullmatch(raw_value):
            return raw_value
        raise ArgCoercionError(raw_value, "iso_week (YYYY-Www, W01-W53)")
    if type_ == "list":
        if raw_value == "":
            return []
        return [element.strip() for element in raw_value.split(",")]
    # Unknown type — accept verbatim. The SKILL is responsible for any
    # further validation (e.g. resolving a `type: page` wikilink).
    return raw_value


# ---------------------------------------------------------------------------
# Contract + kind resolution
# ---------------------------------------------------------------------------


def _operation_contract_path(operation: str, kit_root: Path) -> Path:
    return kit_root / "templates" / "operations" / operation / "contract.yaml"


def _load_contract(operation: str, kit_root: Path) -> OperationContract:
    """Read and validate ``templates/operations/<operation>/contract.yaml``.

    Raises :class:`WikiError` with the absolute path on a missing
    file (the kit-version-skew case — primitive is installed in the
    journal but its contract file disappeared from disk).
    """

    path = _operation_contract_path(operation, kit_root)
    if not path.is_file():
        raise WikiError(f"operation {operation!r}: no contract.yaml at {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OperationContract.model_validate(payload)


def _resolve_operation_kind(
    operation: str,
    *,
    kit_root: Path,
    installed_primitive_names: set[str],
) -> None:
    """Verify ``operation`` is installed AND has kind ``operation``.

    Looks the primitive up in the full discovered catalog
    (``core`` + ``templates/``) so a content-type installed under
    the operation name gives a clean kind-mismatch error rather
    than a confusing missing-contract error. Raises
    :class:`WikiError` on either failure.
    """

    if operation not in installed_primitive_names:
        installed_sorted = ", ".join(sorted(installed_primitive_names)) or "(none)"
        raise WikiError(
            f"operation {operation!r} is not installed in this vault. "
            f"Installed primitives: {installed_sorted}"
        )

    core_dir = kit_root / "core"
    templates_dir = kit_root / "templates"
    catalog: list[Primitive] = []
    if core_dir.is_dir():
        catalog.append(load_primitive(core_dir))
    if templates_dir.is_dir():
        catalog.extend(discover_primitives(templates_dir))

    target = next((p for p in catalog if p.name == operation), None)
    if target is None:
        # In the journal but not on disk — kit-version skew.
        # _load_contract will raise the path-bearing error a moment
        # later; raise the same shape here so callers see one
        # consistent message.
        raise WikiError(
            f"operation {operation!r} is installed but not present in "
            f"the kit's catalog (searched {core_dir} and {templates_dir})"
        )
    if target.kind is not PrimitiveKind.OPERATION:
        raise WikiError(
            f"{operation!r} is installed but its kind is {target.kind.value!r}, not 'operation'"
        )


# ---------------------------------------------------------------------------
# DispatchResult
# ---------------------------------------------------------------------------


@dataclass
class DispatchResult:
    """In-memory return value from :func:`dispatch`.

    ``status`` is bounded to the two values the journal records;
    ``__post_init__`` enforces the spec §Invariants rule "error is
    non-None iff status==invalid_args". The kit's `--help`
    short-circuit lives at the CLI boundary, not here — dispatch
    only sees real invocations.

    ``dispatch_event_id`` carries the ``event_id`` the kit
    generated and journaled on the surviving ``OperationRunEvent``
    (see ``docs/specs/wiki-run-exec/spec.md`` §"DispatchResult
    extension"). Required field, ordered before defaulted fields
    so Python's ``@dataclass`` field-ordering rule holds.
    ``__post_init__`` validates the shape (12 lowercase hex).
    """

    status: Literal["dispatched", "invalid_args"]
    operation: str
    parsed: dict[str, object]
    args_raw: dict[str, str]
    period: str | None
    skill: str
    dispatch_event_id: str
    error: str | None = None
    produced_pages: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status == "invalid_args" and self.error is None:
            raise ValueError("DispatchResult: status='invalid_args' requires a non-None error")
        if self.status == "dispatched" and self.error is not None:
            raise ValueError("DispatchResult: status='dispatched' must have error=None")
        if not _EVENT_ID_RE.fullmatch(self.dispatch_event_id):
            raise ValueError(
                "DispatchResult: dispatch_event_id must be 12 lowercase hex chars; "
                f"got {self.dispatch_event_id!r}"
            )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def _skill_or_default(contract: OperationContract) -> str:
    """Return the skill the dispatch line names. Empty/absent → operation."""

    if contract.skill:
        return contract.skill
    return contract.name


def dispatch(
    operation: str,
    raw_args: list[str],
    *,
    vault_root: Path,
    kit_root: Path,
    journal_path: Path,
    now: datetime,
) -> DispatchResult:
    """Validate args against the operation contract and journal the run.

    See ``docs/specs/task-17-wiki-run/spec.md`` §Behavior for the
    canonical sequence. Pre-load failures (vault check, unknown
    operation, kind mismatch, missing contract.yaml) raise
    :class:`WikiError` and do **not** journal. Post-load failures
    (unknown argument name, type-coercion failure) produce one
    ``OperationRunEvent(status="invalid_args")`` and a
    ``DispatchResult`` carrying the error message.

    Vault root is accepted for symmetry with other dispatch-shaped
    handlers (``wiki ingest`` etc.); the function does not currently
    read anything under it beyond what ``journal_path`` covers, but
    naming it explicitly keeps the seam available for a future
    pre-flight check (e.g. validating that produced-page paths fit
    inside the vault).

    **Installed-state staleness is intentional.** The
    ``read_events`` → ``_resolve_operation_kind`` → ``append_event``
    sequence is *not* wrapped in a ``transaction()``. A concurrent
    ``wiki upgrade`` or ``wiki remove`` could in principle land
    between the installed-check and the journal append, leaving us
    journaling a dispatch for a primitive that's just been
    uninstalled. This is by design: ``wiki run`` is read-only on the
    installed catalog, and the journal-append-only model
    (ADR-0002) already accepts this kind of state staleness across
    every command. The single append itself is locked via
    ``append_event``'s ``flock``; that's the only synchronization
    point.
    """

    # vault_root is reserved for future pre-flight checks; reference
    # it once so static analysis can't flag the unused parameter.
    _ = vault_root

    events = list(read_events(journal_path))
    state = replay_state(events)

    _resolve_operation_kind(
        operation,
        kit_root=kit_root,
        installed_primitive_names=set(state.installed_primitives),
    )

    contract = _load_contract(operation, kit_root)
    skill = _skill_or_default(contract)

    raw = _parse_op_args(raw_args)

    # Walk in dict iteration order — first-occurrence position of each
    # name in the user's typed tokens. First failure wins.
    parsed: dict[str, object] = {}
    error: str | None = None
    for name, value in raw.items():
        spec = contract.inputs.get(name)
        if spec is None:
            error = f"--{name}: unknown argument"
            break
        try:
            parsed[name] = _coerce_input(value, spec)
        except ArgCoercionError as exc:
            error = f"--{name}: {exc}"
            break

    if error is None:
        # Apply defaults for any field the user didn't supply.
        for field_name, spec in contract.inputs.items():
            if field_name in parsed:
                continue
            if spec.default is not None:
                parsed[field_name] = spec.default

    status: Literal["dispatched", "invalid_args"] = (
        "invalid_args" if error is not None else "dispatched"
    )

    event_id = uuid.uuid4().hex[:12]

    append_event(
        journal_path,
        OperationRunEvent(
            timestamp=now,
            by=RUN_VEHICLE,
            operation=operation,
            status=status,
            period=contract.period,
            produced_pages=[],
            args=raw,
            error=error,
            event_id=event_id,
        ),
    )

    return DispatchResult(
        status=status,
        operation=operation,
        parsed=parsed,
        args_raw=raw,
        period=contract.period,
        skill=skill,
        dispatch_event_id=event_id,
        error=error,
    )
