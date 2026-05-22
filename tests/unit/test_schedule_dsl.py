"""Tests for ``llm_wiki_kit.schedule.dsl``.

The seven mandated cases from plan step 3 in
``docs/specs/wiki-schedule/plan.md``: happy-path parse per period,
day-of-week case-insensitivity, cron rejection, malformed rejection,
`resolve_default` table-match, `on-demand` refusal, absent-period
refusal. Per-emitter golden-string coverage of the conversion functions
lives in the per-OS PRs (PR-4 launchd, PR-6 systemd, PR-7 Task
Scheduler); this file pins only the parser + the default-fill table.
"""

from __future__ import annotations

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import OperationContract
from llm_wiki_kit.schedule.dsl import (
    DEFAULT_TIME_BY_PERIOD,
    QUARTERLY_MONTHS,
    ResolvedCadence,
    parse,
    resolve_default,
    to_launchd_calendar_interval,
    to_systemd_oncalendar,
    to_task_scheduler_trigger,
)

# ---------------------------------------------------------------------------
# 1. happy-path parse for each of `daily`, `<DAY>`, `monthly`, `quarterly`.
# ---------------------------------------------------------------------------


def test_parse_daily_happy_path() -> None:
    cadence = parse("daily 07:00")
    assert cadence == ResolvedCadence(period="daily", hour=7, minute=0)


def test_parse_weekly_happy_path() -> None:
    # SUN=0, MON=1, ..., SAT=6 — matches the launchd Weekday encoding pinned
    # by spec CT-2.
    cadence = parse("SUN 09:00")
    assert cadence == ResolvedCadence(period="weekly", hour=9, minute=0, day_of_week=0)


def test_parse_monthly_happy_path() -> None:
    cadence = parse("monthly 1 09:00")
    assert cadence == ResolvedCadence(period="monthly", hour=9, minute=0, day_of_month=1)


def test_parse_quarterly_happy_path() -> None:
    cadence = parse("quarterly 1 09:00")
    assert cadence == ResolvedCadence(period="quarterly", hour=9, minute=0, day_of_month=1)


# ---------------------------------------------------------------------------
# 2. day-of-week case-insensitive.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "day_token,expected_dow",
    [
        ("SUN", 0),
        ("sun", 0),
        ("Sun", 0),
        ("MON", 1),
        ("mon", 1),
        ("TUE", 2),
        ("tue", 2),
        ("wed", 3),
        ("THU", 4),
        ("fri", 5),
        ("SAT", 6),
    ],
)
def test_parse_weekly_day_token_case_insensitive(day_token: str, expected_dow: int) -> None:
    cadence = parse(f"{day_token} 18:00")
    assert cadence.period == "weekly"
    assert cadence.day_of_week == expected_dow
    assert cadence.hour == 18
    assert cadence.minute == 0


# ---------------------------------------------------------------------------
# 3. rejection of cron strings (canary inputs from spec CT-4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cron_form",
    [
        "0 9 * * 0",
        "*/5 * * * *",
        "0 0 1 * *",
        "@daily",
        "@weekly",
    ],
)
def test_parse_rejects_cron_strings(cron_form: str) -> None:
    with pytest.raises(WikiError) as exc:
        parse(cron_form)
    assert "unrecognised cadence DSL" in str(exc.value)


def test_parse_five_field_cron_hint_mentions_cron() -> None:
    """Spec §"Edge cases": cron-shaped input gets a clearer hint.

    The library function can't always translate cron-to-DSL, but it can
    at least tell the user "this looks like cron, which we don't accept"
    instead of dumping the generic accepted-forms list — which would
    leave the user wondering whether their syntax was malformed or
    whether cron itself was the issue.
    """

    with pytest.raises(WikiError) as exc:
        parse("0 9 * * 0")
    msg = str(exc.value)
    assert "unrecognised cadence DSL" in msg
    assert "cron" in msg


