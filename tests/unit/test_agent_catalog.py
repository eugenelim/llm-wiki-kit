"""CT-25: the default agent catalog ships and is well-formed.

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-25: ``templates/agents/`` contains the eight v1 primitives listed
  in spec §"Default agent catalog"; each has a valid ``primitive.yaml``
  (``kind: agent``, ``version`` matching ``SEMVER_PATTERN``); each
  ``files/.claude/agents/<name>/AGENT.md`` parses as YAML frontmatter
  via ``pyyaml.safe_load``.

The frontmatter parse here is a *verification-side* read per spec
§Invariants — kit runtime still reads zero bytes of ``AGENT.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from llm_wiki_kit.models import SEMVER_PATTERN

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "templates" / "agents"

# Spec §"Default agent catalog" — the v1 set, exhaustive.
EXPECTED_AGENTS: frozenset[str] = frozenset(
    {
        "household-manager",
        "trip-planner",
        "care-coordinator",
        "stakeholder-steward",
        "renewals-watch",
        "customer-listener",
        "personal-coordinator",
        "decision-companion",
    }
)


def _shipped_agent_names() -> set[str]:
    return {p.name for p in AGENTS_DIR.iterdir() if p.is_dir()}


def test_eight_default_agents_present() -> None:
    """CT-25 (third sub-test): the eight names from spec §"Default agent
    catalog" all exist as ``templates/agents/<name>/`` directories;
    spurious entries are flagged."""

    shipped = _shipped_agent_names()
    missing = EXPECTED_AGENTS - shipped
    spurious = shipped - EXPECTED_AGENTS
    assert not missing, f"default agent catalog missing: {sorted(missing)}"
    assert not spurious, (
        f"spurious agent directories — spec §Default agent catalog "
        f"pins eight names exactly: {sorted(spurious)}"
    )


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_catalog_primitive_yaml_well_formed(agent_name: str) -> None:
    """CT-25 (first sub-test): every catalog ``primitive.yaml`` has
    ``kind: agent`` and ``version`` matches ``SEMVER_PATTERN``."""

    manifest_path = AGENTS_DIR / agent_name / "primitive.yaml"
    assert manifest_path.is_file(), f"missing {manifest_path}"

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict), f"{manifest_path} is not a YAML mapping"
    assert manifest.get("name") == agent_name, (
        f"{manifest_path} declares name={manifest.get('name')!r}, expected {agent_name!r}"
    )
    assert manifest.get("kind") == "agent", (
        f"{manifest_path} declares kind={manifest.get('kind')!r}, expected 'agent'"
    )
    version = manifest.get("version")
    assert isinstance(version, str) and re.fullmatch(SEMVER_PATTERN, version), (
        f"{manifest_path} declares version={version!r} which does not match SEMVER_PATTERN"
    )
    description = manifest.get("description")
    assert isinstance(description, str) and description.strip(), (
        f"{manifest_path} declares an empty description"
    )


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_md_frontmatter_parses(agent_name: str) -> None:
    """CT-25 (second sub-test): every ``files/.claude/agents/<name>/AGENT.md``
    parses as YAML frontmatter via ``pyyaml.safe_load`` and carries the
    spec §Inputs convention fields.

    The body below the frontmatter is freeform prose and is *not*
    validated — the kit reads zero bytes of AGENT.md at runtime; this
    test is verification-side only.
    """

    agent_md_path = (
        AGENTS_DIR / agent_name / "files" / ".claude" / "agents" / agent_name / "AGENT.md"
    )
    assert agent_md_path.is_file(), f"missing {agent_md_path}"

    text = agent_md_path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), (
        f"{agent_md_path} must open with a YAML frontmatter fence (`---\\n`)"
    )
    # Split exactly twice: the opening `---`, the frontmatter body, the rest.
    parts = text.split("---\n", 2)
    assert len(parts) == 3, (
        f"{agent_md_path} frontmatter fence is malformed (got {len(parts)} parts)"
    )
    frontmatter_text = parts[1]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict), (
        f"{agent_md_path} frontmatter did not parse as a YAML mapping"
    )

    # Spec §Inputs §"Primitive-author surface": ``name``, ``description``,
    # ``audience`` (``family | work-os | personal | shared``), ``role``,
    # ``tone``, ``knows:`` (list). The kit doesn't validate at runtime —
    # this is a verification-side convention check.
    assert frontmatter.get("name") == agent_name, (
        f"{agent_md_path} frontmatter name={frontmatter.get('name')!r}, expected {agent_name!r}"
    )
    for field in ("description", "audience", "role", "tone"):
        value = frontmatter.get(field)
        assert isinstance(value, str) and value.strip(), (
            f"{agent_md_path} frontmatter is missing or empty field: {field!r}"
        )
    audience = frontmatter["audience"]
    assert audience in {"family", "work-os", "personal", "shared"}, (
        f"{agent_md_path} declares audience={audience!r}; expected one of "
        f"family|work-os|personal|shared"
    )
    knows = frontmatter.get("knows")
    assert isinstance(knows, list), (
        f"{agent_md_path} frontmatter ``knows`` must be a list, got {type(knows).__name__}"
    )
