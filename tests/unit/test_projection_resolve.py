"""T2 — destination resolution + the single confinement helper.

Covers spec ACs 1, 2, 3, 9. Both the ``--at`` branch and the
genre-routed candidate are confined through ``resolve_vault_path``; a
crafted basename cannot escape the role folder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.projection import (
    ROLE_FOLDERS,
    resolve_destination,
    resolve_vault_path,
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    for role in ("people", "library", "atlas", "efforts"):
        (vault / "wiki" / role).mkdir(parents=True)
    return vault


# --- ROLE_FOLDERS table (AC1) ----------------------------------------------


def test_role_folders_maps_all_nine_genres() -> None:
    assert ROLE_FOLDERS == {
        "profile": "people",
        "moc": "atlas",
        "note": "library",
        "record": "library",
        "update": "library",
        "decision": "library",
        "reference": "library",
        "log": "library",
        "contract": "library",
    }


# --- genre routing (AC1) ----------------------------------------------------


@pytest.mark.parametrize(
    ("genre", "role"),
    [
        ("profile", "people"),
        ("moc", "atlas"),
        ("record", "library"),
        ("reference", "library"),
    ],
)
def test_genre_routes_to_role_folder(tmp_path: Path, genre: str, role: str) -> None:
    vault = _vault(tmp_path)
    rel, abs_path = resolve_destination(genre, "jane-doe.md", None, vault)
    assert rel == f"wiki/{role}/jane-doe.md"
    assert abs_path == vault / "wiki" / role / "jane-doe.md"


# --- --at override (AC2) ----------------------------------------------------


def test_at_overrides_genre_routing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    rel, abs_path = resolve_destination(
        "record", "jane-doe.md", "wiki/efforts/japan-2026/notes.md", vault
    )
    assert rel == "wiki/efforts/japan-2026/notes.md"
    assert abs_path == vault / "wiki" / "efforts" / "japan-2026" / "notes.md"


# --- confinement of both branches (AC3) ------------------------------------


def test_at_rejects_absolute_path(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(WikiError, match="must be relative to the vault root"):
        resolve_destination("record", "x.md", "/etc/passwd", vault)


def test_at_rejects_parent_escape(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(WikiError, match="must resolve under the vault root"):
        resolve_destination("record", "x.md", "../../etc/x.md", vault)


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics differ on Windows")
def test_at_rejects_symlinked_parent_escape(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    # A symlinked *parent directory* under the vault that points outside it.
    (vault / "wiki" / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WikiError, match="must resolve under the vault root"):
        resolve_destination("record", "x.md", "wiki/link/x.md", vault)


def test_crafted_basename_cannot_escape_role_folder(tmp_path: Path) -> None:
    # A basename carrying path separators / .. is reduced to its final
    # component, so it lands inside the role folder, not outside it.
    vault = _vault(tmp_path)
    rel, abs_path = resolve_destination("record", "../../etc/passwd", None, vault)
    assert rel == "wiki/library/passwd"
    assert abs_path == vault / "wiki" / "library" / "passwd"
    assert os.path.commonpath([abs_path, (vault / "wiki" / "library")]) == str(
        vault / "wiki" / "library"
    )


# --- error branches (AC9 + robustness) -------------------------------------


def test_unknown_genre_raises(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(WikiError, match="no role-folder route for genre 'invoice'"):
        resolve_destination("invoice", "x.md", None, vault)


def test_missing_role_folder_raises(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "wiki" / "library").mkdir(parents=True)  # no people/
    with pytest.raises(WikiError, match="no wiki/people/ role folder"):
        resolve_destination("profile", "jane.md", None, vault)


@pytest.mark.parametrize("name", ["", ".", ".."])
def test_degenerate_basename_raises(tmp_path: Path, name: str) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(WikiError, match="cannot derive a page name"):
        resolve_destination("record", name, None, vault)


# --- shared helper directly -------------------------------------------------


def test_resolve_vault_path_label_in_message(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(WikiError, match="--out path must be relative"):
        resolve_vault_path("/abs", vault, label="--out path")
