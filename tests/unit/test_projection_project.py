"""T3 — the ``project()`` orchestrator writes through ``safe_write``.

Exercises the full chain against a ``tmp_path`` vault. Covers spec ACs
1, 4, 6, 8, 10.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import PageProposalEvent, PageWriteEvent
from llm_wiki_kit.projection import PROJECT_VEHICLE, project
from llm_wiki_kit.write_helper import WriteResult

SCHEMA_YAML = """\
required:
  - genre
  - subtype
  - status
  - provenance
  - created
  - modified
genres: [note, record, reference, profile, moc]
subtypes:
  - meeting
  - person
  - research-brief
statuses: [active, draft]
provenance: [extracted, synthesized, mixed]
"""

ARTIFACT = """\
---
genre: record
subtype: meeting
status: active
provenance: extracted
created: 2026-06-24
modified: 2026-06-24
workspaces: [work]
tags: [standup]
---
# Standup 2026-06-24

Body content here.
"""


def _vault(tmp_path: Path) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    for role in ("people", "library", "atlas"):
        (vault / "wiki" / role).mkdir(parents=True)
    (vault / "frontmatter.schema.yaml").write_text(SCHEMA_YAML, encoding="utf-8")
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True)
    journal_path.touch()
    return vault, journal_path


def _artifact(tmp_path: Path, name: str = "standup.md", text: str = ARTIFACT) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _page_writes(journal_path: Path) -> list[PageWriteEvent]:
    return [e for e in read_events(journal_path) if isinstance(e, PageWriteEvent)]


# --- happy path + attribution (AC1, AC10) ----------------------------------


def test_valid_artifact_writes_to_routed_dest_with_one_event(tmp_path: Path) -> None:
    vault, journal_path = _vault(tmp_path)
    artifact = _artifact(tmp_path)

    result = project(artifact, vault, journal_path, at=None, subtype=None, by=None)

    assert result.result is WriteResult.WRITTEN
    assert result.dest_rel == "wiki/library/standup.md"
    assert (vault / "wiki" / "library" / "standup.md").read_text() == ARTIFACT
    writes = _page_writes(journal_path)
    assert len(writes) == 1
    assert writes[0].path == "wiki/library/standup.md"
    assert writes[0].by == PROJECT_VEHICLE  # AC10 — vehicle, not the subtype


def test_by_overrides_attribution(tmp_path: Path) -> None:
    vault, journal_path = _vault(tmp_path)
    artifact = _artifact(tmp_path)
    project(artifact, vault, journal_path, at=None, subtype=None, by="meeting")
    assert _page_writes(journal_path)[0].by == "meeting"


# --- --as override fidelity (AC4) ------------------------------------------


def test_as_override_sets_subtype_and_preserves_other_frontmatter(tmp_path: Path) -> None:
    # Artifact omits subtype; --as supplies it (the foreign-artifact case).
    text = ARTIFACT.replace("subtype: meeting\n", "")
    artifact = _artifact(tmp_path, text=text)
    vault, journal_path = _vault(tmp_path)

    project(artifact, vault, journal_path, at=None, subtype="meeting", by=None)

    from llm_wiki_kit.projection import load_schema, parse_frontmatter

    written = (vault / "wiki" / "library" / "standup.md").read_text()
    fm, body = parse_frontmatter(written)
    assert fm["subtype"] == "meeting"
    # Every other key/value preserved across the re-serialization round-trip.
    assert fm["genre"] == "record"
    assert fm["status"] == "active"
    assert fm["provenance"] == "extracted"
    assert fm["workspaces"] == ["work"]
    assert fm["tags"] == ["standup"]
    # Written-form fidelity (AC4): re-serialization is value-preserving —
    # every non-subtype facet survives the round-trip in the written file,
    # even though canonical YAML may normalize byte layout.
    assert str(fm["created"]) == "2026-06-24"
    assert "subtype: meeting\n" in written
    # Body byte-identical to the input body.
    assert body == "# Standup 2026-06-24\n\nBody content here.\n"
    # sanity: schema still loads (unrelated) — keeps import used
    assert load_schema(vault).subtypes


def test_as_override_replaces_existing_subtype(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)  # declares subtype: meeting, genre: record
    vault, journal_path = _vault(tmp_path)
    project(artifact, vault, journal_path, at=None, subtype="person", by=None)
    # genre (record) drives the folder → library; only the subtype changes.
    written = (vault / "wiki" / "library" / "standup.md").read_text()
    assert "subtype: person" in written
    assert "subtype: meeting" not in written


def test_missing_subtype_without_as_is_rejected(tmp_path: Path) -> None:
    text = ARTIFACT.replace("subtype: meeting\n", "")
    artifact = _artifact(tmp_path, text=text)
    vault, journal_path = _vault(tmp_path)
    with pytest.raises(WikiError, match="missing required facet: 'subtype'"):
        project(artifact, vault, journal_path, at=None, subtype=None, by=None)


# --- drift → proposal (AC8) ------------------------------------------------


def test_drift_routes_to_proposal_not_overwrite(tmp_path: Path) -> None:
    vault, journal_path = _vault(tmp_path)
    artifact = _artifact(tmp_path)
    project(artifact, vault, journal_path, at=None, subtype=None, by=None)

    # Simulate a user edit on disk (drift off the journaled baseline).
    dest = vault / "wiki" / "library" / "standup.md"
    dest.write_text(ARTIFACT + "\nuser edit\n", encoding="utf-8")

    # Re-project different content → safe_write detects drift.
    artifact.write_text(ARTIFACT.replace("Body content", "New body"), encoding="utf-8")
    result = project(artifact, vault, journal_path, at=None, subtype=None, by=None)

    assert result.result is WriteResult.PROPOSAL
    assert (vault / "wiki" / "library" / "standup.md.proposed").is_file()
    assert any(isinstance(e, PageProposalEvent) for e in read_events(journal_path))


# --- validation failure leaves vault byte-unchanged (AC6) ------------------


def test_validation_failure_writes_nothing_and_appends_nothing(tmp_path: Path) -> None:
    vault, journal_path = _vault(tmp_path)
    text = ARTIFACT.replace("genre: record", "genre: invoice")
    artifact = _artifact(tmp_path, text=text)

    before = journal_path.read_text()
    with pytest.raises(WikiError, match="genre 'invoice' is not in"):
        project(artifact, vault, journal_path, at=None, subtype=None, by=None)

    assert journal_path.read_text() == before  # no event appended
    assert not (vault / "wiki" / "library" / "standup.md").exists()
