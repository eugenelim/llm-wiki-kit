"""Unit tests for the ``wiki-bootstrap`` vault-side artifacts.

Spec: ``docs/specs/wiki-bootstrap/spec.md``
Plan: ``docs/specs/wiki-bootstrap/plan.md`` § T3

Covers ACs 1, 2, 3 — the static artifacts shipped under
``core/files/`` that ``wiki init`` copies into every vault. No
fixtures, no subprocesses; pure file reads.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_FILES = REPO_ROOT / "core" / "files"
SKILL_PATH = CORE_FILES / "skills" / "wiki-bootstrap" / "SKILL.md"
AGENTS_MD = CORE_FILES / "AGENTS.md"
GITIGNORE = CORE_FILES / ".gitignore"
SKILLS_DIR = CORE_FILES / "skills"

CANONICAL_TRIGGER_PHRASES: tuple[str, ...] = (
    "I just made a new vault",
    "help me get started",
    "first time using this vault",
    "what should I do first",
    "walk me through this vault",
)

AGENTS_BULLET_SUBSTRING = (
    "**`wiki-bootstrap`** — first-run wizard for fresh vaults. "
    "Loads on any onboarding-shaped phrase; short-circuits to a brief "
    "no-op message if the vault is already bootstrapped."
)


def _frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter from a SKILL.md file."""

    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"{path} missing YAML frontmatter delimiters"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{path}: frontmatter must be a YAML mapping"
    return data


def test_skill_md_frontmatter_well_formed() -> None:
    """AC 1 — SKILL has valid YAML frontmatter with the required keys."""

    fm = _frontmatter(SKILL_PATH)
    assert fm["name"] == "wiki-bootstrap"
    assert fm["license"] == "MIT"
    description = fm["description"]
    assert isinstance(description, str)
    assert description.strip(), "description must be non-empty"


@pytest.mark.parametrize("phrase", CANONICAL_TRIGGER_PHRASES)
def test_skill_md_description_contains_trigger_phrases(phrase: str) -> None:
    """AC 1 (cont.) — every canonical trigger phrase appears in the description."""

    description = _frontmatter(SKILL_PATH)["description"]
    pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
    assert pattern.search(description), (
        f"trigger phrase {phrase!r} not found in SKILL description: {description!r}"
    )


def test_agents_md_contains_wiki_bootstrap_bullet() -> None:
    """AC 2 — AGENTS.md surfaces wiki-bootstrap with the pinned wording."""

    text = AGENTS_MD.read_text(encoding="utf-8")
    # Normalise leading bullet prefix + intra-line whitespace runs so a
    # gentle line-wrap doesn't fail the substring check.
    normalised = re.sub(r"\s+", " ", text)
    assert AGENTS_BULLET_SUBSTRING in normalised, (
        "wiki-bootstrap bullet missing or rephrased; spec §Inputs §2 pins the wording"
    )


def test_agents_md_intro_is_count_free() -> None:
    """AC 2 (cont.) — neither digit-form nor word-form of a baseline-skill count survives."""

    text = AGENTS_MD.read_text(encoding="utf-8")
    digit_re = re.compile(r"\b\d+[\s\-]+baseline[\s\-]+skills?\b", re.IGNORECASE)
    word_re = re.compile(
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty)[\s\-]+baseline[\s\-]+skills?\b",
        re.IGNORECASE,
    )
    assert not digit_re.search(text), (
        "AGENTS.md intro still references a digit-form skill count; rephrase to count-free form"
    )
    assert not word_re.search(text), (
        "AGENTS.md intro still references a word-form skill count; rephrase to count-free form"
    )


def test_agents_md_lists_every_baseline_skill() -> None:
    """AC 2 (cont.) — every shipped SKILL directory appears as a bullet."""

    text = AGENTS_MD.read_text(encoding="utf-8")
    # Pin the section heading (catches a silent rename of "Available skills").
    assert "## Available skills" in text, (
        "AGENTS.md missing the `## Available skills` section heading"
    )
    # Slice the section content (from the heading to the next `## ` heading).
    after_heading = text.split("## Available skills", 1)[1]
    next_heading_match = re.search(r"\n##\s", after_heading)
    section = after_heading[: next_heading_match.start()] if next_heading_match else after_heading

    missing = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        bullet = f"**`{skill_dir.name}`**"
        if bullet not in section:
            missing.append(skill_dir.name)
    assert not missing, f"AGENTS.md `## Available skills` section missing bullets for: {missing!r}"


def test_gitignore_contains_wiki_bootstrap_entry() -> None:
    """AC 3 — the marker is per-machine SKILL scratch and stays out of git."""

    lines = {line.rstrip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}
    assert ".wiki.bootstrap" in lines, (
        "core/files/.gitignore missing `.wiki.bootstrap` line; "
        "spec §Inputs §3 requires the marker be gitignored"
    )


def test_skill_md_pins_failure_mode_prose() -> None:
    """Spec §Error cases — the two read-side failure paths must stay documented.

    The eval suite covers the happy / re-run / no-verbs / malformed /
    unreadable-marker branches end-to-end. The two read-side error
    paths (journal missing or unreadable; ``wiki outcomes`` exits
    non-zero) cost a full eval spawn each to cover live and are
    deferred there per spec §Risks. This unit test scopes the prose
    pin to each failure branch specifically: a future edit that
    drops the doctor-pointer from one branch fails CI on the
    branch-specific assertion, not on a global substring match
    that would still pass because the same string appears elsewhere
    in the 200-line SKILL.
    """

    text = SKILL_PATH.read_text(encoding="utf-8")

    # Journal-missing branch: locate the surrounding block by its
    # leading anchor (the SKILL prose at SKILL.md Step 2) and assert
    # the doctor-pointer is *inside* that block. Failure mode prose
    # appears between "If the journal is missing or unreadable" and
    # the next section break.
    journal_anchor = "If the journal is missing or unreadable"
    assert journal_anchor in text, (
        f"SKILL prose missing journal failure-mode anchor: {journal_anchor!r}"
    )
    journal_branch = text.split(journal_anchor, 1)[1]
    journal_section = journal_branch.split("\n\n##", 1)[0]
    assert "wiki doctor" in journal_section, (
        "SKILL journal-missing branch dropped the `wiki doctor` pointer"
    )

    # `wiki outcomes`-error branch: same shape. Anchor is the
    # "If `wiki outcomes` exits non-zero" prose at SKILL.md Step 4.
    outcomes_anchor = "If `wiki outcomes` exits non-zero"
    assert outcomes_anchor in text, (
        f"SKILL prose missing wiki-outcomes failure-mode anchor: {outcomes_anchor!r}"
    )
    outcomes_branch = text.split(outcomes_anchor, 1)[1]
    outcomes_section = outcomes_branch.split("\n\n##", 1)[0]
    assert "wiki doctor" in outcomes_section, (
        "SKILL wiki-outcomes-error branch dropped the `wiki doctor` pointer"
    )


def test_trigger_phrases_unique_across_existing_skills() -> None:
    """Plan T3.7 — every canonical trigger phrase is unique to wiki-bootstrap.

    Catches a future SKILL whose description coincidentally contains
    one of the onboarding phrases. CI gate.
    """

    collisions: list[tuple[str, str]] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        if skill_md.parent.name == "wiki-bootstrap":
            continue
        description = _frontmatter(skill_md).get("description", "")
        for phrase in CANONICAL_TRIGGER_PHRASES:
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            if pattern.search(description):
                collisions.append((skill_md.parent.name, phrase))
    assert not collisions, f"trigger-phrase collisions with other SKILLs: {collisions!r}"
