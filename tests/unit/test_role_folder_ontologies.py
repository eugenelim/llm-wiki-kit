"""Goal-based pins for the four role-folder ontologies (RFC-0009 §C/§D).

A vault the kit produces locates pages by *role*, not by *kind*: under
``wiki/`` there are exactly four stable role folders — ``people/`` (entity
nodes), ``efforts/`` (bounded containers), ``library/`` (capture & reference),
``atlas/`` (synthesis). Each is seeded by an ontology primitive shipping a
README plus a ``genre: moc`` ``_index.md`` map so the vault is navigable in
plain Obsidian on day one.

These are goal-based assertions over the static seed trees — no production
logic mirrors them. The MOC ``_index.md`` frontmatter is pinned and uniform:
all six ``required:`` schema fields, ``genre: moc`` / ``subtype: moc``, and
*literal* dates (seed files are copied byte-for-byte, so a templated date
token would either flap ``regenerate.py --check`` or leak ``{{…}}`` into the
shipped page).

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "role ontologies",
"library/atlas", "every _index.md carries all six required fields").
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGIES_DIR = REPO_ROOT / "templates" / "ontologies"

# The four role-folder ontologies and the vault folder each seeds.
ROLE_FOLDERS: dict[str, str] = {
    "people": "people",
    "efforts": "efforts",
    "library": "library",
    "atlas": "atlas",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _index_frontmatter(role: str, folder: str) -> dict[str, object]:
    index_path = ONTOLOGIES_DIR / role / "files" / "wiki" / folder / "_index.md"
    assert index_path.is_file(), f"missing {index_path}"
    text = index_path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^---$", text, maxsplit=2)
    assert len(parts) >= 3 and parts[0] == "", f"{index_path}: no frontmatter block"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{index_path}: frontmatter is not a mapping"
    return data


@pytest.mark.parametrize("role", sorted(ROLE_FOLDERS))
def test_role_ontology_exists(role: str) -> None:
    assert (ONTOLOGIES_DIR / role).is_dir(), f"missing ontology primitive {role}"


@pytest.mark.parametrize("role", sorted(ROLE_FOLDERS))
def test_role_ontology_seeds_readme(role: str) -> None:
    readme = ONTOLOGIES_DIR / role / "files" / "wiki" / ROLE_FOLDERS[role] / "README.md"
    assert readme.is_file(), f"missing {readme}"
    assert readme.read_text(encoding="utf-8").strip(), f"{readme} is empty"


@pytest.mark.parametrize("role", sorted(ROLE_FOLDERS))
def test_role_ontology_index_is_complete_moc(role: str) -> None:
    """Every role-folder ``_index.md`` is a schema-complete ``genre: moc`` map."""
    fm = _index_frontmatter(role, ROLE_FOLDERS[role])
    # All six required fields present (core/files/frontmatter.schema.yaml).
    for field in ("genre", "subtype", "status", "provenance", "created", "modified"):
        assert field in fm, f"{role}/_index.md missing required field {field!r}"
    assert fm["genre"] == "moc", f"{role}/_index.md genre is {fm['genre']!r}, expected 'moc'"
    assert fm["subtype"] == "moc", f"{role}/_index.md subtype is {fm['subtype']!r}"
    assert fm["status"] in {"active", "draft", "archived", "someday"}, fm["status"]
    assert fm["provenance"] in {"extracted", "synthesized", "mixed"}, fm["provenance"]
    for date_field in ("created", "modified"):
        assert _DATE_RE.match(str(fm[date_field])), (
            f"{role}/_index.md {date_field}={fm[date_field]!r} is not a literal YYYY-MM-DD date"
        )


def test_people_readme_documents_node_subtypes() -> None:
    """The people README must collapse the former customers/vendors homes here."""
    readme = (ONTOLOGIES_DIR / "people" / "files" / "wiki" / "people" / "README.md").read_text(
        encoding="utf-8"
    )
    lowered = readme.lower()
    for term in ("organization", "vendor", "customer", "subtype"):
        assert term in lowered, f"people README does not document node subtype {term!r}"
