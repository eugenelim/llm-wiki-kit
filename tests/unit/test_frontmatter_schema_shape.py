"""Shape pin for the baseline ``core/files/frontmatter.schema.yaml`` (RFC-0009).

The faceting migration (ADR-0011) restructures the shipped schema baseline:
the fused ``type`` becomes two facets, ``genre`` (a fixed nine-value enum,
hand-written — *not* a managed region, because the region aggregator
concatenates without deduplicating and several content-types share a genre)
and ``subtype`` (the single managed region content-types contribute to,
replacing ``types``). ``status`` gains ``someday``; ``parent`` is added; the
``required`` set swaps ``type`` for ``genre``+``subtype``.

This is a goal-based test: it parses the shipped baseline and asserts its
shape. ``workspaces`` (RFC-0008) must survive byte-for-byte.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "core" / "files" / "frontmatter.schema.yaml"

# The fixed nine-shape genre vocabulary, in RFC-0009 §B order.
FIXED_GENRES = [
    "note",
    "record",
    "update",
    "decision",
    "reference",
    "profile",
    "log",
    "contract",
    "moc",
]


def _schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _schema() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(_schema_text())
    return data


def test_genre_is_a_fixed_baseline_enum_of_exactly_nine() -> None:
    schema = _schema()
    assert schema["genres"] == FIXED_GENRES


def test_subtype_block_is_present() -> None:
    schema = _schema()
    # Baseline ``subtypes:`` carries only the (empty) managed region, so it
    # parses to ``None``; the key must exist for content-types to extend.
    assert "subtypes" in schema


def test_required_is_exactly_the_facet_set() -> None:
    schema = _schema()
    assert schema["required"] == [
        "genre",
        "subtype",
        "status",
        "provenance",
        "created",
        "modified",
    ]


def test_statuses_gains_someday() -> None:
    schema = _schema()
    assert schema["statuses"] == ["active", "draft", "archived", "someday"]


def test_type_is_absent() -> None:
    schema = _schema()
    assert "type" not in schema
    assert "types" not in schema
    assert "type" not in schema["fields"]
    assert "type" not in schema["required"]


def test_facet_fields_declared() -> None:
    schema = _schema()
    fields = schema["fields"]
    assert fields["genre"] == {"type": "string"}
    assert fields["subtype"] == {"type": "string"}


def test_parent_field_shape() -> None:
    schema = _schema()
    assert schema["fields"]["parent"] == {
        "type": "list",
        "items": "string",
        "optional": True,
    }
    assert "parent" not in schema["required"]


def test_workspaces_unchanged() -> None:
    schema = _schema()
    assert schema["fields"]["workspaces"] == {
        "type": "list",
        "items": "string",
        "optional": True,
    }
    assert "workspaces" not in schema["required"]


def test_managed_regions_are_subtype_and_fields_only() -> None:
    # Match only real marker lines (optionally indented, id then EOL), not the
    # ``# BEGIN MANAGED: id`` mention inside the file's explanatory header.
    regions = set(re.findall(r"^\s*# BEGIN MANAGED: (\w+)\s*$", _schema_text(), re.MULTILINE))
    assert regions == {"subtype", "fields"}
