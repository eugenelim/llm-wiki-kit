"""Tests for ``PrimitiveForceRenderEvent`` (wiki-upgrade-force-render spec).

Pins:

* Pydantic round-trip via the discriminated ``Event`` union.
* Discriminator dispatch through ``append_event`` → ``read_events``.
* ``by`` attribution per spec §Invariants bullet 6
  (``"wiki-upgrade"``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit.journal import (
    append_event,
    dump_event_json,
    parse_event_line,
    read_events,
)
from llm_wiki_kit.models import PrimitiveForceRenderEvent

NOW = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


def test_primitive_force_render_event_round_trips() -> None:
    """Construct → ``dump_event_json`` → ``parse_event_line`` round-trips.

    Structural equality verifies every payload field survives one
    encode/decode cycle through the discriminated-union adapter.
    """

    original = PrimitiveForceRenderEvent(
        timestamp=NOW,
        by="wiki-upgrade",
        primitive="core",
        version="0.1.0",
    )
    line = dump_event_json(original)
    parsed = parse_event_line(line, line_number=1)
    assert parsed == original
    assert isinstance(parsed, PrimitiveForceRenderEvent)
    assert parsed.type == "primitive.force_render"
    assert parsed.primitive == "core"
    assert parsed.version == "0.1.0"


def test_primitive_force_render_event_in_discriminated_union_dispatch(tmp_path: Path) -> None:
    """``append_event`` → ``read_events`` dispatches via the ``type`` literal.

    Pins that the event is wired into the discriminated ``Event`` union
    so the JSONL parser routes the row through the right class.
    """

    journal_path = tmp_path / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True)
    event = PrimitiveForceRenderEvent(
        timestamp=NOW,
        by="wiki-upgrade",
        primitive="people",
        version="0.2.0",
    )
    append_event(journal_path, event)
    events = read_events(journal_path)
    assert len(events) == 1
    assert isinstance(events[0], PrimitiveForceRenderEvent)
    assert events[0].type == "primitive.force_render"
    assert events[0].primitive == "people"


def test_primitive_force_render_event_by_attribution_pinned() -> None:
    """``by == "wiki-upgrade"`` matches spec §Invariants bullet 6.

    The class itself doesn't enforce the constant — the runner does —
    but the test pins the canonical attribution shape used by the
    runner so a divergent caller would surface in review.
    """

    event = PrimitiveForceRenderEvent(
        timestamp=NOW,
        by="wiki-upgrade",
        primitive="core",
        version="0.1.0",
    )
    assert event.by == "wiki-upgrade"
