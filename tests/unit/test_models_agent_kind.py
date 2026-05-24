"""PR-1 model-surface tests for RFC-0004 wiki-agents.

Covers the model changes that land in PR-1 of
``docs/specs/wiki-agents/plan.md``:

- ``PrimitiveKind.AGENT`` enum value.
- ``OperationRunByAgentEvent`` class shape (required ``event_id``,
  literal ``"operation.run_by_agent"`` discriminator).
- Event-union dispatch on the new literal.
- CT-24a: a literal pre-RFC-4 journal — restricted to byte-stable
  event types per ``spec.md`` §CT-24a — replays under the extended
  ``Event`` union and produces a ``VaultState`` whose
  ``model_dump_json()`` is byte-identical to the frozen snapshot at
  ``tests/fixtures/journals/pre_rfc4_state.json``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import (
    Event,
    OperationRunByAgentEvent,
    PrimitiveKind,
)

_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)
NOW = datetime(2026, 5, 15, 0, 0, 0, tzinfo=UTC)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "journals"


def test_primitive_kind_agent_enum_value_exists() -> None:
    """``PrimitiveKind.AGENT`` exists and stringifies to ``"agent"``."""

    assert PrimitiveKind.AGENT.value == "agent"
    assert PrimitiveKind("agent") is PrimitiveKind.AGENT


def test_operation_run_by_agent_event_roundtrips_through_json() -> None:
    """Construct, dump, re-parse via the union — identity holds."""

    event = OperationRunByAgentEvent(
        timestamp=NOW,
        by="wiki-run",
        operation="weekly-digest",
        agent="household-manager",
        event_id="abc123abc123",
    )
    blob = event.model_dump_json()
    reparsed = _EVENT_ADAPTER.validate_json(blob)
    assert isinstance(reparsed, OperationRunByAgentEvent)
    assert reparsed == event


def test_operation_run_by_agent_event_id_is_required() -> None:
    """``event_id`` carries the paired ``OperationRunEvent``'s id — required at construction."""

    with pytest.raises(PydanticValidationError) as excinfo:
        OperationRunByAgentEvent(  # type: ignore[call-arg]
            timestamp=NOW,
            by="wiki-run",
            operation="weekly-digest",
            agent="household-manager",
        )
    locs = {".".join(str(p) for p in err["loc"]) for err in excinfo.value.errors()}
    assert "event_id" in locs


def test_event_union_dispatches_on_operation_run_by_agent_discriminator() -> None:
    """The discriminated ``Event`` union picks the new class by its literal ``type``."""

    payload = {
        "type": "operation.run_by_agent",
        "timestamp": NOW.isoformat(),
        "by": "wiki-run",
        "operation": "weekly-digest",
        "agent": "household-manager",
        "event_id": "abc123abc123",
    }
    parsed = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(parsed, OperationRunByAgentEvent)
    assert parsed.agent == "household-manager"
    assert parsed.event_id == "abc123abc123"


def test_pre_rfc4_journal_without_event_id_replays_byte_identical() -> None:
    """CT-24a: pre-RFC-4 journal replays under the extended union, byte-identical.

    The fixture at ``tests/fixtures/journals/pre_rfc4_journal.jsonl`` is
    restricted to event types whose Pydantic shape this spec leaves
    byte-stable (no ``page.proposal``, no ``schedule.installed``) and
    includes pre-Task-17 ``operation.run`` lines lacking the
    ``event_id`` field. Replaying it under the extended ``Event``
    union must produce a ``VaultState`` whose ``model_dump_json()``
    matches the frozen snapshot byte-for-byte. Catches additive-
    schema regressions to any included byte-stable type via the
    replay path — pinning ADR-0002 §Negative's additive-schema rule
    against accidental field additions or default-value changes that
    would alter legacy-journal derivation.
    """

    journal_path = _FIXTURE_DIR / "pre_rfc4_journal.jsonl"
    snapshot_path = _FIXTURE_DIR / "pre_rfc4_state.json"

    events = read_events(journal_path)
    assert events, "fixture journal is empty"

    state = replay_state(events)
    expected = snapshot_path.read_text(encoding="utf-8").rstrip("\n")
    assert state.model_dump_json() == expected
