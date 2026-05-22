"""Integration tests for PR-6: dynamic ``wiki <verb>`` alias dispatcher.

Covers spec §Outputs §1 (CLI alias resolution) and the dispatcher logic
added to ``cli.main``. Uses the same tmp-kit pattern as
``test_wiki_init_outcomes.py``: a tmp kit is built from the fixture
catalog and a minimal recipe; the vault is seeded either via
``cli.main(["init", ...])`` or by appending journal events directly.

All tests are non-slow (no wheel build required).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit import cli
from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    OperationRunEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "outcome-catalog"

# -------------------------------------------------------------------------
# Shared helpers
# -------------------------------------------------------------------------

_FIXTURE_DIGEST_CONTRACT = """\
name: fixture-digest
description: Test operation for verb-dispatch tests; declares prep-digest verb.
skill: fixture-digest
outcomes:
  - prep-digest
inputs: {}
outputs: {}
"""


def _build_kit(
    tmp_path: Path,
    *,
    include_fixture_digest: bool = True,
) -> Path:
    """Build a minimal tmp kit with optional ``fixture-digest`` operation."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    templates = kit / "templates"
    templates.mkdir()

    if include_fixture_digest:
        op_dir = templates / "operations" / "fixture-digest"
        op_dir.mkdir(parents=True)
        (op_dir / "contract.yaml").write_text(_FIXTURE_DIGEST_CONTRACT, encoding="utf-8")
        (op_dir / "primitive.yaml").write_text(
            "name: fixture-digest\nkind: operation\nversion: 0.1.0\ndescription: PR-6 test op.\n",
            encoding="utf-8",
        )
        skills_dir = op_dir / "files" / "skills" / "fixture-digest"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\n"
            "name: fixture-digest\n"
            "description: >-\n"
            "  Produce a fixture digest. Reach for this skill when the user says\n"
            '  "prep-digest" or invokes /prep-digest. Used by PR-6 tests.\n'
            "---\n\n"
            "# fixture-digest\n\n"
            "Synthetic fixture for PR-6 verb-dispatch tests.\n",
            encoding="utf-8",
        )

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    primitives_line = "  - core\n  - fixture-digest" if include_fixture_digest else "  - core"
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: PR-6 verb-dispatch test recipe.\n"
        f"primitives:\n{primitives_line}\n"
        "variables:\n  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


def _seed_vault_from_events(tmp_path: Path, kit: Path) -> Path:
    """Build a vault with ``fixture-digest`` installed via direct journal events.

    Faster than running ``wiki init``; use when the test only needs a
    vault with the primitive registered in the journal.
    """
    vault = tmp_path / "vault"
    (vault / ".wiki.journal").mkdir(parents=True)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=now, by="wiki-init", vault_name="vault", recipe="minimal"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=now, by="wiki-init", primitive="fixture-digest", version="0.1.0"
        ),
    )
    return vault


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _run_events(vault: Path) -> list[OperationRunEvent]:
    return [e for e in read_events(_journal_path(vault)) if isinstance(e, OperationRunEvent)]


# -------------------------------------------------------------------------
# AC: "CLI alias" — wiki <verb> dispatches to the same _cmd_run path
# -------------------------------------------------------------------------


def test_wiki_verb_dispatches_to_wiki_run_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki prep-digest`` reaches the same ``_cmd_run`` path as
    ``wiki run fixture-digest``.

    Pins spec AC "CLI alias". Both invocations must produce an
    ``OperationRunEvent`` for ``fixture-digest``.
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    # Verb form
    rc = cli.main(["prep-digest"], kit_root=kit)
    assert rc == 0
    events_verb = _run_events(vault)
    assert len(events_verb) == 1
    assert events_verb[0].operation == "fixture-digest"
    assert events_verb[0].status == "dispatched"

    # run form — should produce a second event with the same operation
    rc = cli.main(["run", "fixture-digest"], kit_root=kit)
    assert rc == 0
    events_run = _run_events(vault)
    assert len(events_run) == 2
    assert events_run[1].operation == "fixture-digest"
    assert events_run[1].status == "dispatched"


# -------------------------------------------------------------------------
# AC: "Argument forwarding"
# -------------------------------------------------------------------------


