"""T2 model-surface tests for the workspace-primitive spec.

Pins the five workspace-only ``Primitive`` fields (``scope``, ``agent``,
``operations``, ``bootstrap``, ``view``) and the kind-gated validator that
rejects them on any non-workspace primitive — mirroring the existing
``_routing_only_on_content_types`` validator.

Contract under test (spec AC-2 + the cross-cutting-scope AC):

- all five fields validate on ``kind: workspace``;
- each raises a ``ValidationError`` on a non-workspace kind;
- all five are optional (a minimal ``kind: workspace`` manifest validates);
- a workspace with empty or absent ``scope`` validates (the cross-cutting
  lens case — "covers all notes").
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.models import Primitive, PrimitiveKind, WorkspaceScope


def _workspace(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "content-studio",
        "kind": "workspace",
        "version": "0.1.0",
        "description": "A content-studio lens.",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Fields accepted on kind: workspace
# ---------------------------------------------------------------------------


def test_all_workspace_fields_validate_on_workspace_kind() -> None:
    primitive = Primitive.model_validate(
        _workspace(
            scope={"workspaces": ["content-studio"]},
            agent="personal-coordinator",
            operations=["weekly-digest"],
            bootstrap="files/bootstrap.md",
            view="content-studio.base",
        )
    )
    assert primitive.kind is PrimitiveKind.WORKSPACE
    assert primitive.scope == WorkspaceScope(workspaces=["content-studio"])
    assert primitive.agent == "personal-coordinator"
    assert primitive.operations == ["weekly-digest"]
    assert primitive.bootstrap == "files/bootstrap.md"
    assert primitive.view == "content-studio.base"


def test_minimal_workspace_manifest_validates_with_all_fields_optional() -> None:
    """AC-2: every workspace field is optional — a bare manifest validates."""

    primitive = Primitive.model_validate(_workspace())
    assert primitive.scope is None
    assert primitive.agent is None
    assert primitive.operations == []
    assert primitive.bootstrap is None
    assert primitive.view is None


def test_empty_and_absent_scope_both_validate() -> None:
    """A workspace with empty or absent ``scope`` validates (cross-cutting lens)."""

    absent = Primitive.model_validate(_workspace())
    assert absent.scope is None

    empty = Primitive.model_validate(_workspace(scope={"workspaces": []}))
    assert empty.scope == WorkspaceScope(workspaces=[])


# ---------------------------------------------------------------------------
# Fields rejected on non-workspace kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("scope", {"workspaces": ["content-studio"]}),
        ("agent", "personal-coordinator"),
        ("operations", ["weekly-digest"]),
        ("bootstrap", "files/bootstrap.md"),
        ("view", "content-studio.base"),
    ],
)
@pytest.mark.parametrize("kind", ["content-type", "agent"])
def test_workspace_field_rejected_on_non_workspace_kind(
    field_name: str, value: object, kind: str
) -> None:
    """Each workspace-only field raises on a non-workspace primitive.

    Two kinds exercised (``content-type`` and ``agent``) so the validator
    is proven kind-agnostic rather than special-cased to one foil.
    """

    with pytest.raises(PydanticValidationError) as excinfo:
        Primitive.model_validate(
            {
                "name": "foo",
                "kind": kind,
                "version": "0.1.0",
                "description": "foo.",
                field_name: value,
            }
        )
    message = str(excinfo.value)
    assert field_name in message
    assert kind in message