# ---------------------------------------------------------------------------
# 4. rejection of seconds and other malformed forms.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_input",
    [
        "SUN 09:00:30",  # seconds appended
        "daily 7:00",  # missing leading zero on hour
        "daily 25:00",  # hour out of range
        "daily 12:60",  # minute out of range
        "daily",  # missing time
        "monthly 0 09:00",  # day-of-month < 1
        "monthly 29 09:00",  # day-of-month > 28 (no end-of-month surprises)
        "monthly 1",  # missing time
        "quarterly 29 09:00",  # day-of-month > 28
        "SUNDAY 09:00",  # full day name not accepted (kit uses 3-letter)
        "FOO 09:00",  # unknown day token
        "",  # empty
        "   ",  # whitespace only
        "weekly 09:00",  # 'weekly' alone is not a valid prefix (use <DAY>)
    ],
)
def test_parse_rejects_malformed(bad_input: str) -> None:
    with pytest.raises(WikiError) as exc:
        parse(bad_input)
    assert "unrecognised cadence DSL" in str(exc.value)


# ---------------------------------------------------------------------------
# 5. `resolve_default()` matches the §Inputs table for each `period:` value,
#    pinned against the single named constant `DEFAULT_TIME_BY_PERIOD`.
# ---------------------------------------------------------------------------


def test_default_time_by_period_constant_matches_spec_inputs_table() -> None:
    """The single named constant from spec §Invariants.

    The constant is the source of truth; this test pins each key/value so a
    future tweak of the table fails here loudly rather than drifting silently
    away from the spec's §Inputs table.
    """

    assert DEFAULT_TIME_BY_PERIOD == {
        "daily": "07:00",
        "weekly": "09:00",
        "monthly": "09:00",
        "quarterly": "09:00",
    }


@pytest.mark.parametrize(
    "period,expected",
    [
        ("daily", ResolvedCadence(period="daily", hour=7, minute=0)),
        (
            "weekly",
            ResolvedCadence(period="weekly", hour=9, minute=0, day_of_week=0),
        ),
        (
            "monthly",
            ResolvedCadence(period="monthly", hour=9, minute=0, day_of_month=1),
        ),
        (
            "quarterly",
            ResolvedCadence(period="quarterly", hour=9, minute=0, day_of_month=1),
        ),
    ],
)
def test_resolve_default_uses_table_when_default_time_is_none(
    period: str, expected: ResolvedCadence
) -> None:
    contract = OperationContract.model_validate(
        {"name": "op", "description": "x", "period": period}
    )
    assert resolve_default(contract) == expected


def test_resolve_default_honors_contract_default_time_override() -> None:
    """When `contract.default_time` is set, it overrides the table.

    Pins the override behavior pinned in spec §Invariants:
    `resolve_default(contract)` reads `contract.default_time` if set, else
    falls back to `DEFAULT_TIME_BY_PERIOD[contract.period]`.
    """

    contract = OperationContract.model_validate(
        {
            "name": "op",
            "description": "x",
            "period": "daily",
            "default_time": "06:30",
        }
    )
    cadence = resolve_default(contract)
    assert cadence == ResolvedCadence(period="daily", hour=6, minute=30)


# ---------------------------------------------------------------------------
# 6. refusal on `period: on-demand` (mirrors spec CT-3).
# ---------------------------------------------------------------------------


def test_resolve_default_refuses_on_demand_period() -> None:
    contract = OperationContract.model_validate(
        {"name": "op", "description": "x", "period": "on-demand"}
    )
    with pytest.raises(WikiError) as exc:
        resolve_default(contract)
    msg = str(exc.value)
    # Either spelling from spec §Inputs is acceptable as long as the
    # user-visible reason is clearly attributable.
    assert "on-demand" in msg or "declared no cadence" in msg


# ---------------------------------------------------------------------------
# 7. refusal on absent/other periods.
# ---------------------------------------------------------------------------


def test_resolve_default_refuses_absent_period() -> None:
    contract = OperationContract.model_validate(
        {"name": "op", "description": "x"}  # period defaults to None
    )
    assert contract.period is None
    with pytest.raises(WikiError) as exc:
        resolve_default(contract)
    assert "declared no cadence" in str(exc.value)


def test_resolve_default_refuses_unknown_period() -> None:
    contract = OperationContract.model_validate(
        {"name": "op", "description": "x", "period": "fortnightly"}
    )
    with pytest.raises(WikiError) as exc:
        resolve_default(contract)
    assert "declared no cadence" in str(exc.value)


