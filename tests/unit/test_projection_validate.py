"""T1 — strict frontmatter parse, schema load, and facet validation.

Pure functions over in-memory strings + a schema dict; no I/O beyond
reading a schema file written into ``tmp_path``. Covers spec ACs 5, 6, 7.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.projection import (
    SchemaFacets,
    load_schema,
    parse_frontmatter,
    validate_frontmatter,
)

SCHEMA_YAML = """\
required:
  - genre
  - subtype
  - status
  - provenance
  - created
  - modified
genres:
  - note
  - record
  - reference
  - profile
  - moc
subtypes:
  # BEGIN MANAGED: subtype
  - meeting
  - person
  - research-brief
  # END MANAGED: subtype
statuses:
  - active
  - draft
provenance:
  - extracted
  - synthesized
  - mixed
"""

VALID_FM = {
    "genre": "record",
    "subtype": "meeting",
    "status": "active",
    "provenance": "extracted",
    "created": "2026-06-24",
    "modified": "2026-06-24",
}


def _schema() -> SchemaFacets:
    return SchemaFacets(
        required=list(VALID_FM),
        genres=["note", "record", "reference", "profile", "moc"],
        subtypes=["meeting", "person", "research-brief"],
        statuses=["active", "draft"],
        provenances=["extracted", "synthesized", "mixed"],
    )


# --- parse_frontmatter ------------------------------------------------------


def test_parse_splits_frontmatter_and_body_verbatim() -> None:
    text = "---\ngenre: note\n---\n# Title\n\nBody line.\n"
    fm, body = parse_frontmatter(text)
    assert fm == {"genre": "note"}
    assert body == "# Title\n\nBody line.\n"


def test_parse_preserves_trailing_body_content() -> None:
    text = "---\ngenre: note\n---\nline1\nline2 no trailing newline"
    _, body = parse_frontmatter(text)
    assert body == "line1\nline2 no trailing newline"


def test_parse_missing_block_raises() -> None:
    with pytest.raises(WikiError, match="no YAML frontmatter"):
        parse_frontmatter("# Just a heading\n")


def test_parse_unterminated_block_raises() -> None:
    with pytest.raises(WikiError, match="not terminated"):
        parse_frontmatter("---\ngenre: note\nstill in frontmatter\n")


def test_parse_malformed_yaml_raises_not_silent_empty() -> None:
    # A tab indent under a mapping is a YAML error.
    with pytest.raises(WikiError, match="not valid YAML"):
        parse_frontmatter("---\ngenre: [unclosed\n---\nbody\n")


def test_parse_rejects_unsafe_yaml_tag() -> None:
    # AC5 — safe_load refuses a python/object tag rather than deserialize it.
    text = "---\ngenre: !!python/object/apply:os.system ['echo hi']\n---\nbody\n"
    with pytest.raises(WikiError, match="not valid YAML"):
        parse_frontmatter(text)


def test_parse_non_mapping_frontmatter_raises() -> None:
    with pytest.raises(WikiError, match="must be a YAML mapping"):
        parse_frontmatter("---\n- a\n- b\n---\nbody\n")


# --- load_schema ------------------------------------------------------------


def test_load_schema_parses_all_vocabularies(tmp_path: Path) -> None:
    (tmp_path / "frontmatter.schema.yaml").write_text(SCHEMA_YAML, encoding="utf-8")
    schema = load_schema(tmp_path)
    assert schema.required == [
        "genre",
        "subtype",
        "status",
        "provenance",
        "created",
        "modified",
    ]
    assert schema.genres == ["note", "record", "reference", "profile", "moc"]
    # AC6 — managed-region comment markers do not leak into the list.
    assert schema.subtypes == ["meeting", "person", "research-brief"]
    assert schema.statuses == ["active", "draft"]
    assert schema.provenances == ["extracted", "synthesized", "mixed"]


def test_load_schema_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(WikiError, match=r"no frontmatter\.schema\.yaml"):
        load_schema(tmp_path)


# --- validate_frontmatter ---------------------------------------------------


def test_validate_accepts_fully_valid_frontmatter() -> None:
    validate_frontmatter(dict(VALID_FM), _schema())  # no raise


@pytest.mark.parametrize("facet", list(VALID_FM))
def test_validate_rejects_each_missing_required_facet(facet: str) -> None:
    fm = dict(VALID_FM)
    del fm[facet]
    with pytest.raises(WikiError, match=f"missing required facet: '{facet}'"):
        validate_frontmatter(fm, _schema())


def test_validate_rejects_empty_required_facet() -> None:
    fm = dict(VALID_FM, status="")
    with pytest.raises(WikiError, match="missing required facet: 'status'"):
        validate_frontmatter(fm, _schema())


def test_validate_rejects_genre_outside_enum() -> None:
    fm = dict(VALID_FM, genre="invoice")
    with pytest.raises(WikiError, match="genre 'invoice' is not in"):
        validate_frontmatter(fm, _schema())


def test_validate_rejects_status_outside_enum() -> None:
    fm = dict(VALID_FM, status="pending")
    with pytest.raises(WikiError, match="status 'pending' is not in"):
        validate_frontmatter(fm, _schema())


def test_validate_rejects_provenance_outside_enum() -> None:
    fm = dict(VALID_FM, provenance="guessed")
    with pytest.raises(WikiError, match="provenance 'guessed' is not in"):
        validate_frontmatter(fm, _schema())


def test_validate_rejects_unknown_subtype() -> None:
    fm = dict(VALID_FM, subtype="quarterly-report")
    with pytest.raises(WikiError, match="subtype 'quarterly-report' is not in"):
        validate_frontmatter(fm, _schema())
