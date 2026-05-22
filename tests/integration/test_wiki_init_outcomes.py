"""End-to-end ``wiki init`` integration tests for PR-3.

Exercises the slash-stub pipeline and the SKILL-fragment pre-flight
against the fixture catalog at ``tests/fixtures/outcome-catalog/``,
using the same kit-root override pattern as
``tests/integration/test_wiki_add.py``: build a tmp kit containing
``core``, the relevant fixture operation primitives, and a minimal
recipe; then run ``cli.main(["init", str(vault), "--recipe", ...],
kit_root=kit_root)``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import PageWriteEvent

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"


def _install_kit(
    tmp_path: Path,
    *,
    fixture_operations: tuple[str, ...] = (),
    recipe_primitives: tuple[str, ...] = ("core",),
) -> Path:
    """Build a tmp kit with ``core``, optional fixture operations, and a recipe."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    (kit / "templates").mkdir()
    if fixture_operations:
        (kit / "templates" / "operations").mkdir()
        for op_name in fixture_operations:
            shutil.copytree(
                FIXTURE_CATALOG / "operations" / op_name,
                kit / "templates" / "operations" / op_name,
            )

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    primitives_yaml = "\n".join(f"  - {name}" for name in recipe_primitives)
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: PR-3 outcome-catalog test recipe.\n"
        f"primitives:\n{primitives_yaml}\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


# ---------------------------------------------------------------------------
# AC: "Slash stub written"
# ---------------------------------------------------------------------------


def test_wiki_init_writes_slash_stubs_for_declared_outcomes(
    tmp_path: Path,
) -> None:
    """A vault initialized with an outcome-declaring operation gets the stub."""

    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-digest",),
        recipe_primitives=("core", "fixture-digest"),
    )
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
    body = stub.read_text(encoding="utf-8")
    assert "Invoke the fixture-digest operation (alias: /prep-digest)." in body
    assert "Run the `fixture-digest` skill from this vault." in body


def test_wiki_init_no_stubs_when_no_outcomes_declared(tmp_path: Path) -> None:
    """A v2.0.0-baseline vault (no outcomes declared) writes no stubs."""

    kit = _install_kit(tmp_path)  # core only, no fixture operations
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )
    # `.claude/commands/` is kit territory; on a core-only init the
    # kit must not create it. (Other parts of `.claude/` may still
    # exist from core — assert only on `commands/`.)
    assert not (vault / ".claude" / "commands").exists()


# ---------------------------------------------------------------------------
# AC: "SKILL-fragment presence"
# ---------------------------------------------------------------------------


