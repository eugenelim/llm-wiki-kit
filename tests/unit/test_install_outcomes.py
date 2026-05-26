"""Unit tests for the install-side outcome surfaces — PR-3.

Pins (per ``docs/specs/outcome-named-entry-points/plan.md`` §PR-3):

- ``install.write_outcome_slash_stubs`` — writes one stub per
  declared verb under ``<vault>/.claude/commands/<verb>.md`` via
  ``safe_write``, with the fixed-body template from spec §Outputs §2.
- ``install.validate_outcome_skill_fragments`` — refuses to start
  the install pipeline when an operation primitive declares a verb
  that the matching ``SKILL.md`` description does not mention as a
  whole word.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.install import (
    validate_outcome_skill_fragments,
    write_outcome_slash_stubs,
)
from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    PageWriteEvent,
    Primitive,
    PrimitiveKind,
    VaultInitEvent,
)
from llm_wiki_kit.upgrade import UPGRADE_VEHICLE

# ---------------------------------------------------------------------------
# Fixture-catalog helpers
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUTCOME_CATALOG = _REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"
_FIXTURE_DIGEST = _OUTCOME_CATALOG / "operations" / "fixture-digest"
_FIXTURE_SKILL_MISSING = _OUTCOME_CATALOG / "operations" / "fixture-skill-missing"


def _operation_primitive(name: str, version: str = "0.1.0") -> Primitive:
    return Primitive.model_validate(
        {
            "name": name,
            "kind": "operation",
            "version": version,
            "description": f"{name} operation.",
        }
    )


def _seed_vault(tmp_path: Path) -> Path:
    """Create a minimal vault with a VaultInitEvent journaled."""

    vault = tmp_path / "v"
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    append_event(
        journal_path,
        VaultInitEvent.model_validate(
            {
                "type": "vault.init",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "by": "wiki-init",
                "vault_name": "v",
                "recipe": "minimal",
            }
        ),
    )
    return vault


# ---------------------------------------------------------------------------
# Step 1 — write_outcome_slash_stubs
# ---------------------------------------------------------------------------


def test_write_outcome_slash_stubs_creates_commands_dir(tmp_path: Path) -> None:
    """The helper creates ``.claude/commands/`` before writing."""

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    primitive = _operation_primitive("fixture-digest")
    sources = {primitive.name: _FIXTURE_DIGEST}

    assert not (vault / ".claude" / "commands").exists()
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources=sources,
        journal_path=journal_path,
        by="wiki-init",
    )
    stub = vault / ".claude" / "commands" / "prep-digest.md"
    assert stub.is_file(), "slash stub must land at .claude/commands/<verb>.md"


def test_write_outcome_slash_stubs_body_matches_spec_template(
    tmp_path: Path,
) -> None:
    """Stub body matches spec §Outputs §2 verbatim with substitutions."""

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    primitive = _operation_primitive("fixture-digest")
    sources = {primitive.name: _FIXTURE_DIGEST}

    write_outcome_slash_stubs(
        primitives=[primitive],
        sources=sources,
        journal_path=journal_path,
        by="wiki-init",
    )
    body = (vault / ".claude" / "commands" / "prep-digest.md").read_text(encoding="utf-8")
    expected = textwrap.dedent("""\
        ---
        description: Invoke the fixture-digest operation (alias: /prep-digest).
        ---
        Run the `fixture-digest` skill from this vault. See the SKILL's own
        `when to load` section for inputs.

        <!-- BEGIN MANAGED: outcome-provenance -->
        <!-- END MANAGED: outcome-provenance -->
    """)
    assert body == expected


def test_write_outcome_slash_stubs_byte_stable(tmp_path: Path) -> None:
    """Second call produces no new on-disk bytes, regardless of vehicle.

    Spec §Outputs §2: "The stub is byte-stable: the same verb +
    operation + skill produces identical bytes every time, so
    re-running ``wiki upgrade`` is a no-op in the absence of drift."
    The realistic recurring case is init (``wiki-init``) followed by
    upgrade (``wiki-upgrade``) — same primitive, different ``by``.
    Each call journals a ``PageWriteEvent`` (the audit trail records
    every composed body), but the on-disk file bytes must be
    identical across vehicles — ``by`` is a journal field, not a
    body field.
    """

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    primitive = _operation_primitive("fixture-digest")
    sources = {primitive.name: _FIXTURE_DIGEST}

    write_outcome_slash_stubs(
        primitives=[primitive],
        sources=sources,
        journal_path=journal_path,
        by="wiki-init",
    )
    after_init = (vault / ".claude" / "commands" / "prep-digest.md").read_bytes()

    write_outcome_slash_stubs(
        primitives=[primitive],
        sources=sources,
        journal_path=journal_path,
        by=UPGRADE_VEHICLE,
    )
    after_upgrade = (vault / ".claude" / "commands" / "prep-digest.md").read_bytes()

    assert after_init == after_upgrade, (
        "stub bytes must be vehicle-independent (``by`` is journal-only)"
    )
    # No proposal sidecar — bytes matched, so no drift.
    assert not (vault / ".claude" / "commands" / "prep-digest.md.proposed").exists()


def test_write_outcome_slash_stubs_skill_fallback_when_contract_skill_absent(
    tmp_path: Path,
) -> None:
    """``{skill}`` falls back to ``contract.name`` when ``skill:`` absent.

    Mirrors PR-4's ``installed_outcome_verbs`` fallback and the
    existing ``_cmd_run`` resolution (``run.py:508``) so the on-disk
    stub and the discovery surface stay consistent.
    """

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"

    # Synthetic primitive whose contract omits ``skill:``. We can't
    # reuse the fixture catalog (whose contracts declare ``skill:``),
    # so build a tiny on-the-fly catalog where the operation primitive
    # falls back: contract.skill == None → use contract.name as skill.
    primitive_dir = tmp_path / "src" / "no-skill-op"
    skill_dir = primitive_dir / "files" / "skills" / "no-skill-op"
    skill_dir.mkdir(parents=True)
    (primitive_dir / "primitive.yaml").write_text(
        "name: no-skill-op\nkind: operation\nversion: 0.1.0\ndescription: fallback fixture.\n",
        encoding="utf-8",
    )
    (primitive_dir / "contract.yaml").write_text(
        "name: no-skill-op\n"
        "description: Fallback fixture; skill omitted.\n"
        "outcomes: [prep-fallback]\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: prep-fallback skill description.\n---\n",
        encoding="utf-8",
    )

    primitive = _operation_primitive("no-skill-op")
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={primitive.name: primitive_dir},
        journal_path=journal_path,
        by="wiki-init",
    )
    body = (vault / ".claude" / "commands" / "prep-fallback.md").read_text(encoding="utf-8")
    # Skill substitution falls back to operation name ``no-skill-op``.
    assert "Run the `no-skill-op` skill" in body
    assert "Invoke the no-skill-op operation" in body


def test_write_outcome_slash_stubs_routes_through_safe_write(
    tmp_path: Path,
) -> None:
    """Every stub write produces a ``PageWriteEvent`` with the caller's ``by``."""

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    primitive = _operation_primitive("fixture-digest")
    sources = {primitive.name: _FIXTURE_DIGEST}

    before = len(read_events(journal_path))
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources=sources,
        journal_path=journal_path,
        by=UPGRADE_VEHICLE,
    )
    new_events = read_events(journal_path)[before:]
    page_writes = [e for e in new_events if isinstance(e, PageWriteEvent)]
    assert len(page_writes) == 1, "exactly one PageWriteEvent per declared verb"
    event = page_writes[0]
    assert event.path == ".claude/commands/prep-digest.md"
    assert event.by == UPGRADE_VEHICLE


