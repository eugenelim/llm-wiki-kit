"""Tests for ``PageProposalEvent.proposed_by_agent`` (RFC-0004 wiki-agents PR-6).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-23: ``PageProposalEvent.proposed_by_agent`` round-trips through the
  Pydantic model + discriminated event union.
- CT-24c: A literal pre-RFC-4 ``page.proposal`` JSON line lacking the
  ``proposed_by_agent`` field replays with ``proposed_by_agent is None``.

The field is additive per ADR-0002 §Negative — every new field on a
journal event must have a default so older lines keep parsing. The tests
use literal JSON lines (not ``model_dump_json()`` round-trips) so a
regression that made ``proposed_by_agent`` required would surface here
rather than at first replay against a real vault.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from llm_wiki_kit.models import Event, PageProposalEvent

NOW = datetime(2026, 5, 24, 9, 0, 0, tzinfo=UTC)


def test_page_proposal_event_proposed_by_agent_roundtrips() -> None:
    """CT-23: ``proposed_by_agent`` round-trips through JSON + the Event union."""

    event = PageProposalEvent(
        timestamp=NOW,
        by="wiki",
        path="dashboards/weekly.md",
        proposed_path="dashboards/weekly.md.proposed",
        hash="abc123abc123abc123abc123abc123abc123abc123abc123abc123abc12345",
        proposed_by_agent="household-manager",
    )
    raw = event.model_dump_json()
    parsed = PageProposalEvent.model_validate_json(raw)
    assert parsed.proposed_by_agent == "household-manager"

    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    via_union = adapter.validate_python(json.loads(raw))
    assert isinstance(via_union, PageProposalEvent)
    assert via_union.proposed_by_agent == "household-manager"


def test_page_proposal_event_proposed_by_agent_defaults_to_none() -> None:
    """The field defaults to ``None`` when omitted from the Python constructor."""

    event = PageProposalEvent(
        timestamp=NOW,
        by="wiki",
        path="dashboards/weekly.md",
        proposed_path="dashboards/weekly.md.proposed",
        hash="abc123abc123abc123abc123abc123abc123abc123abc123abc123abc12345",
    )
    assert event.proposed_by_agent is None


def test_page_proposal_event_proposed_by_agent_validates_name_pattern() -> None:
    """Agent names must match ``NAME_PATTERN`` (lowercase kebab-case).

    Mirrors the validation on ``OperationContract.preferred_agent`` and
    ``ScheduleInstalledEvent.agent`` so the three agent-name carrying
    fields reject the same authoring-typos shape (capitals, underscores).
    """

    with pytest.raises(ValidationError):
        PageProposalEvent(
            timestamp=NOW,
            by="wiki",
            path="dashboards/weekly.md",
            proposed_path="dashboards/weekly.md.proposed",
            hash="abc123abc123abc123abc123abc123abc123abc123abc123abc123abc12345",
            proposed_by_agent="Household_Manager",  # invalid: capital + underscore
        )


def test_pre_rfc4_page_proposal_without_proposed_by_agent_replays() -> None:
    """CT-24c: literal pre-RFC-4 line lacking ``proposed_by_agent`` replays with ``None``.

    Pins ADR-0002 §Negative's additive-schema rule end-to-end through
    both the concrete class and the discriminated ``Event`` union the
    journal reader actually dispatches on.
    """

    pre_rfc4_payload = {
        "type": "page.proposal",
        "timestamp": NOW.isoformat(),
        "by": "wiki",
        "path": "dashboards/weekly.md",
        "proposed_path": "dashboards/weekly.md.proposed",
        "hash": "abc123abc123abc123abc123abc123abc123abc123abc123abc123abc12345",
    }
    parsed = PageProposalEvent.model_validate_json(json.dumps(pre_rfc4_payload))
    assert parsed.proposed_by_agent is None

    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    via_union = adapter.validate_python(pre_rfc4_payload)
    assert isinstance(via_union, PageProposalEvent)
    assert via_union.proposed_by_agent is None
