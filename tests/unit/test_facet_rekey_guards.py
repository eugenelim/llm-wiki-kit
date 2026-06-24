"""Guard tests for the operations-and-search-rekey spec (AC8).

Assert that no vault-side *operational* read/write guidance — the operation
SKILLs, the content-type ingest SKILLs, the core skills, the produced-vault
``AGENTS.md``, and the architecture overview — still references the removed
``wiki/<kind>/`` folders, the removed ``--type`` search flag, the removed page
``type`` field (entity-node stubs and operation-output stubs), or the removed
``frontmatter.schema.yaml`` ``types`` managed region.

These are absence-asserting greps over committed source, kept honest with
**anchored** patterns so they don't false-match legitimate prose (the word
"type" in a sentence, ``journal grep --type`` which filters journal *events*,
``asset_type``, the ``*_status`` lifecycle fields, or the
``<!-- BEGIN MANAGED: content-types -->`` region marker). The regenerated
``conflict-pending`` example vault is intentionally *not* scanned here — it is
covered by ``starters/regenerate.py --check`` and its hand-authored seed pages
still carry the ``type:`` frontmatter whose value-faceting
``role-folders-and-containers`` deferred. See
``docs/specs/operations-and-search-rekey/spec.md`` §Acceptance Criteria.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The directories/files that carry vault-side operational read/write guidance.
_SCAN_GLOBS = (
    "templates/operations/**/*",
    "templates/content-types/*/files/skills/**/*",
    "core/files/skills/**/*",
)
_SCAN_FILES = (
    "core/files/AGENTS.md",
    "docs/architecture/overview.md",
)

# Removed entity-kind / content-type-kind folders, plus the illustrative ones
# the core ingest diagram used (`health`, `finances`) and the lifecycle trip
# subfolders. Valid role folders (people, library, atlas, efforts) and
# `efforts/projects/` are deliberately absent so they never match.
_REMOVED_FOLDER = re.compile(
    r"wiki/(?:customers|customer-feedback|vendors|food|domains|medical|meetings"
    r"|actions|decisions|interviews|receipts|tax|stakeholder-updates"
    r"|vendor-contracts|health|finances|projects)/|trips/(?:upcoming|past)/"
)

# Operation-output stubs sit column-0 inside ```yaml fences.
_OUTPUT_STUB = re.compile(
    r"^type: (?:digest|status-synthesis|action-rollup|follow-up-report"
    r"|renewal-reminders|meal-plan|onboarding-pack|stakeholder-map"
    r"|medical-summary)\b"
)

# Entity-node stubs are backtick-wrapped, mid-sentence prose.
_NODE_STUB = re.compile(r"`type: (?:person|customer|vendor|organization|project)`")

_TYPES_REGION = re.compile(r"managed `types` region")


def _scan_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in _SCAN_GLOBS:
        paths.extend(
            p for p in REPO_ROOT.glob(pattern) if p.is_file() and p.suffix in {".md", ".yaml"}
        )
    for rel in _SCAN_FILES:
        p = REPO_ROOT / rel
        if p.is_file():
            paths.append(p)
    return paths


def _is_search_type_flag(line: str) -> bool:
    """True iff ``line`` uses the removed ``--type`` *search* flag.

    Excludes ``wiki journal grep --type`` (a journal *event* filter, retained)
    and its ``--type page.<event>`` arguments.
    """

    if "--type" not in line:
        return False
    if "journal grep" in line or "--type page." in line:
        return False
    return True


@pytest.fixture(scope="module")
def scanned() -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in _scan_paths()]


def test_scan_set_is_non_empty(scanned: list[tuple[Path, str]]) -> None:
    """Guard against a glob typo silently scanning nothing."""

    assert len(scanned) > 20


def test_no_removed_folder_references(scanned: list[tuple[Path, str]]) -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for path, text in scanned
        for n, line in enumerate(text.splitlines(), 1)
        if _REMOVED_FOLDER.search(line)
    ]
    assert not offenders, "removed wiki/<kind>/ folder references remain:\n" + "\n".join(offenders)


def test_no_search_type_flag(scanned: list[tuple[Path, str]]) -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for path, text in scanned
        for n, line in enumerate(text.splitlines(), 1)
        if _is_search_type_flag(line)
    ]
    assert not offenders, "removed --type search flag remains:\n" + "\n".join(offenders)


def test_no_output_type_stub(scanned: list[tuple[Path, str]]) -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for path, text in scanned
        for n, line in enumerate(text.splitlines(), 1)
        if _OUTPUT_STUB.match(line)
    ]
    assert not offenders, "operation-output type: stubs remain (use genre/subtype):\n" + "\n".join(
        offenders
    )


def test_no_entity_node_type_stub(scanned: list[tuple[Path, str]]) -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for path, text in scanned
        for n, line in enumerate(text.splitlines(), 1)
        if _NODE_STUB.search(line)
    ]
    assert not offenders, "entity-node `type:` stubs remain (use genre: profile):\n" + "\n".join(
        offenders
    )


def test_no_types_region_reference(scanned: list[tuple[Path, str]]) -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for path, text in scanned
        for n, line in enumerate(text.splitlines(), 1)
        if _TYPES_REGION.search(line)
    ]
    assert not offenders, "stale `managed types region` references remain:\n" + "\n".join(offenders)