def test_write_outcome_slash_stubs_skips_non_operation_primitives(
    tmp_path: Path,
) -> None:
    """Content-type / ontology primitives are ignored (no contract.yaml lookup)."""

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    primitive = Primitive.model_validate(
        {
            "name": "people",
            "kind": "ontology",
            "version": "0.1.0",
            "description": "ontology primitive — no contract.yaml.",
        }
    )
    assert primitive.kind is PrimitiveKind.ONTOLOGY

    # No source dir need exist — function should short-circuit on kind.
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={primitive.name: tmp_path / "nonexistent"},
        journal_path=journal_path,
        by="wiki-init",
    )
    assert not (vault / ".claude").exists(), (
        "no stubs should be written for non-operation primitives"
    )


def test_write_outcome_slash_stubs_skips_operations_without_outcomes(
    tmp_path: Path,
) -> None:
    """Operations whose contract declares no outcomes write no stubs."""

    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"

    # Build a minimal operation primitive whose contract.outcomes is [].
    primitive_dir = tmp_path / "src" / "no-outcomes-op"
    primitive_dir.mkdir(parents=True)
    (primitive_dir / "primitive.yaml").write_text(
        "name: no-outcomes-op\nkind: operation\nversion: 0.1.0\ndescription: no outcomes.\n",
        encoding="utf-8",
    )
    (primitive_dir / "contract.yaml").write_text(
        "name: no-outcomes-op\ndescription: no outcomes.\nskill: no-outcomes-op\n",
        encoding="utf-8",
    )

    primitive = _operation_primitive("no-outcomes-op")
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={primitive.name: primitive_dir},
        journal_path=journal_path,
        by="wiki-init",
    )
    assert not (vault / ".claude").exists()


