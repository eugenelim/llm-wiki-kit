"""T4 — ``wiki project`` end-to-end through the real CLI verb.

Drives ``cli.main(["project", ...])`` against a hand-seeded vault (a
journal, the four role folders, and a populated ``frontmatter.schema.yaml``)
so the verb's argparse wiring, the ``_cmd_project`` handler, ``projection``,
``safe_write``, and the journal are exercised together. Covers spec ACs
1-9 at the CLI surface.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.journal import read_events
from llm_wiki_kit.models import PageProposalEvent, PageWriteEvent

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
statuses: [active, draft]
provenance: [extracted, synthesized, mixed]
"""

ARTIFACT = """\
---
genre: profile
subtype: person
status: active
provenance: extracted
created: 2026-06-24
modified: 2026-06-24
---
# Jane Doe

A person node.
"""


def _journal(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    v = tmp_path / "vault"
    for role in ("people", "library", "atlas", "efforts"):
        (v / "wiki" / role).mkdir(parents=True)
    (v / "frontmatter.schema.yaml").write_text(SCHEMA_YAML, encoding="utf-8")
    jp = _journal(v)
    jp.parent.mkdir(parents=True)
    jp.touch()
    monkeypatch.chdir(v)
    return v


def _artifact(tmp_path: Path, name: str = "jane-doe.md", text: str = ARTIFACT) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- happy path (AC1) -------------------------------------------------------


def test_project_routes_by_genre(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = _artifact(tmp_path)
    assert cli.main(["project", str(artifact)]) == 0
    assert (vault / "wiki" / "people" / "jane-doe.md").read_text() == ARTIFACT
    assert "wrote wiki/people/jane-doe.md" in capsys.readouterr().out
    writes = [e for e in read_events(_journal(vault)) if isinstance(e, PageWriteEvent)]
    assert len(writes) == 1 and writes[0].by == "wiki-project"


# --- --at override (AC2) ----------------------------------------------------


def test_project_at_override(vault: Path, tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    assert cli.main(["project", str(artifact), "--at", "wiki/efforts/team.md"]) == 0
    assert (vault / "wiki" / "efforts" / "team.md").is_file()


# --- --as / --by argparse wiring at the CLI surface (AC4, AC10) -------------


def test_project_as_override_through_cli(vault: Path, tmp_path: Path) -> None:
    # Exercises the --as → dest="as_subtype" → project(subtype=...) wiring that
    # the orchestrator-level test bypasses.
    artifact = _artifact(tmp_path, text=ARTIFACT.replace("subtype: person\n", ""))
    assert cli.main(["project", str(artifact), "--as", "person"]) == 0
    assert "subtype: person\n" in (vault / "wiki" / "people" / "jane-doe.md").read_text()


def test_project_by_override_through_cli(vault: Path, tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    assert cli.main(["project", str(artifact), "--by", "ingest-person"]) == 0
    writes = [e for e in read_events(_journal(vault)) if isinstance(e, PageWriteEvent)]
    assert writes[0].by == "ingest-person"


# --- drift → proposal (AC8) -------------------------------------------------


def test_project_drift_writes_proposal(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = _artifact(tmp_path)
    cli.main(["project", str(artifact)])
    (vault / "wiki" / "people" / "jane-doe.md").write_text(ARTIFACT + "\nedit\n")
    artifact.write_text(ARTIFACT.replace("A person node.", "Changed."))
    assert cli.main(["project", str(artifact)]) == 0
    assert (vault / "wiki" / "people" / "jane-doe.md.proposed").is_file()
    assert "proposal at wiki/people/jane-doe.md.proposed" in capsys.readouterr().out
    assert any(isinstance(e, PageProposalEvent) for e in read_events(_journal(vault)))


# --- rejection paths leave the vault byte-unchanged (AC3-AC9) ---------------


def _assert_rejected(
    vault: Path, argv: list[str], match: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # ``cli.main`` catches ``WikiError`` and returns a non-zero exit code
    # (printing the one-line reason to stderr), so we assert on the code +
    # message + a byte-unchanged journal, not on a raised exception.
    before = _journal(vault).read_text()
    assert cli.main(argv) != 0
    assert re.search(match, capsys.readouterr().err)
    assert _journal(vault).read_text() == before  # no event appended


def test_reject_bad_genre(vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    art = _artifact(tmp_path, text=ARTIFACT.replace("genre: profile", "genre: invoice"))
    _assert_rejected(vault, ["project", str(art)], "genre 'invoice' is not in", capsys)


def test_reject_unknown_subtype(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    art = _artifact(tmp_path, text=ARTIFACT.replace("subtype: person", "subtype: alien"))
    _assert_rejected(vault, ["project", str(art)], "subtype 'alien' is not in", capsys)


def test_reject_missing_facet(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    art = _artifact(tmp_path, text=ARTIFACT.replace("status: active\n", ""))
    _assert_rejected(vault, ["project", str(art)], "missing required facet: 'status'", capsys)


def test_reject_malformed_frontmatter(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    art = _artifact(tmp_path, text="# no frontmatter here\n")
    _assert_rejected(vault, ["project", str(art)], "no YAML frontmatter", capsys)


def test_reject_unsafe_yaml_tag(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = "---\ngenre: !!python/object/apply:os.system ['x']\n---\nbody\n"
    art = _artifact(tmp_path, text=bad)
    _assert_rejected(vault, ["project", str(art)], "not valid YAML", capsys)


def test_reject_at_escape(vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    art = _artifact(tmp_path)
    _assert_rejected(
        vault, ["project", str(art), "--at", "../../etc/x.md"], "must resolve under", capsys
    )


def test_reject_missing_role_folder(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # atlas exists but remove it to force the missing-folder branch.
    (vault / "wiki" / "atlas").rmdir()
    art = _artifact(tmp_path, text=ARTIFACT.replace("genre: profile", "genre: moc"))
    _assert_rejected(vault, ["project", str(art)], "no wiki/atlas/ role folder", capsys)


def test_reject_artifact_not_found(vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _assert_rejected(vault, ["project", "does-not-exist.md"], "artifact not found", capsys)
