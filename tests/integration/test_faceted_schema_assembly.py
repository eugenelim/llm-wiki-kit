"""End-to-end faceting assembly over a real ``wiki init`` (RFC-0009, ADR-0011).

Renders a content-type-bearing recipe into a temp vault and asserts the
assembled ``frontmatter.schema.yaml`` carries the facet model:

* the assembled ``subtype`` enum equals the union of installed content-types'
  ``subtype`` contributions, with no duplicate lines (the region aggregator
  concatenates without deduplicating, so the crosswalk's pairwise-distinct
  invariant is what guarantees this);
* the assembled ``genre`` enum is exactly the fixed nine, independent of which
  content-types are installed (``genre`` is a baseline enum, not contributed);
* the fused ``type`` is gone and ``workspaces`` (RFC-0008) survives;
* the shipped workspace ``.base`` lenses render byte-for-byte unchanged.

Uses the ``personal`` recipe (installs the ``action-item``, ``decision``,
``meeting``, ``recipe``, and ``trip-doc`` content-types plus the
``content-studio``/``planning`` workspace lenses).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACES_DIR = REPO_ROOT / "templates" / "workspaces"

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


def _render_personal_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--recipe", "personal"]) == 0
    return vault


# The subtypes the ``personal`` recipe's content-types (action-item, decision,
# meeting, recipe, trip-doc) contribute. Hard-coded — not derived from the same
# render under test — so a silently-dropped contribution shrinks the assembled
# set and fails the equality, rather than shrinking the expectation to match.
PERSONAL_SUBTYPES = {"action-item", "decision-record", "meeting", "recipe", "trip"}


def test_assembled_subtype_enum_is_union_with_no_duplicates(tmp_path: Path) -> None:
    vault = _render_personal_vault(tmp_path)
    schema_text = (vault / "frontmatter.schema.yaml").read_text(encoding="utf-8")
    schema = yaml.safe_load(schema_text)

    subtypes = schema["subtypes"]
    assert set(subtypes) == PERSONAL_SUBTYPES
    assert len(subtypes) == len(set(subtypes)), (
        f"assembled subtype enum has duplicate lines: {subtypes}"
    )


def test_assembled_genre_enum_is_the_fixed_nine(tmp_path: Path) -> None:
    vault = _render_personal_vault(tmp_path)
    schema = yaml.safe_load((vault / "frontmatter.schema.yaml").read_text("utf-8"))
    # Independent of which content-types are installed: genre is a baseline enum.
    assert schema["genres"] == FIXED_GENRES


def test_type_absent_and_workspaces_present(tmp_path: Path) -> None:
    vault = _render_personal_vault(tmp_path)
    schema = yaml.safe_load((vault / "frontmatter.schema.yaml").read_text("utf-8"))
    assert "type" not in schema
    assert "types" not in schema
    assert "type" not in schema["required"]
    assert schema["required"][:2] == ["genre", "subtype"]
    assert schema["fields"]["workspaces"] == {
        "type": "list",
        "items": "string",
        "optional": True,
    }


def test_workspace_base_lenses_render_byte_unchanged(tmp_path: Path) -> None:
    vault = _render_personal_vault(tmp_path)
    rendered_bases = list(vault.rglob("*.base"))
    assert rendered_bases, "expected the personal recipe to render workspace lenses"
    for rendered in rendered_bases:
        source = WORKSPACES_DIR / rendered.stem / "files" / rendered.name
        assert source.exists(), f"no shipped source for rendered {rendered.name}"
        assert rendered.read_bytes() == source.read_bytes(), (
            f"{rendered.name} was transformed during render; .base files install verbatim"
        )


def test_operation_skill_deferral_resolved() -> None:
    """The operation-SKILL `type`/`types`-region deferral this spec registered
    was CLOSED by the operations-and-search-rekey spec, so the
    faceted-frontmatter-schema backlog section no longer carries it. The
    still-open starter-seed-page deferral remains under the section."""
    backlog = (REPO_ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    assert "## faceted-frontmatter-schema" in backlog
    # The operation-SKILL deferral bullet (and its `types`-region language) is gone.
    assert "Operation SKILLs reference the removed" not in backlog
    assert "managed `types` region" not in backlog
    # The still-open deferral under the section survives.
    assert "Starter seed pages still carry the fused `type:`" in backlog
