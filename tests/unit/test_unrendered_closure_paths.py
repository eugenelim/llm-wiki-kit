"""Unit tests for ``cli._unrendered_closure_paths`` — scope-guard predicate.

Pinned by ``docs/specs/wiki-upgrade-force-render/spec.md`` §Contracts
and AC2/AC15/AC18. Pure-function tests over a synthetic ``VaultState``
plus a tmp-dir vault; no journal mutation.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.adopt import compute_required_regions
from llm_wiki_kit.cli import _unrendered_closure_paths
from llm_wiki_kit.install import enumerate_rendered_paths
from llm_wiki_kit.models import (
    Contribution,
    Primitive,
    PrimitiveKind,
    VaultState,
)
from llm_wiki_kit.primitives import discover_primitives, load_primitive

REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_kit(tmp_path: Path) -> Path:
    """Mirror ``test_wiki_upgrade._install_kit`` — copy a minimal kit."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    templates_src = REPO_ROOT / "templates"
    (kit / "templates").mkdir()
    for relative in (
        "ontologies/people",
        "content-types/meeting",
        "operations/weekly-digest",
    ):
        kind = relative.split("/", 1)[0]
        (kit / "templates" / kind).mkdir(exist_ok=True)
        shutil.copytree(templates_src / relative, kit / "templates" / relative)

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: Core-only recipe.\n"
        "primitives:\n"
        "  - core\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    return _install_kit(tmp_path)


def _catalog_and_sources(kit_root: Path) -> tuple[list[Primitive], dict[str, Path]]:
    core = load_primitive(kit_root / "core")
    catalog: list[Primitive] = [core]
    catalog.extend(discover_primitives(kit_root / "templates"))
    sources: dict[str, Path] = {core.name: kit_root / "core"}
    for primitive in catalog:
        if primitive.name == core.name:
            continue
        # Mirror cli._primitive_source_dir for templates.
        candidates = list((kit_root / "templates").glob(f"*/{primitive.name}"))
        assert len(candidates) == 1
        sources[primitive.name] = candidates[0]
    return catalog, sources


def _state(installed: dict[str, str]) -> VaultState:
    return VaultState(
        vault_name="v",
        recipe="minimal",
        installed_primitives=dict(installed),
    )


def test_unrendered_closure_paths_empty_when_all_present(tmp_path: Path, kit_root: Path) -> None:
    """A vault with every closure path on disk returns ``[]``.

    Pre-place every path in ``enumerate_rendered_paths([core], sources) |
    set(compute_required_regions([core]))`` and assert the helper
    returns empty.
    """

    vault = tmp_path / "v"
    vault.mkdir()
    catalog, sources = _catalog_and_sources(kit_root)
    core = next(p for p in catalog if p.name == "core")
    state = _state({"core": core.version})

    closure = enumerate_rendered_paths([core], sources) | set(compute_required_regions([core]))
    for rel in closure:
        target = vault / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder", encoding="utf-8")

    assert _unrendered_closure_paths(state, vault, catalog, sources) == []


def test_unrendered_closure_paths_lists_missing_paths_sorted(
    tmp_path: Path, kit_root: Path
) -> None:
    """Deleted paths surface in sorted vault-relative POSIX order."""

    vault = tmp_path / "v"
    vault.mkdir()
    catalog, sources = _catalog_and_sources(kit_root)
    core = next(p for p in catalog if p.name == "core")
    state = _state({"core": core.version})

    closure = sorted(
        enumerate_rendered_paths([core], sources) | set(compute_required_regions([core]))
    )
    for rel in closure:
        target = vault / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder", encoding="utf-8")

    deleted = [closure[0], closure[-1]]
    for rel in deleted:
        (vault / rel).unlink()

    result = _unrendered_closure_paths(state, vault, catalog, sources)
    assert result == sorted(deleted)


def test_unrendered_closure_paths_includes_host_file_only_contributions(
    tmp_path: Path,
) -> None:
    """A primitive whose only claim is via ``contributes_to`` still surfaces.

    Pins the defense-in-depth value of the ``compute_required_regions``
    union in ``_unrendered_closure_paths``: today every host file is
    shipped by some primitive's ``files/`` tree, but if a future
    primitive ships only a ``contributes_to`` entry the helper must
    still include the host path in the closure check.
    """

    vault = tmp_path / "v"
    vault.mkdir()

    host_only = Primitive(
        name="host-only",
        kind=PrimitiveKind.CONTENT_TYPE,
        version="0.1.0",
        description="Contributes-only test primitive (no files/ tree).",
        contributes_to=[Contribution(file="frontmatter.schema.yaml", region="types")],
    )

    # Source root with no ``files/`` directory so enumerate_rendered_paths
    # contributes nothing for this primitive.
    source_root = tmp_path / "src"
    source_root.mkdir()
    sources = {"host-only": source_root}
    state = _state({"host-only": "0.1.0"})
    catalog = [host_only]

    result = _unrendered_closure_paths(state, vault, catalog, sources)
    assert "frontmatter.schema.yaml" in result


def test_unrendered_closure_paths_skips_primitive_missing_from_catalog(
    tmp_path: Path, kit_root: Path
) -> None:
    """An installed primitive absent from the catalog contributes nothing.

    The closure is undefined when the kit doesn't ship the primitive
    anymore; ``wiki doctor``'s ``primitive-missing`` check surfaces
    that state.
    """

    vault = tmp_path / "v"
    vault.mkdir()
    catalog, sources = _catalog_and_sources(kit_root)
    state = _state({"gone": "0.0.1"})
    assert _unrendered_closure_paths(state, vault, catalog, sources) == []


def test_unrendered_closure_paths_empty_when_no_installed_primitives(
    tmp_path: Path, kit_root: Path
) -> None:
    """``installed_primitives == {}`` returns ``[]`` regardless of disk state."""

    vault = tmp_path / "v"
    vault.mkdir()
    catalog, sources = _catalog_and_sources(kit_root)
    state = _state({})
    assert _unrendered_closure_paths(state, vault, catalog, sources) == []


def test_unrendered_closure_paths_is_pure_no_journal_writes(tmp_path: Path, kit_root: Path) -> None:
    """The helper performs no I/O outside the file-existence probe.

    Pins the spec's "Pure function; no I/O outside the file-existence
    probe" contract by asserting the vault's journal mtime is unchanged
    across a call.
    """

    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal"], kit_root=kit_root) == 0
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    pre_mtime = journal_path.stat().st_mtime_ns

    catalog, sources = _catalog_and_sources(kit_root)
    from llm_wiki_kit.journal import read_events, replay_state

    state = replay_state(read_events(journal_path))
    _ = _unrendered_closure_paths(state, vault, catalog, sources)
    post_mtime = journal_path.stat().st_mtime_ns
    assert pre_mtime == post_mtime
