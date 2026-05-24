"""PR-3 tests for the ``Recipe.agents`` block and its closure-walk validator.

Covers RFC-0004 / wiki-agents CT-3 through CT-6 plus two structural
sanity tests:

- CT-3 (split into happy + failure halves): the closure-walk validator
  accepts a binding whose operation is in the recipe's primitives:
  closure, and rejects the same binding once the operation is removed
  from primitives:.
- CT-4: a binding whose key resolves to a non-agent primitive raises
  ``RecipeError`` containing ``kind: agent expected``.
- CT-5: two agents binding the same operation raises ``RecipeError``
  naming both agents and the operation.
- CT-6: ``agents.X.runs: []`` raises a Pydantic ``ValidationError`` at
  recipe-load time, *before* the closure walk runs (via
  ``min_length=1`` on the field). This distinguishes the
  Pydantic-level shape check from the closure-walk RecipeError tests.
- ``agents: {}`` round-trips as a no-op (closure-walk skips the empty
  block).
- The three shipped recipes (``recipes/family.yaml``,
  ``recipes/work-os.yaml``, ``recipes/personal.yaml``) load and resolve
  against the live catalog after PR-3 adds ``agents: {}`` to each.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import RecipeError
from llm_wiki_kit.models import AgentBinding, Primitive, Recipe
from llm_wiki_kit.recipes import load_recipe, resolve_recipe_primitives

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RECIPES_DIR = REPO_ROOT / "recipes"
CORE_DIR = REPO_ROOT / "core"
TEMPLATES_DIR = REPO_ROOT / "templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_primitive(
    name: str,
    *,
    kind: str = "content-type",
    requires: list[str] | None = None,
) -> Primitive:
    return Primitive.model_validate(
        {
            "name": name,
            "kind": kind,
            "version": "0.1.0",
            "description": f"{name} primitive.",
            "requires": requires or [],
        }
    )


def _core() -> Primitive:
    return _make_primitive("core", kind="infrastructure")


# ---------------------------------------------------------------------------
# CT-6: empty runs list raises Pydantic ValidationError at recipe-load
# ---------------------------------------------------------------------------


def test_recipe_agents_empty_runs_list_raises_validation_error() -> None:
    """CT-6: ``agents.X.runs: []`` raises Pydantic ValidationError, not RecipeError.

    The ``min_length=1`` constraint on ``AgentBinding.runs`` fires
    during Pydantic model validation — *before* the closure-walk
    validator runs. This is the load-time shape check; CT-3 / CT-4 /
    CT-5 are the closure-walk semantic checks. Keeping them distinct
    means a future contributor cannot consolidate the four into one
    test without losing the load-vs-closure boundary.
    """

    with pytest.raises(PydanticValidationError) as excinfo:
        AgentBinding.model_validate({"runs": []})
    locs = {".".join(str(p) for p in err["loc"]) for err in excinfo.value.errors()}
    assert "runs" in locs

    with pytest.raises(PydanticValidationError):
        Recipe.model_validate(
            {
                "name": "r",
                "version": "0.1.0",
                "description": "x",
                "primitives": ["core"],
                "agents": {"household-manager": {"runs": []}},
            }
        )


def test_agent_binding_runs_entries_must_match_name_pattern() -> None:
    """``runs:`` entries are pattern-validated against ``NAME_PATTERN`` at recipe-load.

    Per spec §"Contracts with other modules": "Names validated against
    ``NAME_PATTERN``." A capital / underscore name fails at the
    Pydantic layer — before the closure walk gets a chance to look
    the name up against the catalog — so authoring typos surface
    with a clearer load-time error than the closure walk's
    "not in closure" message.
    """

    with pytest.raises(PydanticValidationError) as excinfo:
        AgentBinding.model_validate({"runs": ["Weekly_Digest"]})
    locs = {".".join(str(p) for p in err["loc"]) for err in excinfo.value.errors()}
    assert any("runs" in loc for loc in locs)


# ---------------------------------------------------------------------------
# CT-3: closure-walk validator on the operation membership rule
# ---------------------------------------------------------------------------


def test_recipe_agents_block_validates_closure_happy_path() -> None:
    """CT-3 (happy half): binding validates when both agent + operation are in the closure."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["household-manager", "weekly-digest"],
            "agents": {"household-manager": {"runs": ["weekly-digest"]}},
        }
    )
    catalog = [
        _core(),
        _make_primitive("household-manager", kind="agent"),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    ordered = resolve_recipe_primitives(recipe, catalog)
    assert {p.name for p in ordered} == {"core", "household-manager", "weekly-digest"}


def test_recipe_agents_missing_operation_raises_recipe_error() -> None:
    """CT-3 (failure half): operation missing from closure → RecipeError naming both."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            # ``weekly-digest`` is not in primitives, so the closure
            # cannot reach it — the agent binding is therefore invalid.
            "primitives": ["household-manager"],
            "agents": {"household-manager": {"runs": ["weekly-digest"]}},
        }
    )
    catalog = [
        _core(),
        _make_primitive("household-manager", kind="agent"),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    message = str(excinfo.value)
    assert "weekly-digest" in message
    assert "household-manager" in message


# ---------------------------------------------------------------------------
# CT-4: closure-walk validator on the agent-kind rule
# ---------------------------------------------------------------------------


def test_recipe_agents_wrong_kind_agent_raises_recipe_error() -> None:
    """CT-4: ``agents:`` key resolving to non-agent → RecipeError ``kind: agent expected``."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["weekly-digest", "meal-planning"],
            # ``weekly-digest`` is a kind: operation primitive; binding
            # it as an agent is a recipe-author bug.
            "agents": {"weekly-digest": {"runs": ["meal-planning"]}},
        }
    )
    catalog = [
        _core(),
        _make_primitive("weekly-digest", kind="operation"),
        _make_primitive("meal-planning", kind="operation"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    assert "kind: agent expected" in str(excinfo.value)


def test_recipe_agents_runs_entry_must_be_operation_kind() -> None:
    """Symmetric kind check: a ``runs:`` entry resolving to a non-operation raises.

    The closure-walk validator has two distinct kind checks (agent
    slot vs. operation slot); CT-4 pins the agent half, this test
    pins the operation half. Without it, a regression that miscategorised
    an agent-named ``runs:`` entry as a valid operation would land green.
    """

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["household-manager", "trip-planner"],
            # ``trip-planner`` is itself a kind: agent primitive, not an
            # operation — binding it inside ``runs:`` is a recipe-author bug.
            "agents": {"household-manager": {"runs": ["trip-planner"]}},
        }
    )
    catalog = [
        _core(),
        _make_primitive("household-manager", kind="agent"),
        _make_primitive("trip-planner", kind="agent"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    assert "kind: operation expected" in str(excinfo.value)


# ---------------------------------------------------------------------------
# CT-5: closure-walk validator on one-agent-per-op uniqueness
# ---------------------------------------------------------------------------


def test_recipe_agents_duplicate_operation_binding_raises() -> None:
    """CT-5: two agents both listing the same op → RecipeError naming both agents + the op."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["household-manager", "trip-planner", "weekly-digest"],
            "agents": {
                "household-manager": {"runs": ["weekly-digest"]},
                "trip-planner": {"runs": ["weekly-digest"]},
            },
        }
    )
    catalog = [
        _core(),
        _make_primitive("household-manager", kind="agent"),
        _make_primitive("trip-planner", kind="agent"),
        _make_primitive("weekly-digest", kind="operation"),
    ]
    with pytest.raises(RecipeError) as excinfo:
        resolve_recipe_primitives(recipe, catalog)
    message = str(excinfo.value)
    assert "weekly-digest" in message
    assert "household-manager" in message
    assert "trip-planner" in message


# ---------------------------------------------------------------------------
# Empty agents block is a no-op
# ---------------------------------------------------------------------------


def test_recipe_with_empty_agents_block_roundtrips() -> None:
    """``agents: {}`` loads, closure walks, no validation fires over the empty block."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["core"],
            "agents": {},
        }
    )
    assert recipe.agents == {}
    catalog = [_core()]
    ordered = resolve_recipe_primitives(recipe, catalog)
    assert [p.name for p in ordered] == ["core"]


