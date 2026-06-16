"""Goal-based pins for the three container registries (RFC-0009 §D).

A *container* is a bounded instance with its own identity — a trip, a medical
case, a project — homed under a per-type registry ``efforts/<type>/``. Each
registry is an ontology primitive that declares a ``container_mode`` in its
free-form ``config:`` block: ``folder`` (exclusive material, instance is a
folder) or ``hub`` (shared material, instance is a single page whose members
join by ``parent:``). The kit core never branches on the value — it is read by
this test and by the vault-side agent docs — so this is goal-based, not TDD.

Each registry seeds ``efforts/<type>/README.md`` + a ``genre: moc``
``_index.md`` and declares ``requires: [efforts]`` so the base ``efforts/``
folder and its map arrive transitively. No registry seeds a genre/lifecycle
subfolder (the old ``trips`` ``upcoming/``/``past/`` convention is gone —
lifecycle is the ``status`` facet).

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "efforts
registries", "container_mode declared", Never-do genre/lifecycle subfolder).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGIES_DIR = REPO_ROOT / "templates" / "ontologies"

# Container registry → declared container_mode.
CONTAINER_MODES: dict[str, str] = {
    "trips": "folder",
    "cases": "folder",
    "projects": "hub",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A registry's seed tree must not nest a genre/lifecycle/area subfolder.
FORBIDDEN_SUBFOLDERS = {
    "upcoming",
    "past",
    "sources",
    "drafts",
    "records",
    "archive",
    "someday",
    "areas",
}


def _manifest(reg: str) -> dict[str, object]:
    data = yaml.safe_load((ONTOLOGIES_DIR / reg / "primitive.yaml").read_text("utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.parametrize("reg", sorted(CONTAINER_MODES))
def test_container_mode_declared(reg: str) -> None:
    m = _manifest(reg)
    config = m.get("config")
    assert isinstance(config, dict), f"{reg}: no config block"
    mode = config.get("container_mode")
    assert mode in {"folder", "hub"}, f"{reg}: container_mode={mode!r} not folder|hub"
    expected = CONTAINER_MODES[reg]
    assert mode == expected, f"{reg}: container_mode={mode!r}, expected {expected!r}"


@pytest.mark.parametrize("reg", sorted(CONTAINER_MODES))
def test_container_requires_efforts(reg: str) -> None:
    m = _manifest(reg)
    reqs = m.get("requires")
    assert reqs == ["efforts"], f"{reg}: requires={reqs!r}, expected ['efforts']"


@pytest.mark.parametrize("reg", sorted(CONTAINER_MODES))
def test_container_seeds_under_efforts(reg: str) -> None:
    base = ONTOLOGIES_DIR / reg / "files" / "wiki" / "efforts" / reg
    readme = base / "README.md"
    index = base / "_index.md"
    assert readme.is_file(), f"missing {readme}"
    assert index.is_file(), f"missing {index}"


@pytest.mark.parametrize("reg", sorted(CONTAINER_MODES))
def test_container_index_is_complete_moc(reg: str) -> None:
    index = ONTOLOGIES_DIR / reg / "files" / "wiki" / "efforts" / reg / "_index.md"
    parts = re.split(r"(?m)^---$", index.read_text("utf-8"), maxsplit=2)
    assert len(parts) >= 3 and parts[0] == "", f"{index}: no frontmatter"
    fm = yaml.safe_load(parts[1])
    for field in ("genre", "subtype", "status", "provenance", "created", "modified"):
        assert field in fm, f"{reg}/_index.md missing {field!r}"
    assert fm["genre"] == "moc"
    assert fm["subtype"] == "moc"
    assert fm["status"] in {"active", "draft", "archived", "someday"}
    assert fm["provenance"] in {"extracted", "synthesized", "mixed"}
    for d in ("created", "modified"):
        assert _DATE_RE.match(str(fm[d])), f"{reg}/_index.md {d}={fm[d]!r} not literal YYYY-MM-DD"


@pytest.mark.parametrize("reg", sorted(CONTAINER_MODES))
def test_container_seeds_no_genre_or_lifecycle_subfolder(reg: str) -> None:
    """Container contents are flat; the only permitted subfolder is a bulk sink."""
    seed_root = ONTOLOGIES_DIR / reg / "files" / "wiki"
    for path in seed_root.rglob("*"):
        if path.is_dir() and path.name in FORBIDDEN_SUBFOLDERS:
            raise AssertionError(f"{reg} seeds forbidden subfolder {path.relative_to(seed_root)}")
