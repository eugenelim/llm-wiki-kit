"""Unit tests for ``recipes.installed_outcome_verbs`` — PR-4.

Pins (per ``docs/specs/outcome-named-entry-points/plan.md`` §PR-4):

- The helper returns the verb → (operation, skill) mapping derived
  from the journal-replayed installed-primitive set.
- ``contract.skill or contract.name`` fallback when ``skill:`` is
  omitted (mirrors ``_cmd_run``'s ``run.py:508`` resolution).
- ``PrimitiveRemoveEvent`` removes the verb from the result set —
  matches ``VaultState.installed_primitives`` semantics.
- ``PrimitiveUpgradeEvent`` advances visibility to the new
  catalog version's declared verbs.
- A v2.0.0-baseline vault (no outcome-declaring operations) yields
  the empty dict.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    PrimitiveInstallEvent,
    PrimitiveRemoveEvent,
    PrimitiveUpgradeEvent,
    VaultInitEvent,
)
from llm_wiki_kit.recipes import installed_outcome_verbs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_kit(
    tmp_path: Path,
    *,
    fixture_operations: tuple[str, ...] = (),
    extra_operations: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Build a tmp kit_root with ``core`` + optional fixture operations.

    ``extra_operations`` is a mapping of operation-name → on-disk
    payload (``{"primitive.yaml": str, "contract.yaml": str,
    "skill_description": str}``) used by tests that need a custom
    contract (e.g. the skill-fallback test).
    """

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    (kit / "templates" / "operations").mkdir(parents=True)
    for op_name in fixture_operations:
        shutil.copytree(
            FIXTURE_CATALOG / "operations" / op_name,
            kit / "templates" / "operations" / op_name,
        )
    if extra_operations:
        for name, payload in extra_operations.items():
            op_dir = kit / "templates" / "operations" / name
            skill_dir = op_dir / "files" / "skills" / name
            skill_dir.mkdir(parents=True)
            (op_dir / "primitive.yaml").write_text(payload["primitive.yaml"], encoding="utf-8")
            (op_dir / "contract.yaml").write_text(payload["contract.yaml"], encoding="utf-8")
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                f"description: {payload.get('skill_description', f'{name} description.')}\n"
                "---\n",
                encoding="utf-8",
            )
    return kit


def _seed_vault(tmp_path: Path) -> Path:
    """Create a minimal vault with a VaultInitEvent journaled."""

    vault = tmp_path / "v"
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=datetime.now(UTC),
            by="wiki-init",
            vault_name="v",
            recipe="minimal",
        ),
    )
    return vault


