"""Wheel-acceptance: outcome verbs appear in installed SKILL.md descriptions.

Spec: ``docs/specs/outcome-named-entry-points/spec.md`` §Acceptance
criterion "Wheel-acceptance SKILL-fragment gate". Plan: PR-9 §2.

Builds the kit wheel, installs it into a tmp prefix (mirroring
``test_wheel_install_end_to_end``), walks the installed
``_assets/templates/operations/*/contract.yaml`` tree, and asserts
that for every declared outcome verb, the matching SKILL.md
frontmatter ``description:`` contains the verb as a whole word.
Pins that the wheel-bundling spec (``docs/specs/wheel-bundled-assets/``)
hasn't silently dropped SKILL files between source and wheel — a
regression here would mean an end-user install where the
discovery-by-description surface is broken even though every other
test on the source tree passes.

Marked ``@pytest.mark.slow`` because it consumes ``built_wheel`` and
runs ``pip install`` in a subprocess; CI's default
``pytest -m 'not slow'`` skips it, the wheel-acceptance workflow
gates on it.

The validation is **deliberately re-implemented** against the
installed asset tree — it does not call the production
``install.validate_outcome_skill_fragments`` helper that runs at
``wiki init`` time. Sharing the production validator would let a
wheel-bundling regression that drops SKILL.md files mask itself by
sharing the same code path.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.slow

_BUNDLE_PREFIX = "llm_wiki_kit/_assets"


def _load_contract(contract_path: Path) -> dict[str, object]:
    """Parse ``contract.yaml`` into a dict; surface raw YAML errors loudly."""

    text = contract_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        pytest.fail(
            f"contract.yaml at {contract_path} did not parse to a mapping; "
            f"got {type(data).__name__}"
        )
    return data


def _skill_description(skill_md_path: Path) -> str:
    """Return the SKILL.md frontmatter ``description:`` string.

    Fails the test loudly if the SKILL.md is missing or has no
    parseable frontmatter — those failures are exactly what the
    wheel-acceptance gate exists to catch.
    """

    if not skill_md_path.is_file():
        pytest.fail(f"SKILL.md missing from installed wheel: {skill_md_path}")
    text = skill_md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        pytest.fail(f"SKILL.md at {skill_md_path} has no YAML frontmatter")
    meta = yaml.safe_load(parts[1]) or {}
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        pytest.fail(
            f"SKILL.md at {skill_md_path} frontmatter has no non-empty `description:` field"
        )
    return description


def test_installed_wheel_skill_fragments_cover_every_declared_verb(
    built_wheel: Path, tmp_path: Path
) -> None:
    prefix = tmp_path / "prefix"
    prefix.mkdir()

    # ``--no-deps`` + ``--no-index`` mirrors
    # ``test_wheel_install_end_to_end``: install closed against the
    # network, no dependency churn, fully reproducible.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(prefix),
            "--no-deps",
            "--no-index",
            "--no-cache-dir",
            str(built_wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    operations_dir = prefix / _BUNDLE_PREFIX / "templates" / "operations"
    assert operations_dir.is_dir(), f"installed wheel has no operations tree at {operations_dir}"

    contracts_with_outcomes: list[tuple[str, list[str], Path, Path]] = []
    for op_dir in sorted(operations_dir.iterdir()):
        if not op_dir.is_dir():
            continue
        contract_path = op_dir / "contract.yaml"
        if not contract_path.is_file():
            continue
        contract = _load_contract(contract_path)
        raw_outcomes = contract.get("outcomes")
        # Absent / empty `outcomes:` is the normal case for an
        # operation that ships no outcome verbs — skip silently.
        # But a *malformed* declaration (scalar, non-string entries)
        # is exactly the wheel-bundling regression this gate exists
        # to catch, so fail loudly. The production `OperationContract`
        # Pydantic model would reject these at catalog-load time, but
        # this gate walks raw YAML in the installed wheel without
        # Pydantic in the loop — so it's the last line of defense.
        if raw_outcomes is None or raw_outcomes == []:
            continue
        if not isinstance(raw_outcomes, list):
            pytest.fail(
                f"contract at {contract_path} has non-list `outcomes:` "
                f"({type(raw_outcomes).__name__}); expected a list of strings."
            )
        non_strings = [v for v in raw_outcomes if not isinstance(v, str)]
        if non_strings:
            pytest.fail(
                f"contract at {contract_path} has non-string `outcomes:` "
                f"entries: {non_strings!r}; expected ASCII verb strings."
            )
        # ``skill:`` defaults to the operation's ``name:`` per
        # ``install._resolved_skill_name``; the same fallback here so
        # an operation that omits ``skill:`` still resolves cleanly.
        op_name = contract.get("name")
        if not isinstance(op_name, str):
            pytest.fail(f"contract at {contract_path} has no string `name:` field")
        skill_name = contract.get("skill") or op_name
        if not isinstance(skill_name, str):
            pytest.fail(f"contract at {contract_path} has non-string `skill:` field")
        skill_md_path = op_dir / "files" / "skills" / skill_name / "SKILL.md"
        contracts_with_outcomes.append((op_name, list(raw_outcomes), contract_path, skill_md_path))

    assert contracts_with_outcomes, (
        "installed wheel has no operations with declared `outcomes:` — "
        "either the spec's catalog-rollout contract has regressed, or "
        "wheel-bundling dropped the contract.yaml files for every "
        "operation. See `docs/specs/outcome-named-entry-points/spec.md` "
        "§Three concrete worked examples for the verbs that must be "
        "present (digest, plan-meals, refresh-stakeholders)."
    )

    failures: list[str] = []
    for op_name, verbs, contract_path, skill_md_path in contracts_with_outcomes:
        description = _skill_description(skill_md_path)
        for verb in verbs:
            # Verbs are ASCII-only by spec §Inputs §2 rule 2, so
            # Python's default-mode `\b` is safe here. Matches the
            # production validator's regex shape
            # (``install.validate_outcome_skill_fragments``) — but
            # re-implemented independently so a wheel-bundling
            # regression isn't masked by code reuse.
            #
            # Inherits the same loose-boundary caveat as the
            # production validator: `\b` fires at hyphen-to-letter
            # transitions, so ``prep-digest`` would technically match
            # inside ``re-prep-digest``. No realistic SKILL.md
            # description triggers this; a future spec amendment can
            # tighten to ``(?<![\w-])`` / ``(?![\w-])`` in *both*
            # places if needed.
            if not re.search(rf"\b{re.escape(verb)}\b", description):
                failures.append(
                    f"operation {op_name!r}: verb {verb!r} missing from "
                    f"SKILL.md description.\n"
                    f"  contract.yaml: {contract_path}\n"
                    f"  SKILL.md:      {skill_md_path}"
                )

    if failures:
        joined = "\n".join(failures)
        pytest.fail(f"installed wheel has {len(failures)} SKILL-fragment violation(s):\n{joined}")
