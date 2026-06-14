"""T3: the real ``personal`` recipe composes the content-studio + planning lenses.

Distinct from ``test_recipes_workspaces.py`` (synthetic fixtures for the
reference-validation logic) — these resolve the **shipped** ``recipes/personal.yaml``
against the **real** catalog, the personal-recipe-workspaces follow-on's contract.

The Model A guard (spec AC-4): the ``planning`` lens surfaces ``follow-up-tracker``
and ``weekly-digest``, which the recipe's ``personal-coordinator`` ``agents:``
binding already runs. That overlap must raise **no** error — *and* the two
operations must still resolve in the closure (so the no-throw can't pass by the
workspace operations being silently skipped).
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki_kit.models import Primitive, PrimitiveKind
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import load_recipe, resolve_recipe_primitives

REPO_ROOT = Path(__file__).resolve().parents[2]
RECIPES_DIR = REPO_ROOT / "recipes"
CORE_DIR = REPO_ROOT / "core"
TEMPLATES_DIR = REPO_ROOT / "templates"


def _resolved_personal() -> list[Primitive]:
    recipe = load_recipe(RECIPES_DIR / "personal.yaml")
    catalog = [load_primitive(CORE_DIR), *discover_primitives(TEMPLATES_DIR)]
    return resolve_recipe_primitives(recipe, catalog)


def test_personal_closure_includes_both_lenses() -> None:
    ordered = _resolved_personal()
    names = {p.name for p in ordered}
    assert {"content-studio", "planning"} <= names


def test_personal_lens_operation_overlap_resolves_without_error() -> None:
    # No raise (Model A: a lens surfacing an operation the agents: block also
    # binds is allowed) — and the overlapping operations are still in the
    # closure as kind: operation, proving workspace references were validated,
    # not skipped.
    ordered = _resolved_personal()
    by_name = {p.name: p for p in ordered}
    for op in ("follow-up-tracker", "weekly-digest"):
        assert op in by_name
        assert by_name[op].kind is PrimitiveKind.OPERATION