def test_recipe_defaults_agents_to_empty_dict_when_absent() -> None:
    """Absent ``agents:`` field defaults to ``{}`` — pre-RFC-4 recipes load unchanged."""

    recipe = Recipe.model_validate(
        {
            "name": "r",
            "version": "0.1.0",
            "description": "x",
            "primitives": ["core"],
        }
    )
    assert recipe.agents == {}


# ---------------------------------------------------------------------------
# Existing shipped recipes load with their new empty ``agents: {}`` blocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["family", "personal", "work-os"])
def test_existing_recipes_load_with_empty_agents_blocks(name: str) -> None:
    """PR-3 edits ``recipes/{family,work-os,personal}.yaml`` to ship empty
    ``agents: {}`` blocks. The loader path must keep working — both
    ``load_recipe`` and ``resolve_recipe_primitives`` should succeed on
    every shipped recipe.
    """

    from llm_wiki_kit.primitives import discover_primitives, load_primitive

    recipe = load_recipe(RECIPES_DIR / f"{name}.yaml")
    assert recipe.agents == {}
    catalog = [load_primitive(CORE_DIR), *discover_primitives(TEMPLATES_DIR)]
    ordered = resolve_recipe_primitives(recipe, catalog)
    # Existing live-catalog tests already pin the closure shape per
    # recipe; this assertion is just "resolution succeeded with the
    # empty agents block in place."
    assert "core" in {p.name for p in ordered}
