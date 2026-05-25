"""Integration test for the ``wiki-bootstrap`` SKILL copy.

Spec: ``docs/specs/wiki-bootstrap/spec.md``
Plan: ``docs/specs/wiki-bootstrap/plan.md`` § T4

Covers AC 4 — ``wiki init`` must copy ``core/files/skills/wiki-bootstrap/``
byte-for-byte into the vault. Parametrized over every shipped recipe
so a regression to the core-file copy walk fails for every recipe at
once, not just one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_SKILL = REPO_ROOT / "core" / "files" / "skills" / "wiki-bootstrap" / "SKILL.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("recipe", ["personal", "family", "work-os"])
def test_wiki_init_copies_wiki_bootstrap_skill(tmp_path: Path, recipe: str) -> None:
    """``wiki init --recipe <recipe>`` copies the wiki-bootstrap SKILL byte-equal."""

    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--recipe", recipe, "--no-git"]) == 0, (
        f"`wiki init --recipe {recipe}` should succeed"
    )

    installed = vault / "skills" / "wiki-bootstrap" / "SKILL.md"
    assert installed.is_file(), f"`skills/wiki-bootstrap/SKILL.md` missing from `{recipe}` vault"
    assert _sha256(installed) == _sha256(SOURCE_SKILL), (
        "installed wiki-bootstrap SKILL.md differs from `core/files/` source — "
        "ADR-0001 requires byte-for-byte SKILL copy"
    )
