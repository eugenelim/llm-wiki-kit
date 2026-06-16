"""End-to-end: every shipped recipe renders the four-role layout (RFC-0009 §C/§D).

`wiki init` over `family`, `work-os`, and `personal` must create the four
stable role folders — `people/`, `efforts/`, `library/`, `atlas/` — plus the
recipe's per-type `efforts/<type>/` container registries, and `wiki doctor`
must report no orphan/missing files. This is the layout half of the spec's
"layout renders" AC; the manifest half lives in
`tests/unit/test_requires_repoint.py`.

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "layout renders";
"ontology set").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import load_recipe, resolve_recipe_primitives

REPO_ROOT = Path(__file__).resolve().parents[2]
RECIPES_DIR = REPO_ROOT / "recipes"
CORE_DIR = REPO_ROOT / "core"
TEMPLATES_DIR = REPO_ROOT / "templates"

ROLE_FOLDERS = ("people", "efforts", "library", "atlas")

# The per-type container registries each recipe pulls in (transitively).
EXPECTED_EFFORTS: dict[str, set[str]] = {
    "family": {"trips", "cases"},
    "work-os": {"projects"},
    "personal": {"trips"},
}

REMOVED_ONTOLOGIES = {"customers", "vendors", "food", "domains", "medical"}


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_recipe_resolves_against_full_catalog(recipe: str) -> None:
    """No dangling requires — resolve_recipe_primitives accepts the recipe."""
    catalog = [load_primitive(CORE_DIR), *discover_primitives(TEMPLATES_DIR)]
    resolved = resolve_recipe_primitives(load_recipe(RECIPES_DIR / f"{recipe}.yaml"), catalog)
    assert resolved, f"{recipe} resolved to an empty closure"


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_recipe_primitives_list_names_no_removed_ontology(recipe: str) -> None:
    data = load_recipe(RECIPES_DIR / f"{recipe}.yaml")
    named = set(data.primitives) & REMOVED_ONTOLOGIES
    assert not named, f"{recipe} primitives list names removed ontologies: {sorted(named)}"


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_init_renders_four_role_folders(tmp_path: Path, recipe: str) -> None:
    vault = tmp_path / recipe
    assert main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0
    wiki = vault / "wiki"
    for role in ROLE_FOLDERS:
        folder = wiki / role
        assert folder.is_dir(), f"{recipe}: missing wiki/{role}/"
        assert (folder / "README.md").is_file(), f"{recipe}: missing wiki/{role}/README.md"
        assert (folder / "_index.md").is_file(), f"{recipe}: missing wiki/{role}/_index.md"


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_init_renders_recipe_container_registries(tmp_path: Path, recipe: str) -> None:
    vault = tmp_path / recipe
    assert main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0
    efforts = vault / "wiki" / "efforts"
    for reg in EXPECTED_EFFORTS[recipe]:
        reg_dir = efforts / reg
        assert reg_dir.is_dir(), f"{recipe}: missing wiki/efforts/{reg}/"
        assert (reg_dir / "_index.md").is_file(), f"{recipe}: missing wiki/efforts/{reg}/_index.md"


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_init_renders_no_removed_or_kind_folder(tmp_path: Path, recipe: str) -> None:
    vault = tmp_path / recipe
    assert main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0
    wiki = vault / "wiki"
    forbidden = REMOVED_ONTOLOGIES | {
        "meetings",
        "actions",
        "decisions",
        "interviews",
        "customer-feedback",
        "receipts",
        "tax",
        "stakeholder-updates",
        "vendor-contracts",
    }
    present = {p.name for p in wiki.iterdir() if p.is_dir()}
    leaked = present & forbidden
    assert not leaked, f"{recipe}: kit-rendered a forbidden folder: {sorted(leaked)}"


@pytest.mark.parametrize("recipe", sorted(EXPECTED_EFFORTS))
def test_doctor_reports_no_orphan_or_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recipe: str
) -> None:
    vault = tmp_path / recipe
    assert main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0
    # `wiki doctor` operates on the cwd; it exits 0 when the vault is clean
    # (no orphan/missing/drift).
    monkeypatch.chdir(vault)
    assert main(["doctor"]) == 0, f"{recipe}: wiki doctor reported issues"
