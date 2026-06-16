"""Pin the legacy-``type`` → ``genre``/``subtype`` crosswalk (RFC-0009, ADR-0011).

``docs/specs/faceted-frontmatter-schema/crosswalk.yaml`` is the authoring
reference for the faceting migration: it maps each former fused ``type``
(which is the content-type *directory name*) to its two facets and, where a
shipped operation reads one, a subtype-scoped lifecycle field. This module is
the validation gate for that file.

The invariants pinned here are the spec's Acceptance Criteria for the
crosswalk:

* **Total** — exactly the twelve content-type directory names, no more, no
  fewer. The directory name is the stable discovery source: the ``.types``
  snippet that also carried the legacy string is deleted by the migration.
* **``genre`` is one of the fixed nine** — the genre vocabulary is a fixed
  spine, not growable (only ``subtype`` grows).
* **``subtype`` refines, never duplicates, its ``genre``** — every row's
  ``subtype`` differs from its ``genre``.
* **``subtype`` values are pairwise distinct** — the assembled ``subtype``
  managed region concatenates one bullet per content-type without
  deduplication (``install.aggregate_region_contributions``), so a collision
  would ship a duplicate enum value.
* **Lifecycle fields are retained where an operation reads them** — exactly
  ``decision``/``stakeholder-update``/``trip-doc`` carry, respectively,
  ``decision_status``/``update_status``/``trip_status``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_TYPES_DIR = REPO_ROOT / "templates" / "content-types"
CROSSWALK_PATH = REPO_ROOT / "docs" / "specs" / "faceted-frontmatter-schema" / "crosswalk.yaml"
SCHEMA_PATH = REPO_ROOT / "core" / "files" / "frontmatter.schema.yaml"


def _fixed_genres() -> set[str]:
    """The fixed nine-shape genre vocabulary, sourced from the schema's
    baseline ``genres:`` enum — the single source of truth (RFC-0009 §B;
    ADR-0011 decision 1). Read here rather than re-declared so a crosswalk
    genre can't validate against a stale copy of the vocabulary; that the
    schema's enum *is* exactly the nine is pinned by
    ``test_frontmatter_schema_shape``."""
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    return set(schema["genres"])


# The three subtype-scoped lifecycle fields that shipped operations read, keyed
# by the content-type that owns each (spec Always-do; verified readers:
# ``status-synthesis`` and ``onboarding-pack``).
EXPECTED_LIFECYCLE_FIELDS = {
    "decision": "decision_status",
    "stakeholder-update": "update_status",
    "trip-doc": "trip_status",
}


def _content_type_dir_names() -> set[str]:
    return {p.name for p in CONTENT_TYPES_DIR.iterdir() if p.is_dir()}


def _load_crosswalk() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(CROSSWALK_PATH.read_text("utf-8"))
    return data


def test_crosswalk_keys_are_exactly_the_content_type_dirs() -> None:
    """Total mapping: keys == the twelve content-type directory names."""
    crosswalk = _load_crosswalk()
    assert set(crosswalk) == _content_type_dir_names()


def test_every_genre_is_one_of_the_fixed_nine() -> None:
    fixed_genres = _fixed_genres()
    crosswalk = _load_crosswalk()
    for legacy_type, row in crosswalk.items():
        assert row["genre"] in fixed_genres, (
            f"{legacy_type}: genre {row['genre']!r} is not one of the fixed nine"
        )


def test_every_subtype_differs_from_its_genre() -> None:
    crosswalk = _load_crosswalk()
    for legacy_type, row in crosswalk.items():
        assert row["subtype"] != row["genre"], (
            f"{legacy_type}: subtype must refine, not duplicate, its genre "
            f"(both are {row['genre']!r})"
        )


def test_subtype_values_are_pairwise_distinct() -> None:
    """The assembled ``subtype`` region has no duplicate lines because no two
    content-types share a subtype (the aggregator does not deduplicate)."""
    crosswalk = _load_crosswalk()
    subtypes = [row["subtype"] for row in crosswalk.values()]
    assert len(subtypes) == len(set(subtypes)), (
        f"subtype values are not pairwise distinct: {sorted(subtypes)}"
    )


def test_lifecycle_fields_retained_on_their_owning_content_types() -> None:
    crosswalk = _load_crosswalk()
    declared = {
        legacy_type: row["lifecycle_field"]
        for legacy_type, row in crosswalk.items()
        if "lifecycle_field" in row
    }
    assert declared == EXPECTED_LIFECYCLE_FIELDS


def test_every_row_has_genre_and_subtype() -> None:
    crosswalk = _load_crosswalk()
    for legacy_type, row in crosswalk.items():
        assert set(row) <= {"genre", "subtype", "lifecycle_field"}, (
            f"{legacy_type}: unexpected keys {set(row) - {'genre', 'subtype', 'lifecycle_field'}}"
        )
        assert isinstance(row.get("genre"), str), f"{legacy_type}: missing genre"
        assert isinstance(row.get("subtype"), str), f"{legacy_type}: missing subtype"
