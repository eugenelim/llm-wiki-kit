"""End-to-end ``wiki outcomes`` integration tests for PR-5.

Exercises the ``wiki outcomes`` subcommand, the ``wiki --help`` epilog,
and the ``wiki init`` post-install message via the same kit-root override
pattern used by ``tests/integration/test_wiki_init_outcomes.py``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from llm_wiki_kit import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"


def _install_kit(
    tmp_path: Path,
    *,
    fixture_operations: tuple[str, ...] = (),
    recipe_primitives: tuple[str, ...] = ("core",),
    extra_operations: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Build a tmp kit with ``core``, optional fixture operations, and a recipe.

    ``extra_operations`` lets callers inject additional synthetic operations
    on-the-fly (for multi-row table tests) without adding fixture files.
    Each key is the operation name; the value is a dict with keys:
    ``verb``, ``skill``, and optionally ``skill_description``.
    """

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    (kit / "templates").mkdir()
    if fixture_operations or extra_operations:
        (kit / "templates" / "operations").mkdir()
        for op_name in fixture_operations:
            shutil.copytree(
                FIXTURE_CATALOG / "operations" / op_name,
                kit / "templates" / "operations" / op_name,
            )
        for op_name, spec in (extra_operations or {}).items():
            op_dir = kit / "templates" / "operations" / op_name
            op_dir.mkdir(parents=True)
            (op_dir / "primitive.yaml").write_text(
                f"name: {op_name}\n"
                f"kind: operation\n"
                f"version: 0.1.0\n"
                f"description: Synthetic fixture operation for PR-5 tests.\n",
                encoding="utf-8",
            )
            verb = spec["verb"]
            skill = spec["skill"]
            (op_dir / "contract.yaml").write_text(
                f"name: {op_name}\n"
                f"description: Synthetic operation for PR-5 tests.\n"
                f"skill: {skill}\n"
                f"outcomes:\n"
                f"  - {verb}\n"
                f"inputs: {{}}\n"
                f"outputs: {{}}\n",
                encoding="utf-8",
            )
            skill_dir = op_dir / "files" / "skills" / skill
            skill_dir.mkdir(parents=True)
            skill_desc = spec.get(
                "skill_description",
                f"Synthetic skill. Trigger on '{verb}' or /{verb}.",
            )
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: >\n  {skill_desc}\n---\n\n# {skill}\n",
                encoding="utf-8",
            )

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    primitives_yaml = "\n".join(f"  - {name}" for name in recipe_primitives)
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: PR-5 outcome-catalog test recipe.\n"
        f"primitives:\n{primitives_yaml}\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


# ---------------------------------------------------------------------------
# AC: "wiki outcomes" — empty vault prints nothing
# ---------------------------------------------------------------------------


def test_wiki_outcomes_empty_vault_prints_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fresh vault with no declared outcomes → wiki outcomes exits 0, stdout empty."""

    kit = _install_kit(tmp_path)  # core only, no operations
    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--no-git", "--recipe", "minimal"], kit_root=kit) == 0

    capsys.readouterr()  # discard init output before capturing outcomes output
    monkeypatch.chdir(vault)
    rc = cli.main(["outcomes"], kit_root=kit)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""


# ---------------------------------------------------------------------------
# AC: "wiki outcomes" — table renders sorted by verb, two-space gutter
# ---------------------------------------------------------------------------


def test_wiki_outcomes_renders_table_sorted_by_verb(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Vault with two declared verbs → sorted table with two-space gutter."""

    # fixture-digest declares "prep-digest"; inject a second operation that
    # declares a verb that sorts before "prep-digest" so ordering is visible.
    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-digest",),
        recipe_primitives=("core", "fixture-digest", "fixture-track"),
        extra_operations={
            "fixture-track": {
                "verb": "log-entry",
                "skill": "fixture-track",
                "skill_description": "Synthetic skill. Trigger on 'log-entry' or /log-entry.",
            }
        },
    )
    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--no-git", "--recipe", "minimal"], kit_root=kit) == 0
    capsys.readouterr()  # discard init output before capturing outcomes output

    monkeypatch.chdir(vault)
    rc = cli.main(["outcomes"], kit_root=kit)
    captured = capsys.readouterr()
    assert rc == 0

    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    # Sorted by verb: "log-entry" < "prep-digest"
    assert len(lines) == 2
    assert lines[0].startswith("log-entry")
    assert lines[1].startswith("prep-digest")

    # Spec §Outputs §4 contracts a two-space gutter between columns.
    # Column widths auto-size to the widest entry; padding fills each
    # column to its width, then a literal two-space sequence separates
    # the next column. The combined "gutter" a casual reader sees can
    # therefore be more than two spaces — that's padding + gutter, not
    # the gutter alone. Pin the bytes of each row against the expected
    # padded form so a regression to one-space or four-space gutters
    # fails loudly.
    # Source column added per ``docs/specs/primitive-sideload/spec.md``
    # §"Outputs ``wiki outcomes`` provenance column" — always-present,
    # bundled rows render ``bundled``. The four-column layout is
    # ``verb  source  op  skill`` with a two-space gutter between
    # auto-sized columns.
    expected_data = [
        ("log-entry", "bundled", "fixture-track", "fixture-track"),
        ("prep-digest", "bundled", "fixture-digest", "fixture-digest"),
    ]
    w_verb = max(len(v) for v, _, _, _ in expected_data)
    w_source = max(len(s) for _, s, _, _ in expected_data)
    w_op = max(len(o) for _, _, o, _ in expected_data)
    for (verb, source, op, skill), line in zip(expected_data, lines, strict=True):
        expected = f"{verb:<{w_verb}}  {source:<{w_source}}  {op:<{w_op}}  {skill}"
        assert line == expected, f"row mismatch — expected exactly {expected!r}, got {line!r}"


