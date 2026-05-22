"""Tests for the two new schedule events and ``OperationContract.default_time``.

Pins the additive-schema rule (ADR-0002 §Negative) for the wiki-schedule
PR series — see ``docs/specs/wiki-schedule/spec.md`` §"Contracts with
other modules" and CT-14. The four cases here correspond to plan step 2
in ``docs/specs/wiki-schedule/plan.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.journal import replay_state
from llm_wiki_kit.models import (
    Event,
    OperationContract,
    ScheduleInstalledEvent,
    ScheduleUninstalledEvent,
    VaultInitEvent,
    VaultState,
)

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)
NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Case 1 — both new event types round-trip through the discriminated union.
# ---------------------------------------------------------------------------


def test_schedule_installed_event_round_trips() -> None:
    original = ScheduleInstalledEvent(
        timestamp=NOW,
        by="wiki-schedule",
        operation="weekly-digest",
        machine_id="tower.local",
        cadence_dsl="SUN 09:00",
        os_artifact_path="/Users/me/Library/LaunchAgents/com.llm-wiki-kit.abc.weekly-digest.plist",
        exec_command=["/usr/local/bin/wiki", "run", "--exec", "weekly-digest"],
    )
    text = EVENT_ADAPTER.dump_json(original).decode()
    parsed = EVENT_ADAPTER.validate_json(text)
    assert parsed == original
    assert isinstance(parsed, ScheduleInstalledEvent)
    assert parsed.type == "schedule.installed"


def test_schedule_uninstalled_event_round_trips_both_truthy_and_falsy_removed_flag() -> None:
    for removed in (True, False):
        original = ScheduleUninstalledEvent(
            timestamp=NOW,
            by="wiki-schedule",
            operation="weekly-digest",
            machine_id="tower.local",
            removed_artifact=removed,
        )
        text = EVENT_ADAPTER.dump_json(original).decode()
        parsed = EVENT_ADAPTER.validate_json(text)
        assert parsed == original
        assert isinstance(parsed, ScheduleUninstalledEvent)
        assert parsed.type == "schedule.uninstalled"
        assert parsed.removed_artifact is removed


# ---------------------------------------------------------------------------
# Case 2 — a literal pre-v3 journal (no schedule.* events) replays unchanged.
# Mirrors spec CT-14 ("additive event schema replays cleanly").
# ---------------------------------------------------------------------------


def test_pre_schedule_journal_replays_to_same_vault_state() -> None:
    """A journal predating the schedule events still produces the same
    ``VaultState`` under the extended ``Event`` union — additive only.
    """

    legacy_events: list[Event] = [
        EVENT_ADAPTER.validate_python(
            {
                "type": "vault.init",
                "timestamp": NOW.isoformat(),
                "by": "wiki-init",
                "vault_name": "home",
                "recipe": "family",
            }
        ),
        EVENT_ADAPTER.validate_python(
            {
                "type": "primitive.install",
                "timestamp": NOW.isoformat(),
                "by": "wiki-init",
                "primitive": "meeting",
                "version": "0.1.0",
            }
        ),
    ]
    state = replay_state(legacy_events)

    expected = VaultState(
        vault_name="home",
        recipe="family",
        installed_primitives={"meeting": "0.1.0"},
    )
    assert state == expected

    # And the first event in the journal is still classified as a
    # VaultInitEvent under the extended union — the discriminator hasn't
    # been bumped.
    assert isinstance(legacy_events[0], VaultInitEvent)


# ---------------------------------------------------------------------------
# Case 3 — every shipped operation contract still validates under the
# extended OperationContract. The `default_time` field is additive; no
# existing contract sets it.
# ---------------------------------------------------------------------------


def _shipped_operation_contracts() -> list[Path]:
    contracts_dir = REPO_ROOT / "templates" / "operations"
    return sorted(contracts_dir.glob("*/contract.yaml"))


def test_shipped_operation_contracts_still_validate_under_extended_schema() -> None:
    paths = _shipped_operation_contracts()
    # Sanity: we expect at least one contract in the catalog.
    assert paths, "no shipped operation contracts found; check templates/operations/"
    for path in paths:
        data = yaml.safe_load(path.read_text())
        contract = OperationContract.model_validate(data)
        # `default_time` is additive: pre-PR contracts default to None.
        assert contract.default_time is None, (
            f"{path.relative_to(REPO_ROOT)}: default_time defaulted unexpectedly"
        )


# ---------------------------------------------------------------------------
# Case 4 — `default_time` accept/reject grammar.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["00:00", "07:00", "09:30", "13:45", "23:59"],
)
def test_default_time_accepts_zero_padded_hhmm(value: str) -> None:
    contract = OperationContract.model_validate(
        {
            "name": "weekly-digest",
            "description": "x",
            "period": "weekly",
            "default_time": value,
        }
    )
    assert contract.default_time == value


@pytest.mark.parametrize(
    "value",
    [
        "7:00",  # missing leading zero on hour
        "7",  # not HH:MM
        "25:00",  # hour out of range
        "12:60",  # minute out of range
        "12:5",  # minute missing leading zero
        "07:00:00",  # seconds appended
        "07-00",  # wrong separator
        "",  # empty string
    ],
)
def test_default_time_rejects_malformed(value: str) -> None:
    with pytest.raises(PydanticValidationError):
        OperationContract.model_validate(
            {
                "name": "weekly-digest",
                "description": "x",
                "period": "weekly",
                "default_time": value,
            }
        )


def test_default_time_defaults_to_none_and_is_optional() -> None:
    """No `default_time` key in the YAML → field defaults to None.

    Pinned so a future contract-loader change can't silently mark the field
    required, which would break every shipped contract at once.
    """

    contract = OperationContract.model_validate(
        {"name": "weekly-digest", "description": "x", "period": "weekly"}
    )
    assert contract.default_time is None
