"""Unit tests for ``llm_wiki_kit.install.enumerate_rendered_paths``.

The function is the source of truth for the kit-owned-by-recipe path
set (ADR-0008; spec ``docs/specs/wiki-init-adopt/spec.md`` §Contracts
"`llm_wiki_kit.install`") AND the adopt phase's walker.
:func:`llm_wiki_kit.render.render_tree` walks the same paths through
the shared private ``_iter_files_relative`` helper — see the AC22
structural pin (`test_enumerate_rendered_paths_matches_render_tree_output`).
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki_kit.install import enumerate_rendered_paths
from llm_wiki_kit.models import Primitive, PrimitiveKind
from llm_wiki_kit.render import render_tree

REPO_ROOT = Path(__file__).resolve().parents[2]


def _primitive(name: str, *, kind: PrimitiveKind = PrimitiveKind.CONTENT_TYPE) -> Primitive:
    return Primitive(
        name=name,
        kind=kind,
        version="0.1.0",
        description=f"Test primitive {name}.",
    )


def test_enumerate_rendered_paths_for_core_returns_seed_files() -> None:
    """The shipped ``core`` primitive seeds the file set named in the spec."""

    core = _primitive("core", kind=PrimitiveKind.INFRASTRUCTURE)
    sources = {"core": REPO_ROOT / "core"}

    paths = enumerate_rendered_paths([core], sources)

    # Top-level seed files the spec names (§Contracts "`llm_wiki_kit.install`"
    # plus core/files/ on disk).
    assert "AGENTS.md" in paths
    assert "CORE.md" in paths
    assert ".gitignore" in paths
    assert "frontmatter.schema.yaml" in paths
    # Nested SKILL.md files round-trip with POSIX separators.
    assert "skills/wiki-conflict/SKILL.md" in paths


def test_enumerate_rendered_paths_union_across_primitives() -> None:
    """Two primitives' file trees union into a single set."""

    core = _primitive("core", kind=PrimitiveKind.INFRASTRUCTURE)
    people = _primitive("people", kind=PrimitiveKind.ONTOLOGY)
    sources = {
        "core": REPO_ROOT / "core",
        "people": REPO_ROOT / "templates" / "ontologies" / "people",
    }

    core_only = enumerate_rendered_paths([core], sources)
    people_only = enumerate_rendered_paths([people], sources)
    both = enumerate_rendered_paths([core, people], sources)

    assert both == core_only | people_only
    assert "wiki/people/README.md" in both


def test_enumerate_rendered_paths_handles_nested_directories(tmp_path: Path) -> None:
    """Vault-relative POSIX paths survive deep nesting and round-trip suffixes."""

    primitive_root = tmp_path / "deep-primitive"
    files_dir = primitive_root / "files"
    (files_dir / "a" / "b" / "c").mkdir(parents=True)
    (files_dir / "a" / "b" / "c" / "leaf.md").write_text("hi", encoding="utf-8")
    (files_dir / "a" / "shallow.md").write_text("hi", encoding="utf-8")

    primitive = _primitive("deep-primitive")
    paths = enumerate_rendered_paths([primitive], {"deep-primitive": primitive_root})

    assert paths == {"a/b/c/leaf.md", "a/shallow.md"}


def test_enumerate_rendered_paths_returns_empty_for_no_files_dir(tmp_path: Path) -> None:
    """A primitive with no ``files/`` directory contributes nothing."""

    primitive_root = tmp_path / "no-files"
    primitive_root.mkdir()
    # Intentionally no `files/` subdir.

    primitive = _primitive("no-files")
    paths = enumerate_rendered_paths([primitive], {"no-files": primitive_root})

    assert paths == set()


def test_enumerate_rendered_paths_matches_render_tree_output(tmp_path: Path) -> None:
    """AC22 structural pin: ``render_tree`` writes exactly the path set
    ``enumerate_rendered_paths`` reports.

    Drives both surfaces over the same fixture primitive and asserts
    set-equality between the enumerator's return and the paths
    actually produced by ``render_tree`` into a tmp vault.
    """

    primitive_root = tmp_path / "fixture-primitive"
    files_dir = primitive_root / "files"
    (files_dir / "top.md").parent.mkdir(parents=True)
    (files_dir / "top.md").write_text("top body\n", encoding="utf-8")
    (files_dir / "nested" / "child.md").parent.mkdir(parents=True)
    (files_dir / "nested" / "child.md").write_text("child body\n", encoding="utf-8")
    # Empty-content path — the spec's AC22 explicitly names empty
    # rendered output as a case both walkers must agree on ("an empty
    # file is still a kit-owned file the adoption baseline should
    # journal"). Without an empty file in the fixture, a future
    # refactor that filters zero-byte templates in one walker but not
    # the other could slip past set-equality.
    (files_dir / "nested" / "empty.gitkeep").write_text("", encoding="utf-8")

    primitive = _primitive("fixture-primitive")
    enumerated = enumerate_rendered_paths([primitive], {"fixture-primitive": primitive_root})

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".wiki.journal").mkdir()
    journal_path = vault / ".wiki.journal" / "journal.jsonl"

    render_tree(files_dir, vault, {}, journal_path, by="fixture-primitive")

    written: set[str] = set()
    for path in vault.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(vault).as_posix()
        if rel.startswith(".wiki.journal/"):
            continue
        written.add(rel)

    assert enumerated == written
