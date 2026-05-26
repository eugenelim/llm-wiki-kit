"""Construction tests for ``Primitive`` schema-version freeze + sideload extras.

Plan tasks T2 (``schema_version: int = 1``) and T3
(``Primitive.from_sideload`` with ``extra='ignore'`` and dropped-field
capture). Spec: ``docs/specs/primitive-sideload/spec.md`` §"Schema
versioning (v1 freeze)" and §"Source-scoped extra-field policy".
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.models import Primitive, PrimitiveKind


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "fixture-foo",
        "kind": PrimitiveKind.CONTENT_TYPE.value,
        "version": "0.1.0",
        "description": "Fixture content-type for tests.",
    }
    base.update(overrides)
    return base


def test_schema_version_defaults_to_1() -> None:
    primitive = Primitive.model_validate(_payload())
    assert primitive.schema_version == 1


def test_schema_version_explicit_1_parses() -> None:
    primitive = Primitive.model_validate(_payload(schema_version=1))
    assert primitive.schema_version == 1


def test_schema_version_2_raises_for_bundled() -> None:
    with pytest.raises(PydanticValidationError) as exc_info:
        Primitive.model_validate(_payload(schema_version=2))
    message = str(exc_info.value)
    assert "schema_version 2" in message
    assert "supported: 1" in message


def test_schema_version_2_raises_for_sideload() -> None:
    """AC8: the same error class fires for sideloaded primitives too."""

    with pytest.raises(PydanticValidationError) as exc_info:
        Primitive.from_sideload(_payload(schema_version=2), source="sideload:test")
    assert "schema_version 2" in str(exc_info.value)


def test_from_sideload_accepts_unknown_field() -> None:
    primitive = Primitive.from_sideload(
        _payload(hint_for_kit_2_2="anything"),
        source="sideload:test-pkg",
    )
    assert primitive._dropped_fields == ("hint_for_kit_2_2",)


def test_model_validate_rejects_unknown_field_for_bundled() -> None:
    """AC7: bundled load path rejects the same unknown field sideload accepts."""

    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(_payload(hint_for_kit_2_2="anything"))


def test_from_sideload_sets_source() -> None:
    primitive = Primitive.from_sideload(
        _payload(),
        source="sideload:test-pkg",
    )
    assert primitive.source == "sideload:test-pkg"


def test_from_sideload_strips_nested_unknown_fields() -> None:
    """Pre-strip extends to ``contributes_to`` entries and ``routing`` dict."""

    payload = _payload(
        contributes_to=[{"file": "f.yaml", "region": "types", "ghost_field": "x"}],
        routing={"file_extensions": [".pdf"], "ghost_field": "y"},
    )
    primitive = Primitive.from_sideload(payload, source="sideload:test-pkg")
    # Top-level dropped fields are captured under a namespaced key.
    assert "contributes_to[0].ghost_field" in primitive._dropped_fields
    assert "routing.ghost_field" in primitive._dropped_fields
    # Nested known fields survive the strip.
    assert primitive.contributes_to[0].file == "f.yaml"
    assert primitive.routing is not None
    assert primitive.routing.file_extensions == [".pdf"]


def test_bundled_load_path_tags_source_bundled() -> None:
    primitive = Primitive.model_validate(_payload())
    assert primitive.source == "bundled"
