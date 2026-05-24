"""Vault-side ``wiki-agent/SKILL.md`` is well-formed (PR-7 of
RFC-0004 wiki-agents §B).

The kit reads zero bytes of the SKILL at runtime; it ships at
``core/files/skills/wiki-agent/SKILL.md`` and is copied verbatim into
a user's vault by ``wiki init``. These tests pin only:

- frontmatter parses via ``pyyaml.safe_load`` (well-formedness); and
- the discoverability cues the RFC-0004 §Outcome calls out are
  present in the body — load triggers ("install", "rebind"),
  cross-references to the kit verbs that effect them, and the
  reciprocal SKILL boundary the AGENT.md vs. SKILL distinction
  hinges on.

Phrasing is the SKILL author's judgment call; the tests pin only
that the load-trigger surface remains discoverable.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "core" / "files" / "skills" / "wiki-agent" / "SKILL.md"


def _split_frontmatter(text: str) -> tuple[str, str]:
    assert text.startswith("---\n"), "SKILL.md must open with a YAML frontmatter fence"
    parts = text.split("---\n", 2)
    assert len(parts) == 3, f"frontmatter fence malformed: got {len(parts)} parts"
    return parts[1], parts[2]


def test_wiki_agent_skill_frontmatter_parses() -> None:
    """The SKILL's YAML frontmatter parses via ``pyyaml.safe_load`` and
    carries the standard ``name``/``description`` shape every SKILL ships."""

    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter_text, _body = _split_frontmatter(text)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict), "frontmatter did not parse as a mapping"
    assert frontmatter.get("name") == "wiki-agent", (
        f"frontmatter name={frontmatter.get('name')!r}, expected 'wiki-agent'"
    )
    description = frontmatter.get("description")
    assert isinstance(description, str) and description.strip(), (
        "frontmatter ``description`` must be a non-empty string"
    )


def test_wiki_agent_skill_names_trigger_phrases() -> None:
    """The SKILL body advertises the load triggers per RFC-0004 §Outcome.

    Pins the discoverability cues at the bareword level — load
    triggers ("install"/"rebind"/"remove"), the kit verbs that effect
    them, and the AGENT.md vs. SKILL boundary that prevents the user
    from mis-routing kit-development subagent edits into vault scope.
    """

    text = SKILL_PATH.read_text(encoding="utf-8")
    _frontmatter_text, body = _split_frontmatter(text)

    # Discoverability cues per RFC-0004 §Outcome: the SKILL exists
    # to help Claude prompt the user about installing or rebinding
    # an agent. Each trigger surface needs to be findable.
    #
    # ``wiki remove agent:<name>`` is intentionally NOT pinned here:
    # the spec calls for it (§Edge cases) but the verb is not in the
    # shipped CLI today — the SKILL talks the user through a manual
    # ``rm -r`` instead, so pinning the verb would freeze prose
    # against a kit-side gap rather than against a shipped contract.
    for cue in (
        "wiki add agent:",
        "wiki schedule install",
        "--agent",
        "rebind",
        "AGENT.md",
    ):
        assert cue in body, (
            f"wiki-agent/SKILL.md does not surface discoverability cue {cue!r}; "
            "RFC-0004 §Outcome calls these out as the kit verbs the SKILL "
            "bridges between"
        )
