"""Facet pin for content-type page templates (RFC-0009, ADR-0011).

Each content-type ships a page template under ``files/_templates/<ct>.md``
whose frontmatter pre-stamps the facet fields so a hand-created note is never
an orphan (RFC-0009 §G). After faceting, that frontmatter stamps ``genre:``,
``subtype:`` (per the crosswalk), and ``status:`` — and never the removed
fused ``type:``.

Line-based, not YAML-parsed: the templates carry Obsidian placeholders
(``{{date:YYYY-MM-DD}}``, ``{{title}}``) that are not valid YAML.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_TYPES_DIR = REPO_ROOT / "templates" / "content-types"
CROSSWALK_PATH = REPO_ROOT / "docs" / "specs" / "faceted-frontmatter-schema" / "crosswalk.yaml"


def _crosswalk() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(CROSSWALK_PATH.read_text("utf-8"))
    return data


def _content_type_dirs() -> list[Path]:
    if not CONTENT_TYPES_DIR.exists():
        return []
    return sorted(p for p in CONTENT_TYPES_DIR.iterdir() if p.is_dir())


def _frontmatter_lines(template_path: Path) -> list[str]:
    text = template_path.read_text(encoding="utf-8")
    # Split on line-anchored ``---`` fences so a ``---`` horizontal rule in the
    # body can't truncate the frontmatter block early.
    parts = re.split(r"(?m)^---$", text, maxsplit=2)
    assert len(parts) >= 3 and parts[0] == "", f"{template_path}: no frontmatter block"
    return parts[1].splitlines()


@pytest.mark.parametrize(
    "primitive_dir",
    _content_type_dirs(),
    ids=lambda p: p.name,
)
def test_template_stamps_facets_not_type(primitive_dir: Path) -> None:
    name = primitive_dir.name
    template_path = primitive_dir / "files" / "_templates" / f"{name}.md"
    assert template_path.exists(), f"missing {template_path}"

    lines = _frontmatter_lines(template_path)
    row = _crosswalk()[name]

    assert f"genre: {row['genre']}" in lines, f"{template_path}: expected 'genre: {row['genre']}'"
    assert f"subtype: {row['subtype']}" in lines, (
        f"{template_path}: expected 'subtype: {row['subtype']}'"
    )
    assert any(line.startswith("status:") for line in lines), (
        f"{template_path}: frontmatter must stamp 'status:'"
    )
    assert not any(line.startswith("type:") for line in lines), (
        f"{template_path}: frontmatter must not stamp the removed 'type:' field"
    )