def test_wiki_verb_argument_forwarding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki prep-digest --window=2026-W18`` and the equivalent ``wiki run``
    reach ``_cmd_run`` with structurally equal ``op_args`` namespaces.

    Pins spec AC "Argument forwarding". We capture what ``_cmd_run`` receives
    on both paths by monkeypatching ``cli._cmd_run`` to record the
    ``args.op_args`` and ``args.operation`` values before returning 0.
    """
    import llm_wiki_kit.cli as cli_mod

    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    captured: list[tuple[str, list[str]]] = []

    import argparse

    original_cmd_run = cli_mod._cmd_run

    def _capturing_cmd_run(args: argparse.Namespace) -> int:
        captured.append(
            (
                getattr(args, "operation", ""),
                list(getattr(args, "op_args", []) or []),
            )
        )
        return original_cmd_run(args)

    monkeypatch.setattr(cli_mod, "_cmd_run", _capturing_cmd_run)

    cli.main(["prep-digest", "--window=2026-W18"], kit_root=kit)
    cli.main(["run", "fixture-digest", "--window=2026-W18"], kit_root=kit)
    capsys.readouterr()  # discard output

    assert len(captured) == 2, f"expected 2 _cmd_run calls, got {len(captured)}: {captured}"
    verb_op, verb_op_args = captured[0]
    run_op, run_op_args = captured[1]

    # Both must land in _cmd_run with the same operation and op_args.
    assert verb_op == run_op == "fixture-digest"
    assert verb_op_args == run_op_args, (
        f"op_args mismatch: verb={verb_op_args!r}, run={run_op_args!r}"
    )


# -------------------------------------------------------------------------
# AC: "wiki <verb> --help"
# -------------------------------------------------------------------------


def test_wiki_verb_help_preamble_then_run_help_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki prep-digest --help`` exits 0 and stdout starts with the alias
    preamble followed by the ``wiki run``-help body.

    Pins spec AC "``wiki <verb> --help``".
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    rc = cli.main(["prep-digest", "--help"], kit_root=kit)
    assert rc == 0
    out = capsys.readouterr().out
    # The alias preamble must be present.
    assert "(alias for `wiki run fixture-digest`)" in out
    # The wiki-run help body must follow — assert the well-known "Run a
    # named operation." string from the run subparser's help attribute.
    assert "Run a named operation." in out or "operation" in out.lower()


# -------------------------------------------------------------------------
# AC: "CLI alias outside vault"
# -------------------------------------------------------------------------


def test_wiki_verb_invalid_choice_outside_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki prep-digest`` outside a vault exits 2 with the vault-scoped
    error message.

    Pins spec AC "CLI alias outside vault" and §Outputs §1 contract.
    """
    monkeypatch.chdir(tmp_path)  # no .wiki.journal here

    rc = cli.main(["prep-digest"], kit_root=None)
    assert rc == cli.WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "outcome verbs are vault-scoped" in err
    assert "wiki run <operation>" in err


# -------------------------------------------------------------------------
# AC: non-verb-shaped token outside vault falls through to argparse
# -------------------------------------------------------------------------


def test_wiki_typo_outside_vault_falls_through_to_argparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki not_a_verb`` (underscore — fails kebab regex) outside a vault
    gets argparse's standard "invalid choice" error, NOT the vault-scoped
    WikiError.

    Pins that the dispatcher only intercepts verb-shaped tokens; manifestly
    non-verb input keeps argparse's native error path.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["not_a_verb"], kit_root=None)
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    # argparse "invalid choice" present; vault-scoped message absent.
    assert "invalid choice" in err
    assert "outcome verbs are vault-scoped" not in err


# -------------------------------------------------------------------------
# AC: --verbose must precede the verb (mirrors _cmd_run constraint)
# -------------------------------------------------------------------------


def test_wiki_verbose_position_invariant_for_verbs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--verbose`` must precede the outcome verb token.

    ``wiki --verbose prep-digest`` succeeds (or at least reaches ``_cmd_run``).
    ``wiki prep-digest --verbose`` — the post-verb form — forwards ``--verbose``
    into ``op_args`` (argparse.REMAINDER capture), which _cmd_run passes to
    ``dispatch`` as an unknown arg. The test asserts this form still reaches
    the dispatch path (exit 0 is acceptable) OR exits with a clear error that
    does NOT mention "vault-scoped" (it should be a dispatch-level rejection,
    not a CLI-routing failure). Pins that the pre-verb form reaches the run
    handler.
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    # Pre-verb --verbose must reach _cmd_run successfully.
    rc_pre = cli.main(["--verbose", "prep-digest"], kit_root=kit)
    assert rc_pre == 0
    capsys.readouterr()

    # Post-verb --verbose is forwarded as op_args; the dispatcher must not
    # treat it as a routing failure (no "vault-scoped" message).
    rc_post = cli.main(["prep-digest", "--verbose"], kit_root=kit)
    err = capsys.readouterr().err
    # The "outcome verbs are vault-scoped" message must NOT appear — the
    # dispatcher reached _cmd_run regardless of where --verbose landed.
    assert "outcome verbs are vault-scoped" not in err
    # Either succeeds or fails with a dispatch-level message, not a routing one.
    assert rc_post in (0, cli.WIKI_ERROR_EXIT)