# ---------------------------------------------------------------------------
# Converter smoke tests — golden-string assertions for each (cadence kind,
# emitter format) pair land in the per-OS emitter PRs (PR-4 launchd,
# PR-6 systemd, PR-7 Task Scheduler). The smoke tests here pin the
# cross-PR contract: each converter accepts every ResolvedCadence kind
# and returns the documented shape. Without these, a parallel emitter
# PR could silently rename a key (`"Weekday"` → `"WeekDay"`) and break
# the contract two sibling PRs are mid-author against.
# ---------------------------------------------------------------------------


_DAILY = ResolvedCadence(period="daily", hour=7, minute=0)
_WEEKLY = ResolvedCadence(period="weekly", hour=9, minute=0, day_of_week=0)
_MONTHLY = ResolvedCadence(period="monthly", hour=9, minute=30, day_of_month=15)
_QUARTERLY = ResolvedCadence(period="quarterly", hour=9, minute=0, day_of_month=1)


@pytest.mark.parametrize(
    "cadence,expected",
    [
        (_DAILY, "*-*-* 07:00:00"),
        (_WEEKLY, "Sun *-*-* 09:00:00"),
        (_MONTHLY, "*-*-15 09:30:00"),
        (_QUARTERLY, "*-01,04,07,10-01 09:00:00"),
    ],
)
def test_to_systemd_oncalendar_smoke(cadence: ResolvedCadence, expected: str) -> None:
    assert to_systemd_oncalendar(cadence) == expected


def test_to_launchd_calendar_interval_returns_one_dict_for_non_quarterly() -> None:
    assert to_launchd_calendar_interval(_DAILY) == [{"Hour": 7, "Minute": 0}]
    assert to_launchd_calendar_interval(_WEEKLY) == [{"Weekday": 0, "Hour": 9, "Minute": 0}]
    assert to_launchd_calendar_interval(_MONTHLY) == [{"Day": 15, "Hour": 9, "Minute": 30}]


def test_to_launchd_calendar_interval_fans_quarterly_into_four_month_dicts() -> None:
    """Spec §Inputs: quarterly fires in Jan/Apr/Jul/Oct.

    Pins the four-element shape so the launchd emitter (PR-4) can hand
    the list straight to ``plistlib`` for the plist's
    ``StartCalendarInterval`` array. A regression here (e.g. forgetting
    ``Month``) would silently turn a quarterly schedule into a monthly
    one on day N — the kind of bug that ships unnoticed because no
    immediate test reproduces it.
    """

    intervals = to_launchd_calendar_interval(_QUARTERLY)
    assert intervals == [
        {"Month": 1, "Day": 1, "Hour": 9, "Minute": 0},
        {"Month": 4, "Day": 1, "Hour": 9, "Minute": 0},
        {"Month": 7, "Day": 1, "Hour": 9, "Minute": 0},
        {"Month": 10, "Day": 1, "Hour": 9, "Minute": 0},
    ]
    # And the months match the canonical constant — one source of truth
    # for "what does quarterly mean."
    assert tuple(d["Month"] for d in intervals) == QUARTERLY_MONTHS


@pytest.mark.parametrize(
    "cadence,expected_schedule_tag",
    [
        (_DAILY, "ScheduleByDay"),
        (_WEEKLY, "ScheduleByWeek"),
        (_MONTHLY, "ScheduleByMonth"),
        (_QUARTERLY, "ScheduleByMonth"),
    ],
)
def test_to_task_scheduler_trigger_smoke(
    cadence: ResolvedCadence, expected_schedule_tag: str
) -> None:
    """Smoke test: the trigger renders, carries a StartBoundary at the
    right time, and dispatches on the expected ``<ScheduleBy*>`` child.

    Golden-XML coverage of each cadence kind lands in PR-7's
    ``tests/unit/test_schedule_taskscheduler.py``.
    """

    trigger = to_task_scheduler_trigger(cadence)
    assert trigger.tag == "CalendarTrigger"
    start_boundary = trigger.find("StartBoundary")
    assert start_boundary is not None
    assert start_boundary.text is not None
    assert start_boundary.text.endswith(f"T{cadence.hour:02d}:{cadence.minute:02d}:00")
    assert trigger.find(expected_schedule_tag) is not None
