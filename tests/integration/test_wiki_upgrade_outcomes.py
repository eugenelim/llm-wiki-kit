"""End-to-end ``wiki upgrade`` integration tests for PR-3.

Exercises the spec AC "Backwards compatibility": a vault built
before its operation primitive declared ``outcomes:`` gains the
slash stub via ``wiki upgrade`` without re-init, attributed to
``UPGRADE_VEHICLE``. Mirrors the kit-root override pattern of
``tests/integration/test_wiki_upgrade.py``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import PageWriteEvent
from llm_wiki_kit.upgrade import UPGRADE_VEHICLE

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"


def _install_kit_without_outcomes(tmp_path: Path) -> Path:
    """Build a kit with ``fixture-digest`` primitive but no ``outcomes:`` declared.

    Copies the fixture catalog's ``fixture-digest/`` into a tmp kit,
    then rewrites its ``contract.yaml`` to omit ``outcomes:``. The
    primitive's ``primitive.yaml`` stays at v0.1.0 — the kit
    version-bump happens in :func:`_promote_kit_to_outcomes`.
    """

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    operations = kit / "templates" / "operations"
    operations.mkdir(parents=True)
    shutil.copytree(
        FIXTURE_CATALOG / "operations" / "fixture-digest",
        operations / "fixture-digest",
    )
    # Strip outcomes from contract.yaml for the v0.1.0 init.
    (operations / "fixture-digest" / "contract.yaml").write_text(
        "name: fixture-digest\n"
        "description: PR-3 upgrade fixture; v0.1.0 declares no outcomes.\n"
        "skill: fixture-digest\n"
        "inputs: {}\n"
        "outputs: {}\n",
        encoding="utf-8",
    )

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: PR-3 upgrade-path test recipe.\n"
        "primitives:\n  - core\n  - fixture-digest\n"
        "variables:\n  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


def _promote_kit_to_outcomes(kit: Path) -> None:
    """Bump ``fixture-digest`` to v0.2.0 with ``outcomes: [prep-digest]``."""

    primitive_dir = kit / "templates" / "operations" / "fixture-digest"
    (primitive_dir / "primitive.yaml").write_text(
        "name: fixture-digest\n"
        "kind: operation\n"
        "version: 0.2.0\n"
        "description: PR-3 upgrade fixture; v0.2.0 introduces outcomes.\n",
        encoding="utf-8",
    )
    (primitive_dir / "contract.yaml").write_text(
        "name: fixture-digest\n"
        "description: v0.2.0 declares prep-digest verb.\n"
        "skill: fixture-digest\n"
        "outcomes:\n  - prep-digest\n"
        "inputs: {}\n"
        "outputs: {}\n",
        encoding="utf-8",
    )


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _add_outcomes_keep_version(kit: Path) -> None:
    """Mutate ``contract.yaml`` to add ``outcomes:`` WITHOUT bumping the version.

    Exercises the spec AC "Backwards compatibility" case the plan
    explicitly contracts at PR-3 step 3: a catalog migration where
    an installed operation gains ``outcomes:`` but its
    ``primitive.yaml`` version is unchanged. ``wiki upgrade`` must
    still materialize the stub (the no-op short-circuit must not
    swallow this case).
    """

    primitive_dir = kit / "templates" / "operations" / "fixture-digest"
    (primitive_dir / "contract.yaml").write_text(
        "name: fixture-digest\n"
        "description: outcomes added, version unchanged.\n"
        "skill: fixture-digest\n"
        "outcomes:\n  - prep-digest\n"
        "inputs: {}\n"
        "outputs: {}\n",
        encoding="utf-8",
    )


def test_wiki_upgrade_no_version_bump_still_writes_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catalog migration adds ``outcomes:`` without a version bump → stub lands.

    Spec AC "Backwards compatibility". Without the fix, ``_cmd_upgrade``
    short-circuits at ``not plan.to_upgrade`` and the stub writer
    never runs.
    """

    kit = _install_kit_without_outcomes(tmp_path)
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )
    # Mutate the contract ONLY — primitive.yaml stays at v0.1.0.
    _add_outcomes_keep_version(kit)

    monkeypatch.chdir(vault)
    assert cli.main(["upgrade"], kit_root=kit) == 0

    stub = vault / ".claude" / "commands" / "prep-digest.md"
    assert stub.is_file(), "no-version-bump catalog migration must still materialise the stub"
    new_events = read_events(_journal_path(vault))
    stub_writes = [
        e
        for e in new_events
        if isinstance(e, PageWriteEvent) and e.path == ".claude/commands/prep-digest.md"
    ]
    assert len(stub_writes) == 1
    assert stub_writes[0].by == UPGRADE_VEHICLE