# ---------------------------------------------------------------------------
# AC: "wiki outcomes" — outside vault errors
# ---------------------------------------------------------------------------


def test_wiki_outcomes_outside_vault_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Running wiki outcomes outside a vault exits 2 with a clear message."""

    no_vault = tmp_path / "not-a-vault"
    no_vault.mkdir()

    monkeypatch.chdir(no_vault)
    rc = cli.main(["outcomes"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "not a wiki vault" in captured.err


# ---------------------------------------------------------------------------
# AC: "wiki outcomes" — takes no flags
# ---------------------------------------------------------------------------


def test_wiki_outcomes_takes_no_flags(tmp_path: Path) -> None:
    """wiki outcomes --anything errors with argparse's unrecognized-arguments message."""

    result = subprocess.run(
        [sys.executable, "-m", "llm_wiki_kit", "outcomes", "--anything"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode != 0
    # argparse's standard rejection: "error: unrecognized arguments: --anything".
    # Pin both the rejection class AND the offending token so a regression
    # that, e.g., silently accepts an unknown flag is caught.
    assert "unrecognized arguments" in result.stderr
    assert "--anything" in result.stderr


# ---------------------------------------------------------------------------
# AC: "wiki --help" epilog mentions "wiki outcomes"
# ---------------------------------------------------------------------------


def test_wiki_help_epilog_mentions_wiki_outcomes(tmp_path: Path) -> None:
    """wiki --help stdout must contain the literal 'wiki outcomes' reference."""

    result = subprocess.run(
        [sys.executable, "-m", "llm_wiki_kit", "--help"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert "wiki outcomes" in result.stdout


# ---------------------------------------------------------------------------
# AC: "wiki init" post-install message — mentions wiki outcomes when recipe has verbs
# ---------------------------------------------------------------------------


def test_wiki_init_mentions_wiki_outcomes_when_recipe_has_verbs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """wiki init with an outcome-declaring recipe prints the wiki outcomes reference."""

    kit = _install_kit(
        tmp_path,
        fixture_operations=("fixture-digest",),
        recipe_primitives=("core", "fixture-digest"),
    )
    vault = tmp_path / "v"
    rc = cli.main(["init", str(vault), "--no-git", "--recipe", "minimal"], kit_root=kit)
    assert rc == 0
    captured = capsys.readouterr()
    assert "wiki outcomes" in captured.out


# ---------------------------------------------------------------------------
# AC: "wiki init" post-install message — silent when recipe has no verbs
# ---------------------------------------------------------------------------


def test_wiki_init_silent_about_outcomes_when_recipe_has_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """wiki init with a recipe that declares no outcomes does NOT print wiki outcomes."""

    kit = _install_kit(tmp_path)  # core only, no operations with outcomes
    vault = tmp_path / "v"
    rc = cli.main(["init", str(vault), "--no-git", "--recipe", "minimal"], kit_root=kit)
    assert rc == 0
    captured = capsys.readouterr()
    assert "wiki outcomes" not in captured.out
