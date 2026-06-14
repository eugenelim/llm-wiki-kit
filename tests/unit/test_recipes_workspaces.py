"""T4 tests for workspace ``agent``/``operations`` reference validation.

``resolve_recipe_primitives`` validates, after the closure walk, that every
``kind: workspace`` primitive's ``agent`` resolves to an installed
``kind: agent`` in the closure and every ``operations`` entry resolves to an
installed ``kind: operation`` in the closure — with distinct error shapes,
mirroring the CT-3 / CT-4 agent-binding checks.

The Model A invariant (spec §Boundaries "Never do") is pinned by the
negative test: two workspaces listing the **same** operation resolve with
**no** error. Workspaces are lenses, not schedulers — there is no
CT-5-style uniqueness constraint, and workspaces never feed
``_validate_agent_bindings``.
"""

from __future__ import annotations

import pytest

from llm_wiki_kit.errors import RecipeError
from llm_wiki_kit.models import Primitive, Recipe
from llm_wiki_kit.recipes import resolve_recipe_primitives


def _make_primitive(
    name: str,
    *,
    kind: str = "content-type",
    requires: list[str] | None = None,
    **extra: object,
) -> Primitive:
    data: dict[str, object] = {
        "name": name,
        "kind": kind,
        "version": "0.1.0",
        "description": f"{name} primitive.",
        "requires": requires or [],
    }
    data.update(extra)
    return Primitive.model_validate(data)


def _core() -> Primitive:
    return _make_primitive("core", kind="infrastructure")


def _recipe(*primitives: str) -> Recipe:
    return Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": list(primitives),
        }
    )


# ---------------------------------------------------------------------------
# Happy path — agent + operation both in the closure
# ---------------------------------------------------------------------------


def test_workspace_references_resolve_when_agent_and_operations_in_closure() -> None:
    recipe = _recipe("content-studio")
    catalog = [
        _core(),
        _make_primitive(
            "content-studio",
            kind="workspace",
            requires=["personal-coordinator", "weekly-digest"],
            agent="personal-coordinator",
            operations=["weekly-digest"],
        ),
        _make_primitive("personal-coordinator", kind="agent"),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    ordered = resolve_recipe_primitives(recipe, catalog)
    assert {p.name for p in ordered} == {
        "core",
        "content-studio",
        "personal-coordinator",
        "weekly-digest",
    }


# ---------------------------------------------------------------------------
# Missing reference — agent / operation not in closure
# ---------------------------------------------------------------------------


def test_workspace_agent_not_in_closure_raises() -> None:
    recipe = _recipe("content-studio")
    catalog = [
        _core(),
        _make_primitive("content-studio", kind="workspace", agent="missing-agent"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    message = str(excinfo.value)
    assert "content-studio" in message
    assert "missing-agent" in message


def test_workspace_operation_not_in_closure_raises() -> None:
    recipe = _recipe("content-studio")
    catalog = [
        _core(),
        _make_primitive("content-studio", kind="workspace", operations=["missing-op"]),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    message = str(excinfo.value)
    assert "content-studio" in message
    assert "missing-op" in message


# ---------------------------------------------------------------------------
# Wrong kind — distinct error shapes for the agent slot vs. the operation slot
# ---------------------------------------------------------------------------


def test_workspace_agent_wrong_kind_raises() -> None:
    """``agent:`` pointing at a non-agent primitive raises ``kind: agent expected``."""

    recipe = _recipe("content-studio")
    catalog = [
        _core(),
        _make_primitive(
            "content-studio",
            kind="workspace",
            requires=["weekly-digest"],
            agent="weekly-digest",
        ),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    assert "kind: agent expected" in str(excinfo.value)


def test_workspace_operation_wrong_kind_raises() -> None:
    """An ``operations:`` entry pointing at a non-operation raises ``kind: operation expected``."""

    recipe = _recipe("content-studio")
    catalog = [
        _core(),
        _make_primitive(
            "content-studio",
            kind="workspace",
            requires=["personal-coordinator"],
            operations=["personal-coordinator"],
        ),
        _make_primitive("personal-coordinator", kind="agent"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    assert "kind: operation expected" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Model A guard — two workspaces, same operation, NO error
# ---------------------------------------------------------------------------


def test_two_workspaces_share_an_operation_without_error() -> None:
    """AC-3 / AC-4: workspaces are lenses, not schedulers — no CT-5 uniqueness."""

    recipe = _recipe("content-studio", "research-desk")
    catalog = [
        _core(),
        _make_primitive(
            "content-studio",
            kind="workspace",
            requires=["weekly-digest"],
            operations=["weekly-digest"],
        ),
        _make_primitive(
            "research-desk",
            kind="workspace",
            requires=["weekly-digest"],
            operations=["weekly-digest"],
        ),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    ordered = resolve_recipe_primitives(recipe, catalog)
    assert {"content-studio", "research-desk", "weekly-digest"} <= {p.name for p in ordered}