def test_wiki_upgrade_writes_stubs_for_newly_declared_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vault built before ``outcomes:`` declaration gains the stub on upgrade.

    Spec AC "Backwards compatibility": vaults that predate this
    spec gain new surfaces on ``wiki upgrade`` and lose nothing.
    """

    kit = _install_kit_without_outcomes(tmp_path)
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )
    # v0.1.0 vault: no stub on disk.
    assert not (vault / ".claude" / "commands" / "prep-digest.md").exists()

    # Catalog migration: fixture-digest v0.2.0 introduces outcomes.
    _promote_kit_to_outcomes(kit)

    monkeypatch.chdir(vault)
    assert cli.main(["upgrade"], kit_root=kit) == 0

    stub = vault / ".claude" / "commands" / "prep-digest.md"
    assert stub.is_file(), "wiki upgrade must materialize stubs for newly declared verbs"
    body = stub.read_text(encoding="utf-8")
    assert "Invoke the fixture-digest operation (alias: /prep-digest)." in body


def test_wiki_upgrade_outcome_attribution_by_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every upgrade-written stub PageWriteEvent has ``by == UPGRADE_VEHICLE``."""

    kit = _install_kit_without_outcomes(tmp_path)
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )

    events_before = read_events(_journal_path(vault))
    _promote_kit_to_outcomes(kit)
    monkeypatch.chdir(vault)
    assert cli.main(["upgrade"], kit_root=kit) == 0

    new_events = read_events(_journal_path(vault))[len(events_before) :]
    stub_writes = [
        e
        for e in new_events
        if isinstance(e, PageWriteEvent) and e.path == ".claude/commands/prep-digest.md"
    ]
    assert len(stub_writes) == 1
    assert stub_writes[0].by == UPGRADE_VEHICLE


def test_wiki_init_stub_drift_preserved_as_proposed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User-edited stub survives upgrade; kit version lands as ``.proposed``.

    Spec AC "Slash stub drift": the standard ``safe_write`` proposal
    flow (ADR-0004) applies — kit doesn't silently overwrite a user
    edit to the stub.
    """

    # Init kit already has outcomes declared, so the stub lands at init.
    kit = _install_kit_without_outcomes(tmp_path)
    _promote_kit_to_outcomes(kit)  # outcomes from the start
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )
    stub = vault / ".claude" / "commands" / "prep-digest.md"
    assert stub.is_file()

    # User edits the stub.
    user_body = "---\ndescription: user-edited.\n---\nCustom invocation.\n"
    stub.write_text(user_body, encoding="utf-8")

    # Bump kit version to force a new upgrade (kit content unchanged
    # apart from primitive.yaml's version line).
    (kit / "templates" / "operations" / "fixture-digest" / "primitive.yaml").write_text(
        "name: fixture-digest\n"
        "kind: operation\n"
        "version: 0.3.0\n"
        "description: PR-3 drift-test fixture v0.3.0.\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(vault)
    assert cli.main(["upgrade"], kit_root=kit) == 0

    # Original (user-edited) bytes survive on disk.
    assert stub.read_text(encoding="utf-8") == user_body
    # Kit's would-write lands as `.proposed` sidecar.
    proposed = vault / ".claude" / "commands" / "prep-digest.md.proposed"
    assert proposed.is_file()
    assert "Invoke the fixture-digest operation" in proposed.read_text(encoding="utf-8")
