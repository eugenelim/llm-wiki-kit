"""T5: the shipped ``content-studio`` example workspace installs cleanly.

Spec AC-6: after ``wiki add workspace:content-studio`` the vault contains a
``content-studio.base`` byte-identical to the shipped template and a
``bootstrap.md``. Also pins that the example's manifest passes ``Primitive``
validation and that its ``agent``/``operations`` references resolve against
the real catalog at recipe-resolve time (exercising T4 on the real example).

Runs against the real shipped kit (default ``kit_root``), so a regression in
the example's own files or manifest surfaces here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main
from llm_wiki_kit.models import PrimitiveKind, Recipe
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import resolve_recipe_primitives

REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_DIR = REPO_ROOT / "templates" / "workspaces" / "content-studio"


def test_add_content_studio_installs_base_verbatim_and_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--recipe", "personal"]) == 0

    monkeypatch.chdir(vault)
    assert main(["add", "workspace:content-studio"]) == 0

    base = vault / "content-studio.base"
    assert base.is_file()
    shipped = _WORKSPACE_DIR / "files" / "content-studio.base"
    assert base.read_bytes() == shipped.read_bytes()

    assert (vault / "bootstrap.md").is_file()

    # End-to-end journey (plan §Construction tests): the same real install
    # that wrote the .base must surface through ``wiki workspaces``, reading
    # the journal ``wiki add`` wrote against the real shipped catalog — not a
    # hand-seeded fixture. A drift between what ``add`` journals and what the
    # lister recovers from the catalog would be invisible to the unit tests.
    capsys.readouterr()  # drop the add/init output
    assert main(["workspaces"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "NAME\tSCOPE\tAGENT\tOPERATIONS"
    assert "content-studio\tcontent-studio\tpersonal-coordinator\t—" in out


def test_content_studio_manifest_validates_and_references_resolve() -> None:
    primitive = load_primitive(_WORKSPACE_DIR)
    assert primitive.kind is PrimitiveKind.WORKSPACE
    assert primitive.agent == "personal-coordinator"

    catalog = [load_primitive(REPO_ROOT / "core")]
    catalog.extend(discover_primitives(REPO_ROOT / "templates"))
    recipe = Recipe.model_validate(
        {
            "name": "studio-test",
            "version": "0.1.0",
            "description": "Resolve the content-studio example.",
            "primitives": ["content-studio"],
        }
    )
    # No raise: the example's agent reference (personal-coordinator)
    # resolves to a kind: agent primitive in the closure.
    ordered = resolve_recipe_primitives(recipe, catalog)
    names = {p.name for p in ordered}
    assert {"content-studio", "personal-coordinator"} <= names
