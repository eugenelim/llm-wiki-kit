"""End-to-end integration tests for ``wiki init --adopt`` (PR-C).

Each test pins one acceptance criterion (or refusal predicate) from
``docs/specs/wiki-init-adopt/spec.md`` so a regression points back at
the named contract. The test fixture mirrors ``test_wiki_init.py``'s
``core_only_kit`` pattern: a temporary kit root symlinks back to the
real ``core/`` and ``templates/`` so we exercise the shipped install
pipeline without paying the full ``family``-recipe cost on every
case. A ``--no-git`` flag keeps the journal shape narrow.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from llm_wiki_kit import adopt as adopt_module
from llm_wiki_kit import doctor
from llm_wiki_kit.cli import WIKI_ERROR_EXIT, main
from llm_wiki_kit.journal import (
    append_event,
    dump_event_json,
    parse_event_line,
    read_events,
)
from llm_wiki_kit.models import (
    ManagedRegionAdoptedEvent,
    ManagedRegionWriteEvent,
    PageAdoptedEvent,
    PageProposalEvent,
    PageWriteEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
)


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _hash(content: str | bytes) -> str:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def people_kit(tmp_path: Path) -> Path:
    """Kit root with a recipe shipping core + people (one kit-owned file per ontology).

    The ``people`` ontology ships ``wiki/people/README.md`` so we have
    a kit-owned path under a kit-owned directory to exercise adopt
    behavior without the full family-recipe closure.
    """

    from llm_wiki_kit import cli

    kit_root = tmp_path / "kit-root"
    (kit_root / "recipes").mkdir(parents=True)
    (kit_root / "recipes" / "people-only.yaml").write_text(
        "name: people-only\n"
        "version: 0.1.0\n"
        "description: >-\n"
        "  Test-only recipe for adopt integration tests.\n"
        "primitives:\n"
        "  - people\n"
        "variables:\n"
        "  recipe_name: people-only\n",
        encoding="utf-8",
    )
    repo_root = cli._kit_root()
    (kit_root / "core").symlink_to(repo_root / "core")
    (kit_root / "templates").symlink_to(repo_root / "templates")
    return kit_root


def _seeded_kit_files(vault: Path, people_kit: Path) -> dict[str, bytes]:
    """Run a plain (no-adopt) init in a scratch dir with the SAME directory
    name as ``vault`` to capture the kit's would-render bytes verbatim,
    then tear the scratch down.

    Interpolated files (``AGENTS.md``, ``CORE.md``, ``.gitignore``,
    ``frontmatter.schema.yaml``) embed ``{vault_name}`` — the
    ``Path.name`` of the target. Seeding with a differently-named
    scratch directory would produce different bytes and break the
    "byte-identical" assertion in the AC2 test.

    Returns ``{relative_path: bytes}`` for every kit-rendered file.
    """

    import shutil

    scratch_root = vault.parent / "seed-scratch"
    scratch = scratch_root / vault.name
    scratch.parent.mkdir()
    main(
        ["init", str(scratch), "--recipe", "people-only", "--no-git"],
        kit_root=people_kit,
    )
    seeds: dict[str, bytes] = {}
    for path in scratch.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(scratch).as_posix()
        if relative.startswith(".wiki.journal/"):
            continue
        seeds[relative] = path.read_bytes()
    shutil.rmtree(scratch_root)
    return seeds


# ---------------------------------------------------------------------------
# AC1 — empty target collapses to a normal init
# ---------------------------------------------------------------------------


def test_init_adopt_empty_target_matches_plain_init(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC1 — ``--adopt`` over an empty target behaves identically to plain init.

    Same set of journaled event types in the same order; no
    ``wiki init: adopted ...`` summary line.
    """

    plain_vault = tmp_path / "plain"
    adopt_vault = tmp_path / "adopt"

    assert (
        main(
            ["init", str(plain_vault), "--recipe", "people-only", "--no-git"],
            kit_root=people_kit,
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            ["init", str(adopt_vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()

    plain_events = read_events(_journal_path(plain_vault))
    adopt_events = read_events(_journal_path(adopt_vault))

    # Same (event type, ``by``) sequence: AC7 + Invariant 6 forbid a
    # regression that mis-attributes a non-adopt event to
    # ``wiki-init-adopt`` (or vice versa) on the empty-target collapse.
    # Comparing tuples catches an attribution drift that a type-only
    # check would silently allow.
    assert [(type(e), e.by) for e in plain_events] == [(type(e), e.by) for e in adopt_events]
    # And no event on the empty-target run carries the adopt vehicle
    # string — the entire run should be indistinguishable from a plain
    # ``wiki init``.
    assert all(event.by != "wiki-init-adopt" for event in adopt_events)
    # And no adopt-summary line on stdout — empty target is silent on adopt.
    assert "wiki init: adopted" not in captured.out
    # And no pre-existing-sidecar warning on stderr.
    assert "pre-existing kit-owned" not in captured.err


# ---------------------------------------------------------------------------
# AC2 — byte-identical pre-existing kit-owned files
# ---------------------------------------------------------------------------


def test_init_adopt_byte_identical_files_emit_adopt_and_no_proposals(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2 — byte-identical kit-owned files adopt cleanly; no sidecars."""

    vault = tmp_path / "vault"
    seeds = _seeded_kit_files(vault, people_kit)
    assert seeds, "expected at least one kit-owned file"

    vault.mkdir()
    for relative, body in seeds.items():
        target = vault / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    pre_inodes = {rel: (vault / rel).stat().st_ino for rel in seeds}

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()

    events = read_events(_journal_path(vault))

    adopt_events = [e for e in events if isinstance(e, PageAdoptedEvent)]
    adopted_paths = {e.path for e in adopt_events}
    assert seeds.keys() <= adopted_paths, (
        f"expected every kit-owned path adopted; missing: {seeds.keys() - adopted_paths}"
    )
    for event in adopt_events:
        assert event.by == "wiki-init-adopt"
        if event.path in seeds:
            assert event.hash == _hash(seeds[event.path])

    # Zero proposals.
    assert [e for e in events if isinstance(e, PageProposalEvent)] == []
    # No sidecars on disk under kit-owned paths.
    for relative in seeds:
        assert not (vault / (relative + ".proposed")).exists()
    # Inodes preserved for every adopted file (adopt-match no-rewrite branch).
    for relative in seeds:
        assert (vault / relative).stat().st_ino == pre_inodes[relative], (
            f"adopt-match should preserve inode for {relative}"
        )

    # Summary line on stdout, plural form.
    assert f"wiki init: adopted {len(seeds)} files." in captured.out


# ---------------------------------------------------------------------------
# AC3 — byte-differing pre-existing kit-owned files
# ---------------------------------------------------------------------------


def test_init_adopt_byte_differing_file_produces_sidecar(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3 — byte-differing kit-owned file emits both adopt + proposal events.

    Adopt baseline records the user's bytes; render-phase produces a
    ``.proposed`` with the kit's content; original file is preserved.
    """

    vault = tmp_path / "vault"
    vault.mkdir()

    user_body = "user wrote this people README\n"
    target = vault / "wiki" / "people" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_text(user_body, encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()

    events = read_events(_journal_path(vault))

    adopt_events = [
        e for e in events if isinstance(e, PageAdoptedEvent) and e.path == "wiki/people/README.md"
    ]
    assert len(adopt_events) == 1
    assert adopt_events[0].hash == _hash(user_body)

    proposal_events = [
        e for e in events if isinstance(e, PageProposalEvent) and e.path == "wiki/people/README.md"
    ]
    assert len(proposal_events) == 1
    proposed_path = vault / proposal_events[0].proposed_path
    assert proposed_path.is_file()
    # Original file's bytes are unchanged.
    assert target.read_text(encoding="utf-8") == user_body
    # Drift line on stdout.
    assert (
        "Wrote wiki/people/README.md.proposed (drift detected on wiki/people/README.md)"
        in captured.out
    )
    # Summary line, singular.
    assert "wiki init: adopted 1 file." in captured.out


# ---------------------------------------------------------------------------
# AC4 — already-a-vault refusal
# ---------------------------------------------------------------------------


def test_init_adopt_refuses_when_primitive_install_event_present(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC4 — a vault carrying a PrimitiveInstallEvent refuses re-init."""

    vault = tmp_path / "vault"
    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git"],
            kit_root=people_kit,
        )
        == 0
    )
    capsys.readouterr()
    journal_bytes_before = _journal_path(vault).read_bytes()

    exit_code = main(
        ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
        kit_root=people_kit,
    )

    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "target is already a wiki vault" in err
    assert "wiki upgrade" in err
    # Journal untouched.
    assert _journal_path(vault).read_bytes() == journal_bytes_before


# ---------------------------------------------------------------------------
# AC4b — init-in-progress journal proceeds + re-emits adopt events
# ---------------------------------------------------------------------------


def test_init_adopt_resumes_with_partial_region_prefix_re_emits_complete_interleave(
    tmp_path: Path,
) -> None:
    """AC4b + AC6 (across runs) — a crash that landed page + ONE of TWO region
    events leaves a partial-prefix journal; the re-run re-emits a COMPLETE
    page→regions interleave for the host (not a top-up that skips the
    already-journaled region).

    Per spec §Invariant 1 every adopt sequence is page + ALL its regions
    atomically per-host. Idempotent replay (latest-wins) absorbs the
    duplicate region row; what matters is the re-run produces a fresh
    complete sequence even when the partial prefix already has a region.
    """

    from datetime import UTC, datetime

    vault = tmp_path / "vault"
    vault.mkdir()
    host_body = (
        "types:\n"
        "  # BEGIN MANAGED: types\n"
        "  - user-type\n"
        "  # END MANAGED: types\n"
        "fields:\n"
        "  # BEGIN MANAGED: fields\n"
        "  user_field:\n"
        "    type: string\n"
        "  # END MANAGED: fields\n"
    )
    (vault / "frontmatter.schema.yaml").write_text(host_body, encoding="utf-8")

    # Hand-seed an init-in-progress journal with the page + ONE region
    # (simulating a crash between two ManagedRegionAdoptedEvent appends).
    journal_path = _journal_path(vault)
    journal_path.parent.mkdir()
    now = datetime.now(UTC)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=now, by="wiki-init", vault_name=vault.name, recipe="family"),
    )
    append_event(
        journal_path,
        PageAdoptedEvent(
            timestamp=now,
            by="wiki-init-adopt",
            path="frontmatter.schema.yaml",
            hash=_hash(host_body),
        ),
    )
    append_event(
        journal_path,
        ManagedRegionAdoptedEvent(
            timestamp=now,
            by="wiki-init-adopt",
            file="frontmatter.schema.yaml",
            region="types",
            content_hash="stale-from-prior-run",
        ),
    )
    seed_length = len(read_events(journal_path))

    exit_code = main(
        ["init", str(vault), "--recipe", "family", "--no-git", "--adopt"],
    )
    assert exit_code == 0

    events = read_events(journal_path)
    new_slice = events[seed_length:]

    # Identify the host's re-emitted page-adopt in the new slice and
    # assert the page is followed by BOTH region events before any
    # PrimitiveInstallEvent fires (complete page→regions interleave).
    host_idx = next(
        i
        for i, e in enumerate(new_slice)
        if isinstance(e, PageAdoptedEvent) and e.path == "frontmatter.schema.yaml"
    )
    first_install = next(i for i, e in enumerate(new_slice) if isinstance(e, PrimitiveInstallEvent))
    assert host_idx < first_install

    fresh_region_events = [
        e
        for e in new_slice[host_idx + 1 : first_install]
        if isinstance(e, ManagedRegionAdoptedEvent) and e.file == "frontmatter.schema.yaml"
    ]
    region_ids = sorted(e.region for e in fresh_region_events)
    assert "types" in region_ids
    assert "fields" in region_ids

    # Replay must supersede the seeded stale ``content_hash`` with the
    # fresh canonical hash — without latest-wins replay across the
    # re-emitted region row, the host would silently appear clean on
    # the next aggregator pass. Pins the idempotent-replay invariant
    # spec §Edge cases "Crash during the adoption phase" relies on.
    from llm_wiki_kit.journal import replay_state

    state = replay_state(read_events(journal_path))
    types_key = ("frontmatter.schema.yaml", "types")
    assert types_key in state.adopted_regions
    assert state.adopted_regions[types_key].content_hash != "stale-from-prior-run"


def test_init_adopt_resumes_when_journal_has_only_init_and_adopt_events(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC4b — init-in-progress journal (VaultInit + adopts, no PrimitiveInstall) re-runs.

    Recovery contract from spec §Edge cases "Crash during the adoption
    phase". Asserts the second run re-emits the adopt event freshly
    (NOT a skip-if-already-adopted optimisation).
    """

    from datetime import UTC, datetime

    vault = tmp_path / "vault"
    vault.mkdir()
    user_body = "user wrote this README\n"
    target = vault / "wiki" / "people" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_text(user_body, encoding="utf-8")
    user_hash = _hash(user_body)

    # Hand-seed an init-in-progress journal.
    journal_path = _journal_path(vault)
    journal_path.parent.mkdir()
    now = datetime.now(UTC)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=now, by="wiki-init", vault_name=vault.name, recipe="people-only"),
    )
    append_event(
        journal_path,
        PageAdoptedEvent(
            timestamp=now,
            by="wiki-init-adopt",
            path="wiki/people/README.md",
            hash=user_hash,
        ),
    )
    seed_length = len(read_events(journal_path))

    exit_code = main(
        ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
        kit_root=people_kit,
    )

    assert exit_code == 0
    events = read_events(journal_path)
    new_slice = events[seed_length:]

    # First event after the seed is a fresh VaultInitEvent for the
    # re-run. The next adopt event for the path is a FRESH
    # PageAdoptedEvent (verifies re-emit; latest-wins replay).
    adopt_re_emit = [
        e
        for e in new_slice
        if isinstance(e, PageAdoptedEvent) and e.path == "wiki/people/README.md"
    ]
    assert len(adopt_re_emit) == 1
    assert adopt_re_emit[0].hash == user_hash

    # PrimitiveInstallEvent lands afterward, completing the install.
    primitive_events = [e for e in new_slice if isinstance(e, PrimitiveInstallEvent)]
    assert len(primitive_events) >= 1


def test_init_without_adopt_over_init_in_progress_journal_points_at_adopt(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reviewer Concern 2 — re-run without ``--adopt`` over an init-in-progress
    journal routes the user to the recovery path, not "remove .wiki.journal/".

    The generic empty-dir refusal would tell a user to delete
    ``.wiki.journal/``, destroying the very recovery slot ADR-0008 §6
    pins. ``_cmd_init`` detects the init-in-progress shape and
    surfaces ``re-run with --adopt to resume`` instead.
    """

    from datetime import UTC, datetime

    vault = tmp_path / "vault"
    vault.mkdir()
    journal_path = _journal_path(vault)
    journal_path.parent.mkdir()
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=datetime.now(UTC),
            by="wiki-init",
            vault_name=vault.name,
            recipe="people-only",
        ),
    )

    exit_code = main(
        ["init", str(vault), "--recipe", "people-only", "--no-git"],
        kit_root=people_kit,
    )

    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "init-in-progress" in err
    assert "--adopt" in err
    # The generic "remove its contents" message would mis-direct the
    # user to delete the journal — assert it does NOT fire here.
    assert "remove its contents" not in err


# ---------------------------------------------------------------------------
# AC5 — plain init still refuses non-empty targets
# ---------------------------------------------------------------------------


def test_init_without_adopt_refuses_non_empty(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC5 — without ``--adopt``, the empty-dir refusal still fires."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "stray.md").write_text("user", encoding="utf-8")

    exit_code = main(
        ["init", str(vault), "--recipe", "people-only", "--no-git"],
        kit_root=people_kit,
    )
    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "not empty" in err
    assert not (vault / ".wiki.journal").exists()


# ---------------------------------------------------------------------------
# AC6 — adoption-event interleave order
# ---------------------------------------------------------------------------


def test_init_adopt_interleaves_page_and_region_events_per_host(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC6 — for each pre-existing host file, page → its regions → next host.

    Uses ``frontmatter.schema.yaml`` (the only managed-region host
    shipped by ``core``). The recipe under test doesn't trigger
    content-type contributions, so we forge two regions on disk and
    seed a host file that contains both. The adopt phase walks both.
    """

    vault = tmp_path / "vault"
    vault.mkdir()

    # Pre-place a frontmatter.schema.yaml with two managed regions.
    # The `core` primitive's `files/` tree ships this path, so it's in
    # the recipe's rendered closure. (The adopt phase emits a
    # PageAdoptedEvent for any kit-owned-by-recipe path; managed-region
    # rows only fire when the closure includes a contributor to a region
    # of that file. The ``people-only`` recipe doesn't contribute, so we
    # only assert the PageAdoptedEvent for the host — and pin the
    # interleave with a separate AC8 test that uses the family recipe
    # whose content-type primitives DO contribute to the regions.)
    host_body = "types:\n  # BEGIN MANAGED: types\n  - user-type\n  # END MANAGED: types\n"
    (vault / "frontmatter.schema.yaml").write_text(host_body, encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    events = read_events(_journal_path(vault))
    # First event is the VaultInit.
    assert isinstance(events[0], VaultInitEvent)
    # The page-adopt for the host fires before the install pipeline
    # touches anything (PrimitiveInstallEvent is strictly later).
    host_adopt_indices = [
        i
        for i, e in enumerate(events)
        if isinstance(e, PageAdoptedEvent) and e.path == "frontmatter.schema.yaml"
    ]
    primitive_indices = [i for i, e in enumerate(events) if isinstance(e, PrimitiveInstallEvent)]
    assert host_adopt_indices, "expected a PageAdoptedEvent for the host file"
    assert primitive_indices, "expected at least one PrimitiveInstallEvent"
    assert max(host_adopt_indices) < min(primitive_indices)


def test_init_adopt_emits_managed_region_adopted_and_pages_interleaved(
    tmp_path: Path,
) -> None:
    """AC6 + AC8 — the family recipe pulls in content-type contributors
    so a pre-existing ``frontmatter.schema.yaml`` with managed regions
    emits both a ``PageAdoptedEvent`` and a
    ``ManagedRegionAdoptedEvent`` for each region the recipe needs,
    interleaved page → regions → next host.
    """

    vault = tmp_path / "vault"
    vault.mkdir()

    host_body = (
        "types:\n"
        "  # BEGIN MANAGED: types\n"
        "  - user-type-a\n"
        "  - user-type-b\n"
        "  # END MANAGED: types\n"
        "fields:\n"
        "  # BEGIN MANAGED: fields\n"
        "  user_field:\n"
        "    type: string\n"
        "  # END MANAGED: fields\n"
    )
    (vault / "frontmatter.schema.yaml").write_text(host_body, encoding="utf-8")

    exit_code = main(
        ["init", str(vault), "--recipe", "family", "--no-git", "--adopt"],
    )
    assert exit_code == 0

    events = read_events(_journal_path(vault))

    # Sequence assertion: PageAdoptedEvent(host) is immediately followed
    # by its ManagedRegionAdoptedEvents (sorted by region) before any
    # other host's page event or any PrimitiveInstallEvent.
    page_idx = next(
        i
        for i, e in enumerate(events)
        if isinstance(e, PageAdoptedEvent) and e.path == "frontmatter.schema.yaml"
    )
    next_install = next(i for i, e in enumerate(events) if isinstance(e, PrimitiveInstallEvent))
    assert page_idx < next_install

    region_events_for_host = [
        e
        for e in events[page_idx + 1 : next_install]
        if isinstance(e, ManagedRegionAdoptedEvent) and e.file == "frontmatter.schema.yaml"
    ]
    assert len(region_events_for_host) >= 2
    assert [r.region for r in region_events_for_host] == sorted(
        r.region for r in region_events_for_host
    )
    for region_event in region_events_for_host:
        assert region_event.by == "wiki-init-adopt"


# ---------------------------------------------------------------------------
# AC7 — `by` attribution discipline
# ---------------------------------------------------------------------------


def test_init_adopt_by_attribution(tmp_path: Path, people_kit: Path) -> None:
    """AC7 — each event class carries the expected ``by`` value."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md").write_text("user\n", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    for event in read_events(_journal_path(vault)):
        if isinstance(event, VaultInitEvent):
            assert event.by == "wiki-init"
        elif isinstance(event, PrimitiveInstallEvent):
            assert event.by == "wiki-init"
        elif isinstance(event, (PageAdoptedEvent, ManagedRegionAdoptedEvent)):
            assert event.by == "wiki-init-adopt"
        elif isinstance(event, PageWriteEvent):
            # Adopted-then-no-rewrite emits a PageWriteEvent attributed
            # to the primitive that authored the kit's content; render
            # pipeline writes attribute to the primitive name; the
            # outcome-slash-stub writer attributes to the install
            # vehicle. Either is a non-"wiki-init-adopt" value.
            assert event.by != "wiki-init-adopt"
        elif isinstance(event, ManagedRegionWriteEvent):
            # Aggregator-emitted region writes attribute to wiki-init.
            assert event.by == "wiki-init"


# ---------------------------------------------------------------------------
# AC9 / AC9b — malformed markers / missing required region refuse
# ---------------------------------------------------------------------------


def test_init_adopt_malformed_host_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC9 — unbalanced markers in a host file refuse, no journal events."""

    vault = tmp_path / "vault"
    vault.mkdir()
    # Unbalanced markers.
    (vault / "frontmatter.schema.yaml").write_text(
        "  # BEGIN MANAGED: types\n  - x\n", encoding="utf-8"
    )

    exit_code = main(
        ["init", str(vault), "--recipe", "family", "--no-git", "--adopt"],
    )
    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "cannot adopt managed-region host" in err
    assert "markers do not parse" in err
    # Journal is absent (refusal fires BEFORE target.mkdir / cache scope).
    assert not _journal_path(vault).exists()


def test_init_adopt_missing_required_region_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC9b — parseable host missing a recipe-needed region refuses."""

    vault = tmp_path / "vault"
    vault.mkdir()
    # Declares only `types`, but the family recipe contributes to both
    # `types` and `fields` via its content-type primitives.
    (vault / "frontmatter.schema.yaml").write_text(
        "  # BEGIN MANAGED: types\n  - x\n  # END MANAGED: types\n",
        encoding="utf-8",
    )

    exit_code = main(
        ["init", str(vault), "--recipe", "family", "--no-git", "--adopt"],
    )
    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "cannot adopt managed-region host" in err
    assert "missing markers for region 'fields'" in err


# ---------------------------------------------------------------------------
# AC10 — pre-existing sidecar surfaced not adopted
# ---------------------------------------------------------------------------


def test_init_adopt_pre_existing_sidecar_surfaced_not_adopted(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC10 — kit-owned .proposed is surfaced (stderr) but never adopted."""

    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "wiki" / "people" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_text("user body\n", encoding="utf-8")
    sidecar = vault / "wiki" / "people" / "README.md.proposed"
    sidecar.write_text("orphan sidecar\n", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()

    events = read_events(_journal_path(vault))
    adopt_paths = {e.path for e in events if isinstance(e, PageAdoptedEvent)}
    assert "wiki/people/README.md" in adopt_paths
    assert "wiki/people/README.md.proposed" not in adopt_paths

    # stderr-only warning; stdout must not contain the line.
    assert "found 1 pre-existing kit-owned .proposed sidecar." in captured.err
    # Past-tense remediation surfaced (spec §Outputs Stderr; QE Concern 4
    # — the warning emits AFTER render closes, so the sidecar has already
    # been overwritten by ``safe_write``'s drift branch).
    assert "will have overwritten the prior sidecar content" in captured.err
    assert "recover from git history" in captured.err
    assert "pre-existing kit-owned" not in captured.out


def test_init_adopt_pre_existing_sidecars_plural_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC10 plural — N > 1 pre-existing kit-owned sidecars use the plural noun.

    The family recipe ships ``frontmatter.schema.yaml`` (host file from
    ``core``) and ``wiki/people/README.md`` (from the ``people``
    ontology), so seeding both as pre-existing sidecars exercises the
    plural branch on stderr.
    """

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md.proposed").write_text(
        "stale sidecar A\n", encoding="utf-8"
    )
    (vault / "frontmatter.schema.yaml.proposed").write_text("stale sidecar B\n", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "family", "--no-git", "--adopt"],
        )
        == 0
    )
    err = capsys.readouterr().err
    # Plural noun + count branch.
    assert "found 2 pre-existing kit-owned .proposed sidecars." in err
    assert "1 pre-existing kit-owned .proposed sidecar." not in err


def test_init_adopt_user_territory_sidecar_no_warning(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A .proposed at a path the recipe does NOT own is ignored entirely."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    (vault / "notes" / "personal.md.proposed").write_text("user sidecar\n", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    err = capsys.readouterr().err
    assert "pre-existing kit-owned" not in err


# ---------------------------------------------------------------------------
# AC11 / AC12 — user-territory file under/outside kit dir
# ---------------------------------------------------------------------------


def test_init_adopt_user_file_in_kit_dir_surfaces_as_orphan(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC11 — a user file under a kit-owned dir is NOT adopted but flagged orphan."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "uncle-bob.md").write_text("user", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    events = read_events(_journal_path(vault))
    adopt_paths = {e.path for e in events if isinstance(e, PageAdoptedEvent)}
    assert "wiki/people/uncle-bob.md" not in adopt_paths

    issues = doctor.run_doctor(vault, kit_root=people_kit)
    orphan_paths = {issue.path for issue in issues if issue.kind == doctor.ORPHAN}
    assert "wiki/people/uncle-bob.md" in orphan_paths


def test_init_adopt_user_file_outside_kit_dirs_invisible(tmp_path: Path, people_kit: Path) -> None:
    """AC12 — a user file in user territory is invisible to adopt + doctor."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    (vault / "notes" / "personal.md").write_text("user", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    events = read_events(_journal_path(vault))
    adopt_paths = {e.path for e in events if isinstance(e, PageAdoptedEvent)}
    assert "notes/personal.md" not in adopt_paths

    issues = doctor.run_doctor(vault, kit_root=people_kit)
    flagged = {issue.path for issue in issues}
    assert "notes/personal.md" not in flagged


# ---------------------------------------------------------------------------
# AC17 — doctor after --adopt reports expected issue set
# ---------------------------------------------------------------------------


def test_init_adopt_doctor_clean_for_byte_identical_targets(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC17 — byte-identical adopt produces zero issues post-run."""

    vault = tmp_path / "vault"
    seeds = _seeded_kit_files(vault, people_kit)
    vault.mkdir()
    for relative, body in seeds.items():
        target = vault / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    issues = doctor.run_doctor(vault, kit_root=people_kit)
    assert issues == [], f"expected zero issues; got {issues}"


def test_init_adopt_doctor_reports_pending_proposal_for_differing_target(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC17 — differing-bytes adopt surfaces a pending-proposal in doctor."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md").write_text("user", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    issues = doctor.run_doctor(vault, kit_root=people_kit)
    pending_paths = {issue.path for issue in issues if issue.kind == doctor.PENDING_PROPOSAL}
    # ``doctor`` reports the sidecar path on pending-proposal issues.
    assert "wiki/people/README.md.proposed" in pending_paths, (
        f"expected pending-proposal sidecar; got {issues}"
    )
    other_kinds = {issue.kind for issue in issues} - {doctor.PENDING_PROPOSAL}
    assert other_kinds == set(), f"expected only pending-proposals; got kinds {other_kinds}"


# ---------------------------------------------------------------------------
# AC18 — ordering: adoption events strictly before install events
# ---------------------------------------------------------------------------


def test_init_adopt_event_ordering_adopt_before_install(tmp_path: Path, people_kit: Path) -> None:
    """AC18 — every adoption event lands strictly before the first install event."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md").write_text("user", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    events = read_events(_journal_path(vault))
    first_install = next(i for i, e in enumerate(events) if isinstance(e, PrimitiveInstallEvent))
    for i, event in enumerate(events[:first_install]):
        # Pre-install slice contains only VaultInit + adoption events.
        assert isinstance(event, (VaultInitEvent, PageAdoptedEvent, ManagedRegionAdoptedEvent)), (
            f"event #{i} = {type(event).__name__}; expected init or adopt"
        )


# ---------------------------------------------------------------------------
# AC19 — symlink escape raises, journal absent
# ---------------------------------------------------------------------------


def test_init_adopt_symlink_escape_raises_no_journal(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC19 — a kit-owned symlink resolving outside the vault refuses cleanly."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text("user", encoding="utf-8")
    os.symlink(outside / "leaked.md", vault / "wiki" / "people" / "README.md")

    exit_code = main(
        ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
        kit_root=people_kit,
    )
    assert exit_code == WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "not inside the vault" in err
    # No journal because compute_adoption_set runs BEFORE target.mkdir
    # and BEFORE the journal-cache scope.
    assert not _journal_path(vault).exists()


# ---------------------------------------------------------------------------
# AC20a — TOCTOU between adoption walk and render-phase
# ---------------------------------------------------------------------------


def test_init_adopt_toctou_produces_proposal_not_silent_overwrite(
    tmp_path: Path,
    people_kit: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC20a — TOCTOU between adopt walk and render-phase keeps the user's bytes.

    Pre-place a kit-owned file with the kit's would-render bytes C₁ so
    ``compute_adoption_set`` hashes h(C₁) as the adopt baseline. Wrap
    ``compute_adoption_set`` with a one-shot side-effect that
    atomically replaces the file with C₂ AFTER it returns the
    AdoptionSet. The render phase then re-reads on-disk content; the
    adopt-aware predicate sees ``new_hash == adopted_hash !=
    on_disk_hash`` (kit's C₁ == journaled baseline, file is now C₂) →
    forced-proposal branch. Verifies the journaled hash is the
    walk-time snapshot, not the on-disk-at-render-time hash.
    """

    vault = tmp_path / "vault"
    seeds = _seeded_kit_files(vault, people_kit)
    assert "wiki/people/README.md" in seeds
    kit_bytes_c1 = seeds["wiki/people/README.md"]

    vault.mkdir()
    target = vault / "wiki" / "people" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(kit_bytes_c1)

    original = adopt_module.compute_adoption_set
    user_bytes_c2 = b"USER-EDITED-AFTER-WALK\n"

    def wrapped(vault_root: Path, primitives, sources):  # type: ignore[no-untyped-def]
        result = original(vault_root, primitives, sources)
        # Atomic replace AFTER the walk completes — simulates a user
        # editor saving the file between the adopt walk's read and the
        # render-phase's read.
        tmp_file = vault_root / "wiki" / "people" / "README.md.new"
        tmp_file.write_bytes(user_bytes_c2)
        os.replace(tmp_file, vault_root / "wiki" / "people" / "README.md")
        return result

    # ``llm_wiki_kit.cli`` does ``from llm_wiki_kit import adopt`` and
    # then calls ``adopt.compute_adoption_set(...)`` — both bindings
    # resolve through the same module object, so a single
    # ``monkeypatch.setattr`` on the module is enough.
    monkeypatch.setattr(adopt_module, "compute_adoption_set", wrapped)

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    # (a) on-disk bytes survive as C₂.
    assert target.read_bytes() == user_bytes_c2
    # (b) sidecar with C₁ exists.
    sidecar = vault / "wiki" / "people" / "README.md.proposed"
    assert sidecar.is_file()
    assert sidecar.read_bytes() == kit_bytes_c1
    # (c) journal records baseline at h(C₁) (the walk snapshot, not the
    #     current on-disk bytes) and the proposal at h(C₁).
    events = read_events(_journal_path(vault))
    adopt_events = [
        e for e in events if isinstance(e, PageAdoptedEvent) and e.path == "wiki/people/README.md"
    ]
    proposal_events = [
        e for e in events if isinstance(e, PageProposalEvent) and e.path == "wiki/people/README.md"
    ]
    assert adopt_events and adopt_events[0].hash == _hash(kit_bytes_c1)
    assert proposal_events and proposal_events[0].hash == _hash(kit_bytes_c1)


# ---------------------------------------------------------------------------
# AC21 — adopt-summary pluralization
# ---------------------------------------------------------------------------


def test_init_adopt_summary_line_singular(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC21 — N == 1 uses the singular noun."""

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md").write_text("user", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "wiki init: adopted 1 file." in captured.out
    assert "wiki init: adopted 1 files." not in captured.out


def test_init_adopt_summary_line_zero_no_line(
    tmp_path: Path, people_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC21 — N == 0 emits no summary line (empty target)."""

    vault = tmp_path / "vault"
    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "wiki init: adopted" not in captured.out


# ---------------------------------------------------------------------------
# Smoke: round-trip a hand-crafted journal carrying adopt events
# ---------------------------------------------------------------------------


def test_init_adopt_then_resolve_clears_sticky_adopt_end_to_end(
    tmp_path: Path, people_kit: Path
) -> None:
    """AC16 end-to-end — adopt → drift → resolve → no spurious re-proposal.

    Pins the integrated journey from spec §Invariant 4 + AC16: a
    ``PageAdoptedEvent`` baseline gets superseded by a ``PageWriteEvent``
    emitted from ``resolve_proposal``; the next ``safe_write`` over the
    resolved content takes the direct-write branch (no new
    ``PageProposalEvent``). The unit-level pin in
    ``tests/unit/test_write_helper_adopt.py`` covers the helper; this
    test exercises the full CLI flow → resolve → re-write loop.
    """

    from llm_wiki_kit.write_helper import resolve_proposal, safe_write

    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "wiki" / "people" / "README.md"
    target.parent.mkdir(parents=True)
    target.write_text("user body\n", encoding="utf-8")

    assert (
        main(
            ["init", str(vault), "--recipe", "people-only", "--no-git", "--adopt"],
            kit_root=people_kit,
        )
        == 0
    )

    journal_path = _journal_path(vault)
    events_after_init = read_events(journal_path)
    proposal_events = [
        e
        for e in events_after_init
        if isinstance(e, PageProposalEvent) and e.path == "wiki/people/README.md"
    ]
    assert len(proposal_events) == 1, "expected exactly one PageProposal from the adopt phase"

    # User resolves by accepting the kit's would-render content.
    sidecar_bytes = (vault / proposal_events[0].proposed_path).read_bytes()
    resolved_content = sidecar_bytes.decode("utf-8")
    resolve_proposal(
        path=Path("wiki/people/README.md"),
        content=resolved_content,
        by="wiki-conflict",
        journal_path=journal_path,
    )

    length_after_resolve = len(read_events(journal_path))
    # Subsequent safe_write with the same resolved content must take
    # direct-write — no new proposal — because resolve_proposal's
    # PageWriteEvent supersedes the PageAdoptedEvent baseline.
    safe_write(
        path=Path("wiki/people/README.md"),
        content=resolved_content,
        by="people",
        journal_path=journal_path,
    )

    new_slice = read_events(journal_path)[length_after_resolve:]
    fresh_proposals = [
        e
        for e in new_slice
        if isinstance(e, PageProposalEvent) and e.path == "wiki/people/README.md"
    ]
    assert fresh_proposals == [], (
        f"sticky-adopt should have cleared on resolve; got fresh proposals: {fresh_proposals}"
    )
    fresh_writes = [
        e for e in new_slice if isinstance(e, PageWriteEvent) and e.path == "wiki/people/README.md"
    ]
    assert len(fresh_writes) == 1
    assert fresh_writes[0].by == "people"


def test_adopt_events_dump_parse_round_trip() -> None:
    """Adopt events serialize and parse without loss (sanity)."""

    from datetime import UTC, datetime

    page_event = PageAdoptedEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        by="wiki-init-adopt",
        path="wiki/people/README.md",
        hash="abc",
    )
    region_event = ManagedRegionAdoptedEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        by="wiki-init-adopt",
        file="frontmatter.schema.yaml",
        region="types",
        content_hash="def",
    )

    page_round = parse_event_line(dump_event_json(page_event), 1)
    region_round = parse_event_line(dump_event_json(region_event), 2)
    assert page_round == page_event
    assert region_round == region_event