def test_wiki_init_refuses_when_skill_missing_verb(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An operation whose SKILL.md omits the verb refuses install pre-flight.

    Pre-flight runs BEFORE the journal-cache scope opens, so the
    target vault must have NO ``.wiki.journal/`` directory after
    the refused init. ``cli.main`` catches the ``WikiError`` at its
    boundary, prints to stderr, and returns a non-zero exit code.
    """

    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-skill-missing",),
        recipe_primitives=("core", "fixture-skill-missing"),
    )
    vault = tmp_path / "v"

    rc = cli.main(
        ["init", str(vault), "--no-git", "--recipe", "minimal"],
        kit_root=kit,
    )
    assert rc == 2, "WikiError boundary must produce exit code 2"
    err = capsys.readouterr().err
    assert "track-missing" in err
    assert "SKILL.md" in err
    assert "contract.yaml" in err
    # Pre-flight ran BEFORE ``target.mkdir`` so the vault directory
    # itself must NOT exist — no half-init journal, no kit-owned
    # directories. Any future regression that moves the validator
    # below ``target.mkdir`` trips this assertion.
    assert not vault.exists(), (
        f"vault directory {vault} must not exist after SKILL-fragment refusal"
    )


# ---------------------------------------------------------------------------
# AC: event ordering and attribution
# ---------------------------------------------------------------------------


def test_wiki_init_outcome_event_ordering_after_region_pass(
    tmp_path: Path,
) -> None:
    """Stub PageWriteEvents land AFTER per-primitive renders + region pass.

    Pins the ordering invariant from plan §PR-3 step 3: an
    interrupted install never leaves a stub without its owning
    operation. The PrimitiveInstallEvent for the owning operation
    must appear strictly before the stub's PageWriteEvent.
    """

    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-digest",),
        recipe_primitives=("core", "fixture-digest"),
    )
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )

    from llm_wiki_kit.models import (
        ManagedRegionWriteEvent,
        PrimitiveInstallEvent,
    )

    events = read_events(_journal_path(vault))
    # Find the stub's PageWriteEvent.
    stub_writes = [
        i
        for i, e in enumerate(events)
        if isinstance(e, PageWriteEvent) and e.path == ".claude/commands/prep-digest.md"
    ]
    assert len(stub_writes) == 1, "exactly one stub PageWriteEvent on init"
    stub_index = stub_writes[0]

    # 1. Every PrimitiveInstallEvent precedes the stub PageWriteEvent —
    # the owning operation's install lands first so an interrupted
    # install never leaves an orphan stub.
    install_indices = [i for i, e in enumerate(events) if isinstance(e, PrimitiveInstallEvent)]
    assert install_indices, "expected at least one PrimitiveInstallEvent"
    assert max(install_indices) < stub_index, (
        "every PrimitiveInstallEvent must precede the stub PageWriteEvent"
    )

    # 2. Every ManagedRegionWriteEvent precedes the stub PageWriteEvent
    # — plan §PR-3 step 3 pins the order
    # [VaultInit, PrimitiveInstalls, kit renders, region aggregator,
    # stub writers]. A regression that moves the stub writer BEFORE
    # ``aggregate_region_contributions`` would not be caught by the
    # PrimitiveInstall check alone — pin the aggregator phase too.
    region_indices = [i for i, e in enumerate(events) if isinstance(e, ManagedRegionWriteEvent)]
    if region_indices:
        assert max(region_indices) < stub_index, (
            "stub PageWriteEvent must land AFTER the region aggregator "
            "(plan §PR-3 step 3 ordering invariant)"
        )

    # 3. Every non-stub PageWriteEvent (the per-primitive kit renders
    # from ``render_tree``) precedes the stub PageWriteEvent. By code
    # structure the renders run before ``aggregate_region_contributions``
    # and the stub writer runs after, but pin the order directly so a
    # regression that moves the stub-writer call before the render
    # loop is caught here, not only transitively via the region
    # assertion above.
    render_indices = [
        i
        for i, e in enumerate(events)
        if isinstance(e, PageWriteEvent) and not e.path.startswith(".claude/commands/")
    ]
    if render_indices:
        assert max(render_indices) < stub_index, (
            "stub PageWriteEvent must land AFTER per-primitive kit renders "
            "(plan §PR-3 step 3 ordering invariant)"
        )

    # 4. The owning operation's PrimitiveInstallEvent specifically
    # is in the journal — guards against future refactor that loses
    # the install event for verb-declaring primitives.
    fixture_owner = [
        i
        for i, e in enumerate(events)
        if isinstance(e, PrimitiveInstallEvent) and e.primitive == "fixture-digest"
    ]
    assert len(fixture_owner) == 1


def test_wiki_init_outcome_attribution_by_field(tmp_path: Path) -> None:
    """Stub PageWriteEvent ``by`` is the calling vehicle (``wiki-init``)."""

    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-digest",),
        recipe_primitives=("core", "fixture-digest"),
    )
    vault = tmp_path / "v"
    assert (
        cli.main(
            ["init", str(vault), "--no-git", "--recipe", "minimal"],
            kit_root=kit,
        )
        == 0
    )
    events = read_events(_journal_path(vault))
    stub_writes = [
        e
        for e in events
        if isinstance(e, PageWriteEvent) and e.path == ".claude/commands/prep-digest.md"
    ]
    assert len(stub_writes) == 1
    assert stub_writes[0].by == "wiki-init"