# ---------------------------------------------------------------------------
# Step 2 — validate_outcome_skill_fragments
# ---------------------------------------------------------------------------


def test_validate_skill_fragment_passes_when_verb_present() -> None:
    """Fixture-digest SKILL.md description contains the verb verbatim."""

    primitive = _operation_primitive("fixture-digest")
    # Must not raise.
    validate_outcome_skill_fragments(
        primitives=[primitive],
        sources={primitive.name: _FIXTURE_DIGEST},
    )


def test_validate_skill_fragment_fails_on_missing_verb() -> None:
    """Fixture-skill-missing SKILL.md omits the verb → WikiError."""

    primitive = _operation_primitive("fixture-skill-missing")
    with pytest.raises(WikiError) as excinfo:
        validate_outcome_skill_fragments(
            primitives=[primitive],
            sources={primitive.name: _FIXTURE_SKILL_MISSING},
        )
    msg = str(excinfo.value)
    # Names both the contract path and the SKILL.md path so the
    # primitive author can act on it.
    assert "track-missing" in msg
    assert "contract.yaml" in msg
    assert "SKILL.md" in msg


def test_validate_skill_fragment_whole_word_match(tmp_path: Path) -> None:
    """``digestion`` does NOT satisfy ``\\bdigest\\b`` — substring miss."""

    primitive_dir = tmp_path / "src" / "digestion-op"
    skill_dir = primitive_dir / "files" / "skills" / "digestion-op"
    skill_dir.mkdir(parents=True)
    (primitive_dir / "primitive.yaml").write_text(
        "name: digestion-op\nkind: operation\nversion: 0.1.0\n"
        "description: whole-word-check fixture.\n",
        encoding="utf-8",
    )
    (primitive_dir / "contract.yaml").write_text(
        "name: digestion-op\n"
        "description: Whole-word-check fixture.\n"
        "skill: digestion-op\n"
        "outcomes: [prep-digest]\n",
        encoding="utf-8",
    )
    # Description contains 'digestion' as a substring; the verb is
    # 'prep-digest' which appears NOWHERE as a whole word.
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: helps with digestion of inputs.\n---\n",
        encoding="utf-8",
    )

    primitive = _operation_primitive("digestion-op")
    with pytest.raises(WikiError) as excinfo:
        validate_outcome_skill_fragments(
            primitives=[primitive],
            sources={primitive.name: primitive_dir},
        )
    assert "prep-digest" in str(excinfo.value)


def test_validate_skill_fragment_skips_non_operation_primitives() -> None:
    """Content-type / ontology primitives have no SKILL.md to check."""

    primitive = Primitive.model_validate(
        {
            "name": "people",
            "kind": "ontology",
            "version": "0.1.0",
            "description": "ontology — no outcomes.",
        }
    )
    # Must not raise; the validator short-circuits on kind.
    validate_outcome_skill_fragments(
        primitives=[primitive],
        sources={primitive.name: Path("/nonexistent")},
    )


def test_validate_skill_fragment_skips_operations_without_outcomes(
    tmp_path: Path,
) -> None:
    """An operation with empty ``outcomes`` requires no SKILL fragment."""

    primitive_dir = tmp_path / "src" / "no-outcomes-op"
    primitive_dir.mkdir(parents=True)
    (primitive_dir / "primitive.yaml").write_text(
        "name: no-outcomes-op\nkind: operation\nversion: 0.1.0\ndescription: no outcomes.\n",
        encoding="utf-8",
    )
    (primitive_dir / "contract.yaml").write_text(
        "name: no-outcomes-op\ndescription: no outcomes.\nskill: no-outcomes-op\n",
        encoding="utf-8",
    )

    primitive = _operation_primitive("no-outcomes-op")
    # No SKILL.md file under skills/, but no outcomes declared — the
    # validator must NOT trip on the missing skill directory.
    validate_outcome_skill_fragments(
        primitives=[primitive],
        sources={primitive.name: primitive_dir},
    )
