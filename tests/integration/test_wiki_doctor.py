"""End-to-end ``wiki doctor`` integration tests (RFC-0001 Task 12).

Drives four vault states through the CLI:

* **clean** — a freshly-initted core-only vault has no issues.
* **page-drift** — a user edit to ``AGENTS.md`` with no pending proposal.
* **pending-proposal** — a ``safe_write`` against an edited file
  triggers the proposal sidecar; doctor surfaces the sidecar path.
* **orphan** — a stray file under ``skills/`` with no journal event.

Vault construction reuses the monkeypatched ``cli._KIT_ROOT`` pattern
from ``test_wiki_init_primitives.py``; doctor is invoked via
``cli.main(["doctor"])`` after ``monkeypatch.chdir(vault)``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.write_helper import safe_write

REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_kit(tmp_path: Path) -> Path:
    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    (kit / "templates").mkdir()
    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: Core-only recipe for wiki doctor tests.\n"
        "primitives:\n"
        "  - core\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


@pytest.fixture
def kit_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    kit = _install_kit(tmp_path)
    monkeypatch.setattr(cli, "_KIT_ROOT", kit)
    return kit


def _init_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal"]) == 0
    return vault


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


def test_doctor_clean_vault_exits_zero(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _init_vault(tmp_path)
    monkeypatch.chdir(vault)
    capsys.readouterr()

    assert cli.main(["doctor"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---------------------------------------------------------------------------
# page-drift
# ---------------------------------------------------------------------------


def test_doctor_reports_page_drift(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _init_vault(tmp_path)
    # Simulate a user edit outside the kit's write path.
    (vault / "AGENTS.md").write_text("user override\n", encoding="utf-8")

    monkeypatch.chdir(vault)
    capsys.readouterr()

    exit_code = cli.main(["doctor"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == cli.DOCTOR_ISSUES_EXIT
    assert out == ["page-drift: AGENTS.md"]


# ---------------------------------------------------------------------------
# pending-proposal
# ---------------------------------------------------------------------------


def test_doctor_reports_pending_proposal(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _init_vault(tmp_path)
    # Drift the file, then drive ``safe_write`` again so it falls through
    # to a ``.proposed`` sidecar + ``page.proposal`` event — the exact
    # state ``wiki doctor`` is designed to surface.
    (vault / "AGENTS.md").write_text("user override\n", encoding="utf-8")
    safe_write(
        Path("AGENTS.md"),
        "kit's next version\n",
        by="core",
        journal_path=_journal_path(vault),
    )
    assert (vault / "AGENTS.md.proposed").is_file()

    monkeypatch.chdir(vault)
    capsys.readouterr()

    exit_code = cli.main(["doctor"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == cli.DOCTOR_ISSUES_EXIT
    # The pending-proposal swallows the page-drift for the same path —
    # doctor reports the actionable thing (resolve the sidecar), not the
    # underlying drift.
    assert "pending-proposal: AGENTS.md.proposed" in out
    assert not any(line.startswith("page-drift:") for line in out)


# ---------------------------------------------------------------------------
# orphan
# ---------------------------------------------------------------------------


def test_doctor_reports_orphan_under_kit_path(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _init_vault(tmp_path)
    stray = vault / "skills" / "rogue" / "SKILL.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("not from any primitive", encoding="utf-8")

    monkeypatch.chdir(vault)
    capsys.readouterr()

    exit_code = cli.main(["doctor"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == cli.DOCTOR_ISSUES_EXIT
    assert "orphan: skills/rogue/SKILL.md" in out


def test_doctor_does_not_flag_user_owned_paths(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _init_vault(tmp_path)
    # A user-created folder outside the kit-owned roots must be invisible.
    (vault / "journal").mkdir()
    (vault / "journal" / "2026-05-16.md").write_text("daily note", encoding="utf-8")

    monkeypatch.chdir(vault)
    capsys.readouterr()

    assert cli.main(["doctor"]) == 0


# ---------------------------------------------------------------------------
# CLI error path
# ---------------------------------------------------------------------------


def test_doctor_refuses_when_cwd_is_not_a_vault(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)

    assert cli.main(["doctor"]) == cli.WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "not a wiki vault" in err
