"""Catalog-shape pin for ``templates/content-types/*`` schema snippets.

After the faceting migration (RFC-0009, ADR-0011) every shipped content-type
primitive contributes two managed-region snippets to the rendered
``frontmatter.schema.yaml``:

* ``regions/frontmatter.schema.yaml.subtype`` — one bullet that extends the
  top-level ``subtypes:`` list (replacing the former ``.types`` snippet).
* ``regions/frontmatter.schema.yaml.fields`` — a mapping of extra frontmatter
  fields, each gated by a ``when: subtype == <subtype>`` clause so the field
  only applies to that content-type.

``genre`` is *not* a managed region — it is a fixed baseline enum in
``frontmatter.schema.yaml`` — so content-types ship no ``.genre`` snippet and
declare no ``region: genre`` / ``region: types`` contribution.

Nothing in the kit validates at render time that a field's ``when:`` clause
matches the subtype the snippet pair declares, or that the declared subtype
matches the crosswalk. A renaming mistake ships silently — the kit happily
writes the broken schema. This module is that validator, keyed to the
crosswalk (``docs/specs/faceted-frontmatter-schema/crosswalk.yaml``) as the
source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# A page-``type`` reference: the bare ``type:`` key/token or a ``type ==``
# guard. The ``\b`` on *both* branches excludes ``subtype``/``asset_type`` and
# ``subtype ==`` (no word boundary before ``type`` there); it still matches the
# legitimate field data-type declarations (``type: string``/``date``/``list``),
# so this pattern is only scanned against ``primitive.yaml``, which carries no
# such declarations — never against ``.fields`` snippets.
_PAGE_TYPE_REF = re.compile(r"\btype:|\btype ==")

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_TYPES_DIR = REPO_ROOT / "templates" / "content-types"
CROSSWALK_PATH = REPO_ROOT / "docs" / "specs" / "faceted-frontmatter-schema" / "crosswalk.yaml"


def _content_type_dirs() -> list[Path]:
    if not CONTENT_TYPES_DIR.exists():
        return []
    return sorted(p for p in CONTENT_TYPES_DIR.iterdir() if p.is_dir())


def _crosswalk() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(CROSSWALK_PATH.read_text("utf-8"))
    return data


def _parse_snippet_under(parent_key: str, snippet_path: Path) -> Any:
    """Parse a managed-region snippet as if it were nested under ``parent_key``.

    Snippets live as fragments indented two spaces, ready to be spliced into
    the rendered ``frontmatter.schema.yaml``. Wrapping with the parent key
    gives us a self-contained YAML document we can load.
    """
    body = snippet_path.read_text(encoding="utf-8")
    return yaml.safe_load(f"{parent_key}:\n{body}")


@pytest.mark.parametrize(
    "primitive_dir",
    _content_type_dirs(),
    ids=lambda p: p.name,
)
def test_subtype_snippet_matches_crosswalk_and_no_legacy_snippet(
    primitive_dir: Path,
) -> None:
    """Each content-type ships exactly one ``.subtype`` bullet equal to its
    crosswalk subtype, and ships no legacy ``.types`` / ``.genre`` snippet."""
    regions_dir = primitive_dir / "regions"
    subtype_path = regions_dir / "frontmatter.schema.yaml.subtype"
    name = primitive_dir.name

    assert subtype_path.exists(), f"missing {subtype_path}"
    assert not (regions_dir / "frontmatter.schema.yaml.types").exists(), (
        f"{name}: legacy .types snippet must be removed"
    )
    assert not (regions_dir / "frontmatter.schema.yaml.genre").exists(), (
        f"{name}: genre is a fixed baseline enum, not a managed region; no .genre snippet may exist"
    )

    expected_subtype = _crosswalk()[name]["subtype"]
    declared = _parse_snippet_under("subtypes", subtype_path).get("subtypes") or []
    assert declared == [expected_subtype], (
        f"{name}: .subtype snippet {declared!r} does not match crosswalk "
        f"subtype {expected_subtype!r}"
    )


@pytest.mark.parametrize(
    "primitive_dir",
    _content_type_dirs(),
    ids=lambda p: p.name,
)
def test_manifest_contributes_to_is_subtype_and_fields_only(
    primitive_dir: Path,
) -> None:
    """``contributes_to`` declares ``region: subtype`` + ``region: fields`` for
    the schema file; never ``region: types`` or ``region: genre``."""
    manifest = yaml.safe_load((primitive_dir / "primitive.yaml").read_text(encoding="utf-8"))
    schema_regions = {
        c["region"]
        for c in manifest.get("contributes_to", [])
        if c["file"] == "frontmatter.schema.yaml"
    }
    assert "types" not in schema_regions
    assert "genre" not in schema_regions
    assert {"subtype", "fields"} <= schema_regions, (
        f"{primitive_dir.name}: expected region: subtype + region: fields, got {schema_regions}"
    )


@pytest.mark.parametrize(
    "primitive_dir",
    _content_type_dirs(),
    ids=lambda p: p.name,
)
def test_fields_when_clauses_are_subtype_keyed(primitive_dir: Path) -> None:
    """Every field in the ``.fields`` snippet is gated by
    ``when: subtype == <subtype>`` where ``<subtype>`` is this content-type's
    crosswalk subtype — never a ``type ==`` clause."""
    regions_dir = primitive_dir / "regions"
    fields_path = regions_dir / "frontmatter.schema.yaml.fields"
    name = primitive_dir.name

    assert fields_path.exists(), f"missing {fields_path}"
    fields = _parse_snippet_under("fields", fields_path).get("fields") or {}
    assert fields, f"{fields_path} declares no fields"

    expected_clause = f"subtype == {_crosswalk()[name]['subtype']}"
    for field_name, spec in fields.items():
        assert isinstance(spec, dict), f"{fields_path}: {field_name!r} not a mapping"
        assert "when" in spec, f"{fields_path}: {field_name!r} missing 'when:'"
        assert spec["when"] == expected_clause, (
            f"{fields_path}: field {field_name!r} has when={spec['when']!r}; "
            f"expected {expected_clause!r}"
        )


@pytest.mark.parametrize(
    "primitive_dir",
    _content_type_dirs(),
    ids=lambda p: p.name,
)
def test_manifest_has_no_page_type_reference(primitive_dir: Path) -> None:
    """The ``primitive.yaml`` — including its ``description`` prose — carries no
    page-``type`` reference (AC: "no manifest description references `type`").

    A ``primitive.yaml`` legitimately contains no ``type:`` key (it uses
    ``kind:``, ``region: subtype``, …), so any ``\\btype:`` / ``type ==`` match
    is a stale page-``type`` reference the faceting migration should have
    removed (e.g. a description still saying ``type: meeting``)."""
    text = (primitive_dir / "primitive.yaml").read_text(encoding="utf-8")
    match = _PAGE_TYPE_REF.search(text)
    assert match is None, (
        f"{primitive_dir.name}/primitive.yaml references the page `type` field "
        f"at {match.group()!r}; rewrite it off `type` to `genre`/`subtype`"
    )


def test_lifecycle_fields_present_in_their_owning_content_type() -> None:
    """The three subtype-scoped lifecycle fields a shipped operation reads are
    retained, each in exactly its owning content-type's ``.fields`` snippet."""
    expected_owner = {
        "decision_status": "decision",
        "update_status": "stakeholder-update",
        "trip_status": "trip-doc",
    }
    for field, owner in expected_owner.items():
        for primitive_dir in _content_type_dirs():
            fields = (
                _parse_snippet_under(
                    "fields",
                    primitive_dir / "regions" / "frontmatter.schema.yaml.fields",
                ).get("fields")
                or {}
            )
            present = field in fields
            if primitive_dir.name == owner:
                assert present, f"{field} missing from {owner} .fields snippet"
            else:
                assert not present, (
                    f"{field} unexpectedly present in {primitive_dir.name} "
                    f"(should be scoped to {owner})"
                )


def test_content_types_directory_is_not_empty() -> None:
    """Guard against the parametrised tests silently collecting zero cases."""
    assert _content_type_dirs(), f"no content-type primitives discovered under {CONTENT_TYPES_DIR}"
