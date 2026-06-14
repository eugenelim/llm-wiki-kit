"""T5: a fresh ``wiki init --recipe personal`` lands both lenses and lists them.

The personal-recipe-workspaces follow-on (RFC-0008) composes the ``content-studio``
(membership) and ``planning`` (cross-cutting) lenses into ``recipes/personal.yaml``.
A user who runs ``wiki init --recipe personal`` should get both ``.base`` views, both
namespaced bootstrap notes (coexisting — the bootstrap-clobber regression guard), and
both rows in ``wiki workspaces`` with no extra setup.

Runs against the real shipped kit (default ``kit_root``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTENT_STUDIO = REPO_ROOT / "templates" / "workspaces" / "content-studio" / "files"
_PLANNING = REPO_ROOT / "templates" / "workspaces" / "planning" / "files"


def test_init_personal_lands_both_lenses_and_lists_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--recipe", "personal"]) == 0

    # Both .base views land byte-identical to the shipped templates (verbatim,
    # never interpolated — Bases brace syntax must survive).
    for name in ("content-studio", "planning"):
        landed = vault / f"{name}.base"
        shipped = (_CONTENT_STUDIO if name == "content-studio" else _PLANNING) / f"{name}.base"
        assert landed.read_bytes() == shipped.read_bytes()

    # Both bootstrap notes coexist as distinct files, each byte-identical to its
    # shipped template — the regression guard for the bootstrap-clobber defect.
    cs_bootstrap = vault / "content-studio.bootstrap.md"
    pl_bootstrap = vault / "planning.bootstrap.md"
    cs_shipped = _CONTENT_STUDIO / "content-studio.bootstrap.md"
    pl_shipped = _PLANNING / "planning.bootstrap.md"
    assert cs_bootstrap.read_bytes() == cs_shipped.read_bytes()
    assert pl_bootstrap.read_bytes() == pl_shipped.read_bytes()
    assert cs_bootstrap.read_text() != pl_bootstrap.read_text()

    # `wiki workspaces` lists both rows out of the box.
    monkeypatch.chdir(vault)
    capsys.readouterr()  # drop init output
    assert main(["workspaces"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "NAME\tSCOPE\tAGENT\tOPERATIONS"
    assert "content-studio\tcontent-studio\tpersonal-coordinator\t—" in out
    assert "planning\t(all notes)\tpersonal-coordinator\tfollow-up-tracker, weekly-digest" in out