# -------------------------------------------------------------------------
# AC: unknown verb inside vault lists installed verb choices
# -------------------------------------------------------------------------


def test_wiki_verb_unknown_verb_inside_vault_lists_choices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inside a vault with ``outcomes: [prep-digest]``, ``wiki nonsense`` exits
    2 with argparse's native "invalid choice" prefix AND the installed-verb list.

    Pins spec §Outputs §1: "argparse's standard 'invalid choice' error fires
    with the canonical list of installed outcomes printed alongside".
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["nonsense"], kit_root=kit)
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err
    assert "prep-digest" in err


# -------------------------------------------------------------------------
# AC: "Operation names are not implicit verbs"
# -------------------------------------------------------------------------


def test_wiki_operation_name_not_implicit_verb(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki fixture-digest`` (bare operation name, not the declared verb)
    exits 2 with "invalid choice", NOT a silent rewrite.

    Pins spec AC "Operation names are not implicit verbs" and Invariant 8.
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["fixture-digest"], kit_root=kit)
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


# -------------------------------------------------------------------------
# AC: global commands still work outside vault
# -------------------------------------------------------------------------


def test_wiki_verb_global_commands_still_work_outside_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki --help`` and ``wiki --version`` work unchanged outside a vault.

    Pins spec §Outputs §1: "The built-in commands remain global."
    """
    monkeypatch.chdir(tmp_path)

    # --help exits 0.
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"], kit_root=None)
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "wiki" in out.lower()

    # --version exits 0.
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"], kit_root=None)
    assert exc_info.value.code == 0


# -------------------------------------------------------------------------
# AC: kit_root forwarded through recursive re-dispatch
# -------------------------------------------------------------------------


def test_wiki_verb_dispatch_forwards_kit_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``cli.main(["prep-digest"], kit_root=kit)`` resolves the operation from
    the overridden catalog, not the bundled resolver.

    Pins the recursive re-dispatch forwards ``kit_root`` so test seams survive.
    If ``kit_root`` were dropped during the rewrite, the call would fall back
    to the bundled catalog and either fail (fixture-digest not shipped) or
    dispatch the wrong operation.
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    rc = cli.main(["prep-digest"], kit_root=kit)
    assert rc == 0

    # The operation must have resolved from the overridden catalog.
    run_evts = _run_events(vault)
    assert run_evts, "expected at least one OperationRunEvent"
    assert run_evts[-1].operation == "fixture-digest"


# -------------------------------------------------------------------------
# AC: ArgumentParser.error() override only fires on top-level invalid choice
# -------------------------------------------------------------------------


def test_wiki_argparse_error_override_falls_through_for_non_invalid_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inside a vault, ``wiki run weekly-digest --bogus-flag`` (an argparse
    error that is NOT the top-level "invalid choice") exits 2 but stderr does
    NOT contain the installed-verb list suffix.

    Pins the narrow scope of the ``ArgumentParser.error()`` override: only the
    top-level "invalid choice" path gets the installed-verb list; every other
    argparse error stays untouched.

    Note: ``wiki run fixture-digest --bogus-flag`` flows through ``_cmd_run``
    and ``dispatch``; argparse itself does not fire for op_args because they
    are captured by ``argparse.REMAINDER``. We test with an argparse error
    on the ``run`` subparser itself — a missing required positional.
    Alternatively we provoke a top-level positional error by passing a
    completely broken invocation that the sub-parser reports.
    """
    kit = _build_kit(tmp_path)
    vault = _seed_vault_from_events(tmp_path, kit)
    monkeypatch.chdir(vault)

    # ``wiki run`` with no operation positional triggers argparse's
    # "required positional" error from the run subparser (not the top-level
    # "invalid choice"). The installed-verb list suffix must NOT appear.
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["run"], kit_root=kit)
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    # Must be an argparse error, NOT the installed-verb list.
    assert "prep-digest" not in err
