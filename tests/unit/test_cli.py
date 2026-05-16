"""Tests for the ``wiki`` CLI skeleton.

These tests assert the shape of the dispatcher — every subcommand listed in
RFC-0001 is reachable, ``--help`` works, and the stub handlers exit with
the expected sentinel status. They don't assert anything about behavior,
because there isn't any yet.
"""

from __future__ import annotations

import pytest

from llm_wiki_kit import __version__
from llm_wiki_kit.cli import NOT_IMPLEMENTED_EXIT, build_parser, main

SUBCOMMANDS_WITH_ARGS: list[list[str]] = [
    # ``init`` graduated from stub to real handler in Task 10; ``add``
    # and ``doctor`` graduated in Task 12. Both have their own
    # integration suites under ``tests/integration/``.
    ["upgrade"],
    ["upgrade", "--primitive", "people"],
    ["ingest", "/tmp/transcript.txt"],
    ["run", "weekly-digest"],
    ["research", "what is rust"],
    ["search", "stakeholder"],
    ["journal", "tail"],
    ["journal", "tail", "-n", "20"],
    ["journal", "grep", "ingest"],
    ["journal", "explain", "abc123"],
]


def test_top_level_help_lists_all_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for cmd in (
        "init",
        "add",
        "upgrade",
        "doctor",
        "ingest",
        "run",
        "research",
        "search",
        "journal",
    ):
        assert cmd in out, f"top-level help missing subcommand {cmd!r}"


def test_version_flag_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code != 0


@pytest.mark.parametrize("argv", SUBCOMMANDS_WITH_ARGS, ids=lambda a: " ".join(a))
def test_subcommand_stub_returns_not_implemented(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == NOT_IMPLEMENTED_EXIT
    err = capsys.readouterr().err
    assert "not yet implemented" in err


@pytest.mark.parametrize(
    "subcommand",
    ["init", "add", "upgrade", "doctor", "ingest", "run", "research", "search", "journal"],
)
def test_each_subcommand_has_help(subcommand: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args([subcommand, "--help"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out  # non-empty help text


@pytest.mark.parametrize("subcommand", ["tail", "grep", "explain"])
def test_journal_subcommand_has_help(subcommand: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["journal", subcommand, "--help"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out


def test_init_requires_recipe() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["init", "/tmp/vault"])


def test_journal_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["journal"])
