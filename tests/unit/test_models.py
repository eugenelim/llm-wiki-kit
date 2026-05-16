"""Tests for ``llm_wiki_kit.models``.

These pin the shape that ADR-0005 names: every type that crosses disk is a
Pydantic v2 model, and the journal's ``Event`` type is a discriminated union
on a literal ``type`` field with one class per event type. ADR-0002 names
the load-bearing event types (``page.write``, ``page.proposal``,
``page.conflict_resolved``, ``managed_region.write``, plus the
``primitive.*`` and ``operation.*`` events that ``VaultState`` derives from).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.models import (
    ConfigSetEvent,
    Contribution,
    Event,
    LintRunEvent,
    ManagedRegionWriteEvent,
    OperationContract,
    OperationRunEvent,
    PageConflictResolvedEvent,
    PageProposalEvent,
    PageWriteEvent,
    Primitive,
    PrimitiveInstallEvent,
    PrimitiveKind,
    PrimitiveRemoveEvent,
    PrimitiveUpgradeEvent,
    Recipe,
    ResearchQueryEvent,
    SourceIngestEvent,
    VaultInitEvent,
    VaultState,
)

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)
NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Primitive
# ---------------------------------------------------------------------------


def _valid_primitive_dict() -> dict[str, object]:
    return {
        "name": "meeting",
        "kind": "content-type",
        "version": "0.1.0",
        "description": "Ingest meeting transcripts into pages.",
    }


def test_primitive_validates_minimal_input() -> None:
    p = Primitive.model_validate(_valid_primitive_dict())
    assert p.name == "meeting"
    assert p.kind is PrimitiveKind.CONTENT_TYPE
    assert p.version == "0.1.0"
    assert p.requires == []
    assert p.contributes_to == []
    assert p.config == {}


def test_primitive_accepts_all_four_kinds() -> None:
    for kind in ("ontology", "content-type", "operation", "infrastructure"):
        data = _valid_primitive_dict()
        data["kind"] = kind
        Primitive.model_validate(data)


def test_primitive_rejects_unknown_kind() -> None:
    data = _valid_primitive_dict()
    data["kind"] = "skill"
    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(data)


def test_primitive_rejects_bad_name() -> None:
    data = _valid_primitive_dict()
    data["name"] = "Meeting Notes"
    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(data)


def test_primitive_rejects_bad_version() -> None:
    data = _valid_primitive_dict()
    data["version"] = "v1"
    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(data)


def test_primitive_rejects_extra_top_level_fields() -> None:
    data = _valid_primitive_dict()
    data["mystery"] = "boom"
    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(data)


def test_primitive_parses_contributions() -> None:
    data = _valid_primitive_dict()
    data["contributes_to"] = [
        {"file": "AGENTS.md", "region": "content-types"},
        {"file": "frontmatter.schema.yaml", "region": "fields"},
    ]
    p = Primitive.model_validate(data)
    assert p.contributes_to == [
        Contribution(file="AGENTS.md", region="content-types"),
        Contribution(file="frontmatter.schema.yaml", region="fields"),
    ]


def test_primitive_requires_is_a_list_of_strings() -> None:
    data = _valid_primitive_dict()
    data["requires"] = ["core", "people"]
    p = Primitive.model_validate(data)
    assert p.requires == ["core", "people"]


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


def test_recipe_validates_minimal_input() -> None:
    r = Recipe.model_validate(
        {
            "name": "family",
            "version": "0.1.0",
            "description": "Family-oriented vault.",
            "primitives": ["core", "people", "meeting"],
        }
    )
    assert r.name == "family"
    assert r.primitives == ["core", "people", "meeting"]
    assert r.variables == {}


def test_recipe_rejects_missing_primitives_field() -> None:
    with pytest.raises(PydanticValidationError):
        Recipe.model_validate({"name": "family", "version": "0.1.0", "description": "x"})


def test_recipe_rejects_extra_fields() -> None:
    with pytest.raises(PydanticValidationError):
        Recipe.model_validate(
            {
                "name": "family",
                "version": "0.1.0",
                "description": "x",
                "primitives": ["core"],
                "extends": "personal",
            }
        )


# ---------------------------------------------------------------------------
# OperationContract
# ---------------------------------------------------------------------------


def test_operation_contract_validates_minimal_input() -> None:
    c = OperationContract.model_validate(
        {"name": "weekly-digest", "description": "Synthesize the week."}
    )
    assert c.name == "weekly-digest"
    assert c.period is None
    assert c.inputs == {}
    assert c.outputs == {}


def test_operation_contract_accepts_period_and_skill() -> None:
    c = OperationContract.model_validate(
        {
            "name": "weekly-digest",
            "description": "Synthesize the week.",
            "period": "weekly",
            "skill": "weekly-digest",
            "inputs": {"sources": "list[Page]"},
            "outputs": {"digest": "Page"},
        }
    )
    assert c.period == "weekly"
    assert c.skill == "weekly-digest"


# ---------------------------------------------------------------------------
# Event union — one class per event type
# ---------------------------------------------------------------------------


EVENT_CLASSES_BY_TYPE: dict[str, type] = {
    "vault.init": VaultInitEvent,
    "primitive.install": PrimitiveInstallEvent,
    "primitive.remove": PrimitiveRemoveEvent,
    "primitive.upgrade": PrimitiveUpgradeEvent,
    "managed_region.write": ManagedRegionWriteEvent,
    "source.ingest": SourceIngestEvent,
    "page.write": PageWriteEvent,
    "page.proposal": PageProposalEvent,
    "page.conflict_resolved": PageConflictResolvedEvent,
    "operation.run": OperationRunEvent,
    "research.query": ResearchQueryEvent,
    "lint.run": LintRunEvent,
    "config.set": ConfigSetEvent,
}


EVENT_FIXTURES: dict[str, dict[str, object]] = {
    "vault.init": {"vault_name": "home", "recipe": "family"},
    "primitive.install": {"primitive": "meeting", "version": "0.1.0"},
    "primitive.remove": {"primitive": "meeting"},
    "primitive.upgrade": {
        "primitive": "meeting",
        "from_version": "0.1.0",
        "to_version": "0.2.0",
    },
    "managed_region.write": {
        "file": "AGENTS.md",
        "region": "content-types",
        "content_hash": "deadbeef" * 8,
    },
    "source.ingest": {
        "source": "/tmp/transcript.txt",
        "source_hash": "abc" * 21 + "d",
        "content_type": "meeting",
        "produced_pages": ["meetings/2026-05-15.md"],
    },
    "page.write": {
        "path": "meetings/2026-05-15.md",
        "hash": "feedface" * 8,
    },
    "page.proposal": {
        "path": "meetings/2026-05-15.md",
        "proposed_path": "meetings/2026-05-15.md.proposed",
        "hash": "feedface" * 8,
    },
    "page.conflict_resolved": {
        "path": "meetings/2026-05-15.md",
        "hash": "1234abcd" * 8,
    },
    "operation.run": {
        "operation": "weekly-digest",
        "period": "2026-W20",
        "status": "success",
        "produced_pages": ["digests/2026-W20.md"],
    },
    "research.query": {
        "query": "rust async runtimes",
        "provider": "perplexity",
    },
    "lint.run": {"status": "ok", "issues": 0},
    "config.set": {"key": "search_backend", "value": "ripgrep"},
}


@pytest.mark.parametrize("type_name", sorted(EVENT_CLASSES_BY_TYPE))
def test_each_event_type_has_its_own_class(type_name: str) -> None:
    cls = EVENT_CLASSES_BY_TYPE[type_name]
    payload: dict[str, object] = {
        "type": type_name,
        "timestamp": NOW.isoformat(),
        "by": "core",
        **EVENT_FIXTURES[type_name],
    }
    event = EVENT_ADAPTER.validate_python(payload)
    assert isinstance(event, cls)
    assert event.type == type_name


def test_event_classes_are_all_distinct() -> None:
    seen = set(EVENT_CLASSES_BY_TYPE.values())
    assert len(seen) == len(EVENT_CLASSES_BY_TYPE)


def test_event_union_rejects_unknown_type() -> None:
    with pytest.raises(PydanticValidationError):
        EVENT_ADAPTER.validate_python(
            {
                "type": "made.up",
                "timestamp": NOW.isoformat(),
                "by": "core",
            }
        )


def test_event_union_rejects_missing_discriminator() -> None:
    with pytest.raises(PydanticValidationError):
        EVENT_ADAPTER.validate_python({"timestamp": NOW.isoformat(), "by": "core"})


def test_event_union_round_trips_through_json() -> None:
    original = PageWriteEvent(
        timestamp=NOW,
        by="meeting",
        path="meetings/2026-05-15.md",
        hash="cafebabe" * 8,
    )
    text = EVENT_ADAPTER.dump_json(original).decode()
    parsed = EVENT_ADAPTER.validate_json(text)
    assert parsed == original
    assert isinstance(parsed, PageWriteEvent)


def test_page_write_event_default_hash_algo_is_sha256() -> None:
    e = PageWriteEvent(
        timestamp=NOW,
        by="meeting",
        path="meetings/x.md",
        hash="a" * 64,
    )
    assert e.hash_algo == "sha256"


def test_managed_region_event_records_file_and_region() -> None:
    e = ManagedRegionWriteEvent(
        timestamp=NOW,
        by="meeting",
        file="AGENTS.md",
        region="content-types",
        content_hash="b" * 64,
    )
    assert e.file == "AGENTS.md"
    assert e.region == "content-types"


# ---------------------------------------------------------------------------
# VaultState
# ---------------------------------------------------------------------------


def test_vault_state_defaults_are_empty() -> None:
    state = VaultState()
    assert state.vault_name is None
    assert state.recipe is None
    assert state.installed_primitives == {}
    assert state.page_writes == {}
    assert state.ingested_sources == {}
    assert state.recent_operations == {}
    assert state.recent_research == []
    assert state.pending_proposals == {}


def test_vault_state_rejects_extra_fields() -> None:
    with pytest.raises(PydanticValidationError):
        VaultState.model_validate({"surprise": 1})
