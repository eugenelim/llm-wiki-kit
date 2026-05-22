"""Unit tests for ``doctor._check_outcome_orphan_stubs`` — PR-7.

Pins the four acceptance criteria from
``docs/specs/outcome-named-entry-points/plan.md`` §PR-7:

* ``test_doctor_reports_orphan_stub_after_outcome_dropped`` — a
  kit-written stub whose verb is no longer in the installed-verb set
  is reported as ``orphan`` with the dropped verb named in the detail.
* ``test_doctor_clean_on_verb_enabled_vault_no_user_edits`` — a vault
  with declared verbs and no drift produces zero outcome-related issues.
* ``test_doctor_clean_on_v2_0_0_vault`` — a v2.0.0-baseline vault (no
  outcomes) produces zero outcome-related issues.
* ``test_doctor_ignores_user_owned_command_files`` — a user-created
  ``.claude/commands/myown.md`` (no ``PageWriteEvent``) is not flagged.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit import cli
from llm_wiki_kit.doctor import ORPHAN, run_doctor
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import VaultInitEvent

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_wiki_init_outcomes.py / test_installed_outcomes.py)
# ---------------------------------------------------------------------------


def _build_kit(
    tmp_path: Path,
    *,
    fixture_operations: tuple[str, ...] = (),
    subdir: str = "kit",
) -> Path:
    """Build a tmp kit_root with ``core`` + optional fixture operations."""

    kit = tmp_path / subdir
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    (kit / "templates" / "operations").mkdir(parents=True)
    for op_name in fixture_operations:
        shutil.copytree(
            FIXTURE_CATALOG / "operations" / op_name,
            kit / "templates" / "operations" / op_name,
        )
    # Add a minimal recipe so ``cli.main(["init", …])`` can resolve it.
    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    primitives_yaml = "  - core" + (
        "".join(f"\n  - {op}" for op in fixture_operations) if fixture_operations else ""
    )
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: PR-7 doctor-outcomes test recipe.\n"
        f"primitives:\n{primitives_yaml}\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


def _init_vault_via_cli(tmp_path: Path, kit: Path, vault_name: str = "v") -> Path:
    """Run ``wiki init`` against a fresh vault directory and return the vault path."""

    vault = tmp_path / vault_name
    rc = cli.main(["init", str(vault), "--no-git", "--recipe", "minimal"], kit_root=kit)
    assert rc == 0, "wiki init must succeed for test setup"
    return vault


def _seed_bare_vault(tmp_path: Path, vault_name: str = "v") -> Path:
    """Create a minimal vault with only a ``VaultInitEvent`` — no installed ops."""

    vault = tmp_path / vault_name
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=datetime.now(UTC),
            by="wiki-init",
            vault_name=vault_name,
            recipe="minimal",
        ),
    )
    return vault


# ---------------------------------------------------------------------------
# AC: ``wiki doctor`` flags orphan stubs after verb dropped
# ---------------------------------------------------------------------------


def test_doctor_reports_orphan_stub_after_outcome_dropped(tmp_path: Path) -> None:
    """A kit-written stub whose verb is no longer installed is flagged orphan.

    Scenario:
    1. kit_v1 ships ``fixture-digest`` (declares ``prep-digest``).
    2. ``wiki init`` seeds the vault → stub at
       ``.claude/commands/prep-digest.md`` is written via ``safe_write``
       → ``PageWriteEvent`` in the journal.
    3. kit_v2 drops the ``fixture-digest`` operation entirely.
    4. ``run_doctor(vault, kit_v2)`` should report an ``orphan`` issue
       naming ``.claude/commands/prep-digest.md`` and ``prep-digest``.
    """

    # Step 1-2: init with fixture-digest declared.
    kit_v1 = _build_kit(tmp_path, fixture_operations=("fixture-digest",), subdir="kit_v1")
    vault = _init_vault_via_cli(tmp_path, kit_v1)

    # Sanity: the stub was written.
    assert (vault / ".claude" / "commands" / "prep-digest.md").is_file()

    # Step 3: kit_v2 ships no operations (fixture-digest dropped).
    kit_v2 = _build_kit(tmp_path, fixture_operations=(), subdir="kit_v2")

    # Step 4: doctor against kit_v2.
    issues = run_doctor(vault, kit_v2)
    orphan_issues = [i for i in issues if i.kind == ORPHAN]

    # There must be exactly one orphan issue naming the stub.
    stub_orphans = [i for i in orphan_issues if ".claude/commands/prep-digest.md" in i.path]
    assert len(stub_orphans) == 1, f"expected one orphan issue for the stub; got {orphan_issues!r}"
    assert "prep-digest" in stub_orphans[0].detail, (
        f"detail must name the dropped verb; got {stub_orphans[0].detail!r}"
    )


# ---------------------------------------------------------------------------
# AC: ``wiki doctor`` clean on a verb-enabled vault with no user edits
# ---------------------------------------------------------------------------


def test_doctor_clean_on_verb_enabled_vault_no_user_edits(tmp_path: Path) -> None:
    """A verb-enabled vault with no drift produces zero outcome-related issues.

    Installs ``fixture-digest``, then runs doctor against the same kit.
    The stub exists on disk and is journaled → should not be flagged.
    """

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    vault = _init_vault_via_cli(tmp_path, kit)

    issues = run_doctor(vault, kit)
    outcome_issues = [i for i in issues if ".claude/commands/" in i.path]
    assert outcome_issues == [], (
        f"expected no outcome-related issues on a clean vault; got {outcome_issues!r}"
    )


# ---------------------------------------------------------------------------
# AC: ``wiki doctor`` clean on a v2.0.0-baseline vault (no outcomes)
# ---------------------------------------------------------------------------


def test_doctor_clean_on_v2_0_0_vault(tmp_path: Path) -> None:
    """A v2.0.0-baseline vault (no outcomes installed) yields no outcome issues.

    Pins the additive-only invariant: doctor must not fabricate issues
    on a vault that predate the ``outcomes:`` field.
    """

    kit = _build_kit(tmp_path)  # core only — no operations
    vault = _init_vault_via_cli(tmp_path, kit)

    # No ``.claude/commands/`` directory should exist, but even if doctor
    # were to inspect it, zero stubs → zero orphan issues.
    issues = run_doctor(vault, kit)
    outcome_issues = [i for i in issues if ".claude/commands/" in i.path]
    assert outcome_issues == [], (
        f"expected no outcome issues on v2.0.0-baseline vault; got {outcome_issues!r}"
    )


# ---------------------------------------------------------------------------
# AC: doctor ignores user-owned .claude/commands/ files
# ---------------------------------------------------------------------------


def test_doctor_ignores_user_owned_command_files(tmp_path: Path) -> None:
    """A user-created ``.claude/commands/myown.md`` is not flagged as orphan.

    The kit-vs-user distinction: the orphan filter is
    ``(file in .claude/commands/) AND (verb NOT in installed_verb_set)
    AND (path in state.page_writes)``.  A path that was never written by
    the kit (no ``PageWriteEvent`` for it) must be silently skipped —
    spec §Non-goal 9 contracts this.
    """

    kit = _build_kit(tmp_path, fixture_operations=("fixture-digest",))
    vault = _init_vault_via_cli(tmp_path, kit)

    # Simulate user hand-creating their own command file.
    user_cmd = vault / ".claude" / "commands" / "myown.md"
    user_cmd.parent.mkdir(parents=True, exist_ok=True)
    user_cmd.write_text(
        "---\ndescription: My personal slash command.\n---\nDo something.\n",
        encoding="utf-8",
    )

    # Doctor against the same kit (fixture-digest still installed).
    issues = run_doctor(vault, kit)
    flagged_paths = [i.path for i in issues]

    assert ".claude/commands/myown.md" not in flagged_paths, (
        f"user-owned command file must NOT be flagged as orphan; got issues: {issues!r}"
    )
