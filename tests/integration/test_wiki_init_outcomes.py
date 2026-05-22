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
# AC: "Catalog uniqueness" — wiki init surfaces the collision error
# ---------------------------------------------------------------------------


def _write_synthetic_operation(
    kit: Path,
    *,
    name: str,
    verb: str,
) -> None:
    """Write a synthetic operation primitive under ``kit/templates/operations/<name>/``.

    Both ``contract.yaml`` and the matching SKILL.md frontmatter are
    well-formed; the SKILL.md description names the verb so the
    SKILL-fragment pre-flight passes — the test isolates the
    catalog-uniqueness gate as the *only* failure mode.
    """

    op_dir = kit / "templates" / "operations" / name
    op_dir.mkdir(parents=True)
    (op_dir / "primitive.yaml").write_text(
        f"name: {name}\n"
        "kind: operation\n"
        "version: 0.1.0\n"
        f"description: Synthetic operation for catalog-collision integration test.\n",
        encoding="utf-8",
    )
    (op_dir / "contract.yaml").write_text(
        f"name: {name}\n"
        f"description: Synthetic op that declares the {verb} outcome verb.\n"
        f"skill: {name}\n"
        f"outcomes:\n"
        f"  - {verb}\n"
        "inputs: {}\n"
        "outputs: {}\n",
        encoding="utf-8",
    )
    skill_dir = op_dir / "files" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: Synthetic SKILL declaring the {verb} verb.\n"
        "---\n"
        f"# {name}\n",
        encoding="utf-8",
    )


def test_wiki_init_refuses_when_two_operations_declare_same_verb(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``wiki init`` against a catalog with verb-colliding operations fails loudly.

    Spec Invariant 3 ("the verb namespace is the catalog") and
    Invariant 5 ("catalog-time failures, not user-time failures")
    contract that ``check_outcome_verb_uniqueness`` fires when the
    catalog is loaded — long before any vault sees the conflict.
    The integration shape: ``wiki init`` calls ``discover_primitives``
    on the synthetic kit; the gate raises ``WikiError``; the CLI
    boundary renders it on stderr.

    A unit test already exists at
    ``tests/unit/test_outcome_verbs.py::test_discover_primitives_rejects_collision``;
    this integration test pins the ``wiki init`` user-facing path
    specifically (``add`` and ``upgrade`` route through the same
    ``discover_primitives`` call but aren't parameterized here —
    catching one entry-point regression is enough to surface a
    decoupling without paying the matrix cost).
    """

    kit = _install_kit(tmp_path)  # core, no fixture operations
    # Two synthetic operations declaring the same verb. Both are
    # well-formed individually; only the catalog-uniqueness gate
    # rejects them as a pair.
    _write_synthetic_operation(kit, name="alpha-op", verb="track-collision")
    _write_synthetic_operation(kit, name="beta-op", verb="track-collision")
    vault = tmp_path / "v"

    rc = cli.main(
        ["init", str(vault), "--no-git", "--recipe", "minimal"],
        kit_root=kit,
    )
    assert rc == 2, "catalog-uniqueness collision must produce WikiError exit code"
    err = capsys.readouterr().err
    # The error names both offending operations + the offending verb.
    assert "track-collision" in err
    assert "alpha-op" in err
    assert "beta-op" in err
    # Catalog-time failure: the vault directory must not have been
    # created at all. Pin this strictly (not the weaker "no journal")
    # so a future regression that moved ``target.mkdir()`` ahead of
    # the catalog gate trips the test rather than passing through the
    # shorter disjunction.
    assert not vault.exists(), (
        "catalog-time failure must leave the filesystem untouched; "
        f"found vault directory at {vault}"
    )


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
