"""PR-3 model-surface test for ``OperationContract.preferred_agent``.

Covers CT-7 of ``docs/specs/wiki-agents/spec.md`` — the additive
``preferred_agent: str | None`` field on ``OperationContract``. Names
validate against the standard ``NAME_PATTERN``; absent / null is the
v2.0.0 baseline (no agent suggested by the operation author).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.models import OperationContract


def _base_contract(**overrides: object) -> dict[str, object]:
    """Minimum-fields contract payload; callers override ``preferred_agent``."""

    payload: dict[str, object] = {
        "name": "weekly-digest",
        "description": "Weekly digest operation.",
    }
    payload.update(overrides)
    return payload


def test_operation_contract_preferred_agent_validates_name_pattern() -> None:
    """CT-7: valid names load; capital/underscore names are rejected at contract-load."""

    contract = OperationContract.model_validate(
        _base_contract(preferred_agent="household-manager"),
    )
    assert contract.preferred_agent == "household-manager"

    with pytest.raises(PydanticValidationError) as excinfo:
        OperationContract.model_validate(
            _base_contract(preferred_agent="Household_Manager"),
        )
    locs = {".".join(str(p) for p in err["loc"]) for err in excinfo.value.errors()}
    assert "preferred_agent" in locs


def test_operation_contract_preferred_agent_defaults_to_none() -> None:
    """Absent ``preferred_agent`` is the v2.0.0 baseline — no suggestion."""

    contract = OperationContract.model_validate(_base_contract())
    assert contract.preferred_agent is None


def test_operation_contract_preferred_agent_accepts_null() -> None:
    """Explicit ``preferred_agent: null`` round-trips as ``None``."""

    contract = OperationContract.model_validate(_base_contract(preferred_agent=None))
    assert contract.preferred_agent is None
