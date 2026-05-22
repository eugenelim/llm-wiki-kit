"""Unit tests for outcome-named entry points — PR-1.

Pins:

- ``OperationContract.outcomes`` schema (spec §Inputs §1, AC
  "Schema").
- ``RESERVED_OUTCOME_VERBS`` matches the set of registered
  top-level ``wiki`` subcommands plus the standard discovery
  aliases (spec §Inputs §2 rule 3).
- ``OUTCOME_VERB_STEMS`` carries the illustrative stem list the
  spec names (spec §Inputs §2 rule 4).
- ``is_well_formed_outcome_verb`` enforces rules 1-4 and 6 (spec
  §Inputs §2, AC "Well-formed verb").
- ``check_outcome_verb_uniqueness`` enforces rule 5 plus the
  verb-vs-operation-name shadow check (spec §Edge case "Verb
  collision within the catalog", AC "Catalog uniqueness", AC
  "Verb does not shadow any operation name").
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.cli import build_parser
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import OperationContract
from llm_wiki_kit.primitives import (
    OUTCOME_VERB_STEMS,
    RESERVED_OUTCOME_VERBS,
    check_outcome_verb_uniqueness,
    discover_primitives,
    is_well_formed_outcome_verb,
)

# Shipped catalog root — used by the v2.0.0-catalog and shipped-verbs
# tests below. Anchored on ``__file__`` (``tests/unit/<this>.py`` →
# two parents → repo root). Works for the editable install the
# project's dev workflow uses; a wheel install would resolve
# ``__file__`` into site-packages where ``templates/`` is absent —
# these tests would then error (``FileNotFoundError`` on the
# ``iterdir()`` calls below), not skip. The kit's CI only runs the
# editable layout so this is not in scope for PR-2.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIPPED_TEMPLATES = _REPO_ROOT / "templates"
_SHIPPED_OPERATIONS = _SHIPPED_TEMPLATES / "operations"

# ---------------------------------------------------------------------------
# Step 1 — ``OperationContract.outcomes`` schema
# ---------------------------------------------------------------------------


def _base_contract_payload() -> dict[str, object]:
    """Minimal valid ``OperationContract`` payload (no outcomes)."""

    return {
        "name": "weekly-digest",
        "description": "Summarize the week.",
    }


def test_operation_contract_accepts_outcomes_list() -> None:
    payload = _base_contract_payload() | {"outcomes": ["digest"]}
    contract = OperationContract.model_validate(payload)
    assert contract.outcomes == ["digest"]


def test_operation_contract_defaults_outcomes_to_empty_list() -> None:
    contract = OperationContract.model_validate(_base_contract_payload())
    assert contract.outcomes == []


def test_operation_contract_outcomes_accepts_empty_explicitly() -> None:
    payload = _base_contract_payload() | {"outcomes": []}
    contract = OperationContract.model_validate(payload)
    assert contract.outcomes == []


def test_operation_contract_rejects_unknown_field() -> None:
    payload = _base_contract_payload() | {"extras": "foo"}
    with pytest.raises(PydanticValidationError):
        OperationContract.model_validate(payload)


# ---------------------------------------------------------------------------
# Step 2 — ``RESERVED_OUTCOME_VERBS`` and ``OUTCOME_VERB_STEMS`` constants
# ---------------------------------------------------------------------------


def _registered_subcommands() -> set[str]:
    """Walk ``build_parser()`` and collect every top-level subcommand."""

    parser = build_parser()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return set(choices.keys())
    raise AssertionError("build_parser() exposes no top-level subparsers")


def test_reserved_outcome_verbs_matches_subcommand_set() -> None:
    """The constant is exactly the static subcommands plus discovery aliases.

    Pins spec §Inputs §2 rule 3 ("literal enumeration of the
    current ``wiki`` subcommand set as registered in ``cli.py``
    argparse plus the standard discovery aliases"). Three
    independent assertions catch every direction the reviewer
    can break:

    1. Every discovery alias is reserved (catches a future PR
       that drops ``"outcomes"`` from the set after PR-5 makes
       it a real subcommand — the discovery aliases never go
       away).
    2. Every registered subcommand is reserved (catches a new
       subcommand added in ``cli.py`` without an update here).
    3. Nothing else is reserved (catches a stale entry that
       neither corresponds to a subcommand nor a discovery
       alias).
    """

    subcommands = _registered_subcommands()
    discovery_aliases = {"help", "version", "outcomes"}

    # 1. Discovery aliases never disappear.
    assert discovery_aliases <= RESERVED_OUTCOME_VERBS
    # 2. Every registered subcommand is reserved.
    assert subcommands <= RESERVED_OUTCOME_VERBS
    # 3. No stale entries beyond the union of subcommands and discovery aliases.
    assert RESERVED_OUTCOME_VERBS <= subcommands | discovery_aliases


def test_outcome_verb_stems_contains_bare_and_prefix_forms() -> None:
    """Pins the illustrative stem list spec §Inputs §2 rule 4 names.

    Containment-only (not set-equality), because spec rule 4
    treats the listed stems as illustrative — adding new stems
    is expected. **Removing a spec-listed stem requires either
    updating the spec's illustrative list in the same PR, or
    moving the example to a still-current spec entry** —
    silently dropping a stem the spec still cites is the
    failure mode this test catches.
    """

    # Bare-verb entries.
    assert "digest" in OUTCOME_VERB_STEMS
    assert "roll-up" in OUTCOME_VERB_STEMS
    # Prefix entries (a stem followed by a trailing hyphen).
    for prefix in (
        "plan-",
        "refresh-",
        "log-",
        "summarize-",
        "prep-",
        "review-",
        "track-",
        "synthesize-",
        "pack-",
        "remind-",
        "map-",
    ):
        assert prefix in OUTCOME_VERB_STEMS, prefix


# ---------------------------------------------------------------------------
# Step 3 — ``is_well_formed_outcome_verb``
# ---------------------------------------------------------------------------


_WELL_FORMED_VERBS: tuple[str, ...] = (
    "digest",
    "plan-meals",
    "refresh-stakeholders",
    "summarize-week",
    "track-budget",
)


@pytest.mark.parametrize("verb", _WELL_FORMED_VERBS)
def test_is_well_formed_outcome_verb_accepts(verb: str) -> None:
    # Must not raise.
    is_well_formed_outcome_verb(verb)


@pytest.mark.parametrize(
    ("verb", "expected_phrase"),
    [
        ("a--b", "consecutive hyphens"),
        ("ab-", "trailing hyphen"),
        ("1ab", "leading digit"),
        # 3+ chars so the length rule does not pre-empt the case rule.
        ("Abc", "ASCII lowercase"),
        ("ab", "3-24"),
        ("a" * 25, "3-24"),
        ("wiki-foo", "wiki-"),
        ("meals", "verb-stem"),
        ("weekly-summary", "verb-stem"),
        ("doctor", "reserved"),
        ("digést", "ASCII"),
    ],
)
def test_is_well_formed_outcome_verb_rejects(verb: str, expected_phrase: str) -> None:
    with pytest.raises(WikiError) as excinfo:
        is_well_formed_outcome_verb(verb)
    # Each rejection message names the rule that triggered it.
    assert expected_phrase in str(excinfo.value), (verb, str(excinfo.value))


# ---------------------------------------------------------------------------
# Step 4 — ``check_outcome_verb_uniqueness``
# ---------------------------------------------------------------------------


def _contract(name: str, outcomes: list[str] | None = None) -> OperationContract:
    return OperationContract.model_validate(
        {
            "name": name,
            "description": f"{name} operation.",
            "outcomes": outcomes or [],
        }
    )


def test_uniqueness_passes_with_disjoint_verbs() -> None:
    contracts = [
        _contract("weekly-digest", ["digest"]),
        _contract("meal-planning", ["plan-meals"]),
    ]
    # Must not raise.
    check_outcome_verb_uniqueness(contracts)


def test_uniqueness_passes_with_empty_outcomes() -> None:
    contracts = [
        _contract("weekly-digest"),
        _contract("meal-planning"),
        _contract("stakeholder-map-refresh"),
    ]
    check_outcome_verb_uniqueness(contracts)


def test_uniqueness_fails_on_collision() -> None:
    contracts = [
        _contract("weekly-digest", ["digest"]),
        _contract("other-digest", ["digest"]),
    ]
    with pytest.raises(WikiError) as excinfo:
        check_outcome_verb_uniqueness(contracts)
    msg = str(excinfo.value)
    assert "digest" in msg
    assert "weekly-digest" in msg
    assert "other-digest" in msg


def test_uniqueness_fails_on_verb_equals_operation_name_cross_operation() -> None:
    # Operation ``weekly-digest`` exists; a different operation claims it
    # as its own outcome verb — disallowed even though no verb-vs-verb
    # collision exists, because ``wiki <verb>`` would shadow
    # ``wiki run weekly-digest``'s alias resolution.
    contracts = [
        _contract("weekly-digest"),
        _contract("other-op", ["weekly-digest"]),
    ]
    with pytest.raises(WikiError) as excinfo:
        check_outcome_verb_uniqueness(contracts)
    msg = str(excinfo.value)
    assert "weekly-digest" in msg
    assert "other-op" in msg


def test_uniqueness_fails_on_verb_equals_own_operation_name() -> None:
    # The declaring operation cannot claim its own name as a verb either —
    # the disjoint-sets invariant covers both cases (spec Invariant 8).
    contracts = [_contract("weekly-digest", ["weekly-digest"])]
    with pytest.raises(WikiError) as excinfo:
        check_outcome_verb_uniqueness(contracts)
    msg = str(excinfo.value)
    assert "weekly-digest" in msg


# ---------------------------------------------------------------------------
# PR-2 — ``discover_primitives`` catalog-load gate
# ---------------------------------------------------------------------------


def _write_operation_primitive(
    templates_dir: Path,
    name: str,
    *,
    outcomes: list[str] | None = None,
    skill: str | None = None,
    requires: list[str] | None = None,
) -> Path:
    """Write a minimal operation primitive (manifest + contract).

    Mirrors the shape of ``templates/operations/<name>/`` in the
    shipped catalog: a ``primitive.yaml`` with ``kind: operation``,
    plus a ``contract.yaml`` declaring the operation contract.
    Returns the primitive directory path.
    """

    primitive_dir = templates_dir / "operations" / name
    primitive_dir.mkdir(parents=True, exist_ok=True)

    manifest_lines = [
        f"name: {name}",
        "kind: operation",
        "version: 0.1.0",
        f"description: Fixture operation primitive '{name}'.",
    ]
    if requires:
        manifest_lines.append("requires:")
        manifest_lines.extend(f"  - {r}" for r in requires)
    (primitive_dir / "primitive.yaml").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )

    contract: dict[str, object] = {
        "name": name,
        "description": f"{name} operation contract.",
    }
    if skill is not None:
        contract["skill"] = skill
    if outcomes is not None:
        contract["outcomes"] = outcomes
    (primitive_dir / "contract.yaml").write_text(
        yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
    )
    return primitive_dir


def test_discover_primitives_rejects_collision(tmp_path: Path) -> None:
    """Two operation primitives declaring the same verb raises ``WikiError``."""

    _write_operation_primitive(tmp_path, "weekly-digest", outcomes=["digest"])
    _write_operation_primitive(tmp_path, "other-digest", outcomes=["digest"])

    with pytest.raises(WikiError) as excinfo:
        discover_primitives(tmp_path)
    msg = str(excinfo.value)
    assert "digest" in msg
    assert "weekly-digest" in msg
    assert "other-digest" in msg


def test_discover_primitives_rejects_malformed_verb(tmp_path: Path) -> None:
    """A malformed verb (consecutive hyphens) raises at catalog-load."""

    _write_operation_primitive(tmp_path, "weekly-digest", outcomes=["bad--verb"])

    with pytest.raises(WikiError) as excinfo:
        discover_primitives(tmp_path)
    assert "bad--verb" in str(excinfo.value)
    assert "consecutive hyphens" in str(excinfo.value)


def test_discover_primitives_rejects_reserved_verb(tmp_path: Path) -> None:
    """A verb colliding with a reserved subcommand raises."""

    _write_operation_primitive(tmp_path, "weekly-digest", outcomes=["doctor"])

    with pytest.raises(WikiError) as excinfo:
        discover_primitives(tmp_path)
    assert "doctor" in str(excinfo.value)
    assert "reserved" in str(excinfo.value)


def test_discover_primitives_rejects_verb_with_wiki_prefix(tmp_path: Path) -> None:
    """The belt-and-braces ``wiki-`` prefix block fires at catalog-load."""

    _write_operation_primitive(tmp_path, "weekly-digest", outcomes=["wiki-foo"])

    with pytest.raises(WikiError) as excinfo:
        discover_primitives(tmp_path)
    assert "wiki-foo" in str(excinfo.value)
    assert "wiki-" in str(excinfo.value)


def test_discover_primitives_accepts_v2_0_0_catalog() -> None:
    """The real shipped ``templates/`` tree loads cleanly.

    No operation primitive declares ``outcomes:`` today (PR-8 is the
    rollout). Three checks pin the baseline:

    1. ``discover_primitives`` returns without raising over the real
       shipped tree.
    2. Every on-disk directory under ``templates/operations/`` that
       has a ``primitive.yaml`` is discovered AS an operation-kind
       primitive — catching a misplaced manifest (e.g. ``kind:
       content-type`` under ``operations/``) loudly rather than via
       a set-inequality message.
    3. Every shipped operation contract has ``outcomes == []`` —
       the plan-contracted pre-PR-8 baseline. A stray
       ``outcomes: [digest]`` slipping in before the rollout fails
       here.

    Pins the "vaults that predate this spec gain new surfaces on
    ``wiki upgrade`` and lose nothing" baseline (spec AC "Backwards
    compatibility").
    """

    primitives = discover_primitives(_SHIPPED_TEMPLATES)

    on_disk_ops = sorted(
        d.name
        for d in _SHIPPED_OPERATIONS.iterdir()
        if d.is_dir() and (d / "primitive.yaml").exists()
    )
    # 2. Every on-disk operation directory is discovered AS an
    # operation primitive. Per-name assertion (not set-equality)
    # so a misplaced manifest produces a clear "directory X has
    # kind Y, expected operation" failure.
    by_name = {p.name: p for p in primitives}
    for name in on_disk_ops:
        assert name in by_name, f"shipped operation '{name}' missing from discovered set"
        assert by_name[name].kind.value == "operation", (
            f"shipped operation '{name}' loaded with kind "
            f"'{by_name[name].kind.value}', expected 'operation' "
            "(misplaced primitive.yaml under templates/operations/?)"
        )

    # 3. Every shipped operation contract has empty outcomes
    # pre-PR-8. Walks the on-disk contracts directly so a future
    # `outcomes: [digest]` accidentally landed before the rollout
    # fails here, not just at the catalog-load gate.
    inspected = 0
    for name in on_disk_ops:
        contract_path = _SHIPPED_OPERATIONS / name / "contract.yaml"
        if not contract_path.is_file():
            continue
        payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        contract = OperationContract.model_validate(payload)
        assert contract.outcomes == [], (
            f"shipped operation '{name}' declares outcomes "
            f"{contract.outcomes!r}; rollout is PR-8, not this PR"
        )
        inspected += 1
    # Sanity-pin against an empty templates/ tree silently passing.
    assert inspected == len(on_disk_ops), (
        f"inspected {inspected} contracts but expected "
        f"{len(on_disk_ops)} (one per on-disk operation)"
    )


def test_shipped_catalog_outcome_verbs_well_formed() -> None:
    """Every declared verb in the shipped catalog is well-formed.

    Today's catalog declares zero outcome verbs, so the inner loop is
    empty — but this test still earns its keep:

    - Once PR-8 lands and operations declare verbs, this is the
      direct pin (separate from the in-walker check in
      ``discover_primitives``) so the catalog-time well-formedness
      contract is testable independently of the discovery code path.
    - The ``inspected_contracts`` count ensures a future refactor
      that hollows out ``_SHIPPED_OPERATIONS`` doesn't silently
      green-pass this test.

    Pins spec AC "Catalog-time uniqueness gate" against the actual
    catalog state, not just against fixtures.
    """

    expected_count = sum(
        1 for d in _SHIPPED_OPERATIONS.iterdir() if d.is_dir() and (d / "primitive.yaml").exists()
    )

    inspected_contracts = 0
    for primitive_dir in sorted(_SHIPPED_OPERATIONS.iterdir()):
        if not primitive_dir.is_dir():
            continue
        contract_path = primitive_dir / "contract.yaml"
        if not contract_path.is_file():
            continue
        payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        contract = OperationContract.model_validate(payload)
        for verb in contract.outcomes:
            # Must not raise.
            is_well_formed_outcome_verb(verb)
        inspected_contracts += 1

    # Tighten to one-per-on-disk-operation rather than ``>= 1`` so a
    # future PR that deletes 9/10 contracts cannot keep this
    # "independent pin" green via the surviving contract alone (the
    # v2.0.0-catalog test would still catch the deletion, but the
    # whole point of this test is that it stays independent).
    assert inspected_contracts == expected_count, (
        f"inspected {inspected_contracts} shipped contracts under "
        f"{_SHIPPED_OPERATIONS}; expected {expected_count} (one per "
        "on-disk operation primitive)"
    )
