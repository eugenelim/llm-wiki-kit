"""Pins for the T3 catalog reshape (RFC-0009 role-folders-and-containers).

The five entity-kind ontologies (`customers`, `vendors`, `food`, `domains`,
`medical`) are removed and every content-type *and operation* `requires:` is
re-pointed to the role folder its pages and linked entities live in. The nine
content-type kind-folder seeds (`actions/`, `meetings/`, …) are removed too —
folders are role-only, capture pages home in `library/`.

Goal-based: parse the on-disk manifests and the seed trees; no production logic
mirrors the assertion. Recipe-level resolution (the recipes still listing the
removed ontologies until T4) is proven by the T4 layout-render test, not here.

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "ontology set",
"no dangling requires", "no kind-keyed folder"); plan §Design re-pointing table.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from llm_wiki_kit.primitives import discover_primitives

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
ONTOLOGIES_DIR = TEMPLATES_DIR / "ontologies"
CONTENT_TYPES_DIR = TEMPLATES_DIR / "content-types"
OPERATIONS_DIR = TEMPLATES_DIR / "operations"

REMOVED_ONTOLOGIES = {"customers", "vendors", "food", "domains", "medical"}

# The content-types that used to seed a kind-keyed `files/wiki/<kind>/` folder.
KIND_FOLDER_CONTENT_TYPES = {
    "action-item",
    "customer-feedback",
    "decision",
    "interview",
    "meeting",
    "receipt",
    "stakeholder-update",
    "tax-document",
    "vendor-contract",
}

# Expected new `requires:` (as sets) after re-pointing — plan §Design table.
# A relocation keeps every surviving dep; only a removed ontology is swapped.
EXPECTED_CONTENT_TYPE_REQUIRES: dict[str, set[str]] = {
    "meeting": {"people", "library"},
    "interview": {"people", "library"},
    "recipe": {"library"},
    "receipt": {"people", "library"},
    "tax-document": {"people", "library"},
    "medical-record": {"people", "library", "cases"},
    "trip-doc": {"trips", "people"},
    "vendor-contract": {"people", "library"},
    "customer-feedback": {"people", "library"},
    "stakeholder-update": {"people", "projects", "library"},
    "action-item": {"people", "library"},
    "decision": {"people", "library"},
}
EXPECTED_OPERATION_REQUIRES: dict[str, set[str]] = {
    "onboarding-pack": {"people", "projects", "decision", "customer-feedback"},
}


def _requires(manifest_path: Path) -> set[str]:
    data = yaml.safe_load(manifest_path.read_text("utf-8"))
    return set(data.get("requires") or [])


@pytest.mark.parametrize("removed", sorted(REMOVED_ONTOLOGIES))
def test_removed_ontology_dirs_are_gone(removed: str) -> None:
    assert not (ONTOLOGIES_DIR / removed).exists(), f"ontology {removed} should be removed"


def test_no_requires_names_a_removed_ontology() -> None:
    offenders: list[str] = []
    for manifest in sorted(CONTENT_TYPES_DIR.glob("*/primitive.yaml")) + sorted(
        OPERATIONS_DIR.glob("*/primitive.yaml")
    ):
        named = _requires(manifest) & REMOVED_ONTOLOGIES
        if named:
            offenders.append(f"{manifest.parent.name}: {sorted(named)}")
    assert not offenders, f"requires names removed ontologies: {offenders}"


@pytest.mark.parametrize("ct", sorted(EXPECTED_CONTENT_TYPE_REQUIRES))
def test_content_type_requires_repointed(ct: str) -> None:
    actual = _requires(CONTENT_TYPES_DIR / ct / "primitive.yaml")
    expected = EXPECTED_CONTENT_TYPE_REQUIRES[ct]
    assert actual == expected, f"{ct}: requires={sorted(actual)}, expected {sorted(expected)}"


@pytest.mark.parametrize("op", sorted(EXPECTED_OPERATION_REQUIRES))
def test_operation_requires_repointed(op: str) -> None:
    actual = _requires(OPERATIONS_DIR / op / "primitive.yaml")
    expected = EXPECTED_OPERATION_REQUIRES[op]
    assert actual == expected, f"{op}: requires={sorted(actual)}, expected {sorted(expected)}"


def test_no_content_type_seeds_a_kind_folder() -> None:
    """A content-type no longer owns a wiki folder — its pages home in library/."""
    offenders: list[str] = []
    for ct_dir in sorted(CONTENT_TYPES_DIR.iterdir()):
        wiki_seed = ct_dir / "files" / "wiki"
        if wiki_seed.exists():
            offenders.append(f"{ct_dir.name}: {wiki_seed.relative_to(CONTENT_TYPES_DIR)}")
    assert not offenders, f"content-types still seed wiki folders: {offenders}"


def test_every_named_requires_resolves_to_an_existing_primitive() -> None:
    names = {p.name for p in discover_primitives(TEMPLATES_DIR)}
    names.add("core")
    dangling: list[str] = []
    for manifest in sorted(CONTENT_TYPES_DIR.glob("*/primitive.yaml")) + sorted(
        OPERATIONS_DIR.glob("*/primitive.yaml")
    ):
        for dep in _requires(manifest):
            if dep not in names:
                dangling.append(f"{manifest.parent.name} -> {dep}")
    assert not dangling, f"requires names a non-existent primitive: {dangling}"