def _record_install(vault: Path, primitive: str, version: str = "0.1.0") -> None:
    append_event(
        vault / ".wiki.journal" / "journal.jsonl",
        PrimitiveInstallEvent(
            timestamp=datetime.now(UTC),
            by="wiki-init",
            primitive=primitive,
            version=version,
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_installed_outcome_verbs_empty_for_v2_0_0_vault(tmp_path: Path) -> None:
    """A vault that installed no outcome-declaring operations yields ``{}``."""

    kit = _build_kit(tmp_path)
    vault = _seed_vault(tmp_path)
    # No PrimitiveInstallEvent: vault has only the VaultInitEvent.
    assert installed_outcome_verbs(vault, kit) == {}


def test_installed_outcome_verbs_returns_no_journal_when_journal_missing(
    tmp_path: Path,
) -> None:
    """A path without a journal returns ``{}`` rather than raising.

    Matches PR-6's dispatcher contract: callers that need a
    "vault-or-not" gate handle it themselves; the helper is pure.
    """

    kit = _build_kit(tmp_path)
    not_a_vault = tmp_path / "elsewhere"
    not_a_vault.mkdir()
    assert installed_outcome_verbs(not_a_vault, kit) == {}


def test_installed_outcome_verbs_returns_verb_to_operation_map(
    tmp_path: Path,
) -> None:
    """An installed outcome-declaring operation surfaces its verb mapping."""

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    vault = _seed_vault(tmp_path)
    _record_install(vault, "fixture-digest")

    result = installed_outcome_verbs(vault, kit)
    assert result == {"prep-digest": ("fixture-digest", "fixture-digest")}


def test_installed_outcome_verbs_skips_removed_primitives(tmp_path: Path) -> None:
    """A ``PrimitiveRemoveEvent`` removes the operation's verb from the result.

    Mirrors ``VaultState.installed_primitives`` semantics — the
    helper consumes that map and so inherits the remove-clears-key
    behaviour.
    """

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    vault = _seed_vault(tmp_path)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    _record_install(vault, "fixture-digest")
    append_event(
        journal_path,
        PrimitiveRemoveEvent(
            timestamp=datetime.now(UTC),
            by="wiki-remove",
            primitive="fixture-digest",
        ),
    )
    assert installed_outcome_verbs(vault, kit) == {}


def test_installed_outcome_verbs_picks_up_upgrade_version(tmp_path: Path) -> None:
    """An upgrade into a catalog that newly declares ``outcomes:`` surfaces them.

    Pins the load-bearing property the helper's docstring claims:
    *the helper reads the current catalog's contract, not the
    journaled install version*. The test seeds two on-disk
    catalogs at different paths and swaps which one
    ``installed_outcome_verbs`` reads — the same vault journal
    yields different verb maps depending on the kit it's
    interpreted against. Spec AC "Backwards compatibility" depends
    on this — a vault built before ``outcomes:`` declarations
    must see them post-upgrade.
    """

    # Phase 1: kit_v1 ships fixture-digest WITHOUT any outcomes.
    kit_v1 = tmp_path / "kit_v1"
    kit_v1.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit_v1 / "core")
    op_v1 = kit_v1 / "templates" / "operations" / "fixture-digest"
    op_v1.mkdir(parents=True)
    (op_v1 / "primitive.yaml").write_text(
        "name: fixture-digest\nkind: operation\nversion: 0.1.0\n"
        "description: pre-outcomes fixture.\n",
        encoding="utf-8",
    )
    (op_v1 / "contract.yaml").write_text(
        "name: fixture-digest\ndescription: v0.1.0 has no outcomes.\nskill: fixture-digest\n",
        encoding="utf-8",
    )

    vault = _seed_vault(tmp_path)
    _record_install(vault, "fixture-digest", version="0.1.0")

    # Against kit_v1: no verbs declared, empty result.
    assert installed_outcome_verbs(vault, kit_v1) == {}

    # Phase 2: kit_v2 ships fixture-digest with outcomes declared.
    # Reuse PR-3's fixture catalog (which declares prep-digest).
    kit_v2 = _build_kit(tmp_path, fixture_operations=("fixture-digest",))

    # Append an upgrade event to mirror the realistic flow.
    append_event(
        vault / ".wiki.journal" / "journal.jsonl",
        PrimitiveUpgradeEvent(
            timestamp=datetime.now(UTC),
            by="wiki-upgrade",
            primitive="fixture-digest",
            from_version="0.1.0",
            to_version="0.2.0",
        ),
    )

    # Against kit_v2: the new contract's verbs surface.
    # NB: this works even without the upgrade event (the helper
    # doesn't read versions, only the current catalog), but the
    # event is part of the realistic flow.
    assert installed_outcome_verbs(vault, kit_v2) == {
        "prep-digest": ("fixture-digest", "fixture-digest")
    }


def test_installed_outcome_verbs_raises_on_corrupt_journal(tmp_path: Path) -> None:
    """A corrupt journal raises ``JournalCorruptError`` (strict-read contract).

    The helper uses strict ``read_events`` — not the doctor-only
    ``read_events_lenient`` — because a partial verb set is more
    dangerous than a hard failure (PR-6's dispatcher catches at
    its boundary and falls through to argparse rather than
    silently rewriting to a stale-verb operation). See
    ``docs/specs/journal-locking/plan.md`` §"lenient consumers"
    for the kit-wide rule that lenient is doctor-only.
    """

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    vault = _seed_vault(tmp_path)
    _record_install(vault, "fixture-digest")
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    with journal_path.open("a", encoding="utf-8") as fp:
        fp.write('{"type": "primitive.install", "primitive": "broken')

    import pytest

    from llm_wiki_kit.errors import JournalCorruptError

    with pytest.raises(JournalCorruptError):
        installed_outcome_verbs(vault, kit)


def test_installed_outcome_verbs_falls_back_to_operation_name_when_skill_absent(
    tmp_path: Path,
) -> None:
    """``skill:`` omitted on contract → ``skill_name == contract.name``.

    Mirrors ``_cmd_run``'s resolution (``run.py:508``) and the
    stub writer's fallback (PR-3) so the discovery surface and the
    on-disk stub agree about ``{skill}`` for an operation that
    legally omits ``skill:`` from its contract.
    """

    payload = {
        "primitive.yaml": (
            "name: no-skill-op\nkind: operation\nversion: 0.1.0\ndescription: fallback fixture.\n"
        ),
        "contract.yaml": (
            "name: no-skill-op\n"
            "description: Fallback fixture; skill omitted.\n"
            "outcomes: [prep-noskill]\n"
        ),
        "skill_description": "prep-noskill skill description.",
    }
    kit = _build_kit(tmp_path, extra_operations={"no-skill-op": payload})
    vault = _seed_vault(tmp_path)
    _record_install(vault, "no-skill-op")

    result = installed_outcome_verbs(vault, kit)
    # ``skill_name`` falls back to ``contract.name``.
    assert result == {"prep-noskill": ("no-skill-op", "no-skill-op")}


def test_installed_outcome_verbs_skips_non_operation_primitives(
    tmp_path: Path,
) -> None:
    """An installed content-type / ontology primitive contributes no verbs.

    Non-operation primitives have no ``contract.yaml`` in the kit's
    ``templates/operations/`` tree — the loader returns ``None``
    and the helper silently skips them.
    """

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    # Add a non-operation primitive on disk under a different kind
    # subdirectory so the operations-tree lookup misses it.
    (kit / "templates" / "ontologies" / "people").mkdir(parents=True)
    (kit / "templates" / "ontologies" / "people" / "primitive.yaml").write_text(
        "name: people\nkind: ontology\nversion: 0.1.0\ndescription: people.\n",
        encoding="utf-8",
    )

    vault = _seed_vault(tmp_path)
    _record_install(vault, "fixture-digest")
    _record_install(vault, "people")

    result = installed_outcome_verbs(vault, kit)
    # ``people`` contributes nothing; ``fixture-digest`` contributes
    # its verb.
    assert result == {"prep-digest": ("fixture-digest", "fixture-digest")}


def test_installed_outcome_verbs_skips_primitives_no_longer_in_catalog(
    tmp_path: Path,
) -> None:
    """An installed primitive missing from the kit catalog contributes nothing.

    Matches ``wiki upgrade``'s ``plan.not_in_catalog`` handling —
    the kit's authoritative state is the catalog, not the journal.
    """

    kit = _build_kit(tmp_path)  # no operations in the kit
    vault = _seed_vault(tmp_path)
    _record_install(vault, "fixture-digest")
    assert installed_outcome_verbs(vault, kit) == {}
