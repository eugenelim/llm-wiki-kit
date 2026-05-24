"""Vault-side ``wiki-conflict/SKILL.md`` is agent-aware (PR-7 of
RFC-0004 wiki-agents §B).

The kit reads zero bytes of the SKILL at runtime — the file lives
under ``core/files/skills/`` and is copied verbatim into a user's
vault by ``wiki init``. These tests are *verification-side* against
the shipped prose:

- frontmatter parses via ``pyyaml.safe_load`` (well-formedness);
- the body names the journal field ``proposed_by_agent`` literally
  (so a future SKILL edit can't quietly drop the agent-aware branch
  the kit's ``PageProposalEvent.proposed_by_agent`` field is there
  to feed).

Pinning the bareword field name (not a particular sentence) keeps
the SKILL author free to phrase the prose naturally while the test
guarantees the field is referenced.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "core" / "files" / "skills" / "wiki-conflict" / "SKILL.md"


def _split_frontmatter(text: str) -> tuple[str, str]:
    assert text.startswith("---\n"), "SKILL.md must open with a YAML frontmatter fence"
    parts = text.split("---\n", 2)
    assert len(parts) == 3, f"frontmatter fence malformed: got {len(parts)} parts"
    return parts[1], parts[2]


def test_wiki_conflict_skill_frontmatter_parses() -> None:
    """The SKILL's YAML frontmatter parses via ``pyyaml.safe_load`` and
    carries the standard ``name``/``description`` shape every SKILL ships."""

    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter_text, _body = _split_frontmatter(text)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict), "frontmatter did not parse as a mapping"
    assert frontmatter.get("name") == "wiki-conflict", (
        f"frontmatter name={frontmatter.get('name')!r}, expected 'wiki-conflict'"
    )
    description = frontmatter.get("description")
    assert isinstance(description, str) and description.strip(), (
        "frontmatter ``description`` must be a non-empty string"
    )


def test_wiki_conflict_skill_mentions_proposed_by_agent() -> None:
    """The SKILL body references the journal field ``proposed_by_agent``
    by name (not a particular sentence — phrasing is the SKILL author's
    judgment call)."""

    text = SKILL_PATH.read_text(encoding="utf-8")
    _frontmatter_text, body = _split_frontmatter(text)
    assert "proposed_by_agent" in body, (
        "wiki-conflict/SKILL.md must reference the journal field "
        "`proposed_by_agent` (the field PR-6 added to "
        "PageProposalEvent that this SKILL is meant to surface)"
    )
