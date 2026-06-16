"""Pins for the T5 vault-side folder re-pointing + deferral registration.

The reshape removed the five entity-kind ontologies and the nine content-type
kind folders. Every *folder* reference in the vault-side content-type ingest
`SKILL.md` docs must therefore point at a role folder — entity stubs at
`people/`, page-home at `library/` or the re-homed `efforts/<type>/` registries
— so no shipped SKILL instructs an agent to write into a folder the reshape
deleted. The orthogonal `type:`→`genre`/`subtype` value faceting is *not* done
here; it (plus the operation SKILLs, the search globs, and the starter seed
pages) is registered as deferred under `docs/backlog.md`.

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "entity-stub
re-point"; "deferral registered").
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_TYPES_DIR = REPO_ROOT / "templates" / "content-types"
BACKLOG = REPO_ROOT / "docs" / "backlog.md"

# Folders the reshape removed (entity-kind ontologies + content-type kinds) or
# re-homed (trips/projects now live under efforts/). A reference to any of these
# as a `wiki/<folder>/` path or a `[[<folder>/` wikilink is stale.
STALE_FOLDERS = (
    "customers",
    "vendors",
    "food",
    "medical",
    "domains",
    "meetings",
    "actions",
    "decisions",
    "interviews",
    "customer-feedback",
    "receipts",
    "tax",
    "stakeholder-updates",
    "vendor-contracts",
    "trips",
    "projects",
)

# Matches a stale folder only in a wiki-page context (`wiki/<f>/` or `[[<f>/`),
# never `raw/<f>/` (gitignored input staging) or `efforts/trips/` (re-homed).
_STALE_RE = re.compile(r"(?:wiki/|\[\[)(?:" + "|".join(STALE_FOLDERS) + r")/")


def _ingest_skills() -> list[Path]:
    return sorted(CONTENT_TYPES_DIR.glob("*/files/skills/*/SKILL.md"))


def test_ingest_skills_exist() -> None:
    assert _ingest_skills(), "no content-type ingest SKILLs found"


@pytest.mark.parametrize("skill", _ingest_skills(), ids=lambda p: p.parent.name)
def test_ingest_skill_references_no_stale_folder(skill: Path) -> None:
    text = skill.read_text(encoding="utf-8")
    offenders = sorted({m.group(0) for m in _STALE_RE.finditer(text)})
    assert not offenders, f"{skill.parent.name} references stale folders: {offenders}"


@pytest.mark.parametrize("skill", _ingest_skills(), ids=lambda p: p.parent.name)
def test_ingest_skill_homes_pages_in_a_role_folder(skill: Path) -> None:
    """Each ingest SKILL names at least one role-folder home for its pages/stubs."""
    text = skill.read_text(encoding="utf-8")
    assert re.search(r"wiki/(people|library|efforts|atlas)/", text), (
        f"{skill.parent.name} names no role-folder page home"
    )


def test_backlog_registers_role_folders_deferrals() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    assert "## role-folders-and-containers" in text, "backlog missing the spec section"
    # The deferral set named by the spec AC.
    for needle in (
        "_templates",  # content-type doc/template value faceting
        "operations-and-search-rekey",  # operation SKILLs + search globs
        "starter",  # hand-authored seed pages
        "capture-synthesis-gating",  # atlas/ gating owner
    ):
        assert needle in text, f"backlog role-folders section does not name {needle!r}"
