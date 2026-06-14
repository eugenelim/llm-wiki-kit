"""T1: the shipped ``planning`` cross-cutting workspace primitive validates.

``planning`` is the first shipped *empty-scope* lens (RFC-0008's cross-cutting
case — the path was previously only covered by synthetic fixtures). It carries
no ``scope`` (meaning "all notes"), reuses the existing ``personal-coordinator``
agent, and surfaces the ``follow-up-tracker`` / ``weekly-digest`` operations.
Its ``.base`` is cross-cutting: no ``workspaces.contains(...)`` membership
filter, and ``status`` is the primary (first) sort key.

Runs against the real shipped kit, so a regression in the example's own files
or manifest surfaces here.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki_kit.models import PrimitiveKind
from llm_wiki_kit.primitives import discover_primitives, load_primitive

REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_DIR = REPO_ROOT / "templates" / "workspaces" / "planning"


def test_planning_manifest_validates_as_empty_scope_workspace() -> None:
    primitive = load_primitive(_WORKSPACE_DIR)
    assert primitive.kind is PrimitiveKind.WORKSPACE
    # Empty/absent scope == the cross-cutting "all notes" lens.
    assert primitive.scope is None
    assert primitive.agent == "personal-coordinator"
    assert primitive.operations == ["follow-up-tracker", "weekly-digest"]
    assert primitive.view == "planning.base"
    assert primitive.bootstrap == "planning.bootstrap.md"


def test_planning_is_discovered_as_a_workspace() -> None:
    catalog = {p.name: p for p in discover_primitives(REPO_ROOT / "templates")}
    assert "planning" in catalog
    assert catalog["planning"].kind is PrimitiveKind.WORKSPACE


def test_planning_base_is_cross_cutting_and_status_ordered() -> None:
    base_path = _WORKSPACE_DIR / "files" / "planning.base"
    text = base_path.read_text(encoding="utf-8")
    # Cross-cutting: no membership filter.
    assert "workspaces.contains" not in text
    # status-primary ordering is the machine-checkable part of "ordered by status".
    parsed = yaml.safe_load(text)
    order = parsed["views"][0]["order"]
    assert order[0] == "status"


def test_workspace_bootstraps_are_namespaced_no_clobber() -> None:
    """T2 / spec AC-3: bootstraps render to distinct vault-relative paths.

    Both ``content-studio`` and ``planning`` ship a bootstrap note. Before the
    fix they used the bare ``files/bootstrap.md``, which ``render_tree`` flattens
    to the same vault-root ``bootstrap.md`` — so composing both in one recipe
    silently clobbered the first-installed lens's bootstrap. Namespacing as
    ``<name>.bootstrap.md`` is the regression guard at the render layer: the two
    workspaces' ``files/`` trees must yield two distinct bootstrap paths, and no
    bare ``bootstrap.md`` may remain.
    """

    from llm_wiki_kit.render import _iter_files_relative

    templates = REPO_ROOT / "templates" / "workspaces"
    cs_files = set(_iter_files_relative(templates / "content-studio" / "files"))
    pl_files = set(_iter_files_relative(templates / "planning" / "files"))

    assert "content-studio.bootstrap.md" in cs_files
    assert "planning.bootstrap.md" in pl_files
    # No clobber: no bare bootstrap.md, and the two bootstrap paths differ.
    assert "bootstrap.md" not in cs_files
    assert "bootstrap.md" not in pl_files
    cs_bootstraps = {f for f in cs_files if f.endswith("bootstrap.md")}
    pl_bootstraps = {f for f in pl_files if f.endswith("bootstrap.md")}
    assert cs_bootstraps.isdisjoint(pl_bootstraps)
