"""Cadence DSL parser, default-fill table, and per-OS converters.

Contract pinned in ``docs/specs/wiki-schedule/spec.md`` §Inputs and
plan step 3 in ``docs/specs/wiki-schedule/plan.md``. The DSL is the
human-typeable cadence vocabulary the ``wiki schedule install --at "<dsl>"``
flag accepts; ``resolve_default`` is the contract-driven fallback for
when ``--at`` is omitted. The three ``to_*`` converters are consumed by
the per-OS emitters (PR-4 launchd, PR-6 systemd, PR-7 Task Scheduler);
golden-string assertions for each artifact format live in those PRs.

Cron strings are not accepted — RFC-0003 §"Cadence vocabulary". The
parser raises ``WikiError`` with the same message phrasing the spec
quotes in CT-4 so the CLI error stays stable across the eight PRs in
this series.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal
from xml.etree import ElementTree as ET

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import OperationContract

PeriodKind = Literal["daily", "weekly", "monthly", "quarterly"]


# Single source of truth for the default fire time per ``period:`` value,
# referenced from spec §Invariants. Mirrored in
# ``test_schedule_dsl.py::test_default_time_by_period_constant_matches_spec_inputs_table``
# so a drift here fails loudly.
DEFAULT_TIME_BY_PERIOD: Final[dict[str, str]] = {
    "daily": "07:00",
    "weekly": "09:00",
    "monthly": "09:00",
    "quarterly": "09:00",
}

# Launchd ``StartCalendarInterval.Weekday`` uses 0=Sunday..6=Saturday
# (spec CT-2). The same numeric encoding is reused on the ``ResolvedCadence``
# struct so emitters that consume other encodings (systemd ``Sun..Sat``,
# Task Scheduler ``<Sunday/>``) translate from one canonical integer.
_DAY_TOKEN_TO_WEEKDAY: Final[dict[str, int]] = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}

_WEEKDAY_TO_SYSTEMD: Final[dict[int, str]] = {
    0: "Sun",
    1: "Mon",
    2: "Tue",
    3: "Wed",
    4: "Thu",
    5: "Fri",
    6: "Sat",
}

_WEEKDAY_TO_TASK_SCHEDULER: Final[dict[int, str]] = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}

# Quarterly fires in months 1/4/7/10 — the four quarter starts. Shared
# between the three per-OS converters: ``to_systemd_oncalendar`` joins
# the months into the OnCalendar string; ``to_launchd_calendar_interval``
# emits one StartCalendarInterval dict per month; ``to_task_scheduler_trigger``
# adds them as ``<Months>`` children. One source of truth for "what does
# quarterly mean."
QUARTERLY_MONTHS: Final[tuple[int, int, int, int]] = (1, 4, 7, 10)

_HHMM_PATTERN: Final[re.Pattern[str]] = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Shape error returned for every malformed DSL input. Quoting the form
# verbatim from spec §Inputs keeps the CLI error stable across releases.
# The CLI handler (PR-5's `_cmd_schedule_install`) prepends `--at: ` to
# match the spec §Inputs wording when the input came from the flag; the
# library function leaves the message unprefixed because the same parser
# serves contract-driven defaults too.
_DSL_ERROR_MESSAGE: Final[str] = (
    "unrecognised cadence DSL; accepted forms: 'daily HH:MM', "
    "'<DAY> HH:MM', 'monthly <DD> HH:MM', 'quarterly <DD> HH:MM'"
)

# Cron-string nudge per spec §"Edge cases" — when the input looks like
# a five-field cron expression, the error appends a clearer hint than the
# generic accepted-forms list. Match is intentionally loose (mostly digits,
# stars, slashes, commas) to catch the common shapes a user might type.
_CRON_FIELD_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[\d*/,\-]+$")
_CRON_HINT: Final[str] = "; cron strings are not accepted (RFC-0003 §'Cadence vocabulary')"


@dataclass(frozen=True)
class ResolvedCadence:
    """A parsed cadence, ready for an emitter to render.

    Internal to ``llm_wiki_kit.schedule``; not exported from the package
    namespace (PR-5 owns the public install/uninstall/list surface).
    ``day_of_week`` is 0=Sunday..6=Saturday; ``day_of_month`` is 1..28
    (the spec caps at 28 so no month rolls over).
    """

    period: PeriodKind
    hour: int
    minute: int
    day_of_week: int | None = None
    day_of_month: int | None = None


def parse(dsl: str) -> ResolvedCadence:
    """Parse a cadence DSL string.

    Grammar pinned by ``docs/specs/wiki-schedule/spec.md`` §Inputs:
    ``daily HH:MM``, ``<DAY> HH:MM`` (SUN..SAT, case-insensitive),
    ``monthly <DD> HH:MM`` (DD ∈ 1..28), ``quarterly <DD> HH:MM``
    (DD ∈ 1..28). Cron strings and any other form raise
    ``WikiError`` with the exact spec-mandated phrasing.
    """

    tokens = dsl.split()
    if len(tokens) < 2:
        raise WikiError(_dsl_error_for(tokens))

    head = tokens[0]
    head_upper = head.upper()

    # <DAY> HH:MM — weekly cadence.
    if head_upper in _DAY_TOKEN_TO_WEEKDAY:
        if len(tokens) != 2:
            raise WikiError(_dsl_error_for(tokens))
        hour, minute = _parse_hhmm_in_context(tokens[1], tokens)
        return ResolvedCadence(
            period="weekly",
            hour=hour,
            minute=minute,
            day_of_week=_DAY_TOKEN_TO_WEEKDAY[head_upper],
        )

    head_lower = head.lower()

    if head_lower == "daily":
        if len(tokens) != 2:
            raise WikiError(_dsl_error_for(tokens))
        hour, minute = _parse_hhmm_in_context(tokens[1], tokens)
        return ResolvedCadence(period="daily", hour=hour, minute=minute)

    if head_lower == "monthly":
        return _parse_day_of_month_form("monthly", tokens)

    if head_lower == "quarterly":
        return _parse_day_of_month_form("quarterly", tokens)

    raise WikiError(_dsl_error_for(tokens))


def resolve_default(contract: OperationContract) -> ResolvedCadence:
    """Compute the default cadence for an operation whose ``--at`` was omitted.

    Honors ``contract.default_time`` when set, otherwise falls back to
    ``DEFAULT_TIME_BY_PERIOD[contract.period]``. Refuses ``period: on-demand``
    (spec CT-3) and any other ``period:`` value not in the table (spec
    §Inputs).
    """

    period = contract.period
    if period == "on-demand":
        raise WikiError(
            f"operation '{contract.name}' is on-demand only (period=on-demand); not schedulable"
        )
    if period is None or period not in DEFAULT_TIME_BY_PERIOD:
        raise WikiError(
            f"operation '{contract.name}' declared no cadence (period={period!r}); not schedulable"
        )

    default_time = contract.default_time or DEFAULT_TIME_BY_PERIOD[period]
    hour, minute = _parse_hhmm(default_time)

    if period == "daily":
        return ResolvedCadence(period="daily", hour=hour, minute=minute)
    if period == "weekly":
        return ResolvedCadence(period="weekly", hour=hour, minute=minute, day_of_week=0)
    if period == "monthly":
        return ResolvedCadence(period="monthly", hour=hour, minute=minute, day_of_month=1)
    # period == "quarterly" — exhaustive: `period in DEFAULT_TIME_BY_PERIOD`
    # already screened.
    return ResolvedCadence(period="quarterly", hour=hour, minute=minute, day_of_month=1)


def to_systemd_oncalendar(cadence: ResolvedCadence) -> str:
    """Render a systemd ``OnCalendar=`` value for the given cadence.

    Format reference: ``man systemd.time(7)`` calendar events. Tested
    end-to-end against ``systemd-analyze calendar`` in the systemd
    emitter PR (plan step 6).
    """

    time_part = f"{cadence.hour:02d}:{cadence.minute:02d}:00"

    if cadence.period == "daily":
        return f"*-*-* {time_part}"
    if cadence.period == "weekly":
        assert cadence.day_of_week is not None
        day_name = _WEEKDAY_TO_SYSTEMD[cadence.day_of_week]
        return f"{day_name} *-*-* {time_part}"
    if cadence.period == "monthly":
        assert cadence.day_of_month is not None
        return f"*-*-{cadence.day_of_month:02d} {time_part}"
    # quarterly — fire on day_of_month of Jan/Apr/Jul/Oct.
    assert cadence.day_of_month is not None
    months = ",".join(f"{m:02d}" for m in QUARTERLY_MONTHS)
    return f"*-{months}-{cadence.day_of_month:02d} {time_part}"


def to_launchd_calendar_interval(cadence: ResolvedCadence) -> list[dict[str, int]]:
    """Render launchd ``StartCalendarInterval`` entries for the given cadence.

    Returns a list because launchd treats ``StartCalendarInterval`` as
    either a single dict or an array of dicts (one trigger per element).
    Daily / weekly / monthly cadences produce a one-element list; a
    quarterly cadence produces a four-element list — one entry per month
    in ``QUARTERLY_MONTHS`` — so the launchd emitter (PR-4) can hand the
    whole list straight to ``plistlib`` without computing the quarterly
    fan-out itself. Launchd's ``Weekday`` integer follows the convention
    spec CT-2 pins: Sunday=0, Monday=1, …, Saturday=6.
    """

    base: dict[str, int] = {"Hour": cadence.hour, "Minute": cadence.minute}
    if cadence.period == "daily":
        return [base]
    if cadence.period == "weekly":
        assert cadence.day_of_week is not None
        return [{"Weekday": cadence.day_of_week, **base}]
    if cadence.period == "monthly":
        assert cadence.day_of_month is not None
        return [{"Day": cadence.day_of_month, **base}]
    # quarterly — fan out one dict per quarter-start month.
    assert cadence.day_of_month is not None
    return [{"Month": month, "Day": cadence.day_of_month, **base} for month in QUARTERLY_MONTHS]


def to_task_scheduler_trigger(cadence: ResolvedCadence) -> ET.Element:
    """Render a Task Scheduler ``<CalendarTrigger>`` element.

    Returns one ``<CalendarTrigger>`` element ready to insert under
    ``<Triggers>``. The Task Scheduler emitter (PR-7) wraps it in the
    full task envelope. ``StartBoundary`` carries an arbitrary anchor
    date (``2026-01-01T<HH:MM>:00``); Task Scheduler uses only the
    time-of-day portion in combination with the ``<ScheduleBy*>`` block.
    """

    trigger = ET.Element("CalendarTrigger")
    start_boundary = ET.SubElement(trigger, "StartBoundary")
    start_boundary.text = f"2026-01-01T{cadence.hour:02d}:{cadence.minute:02d}:00"
    enabled = ET.SubElement(trigger, "Enabled")
    enabled.text = "true"

    if cadence.period == "daily":
        schedule = ET.SubElement(trigger, "ScheduleByDay")
        ET.SubElement(schedule, "DaysInterval").text = "1"
    elif cadence.period == "weekly":
        assert cadence.day_of_week is not None
        schedule = ET.SubElement(trigger, "ScheduleByWeek")
        ET.SubElement(schedule, "WeeksInterval").text = "1"
        days_of_week = ET.SubElement(schedule, "DaysOfWeek")
        ET.SubElement(days_of_week, _WEEKDAY_TO_TASK_SCHEDULER[cadence.day_of_week])
    elif cadence.period == "monthly":
        assert cadence.day_of_month is not None
        schedule = ET.SubElement(trigger, "ScheduleByMonth")
        days_of_month = ET.SubElement(schedule, "DaysOfMonth")
        ET.SubElement(days_of_month, "Day").text = str(cadence.day_of_month)
        months = ET.SubElement(schedule, "Months")
        for month_name in (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ):
            ET.SubElement(months, month_name)
    else:
        # quarterly — fire in Jan/Apr/Jul/Oct on the configured day.
        assert cadence.day_of_month is not None
        schedule = ET.SubElement(trigger, "ScheduleByMonth")
        days_of_month = ET.SubElement(schedule, "DaysOfMonth")
        ET.SubElement(days_of_month, "Day").text = str(cadence.day_of_month)
        months = ET.SubElement(schedule, "Months")
        for month_name in ("January", "April", "July", "October"):
            ET.SubElement(months, month_name)

    return trigger


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_hhmm(token: str) -> tuple[int, int]:
    """Split a zero-padded ``HH:MM`` string into integers.

    Caller is responsible for catching the ``WikiError`` and re-raising
    with a context-appropriate message (the ``parse()`` path adds a
    cron-shape hint; ``resolve_default()`` only reaches here if a
    ``model_construct`` bypass injected a bad ``default_time``).
    """

    match = _HHMM_PATTERN.match(token)
    if not match:
        raise WikiError(_DSL_ERROR_MESSAGE)
    return int(match.group(1)), int(match.group(2))


def _parse_day_of_month_form(period: PeriodKind, tokens: list[str]) -> ResolvedCadence:
    if len(tokens) != 3:
        raise WikiError(_dsl_error_for(tokens))
    try:
        day = int(tokens[1])
    except ValueError as exc:
        raise WikiError(_dsl_error_for(tokens)) from exc
    if not 1 <= day <= 28:
        raise WikiError(_dsl_error_for(tokens))
    hour, minute = _parse_hhmm_in_context(tokens[2], tokens)
    return ResolvedCadence(
        period=period,
        hour=hour,
        minute=minute,
        day_of_month=day,
    )


def _parse_hhmm_in_context(token: str, tokens: list[str]) -> tuple[int, int]:
    """Parse ``HH:MM`` and re-raise with the full-input cron-shape hint on failure."""

    match = _HHMM_PATTERN.match(token)
    if not match:
        raise WikiError(_dsl_error_for(tokens))
    return int(match.group(1)), int(match.group(2))


def _dsl_error_for(tokens: list[str]) -> str:
    """Compose the error message, appending a cron-shape hint when warranted.

    Spec §"Edge cases" requires that cron-string inputs like
    ``0 9 * * 0`` get a hint they were rejected for being cron, not
    a generic "didn't parse". Detection is loose: five whitespace-
    separated tokens whose characters are all digits / stars / slashes
    / commas / hyphens.
    """

    if len(tokens) == 5 and all(_CRON_FIELD_PATTERN.match(t) for t in tokens):
        return _DSL_ERROR_MESSAGE + _CRON_HINT
    return _DSL_ERROR_MESSAGE
