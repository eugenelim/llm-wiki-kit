"""Tests for the two adoption-baseline event classes (PR-A of wiki-init-adopt).

ADR-0008 §Decision sub-choice 3 names ``PageAdoptedEvent`` and
``ManagedRegionAdoptedEvent`` as the seed-baseline event shape for the
``--adopt`` flow. PR-A's job is the additive schema work: the two
classes must round-trip through ``append_event`` /
:func:`parse_event_line` like every other event in the union, dispatch
on the discriminator, and default ``hash_algo`` to ``"sha256"``
(matching ``PageWriteEvent`` / ``ManagedRegionWriteEvent``).

The adopt-aware ``safe_write`` predicate (PR-B) and the CLI surface
(PR-C) consume these classes but are out of scope for this file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit.journal import append_event, dump_event_json, parse_event_line, read_events
from llm_wiki_kit.models import (
    ManagedRegionAdoptedEvent,
    PageAdoptedEvent,
)

NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)


def test_page_adopted_event_round_trips() -> None:
    """``PageAdoptedEvent`` survives ``dump_event_json`` → ``parse_event_line``."""

    event = PageAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        path="wiki/people/.gitkeep",
        hash="a" * 64,
    )
    raw = dump_event_json(event)
    parsed = parse_event_line(raw, line_number=1)
    assert parsed == event
    assert isinstance(parsed, PageAdoptedEvent)


def test_managed_region_adopted_event_round_trips() -> None:
    """``ManagedRegionAdoptedEvent`` survives ``dump_event_json`` → ``parse_event_line``."""

    event = ManagedRegionAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash="b" * 64,
    )
    raw = dump_event_json(event)
    parsed = parse_event_line(raw, line_number=1)
    assert parsed == event
    assert isinstance(parsed, ManagedRegionAdoptedEvent)


def test_adopted_events_in_discriminated_union_dispatch(tmp_path: Path) -> None:
    """Two events written via ``append_event`` parse back as their concrete classes.

    Pins the discriminated-union dispatch: a ``"type":"page.adopted"``
    line MUST parse as :class:`PageAdoptedEvent` (not the nearest
    fallback), same for ``managed_region.adopted``.
    """

    journal = tmp_path / "journal.jsonl"
    page = PageAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        path="wiki/people/.gitkeep",
        hash="a" * 64,
    )
    region = ManagedRegionAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash="b" * 64,
    )
    append_event(journal, page)
    append_event(journal, region)

    loaded = read_events(journal)
    assert loaded == [page, region]
    assert isinstance(loaded[0], PageAdoptedEvent)
    assert isinstance(loaded[1], ManagedRegionAdoptedEvent)


def test_page_adopted_event_type_discriminator_is_page_adopted() -> None:
    """Spec §Outputs Journal events bullet 2: ``type`` is ``"page.adopted"``."""

    event = PageAdoptedEvent(timestamp=NOW, by="wiki-init-adopt", path="p.md", hash="a" * 64)
    assert event.type == "page.adopted"


def test_managed_region_adopted_event_type_discriminator_is_namespaced() -> None:
    """ADR-0008 §Decision sub-choice 3: ``type`` is ``"managed_region.adopted"``."""

    event = ManagedRegionAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        file="f.yaml",
        region="r",
        content_hash="b" * 64,
    )
    assert event.type == "managed_region.adopted"


def test_page_adopted_event_default_hash_algo_sha256() -> None:
    """Mirrors ``PageWriteEvent``'s ``hash_algo`` default — ADR-0008 §3."""

    event = PageAdoptedEvent(timestamp=NOW, by="wiki-init-adopt", path="p.md", hash="a" * 64)
    assert event.hash_algo == "sha256"


def test_managed_region_adopted_event_default_hash_algo_sha256() -> None:
    """Mirrors ``ManagedRegionWriteEvent``'s ``hash_algo`` default — ADR-0008 §3."""

    event = ManagedRegionAdoptedEvent(
        timestamp=NOW,
        by="wiki-init-adopt",
        file="f.yaml",
        region="r",
        content_hash="b" * 64,
    )
    assert event.hash_algo == "sha256"
