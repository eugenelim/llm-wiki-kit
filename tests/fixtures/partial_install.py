"""Shared partial-install fixture builders for force-render integration tests.

Three helpers cover every shape the wiki-upgrade-force-render spec's
acceptance criteria need:

* :func:`make_partial_install_vault` — single-cut. Truncates the
  journal after the named primitive's ``PrimitiveInstallEvent`` so
  primitives that come after the cut are NOT in
  ``state.installed_primitives``. Used by AC2, AC3, AC7.
* :func:`make_two_primitive_partial_install_vault` — two-cut. Keeps
  BOTH ``PrimitiveInstallEvent`` rows durable but strips every
  per-primitive ``PageWriteEvent`` / ``ManagedRegionWriteEvent`` so
  both primitives' closures are partial. Used by AC5, AC20.
* :func:`make_init_only_vault` — keeps only ``VaultInitEvent``. Used
  by AC18 (post-init-pre-install crash).

The helpers live under ``tests/fixtures/`` because they are test-only
and not shipped to users. Each helper returns a
:class:`PartialInstallVault` snapshot — vault root, journal path,
pre-call journal bytes (for value-equal idempotence comparisons), the
``_unrendered_closure_paths`` list (for assertion-time invariant pins),
and the inodes of every adopted-path for AC2(c) inode-preservation
checks.

Self-tests in ``test_partial_install.py`` pin every helper's contract;
downstream ACs should not pass vacuously via short-circuit.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from llm_wiki_kit import cli
from llm_wiki_kit.adopt import compute_required_regions
from llm_wiki_kit.cli import _unrendered_closure_paths
from llm_wiki_kit.install import enumerate_rendered_paths
from llm_wiki_kit.journal import (
    append_event,
    dump_event_json,
    read_events,
    replay_state,
)
from llm_wiki_kit.models import (
    Event,
    ManagedRegionAdoptedEvent,
    ManagedRegionWriteEvent,
    PageAdoptedEvent,
    PageProposalEvent,
    PageWriteEvent,
    Primitive,
    PrimitiveInstallEvent,
)
from llm_wiki_kit.primitives import discover_primitives, load_primitive


@dataclass(frozen=True)
class PartialInstallVault:
    """Snapshot returned by every fixture helper.

    ``vault_root`` and ``journal_path`` point at the fixture vault on
    disk. ``pre_call_journal_bytes`` is the journal file's bytes
    immediately after truncation — handy for value-equal idempotence
    snapshots. ``pre_call_unrendered`` is the closure-presence list
    after truncation (the self-tests pin its non-empty contract for
    the partial-install helpers). ``adopted_path_inodes`` records the
    ``stat().st_ino`` of every adopted path so AC2(c) can pin the
    no-rewrite branch's inode-preservation contract.

    ``kit_root`` is the synthetic kit directory the helper built
    (so downstream tests can pass it to ``cli.main(..., kit_root=...)``).
    """

    vault_root: Path
    journal_path: Path
    kit_root: Path
    pre_call_journal_bytes: bytes
    pre_call_unrendered: list[str]
    adopted_path_inodes: dict[str, int]


def _install_kit(tmp_path: Path, *, primitives: list[str], recipe: str) -> Path:
    """Build a synthetic kit copying real ``core`` + ``templates``.

    Copies (does not symlink) so downstream tests can safely mutate
    the kit — e.g., AC17's broken-snippet scenario writes into
    ``kit_root/core/regions/`` which on a symlinked kit would
    pollute the source repo. ``shutil.copytree`` is the source of
    most of the fixture's wall-clock cost; the wiki-upgrade tests'
    ``_install_kit`` uses the same pattern, so the latency is
    bounded by the existing suite.

    The recipe lists ``primitives`` literally — the caller is
    responsible for naming primitives that exist in the repo's
    ``core/`` or ``templates/`` trees.
    """

    repo_root = cli._kit_root()
    kit_root = tmp_path / "kit"
    (kit_root / "recipes").mkdir(parents=True)
    primitive_lines = "\n".join(f"  - {name}" for name in primitives)
    (kit_root / "recipes" / f"{recipe}.yaml").write_text(
        f"name: {recipe}\n"
        "version: 0.1.0\n"
        "description: Test-only recipe for partial-install fixtures.\n"
        "primitives:\n"
        f"{primitive_lines}\n"
        "variables:\n"
        f"  recipe_name: {recipe}\n",
        encoding="utf-8",
    )
    shutil.copytree(repo_root / "core", kit_root / "core")
    shutil.copytree(repo_root / "templates", kit_root / "templates")
    return kit_root


def _journal_path(vault_root: Path) -> Path:
    return vault_root / ".wiki.journal" / "journal.jsonl"


def _resolve_sources(
    kit_root: Path,
    primitives_seq: list[str],
) -> dict[str, Path]:
    """Mirror ``cli._primitive_source_dir`` resolution for synthetic kits."""

    core_dir = kit_root / "core"
    templates_dir = kit_root / "templates"
    sources: dict[str, Path] = {}
    for name in primitives_seq:
        if name == "core":
            sources[name] = core_dir
        else:
            candidates = list(templates_dir.glob(f"*/{name}"))
            if len(candidates) != 1:
                raise AssertionError(
                    f"expected exactly one templates/<kind>/{name} dir, got {candidates}"
                )
            sources[name] = candidates[0]
    return sources


def _load_full_catalog(kit_root: Path) -> list[Primitive]:
    catalog = [load_primitive(kit_root / "core")]
    catalog.extend(discover_primitives(kit_root / "templates"))
    return catalog


def _rewrite_journal(journal_path: Path, events: list[Event]) -> None:
    """Overwrite the journal with the given events list, in order.

    Test-only operation: bypasses ``append_event`` so the on-disk byte
    layout is deterministic across runs (one event per line, trailing
    newline). The helpers below are the only callers; downstream tests
    never touch the journal directly.
    """

    lines = [dump_event_json(event) + "\n" for event in events]
    journal_path.write_text("".join(lines), encoding="utf-8")


def _validate_adopted_paths(
    adopted_paths: dict[str, bytes],
    surviving_primitives: list[str],
    sources: dict[str, Path],
    catalog: list[Primitive],
) -> None:
    """Raise ``ValueError`` if any adopted path is outside surviving primitives.

    A path "lies under" a primitive's ``files/`` tree if it is in
    ``enumerate_rendered_paths([primitive], sources)``. We accept
    paths that are reached as host-file contributions too
    (``compute_required_regions``) since the aggregator pass re-emits
    them.
    """

    if not adopted_paths:
        return
    catalog_by_name = {p.name: p for p in catalog}
    surviving_closure: set[str] = set()
    for name in surviving_primitives:
        if name not in catalog_by_name:
            continue
        primitive = catalog_by_name[name]
        surviving_closure |= enumerate_rendered_paths([primitive], sources)
        surviving_closure |= set(compute_required_regions([primitive]))
    for path in adopted_paths:
        if path not in surviving_closure:
            raise ValueError(
                f"adopted path '{path}' does not lie under any surviving primitive's "
                f"closure ({sorted(surviving_primitives)}); the runner's re-walk "
                "won't reach it. Choose a path under a primitive that survives the cut."
            )


def _delete_kit_owned_files(
    vault_root: Path,
    paths_to_delete: set[str],
) -> None:
    """Delete vault-relative paths from disk; ignore missing ones."""

    for relative in paths_to_delete:
        target = vault_root / relative
        if target.is_file():
            target.unlink()


def _adopted_inode_snapshot(vault_root: Path, adopted_paths: dict[str, bytes]) -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for path in adopted_paths:
        target = vault_root / path
        if target.is_file():
            snapshot[path] = target.stat().st_ino
    return snapshot


def make_partial_install_vault(
    tmp_path: Path,
    *,
    with_adopt: bool,
    primitives: list[str],
    cut_after_primitive: str,
    adopted_paths: dict[str, bytes] | None = None,
    recipe: str = "partial",
) -> PartialInstallVault:
    """Build a vault truncated after ``cut_after_primitive``'s install event.

    Behavior:

    1. Build a synthetic kit listing ``primitives`` in a recipe named
       ``recipe``.
    2. (Optional) Pre-place every entry in ``adopted_paths`` into the
       vault target. Validates that each adopted path lies under a
       primitive that survives the cut (a path under a cut primitive
       would be unreachable during force-render's re-walk, silently
       breaking downstream ACs).
    3. Run ``wiki init [--adopt] --no-git`` so the install pipeline
       writes the full closure and the journal.
    4. Truncate the journal: keep every event up to and including the
       ``PrimitiveInstallEvent`` whose ``primitive == cut_after_primitive``;
       drop the tail.
    5. Delete on-disk files corresponding to dropped events (so disk
       state matches the truncated journal).
    6. Return a :class:`PartialInstallVault` snapshot.

    Raises ``ValueError`` when ``adopted_paths`` lies outside the
    surviving primitives' closure (the self-test pins this contract).
    """

    if adopted_paths is None:
        adopted_paths = {}

    kit_root = _install_kit(tmp_path, primitives=primitives, recipe=recipe)
    vault_root = tmp_path / "vault"
    sources = _resolve_sources(kit_root, primitives)
    catalog = _load_full_catalog(kit_root)

    # Validate adopted_paths against the SURVIVING-primitives set so
    # the helper raises BEFORE doing any disk work.
    if cut_after_primitive not in primitives:
        raise ValueError(f"cut_after_primitive '{cut_after_primitive}' must be one of {primitives}")
    cut_index = primitives.index(cut_after_primitive)
    surviving = primitives[: cut_index + 1]
    _validate_adopted_paths(adopted_paths, surviving, sources, catalog)

    # Pre-place adopted content BEFORE init so --adopt captures it.
    if adopted_paths:
        for relative, content in adopted_paths.items():
            target = vault_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    init_argv = ["init", str(vault_root), "--recipe", recipe, "--no-git"]
    if with_adopt:
        init_argv.append("--adopt")
    assert cli.main(init_argv, kit_root=kit_root) == 0, (
        f"fixture pre-condition: wiki init must succeed; argv={init_argv}"
    )

    journal_path = _journal_path(vault_root)
    events = read_events(journal_path)

    # Find the cut index: the position of cut_after_primitive's install event.
    cut_event_index: int | None = None
    for index, event in enumerate(events):
        if isinstance(event, PrimitiveInstallEvent) and event.primitive == cut_after_primitive:
            cut_event_index = index
            break
    if cut_event_index is None:
        raise AssertionError(
            f"fixture pre-condition: PrimitiveInstallEvent({cut_after_primitive!r}) "
            f"not found in journal; events={[type(e).__name__ for e in events]}"
        )

    kept_events = events[: cut_event_index + 1]
    dropped_events = events[cut_event_index + 1 :]
    _rewrite_journal(journal_path, kept_events)

    # Delete on-disk files for every dropped PageWriteEvent /
    # ManagedRegionWriteEvent. Never delete an adopted path — those
    # are pre-existing user bytes the runner needs to find on disk so
    # the adopt-aware predicate can route correctly. Byte-identical
    # adopt-match paths produce a PageWriteEvent during the install
    # pipeline (the no-rewrite branch records the event), so this
    # subset MUST be filtered out: deleting them would erase user
    # bytes the runner is supposed to compare against.
    page_paths = {event.path for event in dropped_events if isinstance(event, PageWriteEvent)}
    region_files = {
        event.file for event in dropped_events if isinstance(event, ManagedRegionWriteEvent)
    }
    paths_to_delete = (page_paths | region_files) - set(adopted_paths)
    # Also drop any .proposed sidecars whose journal event was cut —
    # disk state must mirror the truncated journal, and a stale sidecar
    # would falsely satisfy ``rglob("*.proposed")`` precondition probes
    # in downstream ACs.
    dropped_sidecars = {
        event.proposed_path for event in dropped_events if isinstance(event, PageProposalEvent)
    }
    paths_to_delete |= dropped_sidecars
    _delete_kit_owned_files(vault_root, paths_to_delete)

    # Recompute snapshot AFTER deletions. Re-validate ``adopted_paths``
    # against the truncated state's installed_primitives (covers
    # transitive ``requires:`` so e.g. ``meeting`` pulling in ``people``
    # is recognised) — the up-front check against the user's literal
    # list is conservative; this one is precise.
    state = replay_state(kept_events)
    _validate_adopted_paths(adopted_paths, list(state.installed_primitives), sources, catalog)
    pre_call_unrendered = _unrendered_closure_paths(state, vault_root, catalog, sources)
    pre_call_journal_bytes = journal_path.read_bytes()
    adopted_path_inodes = _adopted_inode_snapshot(vault_root, adopted_paths)

    return PartialInstallVault(
        vault_root=vault_root,
        journal_path=journal_path,
        kit_root=kit_root,
        pre_call_journal_bytes=pre_call_journal_bytes,
        pre_call_unrendered=pre_call_unrendered,
        adopted_path_inodes=adopted_path_inodes,
    )


def make_two_primitive_partial_install_vault(
    tmp_path: Path,
    *,
    primitives: list[str],
    with_adopt: bool = False,
    adopted_paths: dict[str, bytes] | None = None,
    recipe: str = "partial",
) -> PartialInstallVault:
    """Build a vault where BOTH primitives have partial closures.

    Different shape from :func:`make_partial_install_vault`: both
    ``PrimitiveInstallEvent`` rows survive (so both primitives are in
    ``state.installed_primitives``), but every per-primitive
    ``PageWriteEvent`` and every ``ManagedRegionWriteEvent`` is
    stripped from the journal AND removed from disk. Used by AC5 (the
    ``--primitive`` narrowing test needs both primitives to have
    missing closure paths) and AC20 (shared-host-file recovery).

    Adopt baselines are preserved when ``with_adopt=True``.
    """

    if adopted_paths is None:
        adopted_paths = {}

    kit_root = _install_kit(tmp_path, primitives=primitives, recipe=recipe)
    vault_root = tmp_path / "vault"
    sources = _resolve_sources(kit_root, primitives)
    catalog = _load_full_catalog(kit_root)

    _validate_adopted_paths(adopted_paths, primitives, sources, catalog)

    if adopted_paths:
        for relative, content in adopted_paths.items():
            target = vault_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    init_argv = ["init", str(vault_root), "--recipe", recipe, "--no-git"]
    if with_adopt:
        init_argv.append("--adopt")
    assert cli.main(init_argv, kit_root=kit_root) == 0, (
        f"fixture pre-condition: wiki init must succeed; argv={init_argv}"
    )

    journal_path = _journal_path(vault_root)
    events = read_events(journal_path)

    # Keep VaultInit, adopt baselines, and every PrimitiveInstallEvent.
    # Drop every per-primitive PageWriteEvent / ManagedRegionWriteEvent /
    # PageProposalEvent. Adopt baselines are interleaved before
    # PrimitiveInstallEvents (per wiki-init-adopt spec §Outputs Journal
    # events); preserving them means BOTH the adopt-aware predicate AND
    # the post-truncation closure presence check operate on the right
    # state.
    kept_events: list[Event] = []
    dropped_events: list[Event] = []
    for event in events:
        if isinstance(event, PageWriteEvent | ManagedRegionWriteEvent | PageProposalEvent):
            dropped_events.append(event)
        else:
            kept_events.append(event)

    _rewrite_journal(journal_path, kept_events)

    page_paths = {event.path for event in dropped_events if isinstance(event, PageWriteEvent)}
    region_files = {
        event.file for event in dropped_events if isinstance(event, ManagedRegionWriteEvent)
    }
    paths_to_delete = (page_paths | region_files) - set(adopted_paths)
    paths_to_delete |= {
        event.proposed_path for event in dropped_events if isinstance(event, PageProposalEvent)
    }
    _delete_kit_owned_files(vault_root, paths_to_delete)

    state = replay_state(kept_events)
    _validate_adopted_paths(adopted_paths, list(state.installed_primitives), sources, catalog)
    pre_call_unrendered = _unrendered_closure_paths(state, vault_root, catalog, sources)
    pre_call_journal_bytes = journal_path.read_bytes()
    adopted_path_inodes = _adopted_inode_snapshot(vault_root, adopted_paths)

    return PartialInstallVault(
        vault_root=vault_root,
        journal_path=journal_path,
        kit_root=kit_root,
        pre_call_journal_bytes=pre_call_journal_bytes,
        pre_call_unrendered=pre_call_unrendered,
        adopted_path_inodes=adopted_path_inodes,
    )


def make_init_only_vault(
    tmp_path: Path,
    *,
    primitives: list[str] | None = None,
    recipe: str = "partial",
) -> PartialInstallVault:
    """Build a vault whose journal contains exactly one ``VaultInitEvent``.

    Implements the init-in-progress post-init-pre-install crash shape
    that wiki-init-adopt spec §Edge cases names. The helper truncates
    the journal to just the ``VaultInitEvent`` row and removes every
    kit-rendered file from disk so ``state.installed_primitives`` is
    empty and the closure check is degenerate.

    Used by AC18 — empty-installed init-in-progress hint.
    """

    if primitives is None:
        primitives = ["core"]
    kit_root = _install_kit(tmp_path, primitives=primitives, recipe=recipe)
    vault_root = tmp_path / "vault"

    assert (
        cli.main(
            ["init", str(vault_root), "--recipe", recipe, "--no-git"],
            kit_root=kit_root,
        )
        == 0
    )

    journal_path = _journal_path(vault_root)
    events = read_events(journal_path)
    init_events: list[Event] = [e for e in events if e.type == "vault.init"]
    if len(init_events) != 1:
        raise AssertionError(
            f"fixture pre-condition: exactly one VaultInitEvent expected; got {init_events}"
        )

    _rewrite_journal(journal_path, init_events)

    # Delete every kit-rendered file AND any proposal sidecar: the
    # journal now claims an empty installed_primitives set, so any
    # kit-owned file on disk would be an orphan from the doctor's
    # perspective.
    dropped = events[1:]
    paths_to_delete = {event.path for event in dropped if isinstance(event, PageWriteEvent)}
    region_files = {event.file for event in dropped if isinstance(event, ManagedRegionWriteEvent)}
    paths_to_delete |= region_files
    paths_to_delete |= {
        event.proposed_path for event in dropped if isinstance(event, PageProposalEvent)
    }
    _delete_kit_owned_files(vault_root, paths_to_delete)

    catalog = _load_full_catalog(kit_root)
    sources = _resolve_sources(kit_root, primitives)
    state = replay_state(init_events)
    pre_call_unrendered = _unrendered_closure_paths(state, vault_root, catalog, sources)
    pre_call_journal_bytes = journal_path.read_bytes()

    return PartialInstallVault(
        vault_root=vault_root,
        journal_path=journal_path,
        kit_root=kit_root,
        pre_call_journal_bytes=pre_call_journal_bytes,
        pre_call_unrendered=pre_call_unrendered,
        adopted_path_inodes={},
    )


# Re-export for convenience; downstream tests can import everything
# they need from this single module.
__all__ = [
    "PartialInstallVault",
    "make_init_only_vault",
    "make_partial_install_vault",
    "make_two_primitive_partial_install_vault",
]


# Silence "imported but unused" warnings for re-exported event classes
# used in fixture-self-tests.
_ = (
    PageAdoptedEvent,
    ManagedRegionAdoptedEvent,
    append_event,
)
